import asyncio
import pytest

from temi_bridge.nav2_backend import Nav2Backend


class Transport:
    def __init__(self):
        self.destinations = []
        self.started = asyncio.Event()
        self.finished = asyncio.Event()
        self.cancelled = False
    async def navigate(self, pose, *, on_active=None):
        self.destinations.append(pose)
        self.started.set()
        if on_active is not None:
            on_active()
        await self.finished.wait()
        return True
    async def stop(self):
        self.cancelled = True
        self.finished.set()
        return True
    def ready(self):
        return True
    def snapshot(self):
        return {'x': 0.0, 'y': 0.0, 'yaw': 0.0, 'moving': False}


def test_nav2_backend_binds_gateway_task_id_to_transport_safety_state():
    class SessionTransport(Transport):
        def __init__(self):
            super().__init__()
            self.session_id = ''
            self.finished.set()

        def set_navigation_session_id(self, session_id):
            self.session_id = session_id

    async def scenario():
        transport = SessionTransport()
        backend = Nav2Backend(transport, {'zone_1': {'x': 1., 'y': 2., 'yaw': 0.}})
        await backend.connect()
        result = await backend.navigate_to('zone_1', 2, task_id='current-task')

        assert result.success
        assert transport.session_id == 'current-task'

    asyncio.run(scenario())


def test_nav2_backend_reports_navigation_events_with_the_gateway_task_id():
    async def scenario():
        transport = Transport()
        transport.finished.set()
        backend = Nav2Backend(transport, {'zone_1': {'x': 1., 'y': 2., 'yaw': 0.}})
        await backend.connect()
        events = []

        result = await backend.navigate_to(
            'zone_1', 2, task_id='active-task', feedback=events.append)

        assert result.success
        assert [event.status for event in events] == ['start', 'calculating', 'going', 'complete']
        assert all(event.task_id == 'active-task' and event.target == 'zone_1' for event in events)

    asyncio.run(scenario())


def test_interaction_route_uses_waypoints_only_after_zone_four():
    async def scenario():
        transport = Transport()
        transport.finished.set()
        goals = {'zone_4': {'x': 0., 'y': 0., 'yaw': 0.}, 'zone_5': {'x': 5., 'y': 5., 'yaw': 0.}}
        waypoints = {('zone_4', 'zone_5'): [{'x': 1., 'y': 1., 'yaw': 0.}, {'x': 2., 'y': 2., 'yaw': 0.}]}
        backend = Nav2Backend(transport, goals, waypoints)
        await backend.connect()
        assert (await backend.navigate_to('zone_4', 2, task_id='a')).success
        assert (await backend.navigate_to('zone_5', 2, task_id='b')).success
        assert transport.destinations == [goals['zone_4'], *waypoints[('zone_4', 'zone_5')], goals['zone_5']]
    asyncio.run(scenario())


def test_nav2_backend_validates_maps_and_stops_active_motion():
    async def scenario():
        transport = Transport()
        backend = Nav2Backend(transport, {'zone_1': {'x': 1., 'y': 2., 'yaw': 0.}})
        assert (await backend.connect()).success
        assert not (await backend.navigate_to('missing', 1, task_id='a')).success
        nav = asyncio.create_task(backend.navigate_to('zone_1', 5, task_id='b'))
        await transport.started.wait()
        assert not (await backend.navigate_to('zone_1', 5, task_id='c')).success
        assert (await backend.stop()).success
        assert not (await nav).success
        assert transport.cancelled and transport.destinations == [{'x': 1., 'y': 2., 'yaw': 0.}]
        assert (await backend.speak('测试', task_id='s')).message == '模拟播报完成（无真实音频）'
        await backend.disconnect()
    asyncio.run(scenario())


def test_nav2_backend_times_out_and_stops():
    async def scenario():
        transport = Transport()
        backend = Nav2Backend(transport, {'zone_1': {'x': 1., 'y': 2., 'yaw': 0.}})
        await backend.connect()
        result = await backend.navigate_to('zone_1', 0.02, task_id='a')
        assert not result.success and transport.cancelled
    asyncio.run(scenario())


def test_cancelling_navigation_stops_transport_and_unlocks():
    async def scenario():
        transport = Transport()
        backend = Nav2Backend(transport, {'zone_1': {'x': 1., 'y': 2., 'yaw': 0.}})
        await backend.connect()
        events = []
        nav = asyncio.create_task(backend.navigate_to(
            'zone_1', 5, task_id='a', feedback=events.append))
        await transport.started.wait()
        nav.cancel()
        with pytest.raises(asyncio.CancelledError):
            await nav
        assert transport.cancelled and not backend.active
        assert events[-1].status == 'cancelled'
        assert events[-1].task_id == 'a'
    asyncio.run(scenario())
