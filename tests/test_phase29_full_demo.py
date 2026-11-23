from pathlib import Path
import ast
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import run_visitor_full_demo as demo_runner
from run_visitor_full_demo import (
    ResourceBlocked, allocate_run_directory, build_run_manifest, parse_args,
    pause_stop_evidence, evaluate_resource_snapshot, gazebo_processes_from_ps,
    summarize_navigation_motion,
)


def test_full_demo_accepts_layout_mode_timeout_and_output_dir(tmp_path):
    args = parse_args([
        '--layout', 'adaptive', '--team-decision-mode', 'vision_conservative',
        '--timeout-sec', '900', '--output-dir', str(tmp_path / 'run'),
        '--expected-visitors', '3',
        '--domain-id', '232', '--gazebo-port', '11371', '--web-port', '8093',
    ])

    assert args.layout == 'adaptive'
    assert args.team_decision_mode == 'vision_conservative'
    assert args.timeout_sec == 900
    assert args.expected_visitors == 3
    assert args.output_dir == tmp_path / 'run'
    assert args.keep_open is False


def test_full_demo_rejects_unknown_layout_and_invalid_timeout():
    with pytest.raises(SystemExit):
        parse_args(['--layout', 'unknown'])
    with pytest.raises(SystemExit):
        parse_args(['--timeout-sec', '0'])


def test_full_demo_run_directory_is_unique_and_never_overwritten(tmp_path):
    first = allocate_run_directory(tmp_path, timestamp='run-fixed')
    second = allocate_run_directory(tmp_path, timestamp='run-fixed')

    assert first != second
    assert first.parent == second.parent == tmp_path
    assert first.is_dir() and second.is_dir()


def test_full_demo_startup_forwards_one_layout_to_every_component():
    script = (ROOT / 'scripts/start_phase25_system.sh').read_text()
    assert 'layout:=$layout' in script
    assert '--layout "$layout"' in script
    assert 'PHASE25_LAYOUT' not in script
    wrapper = (ROOT / 'scripts/start_full_visitor_demo.sh').read_text()
    assert '--keep-open' not in wrapper
    assert 'run_visitor_full_demo.py "$@"' in wrapper


def test_phase25_supervisor_starts_in_an_owned_session():
    tree = ast.parse((ROOT / 'scripts/run_visitor_full_demo.py').read_text())
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == 'Popen']
    launch = next(node for node in calls if any(
        isinstance(arg, ast.Constant) and isinstance(arg.value, str) and
        'start_phase25_system.sh' in arg.value for arg in ast.walk(node)))

    assert any(keyword.arg == 'start_new_session' and isinstance(keyword.value, ast.Constant)
               and keyword.value.value is True for keyword in launch.keywords)


def test_expected_visitor_count_is_an_explicit_observer_input():
    startup = (ROOT / 'scripts/start_phase25_system.sh').read_text()
    runner = (ROOT / 'scripts/run_visitor_full_demo.py').read_text()
    launch = (ROOT / 'ros2_ws/src/visitor_perception/launch/sensor_fusion.launch.py').read_text()
    observer = (ROOT / 'ros2_ws/src/visitor_perception/visitor_perception/ros_team_observer.py').read_text()
    assert 'PHASE25_EXPECTED_VISITORS' in runner
    assert 'expected_visitors:=$expected_visitors' in startup
    assert "DeclareLaunchArgument('expected_visitors'" in launch
    assert "self.declare_parameter('expected_count'" in observer


def test_pause_stop_requires_fresh_stationary_odom_and_manager_stop():
    sample = {'tour': {'is_moving': False}, 'evidence': {
        'odom': {'fresh': True, 'value': {'linear_speed_mps': 0.01}}}}
    assert pause_stop_evidence(sample)['confirmed'] is True
    sample['evidence']['odom']['fresh'] = False
    assert pause_stop_evidence(sample)['confirmed'] is False
    sample['evidence']['odom']['fresh'] = True
    sample['tour']['is_moving'] = True
    assert pause_stop_evidence(sample)['confirmed'] is False


