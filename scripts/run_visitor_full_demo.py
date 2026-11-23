"""Run a scripted visitor/operator demonstration over real Gazebo ROS services."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MIN_AVAILABLE_GIB = 6.0
MIN_DISK_GIB = 5.0


def should_handle_paused_team(team_decision_mode, tour, team, *, now_monotonic=None):
    if not isinstance(tour, dict) or tour.get('state') != 'PAUSED':
        return False
    reason = tour.get('reason') or ''
    if team_decision_mode == 'vision_conservative':
        return (tour.get('pause_source') in ('team', 'safety') and
                tour.get('team_recovery_required') is True and
                isinstance(team, dict) and
                team.get('requires_manual_confirmation') is True)
    if team_decision_mode != 'business_script' or not isinstance(team, dict):
        return False
    stamp = team.get('time_monotonic_sec')
    now = time.monotonic() if now_monotonic is None else now_monotonic
    fresh_team = (team.get('valid') is True and type(stamp) in (int, float) and
                  0 <= now-stamp <= 1.0)
    pending_recovery = tour.get('team_recovery_required') is True
    return (fresh_team and (pending_recovery or team.get('state') == 'LOST' or
                            '掉队' in reason))


def should_inject_scripted_straggle(team_decision_mode):
    return team_decision_mode == 'business_script'


def scripted_operator_confirmation_allowed(operator_mode, team_decision_mode, tour,
                                           team_observation, stop_evidence):
    return (operator_mode == 'scripted_test' and
            team_decision_mode == 'vision_conservative' and
            isinstance(tour, dict) and tour.get('team_resume_confirmed') is not True and
            isinstance(tour.get('paused_session_id'), str) and
            bool(tour.get('paused_session_id')) and
            isinstance(tour.get('team_pause_event_id'), str) and
            bool(tour.get('team_pause_event_id')) and
            should_handle_paused_team(team_decision_mode, tour, team_observation) and
            isinstance(stop_evidence, dict) and stop_evidence.get('confirmed') is True)


def business_team_complete(team, expected_visitors):
    return (isinstance(team, dict) and team.get('valid') is True and
            team.get('count') == expected_visitors and team.get('gathered') is True)


def positive_seconds(value):
    try:
        seconds = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError('必须是正整数秒数') from error
    if seconds <= 0:
        raise argparse.ArgumentTypeError('必须是正整数秒数')
    return seconds


def visitor_count(value):
    try:
        count = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError('游客人数必须是1–8之间的整数') from error
    if not 1 <= count <= 8:
        raise argparse.ArgumentTypeError('游客人数必须是1–8之间的整数')
    return count


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', choices=('official', 'adaptive'), default='official')
    parser.add_argument('--team-decision-mode', choices=('business_script', 'vision_conservative'),
                        default='business_script')
    parser.add_argument('--operator-mode', choices=('external', 'scripted_test'),
                        default='external')
    parser.add_argument('--domain-id', type=int, default=229)
    parser.add_argument('--gazebo-port', type=int, default=11367)
    parser.add_argument('--web-port', type=int, default=8098)
    parser.add_argument('--timeout-sec', type=positive_seconds, default=1200)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--expected-visitors', type=visitor_count, default=3)
    parser.add_argument('--keep-open', action='store_true')
    args = parser.parse_args(argv)
    if args.operator_mode == 'scripted_test' and args.team_decision_mode != 'vision_conservative':
        parser.error('scripted_test 仅支持由本运行器启动的 vision_conservative Gazebo 场景')
    return args


def allocate_run_directory(output_root, timestamp=None):
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    base_name = timestamp or datetime.now().strftime('visitor-full-%Y%m%d-%H%M%S')
    candidate = output_root / base_name
    suffix = 1
    while True:
        try:
            candidate.mkdir(exist_ok=False)
            return candidate
        except FileExistsError:
            candidate = output_root / f'{base_name}-{suffix:02d}'
            suffix += 1


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _git_output(*arguments):
    result = subprocess.run(['git', *arguments], cwd=ROOT, capture_output=True,
                            text=True, check=False)
    if result.returncode != 0:
        return ''
    return result.stdout


def build_run_manifest(run, args, command=None):
    source_status = _git_output('status', '--short', '--untracked-files=all', '--',
                                'scripts', 'ros2_ws/src', 'visualization', 'simulation',
                                'config', 'tests')
    source_hashes = {}
    for line in source_status.splitlines():
        relative = line[3:]
        path = ROOT / relative
        if path.is_file():
            source_hashes[relative] = _sha256(path)
    tracked_diff = _git_output('diff', '--binary', 'HEAD')
    dirty_fingerprint = hashlib.sha256(json.dumps({
        'tracked_diff_sha256': hashlib.sha256(tracked_diff.encode()).hexdigest(),
        'source_file_sha256': source_hashes,
    }, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    map_yaml = ROOT / f'simulation/generated/{args.layout}.yaml'
    map_image = ROOT / f'simulation/generated/{args.layout}.pgm'
    goals = ROOT / f'simulation/generated/{args.layout}_goals.json'
    model = ROOT / 'assets/vision/object_detection_yolox_2022nov.onnx'
    return {
        'schema_version': 1,
        'run_id': run.name,
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'git_head': _git_output('rev-parse', 'HEAD').strip(),
        'git_dirty_paths': _git_output('status', '--short', '--untracked-files=all').splitlines(),
        'dirty_source_sha256': dirty_fingerprint,
        'dirty_source_files': source_hashes,
        'layout': args.layout,
        'map_yaml': str(map_yaml.relative_to(ROOT)),
        'map_sha256': _sha256(map_yaml),
        'map_image': str(map_image.relative_to(ROOT)),
        'map_image_sha256': _sha256(map_image),
        'goals_file': str(goals.relative_to(ROOT)),
        'goals_sha256': _sha256(goals),
        'vision_model_sha256': _sha256(model),
        'team_decision_mode': args.team_decision_mode,
        'operator_mode': args.operator_mode,
        'expected_visitors': args.expected_visitors,
        'expected_visitors_source': 'explicit operator/demo configuration',
        'team_truth_used_for_decision': args.team_decision_mode == 'business_script',
        'ros_domain': args.domain_id,
        'gazebo_port': args.gazebo_port,
        'web_port': args.web_port,
        'timeout_sec': args.timeout_sec,
        'keep_open': args.keep_open,
        'command': list(command if command is not None else sys.argv),
    }


def evaluate_resource_snapshot(available_memory_gib, free_disk_gib, load_per_cpu,
                               cpu_cores, gazebo_processes=(), ports_available=True,
                               port_errors=()):
    reasons = []
    if available_memory_gib < MIN_AVAILABLE_GIB:
        reasons.append(f'available memory below {MIN_AVAILABLE_GIB:.1f} GiB')
    if free_disk_gib < MIN_DISK_GIB:
        reasons.append(f'free disk below {MIN_DISK_GIB:.1f} GiB')
    if load_per_cpu > 1.0:
        reasons.append('host load exceeds one runnable task per CPU')
    if gazebo_processes:
        reasons.append('another Gazebo process is already running')
    if not ports_available:
        reasons.append('one or more required local ports cannot be bound')
    return {'ready': not reasons, 'available_memory_gib': available_memory_gib,
            'free_disk_gib': free_disk_gib, 'load_per_cpu': load_per_cpu,
            'cpu_cores': cpu_cores, 'gazebo_processes': list(gazebo_processes),
            'ports_available': ports_available, 'port_errors': list(port_errors),
            'reasons': reasons}


class ResourceBlocked(RuntimeError):
    pass


def gazebo_processes_from_ps(output, returncode):
    if returncode != 0:
        raise ResourceBlocked('无法核对Gazebo进程，拒绝启动重型实验')
    gazebo_names = {'gzserver', 'gzclient'}
    return [name.strip() for name in output.splitlines() if name.strip() in gazebo_names]


def _check_local_tcp_ports(ports):
    results = []
    seen = set()
    for label, port in ports:
        if port in seen:
            results.append({'name': label, 'port': port, 'bindable': False,
                            'error': 'duplicate configured port'})
            continue
        seen.add(port)
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except OSError as error:
            results.append({'name': label, 'port': port, 'bindable': False,
                            'error': f'{type(error).__name__}: {error}'})
            continue
        try:
            probe.bind(('127.0.0.1', port))
            results.append({'name': label, 'port': port, 'bindable': True})
        except OSError as error:
            results.append({'name': label, 'port': port, 'bindable': False,
                            'error': f'{type(error).__name__}: {error}'})
        finally:
            probe.close()
    return results


def check_resource_preflight(args):
    mem_available_kib = next(
        int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()
        if line.startswith('MemAvailable:'))
    load_1m = float(Path('/proc/loadavg').read_text().split()[0])
    cpu_cores = os.cpu_count() or 1
    disk = shutil.disk_usage(ROOT)
    processes = subprocess.run(['ps', '-e', '-o', 'comm='],
                               capture_output=True, text=True, check=False)
    gazebo_processes = gazebo_processes_from_ps(processes.stdout, processes.returncode)
    port_results = _check_local_tcp_ports((('gazebo', args.gazebo_port),
                                           ('web', args.web_port)))
    port_errors = [f"{item['name']}:{item['port']} {item.get('error', 'unavailable')}"
                   for item in port_results if not item['bindable']]
    resource = evaluate_resource_snapshot(
        mem_available_kib / 1024 / 1024,
        disk.free / 1024**3,
        load_1m / cpu_cores,
        cpu_cores,
        gazebo_processes,
        ports_available=not port_errors,
        port_errors=port_errors)
    resource['domain_id'] = args.domain_id
    resource['domain_available'] = args.domain_id not in (211, 219)
    if not resource['domain_available']:
        resource['ready'] = False
        resource['reasons'].append(
            f'ROS domain {args.domain_id} is reserved by the local simulation setup')
    return resource


class StationaryStopWindow:
    def __init__(self, minimum_duration_sec=0.5, maximum_gap_sec=0.2):
        self.minimum_duration_sec = minimum_duration_sec
        self.maximum_gap_sec = maximum_gap_sec
        self.reset()

    def reset(self):
        self.session_id = None
        self.first_received_sec = None
        self.last_received_sec = None
        self.last_stamp_ns = None
        self.sample_count = 0

    def observe(self, *, valid, session_id, stamp_ns, received_sec):
        if (not valid or not isinstance(session_id, str) or not session_id or
                type(stamp_ns) is not int or stamp_ns <= 0 or
                type(received_sec) not in (int, float) or not math.isfinite(received_sec)):
            self.reset()
            return self.result()
        if self.session_id is not None and self.session_id != session_id:
            self.reset()
        if self.last_stamp_ns is not None:
            if stamp_ns == self.last_stamp_ns:
                return self.result()
            gap = received_sec - self.last_received_sec
            if stamp_ns < self.last_stamp_ns or gap <= 0 or gap > self.maximum_gap_sec:
                self.reset()
        if self.sample_count == 0:
            self.session_id = session_id
            self.first_received_sec = received_sec
        self.last_received_sec = received_sec
        self.last_stamp_ns = stamp_ns
        self.sample_count += 1
        return self.result()

    def result(self):
        duration = (0.0 if self.sample_count < 2 else
                    self.last_received_sec - self.first_received_sec)
        return {'confirmed': self.sample_count >= 2 and duration >= self.minimum_duration_sec,
                'sample_count': self.sample_count,
                'stable_duration_sec': max(0.0, duration)}


def pause_stop_evidence(snapshot, window=None):
    tour = snapshot.get('tour') or {}
    evidence = snapshot.get('evidence') or {}
    odom_snapshot = evidence.get('odom') or {}
    odom = odom_snapshot.get('value') or {}
    fused_snapshot = evidence.get('fused') or {}
    fused = fused_snapshot.get('value') or {}
    cmd_snapshot = evidence.get('cmd_vel') or {}
    cmd = cmd_snapshot.get('value') or {}
    speed = odom.get('linear_speed_mps')
    angular_speed = odom.get('angular_speed_rps')
    fresh_odom = odom_snapshot.get('fresh') is True
    age = odom_snapshot.get('age_sec')
    bounded = lambda value, limit: (type(value) in (int, float) and
                                    math.isfinite(value) and abs(value) <= limit)
    session_id = tour.get('paused_session_id')
    terminal = tour.get('state') == 'COMPLETED'
    if terminal:
        session_id = f"terminal:{tour.get('target') or 'exit'}"
    pause_state = tour.get('state') == 'PAUSED'
    stop_requested = pause_state and tour.get('last_pause_stop_requested') is True
    stop_confirmed = pause_state and tour.get('last_pause_stop_confirmed') is True
    action_quiescent = pause_state and tour.get('last_pause_action_quiescence_confirmed') is True
    manager_stop_valid = terminal or (
        tour.get('state') == 'PAUSED' and stop_requested and stop_confirmed and action_quiescent)
    safety_session_valid = (terminal or tour.get('pause_source') != 'safety' or
                            fused_snapshot.get('fresh') is True and
                            fused.get('stop_confirmed') is True and
                            fused.get('stop_confirmed_session_id') == session_id)
    cmd_clear = (cmd_snapshot.get('fresh') is not True or
                 bounded(cmd.get('linear_speed_mps'), 0.02) and
                 bounded(cmd.get('angular_speed_rps'), 0.05))
    sample_valid = (tour.get('is_moving') is False and fresh_odom and
                    type(age) in (int, float) and math.isfinite(age) and 0 <= age <= 0.5 and
                    bounded(speed, 0.02) and bounded(angular_speed, 0.05) and
                    cmd_clear and safety_session_valid and manager_stop_valid)
    window_result = ({'confirmed': False, 'sample_count': 0,
                      'stable_duration_sec': 0.0} if window is None else
                     window.observe(valid=sample_valid, session_id=session_id,
                                    stamp_ns=odom.get('stamp_ns'),
                                    received_sec=odom.get('received_monotonic_sec')))
    return {**window_result, 'sample_valid': sample_valid,
            'tour_is_moving': tour.get('is_moving'),
            'odom_fresh': fresh_odom, 'odom_linear_speed_mps': speed,
            'odom_angular_speed_rps': angular_speed, 'odom_age_sec': age,
            'stop_requested': stop_requested,
            'stop_confirmed': stop_confirmed,
            'action_quiescence_confirmed': action_quiescent,
            'stop_confirmed_session_id': fused.get('stop_confirmed_session_id'),
            'navigation_session_id': session_id}


def summarize_navigation_motion(evidence_path, *, minimum_samples_per_target=3):
    targets = ('zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5', 'exit')
    summary = {target: {'cmd_vel_motion_samples': 0, 'paired_odom_motion_samples': 0,
                        'max_cmd_vel_linear_mps': 0.0, 'max_odom_linear_mps': 0.0,
                        'navigation_sessions': set()}
               for target in targets}
    with Path(evidence_path).open(encoding='utf-8') as source:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            tour = row.get('tour') or {}
            target = tour.get('target')
            if target not in summary or tour.get('state') not in ('NAVIGATING', 'RETURNING'):
                continue
            evidence = row.get('evidence') or {}
            cmd_snapshot = evidence.get('cmd_vel') or {}
            odom_snapshot = evidence.get('odom') or {}
            cmd = cmd_snapshot.get('value') or {}
            odom = odom_snapshot.get('value') or {}
            cmd_speed = cmd.get('linear_speed_mps')
            odom_speed = odom.get('linear_speed_mps')
            cmd_age, odom_age = cmd_snapshot.get('age_sec'), odom_snapshot.get('age_sec')
            fused = (evidence.get('fused') or {}).get('value') or {}
            session_id = fused.get('navigation_session_id')
            cmd_received = cmd.get('received_monotonic_sec')
            odom_received = odom.get('received_monotonic_sec')
            odom_stamp = odom.get('stamp_ns')
            cmd_valid = (
                cmd_snapshot.get('fresh') is True and
                type(cmd_age) in (int, float) and math.isfinite(cmd_age) and 0 <= cmd_age <= 0.5 and
                type(cmd_speed) in (int, float) and math.isfinite(cmd_speed) and abs(cmd_speed) > 0.02 and
                type(cmd_received) in (int, float) and math.isfinite(cmd_received))
            if not cmd_valid:
                continue
            item = summary[target]
            item['cmd_vel_motion_samples'] += 1
            item['max_cmd_vel_linear_mps'] = max(item['max_cmd_vel_linear_mps'], abs(cmd_speed))
            valid_motion_pair = (
                odom_snapshot.get('fresh') is True and
                type(odom_age) in (int, float) and math.isfinite(odom_age) and 0 <= odom_age <= 0.5 and
                type(odom_speed) in (int, float) and math.isfinite(odom_speed) and abs(odom_speed) > 0.02 and
                type(odom_stamp) is int and odom_stamp > 0 and
                type(odom_received) in (int, float) and math.isfinite(odom_received) and
                abs(cmd_received - odom_received) <= 0.2 and
                isinstance(session_id, str) and bool(session_id))
            if not valid_motion_pair:
                continue
            item['navigation_sessions'].add(session_id)
            item['paired_odom_motion_samples'] += 1
            item['max_odom_linear_mps'] = max(item['max_odom_linear_mps'], abs(odom_speed))
    missing = [target for target, samples in summary.items()
               if samples['paired_odom_motion_samples'] < minimum_samples_per_target]
    for item in summary.values():
        item['navigation_sessions'] = sorted(item['navigation_sessions'])
    return {'complete': not missing, 'required_targets': list(targets),
            'minimum_paired_motion_samples_per_target': minimum_samples_per_target,
            'missing_targets': missing, 'targets': summary}


def summarize_pause_resumes(evidence_path):
    rows = [json.loads(line) for line in Path(evidence_path).open(encoding='utf-8')
            if line.strip()]
    summaries = []
    seen_events = set()
    for index, row in enumerate(rows):
        tour = row.get('tour') or {}
        event_id = tour.get('team_pause_event_id')
        if (tour.get('state') != 'PAUSED' or tour.get('team_recovery_required') is not True or
                not isinstance(event_id, str) or not event_id or event_id in seen_events):
            continue
        seen_events.add(event_id)
        old_session = tour.get('paused_session_id')
        route_index, target = tour.get('route_index'), tour.get('target')
        resumed_index, new_session = None, ''
        for candidate_index in range(index + 1, len(rows)):
            candidate = rows[candidate_index]
            candidate_tour = candidate.get('tour') or {}
            if (candidate_tour.get('state') == 'PAUSED' and
                    candidate_tour.get('team_pause_event_id') != event_id):
                break
            if (candidate_tour.get('state') not in ('NAVIGATING', 'RETURNING') or
                    candidate_tour.get('route_index') != route_index or
                    candidate_tour.get('target') != target):
                continue
            evidence = candidate.get('evidence') or {}
            fused_snapshot = evidence.get('fused') or {}
            fused = fused_snapshot.get('value') or {}
            candidate_session = fused.get('navigation_session_id')
            if (fused_snapshot.get('fresh') is True and isinstance(candidate_session, str) and
                    candidate_session and candidate_session != old_session):
                resumed_index, new_session = candidate_index, candidate_session
                break
        paired_samples = 0
        max_cmd_vel = max_odom = 0.0
        if resumed_index is not None:
            for candidate in rows[resumed_index:]:
                candidate_tour = candidate.get('tour') or {}
                if (candidate_tour.get('state') not in ('NAVIGATING', 'RETURNING') or
                        candidate_tour.get('route_index') != route_index or
                        candidate_tour.get('target') != target):
                    break
                evidence = candidate.get('evidence') or {}
                fused_snapshot = evidence.get('fused') or {}
                fused = fused_snapshot.get('value') or {}
                cmd_snapshot = evidence.get('cmd_vel') or {}
                odom_snapshot = evidence.get('odom') or {}
                cmd, odom = cmd_snapshot.get('value') or {}, odom_snapshot.get('value') or {}
                cmd_speed, odom_speed = cmd.get('linear_speed_mps'), odom.get('linear_speed_mps')
                cmd_received, odom_received = (cmd.get('received_monotonic_sec'),
                                               odom.get('received_monotonic_sec'))
                valid_pair = (
                    fused_snapshot.get('fresh') is True and fused.get('navigation_session_id') == new_session and
                    cmd_snapshot.get('fresh') is True and odom_snapshot.get('fresh') is True and
                    type(cmd_speed) in (int, float) and math.isfinite(cmd_speed) and abs(cmd_speed) > 0.02 and
                    type(odom_speed) in (int, float) and math.isfinite(odom_speed) and abs(odom_speed) > 0.02 and
                    type(cmd_received) in (int, float) and math.isfinite(cmd_received) and
                    type(odom_received) in (int, float) and math.isfinite(odom_received) and
                    abs(cmd_received - odom_received) <= 0.2)
                if valid_pair:
                    paired_samples += 1
                    max_cmd_vel = max(max_cmd_vel, abs(cmd_speed))
                    max_odom = max(max_odom, abs(odom_speed))
        same_target = resumed_index is not None
        uuid_changed = bool(old_session and new_session and old_session != new_session)
        summaries.append({
            'pause_event_id': event_id, 'pause_source': tour.get('pause_source'),
            'paused_session_id': old_session, 'route_index': route_index, 'target': target,
            'resumed_session_id': new_session or None, 'uuid_changed': uuid_changed,
            'same_target': same_target, 'paired_motion_samples': paired_samples,
            'max_cmd_vel_linear_mps': max_cmd_vel, 'max_odom_linear_mps': max_odom,
            'physical_motion_observed': paired_samples > 0,
            'status': 'PASS' if same_target and uuid_changed else 'NOT_VERIFIED',
        })
    return summaries


def main(argv=None):
    args = parse_args(argv)
    output_root = args.output_dir or ROOT/'docs/phase2_9/experiments/WP01-full-tour'
    run = allocate_run_directory(output_root)
    manifest = build_run_manifest(run, args)
    (run/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    env = dict(os.environ, PHASE25_INTERACTIVE='1', PHASE25_VISITOR_TEAM='1',
               PHASE25_PRESENTATION='1',
               PHASE28_TEAM_DECISION_MODE=args.team_decision_mode,
               PHASE25_EXPECTED_VISITORS=str(args.expected_visitors),
               PHASE25_LOG_DIR=str(run/'system'))
    origin = f'http://127.0.0.1:{args.web_port}'
    events = []
    report = {'status': 'RUNNING', 'layout': args.layout,
              'team_decision_mode': args.team_decision_mode,
              'operator_mode': args.operator_mode,
              'run_id': run.name,
              'manifest': str(run/'manifest.json'),
              'team_evidence_source': ('vision_tracker' if args.team_decision_mode == 'vision_conservative'
                                       else 'gazebo_scripted_actors'),
              'actor_source': 'Gazebo scripted visitor actors',
              'expected_visitors': args.expected_visitors,
              'expected_visitors_source': 'explicit demo/operator configuration',
              'operator_mode_description': ('simulated consent; test operator input is separately logged'
                                            if args.operator_mode == 'scripted_test' else
                                            'simulated visitor consent; vision recovery requires an external operator action'),
              'scripted_operator_scope': ('this run-owned Gazebo process'
                                          if args.operator_mode == 'scripted_test' else None),
              'speech_mode': 'timed subtitles, no physical temi audio'}
    handle = (run/'system.log').open('w')
    process = None
    print(f'完整演示：{origin}\n证据：{run}', flush=True)
    started = time.monotonic()

    def command(action, question=None, **fields):
        payload = {'action': action, 'question': question, **fields}
        request = urllib.request.Request(origin+'/api/interact', data=json.dumps(payload).encode(), headers={'Origin': origin, 'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=12) as response:
            result = json.load(response)
        events.append({'elapsed_sec': time.monotonic()-started, 'action': action, 'result': result})
        if not result.get('success'):
            raise RuntimeError(f'{action}: {result}')
        print(f'模拟游客/操作员：{action}', flush=True)

    begun = accepted = straggled = gathering = resumed = asked = finished_qa = False
    gathered_at = None
    pause_handled = False
    last_state = None
    ready_since = None
    vision_pause_seen = False
    pause_stops = []
    last_pause_signature = None
    active_pause_signature = None
    pause_stop_window = StationaryStopWindow()
    final_stop_window = StationaryStopWindow()
    try:
        resource_state = check_resource_preflight(args)
        report['resource_preflight'] = resource_state
        if not resource_state['ready']:
            raise ResourceBlocked('; '.join(resource_state['reasons']))
        process = subprocess.Popen(['bash', 'scripts/start_phase25_system.sh', str(args.domain_id),
                                    str(args.gazebo_port), str(args.web_port), '0.35', '0.55', '0',
                                    args.layout], cwd=ROOT, env=env, stdout=handle,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        with (run/'live_evidence.jsonl').open('w') as evidence:
            while time.monotonic()-started < args.timeout_sec:
                if process.poll() is not None:
                    raise RuntimeError('仿真系统已退出，查看 system.log')
                try:
                    with urllib.request.urlopen(origin+'/api/pose', timeout=3) as response:
                        data = json.load(response)
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(.5)
                    continue
                evidence.write(json.dumps({'elapsed_sec': time.monotonic()-started, **data}, ensure_ascii=False)+'\n')
                evidence.flush()
                tour, team, speed = data.get('tour') or {}, data.get('team') or {}, data.get('speed_control') or {}
                state = tour.get('state')
                if state != 'PAUSED':
                    pause_handled = False
                    gathered_at = None
                    active_pause_signature = None
                    pause_stop_window.reset()
                previous_state = last_state
                if state != last_state:
                    print(f'{state}: {tour.get("reason", "")}', flush=True)
                    last_state = state
                if (args.team_decision_mode == 'vision_conservative' and vision_pause_seen and
                        previous_state == 'PAUSED' and state in ('NAVIGATING', 'RETURNING')):
                    resumed = True
                    events.append({'elapsed_sec': time.monotonic()-started,
                                   'action': 'operator_resume_observed',
                               'result': {'source': 'external dashboard action',
                                          'operator_identity_verified': False}})
                if state == 'ERROR' or speed.get('state') == 'ERROR':
                    raise RuntimeError(f'故障需人工检查：{tour.get("reason")} / {speed.get("reason")}')
                try:
                    system_ready = json.loads((run/'system/preflight.json').read_text()).get('ready') is True
                except (OSError, ValueError):
                    system_ready = False
                if args.team_decision_mode == 'vision_conservative':
                    team_ready = True
                else:
                    team_ready = team.get('gathered') is True
                ready = system_ready and state == 'IDLE' and team_ready and tour.get('connected') and tour.get('is_moving') is False
                ready_since = (ready_since or time.monotonic()) if ready else None
                pause_team = team
                if args.team_decision_mode == 'vision_conservative':
                    pause_team = (((data.get('evidence') or {}).get('team_observation') or {}).get('value'))
                if not begun and ready_since is not None and time.monotonic()-ready_since > 1.0:
                    command('start'); begun = True
                elif not accepted and state == 'WAITING_CONSENT':
                    time.sleep(2)
                    command('accept'); accepted = True
                elif (not straggled and should_inject_scripted_straggle(args.team_decision_mode) and
                      state == 'NAVIGATING' and tour.get('target') == 'zone_2'):
                    command('straggle'); straggled = True
                elif should_handle_paused_team(args.team_decision_mode, tour, pause_team):
                    signature = (tour.get('pause_source'), tour.get('route_index'),
                                 tour.get('paused_session_id'), tour.get('target'))
                    if signature != active_pause_signature:
                        pause_stop_window.reset()
                        active_pause_signature = signature
                    stop_evidence = pause_stop_evidence(data, pause_stop_window)
                    if not stop_evidence['confirmed']:
                        time.sleep(.1)
                        continue
                    if signature != last_pause_signature:
                        pause_stops.append({'elapsed_sec': time.monotonic()-started,
                                            'reason': tour.get('reason'), **stop_evidence})
                        last_pause_signature = signature
                    if not pause_handled:
                        if args.team_decision_mode == 'vision_conservative':
                            vision_pause_seen = True
                            if scripted_operator_confirmation_allowed(
                                    args.operator_mode, args.team_decision_mode, tour,
                                    pause_team, stop_evidence):
                                fused = (((data.get('evidence') or {}).get('fused') or {}).get('value') or {})
                                command('confirm_team_recovery',
                                        pause_event_id=tour['team_pause_event_id'])
                                events.append({
                                    'elapsed_sec': time.monotonic()-started,
                                    'action': 'operator_team_confirmation',
                                    'result': {
                                        'operator_type': 'simulated_test_input',
                                        'pause_source': tour.get('pause_source'),
                                        'team_pause_event_id': tour.get('team_pause_event_id'),
                                        'route_index': tour.get('route_index'),
                                        'target': tour.get('target'),
                                        'paused_session_id': tour.get('paused_session_id'),
                                        'team_resume_confirmed_before': tour.get('team_resume_confirmed'),
                                        'recovery_ack_id': tour.get('recovery_ack_id'),
                                        'observed_navigation_session_id': fused.get('navigation_session_id'),
                                        'team_state_source': 'vision_tracker',
                                        'tour_resume_requested': True,
                                        'safety_recovery_bypassed': False,
                                    },
                                })
                            pause_handled = True
                        else:
                            command('gather'); gathering = True; pause_handled = True
                    if args.team_decision_mode == 'business_script':
                        gathered_visually = team.get('gathered') is True
                        if gathered_visually:
                            gathered_at = gathered_at or time.monotonic()
                            if time.monotonic()-gathered_at > 2:
                                command('resume'); resumed = True
                elif state == 'QA' and tour.get('qa_waiting'):
                    if not asked:
                        command('ask', '潮州音乐有哪些类型？'); asked = True
                    elif tour.get('qa_result') and not finished_qa:
                        time.sleep(3)
                        command('finish_qa'); finished_qa = True
                if state == 'COMPLETED':
                    if args.team_decision_mode == 'business_script':
                        expected_events = all((accepted, straggled, gathering, resumed, asked))
                    else:
                        expected_events = accepted and asked and (not vision_pause_seen or resumed)
                    if tour.get('visited') != ['wait','zone_1','zone_2','zone_3','zone_4','zone_5','exit'] or not expected_events:
                        raise RuntimeError('路线或交互证据不完整')
                    final_stop = pause_stop_evidence(data, final_stop_window)
                    if not final_stop['confirmed']:
                        time.sleep(.1)
                        continue
                    cmd_vel = ((data.get('evidence') or {}).get('cmd_vel') or {})
                    motion_evidence = summarize_navigation_motion(run/'live_evidence.jsonl')
                    report['navigation_motion_evidence'] = motion_evidence
                    if not motion_evidence['complete']:
                        raise RuntimeError('导航期间缺少有效cmd_vel/odom运动证据')
                    pause_resume_evidence = summarize_pause_resumes(run/'live_evidence.jsonl')
                    report['pause_resume_evidence'] = pause_resume_evidence
                    if (not pause_resume_evidence or
                            any(item['status'] != 'PASS' for item in pause_resume_evidence) or
                            not any(item['physical_motion_observed'] for item in pause_resume_evidence)):
                        raise RuntimeError('暂停恢复缺少同目标新UUID或配对cmd_vel/odom证据')
                    if not final_stop['confirmed']:
                        raise RuntimeError('终点缺少新鲜odom停稳证据')
                    if not pause_stops:
                        raise RuntimeError('未采到暂停期间新鲜odom停稳证据')
                    qa = tour.get('qa_result') or {}
                    if qa.get('found') is not True or qa.get('spoken') is not True:
                        raise RuntimeError('知识回答或模拟播报终态不完整')
                    if (args.team_decision_mode == 'business_script' and
                            not business_team_complete(team, args.expected_visitors)):
                        raise RuntimeError('business_script 模式团队未完整集合')
                    if args.team_decision_mode == 'vision_conservative':
                        report['team_truth_used_for_decision'] = False
                        report['status'] = 'PASS_WITH_RISK'
                        report['gazebo_actor_status'] = team
                        report['final_team_observation'] = ((data.get('evidence') or {}).get('team_observation') or {})
                    else:
                        report.update(status='PASS', final_team=team)
                    report['final_tour'] = tour
                    report['final_stop_evidence'] = final_stop
                    report['terminal_cmd_vel_snapshot'] = cmd_vel
                    report['pause_stop_evidence'] = pause_stops
                    break
                time.sleep(.3)
            else:
                raise TimeoutError('完整演示超时')
    except KeyboardInterrupt:
        report.update(status='FAIL', error='演示被操作员中断')
    except ResourceBlocked as error:
        report.update(status='BLOCKED', error=str(error))
    except Exception as error:
        report.update(status='FAIL', error=str(error))
    finally:
        report.update(events=events, elapsed_sec=time.monotonic()-started)
        (run/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({'status': report['status'], 'report': str(run/'report.json'), 'error': report.get('error')}, ensure_ascii=False), flush=True)
        try:
            if args.keep_open and report['status'] in ('PASS', 'PASS_WITH_RISK'):
                print('演示完成，保留出口画面；按 Ctrl+C 关闭本轮系统。', flush=True)
                try:
                    process.wait()
                except KeyboardInterrupt:
                    pass
        finally:
            if process is not None and process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=25)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            handle.close()
    return (0 if report['status'] in ('PASS', 'PASS_WITH_RISK') else
            2 if report['status'] == 'BLOCKED' else 1)


if __name__ == '__main__':
    raise SystemExit(main())
