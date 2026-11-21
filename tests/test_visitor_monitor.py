"""验证匿名人数的稳定判断、团队事件及断流，不依赖 ROS2。"""

from pathlib import Path

import pytest

from visitor_perception.visitor_monitor import VisitorConfig, VisitorMonitor


def stable(monitor, count, start):
    events = []
    for index in range(3):
        events.extend(monitor.observe(count, start + index * 0.1))
    return events


def test_initial_unknown_and_first_zero_is_not_departure():
    monitor = VisitorMonitor(VisitorConfig())
    assert monitor.snapshot() == {
        'valid': False, 'people_count': None, 'expected_count': 0,
        'group_state': 'untracked', 'source': 'mock', 'stable': False, 'stable_fresh': False,
        'sample_timestamp_monotonic_sec': None, 'sample_age_sec': None,
    }
    assert monitor.tick(10.0) == []
    assert stable(monitor, 0, 11.0) == []
    assert monitor.snapshot()['valid'] and monitor.snapshot()['people_count'] == 0


def test_arrival_requires_consecutive_equal_counts():
    monitor = VisitorMonitor(VisitorConfig())
    assert monitor.observe(3, 0.1) == []
    assert monitor.observe(2, 0.2) == []
    assert monitor.observe(3, 0.3) == []
    assert monitor.observe(3, 0.4) == []
    assert monitor.observe(3, 0.5) == ['arrival']
    assert monitor.observe(3, 0.6) == []
    assert monitor.snapshot()['people_count'] == 3


def test_count_changes_without_new_arrival_and_transient_occlusion_filtered():
    monitor = VisitorMonitor(VisitorConfig())
    assert stable(monitor, 3, 0.1) == ['arrival']
    assert monitor.observe(0, 0.5) == []
    assert monitor.snapshot()['people_count'] == 3
    assert stable(monitor, 2, 0.6) == []
    assert monitor.snapshot()['people_count'] == 2
    assert stable(monitor, 0, 1.0) == ['departure']
    assert stable(monitor, 0, 1.4) == []
    assert stable(monitor, 1, 1.8) == ['arrival']


def test_snapshot_exposes_monotonic_timestamp_and_age():
    monitor = VisitorMonitor(VisitorConfig())
    assert stable(monitor, 2, 10.0) == ['arrival']

    snapshot = monitor.snapshot(now=10.5)

    assert snapshot['sample_timestamp_monotonic_sec'] == 10.2
    assert snapshot['sample_age_sec'] == pytest.approx(0.3)


def test_camera_is_a_distinct_live_count_source():
    monitor = VisitorMonitor(VisitorConfig(count_source='camera'))
    assert monitor.snapshot()['source'] == 'camera'


def test_tracking_only_after_explicit_expected_count():
    monitor = VisitorMonitor(VisitorConfig())
    assert stable(monitor, 3, 0.1) == ['arrival']
    assert stable(monitor, 2, 0.5) == []
    assert monitor.snapshot()['group_state'] == 'untracked'
    assert monitor.set_expected_count(3, 0.8) == []
    assert monitor.snapshot()['group_state'] == 'unknown'
    assert stable(monitor, 2, 1.0) == ['visitor_lost']
    assert monitor.snapshot()['group_state'] == 'lost'
    assert monitor.set_expected_count(3, 1.3) == []
    assert stable(monitor, 1, 1.4) == []
    assert stable(monitor, 4, 1.8) == ['regrouped']
    assert monitor.snapshot()['group_state'] == 'following'
    assert stable(monitor, 3, 2.2) == []
    assert monitor.set_expected_count(0, 2.6) == []
    assert stable(monitor, 0, 2.8) == ['departure']
    assert monitor.snapshot()['group_state'] == 'untracked'


def test_stale_preserves_previous_presence_and_loss_latch():
    monitor = VisitorMonitor(VisitorConfig(stale_timeout_sec=1.0))
    monitor.set_expected_count(3, 0.0)
    assert stable(monitor, 2, 0.1) == ['arrival', 'visitor_lost']
    assert monitor.tick(1.4) == ['data_stale']
    assert monitor.snapshot()['people_count'] is None
    assert not monitor.snapshot()['valid']
    assert monitor.snapshot()['group_state'] == 'unknown'
    assert monitor.tick(1.5) == []
    assert stable(monitor, 2, 1.6) == ['data_restored']
    assert monitor.snapshot()['group_state'] == 'lost'
    assert stable(monitor, 3, 2.0) == ['regrouped']


def test_long_gap_breaks_candidate_even_before_timer_ticks():
    monitor = VisitorMonitor(VisitorConfig(stale_timeout_sec=1.0))
    assert monitor.observe(3, 0.0) == []
    assert monitor.observe(3, 0.1) == []
    assert monitor.observe(3, 1.2) == ['data_stale']
    assert monitor.observe(3, 1.3) == []
    assert monitor.observe(3, 1.4) == ['data_restored', 'arrival']


def test_invalid_observation_breaks_candidate_and_does_not_refresh_timeout():
    monitor = VisitorMonitor(VisitorConfig(stale_timeout_sec=1.0))
    assert stable(monitor, 3, 0.0) == ['arrival']
    assert monitor.observe(0, 0.4) == []
    assert monitor.observe(-1, 0.5) == []
    assert monitor.observe(0, 0.6) == []
    assert monitor.observe(0, 0.7) == []
    assert monitor.snapshot()['people_count'] == 3
    assert monitor.set_expected_count(-1, 0.8) == []
    assert monitor.snapshot()['expected_count'] == 0
    assert monitor.observe(-1, 1.8) == ['data_stale']
    assert stable(monitor, 0, 2.0) == ['data_restored', 'departure']


def test_new_expected_count_resets_comparison_and_deduplicates_events():
    monitor = VisitorMonitor(VisitorConfig())
    monitor.set_expected_count(3, 0.0)
    assert stable(monitor, 2, 0.1) == ['arrival', 'visitor_lost']
    monitor.set_expected_count(2, 0.4)
    assert monitor.snapshot()['group_state'] == 'unknown'
    assert stable(monitor, 2, 0.5) == []
    assert monitor.snapshot()['group_state'] == 'following'


@pytest.mark.parametrize('kwargs', [
    {'stable_samples': 0}, {'stable_samples': 1.5}, {'stable_samples': True},
    {'stale_timeout_sec': 0}, {'stale_timeout_sec': float('inf')},
    {'stale_timeout_sec': float('nan')}, {'stale_timeout_sec': True},
])
def test_invalid_config_rejected(kwargs):
    with pytest.raises(ValueError):
        VisitorConfig(**kwargs)


def test_configuration_loaded_from_project_yaml():
    root = Path(__file__).resolve().parents[1]
    assert VisitorConfig.from_yaml(root / 'config/system.yaml') == VisitorConfig()


def test_continuous_unstable_counts_do_not_refresh_stable_confirmation():
    monitor = VisitorMonitor(VisitorConfig(stale_timeout_sec=1.0))
    assert stable(monitor, 3, 0.0) == ['arrival']
    assert monitor.snapshot()['stable'] and monitor.snapshot()['stable_fresh']
    for index in range(1, 7):
        assert monitor.observe(2 if index % 2 else 3, 0.2 + index * 0.2) == []
        assert not monitor.snapshot()['stable']
    assert monitor.snapshot()['valid'] and not monitor.snapshot()['stable_fresh']
    assert monitor.snapshot()['people_count'] == 3
    assert stable(monitor, 3, 1.6) == []
    assert monitor.snapshot()['stable_fresh'] and monitor.snapshot()['stable']
