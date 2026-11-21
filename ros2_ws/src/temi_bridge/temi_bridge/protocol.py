"""版本化 WebSocket JSON 契约；不依赖具体传输或 Android SDK。"""

import json
import math
import time

from .backend import RobotSnapshot


PROTOCOL_VERSION = 1
COMMAND_EVENTS = {
    'navigate': 'navigation_status',
    'speak': 'speech_status',
    'stop': 'stop_status',
    'cancel_speech': 'speech_cancel_status',
    'set_speed': 'speed_status',
}
EVENT_STATUSES = {
    'navigation_status': {'start', 'calculating', 'going', 'reposing', 'complete',
                          'abort', 'stopped', 'timeout', 'disconnected'},
    'speech_status': {'started', 'complete', 'error', 'not_allowed', 'canceled'},
    'stop_status': {'complete', 'error'},
    'speech_cancel_status': {'complete', 'error'},
    'speed_status': {'complete', 'error'},
}
TERMINAL_STATUSES = {'complete', 'abort', 'stopped', 'timeout', 'disconnected',
                     'error', 'not_allowed', 'canceled'}


class ProtocolError(ValueError):
    """无效或不支持的协议消息。"""


def _reject_constant(value):
    raise ProtocolError(f'禁止非有限 JSON 数值: {value}')


def decode_message(raw: str) -> dict:
    """只接受合法 JSON 文本对象，并拒绝 NaN/Infinity。"""
    if not isinstance(raw, str):
        raise ProtocolError('只支持 WebSocket 文本帧')
    try:
        message = json.loads(raw, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as error:
        raise ProtocolError('无效 JSON') from error
    if not isinstance(message, dict) or not isinstance(message.get('type'), str):
        raise ProtocolError('消息必须是含 type 的 JSON 对象')
    return message


def encode_message(message: dict) -> str:
    return json.dumps(message, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def valid_id(task_id: str) -> bool:
    return isinstance(task_id, str) and bool(task_id.strip()) and len(task_id) <= 128


def make_command(command: str, task_id: str, timeout_sec: float, **fields) -> dict:
    """生成带唯一 ID 和 Unix 毫秒到期时间的控制命令。"""
    required = {'navigate': {'location'}, 'speak': {'text'}, 'stop': {'target_id'},
                'cancel_speech': {'target_id'},
                'set_speed': {'navigation_session_id', 'target_speed_mps', 'control_reason'}}
    if command not in required or set(fields) != required[command] or not valid_id(task_id):
        raise ProtocolError('无效命令、命令 ID 或字段')
    if not math.isfinite(timeout_sec) or timeout_sec <= 0:
        raise ProtocolError('命令超时必须为正数')
    if command == 'set_speed':
        speed = fields['target_speed_mps']
        if (not isinstance(fields['navigation_session_id'], str) or not valid_id(fields['navigation_session_id']) or
                not isinstance(fields['control_reason'], str) or not fields['control_reason'].strip() or
                type(speed) not in (int, float) or not math.isfinite(speed) or not 0.3 <= speed <= 0.8):
            raise ProtocolError('无效调速会话、速度或原因')
    elif any(not isinstance(value, str) or (not value.strip() and command != 'stop')
             for value in fields.values()):
        raise ProtocolError('命令参数必须为有效文本')
    return {'type': 'command', 'id': task_id, 'command': command,
            'expires_at_ms': math.ceil(time.time() * 1000 + timeout_sec * 1000), **fields}


def parse_state(message: dict) -> RobotSnapshot:
    """将 Android 完整状态快照映射到后端；不推测缺少的传感器数据。"""
    values = {}
    for field in ('connected', 'is_moving'):
        value = message.get(field)
        if type(value) is not bool:
            raise ProtocolError(f'{field} 必须为布尔值')
        values[field] = value
    for field in ('battery_percentage', 'x', 'y', 'yaw'):
        value = message.get(field)
        if type(value) not in (int, float):
            raise ProtocolError(f'{field} 必须为有限数值')
        try:
            numeric = float(value)
        except OverflowError as error:
            raise ProtocolError(f'{field} 超出数值范围') from error
        if not math.isfinite(numeric):
            raise ProtocolError(f'{field} 必须为有限数值')
        values[field] = numeric
    battery = values['battery_percentage']
    if battery != -1.0 and not 0.0 <= battery <= 100.0:
        raise ProtocolError('电量必须为 -1 或 0~100')
    for field in ('navigation_status', 'current_location', 'error_message', 'frame_id'):
        value = message.get(field)
        if not isinstance(value, str):
            raise ProtocolError(f'{field} 必须为字符串')
        values[field] = value
    return RobotSnapshot(**values)


def parse_ack(message: dict) -> tuple[str, bool, str]:
    task_id, accepted, description = message.get('id'), message.get('accepted'), message.get('message')
    if not valid_id(task_id) or type(accepted) is not bool or not isinstance(description, str):
        raise ProtocolError('无效 ACK')
    return task_id, accepted, description


def parse_event(message: dict) -> tuple[str, str, str, str]:
    task_id = message.get('id')
    kind, status, description = message.get('event'), message.get('status'), message.get('description', '')
    if (not valid_id(task_id) or not isinstance(kind, str) or kind not in EVENT_STATUSES
            or not isinstance(status, str) or status not in EVENT_STATUSES[kind]
            or not isinstance(description, str)):
        raise ProtocolError('无效事件')
    return task_id, kind, status, description
