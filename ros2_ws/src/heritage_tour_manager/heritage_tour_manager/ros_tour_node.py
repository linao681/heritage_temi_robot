"""通过 ROS2 Gateway 执行导览；所有状态机操作在同一个 asyncio loop。"""

import asyncio
from concurrent.futures import TimeoutError as ThreadTimeoutError
from functools import partial
import json
from threading import Lock, Thread

from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from std_msgs.msg import Int32, String
from std_srvs.srv import Trigger
from temi_interfaces.action import NavigateTo, Speak
from temi_interfaces.msg import RobotStatus
from temi_interfaces.srv import StopRobot, AskHeritage, SubmitQuestion

from .tour_config import TourConfig
from .tour_manager import OperationResult, TourManager
from .visitor_assist import VisitorAssist


async def _wait_future(future, deadline=None):
    """rclpy Future 由 ROS executor 完成；轮询不会取消尚未返回的 Goal。"""
    loop = asyncio.get_running_loop()
    while not future.done():
        if deadline is not None and loop.time() >= deadline:
            raise asyncio.TimeoutError
        await asyncio.sleep(0.01)
    return future.result()


async def _wait_ready(ready, deadline):
    loop = asyncio.get_running_loop()
    while not ready():
        if loop.time() >= deadline:
            raise asyncio.TimeoutError
        await asyncio.sleep(0.01)


class _RosTourRobot:
    """实现状态机所需的机器人操作，仅使用 ROS Action 和 Service。"""

    def __init__(self, node, config):
        self._node = node
        self._config = config
        group = ReentrantCallbackGroup()
        self._navigation = ActionClient(node, NavigateTo, 'temi/navigate_to', callback_group=group)
        self._speech = ActionClient(node, Speak, 'temi/speak', callback_group=group)
        self._stop_client = node.create_client(StopRobot, 'temi/stop', callback_group=group)
        self._cleanup = {}

    async def _settle_goal(self, acceptance, goal, result):
        """取消时 Goal 可能尚未被接受；收到迟到的接受响应也必须取消它。"""
        try:
            if goal is None:
                goal = await _wait_future(acceptance)
            if not goal.accepted:
                return True
            if result is None:
                result = goal.get_result_async()
            if not result.done():
                cancel = goal.cancel_goal_async()
                try:
                    deadline = asyncio.get_running_loop().time() + self._config.communication_timeout_sec
                    await _wait_future(cancel, deadline)
                except asyncio.TimeoutError:
                    # 即使取消响应丢失，仍须等待 Action 的终态才能解除旧任务占用。
                    pass
            response = await _wait_future(result)
            return response.status in (GoalStatus.STATUS_SUCCEEDED, GoalStatus.STATUS_CANCELED, GoalStatus.STATUS_ABORTED)
        except Exception as error:
            self._node.get_logger().error(f'无法确认旧 Action 已终止: {error}')
            return False

    async def _cancel_action(self, client, acceptance, goal, result):
        if acceptance is None:
            return True
        task = asyncio.create_task(self._settle_goal(acceptance, goal, result))
        self._cleanup[client] = task
        # 前台有界等待；迟到的 Goal 响应仍由该任务处理，在此之前不发送同类新 Goal。
        await asyncio.wait({task}, timeout=2 * self._config.communication_timeout_sec)
        return task.done() and task.result()

    async def _action(self, client, request, timeout):
        loop = asyncio.get_running_loop()
        communication = self._config.communication_timeout_sec
        deadline = loop.time() + timeout
        acceptance = goal = result = None
        try:
            old = self._cleanup.get(client)
            if old is not None:
                await asyncio.wait({old}, timeout=min(communication, timeout))
                if not old.done() or not old.result():
                    return OperationResult(False, '上一 Action 尚未确认终止', False)
                self._cleanup.pop(client)
            await _wait_ready(client.server_is_ready, min(deadline, loop.time() + communication))
            acceptance = client.send_goal_async(request)
            goal = await _wait_future(acceptance, min(deadline, loop.time() + communication))
            if not goal.accepted:
                return OperationResult(False, 'ROS Action 拒绝了任务')
            result = goal.get_result_async()
            response = await _wait_future(result, deadline)
            if response.status not in (GoalStatus.STATUS_SUCCEEDED, GoalStatus.STATUS_CANCELED, GoalStatus.STATUS_ABORTED):
                self._cleanup[client] = asyncio.create_task(self._settle_goal(acceptance, goal, result))
                return OperationResult(False, 'ROS Action 返回非终态，尚未确认终止', False)
            return OperationResult(
                response.status == GoalStatus.STATUS_SUCCEEDED and response.result.success,
                response.result.message,
            )
        except asyncio.CancelledError:
            if not await self._cancel_action(client, acceptance, goal, result):
                raise RuntimeError('旧 ROS Action 尚未确认终止')
            raise
        except asyncio.TimeoutError:
            confirmed = await self._cancel_action(client, acceptance, goal, result)
            return OperationResult(False, 'ROS Action 请求或执行超时' if confirmed else
                                   'ROS Action 超时且旧任务未确认终止', confirmed)
        except Exception as error:
            confirmed = await self._cancel_action(client, acceptance, goal, result)
            return OperationResult(False, f'ROS Action 失败: {error}', confirmed)

    async def navigate(self, location, timeout_sec):
        return await self._action(self._navigation, NavigateTo.Goal(
            location=location, timeout_sec=timeout_sec), timeout_sec)

    async def speak(self, text):
        return await self._action(self._speech, Speak.Goal(text=text), self._config.speech_timeout_sec)

    async def stop(self):
        deadline = asyncio.get_running_loop().time() + self._config.communication_timeout_sec
        try:
            await _wait_ready(self._stop_client.service_is_ready, deadline)
            response = await _wait_future(self._stop_client.call_async(StopRobot.Request(stop=True)), deadline)
            return OperationResult(response.success, response.message)
        except asyncio.TimeoutError:
            return OperationResult(False, 'ROS STOP 请求超时，未确认停止')
        except Exception as error:
            return OperationResult(False, f'ROS STOP 请求失败，未确认停止: {error}')

    async def shutdown(self):
        if self._cleanup:
            _, pending = await asyncio.wait(self._cleanup.values(), timeout=self._config.communication_timeout_sec)
            if pending:
                self._node.get_logger().warning('关闭时仍有 Action 未确认终止')
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

    def destroy(self):
        self._navigation.destroy()
        self._speech.destroy()


