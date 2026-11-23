"""使用真实 localhost WebSocket，以测试客户端模拟未来 Android Bridge。"""

import asyncio
import json
import time

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus


TOKEN = 'local-test-token-0123456789'


def state_message(**values):
    state = {
        'type': 'state', 'connected': True, 'battery_percentage': 88.0,
        'x': 0.0, 'y': 0.0, 'yaw': 0.0, 'navigation_status': 'idle',
        'current_location': 'entrance', 'is_moving': False, 'error_message': '',
        'frame_id': 'temi_map',
    }
    return {**state, **values}


async def send(socket, data):
    await socket.send(json.dumps(data, ensure_ascii=False))


async def receive(socket):
    return json.loads(await asyncio.wait_for(socket.recv(), 2.0))


async def wait_until(predicate, timeout=1.5):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            pytest.fail('等待 WebSocket 状态超时')
        await asyncio.sleep(0.005)


def make_backend(**overrides):
    from temi_bridge.websocket_backend import WebSocketConfig, WebSocketTemiBackend

    options = dict(port=0, ack_timeout_sec=0.15, speech_timeout_sec=0.6,
                   stop_timeout_sec=0.4, heartbeat_interval_sec=0.2,
                   heartbeat_timeout_sec=0.2)
    return WebSocketTemiBackend(WebSocketConfig(**{**options, **overrides}), TOKEN)


def url(backend):
    return f'ws://127.0.0.1:{backend.bound_port}/temi'


async def handshake(backend, socket, **state):
    await send(socket, {'type': 'hello', 'protocol_version': 1})
    assert await receive(socket) == {'type': 'hello_ack', 'protocol_version': 1}
    assert await receive(socket) == {'type': 'state_request'}
    await send(socket, state_message(**state))
    await wait_until(lambda: backend.get_status().connected == state.get('connected', True))


def authorized(backend):
    return connect(url(backend), additional_headers={'Authorization': f'Bearer {TOKEN}'}, proxy=None)


async def ack(socket, command, accepted=True):
    await send(socket, {'type': 'ack', 'id': command['id'], 'accepted': accepted,
                        'message': 'ack' if accepted else 'rejected'})


async def event(socket, command, event_type, status, description=''):
    await send(socket, {'type': 'event', 'id': command['id'], 'event': event_type,
                        'status': status, 'description': description})


def test_protocol_validates_json_state_and_command_expiry():
    from temi_bridge.protocol import ProtocolError, decode_message, make_command, parse_state

    before = int(time.time() * 1000)
    command = make_command('navigate', 'nav_001', 2.0, location='exhibit_01')
    assert command['id'] == 'nav_001' and command['command'] == 'navigate'
    assert before + 1900 <= command['expires_at_ms'] <= before + 2100
    assert parse_state(state_message()).battery_percentage == 88.0
    for raw in ('[]', '{"type": "state", "x": NaN}', '{not json}', '{"id":"x"}'):
        with pytest.raises(ProtocolError):
            decode_message(raw)
    for state in (state_message(x=float('inf')), state_message(connected='true'),
                  state_message(battery_percentage=101.0), state_message(x=10**1000)):
        with pytest.raises(ProtocolError):
            parse_state(state)


@pytest.mark.parametrize('host', ['0.0.0.0', '8.8.8.8', 'example.org'])
def test_non_private_bind_is_rejected(host):
    from temi_bridge.websocket_backend import WebSocketConfig

    with pytest.raises(ValueError):
        WebSocketConfig(bind_host=host)


def test_listener_without_bound_socket_fails_closed(monkeypatch):
    import temi_bridge.websocket_backend as websocket_module
    from temi_bridge.websocket_backend import WebSocketConfig, WebSocketTemiBackend

    class EmptyServer:
        sockets = ()
        closed = False

        def close(self):
            self.closed = True

        async def wait_closed(self):
            return None

    server = EmptyServer()

    async def serve_without_sockets(*_args, **_kwargs):
        return server

    monkeypatch.setattr(websocket_module, 'serve', serve_without_sockets)

    async def scenario():
        backend = WebSocketTemiBackend(WebSocketConfig(port=0), TOKEN)
        result = await backend.connect()

        assert not result.success
        assert backend._server is None
        assert server.closed

    asyncio.run(scenario())


