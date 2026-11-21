"""Linux WebSocket 代理后端：真正 SDK 动作仅在 Android 客户端执行。"""

import asyncio
import hmac
import ipaddress
import logging
import math
import uuid
from dataclasses import dataclass, replace
from http import HTTPStatus
from typing import Callable

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from .backend import NavigationFeedback, RobotSnapshot, SpeechFeedback, TaskResult, TemiBackend
from .protocol import (
    COMMAND_EVENTS, PROTOCOL_VERSION, TERMINAL_STATUSES, ProtocolError, decode_message,
    encode_message, make_command, parse_ack, parse_event, parse_state, valid_id,
)


LOGGER = logging.getLogger(__name__)
PRIVATE_NETWORKS = tuple(map(ipaddress.IPv4Network, ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')))


@dataclass(frozen=True)
class WebSocketConfig:
    """明确绑定本机或一个 RFC1918 私有 IPv4 地址，禁止通配及公网监听。"""

    bind_host: str = '127.0.0.1'
    port: int = 8765
    ack_timeout_sec: float = 1.0
    speech_timeout_sec: float = 10.0
    stop_timeout_sec: float = 2.0
    heartbeat_interval_sec: float = 5.0
    heartbeat_timeout_sec: float = 3.0
    replay_window_sec: float = 300.0

    def __post_init__(self):
        address = ipaddress.IPv4Address(self.bind_host)
        if not address.is_loopback and not any(address in network for network in PRIVATE_NETWORKS):
            raise ValueError('仅允许本机或显式私有局域网 IPv4 地址')
        if type(self.port) is not int or not 0 <= self.port <= 65535:
            raise ValueError('无效 WebSocket 端口')
        for name in ('ack_timeout_sec', 'speech_timeout_sec', 'stop_timeout_sec',
                     'heartbeat_interval_sec', 'heartbeat_timeout_sec', 'replay_window_sec'):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} 必须为正数')


class _CommandTimeout(Exception):
    pass


@dataclass
class _PendingCommand:
    session: ServerConnection
    command: str
    task_id: str
    deadline: float
    ack: asyncio.Future
    result: asyncio.Future
    target: str
    feedback: Callable | None
    remote_timeout: bool = False


class WebSocketTemiBackend(TemiBackend):
    """单连接、无重放的 ROS→Android 代理，所有控制方法运行于同一事件循环。"""

    def __init__(self, config: WebSocketConfig, token: str):
        if not isinstance(token, str) or len(token) < 16 or not token.isascii() or any(c.isspace() for c in token):
            raise ValueError('认证 token 必须是至少 16 字符且无空白的 ASCII 文本')
        self.config = config
        self._authorization = ('Bearer ' + token).encode()
        self._server: Server | None = None
        self._lifecycle_lock = asyncio.Lock()
        self._closing = False
        self._socket: ServerConnection | None = None
        self._state = RobotSnapshot()
        self._pending: dict[str, _PendingCommand] = {}
        self._issued: dict[str, float] = {}
        self._navigation: str | None = None
        self._speech: str | None = None
        self._stopping: str | None = None
        self._motion_uncertain = False
        self._speech_uncertain = False

    @property
    def bound_port(self) -> int:
        """返回实际绑定端口，允许测试使用 port=0 的临时本机端口。"""
        if self._server is None:
            raise RuntimeError('WebSocket 服务未启动')
        return self._server.sockets[0].getsockname()[1]

    def _authenticate(self, connection, request):
        if request.path != '/temi':
            return connection.respond(HTTPStatus.NOT_FOUND, 'Not found')
        headers = request.headers.get_all('Authorization')
        if len(headers) != 1 or not hmac.compare_digest(headers[0].encode(), self._authorization):
            return connection.respond(HTTPStatus.UNAUTHORIZED, 'Unauthorized')
        return None

    async def connect(self) -> TaskResult:
        """启动监听，只有完成 Android Ready 快照同步才标记连接。"""
        async with self._lifecycle_lock:
            if self._server is None:
                try:
                    self._server = await serve(
                        self._handle_connection, self.config.bind_host, self.config.port,
                        process_request=self._authenticate, origins=[None], compression=None,
                        max_size=65536, open_timeout=5.0, close_timeout=1.0,
                        ping_interval=self.config.heartbeat_interval_sec,
                        ping_timeout=self.config.heartbeat_timeout_sec,
                    )
                except OSError as error:
                    LOGGER.error('WebSocket 本机监听失败: %s', error)
                    return TaskResult(False, 'WebSocket 服务启动失败')
                LOGGER.info('WebSocket 服务等待 Android：%s:%d', self.config.bind_host, self.bound_port)
            return TaskResult(self._state.connected, '机器人已就绪' if self._state.connected else '等待 Android 就绪')

    async def disconnect(self) -> TaskResult:
        """关闭监听和会话，并终结旧命令；不重发或保留控制队列。"""
        async with self._lifecycle_lock:
            self._closing = True
            try:
                session = self._socket
                if self._state.connected and (self._navigation or self._state.is_moving or self._motion_uncertain):
                    if not (await self.stop()).success:
                        LOGGER.warning('关闭时无法确认运动已停止，需 Android 断线保护')
                if self._state.connected and self._socket is session and self._speech:
                    if not (await self._cancel_speech(self._speech)).success:
                        LOGGER.warning('关闭时无法确认语音已取消')
            finally:
                if self._server is not None:
                    self._server.close()
                    await self._server.wait_closed()
                    self._server = None
                self._lose_readiness('WebSocket 服务已关闭')
                self._closing = False
            return TaskResult(True, 'WebSocket 服务已关闭')

    def get_status(self) -> RobotSnapshot:
        return self._state

    async def _handle_connection(self, socket: ServerConnection):
        if self._socket is not None:
            await socket.close(1008, 'Only one robot connection is supported')
            return
        self._socket = socket
        try:
            hello = decode_message(await asyncio.wait_for(socket.recv(), timeout=self.config.ack_timeout_sec))
            if hello.get('type') != 'hello' or type(hello.get('protocol_version')) is not int or hello['protocol_version'] != PROTOCOL_VERSION:
                raise ProtocolError('不支持的握手版本')
            await socket.send(encode_message({'type': 'hello_ack', 'protocol_version': PROTOCOL_VERSION}))
            await socket.send(encode_message({'type': 'state_request'}))
            initial = decode_message(await asyncio.wait_for(socket.recv(), timeout=self.config.ack_timeout_sec))
            if initial['type'] != 'state':
                raise ProtocolError('握手后必须提供完整状态')
            self._handle_message(socket, initial)
            async for raw in socket:
                self._handle_message(socket, decode_message(raw))
        except (ProtocolError, asyncio.TimeoutError) as error:
            LOGGER.warning('Android 会话协议错误: %s', error)
            await socket.close(1008, 'Invalid protocol message')
        except ConnectionClosed:
            LOGGER.info('Android WebSocket 已断开')
        finally:
            if self._socket is socket:
                self._socket = None
                self._lose_readiness('Android WebSocket 连接断开')

    def _feedback(self, pending: _PendingCommand, status: str, description: str):
        if pending.feedback is None:
            return
        try:
            if pending.command == 'navigate':
                pending.feedback(NavigationFeedback(pending.task_id, pending.target, status, description))
            elif pending.command == 'speak':
                pending.feedback(SpeechFeedback(pending.task_id, status))
        except Exception as error:
            LOGGER.warning('反馈回调失败: %s', type(error).__name__)

    def _lose_readiness(self, reason: str):
        self._state = replace(self._state, connected=False, navigation_status='disconnected',
                              is_moving=False, error_message=reason)
        self._navigation = self._speech = self._stopping = None
        self._motion_uncertain = False
        self._speech_uncertain = False
        for pending in tuple(self._pending.values()):
            if not pending.ack.done():
                pending.ack.set_result(TaskResult(False, reason))
            if not pending.result.done():
                self._feedback(pending, 'disconnected' if pending.command == 'navigate' else 'error', reason)
                pending.result.set_result(TaskResult(False, reason))

    def _handle_message(self, socket: ServerConnection, message: dict):
        if self._socket is not socket:
            return
        kind = message['type']
        if kind == 'state':
            state = parse_state(message)
            epoch = self._state.connection_epoch + int(state.connected and not self._state.connected)
            self._state = replace(state, connection_epoch=epoch)
            if not state.connected:
                self._lose_readiness(state.error_message or 'Android SDK 未就绪')
            elif self._motion_uncertain:
                self._state = replace(self._state, error_message='停车尚未确认，禁止新导航')
            return

        if kind == 'ack':
            task_id, accepted, description = parse_ack(message)
        elif kind == 'event':
            task_id, event, status, description = parse_event(message)
        else:
            raise ProtocolError('未知的 Android 消息类型')

        pending = self._pending.get(task_id)
        if (pending is None or pending.session is not socket or
                pending.result.done() or asyncio.get_running_loop().time() >= pending.deadline):
            return  # 旧会话、重复终态和过期事件不得影响新任务
        if kind == 'ack':
            if not pending.ack.done():
                pending.ack.set_result(TaskResult(accepted, description))
            return
        if event != COMMAND_EVENTS[pending.command] or not pending.ack.done() or not pending.ack.result().success:
            return  # 必须先确认命令，再接收匹配类型的结果
        if pending.command == 'navigate' and self._navigation == task_id:
            if status == 'disconnected':
                self._lose_readiness(description or 'Android SDK 断开')
                return
            if status == 'timeout':
                # 不把远端超时事件本身视为物理停车证明，交给导航协程发 STOP。
                pending.remote_timeout = True
                pending.result.set_result(TaskResult(False, description or status))
                return
            self._state = replace(
                self._state, navigation_status=status, is_moving=status in ('going', 'reposing'),
                current_location=pending.target if status == 'complete' else self._state.current_location,
                error_message=description if status in ('abort', 'timeout', 'disconnected') else '',
            )
        if pending.command == 'stop' and status == 'complete' and self._stopping == task_id:
            self._confirm_stop(pending.target)
        self._feedback(pending, status, description)
        if status in TERMINAL_STATUSES:
            pending.result.set_result(TaskResult(status == 'complete', description or status))

    @staticmethod
    async def _wait_for_result(future: asyncio.Future, timeout: float) -> TaskResult:
        # asyncio.wait 不会在 Python 3.10 并发完成时吞掉外部取消。
        if future.done():
            return future.result()
        if timeout <= 0:
            raise _CommandTimeout
        done, _ = await asyncio.wait({future}, timeout=timeout)
        if not done:
            raise _CommandTimeout
        return future.result()

    async def _command(self, command: str, task_id: str, timeout: float, feedback=None, **fields) -> TaskResult:
        if not self._state.connected or self._socket is None:
            return TaskResult(False, 'Android SDK 未连接或未就绪')
        try:
            message = make_command(command, task_id, timeout, **fields)
        except ProtocolError as error:
            return TaskResult(False, str(error))
        payload = encode_message(message)
        if len(payload.encode()) > 65536:
            return TaskResult(False, '命令消息超过 64 KiB')
        loop = asyncio.get_running_loop()
        now = loop.time()
        self._issued = {key: expiry for key, expiry in self._issued.items() if expiry > now}
        if task_id in self._issued or task_id in self._pending:
            return TaskResult(False, '重复命令 ID 已拒绝')
        self._issued[task_id] = now + max(self.config.replay_window_sec, timeout)
        pending = _PendingCommand(self._socket, command, task_id, now + timeout, loop.create_future(),
                                  loop.create_future(), fields.get('location', fields.get('target_id', fields.get('navigation_session_id', ''))), feedback)
        self._pending[task_id] = pending
        try:
            send_task = asyncio.create_task(pending.session.send(payload))
            try:
                await self._wait_for_result(send_task, min(self.config.ack_timeout_sec, pending.deadline-loop.time()))
            finally:
                if not send_task.done():
                    send_task.cancel()
                    await asyncio.gather(send_task, return_exceptions=True)
            ack = await self._wait_for_result(pending.ack, min(self.config.ack_timeout_sec, pending.deadline-loop.time()))
            if not ack.success:
                return ack
            result = await self._wait_for_result(pending.result, pending.deadline-loop.time())
            if pending.remote_timeout:
                raise _CommandTimeout
            return result
        except ConnectionClosed:
            return TaskResult(False, '连接已断开，命令未确认完成')
        finally:
            if self._pending.get(task_id) is pending:
                del self._pending[task_id]

    async def set_navigation_speed(self, target_speed_mps: float, *, command_id: str,
                                   navigation_session_id: str, control_reason: str) -> TaskResult:
        """仅向 Android 请求调节与当前 GoTo 匹配的速度，并等待 SDK 返回。"""
        if (not math.isfinite(target_speed_mps) or not 0.3 <= target_speed_mps <= 0.8 or
                not valid_id(command_id) or not control_reason.strip() or
                self._navigation != navigation_session_id or self._stopping is not None or
                self._motion_uncertain):
            return TaskResult(False, '活动导航会话不匹配或速度无效')
        try:
            return await self._command('set_speed', command_id, self.config.ack_timeout_sec + 1.0,
                                       navigation_session_id=navigation_session_id,
                                       target_speed_mps=target_speed_mps,
                                       control_reason=control_reason)
        except _CommandTimeout:
            return TaskResult(False, 'SDK 调速确认超时；实际执行状态未知')

    async def navigate_to(self, location: str, timeout_sec: float, *, task_id: str,
                          feedback: Callable[[NavigationFeedback], None] | None = None) -> TaskResult:
        if not valid_id(task_id) or not isinstance(location, str) or not location.strip() or not math.isfinite(timeout_sec) or timeout_sec <= 0:
            return TaskResult(False, '无效导航目标、ID 或超时')
        if self._closing or self._navigation is not None or self._stopping is not None or self._motion_uncertain or self._state.is_moving:
            return TaskResult(False, '已有活动运动或尚未确认停止')
        self._navigation = task_id
        try:
            return await self._command('navigate', task_id, timeout_sec, feedback, location=location)
        except _CommandTimeout:
            stopped = await self.stop() if self._navigation == task_id else TaskResult(False, '连接丢失')
            message = '导航超时，已确认停止' if stopped.success else '导航超时，无法确认停止'
            if self._state.connected and (self._navigation is None or self._navigation == task_id):
                self._motion_uncertain = not stopped.success
                self._state = replace(self._state, navigation_status='timeout', error_message=message)
            if feedback:
                feedback(NavigationFeedback(task_id, location, 'timeout', message))
            return TaskResult(False, message)
        except asyncio.CancelledError:
            if self._navigation == task_id and self._state.connected:
                stopped = await self.stop()
                self._motion_uncertain = not stopped.success
            raise
        finally:
            if self._navigation == task_id:
                self._navigation = None

    async def stop(self) -> TaskResult:
        """独立发送 STOP，不等待活动导航或语音命令完成。"""
        if self._stopping is not None:
            return TaskResult(False, '停止请求正在执行')
        stop_id = uuid.uuid4().hex
        target, self._stopping = self._navigation, stop_id
        try:
            result = await self._command('stop', stop_id, self.config.stop_timeout_sec, target_id=target or '')
            if not result.success and self._state.connected and self._stopping == stop_id:
                self._motion_uncertain = True
                self._state = replace(self._state, error_message='停车尚未确认，禁止新导航')
            return result
        except _CommandTimeout:
            if self._stopping == stop_id and self._state.connected:
                self._motion_uncertain = True
                self._state = replace(self._state, error_message='停车尚未确认，禁止新导航')
            return TaskResult(False, '停止命令超时，无法确认停止')
        except asyncio.CancelledError:
            if self._stopping == stop_id and self._state.connected:
                self._motion_uncertain = True
                self._state = replace(self._state, error_message='停车尚未确认，禁止新导航')
            raise
        finally:
            if self._stopping == stop_id:
                self._stopping = None

    def _confirm_stop(self, target: str):
        # 与 STOP 终态在同一接收步骤落实，迟到的旧导航完成事件无法抢占。
        self._motion_uncertain = False
        self._state = replace(self._state, is_moving=False, navigation_status='stopped', error_message='')
        if target and self._navigation == target:
            self._navigation = None
            pending = self._pending.get(target)
            if pending is not None and not pending.result.done():
                self._feedback(pending, 'stopped', '运动已停止')
                if not pending.ack.done():
                    pending.ack.set_result(TaskResult(False, '运动已停止'))
                pending.result.set_result(TaskResult(False, '运动已停止'))

    async def _cancel_speech(self, task_id: str) -> TaskResult:
        try:
            return await self._command('cancel_speech', uuid.uuid4().hex,
                                       self.config.stop_timeout_sec, target_id=task_id)
        except _CommandTimeout:
            return TaskResult(False, '语音取消超时')

    async def speak(self, text: str, *, task_id: str,
                    feedback: Callable[[SpeechFeedback], None] | None = None) -> TaskResult:
        if not valid_id(task_id) or not isinstance(text, str) or not text.strip():
            return TaskResult(False, '无效语音文本或任务 ID')
        if self._closing or self._speech is not None or self._speech_uncertain:
            return TaskResult(False, '已有活动语音任务或上次取消未确认')
        self._speech = task_id
        try:
            return await self._command('speak', task_id, self.config.speech_timeout_sec, feedback, text=text)
        except _CommandTimeout:
            canceled = TaskResult(False, '连接丢失')
            if self._speech == task_id:
                canceled = await self._cancel_speech(task_id)
                if self._state.connected and self._speech == task_id:
                    self._speech_uncertain = not canceled.success
            if feedback:
                feedback(SpeechFeedback(task_id, 'error'))
            return TaskResult(False, '语音命令超时，已取消' if canceled.success else '语音命令超时，取消未确认')
        except asyncio.CancelledError:
            if self._speech == task_id and self._state.connected:
                canceled = await self._cancel_speech(task_id)
                if self._state.connected and self._speech == task_id:
                    self._speech_uncertain = not canceled.success
                if feedback:
                    feedback(SpeechFeedback(task_id, 'canceled' if canceled.success else 'error'))
            raise
        finally:
            if self._speech == task_id:
                self._speech = None
