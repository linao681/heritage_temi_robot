"""Mock 与 Android 实机通信后端共同遵循的独立 Python 契约。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RobotSnapshot:
    """机器人状态快照：不持有 ROS2 或 Android 运行时对象。"""

    connected: bool = False
    battery_percentage: float = -1.0
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    navigation_status: str = 'disconnected'
    current_location: str = ''
    is_moving: bool = False
    error_message: str = ''
    frame_id: str = ''
    # 内部连接代数：断线重连后的旧 ROS Goal 不得被提交给新会话。
    connection_epoch: int = 0


@dataclass(frozen=True)
class TaskResult:
    """命令的最终执行结果，不代表仅收到命令的 ACK。"""

    success: bool
    message: str


@dataclass(frozen=True)
class NavigationFeedback:
    """包含原始命令 ID 的异步导航状态。"""

    task_id: str
    target: str
    status: str
    description: str


@dataclass(frozen=True)
class SpeechFeedback:
    """包含原始命令 ID 的异步语音状态。"""

    task_id: str
    status: str


class TemiBackend(ABC):
    """统一控制接口；实现应支持活动任务执行期间的并发停止请求。"""

    @abstractmethod
    async def connect(self) -> TaskResult:
        """建立连接，只有后端实际就绪才返回成功。"""
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> TaskResult:
        """断开连接并终止活动任务，不在重连后自动重放命令。"""
        raise NotImplementedError

    @abstractmethod
    async def navigate_to(
        self,
        location: str,
        timeout_sec: float,
        *,
        task_id: str,
        feedback: Callable[[NavigationFeedback], None] | None = None,
    ) -> TaskResult:
        """导航至保存地点，报告进度并等待到达、停止、超时或失败。"""
        raise NotImplementedError

    async def set_navigation_speed(self, target_speed_mps: float, *, command_id: str,
                                   navigation_session_id: str, control_reason: str) -> TaskResult:
        """仅调整当前应用导航会话的目标速度；后端不支持时明确失败。"""
        return TaskResult(False, '当前后端不支持活动导航调速')

    @abstractmethod
    async def stop(self) -> TaskResult:
        """高优先级停止运动，不能等待活动导航自然结束。"""
        raise NotImplementedError

    @abstractmethod
    async def speak(
        self,
        text: str,
        *,
        task_id: str,
        feedback: Callable[[SpeechFeedback], None] | None = None,
    ) -> TaskResult:
        """发出语音请求并等待终止状态，不将接收确认视作播报完成。"""
        raise NotImplementedError

    @abstractmethod
    def get_status(self) -> RobotSnapshot:
        """非阻塞地读取最近的状态快照，不进行同步网络或 SDK 调用。"""
        raise NotImplementedError
