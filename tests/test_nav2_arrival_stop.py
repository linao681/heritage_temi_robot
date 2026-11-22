import sys
import asyncio
import math
from threading import Lock
from types import SimpleNamespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros2_ws/src/temi_bridge'))

from temi_bridge import nav2_transport
from temi_bridge.nav2_transport import Nav2Transport, arrival_stop_confirmed


def test_arrival_requires_fresh_odom_and_a_continuous_stationary_window():
    assert not arrival_stop_confirmed(stable_since=10.0, last_sample=10.4, now=10.49)
    assert arrival_stop_confirmed(stable_since=10.0, last_sample=10.49, now=10.5)


def test_arrival_is_not_confirmed_by_stale_odom():
    assert not arrival_stop_confirmed(stable_since=10.0, last_sample=10.0, now=10.6)


def test_arrival_is_not_confirmed_when_the_stationary_window_was_reset_by_motion():
    assert not arrival_stop_confirmed(stable_since=None, last_sample=10.49, now=10.8)


def transport_state():
    transport = Nav2Transport.__new__(Nav2Transport)
    transport._mutex = Lock()
    transport._last_odom = 10.0
    transport._last_odom_stamp_ns = 99_900_000_000
    transport._odom_initial_age = 0.1
    transport._unsafe = False
    transport._stop_action_terminal = False
    transport._stop_was_confirmed = False
    return transport


def transform_at(seconds):
    return SimpleNamespace(header=SimpleNamespace(
        stamp=SimpleNamespace(sec=int(seconds), nanosec=int((seconds - int(seconds)) * 10**9))))


def test_transport_rejects_stale_tf_even_if_transform_is_available(monkeypatch):
    transport = transport_state()
    monkeypatch.setattr(nav2_transport.time, 'monotonic', lambda: 10.1)
    monkeypatch.setattr(Nav2Transport, 'get_clock', lambda _: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=100 * 10**9)))
    transport.client = SimpleNamespace(server_is_ready=lambda: True)
    transport.buffer = SimpleNamespace(can_transform=lambda *_: True,
                                       lookup_transform=lambda *_: transform_at(99.0))

    assert not transport.ready()
    transport.buffer.lookup_transform = lambda *_: transform_at(99.8)
    assert transport.ready()


def test_transport_accepts_tf_with_bounded_future_sim_clock_skew(monkeypatch):
    transport = transport_state()
    monkeypatch.setattr(nav2_transport.time, 'monotonic', lambda: 10.1)
    monkeypatch.setattr(Nav2Transport, 'get_clock', lambda _: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=100 * 10**9)))
    transport.client = SimpleNamespace(server_is_ready=lambda: True)
    transport.buffer = SimpleNamespace(can_transform=lambda *_: True,
                                       lookup_transform=lambda *_: transform_at(100.1))

    assert transport.ready()


def test_transport_rejects_tf_beyond_future_sim_clock_skew_bound(monkeypatch):
    transport = transport_state()
    monkeypatch.setattr(nav2_transport.time, 'monotonic', lambda: 10.1)
    monkeypatch.setattr(Nav2Transport, 'get_clock', lambda _: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=100 * 10**9)))
    transport.client = SimpleNamespace(server_is_ready=lambda: True)
    transport.buffer = SimpleNamespace(can_transform=lambda *_: True,
                                       lookup_transform=lambda *_: transform_at(100.2))

    assert not transport.ready()


def test_transport_uses_stop_odom_freshness_at_navigation_reentry(monkeypatch):
    transport = transport_state()
    monkeypatch.setattr(nav2_transport.time, 'monotonic', lambda: 10.6)
    monkeypatch.setattr(Nav2Transport, 'get_clock', lambda _: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=100 * 10**9)))
    transport.client = SimpleNamespace(server_is_ready=lambda: True)
    transport.buffer = SimpleNamespace(can_transform=lambda *_: True,
                                       lookup_transform=lambda *_: transform_at(99.8))

    assert not transport.ready()