def test_authentication_single_client_and_ready_snapshot():
    async def scenario():
        backend = make_backend()
        assert not (await backend.connect()).success
        try:
            with pytest.raises(InvalidStatus) as error:
                async with connect(url(backend), proxy=None):
                    pass
            assert error.value.response.status_code == 401
            assert not backend.get_status().connected
            async with authorized(backend) as socket:
                await handshake(backend, socket, x=1.25, battery_percentage=73.5)
                assert backend.get_status().x == 1.25 and backend.get_status().battery_percentage == 73.5
                assert (await backend.connect()).success
                async with authorized(backend) as second:
                    with pytest.raises(ConnectionClosed):
                        await asyncio.wait_for(second.recv(), 1.0)
                pong = await socket.ping(b'interface-test')
                await asyncio.wait_for(pong, 1.0)
        finally:
            await backend.disconnect()

    asyncio.run(scenario())


def test_navigation_requires_ack_and_terminal_event_and_rejects_duplicate_id():
    async def scenario():
        backend = make_backend()
        await backend.connect()
        try:
            async with authorized(backend) as socket:
                await handshake(backend, socket)
                events = []
                nav = asyncio.create_task(backend.navigate_to('exhibit_01', 1.0, task_id='n1', feedback=events.append))
                command = await receive(socket)
                assert command['location'] == 'exhibit_01' and command['command'] == 'navigate'
                assert command['expires_at_ms'] > int(time.time()*1000)
                await event(socket, command, 'navigation_status', 'complete')  # 未确认的终态不得完成任务
                await asyncio.sleep(0.02)
                assert not nav.done()
                await ack(socket, command)
                await event(socket, command, 'navigation_status', 'going')
                await wait_until(lambda: bool(events))
                assert not nav.done() and backend.get_status().is_moving
                await send(socket, state_message(x=0.5, is_moving=True, navigation_status='going'))
                await wait_until(lambda: backend.get_status().x == 0.5)
                await event(socket, command, 'navigation_status', 'complete', 'arrived')
                assert (await nav).success and events[-1].status == 'complete'
                assert backend.get_status().current_location == 'exhibit_01'
                assert not (await backend.navigate_to('exhibit_01', 1.0, task_id='n1')).success
        finally:
            await backend.disconnect()

    asyncio.run(scenario())


def test_urgent_stop_is_sent_while_navigation_and_speech_active():
    async def scenario():
        backend = make_backend()
        await backend.connect()
        try:
            async with authorized(backend) as socket:
                await handshake(backend, socket)
                events = []
                nav = asyncio.create_task(backend.navigate_to('exhibit_01', 2.0, task_id='nav', feedback=events.append))
                nav_command = await receive(socket)
                await ack(socket, nav_command)
                await event(socket, nav_command, 'navigation_status', 'going')
                speech = asyncio.create_task(backend.speak('欢迎', task_id='say'))
                speech_command = await receive(socket)
                await ack(socket, speech_command)
                stop = asyncio.create_task(backend.stop())
                stop_command = await receive(socket)
                assert stop_command['command'] == 'stop' and stop_command['target_id'] == 'nav'
                await ack(socket, stop_command)
                await event(socket, stop_command, 'stop_status', 'complete')
                await event(socket, nav_command, 'navigation_status', 'complete', 'late event')
                assert (await stop).success and not (await nav).success
                assert events[-1].status == 'stopped' and not backend.get_status().is_moving
                assert not speech.done()
                await event(socket, speech_command, 'speech_status', 'complete')
                assert (await speech).success
        finally:
            await backend.disconnect()

    asyncio.run(scenario())


def test_deadline_timeout_attempts_stop_and_ignores_late_navigation_event():
    async def scenario():
        backend = make_backend(ack_timeout_sec=0.08)
        await backend.connect()
        try:
            async with authorized(backend) as socket:
                await handshake(backend, socket)
                events = []
                nav = asyncio.create_task(backend.navigate_to('exhibit_01', 0.12, task_id='expire', feedback=events.append))
                command = await receive(socket)
                await ack(socket, command)
                stop_command = await receive(socket)  # 导航超时后独立 STOP
                assert stop_command['command'] == 'stop'
                await event(socket, command, 'navigation_status', 'complete')
                await ack(socket, stop_command)
                await event(socket, stop_command, 'stop_status', 'complete')
                assert not (await nav).success and events[-1].status == 'timeout'
                assert backend.get_status().current_location == 'entrance'
                assert not (await backend.navigate_to('exhibit_01', 1.0, task_id='expire')).success
        finally:
            await backend.disconnect()

    asyncio.run(scenario())


