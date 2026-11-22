#!/usr/bin/env python3
"""Validate and execute one isolated phase 2.7 Gazebo experiment."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / 'assets/vision/object_detection_yolox_2022nov.onnx'
KNOWN_USER_DOMAINS = {211, 219, 225}
VALID_LAYOUTS = {'official', 'adaptive'}
VALID_STATIONS = ['wait', 'zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5', 'exit']
VALID_SCENARIOS = {
    'tour', 'none', 'approaching', 'crossing', 'leaving', 'group_straggler',
    'crowded', 'crowd_sequence', 'qa', 'camera_a', 'camera_b', 'camera_c', 'camera_d',
}
CAMERA_VARIANTS = {
    'camera_a': (0.55, 0.0),
    'camera_b': (0.55, 10.0),
    'camera_c': (0.70, 0.0),
    'camera_d': (0.55, 0.0),
}


def _finite(value, name, *, minimum=None, maximum=None, allow_equal_minimum=True):
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{name} must be a finite number') from error
    if not math.isfinite(number):
        raise ValueError(f'{name} must be a finite number')
    if minimum is not None and (number < minimum or
                                (number == minimum and not allow_equal_minimum)):
        raise ValueError(f'{name} must be >= {minimum}')
    if maximum is not None and number > maximum:
        raise ValueError(f'{name} must be <= {maximum}')
    return number


def validate_experiment(experiment):
    """Validate the values that affect a run; reject non-finite values early."""
    if not isinstance(experiment, dict):
        raise ValueError('experiment must be a mapping')
    experiment = dict(experiment)
    identifier = experiment.get('id')
    if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', identifier):
        raise ValueError('id must be a safe 1-64 character identifier')
    scenario = experiment.get('scenario')
    if scenario not in VALID_SCENARIOS:
        raise ValueError(f'unsupported scenario: {scenario}')
    if experiment.get('layout') not in VALID_LAYOUTS:
        raise ValueError(f'unsupported layout: {experiment.get("layout")}')
    route = experiment.get('route')
    if (not isinstance(route, list) or not route or
            any(station not in VALID_STATIONS for station in route)):
        raise ValueError('route must contain supported stations')
    indices = [VALID_STATIONS.index(station) for station in route]
    if indices != sorted(indices) or len(indices) != len(set(indices)):
        raise ValueError('route stations must be unique and in forward order')
    experiment['robot_speed_mps'] = _finite(
        experiment.get('robot_speed_mps'), 'robot_speed_mps', minimum=0.0,
        maximum=1.2, allow_equal_minimum=False)
    experiment['camera_height_m'] = _finite(
        experiment.get('camera_height_m', 0.55), 'camera_height_m',
        minimum=0.3, maximum=1.2)
    experiment['camera_pitch_down_deg'] = _finite(
        experiment.get('camera_pitch_down_deg', 0.0), 'camera_pitch_down_deg',
        minimum=0.0, maximum=30.0)
    timeouts = experiment.get('timeouts')
    if not isinstance(timeouts, dict) or not timeouts:
        raise ValueError('timeouts must be a non-empty mapping')
    for name, value in timeouts.items():
        timeouts[name] = _finite(value, f'timeouts.{name}', minimum=0.0,
                                  allow_equal_minimum=False)
    actor = experiment.get('actor_motion', {})
    if actor is None:
        actor = {}
    if not isinstance(actor, dict):
        raise ValueError('actor_motion must be a mapping')
    actor = dict(actor)
    if scenario in ({'approaching', 'crossing', 'leaving', 'group_straggler', 'crowded'} |
                    set(CAMERA_VARIANTS)):
        actor['movement_speed_mps'] = _finite(
            actor.get('movement_speed_mps', 0.25), 'actor_motion.movement_speed_mps',
            minimum=0.0, allow_equal_minimum=False)
    if 'target_distance_m' in actor:
        actor['target_distance_m'] = _finite(
            actor['target_distance_m'], 'actor_motion.target_distance_m', minimum=0.0)
    for key in ('hold_at_target_sec', 'leave_distance_m', 'hold_clear_sec'):
        if key in actor:
            actor[key] = _finite(actor[key], f'actor_motion.{key}', minimum=0.0)
    if actor.get('leave_direction', 'forward') not in ('forward', 'left', 'right'):
        raise ValueError('actor_motion.leave_direction must be forward, left, or right')
    if bool(actor.get('leave_after_hold')) and not bool(actor.get('continue_after_robot_stop')):
        raise ValueError('leave_after_hold requires continue_after_robot_stop')
    experiment['actor_motion'] = actor
    if scenario in CAMERA_VARIANTS:
        expected_height, expected_pitch = CAMERA_VARIANTS[scenario]
        if (not math.isclose(experiment['camera_height_m'], expected_height, abs_tol=1e-9) or
                not math.isclose(experiment['camera_pitch_down_deg'], expected_pitch,
                                 abs_tol=1e-9)):
            raise ValueError(f'{scenario} must use camera height {expected_height} m and '
                             f'downward pitch {expected_pitch} degrees')
    seed = experiment.get('seed')
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError('seed must be a non-negative integer')
    return experiment


def load_experiment(config_path, experiment_id):
    document = yaml.safe_load(Path(config_path).read_text(encoding='utf-8'))
    if not isinstance(document, dict):
        raise ValueError('configuration root must be a mapping')
    defaults = document.get('defaults', {})
    entries = document.get('experiments')
    if not isinstance(defaults, dict) or not isinstance(entries, list):
        raise ValueError('configuration requires defaults and an experiments list')
    selected = [item for item in entries if isinstance(item, dict) and
                item.get('id') == experiment_id]
    if len(selected) != 1:
        raise ValueError(f'expected exactly one experiment id {experiment_id!r}')
    merged = dict(defaults)
    merged.update(selected[0])
    merged.setdefault('layout', document.get('layout', 'official'))
    return validate_experiment(merged)


def allocate_run_directory(root, experiment_id, run_id):
    root = Path(root)
    path = root / experiment_id / run_id
    path.mkdir(parents=True, exist_ok=False)
    return path


def check_port_available(port):
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ValueError('port must be an integer in 1024..65535')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', port))


def ensure_empty_domain(domain_id, probe):
    if isinstance(domain_id, bool) or not isinstance(domain_id, int) or not 0 <= domain_id <= 232:
        raise ValueError('domain id must be an integer in 0..232')
    if domain_id in KNOWN_USER_DOMAINS:
        raise ValueError(f'ROS domain {domain_id} is reserved for existing user systems')
    peers = probe(domain_id)
    if peers:
        raise RuntimeError(f'ROS domain {domain_id} is not empty: {peers}')
    return peers


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def manifest_payload(experiment, *, domain_id, gazebo_port, web_port, base_sha,
                     dirty_paths, python_version, dependency_versions,
                     model_sha256, source_import_paths, started_utc=None,
                     patch_summary=None):
    config_bytes = json.dumps(experiment, sort_keys=True, ensure_ascii=False,
                             allow_nan=False).encode('utf-8')
    return {
        'experiment_id': experiment['id'],
        'camera_configuration': {
            'height_m': experiment.get('camera_height_m', 0.55),
            'pitch_down_deg': experiment.get('camera_pitch_down_deg', 0.0),
            'sensor_policy': 'existing RGB-D and laser near-field protection',
        },
        'baseline_sha': base_sha,
        'dirty_paths': sorted(dirty_paths),
        'patch_summary': patch_summary,
        'config_sha256': hashlib.sha256(config_bytes).hexdigest(),
        'model_sha256': model_sha256,
        'python_version': python_version,
        'dependency_versions': dependency_versions,
        'domain_id': domain_id,
        'ports': {'gazebo': gazebo_port, 'web': web_port},
        'started_utc': started_utc or datetime.now(timezone.utc).isoformat(),
        'source_import_paths': source_import_paths,
        'data_sources': ['Gazebo model states', 'ROS2 topics', 'Nav2 odometry'],
        'preplanned_assertions': [
            'actual actor and robot odometry are recorded',
            'predicted geometric overlap aborts before the next actor move',
            'only fresh same-session safety evidence can qualify recovery',
        ],
        'resource_limits': experiment.get('resource_limits', {}),
    }


def resource_snapshot(path):
    available_memory_kib = None
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemAvailable:'):
                available_memory_kib = int(line.split()[1])
                break
    except OSError:
        pass
    disk = shutil.disk_usage(path)
    return {'mem_available_kib': available_memory_kib,
            'disk_free_bytes': disk.free}


def git_context(root):
    def git(*arguments):
        return subprocess.run(['git', '-C', str(root), *arguments], check=True,
                              capture_output=True, text=True).stdout.strip()
    head = git('rev-parse', 'HEAD')
    dirty = git('status', '--porcelain', '--untracked-files=all')
    paths = [line[3:] for line in dirty.splitlines() if len(line) > 3]
    summary = git('diff', '--stat')
    return head, paths, summary


def source_paths(root):
    sys.path.insert(0, str(root / 'scripts'))
    result = {}
    for name in ('phase27_scenario', 'spawn_people_scenario', 'run_phase25_clean_tour'):
        spec = importlib.util.find_spec(name)
        result[name] = str(Path(spec.origin).resolve()) if spec and spec.origin else None
    return result


def _domain_probe(domain_id, root, base_env):
    env = dict(base_env, ROS_LOCALHOST_ONLY='1', ROS_DOMAIN_ID=str(domain_id))
    completed = subprocess.run(
        [sys.executable, str(root / 'scripts/phase25_preflight.py'), '--check-domain-empty'],
        cwd=root, env=env, capture_output=True, text=True, timeout=5.0)
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout.strip() or completed.stderr.strip() or
                           f'failed to verify ROS domain {domain_id}')
    payload = json.loads(completed.stdout)
    return payload.get('other_nodes', [])


@contextmanager
def domain_lock(domain_id, lock_dir=Path('/tmp')):
    path = Path(lock_dir) / f'heritage-phase27-{domain_id}.lock'
    handle = path.open('a+', encoding='utf-8')
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        handle.close()
        raise RuntimeError(f'phase 2.7 domain {domain_id} is already locked') from error
    try:
        yield handle
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def stop_owned_process_group(process, timeout_sec=8.0):
    """Stop only a child started with start_new_session=True by this runner."""
    if process is None or process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGINT)
    try:
        process.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3.0)


def _dependency_versions(python):
    completed = subprocess.run(
        [str(python), '-c',
         'import importlib.metadata as m; print("\\n".join(f"{n}=={m.version(n)}" '
         'for n in ("pytest", "websockets", "PyYAML", "numpy") if '
         'next((d for d in m.distributions() if d.metadata["Name"].lower()==n.lower()), None)))'],
        capture_output=True, text=True, check=True)
    return dict(line.split('==', 1) for line in completed.stdout.splitlines() if '==' in line)


def _wait_for_system_ready(process, log_path, root, env, timeout_sec):
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'system exited early ({process.returncode}); see {log_path}')
        try:
            probe = subprocess.run(
                [sys.executable, str(root / 'scripts/phase25_preflight.py'), '--timeout-sec', '2'],
                cwd=root, env=env, capture_output=True, text=True, timeout=4.0)
        except subprocess.TimeoutExpired:
            time.sleep(0.5)
            continue
        if probe.returncode == 0:
            return json.loads(probe.stdout)
        time.sleep(0.5)
    raise TimeoutError(f'system readiness timed out after {timeout_sec}s; see {log_path}')


def prepare_arrival_visitor(experiment, run_dir, *, root=ROOT, env=None):
    """Spawn and record the real Gazebo visitor needed to start a clean tour."""
    run_dir = Path(run_dir)
    visitor_dir = run_dir / 'arrival_visitor'
    visitor_dir.mkdir(parents=True, exist_ok=True)
    truth_path = visitor_dir / 'truth.json'
    log_path = visitor_dir / 'spawn.log'
    command = [
        sys.executable, str(Path(root) / 'scripts/spawn_people_scenario.py'),
        '--scenario', 'single_static', '--layout', experiment['layout'],
        '--seed', str(experiment['seed']), '--truth-output', str(truth_path),
    ]
    try:
        completed = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                   text=True, timeout=30.0)
        log_path.write_text(completed.stdout + completed.stderr, encoding='utf-8')
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ''
        stderr = error.stderr or ''
        if isinstance(stdout, bytes):
            stdout = stdout.decode('utf-8', errors='replace')
        if isinstance(stderr, bytes):
            stderr = stderr.decode('utf-8', errors='replace')
        log_path.write_text(str(stdout) + str(stderr), encoding='utf-8')
        raise RuntimeError(f'arrival visitor spawn timed out; see {log_path}') from error
    if completed.returncode != 0:
        raise RuntimeError(f'arrival visitor spawn failed ({completed.returncode}); see {log_path}')
    try:
        truth = json.loads(truth_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f'arrival visitor Gazebo truth is missing or invalid: {error}') from error
    models = truth.get('commanded_model_poses_world')
    if truth.get('status') != 'PASS' or not isinstance(models, list) or not models:
        raise RuntimeError('arrival visitor Gazebo truth did not confirm a spawned model')
    names = [model.get('name') for model in models
             if isinstance(model, dict) and isinstance(model.get('name'), str)]
    if not names:
        raise RuntimeError('arrival visitor Gazebo truth did not name the spawned model')
    return {
        'status': 'PASS', 'scenario': 'single_static', 'seed': experiment['seed'],
        'model_names': names, 'truth_file': str(truth_path.relative_to(run_dir)),
        'spawn_log': str(log_path.relative_to(run_dir)),
    }


def execute_experiment(experiment, *, domain_id, gazebo_port, web_port,
                       output_dir=None, root=ROOT):
    experiment = validate_experiment(experiment)
    output_root = root / 'docs/phase2_7/experiments'
    if output_dir is not None:
        output_dir = Path(output_dir).resolve()
        if output_root.resolve() not in output_dir.parents:
            raise ValueError('output directory must be inside docs/phase2_7/experiments')
        if output_dir.exists():
            raise FileExistsError(str(output_dir))
        run_dir = output_dir
        run_dir.mkdir(parents=True, exist_ok=False)
    else:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        parent = output_root / experiment['id']
        run_dir = None
        for index in range(1, 1000):
            name = f'{stamp}-{experiment["id"]}-r{index:03d}'
            try:
                run_dir = allocate_run_directory(output_root, experiment['id'], name)
                break
            except FileExistsError:
                continue
        if run_dir is None:
            raise RuntimeError(f'could not allocate unique run directory under {parent}')

    logs = run_dir / 'logs'
    logs.mkdir()
    started_utc = datetime.now(timezone.utc).isoformat()
    env = dict(os.environ)
    env.update(ROS_LOCALHOST_ONLY='1', ROS_DOMAIN_ID=str(domain_id),
               GAZEBO_MASTER_URI=f'http://127.0.0.1:{gazebo_port}',
               PHASE25_LOG_DIR=str(logs / 'system'),
               PHASE25_PREFLIGHT_TIMEOUT_SEC=str(
                   experiment['timeouts'].get('preflight_sec', 240)))
    experiment_path = run_dir / 'config.yaml'
    experiment_path.write_text(yaml.safe_dump(experiment, allow_unicode=True, sort_keys=False),
                               encoding='utf-8')
    base_sha, dirty_paths, patch_summary = git_context(root)
    python = root / '.venv/bin/python'
    manifest = manifest_payload(
        experiment, domain_id=domain_id, gazebo_port=gazebo_port, web_port=web_port,
        base_sha=base_sha, dirty_paths=dirty_paths, patch_summary=patch_summary,
        python_version=sys.version, dependency_versions=_dependency_versions(python),
        model_sha256=sha256_file(MODEL_PATH) if MODEL_PATH.is_file() else None,
        source_import_paths=source_paths(root), started_utc=started_utc)
    manifest.update({'status': 'RUNNING', 'config_file': 'config.yaml',
                     'resources_before': resource_snapshot(run_dir),
                     'owned_process_groups': []})
    (run_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n',
                                           encoding='utf-8')
    system_process = None
    tour_process = None
    status = 'FAIL'
    try:
        with domain_lock(domain_id):
            ensure_empty_domain(
                domain_id, lambda value: _domain_probe(value, root, os.environ))
            check_port_available(gazebo_port)
            check_port_available(web_port)
            if gazebo_port == web_port:
                raise ValueError('Gazebo and web ports must differ')
            manifest['preflight'] = {
                'domain_empty': True, 'ports_bindable': [gazebo_port, web_port],
                'localhost_only': True,
            }
            system_log_path = logs / 'system_start.log'
            with system_log_path.open('w', encoding='utf-8') as system_log:
                system_process = subprocess.Popen(
                    ['bash', str(root / 'scripts/start_phase25_system.sh'),
                     str(domain_id), str(gazebo_port), str(web_port),
                     str(experiment['robot_speed_mps']),
                     str(experiment['camera_height_m']),
                     str(experiment['camera_pitch_down_deg'])],
                    cwd=root, env=env, stdout=system_log, stderr=subprocess.STDOUT,
                    start_new_session=True)
                manifest['owned_process_groups'].append({
                    'pid': system_process.pid, 'pgid': system_process.pid,
                    'purpose': 'phase25_system_startup',
                })
                (run_dir / 'manifest.json').write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
                readiness = _wait_for_system_ready(
                    system_process, system_log_path, root, env,
                    experiment['timeouts'].get('preflight_sec', 240))
                (run_dir / 'preflight.json').write_text(
                    json.dumps(readiness, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

            manifest['arrival_visitor'] = prepare_arrival_visitor(
                experiment, run_dir, root=root, env=env)
            (run_dir / 'manifest.json').write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

            tour_output = run_dir / 'tour'
            command = [str(python), str(root / 'scripts/run_phase25_clean_tour.py'),
                       '--experiment-id', experiment['id'], '--timeout-sec',
                       str(experiment['timeouts'].get('tour_sec', 1200)),
                       '--visitor-timeout-sec', str(experiment['timeouts'].get('visitor_sec', 90)),
                       '--output-dir', str(tour_output)]
            scenario = experiment['scenario']
            if (scenario not in {'tour', 'none', 'qa', 'approaching', 'crossing', 'leaving'} and
                    scenario not in CAMERA_VARIANTS):
                raise ValueError(f'scenario is not supported by the phase 2.7 tour executor: {scenario}')
            if scenario in {'approaching', 'crossing', 'leaving'} | set(CAMERA_VARIANTS):
                command.extend(['--dynamic-scenario',
                                'approaching' if scenario in CAMERA_VARIANTS else scenario,
                                '--scenario-target', experiment.get('scenario_target', 'zone_1')])
                actor = experiment['actor_motion']
                command.extend(['--person-speed-mps', str(actor['movement_speed_mps'])])
                if actor.get('target_distance_m') is not None:
                    command.extend(['--scenario-end-distance-m', str(actor['target_distance_m'])])
                if actor.get('continue_after_robot_stop'):
                    command.append('--continue-after-robot-stop')
                    command.append('--retain-scenario-model')
                    command.extend(['--hold-at-target-sec',
                                    str(actor.get('hold_at_target_sec', 2.0)),
                                    '--leave-distance-m', str(actor.get('leave_distance_m', 3.9)),
                                    '--leave-direction', str(actor.get('leave_direction', 'forward')),
                                    '--hold-clear-sec', str(actor.get('hold_clear_sec', 1.0))])
                    if actor.get('leave_after_hold'):
                        command.append('--leave-after-hold')
            if scenario == 'qa':
                command.extend(['--question', experiment.get('question', '潮州音乐有哪些类型？'),
                                '--exhibit', experiment.get('exhibit', 'exhibit_05')])
            with (logs / 'tour.log').open('w', encoding='utf-8') as tour_log:
                tour_process = subprocess.Popen(
                    command, cwd=root, env=env, stdout=tour_log, stderr=subprocess.STDOUT,
                    start_new_session=True)
                manifest['owned_process_groups'].append({
                    'pid': tour_process.pid, 'pgid': tour_process.pid,
                    'purpose': 'phase25_clean_tour',
                })
                (run_dir / 'manifest.json').write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
                try:
                    tour_code = tour_process.wait(
                        timeout=experiment['timeouts'].get('tour_sec', 1200) + 120)
                except subprocess.TimeoutExpired:
                    stop_owned_process_group(tour_process)
                    raise TimeoutError('tour experiment exceeded its total timeout')
            if tour_code != 0:
                raise RuntimeError(f'tour exited with code {tour_code}; see logs/tour.log')
            report_path = tour_output / 'report.json'
            if not report_path.is_file():
                raise RuntimeError('tour completed without report.json')
            tour_report = json.loads(report_path.read_text(encoding='utf-8'))
            if tour_report.get('status') not in {'PASS', 'PASS_WITH_RISK'}:
                raise RuntimeError(f'tour result status {tour_report.get("status")}')
            status = tour_report['status']
            manifest['tour_report'] = str(report_path.relative_to(run_dir))
    except BaseException as error:
        manifest['error'] = f'{type(error).__name__}: {error}'
        if isinstance(error, KeyboardInterrupt):
            manifest['interrupted'] = True
        raise
    finally:
        stop_owned_process_group(tour_process)
        stop_owned_process_group(system_process)
        manifest.update({'status': status, 'ended_utc': datetime.now(timezone.utc).isoformat(),
                         'resources_after': resource_snapshot(run_dir)})
        (run_dir / 'manifest.json').write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        (run_dir / 'status.json').write_text(
            json.dumps({'status': status, 'experiment_id': experiment['id'],
                        'manifest': 'manifest.json'}, indent=2) + '\n', encoding='utf-8')
    return run_dir, status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/phase27_experiments.yaml')
    parser.add_argument('--experiment', required=True)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--domain-id', type=int)
    parser.add_argument('--gazebo-port', type=int, default=11361)
    parser.add_argument('--web-port', type=int, default=8089)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args(argv)
    try:
        experiment = load_experiment(args.config, args.experiment)
        if args.validate_only:
            print(json.dumps({'valid': True, 'experiment': experiment},
                             ensure_ascii=False, allow_nan=False))
            return 0
        if args.domain_id is None:
            raise ValueError('--domain-id is required unless --validate-only is used')
        run_dir, status = execute_experiment(
            experiment, domain_id=args.domain_id, gazebo_port=args.gazebo_port,
            web_port=args.web_port, output_dir=args.output_dir)
        print(json.dumps({'status': status, 'run_directory': str(run_dir)}, ensure_ascii=False))
        return 0 if status in {'PASS', 'PASS_WITH_RISK'} else 1
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'error': f'{type(error).__name__}: {error}'}),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