def test_motion_during_stop_window_invalidates_previous_stationary_history(monkeypatch):
    transport = transport_state()
    transport._stop_state = 'STOPPING'
    transport._stop_stable_since = transport._arrival_stable_since = 9.9
    monkeypatch.setattr(nav2_transport.time, 'monotonic', lambda: 10.6)
    monkeypatch.setattr(Nav2Transport, 'get_clock', lambda _: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=100 * 10**9)))
    message = SimpleNamespace(header=transform_at(100.0).header,
        twist=SimpleNamespace(twist=SimpleNamespace(
        linear=SimpleNamespace(x=0., y=0.), angular=SimpleNamespace(z=0.))))

    transport._odom(message)

    assert transport._stop_stable_since == 10.6
    assert transport._arrival_stable_since == 10.6


def test_fresh_arrival_of_stale_stamped_odom_cannot_qualify_stop(monkeypatch):
    transport = transport_state()
    transport._stop_state = 'STOPPING'
    transport._stop_stable_since = transport._arrival_stable_since = 9.9
    transport._last_odom_stamp_ns = 99_900_000_000
    monkeypatch.setattr(nav2_transport.time, 'monotonic', lambda: 10.1)
    monkeypatch.setattr(Nav2Transport, 'get_clock', lambda _: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=100 * 10**9)))
    message = SimpleNamespace(header=transform_at(99.0).header,
        twist=SimpleNamespace(twist=SimpleNamespace(
            linear=SimpleNamespace(x=0., y=0.), angular=SimpleNamespace(z=0.))))

    transport._odom(message)
    assert transport._stop_stable_since is None
    assert transport._arrival_stable_since is None


def test_odom_accepts_bounded_future_stamp_skew_from_sim_clock(monkeypatch):
    transport = transport_state()
    transport._stop_state = 'CLEAR'
    transport._stop_stable_since = transport._arrival_stable_since = None
    monkeypatch.setattr(nav2_transport.time, 'monotonic', lambda: 10.1)
    monkeypatch.setattr(Nav2Transport, 'get_clock', lambda _: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=100 * 10**9)))
    message = SimpleNamespace(header=SimpleNamespace(stamp=SimpleNamespace(
        sec=100, nanosec=100_000_000)),
        twist=SimpleNamespace(twist=SimpleNamespace(
            linear=SimpleNamespace(x=0., y=0.), angular=SimpleNamespace(z=0.))))

    transport._odom(message)

    assert transport._last_odom == 10.1
    assert transport._last_odom_stamp_ns == 100_100_000_000
    assert transport._odom_initial_age == 0.0


def test_odom_rejects_future_stamp_beyond_sim_clock_skew_bound(monkeypatch):
    transport = transport_state()
    transport._stop_state = 'CLEAR'
    monkeypatch.setattr(nav2_transport.time, 'monotonic', lambda: 10.1)
    monkeypatch.setattr(Nav2Transport, 'get_clock', lambda _: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=100 * 10**9)))
    message = SimpleNamespace(header=transform_at(100.2).header,
        twist=SimpleNamespace(twist=SimpleNamespace(
            linear=SimpleNamespace(x=0., y=0.), angular=SimpleNamespace(z=0.))))

    transport._odom(message)

    assert transport._last_odom == 0.0
    assert transport._last_odom_stamp_ns == 99_900_000_000


def test_odom_age_uses_receipt_age_for_bounded_future_stamps(monkeypatch):
    transport = transport_state()
    transport._last_odom_stamp_ns = 100_100_000_000
    transport._odom_initial_age = 0.0
    monkeypatch.setattr(nav2_transport.time, 'monotonic', lambda: 10.2)
    monkeypatch.setattr(Nav2Transport, 'get_clock', lambda _: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=100 * 10**9)))

    assert transport._odom_age(10.2) == pytest.approx(0.2)


