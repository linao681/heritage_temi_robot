"""通过 ROS2 Gateway 执行导览；所有状态机操作在同一个 asyncio loop。"""

import asyncio
from concurrent.futures import TimeoutError as ThreadTimeoutError
from functools import partial
import json
import math
import time
from threading import Lock, Thread

from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from std_msgs.msg import Int32, String
from std_srvs.srv import Trigger
from temi_interfaces.action import NavigateTo, Speak
from temi_interfaces.msg import NavigationStatus, PerceptionInput, RobotStatus
from temi_interfaces.srv import StopRobot, AskHeritage, SubmitQuestion

from .tour_config import TourConfig
from .tour_manager import OperationResult, TourManager
from .team_observation import (
    observation_requires_pause, simulation_team_controls, validate_team_decision_mode,
)
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
        self.navigation_send_guard = None

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
            if (client is self._navigation and self.navigation_send_guard is not None and
                    not self.navigation_send_guard()):
                return OperationResult(False, '导航资格已撤销，未提交 ROS Action', submitted=False)
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
        self.declare_parameter('team_decision_mode', 'business_script')
        self._team_decision_mode = validate_team_decision_mode(
            self.get_parameter('team_decision_mode').value)
        self._vision_team = None
        self._vision_team_received = 0.0
        self._vision_pause_pending = False
        self._vision_confirmed_route_index = None
        self._vision_expected_count = 0
        self._loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._loop.run_forever, name='heritage-tour', daemon=True)
        self._status = self.create_publisher(String, 'heritage/tour/status', 10)
        self._robot = _RosTourRobot(self, config)
        self._knowledge = self.create_client(AskHeritage, 'heritage/knowledge/ask',
                                             callback_group=ReentrantCallbackGroup())
        self._last_telemetry = None
        self._last_snapshot = None
        self._navigation_session_id = ''
        self._retired_sessions = set()
        self._fused = None
        self._speed_recovery = None
        self._used_recovery_decisions = set()
        self._recovery_interrupted_at = -math.inf
        self._assist = None
        if config.visitor_assist_enabled:
            self._expected_count = self.create_publisher(Int32, 'heritage/visitor/expected_count', 10)
        self._thread.start()
        asyncio.run_coroutine_threadsafe(self._initialize(), self._loop).result()
        self.create_subscription(RobotStatus, 'temi/robot_status', self._on_robot_status, 10)
        self.create_subscription(NavigationStatus, 'temi/navigation_status', self._on_navigation, 20)
        self.create_subscription(PerceptionInput, 'heritage/perception/fused', self._on_fused, 10)
        self.create_subscription(String, 'heritage/speed_control/status', self._on_speed, 10)
        interval = min(0.2, config.communication_timeout_sec / 2)
        if self._assist is not None:
            interval = min(interval, config.visitor_status_timeout_sec / 2)
            self.create_subscription(String, 'heritage/visitor/status', self._on_visitor_status, 10)
        self.create_timer(interval, self._on_timer, clock=Clock(clock_type=ClockType.STEADY_TIME))
        control_group = MutuallyExclusiveCallbackGroup()
        self.create_service(SubmitQuestion, 'heritage/tour/ask', self._on_question,
                            callback_group=control_group)
        self._sim_team = None
        self._sim_team_received = 0.0
        if simulation_team_controls(self._team_decision_mode):
            self.create_subscription(String, 'heritage/simulation/team_status',
                                     self._on_sim_team, 10)
        else:
            self.create_subscription(String, 'heritage/visitor/team_observation',
                                     self._on_vision_team, 10)
        controls = {
            'start': self._start_tour,
            'accept': partial(self._manager.consent, True),
            'refuse': partial(self._manager.consent, False),
            'pause': self._manager.pause,
            'pause_safety': self._pause_safety,
            'resume': self._manager.resume,
            'resume_safety': self._resume_safety,
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
        self._robot.navigation_send_guard = self._manager.navigation_send_permitted
        if self._config.visitor_assist_enabled:
            self._assist = VisitorAssist(self._manager,
                                         lambda count: self._expected_count.publish(Int32(data=count)),
                                         self._config.visitor_status_timeout_sec)

    def _publish(self, status):
        try:
            if self.context.ok():
                status['recovery_ack_id'] = self._recovery_ack(status)
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

    def _on_navigation(self, message):
        self._schedule(self._update_navigation, message.status, message.task_id)

    def _update_navigation(self, state, session_id):
        if state in ('start', 'calculating', 'going', 'reposing'):
            if session_id and session_id not in self._retired_sessions:
                if self._navigation_session_id and self._navigation_session_id != session_id:
                    self._retired_sessions.add(self._navigation_session_id)
                self._navigation_session_id = session_id
        elif session_id and session_id == self._navigation_session_id:
            self._retired_sessions.add(session_id)
            self._navigation_session_id = ''

    def _on_fused(self, message):
        self._schedule(self._update_fused, message, time.monotonic())

    def _update_fused(self, message, received_at):
        previous = self._fused
        ordered = previous is None or (
            message.sample_timestamp_monotonic_sec >= previous[0].sample_timestamp_monotonic_sec)
        self._fused = (message, received_at, ordered)
        if previous and not ordered:
            self._fused = (previous[0], received_at, False)
        evidence = self._speed_recovery[0] if self._speed_recovery is not None else None
        if (not ordered or not message.valid or message.safety_stop or message.group_state == 'lost' or
                isinstance(evidence, dict) and not self._recovery_sample_clear(
                    message, evidence, received_at)):
            self._recovery_interrupted_at = received_at

    def _on_speed(self, message):
        try:
            value = json.loads(message.data)
        except (TypeError, ValueError):
            value = None
        evidence = value.get('recovery') if isinstance(value, dict) and value.get('recovery_eligible') is True else None
        self._schedule(self._update_recovery, evidence, time.monotonic())

    def _update_recovery(self, evidence, received_at):
        self._speed_recovery = (evidence, received_at)

    def _pause_safety(self):
        return self._manager.safety_pause(self._navigation_session_id)

    @staticmethod
    def _recovery_sample_clear(sample, evidence, now):
        limit = evidence.get('input_timeout_sec')
        person = evidence.get('minimum_person_distance_m')
        laser = evidence.get('minimum_laser_distance_m')
        if any(type(value) not in (int, float) or not math.isfinite(value)
               for value in (limit, person, laser)):
            return False
        person_clear = ((sample.person_distance_valid and math.isfinite(sample.nearest_person_m) and
                         sample.nearest_person_m > person) or
                        sample.person_observation_state == 'NO_PERSON_OBSERVED')
        return (sample.valid and sample.position_valid and sample.communication_valid and
                sample.safety_stop_valid and not sample.safety_stop and not sample.navigation_error and
                not sample.navigating and not sample.explaining and sample.group_state != 'lost' and
                sample.stop_confirmed and sample.stop_confirmed_session_id == evidence.get('stopped_session_id') and
                sample.person_observation_valid and person_clear and
                sample.obstacle_distance_valid and math.isfinite(sample.obstacle_distance_m) and
                sample.obstacle_distance_m > laser and
                0 <= sample.sample_age_sec <= limit and
                0 <= now - sample.sample_timestamp_monotonic_sec <= limit)

    def _recovery_ack(self, status, *, consuming=False):
        if self._speed_recovery is None or self._fused is None:
            return ''
        evidence, received_at = self._speed_recovery
        eligible_states = ('PAUSED', 'NAVIGATING', 'RETURNING') if consuming else ('PAUSED',)
        if (status.get('team_recovery_required') and
                (not status.get('team_resume_confirmed') or
                 not self._manager._visitor_ready_to_resume())):
            return ''
        if (not isinstance(evidence, dict) or status['state'] not in eligible_states or
                status['pause_source'] != 'safety' or not status['connected'] or status['is_moving'] or
                not isinstance(evidence.get('decision_id'), str) or not evidence['decision_id'] or
                not status['paused_session_id'] or
                status['paused_session_id'] != evidence.get('stopped_session_id') or
                status['target'] != evidence.get('original_target') or
                evidence.get('manual_latched') is not False or evidence.get('error_latched') is not False):
            return ''
        fields = ('evidence_at', 'evidence_sample_id', 'sample_age_sec', 'clear_since', 'hold_sec',
                  'odom_age_sec', 'position_age_sec', 'input_timeout_sec',
                  'minimum_person_distance_m', 'minimum_laser_distance_m')
        if any(type(evidence.get(key)) not in (int, float) or not math.isfinite(evidence[key])
               for key in fields):
            return ''
        now = time.monotonic()
        sample, sample_received_at, ordered = self._fused
        observation_age = now - evidence['evidence_at']
        timeout = evidence['input_timeout_sec']
        if (not ordered or not 0 <= now - received_at <= 0.5 or
                not 0 <= now - sample_received_at <= 0.5 or not 0 <= observation_age <= 0.5 or
                self._last_telemetry is None or not 0 <= now - self._last_telemetry <= 0.5 or
                not 0 <= evidence['odom_age_sec'] + observation_age <= 0.5 or
                not 0 <= evidence['sample_age_sec'] + observation_age <= timeout or
                not 0 <= evidence['position_age_sec'] + observation_age <= timeout or
                evidence['clear_since'] < self._recovery_interrupted_at or
                not 0 < evidence['hold_sec'] <= evidence['evidence_at'] - evidence['clear_since'] or
                not 0 <= now - sample.sample_timestamp_monotonic_sec <= timeout or
                not 0 <= sample.sample_age_sec + now - sample_received_at <= timeout or
                sample.sample_timestamp_monotonic_sec < evidence['evidence_sample_id']):
            return ''
        if not self._recovery_sample_clear(sample, evidence, now):
            return ''
        return evidence['decision_id']

    def _resume_safety(self):
        status = self._manager.status()
        decision_id = self._recovery_ack(status)
        if (not decision_id or decision_id in self._used_recovery_decisions or
                not self._manager.resume_safety(status['paused_session_id'],
                    lambda: self._recovery_ack(self._manager.status(), consuming=True) == decision_id)):
            return False
        self._used_recovery_decisions.add(decision_id)
        return True

    def _update_robot_status(self, snapshot, frame):
        self._last_telemetry = self._loop.time()
        if snapshot['is_moving'] or not snapshot['connected']:
            self._recovery_interrupted_at = time.monotonic()
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
        if self._team_decision_mode == 'vision_conservative':
            self._check_vision_team_freshness()
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

    def _business_team_ready(self):
        team = self._sim_team
        age = time.monotonic() - self._sim_team_received
        return (isinstance(team, dict) and team.get('valid') is True and
                team.get('source') == 'gazebo_scripted_actors' and
                team.get('gathered') is True and 0 <= age <= 1.0)

    def _start_tour(self):
        if self._team_decision_mode == 'business_script':
            guard = lambda: (not self._manager.status()['team_recovery_required'] or
                             self._business_team_ready())
            return self._manager.start(visitor_guard=guard)
        return self._manager.start()

    def _on_sim_team(self, message):
        if not simulation_team_controls(self._team_decision_mode):
            return
        try:
            value = json.loads(message.data)
            if value.get('source') == 'gazebo_scripted_actors':
                self._sim_team = value
                self._sim_team_received = time.monotonic()
        except (ValueError, AttributeError):
            pass

    def _on_vision_team(self, message):
        now_ns = self.get_clock().now().nanoseconds
        try:
            value = json.loads(message.data)
        except (ValueError, TypeError):
            value = None
        self._vision_team = value
        self._vision_team_received = time.monotonic()
        if (isinstance(value, dict) and type(value.get('expected_count')) is int and
                value['expected_count'] >= 0):
            self._vision_expected_count = value['expected_count']
        if (self._vision_expected_count > 0 and
                observation_requires_pause(value, now_ns=now_ns)):
            self._schedule(self._pause_for_vision_uncertainty)

    def _check_vision_team_freshness(self):
        value = self._vision_team
        if not isinstance(value, dict) or self._vision_expected_count <= 0:
            return
        ros_stale = observation_requires_pause(
            value, now_ns=self.get_clock().now().nanoseconds)
        wall_stale = time.monotonic() - self._vision_team_received > 1.0
        if ros_stale or wall_stale:
            self._schedule(self._pause_for_vision_uncertainty)

    def _pause_for_vision_uncertainty(self):
        status = self._manager.status()
        if self._vision_confirmed_route_index == status['route_index']:
            return
        self._vision_confirmed_route_index = None
        if status['state'] not in ('NAVIGATING', 'RETURNING') or self._vision_pause_pending:
            return
        self._vision_pause_pending = self._manager.visitor_uncertain()

    def _on_control(self, name, action, request, response):
        if self._team_decision_mode == 'vision_conservative' and name == 'visitor_lost':
            response.success = False
            response.message = '视觉模式拒绝脚本掉队指令；状态由视觉观察器提供'
            return response
        team = self._sim_team
        if (self._team_decision_mode == 'business_script' and name == 'resume' and
                self._manager.status()['team_recovery_required'] and
                not self._business_team_ready()):
            response.success = False
            response.message = '游客尚未集合或队伍状态过期，保持暂停'
            return response
        with self._lock:
            if self._closed:
                response.message = '导览节点已关闭'
                return response
            future = asyncio.run_coroutine_threadsafe(self._dispatch(action), self._loop)
        try:
            response.success = future.result(timeout=self._config.communication_timeout_sec)
            if (response.success and name == 'resume' and
                    self._team_decision_mode == 'vision_conservative' and
                    self._vision_pause_pending):
                self._vision_confirmed_route_index = self._manager.status()['route_index']
                self._vision_pause_pending = False
                response.message = 'resume: 操作员已确认队伍并继续导览'
            else:
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
