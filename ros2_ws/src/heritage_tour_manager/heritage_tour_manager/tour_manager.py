"""独立导览状态机；不导入 temi SDK、ROS2 或任何具体机器人后端。"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, Protocol

from .tour_config import TourConfig


LOGGER = logging.getLogger(__name__)


class TourState(str, Enum):
    IDLE = 'IDLE'
    GREETING = 'GREETING'
    WAITING_CONSENT = 'WAITING_CONSENT'
    PLANNING = 'PLANNING'
    NAVIGATING = 'NAVIGATING'
    EXPLAINING = 'EXPLAINING'
    QA = 'QA'
    PAUSED = 'PAUSED'
    RETURNING = 'RETURNING'
    COMPLETED = 'COMPLETED'
    ERROR = 'ERROR'


@dataclass(frozen=True)
class OperationResult:
    success: bool
    message: str
    termination_confirmed: bool = True
    submitted: bool = True


class TourRobot(Protocol):
    async def navigate(self, location: str, timeout_sec: float) -> OperationResult: ...
    async def speak(self, text: str) -> OperationResult: ...
    async def stop(self) -> OperationResult: ...


class _TourEnd(Exception):
    def __init__(self, state: TourState, outcome: str, reason: str):
        self.state, self.outcome, self.reason = state, outcome, reason


class _LowBattery(Exception):
    pass


class TourManager:
    """全部控制及运行方法由同一 asyncio loop 串行执行。"""

    _PRIORITY = {'team_pause': 0, 'safety_pause': 1, 'pause': 2, 'low': 3,
                 'cancel': 4, 'manual': 5, 'critical': 6, 'disconnect': 7}

    def __init__(self, robot: TourRobot, config: TourConfig,
                 on_change: Callable[[dict], None] | None = None, qa_lookup=None):
        self.robot, self.config, self.on_change = robot, config, on_change
        self.state = TourState.IDLE
        self.reason = '等待游客'
        self.outcome = 'idle'
        self.route_index = -1
        self.target = ''
        self.visited: list[str] = []
        self.history: list[dict] = []
        self.error_count = 0
        self.connected = False
        self.battery_percentage = -1.0
        self.current_location = ''
        self.is_moving = False
        self._task: asyncio.Task | None = None
        self._started: float | None = None
        self._ended: float | None = None
        self._control: tuple[str, str] | None = None
        self._control_event = asyncio.Event()
        self._consent_event = asyncio.Event()
        self._resume_event = asyncio.Event()
        self._pause_source = ''
        self._paused_session_id = ''
        self._pending_safety_session_id = ''
        self._recovery_guard: Callable[[], bool] | None = None
        self._qa_event = asyncio.Event()
        self._accepted = False
        self._returning_low = False
        self._safe_return_completed = False
        self._visitor_guard: Callable[[], bool] | None = None
        self._team_recovery_required = False
        self._team_resume_confirmed = False
        self.qa_lookup = qa_lookup
        self._qa_open = False
        self._qa_question = None
        self._qa_result = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def consent_accepted(self) -> bool:
        return self._accepted

    @property
    def returning_low(self) -> bool:
        return self._returning_low

    def status(self) -> dict:
        """复制状态及历史，避免观察者修改任务内部数据。"""
        elapsed = 0.0 if self._started is None else (self._ended or time.monotonic()) - self._started
        return {
            'state': self.state.value, 'reason': self.reason, 'outcome': self.outcome,
            'route_index': self.route_index, 'visited': list(self.visited),
            'target': self.target,
            'pause_source': self._pause_source,
            'paused_session_id': self._paused_session_id,
            'current_location': self.current_location, 'connected': self.connected,
            'battery_percentage': self.battery_percentage, 'is_moving': self.is_moving,
            'error_count': self.error_count, 'elapsed_sec': round(elapsed, 3),
            'team_recovery_required': self._team_recovery_required,
            'team_resume_confirmed': self._team_resume_confirmed,
            'safe_return_completed': self._safe_return_completed,
            'qa_waiting': self.state is TourState.QA and self._qa_open and not self._qa_event.is_set(),
            'qa_result': self._qa_result,
            'history': [dict(event) for event in self.history],
        }

    def _emit(self):
        if self.on_change is not None:
            try:
                self.on_change(self.status())
            except Exception as error:
                LOGGER.warning('导览状态观察者异常: %s', type(error).__name__)

    def _transition(self, state: TourState, reason: str):
        """显式写入每个状态转换及相对开始时间。"""
        self.state, self.reason = state, reason
        self.history.append({'state': state.value, 'reason': reason,
                             'elapsed_sec': self.status()['elapsed_sec']})
        LOGGER.info('%s: %s', state.value, reason)
        self._emit()

    def start(self, *, visitor_guard: Callable[[], bool] | None = None) -> bool:
        if self.running or not self.connected or self.is_moving:
            return False
        self._started, self._ended = time.monotonic(), None
        self.outcome = 'running'
        self.route_index, self.error_count = -1, 0
        self.target = ''
        self.visited.clear()
        self.history.clear()
        self._returning_low = self._safe_return_completed = False
        self._accepted = False
        self._qa_open = False
        self._qa_question = self._qa_result = None
        self._visitor_guard = visitor_guard
        self._team_recovery_required = self._team_resume_confirmed = False
        self._control = None
        self._pause_source = self._paused_session_id = self._pending_safety_session_id = ''
        self._recovery_guard = None
        for event in (self._control_event, self._consent_event, self._resume_event, self._qa_event):
            event.clear()
        self._transition(TourState.IDLE, '开始新导览任务')
        self._task = asyncio.create_task(self._run())
        if 0 <= self.battery_percentage <= self.config.low_battery_threshold:
            self._request('low', '低电量，停止常规导览')
        return True

    def consent(self, accepted: bool) -> bool:
        if self.state is not TourState.WAITING_CONSENT or self._consent_event.is_set():
            return False
        if accepted and self._visitor_guard is not None and not self._visitor_guard():
            return False
        self._accepted = accepted
        self._consent_event.set()
        return True

    def _request(self, command: str, reason: str) -> bool:
        if not self.running:
            return False
        if self._control is not None and self._PRIORITY[command] <= self._PRIORITY[self._control[0]]:
            return False
        self._control = (command, reason)
        self._control_event.set()
        return True

    def pause(self) -> bool:
        if self.state is TourState.PAUSED and self._pause_source == 'safety':
            return self._request('pause', '用户暂停')
        return self.state is not TourState.PAUSED and self._request('pause', '用户暂停')

    def safety_pause(self, session_id: str) -> bool:
        if (not session_id or self.state not in (TourState.NAVIGATING, TourState.RETURNING) or
                not self._request('safety_pause', '导航安全停车')):
            return False
        self._pending_safety_session_id = session_id
        return True

    def _request_visitor_pause(self, reason: str) -> bool:
        if self._team_recovery_required:
            return True
        if self._control is not None:
            if self._control[0] != 'safety_pause':
                return False
            accepted = True
        elif self.state is TourState.PAUSED:
            if self._pause_source != 'safety':
                return False
            accepted = True
        else:
            accepted = self._request('team_pause', reason)
        if accepted:
            self._team_recovery_required = True
            self._team_resume_confirmed = False
            self.error_count += 1
            self._emit()
        return accepted

    def visitor_lost(self) -> bool:
        return self._request_visitor_pause('游客掉队，等待重新集合')

    def visitor_uncertain(self) -> bool:
        return self._request_visitor_pause('团队视觉信息不完整，安全等待人工确认')

    def resume(self) -> bool:
        if not self._can_resume():
            return False
        if self._pause_source == 'safety':
            if not self._team_recovery_required:
                return False
            self._team_resume_confirmed = True
            self._emit()
            return True
        if self._team_recovery_required:
            self._team_resume_confirmed = True
        self._resume_event.set()
        self._emit()
        return True

    def resume_safety(self, session_id: str, guard: Callable[[], bool]) -> bool:
        if (not self._can_resume() or self._pause_source != 'safety' or
                session_id != self._paused_session_id or not guard() or
                self._team_recovery_required and not self._team_resume_confirmed):
            return False
        self._recovery_guard = guard
        self._resume_event.set()
        return True

    def _can_resume(self) -> bool:
        return (self.running and self.state is TourState.PAUSED and self._control is None and
                not self._resume_event.is_set() and self.connected and not self.is_moving and
                self._visitor_ready_to_resume())

    def navigation_send_permitted(self, *, consume=True):
        """Validate the current control and recovery immediately before goal submission."""
        if self._control is not None:
            return False
        if (self._team_recovery_required and not self._returning_low and
                (not self._team_resume_confirmed or not self._visitor_ready_to_resume())):
            self._team_resume_confirmed = False
            if self._pause_source == 'safety':
                self._resume_event.clear()
                self._recovery_guard = None
                self._pending_safety_session_id = self._paused_session_id
                self._request('safety_pause', '游客集合确认失效，继续等待人工确认')
            return False
        if self._pause_source != 'safety':
            if consume:
                self._clear_team_recovery()
            return True
        if (not self._resume_event.is_set() or not self.connected or self.is_moving or
                not self._visitor_ready_to_resume() or self._recovery_guard is None or
                not self._recovery_guard()):
            self._pending_safety_session_id = self._paused_session_id
            self._request('safety_pause', '恢复资格已撤销，继续等待安全条件')
            return False
        if consume:
            self._pause_source = self._paused_session_id = ''
            self._recovery_guard = None
            self._resume_event.clear()
            self._clear_team_recovery()
        return True

    def _visitor_ready_to_resume(self) -> bool:
        ready = self._visitor_guard is None or self._returning_low or self._visitor_guard()
        if not ready and self._team_recovery_required:
            self._team_resume_confirmed = False
        return ready

    def _clear_team_recovery(self):
        self._team_recovery_required = False
        self._team_resume_confirmed = False

    def invalidate_visitor_resume(self):
        """辅助队伍状态失效时撤销尚未消费的恢复请求。"""
        if self._visitor_guard is not None and not self._returning_low and self.state is TourState.PAUSED:
            self._resume_event.clear()
            if self._team_recovery_required:
                self._team_resume_confirmed = False

    def visitor_source_lost(self) -> bool:
        return self._request('disconnect', '辅助导览 Mock 机器人来源失效')

    def cancel(self) -> bool:
        return self._request('cancel', '用户取消导览')

    def manual_takeover(self) -> bool:
        return self._request('manual', '人工接管')

    def finish_qa(self) -> bool:
        if self.state is not TourState.QA or not self._qa_open or self._qa_event.is_set():
            return False
        self._qa_event.set()
        return True

    def submit_question(self, question: str, exhibit='', level='basic') -> bool:
        """互动区一次仅接收一个明确文本问题，拒绝迟到或重复请求。"""
        if (self.state is not TourState.QA or not self._qa_open or self._qa_event.is_set() or
                self._control is not None or not isinstance(question, str) or not question.strip() or
                len(question) > 256 or level not in ('basic', 'child', 'advanced') or
                exhibit not in ('', 'exhibit_01', 'exhibit_02', 'exhibit_03', 'exhibit_04', 'exhibit_05')):
            return False
        self._qa_question = (question, exhibit, level)
        self._qa_event.set()
        return True

    async def _answer_question(self):
        """查询超时或服务不可用时播报明确的回退提示，不生成事实。"""
        try:
            if self.qa_lookup is None:
                raise RuntimeError('知识服务不可用')
            result = await asyncio.wait_for(self.qa_lookup(*self._qa_question),
                                            self.config.communication_timeout_sec)
            if (not isinstance(result, dict) or not isinstance(result.get('answer'), str) or
                    not result['answer'].strip() or type(result.get('found')) is not bool or
                    not isinstance(result.get('source'), dict) or
                    (result['found'] and not result['source'].get('url'))):
                raise ValueError('无效知识服务响应')
        except Exception:
            result = {'found': False, 'entry_id': '', 'answer': '知识服务暂不可用，请向工作人员咨询。', 'source': {}}
        self._qa_result = {**result, 'spoken': False}
        self._emit()
        spoken = await self.robot.speak(result['answer'])
        if spoken.success:
            self._qa_result = {**result, 'spoken': True}
            self._emit()
        return spoken

    def update_robot_status(self, *, connected: bool, battery_percentage: float,
                            current_location: str, is_moving: bool):
        changed = (connected, battery_percentage, current_location, is_moving) != (
            self.connected, self.battery_percentage, self.current_location, self.is_moving)
        self.connected, self.battery_percentage = connected, battery_percentage
        self.current_location, self.is_moving = current_location, is_moving
        if self.running:
            if not connected:
                self._request('disconnect', '机器人通信中断，停止状态未确认')
            elif self._returning_low and battery_percentage == 0:
                self._request('critical', '返回途中电量耗尽，需要人工接管')
            elif not self._returning_low and 0 <= battery_percentage <= self.config.low_battery_threshold:
                self._request('low', '低电量，停止常规导览')
        if changed:
            self._emit()

    async def _checkpoint(self, stopped: bool = False):
        """每个阶段前处理高优先级控制；暂停后仍执行当前段而不是跳过。"""
        while self._control is not None:
            command, reason = self._control
            if command != 'disconnect' and (self.is_moving or command == 'manual') and not stopped:
                # 保留当前控制优先级直至 STOP 结算；等待中更高优先级命令仍可替换。
                result = await self.robot.stop()
                if not result.success:
                    raise _TourEnd(TourState.ERROR, 'error', '停车未确认: ' + result.message)
                stopped = True
                command, reason = self._control
            self._control = None
            self._control_event.clear()
            if command in ('pause', 'safety_pause', 'team_pause'):
                self._resume_event.clear()
                self._recovery_guard = None
                self._pause_source = {'pause': 'manual', 'team_pause': 'team',
                                      'safety_pause': 'safety'}[command]
                self._paused_session_id = (self._pending_safety_session_id
                                           if command == 'safety_pause' else '')
                self._transition(TourState.PAUSED, reason)
                # 等待显式恢复，低电量、取消、人工接管与断线仍可中断暂停。
                while True:
                    resume = asyncio.create_task(self._resume_event.wait())
                    other = asyncio.create_task(self._control_event.wait())
                    try:
                        await asyncio.wait({resume, other}, return_when=asyncio.FIRST_COMPLETED)
                    finally:
                        for task in (resume, other):
                            task.cancel()
                        await asyncio.gather(resume, other, return_exceptions=True)
                    if self._control is not None or (
                            self._resume_event.is_set() and self.connected and not self.is_moving and
                            self._visitor_ready_to_resume() and
                            (self._pause_source != 'safety' or
                             self._recovery_guard is not None and self._recovery_guard())):
                        break
                    # 恢复请求与感知失效竞态：旧请求必须丢弃，不等待数据变好后自动执行。
                    self._resume_event.clear()
                    self._recovery_guard = None
                if self._control is None and self._pause_source == 'safety':
                    # Keep the exact paused session and qualification until the
                    # operation coroutine is about to send the resumed goal.
                    return
                self._pause_source = self._paused_session_id = ''
                self._recovery_guard = None
            elif command == 'low':
                raise _LowBattery(reason)
            elif command in ('disconnect', 'critical'):
                raise _TourEnd(TourState.ERROR, 'error', reason)
            elif command == 'manual':
                raise _TourEnd(TourState.IDLE, 'manual_takeover', reason)
            else:
                raise _TourEnd(TourState.IDLE, 'canceled', reason)

    async def _operate(self, state: TourState, reason: str,
                       operation: Callable[[], Awaitable[OperationResult]], *, motion=False):
        """异步执行单段任务，任何控制都先等待取消清理，导航需确认 STOP。"""
        while True:
            await self._checkpoint()
            self._transition(state, reason)
            operation_started = False

            async def begin_operation():
                nonlocal operation_started
                # A control queued after the transition can run before the child task.
                deferred_gate = motion and getattr(self.robot, 'navigation_send_guard', None) is not None
                if not self.navigation_send_permitted(consume=not deferred_gate):
                    return None
                operation_started = True
                return await operation()

            task = asyncio.create_task(begin_operation())
            interrupt = asyncio.create_task(self._control_event.wait())
            try:
                await asyncio.wait({task, interrupt}, return_when=asyncio.FIRST_COMPLETED)
                if self._control is not None:
                    stop_result = None
                    was_done = task.done()
                    never_submitted = (was_done and not task.cancelled() and task.exception() is None and
                                       isinstance(task.result(), OperationResult) and not task.result().submitted)
                    finished_successfully = (operation_started and was_done and not task.cancelled() and
                                             task.exception() is None and task.result().success)
                    if (motion and operation_started and not never_submitted and not finished_successfully) or self.is_moving:
                        stop_result = await self.robot.stop()
                    if not task.done():
                        task.cancel()
                    settled, = await asyncio.gather(task, return_exceptions=True)
                    if stop_result is not None and not stop_result.success:
                        raise _TourEnd(TourState.ERROR, 'error', '中断导航时停车未确认: ' + stop_result.message)
                    if isinstance(settled, Exception):
                        raise _TourEnd(TourState.ERROR, 'error', '任务终止未确认: ' + str(settled))
                    if isinstance(settled, OperationResult) and (
                            not settled.termination_confirmed or (was_done and not settled.success and settled.submitted)):
                        raise _TourEnd(TourState.ERROR, 'error', '中断前任务失败或终止未确认: ' + settled.message)
                    await self._checkpoint(stopped=stop_result is not None)
                    continue
                try:
                    result = task.result()
                except Exception as error:
                    detail = str(error)
                    if motion:
                        stopped = await self.robot.stop()
                        if not stopped.success:
                            detail += '; 停车未确认: ' + stopped.message
                    raise _TourEnd(TourState.ERROR, 'error', f'{reason}异常: {detail}') from error
                if not result.success:
                    detail = result.message
                    if motion:
                        stopped = await self.robot.stop()
                        if not stopped.success:
                            detail += '; 停车未确认: ' + stopped.message
                    raise _TourEnd(TourState.ERROR, 'error', f'{reason}失败: {detail}')
                return
            finally:
                interrupt.cancel()
                if not task.done():
                    task.cancel()
                await asyncio.gather(interrupt, task, return_exceptions=True)

    async def _wait_signal(self, state: TourState, reason: str, event: asyncio.Event, timeout: float):
        """等待游客明确反馈或超时；暂停不会在后台自行推进。"""
        while True:
            await self._checkpoint()
            self._transition(state, reason)
            signal = asyncio.create_task(event.wait())
            control = asyncio.create_task(self._control_event.wait())
            try:
                await asyncio.wait({signal, control}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
                if self._control is None:
                    return event.is_set()
            finally:
                for task in (signal, control):
                    task.cancel()
                await asyncio.gather(signal, control, return_exceptions=True)

    async def _normal_tour(self):
        await self._operate(TourState.GREETING, '迎宾', lambda: self.robot.speak(self.config.greeting_text))
        has_consent = await self._wait_signal(TourState.WAITING_CONSENT, '等待游客同意',
                                              self._consent_event, self.config.consent_timeout_sec)
        await self._checkpoint()
        if not has_consent:
            raise _TourEnd(TourState.IDLE, 'consent_timeout', '游客未在期限内同意')
        if not self._accepted:
            raise _TourEnd(TourState.IDLE, 'declined', '游客拒绝导览')
        self._transition(TourState.PLANNING, '确定固定导览路线')
        for index, exhibit in enumerate(self.config.route):
            self.route_index = index
            self.target = exhibit.temi_location
            state = TourState.RETURNING if exhibit.id == 'exit' else TourState.NAVIGATING
            await self._operate(state, f'前往{exhibit.name}', lambda: self.robot.navigate(
                exhibit.temi_location, self.config.navigation_timeout_sec), motion=True)
            self.visited.append(exhibit.temi_location)
            await self._operate(TourState.EXPLAINING, f'讲解{exhibit.name}',
                                lambda: self.robot.speak(exhibit.guide_content))
            if exhibit.id == 'interaction_zone':
                self._qa_open = True
                try:
                    await self._wait_signal(TourState.QA, '互动等待，接受文字提问、人工结束或超时继续',
                                            self._qa_event, self.config.qa_timeout_sec)
                finally:
                    self._qa_open = False
                if self._qa_question is not None:
                    await self._operate(TourState.QA, '知识问答与播报', self._answer_question)
        await self._checkpoint()
        raise _TourEnd(TourState.COMPLETED, 'completed', '完整导览已结束')

    async def _run(self):
        try:
            try:
                await self._normal_tour()
            except _LowBattery:
                if self._visitor_guard is not None and not self._accepted:
                    raise _TourEnd(TourState.ERROR, 'low_battery_before_consent',
                                   '辅助迎宾期间低电量，未获同意，不执行导航')
                self._returning_low = True
                if not self.connected or self.battery_percentage <= 0:
                    raise _TourEnd(TourState.ERROR, 'error', '低电量且无法安全返回，需要人工接管')
                self.target = self.config.safe_return_location
                await self._operate(TourState.RETURNING, '低电量返回安全地点', lambda: self.robot.navigate(
                    self.config.safe_return_location, self.config.navigation_timeout_sec), motion=True)
                self._safe_return_completed = True
                await self._checkpoint()
                raise _TourEnd(TourState.ERROR, 'low_battery_returned', '已返回安全地点，需人工处理电量')
        except _TourEnd as end:
            self.outcome = end.outcome
            self._ended = time.monotonic()
            if end.state is TourState.ERROR:
                self.error_count += 1
            self._transition(end.state, end.reason)
        except Exception as error:
            self.error_count += 1
            self.outcome = 'error'
            self._ended = time.monotonic()
            self._transition(TourState.ERROR, f'导览异常: {error}')

    async def shutdown(self):
        """关闭前请求取消并等待本段任务收尾。"""
        if self.running:
            self.cancel()
            await self._task