def test_odom_age_rejects_future_stamp_beyond_clock_skew_bound(monkeypatch):
    transport = transport_state()
    transport._last_odom_stamp_ns = 100_200_000_000
    transport._odom_initial_age = 0.0
    monkeypatch.setattr(nav2_transport.time, 'monotonic', lambda: 10.2)
    monkeypatch.setattr(Nav2Transport, 'get_clock', lambda _: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=100 * 10**9)))

    assert math.isinf(transport._odom_age(10.2))


def test_confirmed_stop_after_odom_gap_requires_a_new_stationary_window(monkeypatch):
    transport = transport_state()
    transport._stop_state = 'STOP_CONFIRMED'
    transport._stop_action_terminal = True
    transport._stop_stable_since = transport._arrival_stable_since = 9.0
    transport._last_odom_stamp_ns = 99_000_000_000
    now = [10.6]
    monkeypatch.setattr(nav2_transport.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(Nav2Transport, 'get_clock', lambda _: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=int((90.0 + now[0]) * 10**9))))
    message = SimpleNamespace(twist=SimpleNamespace(twist=SimpleNamespace(
        linear=SimpleNamespace(x=0., y=0.), angular=SimpleNamespace(z=0.))))
    for sample in (10.6, 10.8, 11.0, 11.11):
        now[0] = sample
        message.header = transform_at(90.0 + sample).header
        transport._odom(message)
    assert transport._stop_stable_since == 10.6
    assert arrival_stop_confirmed(transport._stop_stable_since, transport._last_odom, 11.11)


def test_motion_after_confirmation_is_latched_even_after_intervening_stale_odom(monkeypatch):
    transport = transport_state()
    transport._stop_state = 'STOP_CONFIRMED'
    transport._stop_action_terminal = True
    transport._stop_stable_since = 9.0
    monkeypatch.setattr(nav2_transport.time, 'monotonic', lambda: 10.1)
    monkeypatch.setattr(Nav2Transport, 'get_clock', lambda _: SimpleNamespace(
        now=lambda: SimpleNamespace(nanoseconds=100 * 10**9)))
    message = SimpleNamespace(header=transform_at(99.0).header,
        twist=SimpleNamespace(twist=SimpleNamespace(
            linear=SimpleNamespace(x=0., y=0.), angular=SimpleNamespace(z=0.))))
    transport._odom(message)
    message.header = transform_at(100.0).header
    message.twist.twist.angular.z = 0.1
    transport._odom(message)

    assert transport._unsafe
    assert transport._stop_state == 'STOP_FAILED'
    assert transport._stop_stable_since is None


def test_failed_nav2_parameter_readback_rolls_back_both_servers():
    transport = transport_state()
    old_controller = [0.5, 0.5]
    old_smoother = [0.5, 0.0, 1.0]
    controller = list(old_controller)
    smoother = list(old_smoother)
    readback_injected = False

    def read_controller(_):
        nonlocal readback_injected
        values = controller
        if controller[0] == 0.3 and not readback_injected:
            values = [0.29, 0.3]
            readback_injected = True
        return SimpleNamespace(values=[SimpleNamespace(double_value=i) for i in values])

    def set_controller(req):
        controller[:] = [p.value.double_value for p in req.parameters]
        return SimpleNamespace(results=[SimpleNamespace(successful=True) for _ in req.parameters])

    def set_smoother(req):
        smoother[:] = list(req.parameters[0].value.double_array_value)
        return SimpleNamespace(results=[SimpleNamespace(successful=True)])

    transport._controller_get = SimpleNamespace(service_is_ready=lambda: True, call_async=read_controller)
    transport._controller_set = SimpleNamespace(service_is_ready=lambda: True, call_async=set_controller)
    transport._smoother_get = SimpleNamespace(service_is_ready=lambda: True,
        call_async=lambda _: SimpleNamespace(values=[SimpleNamespace(double_array_value=smoother)]))
    transport._smoother_set = SimpleNamespace(service_is_ready=lambda: True, call_async=set_smoother)

    async def immediate(response, _):
        return response

    transport._future = immediate
    assert not asyncio.run(transport.set_speed(0.3))
    assert controller == old_controller
    assert smoother == old_smoother
