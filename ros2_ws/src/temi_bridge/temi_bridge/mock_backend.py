"""不依赖 ROS2、Android 或网络的 temi 虚拟机器人后端。"""

import asyncio
import math
import random
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

import yaml

from .backend import (
    NavigationFeedback, RobotSnapshot, SpeechFeedback, TaskResult, TemiBackend,
)


@dataclass(frozen=True)
class MockConfig:
    """仅用于模拟的地点与参数，不能作为实体 temi 地图。"""

    locations: dict[str, tuple[float, float]]
    initial_location: str = 'entrance'
    speed_mps: float = 1.0
    navigation_delay_sec: float = 0.2
    navigation_failure_probability: float = 0.0
    tick_sec: float = 0.05
    speech_delay_sec: float = 0.4
    speech_timeout_sec: float = 10.0
    initial_battery_percentage: float = 100.0
    battery_drain_per_meter: float = 0.5

    def __post_init__(self):
        """避免无效速度、时间或坐标导致无限模拟任务。"""
        for name in ('speed_mps', 'tick_sec', 'speech_timeout_sec'):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} 必须为正数')
        for name in ('navigation_delay_sec', 'speech_delay_sec', 'battery_drain_per_meter'):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f'{name} 必须为非负数')
        if not 0.0 <= self.navigation_failure_probability <= 1.0:
            raise ValueError('navigation_failure_probability 必须在 0~1 之间')
        if not 0.0 <= self.initial_battery_percentage <= 100.0:
            raise ValueError('initial_battery_percentage 必须在 0~100 之间')
        if self.initial_location not in self.locations:
            raise ValueError('initial_location 必须位于虚拟地点列表中')
        for name, position in self.locations.items():
            if not name.strip() or len(position) != 2 or not all(map(math.isfinite, position)):
                raise ValueError(f'无效虚拟地点: {name}')

    @classmethod
    def from_yaml(cls, path: str | Path) -> 'MockConfig':
        """从项目 YAML 加载模拟参数，不读取真实地图。"""
        with Path(path).open(encoding='utf-8') as file:
            parameters = yaml.safe_load(file)['mock']
        parameters['locations'] = {name: tuple(point) for name, point in parameters['locations'].items()}
        return cls(**parameters)


@dataclass
class _Operation:
    """活动任务的单次中断信号，只保留首次终止原因。"""

    event: asyncio.Event = field(default_factory=asyncio.Event)
    status: str = ''
    message: str = ''

    def interrupt(self, status: str, message: str) -> None:
        if not self.event.is_set():
            self.status = status
            self.message = message
            self.event.set()

    async def wait(self, delay: float) -> bool:
        """等待模拟延时；STOP 或掉线可提前唤醒，不必等待下一周期。"""
        if self.event.is_set():
            return True
        if delay <= 0:
            return False
        waiter = asyncio.create_task(self.event.wait())
        try:
            # Python 3.10 的 wait_for 在内层 Future 同时完成时可能吞掉外层取消。
            await asyncio.wait({waiter}, timeout=delay)
        finally:
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)
        return self.event.is_set()


