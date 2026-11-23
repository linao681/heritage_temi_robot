"""Run a scripted visitor/operator demonstration over real Gazebo ROS services."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
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
        if isinstance(team, dict) and 'requires_manual_confirmation' in team:
            return team.get('requires_manual_confirmation') is True
        return '视觉' in reason or '观察' in reason
    if team_decision_mode != 'business_script' or not isinstance(team, dict):
        return False
    stamp = team.get('time_monotonic_sec')
    now = time.monotonic() if now_monotonic is None else now_monotonic
    fresh_team = (team.get('valid') is True and type(stamp) in (int, float) and
                  0 <= now-stamp <= 1.0)
    pending_recovery = tour.get('team_recovery_required') is True
    return (fresh_team and (pending_recovery or team.get('state') == 'LOST' or
                            '掉队' in reason))


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
    parser.add_argument('--domain-id', type=int, default=229)
    parser.add_argument('--gazebo-port', type=int, default=11367)
    parser.add_argument('--web-port', type=int, default=8098)
    parser.add_argument('--timeout-sec', type=positive_seconds, default=1200)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--expected-visitors', type=visitor_count, default=3)
    parser.add_argument('--keep-open', action='store_true')
    return parser.parse_args(argv)


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
    return evaluate_resource_snapshot(
        mem_available_kib / 1024 / 1024,
        disk.free / 1024**3,
        load_1m / cpu_cores,
        cpu_cores,
        gazebo_processes,
        ports_available=not port_errors,
        port_errors=port_errors)


def pause_stop_evidence(snapshot):
    tour = snapshot.get('tour') or {}
    odom_snapshot = ((snapshot.get('evidence') or {}).get('odom') or {})
    odom = odom_snapshot.get('value') or {}
    speed = odom.get('linear_speed_mps')
    fresh_odom = odom_snapshot.get('fresh') is True
    stopped = (tour.get('is_moving') is False and fresh_odom and
               isinstance(speed, (int, float)) and speed <= 0.02)
    return {'confirmed': stopped, 'tour_is_moving': tour.get('is_moving'),
            'odom_fresh': fresh_odom, 'odom_linear_speed_mps': speed,
            'odom_age_sec': odom_snapshot.get('age_sec'),
            'navigation_session_id': tour.get('paused_session_id')}


def summarize_navigation_motion(evidence_path, *, minimum_samples_per_target=3):
    targets = ('zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5', 'exit')
    summary = {target: {'cmd_vel_motion_samples': 0, 'paired_odom_motion_samples': 0,
                        'max_cmd_vel_linear_mps': 0.0, 'max_odom_linear_mps': 0.0}
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
            if (cmd_snapshot.get('fresh') is not True or type(cmd_speed) not in (int, float) or
                    abs(cmd_speed) <= 0.02):
                continue
            item = summary[target]
            item['cmd_vel_motion_samples'] += 1
            item['max_cmd_vel_linear_mps'] = max(item['max_cmd_vel_linear_mps'], abs(cmd_speed))
            if (odom_snapshot.get('fresh') is True and type(odom_speed) in (int, float) and
                    abs(odom_speed) > 0.02):
                item['paired_odom_motion_samples'] += 1
                item['max_odom_linear_mps'] = max(item['max_odom_linear_mps'], abs(odom_speed))
    missing = [target for target, samples in summary.items()
               if samples['paired_odom_motion_samples'] < minimum_samples_per_target]
    return {'complete': not missing, 'required_targets': list(targets),
            'minimum_paired_motion_samples_per_target': minimum_samples_per_target,
            'missing_targets': missing, 'targets': summary}


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
              'run_id': run.name,
              'manifest': str(run/'manifest.json'),
              'team_evidence_source': ('vision_tracker' if args.team_decision_mode == 'vision_conservative'
                                       else 'gazebo_scripted_actors'),
              'actor_source': 'Gazebo scripted visitor actors',
              'expected_visitors': args.expected_visitors,
              'expected_visitors_source': 'explicit demo/operator configuration',
              'operator_mode': ('scripted simulated consent; business regroup is scripted; '
                                'vision resume requires an external operator action'),
              'speech_mode': 'timed subtitles, no physical temi audio'}
    handle = (run/'system.log').open('w')
    process = None
    print(f'完整演示：{origin}\n证据：{run}', flush=True)
    started = time.monotonic()

    def command(action, question=None):
        request = urllib.request.Request(origin+'/api/interact', data=json.dumps({'action': action, 'question': question}).encode(), headers={'Origin': origin, 'Content-Type': 'application/json'}, method='POST')
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
                elif not straggled and state == 'NAVIGATING' and tour.get('target') == 'zone_2':
                    command('straggle'); straggled = True
                elif should_handle_paused_team(args.team_decision_mode, tour, pause_team):
                    stop_evidence = pause_stop_evidence(data)
                    if not stop_evidence['confirmed']:
                        time.sleep(.1)
                        continue
                    signature = (tour.get('route_index'), tour.get('paused_session_id'))
                    if signature != last_pause_signature:
                        pause_stops.append({'elapsed_sec': time.monotonic()-started,
                                            'reason': tour.get('reason'), **stop_evidence})
                        last_pause_signature = signature
                    if not pause_handled:
                        if args.team_decision_mode == 'vision_conservative':
                            vision_pause_seen = True
                            if straggled:
                                command('gather'); gathering = True
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
                    expected_events = (accepted, straggled, gathering, resumed, asked)
                    if tour.get('visited') != ['wait','zone_1','zone_2','zone_3','zone_4','zone_5','exit'] or not all(expected_events):
                        raise RuntimeError('路线或交互证据不完整')
                    final_stop = pause_stop_evidence(data)
                    cmd_vel = ((data.get('evidence') or {}).get('cmd_vel') or {})
                    motion_evidence = summarize_navigation_motion(run/'live_evidence.jsonl')
                    report['navigation_motion_evidence'] = motion_evidence
                    if not motion_evidence['complete']:
                        raise RuntimeError('导航期间缺少有效cmd_vel/odom运动证据')
                    if (tour.get('is_moving') is not False or not final_stop['odom_fresh'] or
                            not isinstance(final_stop['odom_linear_speed_mps'], (int, float)) or
                            final_stop['odom_linear_speed_mps'] > 0.02):
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