def test_run_manifest_records_layout_mode_and_map_hashes(tmp_path):
    args = parse_args(['--layout', 'adaptive', '--team-decision-mode', 'vision_conservative',
                       '--expected-visitors', '3'])
    run = allocate_run_directory(tmp_path, timestamp='manifest')
    manifest = build_run_manifest(run, args, command=['demo', '--layout', 'adaptive'])

    assert manifest['layout'] == 'adaptive'
    assert manifest['team_decision_mode'] == 'vision_conservative'
    assert manifest['expected_visitors'] == 3
    assert manifest['team_truth_used_for_decision'] is False
    assert manifest['map_sha256']
    assert manifest['goals_sha256']
    assert manifest['git_head']
    assert manifest['dirty_source_sha256']


def test_heavy_run_resource_gate_blocks_low_memory_load_and_existing_gazebo():
    assert evaluate_resource_snapshot(5.9, 40.0, 0.5, 16)['ready'] is False
    assert evaluate_resource_snapshot(8.0, 40.0, 1.1, 16)['ready'] is False
    assert evaluate_resource_snapshot(8.0, 40.0, 0.5, 16, ['gzserver'])['ready'] is False
    assert evaluate_resource_snapshot(8.0, 40.0, 0.5, 16)['ready'] is True
    assert evaluate_resource_snapshot(8.0, 40.0, 0.5, 16,
                                      ports_available=False)['ready'] is False


def test_local_port_probe_reports_bind_errors_and_closes_sockets(monkeypatch):
    class FakeSocket:
        closed = False

        def bind(self, address):
            if address[1] == 11361:
                raise PermissionError('local bind denied')

        def close(self):
            self.closed = True

    probes = []

    def fake_socket(*_args):
        probe = FakeSocket()
        probes.append(probe)
        return probe

    monkeypatch.setattr(demo_runner.socket, 'socket', fake_socket)
    result = demo_runner._check_local_tcp_ports((('gazebo', 11361), ('web', 8089)))

    assert result == [
        {'name': 'gazebo', 'port': 11361, 'bindable': False,
         'error': 'PermissionError: local bind denied'},
        {'name': 'web', 'port': 8089, 'bindable': True},
    ]
    assert all(probe.closed for probe in probes)


def test_local_port_probe_reports_socket_creation_error(monkeypatch):
    def denied_socket(*_args):
        raise PermissionError('socket creation denied')

    monkeypatch.setattr(demo_runner.socket, 'socket', denied_socket)
    assert demo_runner._check_local_tcp_ports((('gazebo', 11361),)) == [
        {'name': 'gazebo', 'port': 11361, 'bindable': False,
         'error': 'PermissionError: socket creation denied'}
    ]


def test_gazebo_process_preflight_distinguishes_empty_list_from_ps_error():
    assert gazebo_processes_from_ps('codex-linux-san\nps\n', 0) == []
    assert gazebo_processes_from_ps('gzserver\ngzclient\n', 0) == ['gzserver', 'gzclient']
    with pytest.raises(ResourceBlocked, match='无法核对Gazebo进程'):
        gazebo_processes_from_ps('', 2)


def test_ros_build_script_can_write_colcon_logs_to_tmp():
    build = (ROOT / 'scripts/build_ros2.sh').read_text()
    assert 'COLCON_LOG_BASE' in build
    assert 'COLCON_INSTALL_BASE' in build
    assert 'colcon --log-base "$log_base" build' in build



def test_business_script_regroups_a_lost_team_during_generic_safety_pause():
    tour = {'state': 'PAUSED', 'reason': '导航安全停车'}
    team = {'valid': True, 'state': 'LOST', 'time_monotonic_sec': 10.5}

    assert demo_runner.should_handle_paused_team(
        'business_script', tour, team, now_monotonic=10.8)
    assert not demo_runner.should_handle_paused_team(
        'business_script', tour,
        {'valid': True, 'state': 'LOST', 'time_monotonic_sec': 8.0},
        now_monotonic=10.8)
    assert not demo_runner.should_handle_paused_team(
        'business_script', tour,
        {'valid': True, 'state': 'FOLLOWING', 'time_monotonic_sec': 10.8},
        now_monotonic=10.8)


