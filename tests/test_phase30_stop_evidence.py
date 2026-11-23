from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from run_visitor_full_demo import StationaryStopWindow, pause_stop_evidence


def sample(received=1.0, stamp_ns=1_000_000_000, *, linear=0.005, angular=0.01,
           cmd_linear=0.0, session='nav-a', odom_fresh=True, odom_age=0.02,
           stop_session='nav-a'):
    return {
        'tour': {'state': 'PAUSED', 'pause_source': 'safety',
                 'paused_session_id': session, 'is_moving': False,
                 'last_pause_stop_requested': True,
                 'last_pause_stop_confirmed': True,
                 'last_pause_action_quiescence_confirmed': True},
        'evidence': {
            'odom': {'fresh': odom_fresh, 'age_sec': odom_age, 'value': {
                'linear_speed_mps': linear, 'angular_speed_rps': angular,
                'stamp_ns': stamp_ns, 'received_monotonic_sec': received}},
            'cmd_vel': {'fresh': True, 'age_sec': 0.02, 'value': {
                'linear_speed_mps': cmd_linear, 'angular_speed_rps': 0.0,
                'received_monotonic_sec': received}},
            'fused': {'fresh': True, 'age_sec': 0.02, 'value': {
                'stop_confirmed': True,
                'stop_confirmed_session_id': stop_session}},
        },
    }


def test_single_or_repeated_http_snapshot_does_not_confirm_stationary_window():
    window = StationaryStopWindow()
    first = sample()
    assert not pause_stop_evidence(first, window)['confirmed']
    repeated = sample(received=1.6, stamp_ns=1_000_000_000)
    assert not pause_stop_evidence(repeated, window)['confirmed']


def test_unique_fresh_odom_samples_confirm_half_second_stationary_window():
    window = StationaryStopWindow()
    result = None
    for index in range(6):
        result = pause_stop_evidence(
            sample(received=1.0 + index * 0.1,
                   stamp_ns=1_000_000_000 + index * 100_000_000), window)
    assert result['confirmed'] is True
    assert result['sample_count'] == 6
    assert result['stable_duration_sec'] >= 0.5


def test_pause_stop_requires_bounded_absolute_linear_and_angular_speed():
    for bad in (sample(linear=-0.03), sample(angular=0.06), sample(linear=float('nan')),
                sample(angular=float('inf'))):
        assert pause_stop_evidence(bad, StationaryStopWindow())['confirmed'] is False


def test_pause_stop_requires_matching_pause_session_and_fresh_odom():
    assert not pause_stop_evidence(sample(stop_session='old-nav'),
                                   StationaryStopWindow())['confirmed']
    assert not pause_stop_evidence(sample(odom_fresh=False),
                                   StationaryStopWindow())['confirmed']
    assert not pause_stop_evidence(sample(odom_age=-0.01),
                                   StationaryStopWindow())['confirmed']


def test_pause_stop_requires_manager_stop_ack_and_action_quiescence():
    missing_stop_ack = sample()
    missing_stop_ack['tour']['last_pause_stop_confirmed'] = False
    assert not pause_stop_evidence(missing_stop_ack, StationaryStopWindow())['sample_valid']
    missing_quiescence = sample()
    missing_quiescence['tour']['last_pause_action_quiescence_confirmed'] = False
    assert not pause_stop_evidence(missing_quiescence, StationaryStopWindow())['sample_valid']


def test_long_gap_and_new_motion_reset_stationary_window():
    window = StationaryStopWindow()
    pause_stop_evidence(sample(), window)
    gap_result = pause_stop_evidence(
        sample(received=1.3, stamp_ns=1_300_000_000), window)
    assert gap_result['sample_count'] == 1
    motion_result = pause_stop_evidence(
        sample(received=1.4, stamp_ns=1_400_000_000, linear=0.04), window)
    assert motion_result['confirmed'] is False
    assert motion_result['sample_count'] == 0


def test_fresh_nonzero_cmd_vel_resets_stationary_window():
    window = StationaryStopWindow()
    pause_stop_evidence(sample(), window)
    moved_command = sample(received=1.1, stamp_ns=1_100_000_000,
                           cmd_linear=0.1)
    result = pause_stop_evidence(moved_command, window)
    assert result['confirmed'] is False
    assert result['sample_count'] == 0