class MockTemiBackend(TemiBackend):
    """由事件循环驱动的虚拟机器人，所有控制操作在同一 asyncio loop 执行。"""

    def __init__(self, config: MockConfig):
        self.config = config
        self._locations = {name: tuple(point) for name, point in config.locations.items()}
        self._state = RobotSnapshot()
        self._initialized = False
        self._navigation: _Operation | None = None
        self._speech: _Operation | None = None
        self._fail_next_navigation = False
        self._navigation_task_id = ""
        self._target_speed_mps = config.speed_mps
        self._simulated_velocity_mps = 0.0

    async def connect(self) -> TaskResult:
        """首次连接位于入口；以后连接保留快照，不重新执行旧任务。"""
        if not self._initialized:
            x, y = self._locations[self.config.initial_location]
            self._state = RobotSnapshot(
                connected=True, battery_percentage=self.config.initial_battery_percentage,
                x=float(x), y=float(y), navigation_status='idle',
                current_location=self.config.initial_location, frame_id='mock_map',
                connection_epoch=1,
            )
            self._initialized = True
        elif not self._state.connected:
            self._state = replace(self._state, connected=True, navigation_status='idle',
                                  is_moving=False, error_message='',
                                  connection_epoch=self._state.connection_epoch + 1)
        return TaskResult(True, 'Mock 机器人已连接')

    def _disconnect(self, message: str) -> None:
        # 先释放活动槽位，再唤醒旧协程；新连接不需要等待旧任务清理。
        navigation, self._navigation = self._navigation, None
        speech, self._speech = self._speech, None
        self._state = replace(self._state, connected=False, is_moving=False,
                              navigation_status='disconnected', error_message=message)
        if navigation:
            navigation.interrupt('disconnected', message)
        if speech:
            speech.interrupt('error', message)

    async def disconnect(self) -> TaskResult:
        """正常断开并唤醒所有正在等待的活动任务。"""
        self._disconnect('Mock 机器人已断开')
        return TaskResult(True, 'Mock 机器人已断开')

    async def simulate_disconnect(self) -> None:
        """显式模拟通信故障；须重新调用 connect 恢复。"""
        self._disconnect('模拟网络断开')

    def inject_navigation_failure(self) -> None:
        """使下一次被接受的导航失败；故障仅生效一次。"""
        self._fail_next_navigation = True

    def set_battery_percentage(self, percentage: float) -> None:
        """显式注入包括低电量在内的模拟电池状态。"""
        if not 0.0 <= percentage <= 100.0:
            raise ValueError('电量必须在 0~100 之间')
        self._state = replace(self._state, battery_percentage=float(percentage))

    def get_status(self) -> RobotSnapshot:
        """返回最近的不可变位置与状态，无等待或网络访问。"""
        return self._state

    async def navigate_to(
        self, location: str, timeout_sec: float, *, task_id: str,
        feedback: Callable[[NavigationFeedback], None] | None = None,
    ) -> TaskResult:
        """根据单调时钟与配置速度，逐周期推进虚拟位置。"""
        if not self._state.connected:
            return TaskResult(False, '机器人未连接')
        if not task_id.strip() or location not in self._locations:
            return TaskResult(False, '无效任务 ID 或虚拟地点')
        if not math.isfinite(timeout_sec) or timeout_sec <= 0:
            return TaskResult(False, '导航超时必须为正数')
        if self._navigation is not None:
            return TaskResult(False, '已有活动导航任务')

        operation = self._navigation = _Operation()
        self._navigation_task_id = task_id
        self._target_speed_mps = self.config.speed_mps
        clock = asyncio.get_running_loop().time
        deadline = clock() + timeout_sec
        should_fail = (self._fail_next_navigation or
                       random.random() < self.config.navigation_failure_probability)
        self._fail_next_navigation = False

        def report(status: str, description: str) -> None:
            if feedback is not None:
                feedback(NavigationFeedback(task_id, location, status, description))

        def finish(status: str, message: str, success: bool = False) -> TaskResult:
            # 被停止或断线的旧任务不得覆盖已经接受的新导航状态。
            if self._navigation is operation and self._state.connected:
                self._state = replace(
                    self._state, navigation_status=status, is_moving=False,
                    current_location=location if success else self._state.current_location,
                    error_message='' if success else message,
                )
            report(status, message)
            return TaskResult(success, message)

        try:
            self._state = replace(self._state, navigation_status='start', error_message='')
            report('start', '开始导航')
            self._state = replace(self._state, navigation_status='calculating')
            report('calculating', '计算虚拟路线')
            if await operation.wait(min(self.config.navigation_delay_sec, max(0.0, deadline-clock()))):
                return finish(operation.status, operation.message)
            if clock() >= deadline:
                return finish('timeout', '模拟导航超时')
            if should_fail:
                return finish('abort', '模拟导航故障')

            target_x, target_y = self._locations[location]
            dx, dy = target_x - self._state.x, target_y - self._state.y
            distance = math.hypot(dx, dy)
            if distance == 0.0:
                return finish('complete', '已到达虚拟地点', True)
            self._state = replace(self._state, navigation_status='going', is_moving=True,
                                  yaw=math.atan2(dy, dx))
            report('going', '向虚拟地点移动')
            previous = clock()
            while distance > 0.0:
                remaining = deadline - clock()
                if remaining <= 0.0:
                    return finish('timeout', '模拟导航超时')
                if await operation.wait(min(self.config.tick_sec, remaining)):
                    return finish(operation.status, operation.message)

                now = min(clock(), deadline)
                movement = min(distance, self._target_speed_mps * max(0.0, now-previous))
                self._simulated_velocity_mps = self._target_speed_mps
                previous = now
                reached = movement >= distance
                # 使用实际位移扣减电量；到达时吸附至精确目标坐标。
                x = target_x if reached else self._state.x + dx / distance * movement
                y = target_y if reached else self._state.y + dy / distance * movement
                self._state = replace(
                    self._state, x=float(x), y=float(y),
                    battery_percentage=max(0.0, self._state.battery_percentage -
                                           movement * self.config.battery_drain_per_meter),
                )
                if reached:
                    return finish('complete', '已到达虚拟地点', True)
                dx, dy = target_x - x, target_y - y
                distance = math.hypot(dx, dy)
            return finish('complete', '已到达虚拟地点', True)
        except asyncio.CancelledError:
            finish(operation.status or 'stopped', operation.message or '导航任务已取消')
            raise
        finally:
            if self._navigation is operation:
                self._navigation = None
                self._navigation_task_id = ""
                self._simulated_velocity_mps = 0.0

    async def set_navigation_speed(self, target_speed_mps: float, *, command_id: str,
                                   navigation_session_id: str, control_reason: str) -> TaskResult:
        if (not math.isfinite(target_speed_mps) or not 0.3 <= target_speed_mps <= 0.8 or
                not command_id.strip() or navigation_session_id != self._navigation_task_id or
                self._navigation is None or not control_reason.strip()):
            return TaskResult(False, 'Mock 拒绝无效或过期的导航速度命令')
        self._target_speed_mps = target_speed_mps
        return TaskResult(True, f'Mock 目标速度已设为 {target_speed_mps:.2f} m/s（模拟值）')

    async def stop(self) -> TaskResult:
        """立即停止运动，独立的语音任务继续执行。"""
        if not self._state.connected:
            return TaskResult(False, '机器人未连接，无法确认停止')
        if self._navigation is not None:
            navigation, self._navigation = self._navigation, None
            navigation.interrupt('stopped', '运动已停止')
            self._state = replace(self._state, navigation_status='stopped', is_moving=False,
                                  error_message='运动已停止')
        return TaskResult(True, '运动已停止')

    async def speak(
        self, text: str, *, task_id: str,
        feedback: Callable[[SpeechFeedback], None] | None = None,
    ) -> TaskResult:
        """用可配置延时模拟语音服务的开始、完成、超时和取消。"""
        if not self._state.connected:
            return TaskResult(False, '机器人未连接')
        if not text.strip() or not task_id.strip():
            return TaskResult(False, '无效文本或任务 ID')
        if self._speech is not None:
            return TaskResult(False, '已有活动播报任务')

        operation = self._speech = _Operation()

        def report(status: str) -> None:
            if feedback is not None:
                feedback(SpeechFeedback(task_id, status))

        try:
            report('started')
            delay = min(self.config.speech_delay_sec, self.config.speech_timeout_sec)
            if await operation.wait(delay):
                report(operation.status)
                return TaskResult(False, operation.message)
            if self.config.speech_delay_sec > self.config.speech_timeout_sec:
                report('error')
                return TaskResult(False, '模拟语音播报超时')
            report('complete')
            return TaskResult(True, '模拟语音播报完成')
        except asyncio.CancelledError:
            report(operation.status or 'canceled')
            raise
        finally:
            if self._speech is operation:
                self._speech = None
