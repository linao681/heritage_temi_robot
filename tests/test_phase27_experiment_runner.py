import math
import json
import sys
import yaml
from pathlib import Path

import pytest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from run_phase27_experiment import (
    allocate_run_directory, check_port_available, ensure_empty_domain,
    execute_experiment, manifest_payload, stop_owned_process_group,
    validate_experiment,
)


def experiment(**overrides):
    value = {
        'id': 'E03-S01', 'scenario': 'approaching', 'layout': 'official',
        'route': ['wait', 'zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5', 'exit'],
        'robot_speed_mps': 0.3,
        'actor_motion': {
            'continue_after_robot_stop': True, 'stop_at_target': True,
            'movement_speed_mps': 0.1, 'target_distance_m': 1.4,
            'hold_at_target_sec': 2.0, 'leave_after_hold': True,
            'leave_distance_m': 3.1,
        },
        'timeouts': {'preflight_sec': 240, 'tour_sec': 900, 'visitor_sec': 60},
        'seed': 31,
    }
    value.update(overrides)
    return value


def test_phase27_experiment_config_accepts_supported_complete_run():
    validated = validate_experiment(experiment())

    assert validated['id'] == 'E03-S01'
    assert validated['actor_motion']['target_distance_m'] == 1.4


def test_phase27_config_accepts_lateral_actor_departure_and_rejects_unknown_direction():
    validated = validate_experiment(experiment(actor_motion={
        'continue_after_robot_stop': True, 'leave_after_hold': True,
        'movement_speed_mps': 0.1, 'leave_direction': 'left',
    }))

    assert validated['actor_motion']['leave_direction'] == 'left'
    with pytest.raises(ValueError, match='leave_direction'):
        validate_experiment(experiment(actor_motion={
            'continue_after_robot_stop': True, 'leave_after_hold': True,
            'movement_speed_mps': 0.1, 'leave_direction': 'diagonal',
        }))


@pytest.mark.parametrize(('scenario', 'height', 'pitch'), [
    ('camera_a', 0.55, 0.0), ('camera_b', 0.55, 10.0),
    ('camera_c', 0.70, 0.0), ('camera_d', 0.55, 0.0),
])
def test_camera_experiment_requires_its_declared_geometry(scenario, height, pitch):
    validated = validate_experiment(experiment(
        scenario=scenario, camera_height_m=height, camera_pitch_down_deg=pitch))

    assert validated['camera_height_m'] == height
    assert validated['camera_pitch_down_deg'] == pitch


def test_camera_experiment_rejects_geometry_mismatch():
    with pytest.raises(ValueError, match='camera_b must use'):
        validate_experiment(experiment(
            scenario='camera_b', camera_height_m=0.55, camera_pitch_down_deg=0.0))


@pytest.mark.parametrize('change', [
    {'robot_speed_mps': float('nan')},
    {'robot_speed_mps': -0.1},
    {'scenario': 'unknown'},
    {'layout': 'missing'},
    {'route': ['exit', 'zone_1']},
    {'seed': -1},
    {'timeouts': {'tour_sec': 0}},
    {'actor_motion': {'movement_speed_mps': float('nan')}},
])
def test_phase27_config_rejects_invalid_values(change):
    with pytest.raises(ValueError):
        validate_experiment(experiment(**change))


def test_run_directory_never_overwrites_an_existing_run(tmp_path):
    existing = tmp_path / 'E03-S01' / 'run-001'
    existing.mkdir(parents=True)

    with pytest.raises(FileExistsError):
        allocate_run_directory(tmp_path, 'E03-S01', 'run-001')


def test_port_preflight_rejects_a_bound_local_port(monkeypatch):
    import run_phase27_experiment as runner

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def bind(self, address):
            assert address == ('127.0.0.1', 8123)
            raise OSError('address already in use')

    monkeypatch.setattr(runner.socket, 'socket', lambda *_args, **_kwargs: FakeSocket())
    with pytest.raises(OSError, match='already in use'):
        check_port_available(8123)


def test_domain_preflight_rejects_nonempty_domain_without_cleanup():
    with pytest.raises(RuntimeError, match='not empty'):
        ensure_empty_domain(227, lambda _domain: [('user_node', '/')])


def test_manifest_has_real_hash_and_execution_context_fields():
    payload = manifest_payload(
        experiment(), domain_id=227, gazebo_port=11361, web_port=8089,
        base_sha='057761908e386f3d0ba7a779d61b860a15debbda',
        dirty_paths=['scripts/run_phase27_experiment.py'],
        python_version='3.10.12', dependency_versions={'pytest': '6.2.5'},
        model_sha256='abc123', source_import_paths={'phase27_scenario': 'scripts/phase27_scenario.py'},
        started_utc='2026-11-22T00:00:00+00:00',
    )

    assert payload['domain_id'] == 227
    assert payload['dirty_paths'] == ['scripts/run_phase27_experiment.py']
    assert len(payload['config_sha256']) == 64
    assert payload['model_sha256'] == 'abc123'
    assert payload['data_sources'] == ['Gazebo model states', 'ROS2 topics', 'Nav2 odometry']