def test_lost_connection_fails_active_commands_and_reconnect_syncs_state():
    async def scenario():
        backend = make_backend()
        await backend.connect()
        try:
            async with authorized(backend) as socket:
                await handshake(backend, socket)
                old_epoch = backend.get_status().connection_epoch
                nav = asyncio.create_task(backend.navigate_to('exhibit_01', 2.0, task_id='old'))
                command = await receive(socket)
                await ack(socket, command)
                await socket.close()
                assert not (await nav).success
                await wait_until(lambda: not backend.get_status().connected)
            assert not (await backend.speak('offline', task_id='offline')).success
            async with authorized(backend) as socket:
                await handshake(backend, socket, x=0.4, battery_percentage=67.0)
                assert backend.get_status().connection_epoch == old_epoch + 1
                assert backend.get_status().x == 0.4 and backend.get_status().battery_percentage == 67.0
                assert not (await backend.navigate_to('exhibit_01', 1.0, task_id='old')).success
                new = asyncio.create_task(backend.speak('恢复', task_id='new'))
                command = await receive(socket)
                assert command['id'] == 'new' and command['command'] == 'speak'
                await ack(socket, command)
                await event(socket, command, 'speech_status', 'complete')
                assert (await new).success
        finally:
            await backend.disconnect()

    asyncio.run(scenario())


def test_speech_cancel_sends_cancel_command_and_propagates():
    async def scenario():
        backend = make_backend()
        await backend.connect()
        try:
            async with authorized(backend) as socket:
                await handshake(backend, socket)
                task = asyncio.create_task(backend.speak('取消', task_id='speech'))
                command = await receive(socket)
                await ack(socket, command)
                await asyncio.sleep(0.02)
                task.cancel()
                cancel = await receive(socket)
                assert cancel['command'] == 'cancel_speech' and cancel['target_id'] == 'speech'
                await ack(socket, cancel)
                await event(socket, cancel, 'speech_cancel_status', 'complete')
                with pytest.raises(asyncio.CancelledError):
                    await task
        finally:
            await backend.disconnect()

    asyncio.run(scenario())


def test_first_state_timeout_releases_single_client_slot():
    async def scenario():
        backend = make_backend(ack_timeout_sec=0.08)
        await backend.connect()
        try:
            async with authorized(backend) as socket:
                await send(socket, {'type': 'hello', 'protocol_version': 1})
                await receive(socket)
                await receive(socket)
                with pytest.raises(ConnectionClosed):
                    await asyncio.wait_for(socket.recv(), 0.5)
            async with authorized(backend) as socket:
                await handshake(backend, socket)
        finally:
            await backend.disconnect()

    asyncio.run(scenario())


def test_missing_pong_loses_ready_connection():
    async def scenario():
        backend = make_backend(heartbeat_interval_sec=0.05, heartbeat_timeout_sec=0.05)
        await backend.connect()
        try:
            async with authorized(backend) as socket:
                await handshake(backend, socket)
                # 暂停客户端 socket 读取，实际阻止其回应服务器 Ping。
                socket.transport.pause_reading()
                try:
                    await wait_until(lambda: not backend.get_status().connected, timeout=2.0)
                finally:
                    socket.transport.resume_reading()
        finally:
            await backend.disconnect()

    asyncio.run(scenario())


def test_unconfirmed_stop_blocks_navigation_until_confirmed_stop():
    async def scenario():
        backend = make_backend(stop_timeout_sec=0.12, ack_timeout_sec=0.06)
        await backend.connect()
        try:
            async with authorized(backend) as socket:
                await handshake(backend, socket)
                stop = asyncio.create_task(backend.stop())
                command = await receive(socket)
                await ack(socket, command)
                assert not (await stop).success
                await send(socket, state_message(x=0.25, is_moving=False))
                await wait_until(lambda: backend.get_status().x == 0.25)
                assert not (await backend.navigate_to('exhibit_01', 1.0, task_id='blocked')).success
                stop = asyncio.create_task(backend.stop())
                command = await receive(socket)
                await ack(socket, command)
                await event(socket, command, 'stop_status', 'complete')
                assert (await stop).success
                nav = asyncio.create_task(backend.navigate_to('exhibit_01', 1.0, task_id='allowed'))
                command = await receive(socket)
                await ack(socket, command)
                await event(socket, command, 'navigation_status', 'complete')
                assert (await nav).success
        finally:
            await backend.disconnect()

    asyncio.run(scenario())


def test_ack_rejection_and_missing_ack_fail_without_replay():
    async def scenario():
        backend = make_backend(ack_timeout_sec=0.06)
        await backend.connect()
        try:
            async with authorized(backend) as socket:
                await handshake(backend, socket)
                rejected = asyncio.create_task(backend.navigate_to('exhibit_01', 1.0, task_id='rejected'))
                command = await receive(socket)
                await ack(socket, command, accepted=False)
                assert not (await rejected).success
                unanswered = asyncio.create_task(backend.navigate_to('exhibit_01', 1.0, task_id='unanswered'))
                command = await receive(socket)
                stop = await receive(socket)
                assert stop['command'] == 'stop' and stop['target_id'] == 'unanswered'
                await ack(socket, stop)
                await event(socket, stop, 'stop_status', 'complete')
                assert not (await unanswered).success
                assert not (await backend.navigate_to('exhibit_01', 1.0, task_id='unanswered')).success
        finally:
            await backend.disconnect()

    asyncio.run(scenario())