def test_business_script_handles_gathered_team_with_pending_recovery_latch():
    tour = {'state': 'PAUSED', 'reason': '导航安全停车',
            'team_recovery_required': True}
    team = {'valid': True, 'state': 'GATHERED', 'gathered': True,
            'time_monotonic_sec': 10.8}

    assert demo_runner.should_handle_paused_team(
        'business_script', tour, team, now_monotonic=10.8)
    stale = dict(team, time_monotonic_sec=8.0)
    assert not demo_runner.should_handle_paused_team(
        'business_script', tour, stale, now_monotonic=10.8)
    assert not demo_runner.should_handle_paused_team(
        'business_script', dict(tour, team_recovery_required=False),
        team, now_monotonic=10.8)


def test_vision_runner_handles_generic_pause_from_unconfirmed_observation():
    tour = {'state': 'PAUSED', 'reason': '导航安全停车', 'pause_source': 'safety'}
    observation = {
        'valid': True, 'observation_state': 'UNKNOWN', 'observed_count': 1,
        'expected_count': 3, 'requires_manual_confirmation': True,
    }

    assert demo_runner.should_handle_paused_team(
        'vision_conservative', tour, observation)


def test_vision_runner_does_not_flag_confirmed_observation_as_team_pause():
    tour = {'state': 'PAUSED', 'reason': '导航安全停车', 'pause_source': 'safety'}
    observation = {
        'valid': True, 'observation_state': 'OBSERVED', 'observed_count': 3,
        'expected_count': 3, 'requires_manual_confirmation': False,
    }

    assert not demo_runner.should_handle_paused_team(
        'vision_conservative', tour, observation)


def test_terminal_stop_uses_fresh_odom_while_motion_evidence_uses_cmd_vel_and_odom(tmp_path):
    stopped = {'tour': {'is_moving': False}, 'evidence': {
        'cmd_vel': {'fresh': False, 'age_sec': 3.6, 'value': None},
        'odom': {'fresh': True, 'value': {'linear_speed_mps': 0.003}}}}
    assert pause_stop_evidence(stopped)['confirmed'] is True

    rows = []
    for target in ('zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5', 'exit'):
        for _ in range(3):
            rows.append({'tour': {'state': 'RETURNING' if target == 'exit' else 'NAVIGATING',
                                  'target': target},
                         'evidence': {
                             'cmd_vel': {'fresh': True, 'value': {'linear_speed_mps': 0.3}},
                             'odom': {'fresh': True, 'value': {'linear_speed_mps': 0.29}}}})
    path = tmp_path / 'motion.jsonl'
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))

    summary = summarize_navigation_motion(path)
    assert summary['complete'] is True
    assert summary['missing_targets'] == []
    assert summary['targets']['zone_3']['paired_odom_motion_samples'] == 3


def test_motion_evidence_rejects_stale_or_unpaired_velocity_samples(tmp_path):
    path = tmp_path / 'motion.jsonl'
    rows = [{'tour': {'state': 'NAVIGATING', 'target': 'zone_1'}, 'evidence': {
        'cmd_vel': {'fresh': True, 'value': {'linear_speed_mps': 0.3}},
        'odom': {'fresh': False, 'value': {'linear_speed_mps': 0.3}}}}
        for _ in range(5)]
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))

    summary = summarize_navigation_motion(path)
    assert summary['complete'] is False
    assert summary['missing_targets'] == ['zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5', 'exit']
    assert summary['targets']['zone_1']['cmd_vel_motion_samples'] == 5
    assert summary['targets']['zone_1']['paired_odom_motion_samples'] == 0


def test_business_script_completion_requires_the_whole_team_gathered():
    gathered = {'valid': True, 'count': 3, 'state': 'GATHERED', 'gathered': True}
    lost = {'valid': True, 'count': 3, 'state': 'LOST', 'gathered': False}

    assert demo_runner.business_team_complete(gathered, 3)
    assert not demo_runner.business_team_complete(lost, 3)
