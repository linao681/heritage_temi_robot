import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros2_ws/src/temi_bridge'))

from temi_bridge.nav2_transport import arrival_stop_confirmed


def test_arrival_requires_fresh_odom_and_a_continuous_stationary_window():
    assert not arrival_stop_confirmed(stable_since=10.0, last_sample=10.4, now=10.49)
    assert arrival_stop_confirmed(stable_since=10.0, last_sample=10.49, now=10.5)


def test_arrival_is_not_confirmed_by_stale_odom():
    assert not arrival_stop_confirmed(stable_since=10.0, last_sample=10.0, now=10.6)


def test_arrival_is_not_confirmed_when_the_stationary_window_was_reset_by_motion():
    assert not arrival_stop_confirmed(stable_since=None, last_sample=10.49, now=10.8)
