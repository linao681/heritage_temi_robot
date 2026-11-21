"""ROS2 接口与统一机器人后端之间的网关；不直接调用 Android SDK。"""

import asyncio
from concurrent.futures import TimeoutError
from dataclasses import dataclass, field
from functools import partial
import math
from threading import Event, Lock, Thread

from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from temi_interfaces.action import NavigateTo, Speak
from temi_interfaces.msg import NavigationStatus, RobotStatus
from temi_interfaces.srv import StopRobot, SetNavigationSpeed

from .backend import TaskResult, TemiBackend


@dataclass(frozen=True)
class _Reservation:
    connection_epoch: int
    task_id: str
    blocked: Event = field(default_factory=Event)


class TemiGatewayNode(Node):
    """后端控制在独立 asyncio loop；ROS 执行器至少需要四个工作线程。"""

    def __init__(self, backend: TemiBackend, status_hz: float = 10.0):
        if not math.isfinite(status_hz) or status_hz <= 0:
            raise ValueError('status_hz 必须为正数')
        super().__init__('temi_gateway')
        self._backend = backend
        self._lock = Lock()
        self._active: dict[str, _Reservation] = {}
        self._stopping = False
        self._closed = False
        self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._loop.run_forever, name='temi-backend', daemon=True)
        self._thread.start()
        self._group = ReentrantCallbackGroup()
        self._robot_status = self.create_publisher(RobotStatus, 'temi/robot_status', 10)
        self._navigation_status = self.create_publisher(NavigationStatus, 'temi/navigation_status', 10)
        self._navigation = ActionServer(
            self, NavigateTo, 'temi/navigate_to', self._execute_navigation,
            callback_group=self._group, goal_callback=self._navigation_goal,
            cancel_callback=lambda _: CancelResponse.ACCEPT,
        )
        self._speech = ActionServer(
            self, Speak, 'temi/speak', self._execute_speech,
            callback_group=self._group, goal_callback=self._speech_goal,
            cancel_callback=lambda _: CancelResponse.ACCEPT,
        )
        self._stop = self.create_service(StopRobot, 'temi/stop', self._stop_robot,
                                         callback_group=self._group)
        self._speed = self.create_service(SetNavigationSpeed, 'temi/set_navigation_speed',
                                         self._set_navigation_speed, callback_group=self._group)
        self._timer = self.create_timer(1.0 / status_hz, self._publish_snapshot)
        try:
            connection = self._submit(self._backend.connect).result()
            if not connection.success:
                self.get_logger().warning(connection.message)
        except Exception as error:
            self.get_logger().error(f'连接后端失败: {error}')

    def _submit(self, start):
        """与 close 串行提交，不允许关闭后启动新的控制操作。"""
        with self._lock:
            if self._closed:
                raise RuntimeError('Gateway 已关闭')
            return asyncio.run_coroutine_threadsafe(start(), self._loop)

    def _reserve(self, kind):
        # 先预留每种 Action 的单一槽位，避免重复 execute 占满 ROS 工作线程。
        with self._lock:
            snapshot = self._backend.get_status()
            if (self._closed or kind in self._active or
                    (kind == 'navigation' and self._stopping) or not snapshot.connected):
                return GoalResponse.REJECT
            self._active[kind] = _Reservation(snapshot.connection_epoch, '')
            return GoalResponse.ACCEPT

    def _navigation_goal(self, request):
        if not request.location.strip() or not math.isfinite(request.timeout_sec) or request.timeout_sec <= 0:
            return GoalResponse.REJECT
        return self._reserve('navigation')

    def _speech_goal(self, request):
        if not request.text.strip():
            return GoalResponse.REJECT
        return self._reserve('speech')

    def _publish_snapshot(self):
        snapshot = self._backend.get_status()
        message = RobotStatus(
            connected=snapshot.connected, battery_percentage=snapshot.battery_percentage,
            x=snapshot.x, y=snapshot.y, yaw=snapshot.yaw,
            navigation_status=snapshot.navigation_status, current_location=snapshot.current_location,
            is_moving=snapshot.is_moving, error_message=snapshot.error_message,
        )
        message.header.frame_id = snapshot.frame_id
        message.header.stamp = self.get_clock().now().to_msg()
        self._robot_status.publish(message)

    def _navigation_feedback(self, goal, event):
        if not self.context.ok():
            return
        try:
            message = NavigationStatus(task_id=event.task_id, target=event.target,
                                       status=event.status, description=event.description)
            message.header.frame_id = self._backend.get_status().frame_id
            message.header.stamp = self.get_clock().now().to_msg()
            self._navigation_status.publish(message)
        except Exception as error:
            self.get_logger().warning(f'发布导航状态失败: {error}')
        self._publish_action_feedback(
            goal, NavigateTo.Feedback(status=event.status, description=event.description),
        )

    def _speech_feedback(self, goal, event):
        self._publish_action_feedback(goal, Speak.Feedback(status=event.status))

    def _publish_action_feedback(self, goal, message):
        # ROS 反馈发布失败不能中断后端控制协程或跳过其运动/语音清理。
        try:
            if self.context.ok():
                goal.publish_feedback(message)
        except Exception as error:
            self.get_logger().warning(f'发布 Action 反馈失败: {error}')

    async def _run_operation(self, start, cancel, reservation):
        """由后端 loop 取消协程，并在槽位释放前等待其 finally 清理。"""
        async def start_if_allowed():
            # STOP 可能发生在 ROS 接受导航后、后端开始导航前。
            if reservation.blocked.is_set():
                return TaskResult(False, 'STOP 已阻止导航启动')
            if cancel.is_set():
                return TaskResult(False, '任务已取消')
            # 此检查与控制操作在后端同一 loop：旧连接的 Goal 不得重放。
            snapshot = self._backend.get_status()
            if not snapshot.connected or snapshot.connection_epoch != reservation.connection_epoch:
                return TaskResult(False, '机器人连接已变化，旧任务不会重发')
            return await start()

        task = asyncio.create_task(start_if_allowed())
        try:
            while not task.done():
                if cancel.is_set():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                    return TaskResult(False, '任务已取消')
                await asyncio.wait({task}, timeout=0.02)
            return task.result()
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    def _execute(self, kind, goal, start, result_type):
        cancel = Event()
        try:
            try:
                with self._lock:
                    reservation = self._active[kind]
                if goal.is_cancel_requested:
                    cancel.set()
                if kind == 'navigation':
                    reservation = _Reservation(reservation.connection_epoch, bytes(goal.goal_id.uuid).hex(),
                                              reservation.blocked)
                    with self._lock:
                        self._active[kind] = reservation
                future = self._submit(partial(self._run_operation, start, cancel, reservation))
                while True:
                    if goal.is_cancel_requested:
                        cancel.set()
                    try:
                        result = future.result(timeout=0.02)
                        break
                    except TimeoutError:
                        if future.done():
                            raise
            except Exception as error:
                result = TaskResult(False, str(error) or '后端任务已终止')
            if goal.is_cancel_requested:
                goal.canceled()
                return result_type(success=False, message='任务已取消')
            if result.success:
                goal.succeed()
            else:
                goal.abort()
            return result_type(success=result.success, message=result.message)
        finally:
            with self._lock:
                self._active.pop(kind, None)

    def _execute_navigation(self, goal):
        request = goal.request
        start = partial(self._backend.navigate_to, request.location, request.timeout_sec,
                        task_id=bytes(goal.goal_id.uuid).hex(),
                        feedback=partial(self._navigation_feedback, goal))
        return self._execute('navigation', goal, start, NavigateTo.Result)

    def _execute_speech(self, goal):
        start = partial(self._backend.speak, goal.request.text,
                        task_id=bytes(goal.goal_id.uuid).hex(),
                        feedback=partial(self._speech_feedback, goal))
        return self._execute('speech', goal, start, Speak.Result)


    def _set_navigation_speed(self, request, response):
        speed = float(request.target_speed_mps)
        if (not math.isfinite(speed) or not 0.3 <= speed <= 0.8 or
                not request.command_id.strip() or not request.navigation_session_id.strip()):
            response.success = False
            response.message = '无效速度、命令 ID 或导航会话 ID'
            response.sdk_return_code = -1
            return response
        with self._lock:
            active = self._active.get('navigation')
            if (active is None or active.blocked.is_set() or active.task_id != request.navigation_session_id or
                    self._stopping or 'speech' in self._active):
                response.success = False
                response.message = '导航会话不匹配或当前任务禁止调速'
                response.sdk_return_code = -1
                return response
        try:
            result = self._submit(partial(self._backend.set_navigation_speed, speed,
                                          command_id=request.command_id,
                                          navigation_session_id=request.navigation_session_id,
                                          control_reason=request.control_reason)).result()
        except Exception as error:
            result = TaskResult(False, str(error) or '调速后端失败')
        response.success = result.success
        response.message = result.message
        import re
        match = re.search(r'sdk_code=(-?\d+)', result.message)
        response.sdk_return_code = int(match.group(1)) if match else (-2 if result.success else -1)
        return response

    def _stop_robot(self, request, response):
        if not request.stop:
            response.success = False
            response.message = 'stop 必须为 true'
            return response
        with self._lock:
            if self._stopping:
                response.success = False
                response.message = '正在处理另一 STOP 请求，尚无停止确认'
                return response
            self._stopping = True
            if 'navigation' in self._active:
                self._active['navigation'].blocked.set()
        try:
            result = self._submit(self._backend.stop).result()
        except Exception as error:
            result = TaskResult(False, str(error) or '无法确认停止')
        finally:
            with self._lock:
                self._stopping = False
        response.success = result.success
        response.message = result.message
        return response

    async def _disconnect_and_cancel(self):
        try:
            await self._backend.disconnect()
        finally:
            pending = asyncio.all_tasks() - {asyncio.current_task()}
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    def close(self):
        """停止接收任务，断开后端并回收其 loop；可重复调用。"""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            asyncio.run_coroutine_threadsafe(self._disconnect_and_cancel(), self._loop).result()
        except Exception as error:
            self.get_logger().warning(f'断开后端失败: {error}')
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join()
            self._loop.close()

    def destroy_node(self):
        """在调用方停止 ROS executor 后释放 ActionServer 和节点资源。"""
        self.close()
        self._navigation.destroy()
        self._speech.destroy()
        return super().destroy_node()