def test_unconfirmed_speech_cancel_blocks_replacement_until_reconnect():
    async def scenario():
        backend = make_backend(speech_timeout_sec=0.1, ack_timeout_sec=0.05)
        await backend.connect()
        try:
            async with authorized(backend) as socket:
                await handshake(backend, socket)
                speech = asyncio.create_task(backend.speak('超时语音', task_id='old_speech'))
                command = await receive(socket)
                await ack(socket, command)
                cancel = await receive(socket)
                assert cancel['command'] == 'cancel_speech'
                result = await speech
                assert not result.success and '取消未确认' in result.message
                assert not (await backend.speak('新语音', task_id='blocked')).success
            await wait_until(lambda: not backend.get_status().connected)
            async with authorized(backend) as socket:
                await handshake(backend, socket)
                speech = asyncio.create_task(backend.speak('新语音', task_id='fresh'))
                command = await receive(socket)
                await ack(socket, command)
                await event(socket, command, 'speech_status', 'complete')
                assert (await speech).success
        finally:
            await backend.disconnect()

    asyncio.run(scenario())


def test_graceful_disconnect_requests_stop_and_speech_cancel_before_closing():
    async def scenario():
        backend = make_backend()
        await backend.connect()
        try:
            async with authorized(backend) as socket:
                await handshake(backend, socket)
                nav = asyncio.create_task(backend.navigate_to('exhibit_01', 2.0, task_id='nav'))
                command = await receive(socket)
                await ack(socket, command)
                await event(socket, command, 'navigation_status', 'going')
                speech = asyncio.create_task(backend.speak('播报', task_id='speech'))
                command = await receive(socket)
                await ack(socket, command)
                close = asyncio.create_task(backend.disconnect())
                command = await receive(socket)
                assert command['command'] == 'stop'
                await ack(socket, command)
                await event(socket, command, 'stop_status', 'complete')
                command = await receive(socket)
                assert command['command'] == 'cancel_speech'
                await ack(socket, command)
                await event(socket, command, 'speech_cancel_status', 'complete')
                assert (await close).success
                assert not (await nav).success and not (await speech).success
                assert not backend.get_status().connected
        finally:
            await backend.disconnect()

    asyncio.run(scenario())


def test_speed_command_is_bound_to_current_navigation_session_and_software_limits():
    from temi_bridge.protocol import ProtocolError, make_command

    command = make_command('set_speed', 'speed_01', 2.0,
                           navigation_session_id='nav_01', target_speed_mps=0.6,
                           control_reason='crowd')
    assert command['navigation_session_id'] == 'nav_01'
    assert command['target_speed_mps'] == 0.6
    with pytest.raises(ProtocolError):
        make_command('set_speed', 'speed_02', 2.0,
                     navigation_session_id='old', target_speed_mps=0.0,
                     control_reason='stop')


def test_current_navigation_speed_command_waits_for_correlated_sdk_result():
    async def scenario():
        backend = make_backend()
        await backend.connect()
        try:
            async with authorized(backend) as socket:
                await handshake(backend, socket)
                navigation = asyncio.create_task(backend.navigate_to('exhibit_01', 2.0, task_id='nav_speed'))
                nav_command = await receive(socket)
                await ack(socket, nav_command)
                await event(socket, nav_command, 'navigation_status', 'going')
                speed = asyncio.create_task(backend.set_navigation_speed(
                    0.6, command_id='speed_ok', navigation_session_id='nav_speed',
                    control_reason='crowd'))
                command = await receive(socket)
                assert command['command'] == 'set_speed'
                assert command['navigation_session_id'] == 'nav_speed'
                assert command['target_speed_mps'] == 0.6
                await ack(socket, command)
                await event(socket, command, 'speed_status', 'complete', 'sdk_code=200')
                assert (await speed).success
                stale = await backend.set_navigation_speed(
                    0.7, command_id='speed_stale', navigation_session_id='old', control_reason='open')
                assert not stale.success
                await event(socket, nav_command, 'navigation_status', 'complete')
                assert (await navigation).success
        finally:
            await backend.disconnect()

    asyncio.run(scenario())