def test_readiness_poll_retries_a_slow_ros_preflight(monkeypatch, tmp_path):
    import run_phase27_experiment as runner

    responses = iter([
        runner.subprocess.TimeoutExpired(cmd='phase25_preflight', timeout=4.0),
        runner.subprocess.CompletedProcess(
            args=['phase25_preflight'], returncode=0, stdout='{"ready": true}', stderr=''),
    ])

    def run_probe(*_args, **_kwargs):
        result = next(responses)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(runner.subprocess, 'run', run_probe)
    monkeypatch.setattr(runner.time, 'sleep', lambda _seconds: None)
    process = SimpleNamespace(poll=lambda: None)

    result = runner._wait_for_system_ready(
        process, tmp_path / 'system.log', tmp_path, {}, timeout_sec=2.0)

    assert result == {'ready': True}


def test_initial_visitor_records_a_real_static_gazebo_model(tmp_path, monkeypatch):
    import run_phase27_experiment as runner

    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    called = {}

    def spawn(command, **kwargs):
        called['command'] = command
        called['kwargs'] = kwargs
        truth_path = Path(command[command.index('--truth-output') + 1])
        truth_path.parent.mkdir(parents=True, exist_ok=True)
        truth_path.write_text(json.dumps({
            'status': 'PASS', 'commanded_model_poses_world': [{'name': 'phase25_person_01'}],
        }))
        return runner.subprocess.CompletedProcess(command, 0, 'spawned\n', '')

    monkeypatch.setattr(runner.subprocess, 'run', spawn)
    evidence = runner.prepare_arrival_visitor(experiment(), run_dir, root=tmp_path, env={})

    command = called['command']
    assert command[command.index('--scenario') + 1] == 'single_static'
    assert command[command.index('--seed') + 1] == '31'
    assert called['kwargs']['timeout'] > 0
    assert evidence['status'] == 'PASS'
    assert evidence['model_names'] == ['phase25_person_01']
    assert (run_dir / evidence['truth_file']).is_file()


def test_initial_visitor_does_not_pass_without_gazebo_truth(tmp_path, monkeypatch):
    import run_phase27_experiment as runner

    run_dir = tmp_path / 'run'
    run_dir.mkdir()

    def spawn(command, **_kwargs):
        truth_path = Path(command[command.index('--truth-output') + 1])
        truth_path.parent.mkdir(parents=True, exist_ok=True)
        truth_path.write_text(json.dumps({'status': 'FAIL', 'commanded_model_poses_world': []}))
        return runner.subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(runner.subprocess, 'run', spawn)
    with pytest.raises(RuntimeError, match='Gazebo truth'):
        runner.prepare_arrival_visitor(experiment(), run_dir, root=tmp_path, env={})


def test_yaml_float_nan_is_rejected_after_safe_load(tmp_path):
    path = tmp_path / 'experiment.yaml'
    path.write_text(yaml.safe_dump(experiment(robot_speed_mps=math.nan)))

    value = yaml.safe_load(path.read_text())
    with pytest.raises(ValueError):
        validate_experiment(value)


def test_preflight_failure_keeps_a_failed_run_record(tmp_path, monkeypatch):
    import run_phase27_experiment as runner

    monkeypatch.setattr(runner, 'git_context', lambda _root: ('base-sha', [], ''))
    monkeypatch.setattr(runner, '_dependency_versions', lambda _python: {'pytest': '6.2.5'})
    monkeypatch.setattr(runner, 'source_paths', lambda _root: {'phase27_scenario': 'scripts/phase27_scenario.py'})
    run_dir = tmp_path / 'docs/phase2_7/experiments/E03-S01/run-001'

    with pytest.raises(ValueError, match='reserved'):
        execute_experiment(
            experiment(), domain_id=225, gazebo_port=11361, web_port=8089,
            output_dir=run_dir, root=tmp_path)

    manifest = yaml.safe_load((run_dir / 'manifest.json').read_text())
    assert manifest['status'] == 'FAIL'
    assert 'reserved' in manifest['error']
    assert (run_dir / 'config.yaml').is_file()


def test_shutdown_targets_only_owned_process_group(monkeypatch):
    signals = []
    monkeypatch.setattr('run_phase27_experiment.os.killpg',
                        lambda group, sig: signals.append((group, sig)))

    class OwnedProcess:
        pid = 4321
        def poll(self):
            return None
        def wait(self, timeout=None):
            return 0

    stop_owned_process_group(OwnedProcess())

    import signal
    assert signals == [(4321, signal.SIGINT)]