class HeritageTourNode(Node):
    """固定路线导览 ROS2 节点，状态以 JSON 字符串发布。"""

    def __init__(self, config: TourConfig):
        super().__init__('heritage_tour_manager')
        self._config = config
        self._lock = Lock()
        self._closed = False
        self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._loop.run_forever, name='heritage-tour', daemon=True)
        self._status = self.create_publisher(String, 'heritage/tour/status', 10)
        self._robot = _RosTourRobot(self, config)
        self._knowledge = self.create_client(AskHeritage, 'heritage/knowledge/ask',
                                             callback_group=ReentrantCallbackGroup())
        self._last_telemetry = None
        self._last_snapshot = None
        self._assist = None
        if config.visitor_assist_enabled:
            self._expected_count = self.create_publisher(Int32, 'heritage/visitor/expected_count', 10)
        self._thread.start()
        asyncio.run_coroutine_threadsafe(self._initialize(), self._loop).result()
        self.create_subscription(RobotStatus, 'temi/robot_status', self._on_robot_status, 10)
        interval = min(0.2, config.communication_timeout_sec / 2)
        if self._assist is not None:
            interval = min(interval, config.visitor_status_timeout_sec / 2)
            self.create_subscription(String, 'heritage/visitor/status', self._on_visitor_status, 10)
        self.create_timer(interval, self._on_timer, clock=Clock(clock_type=ClockType.STEADY_TIME))
        control_group = MutuallyExclusiveCallbackGroup()
        self.create_service(SubmitQuestion, 'heritage/tour/ask', self._on_question,
                            callback_group=control_group)
        controls = {
            'start': self._manager.start,
            'accept': partial(self._manager.consent, True),
            'refuse': partial(self._manager.consent, False),
            'pause': self._manager.pause,
            'resume': self._manager.resume,
            'cancel': self._manager.cancel,
            'visitor_lost': self._manager.visitor_lost,
            'manual_takeover': self._manager.manual_takeover,
            'finish_qa': self._manager.finish_qa,
        }
        if self._assist is not None:
            controls.update(start=self._assist.manual_start, cancel=self._assist.cancel,
                            manual_takeover=self._assist.manual_takeover, arm_visitor=self._assist.arm)
        for name, action in controls.items():
            self.create_service(Trigger, 'heritage/tour/' + name,
                                partial(self._on_control, name, action), callback_group=control_group)

    async def _initialize(self):
        self._manager = TourManager(self._robot, self._config, on_change=self._publish,
                                    qa_lookup=self._lookup_question)
        if self._config.visitor_assist_enabled:
            self._assist = VisitorAssist(self._manager,
                                         lambda count: self._expected_count.publish(Int32(data=count)),
                                         self._config.visitor_status_timeout_sec)

    def _publish(self, status):
        try:
            if self.context.ok():
                if self._assist is not None:
                    self._assist.sync_terminal()
                    status['visitor_assist'] = self._assist.snapshot()
                self._status.publish(String(data=json.dumps(status, ensure_ascii=False)))
        except Exception as error:
            self.get_logger().warning(f'导览状态发布失败: {error}')

    def _schedule(self, callback, *args):
        with self._lock:
            if not self._closed:
                self._loop.call_soon_threadsafe(callback, *args)

    def _on_robot_status(self, status):
        self._schedule(self._update_robot_status, {
            'connected': status.connected, 'battery_percentage': status.battery_percentage,
            'current_location': status.current_location, 'is_moving': status.is_moving,
        }, status.header.frame_id)

    def _update_robot_status(self, snapshot, frame):
        self._last_telemetry = self._loop.time()
        self._last_snapshot = snapshot
        self._manager.update_robot_status(**snapshot)
        if self._assist is not None:
            self._assist.robot_frame(frame)

    def _on_visitor_status(self, message):
        try:
            value = json.loads(message.data)
        except (ValueError, TypeError):
            value = None
        self._schedule(self._assist.observe, value)

    def _on_timer(self):
        self._schedule(self._tick)

    def _tick(self):
        if (self._last_snapshot is not None and self._last_snapshot['connected'] and
                self._loop.time() - self._last_telemetry >= self._config.communication_timeout_sec):
            self._last_snapshot = {**self._last_snapshot, 'connected': False}
            self._manager.update_robot_status(**self._last_snapshot)
        if self._assist is not None:
            self._assist.tick()
        self._publish(self._manager.status())

    async def _dispatch(self, action):
        result = action()
        if self._assist is not None:
            self._publish(self._manager.status())
        return result

    async def _lookup_question(self, question, exhibit, level):
        deadline = self._loop.time() + self._config.communication_timeout_sec
        await _wait_ready(self._knowledge.service_is_ready, deadline)
        future = self._knowledge.call_async(AskHeritage.Request(question=question, exhibit=exhibit, level=level))
        try:
            response = await _wait_future(future, deadline)
            return {'found': response.found, 'entry_id': response.entry_id,
                    'answer': response.answer, 'source': json.loads(response.source_json)}
        finally:
            if not future.done():
                future.cancel()

    def _on_question(self, request, response):
        with self._lock:
            if self._closed:
                response.message = '导览节点已关闭'
                return response
            action = partial(self._manager.submit_question, request.question, request.exhibit,
                             request.level or 'basic')
            future = asyncio.run_coroutine_threadsafe(self._dispatch(action), self._loop)
        try:
            response.accepted = future.result(timeout=self._config.communication_timeout_sec)
            response.message = '已接受文字提问' if response.accepted else '当前不接受提问或参数无效'
        except ThreadTimeoutError:
            future.cancel()
            response.message = '提问确认超时'
        return response

    def _on_control(self, name, action, request, response):
        with self._lock:
            if self._closed:
                response.message = '导览节点已关闭'
                return response
            future = asyncio.run_coroutine_threadsafe(self._dispatch(action), self._loop)
        try:
            response.success = future.result(timeout=self._config.communication_timeout_sec)
            response.message = f'{name}: 已接受' if response.success else f'{name}: 当前状态不允许'
        except ThreadTimeoutError:
            future.cancel()
            response.message = f'{name}: 未在通信超时内确认'
        except Exception as error:
            response.message = f'{name}: {error}'
        return response

    async def _shutdown(self):
        try:
            if self._assist is not None:
                self._assist.disarm()
            await self._manager.shutdown()
        finally:
            await self._robot.shutdown()
            pending = asyncio.all_tasks() - {asyncio.current_task()}
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    def close(self):
        """先停止导览并确认旧任务，再结束工作 loop；可重复调用。"""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop).result()
        except Exception as error:
            self.get_logger().warning(f'导览关闭失败: {error}')
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join()
            self._loop.close()

    def destroy_node(self):
        self.close()
        self._robot.destroy()
        return super().destroy_node()
