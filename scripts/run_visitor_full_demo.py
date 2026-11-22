"""Run a scripted visitor/operator demonstration over real Gazebo ROS services."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain-id', type=int, default=229)
    parser.add_argument('--gazebo-port', type=int, default=11367)
    parser.add_argument('--web-port', type=int, default=8098)
    parser.add_argument('--keep-open', action='store_true')
    args = parser.parse_args()
    run = ROOT/'docs/phase2_7/experiments'/datetime.now().strftime('visitor-full-%Y%m%d-%H%M%S')
    run.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PHASE25_INTERACTIVE='1', PHASE25_VISITOR_TEAM='1', PHASE25_PRESENTATION='1', PHASE25_LOG_DIR=str(run/'system'))
    origin = f'http://127.0.0.1:{args.web_port}'
    events = []
    report = {'status': 'RUNNING', 'operator_mode': 'scripted simulated consent and regroup confirmation', 'speech_mode': 'timed subtitles, no physical temi audio'}
    handle = (run/'system.log').open('w')
    process = subprocess.Popen(['bash', 'scripts/start_phase25_system.sh', str(args.domain_id), str(args.gazebo_port), str(args.web_port)], cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT)
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
    try:
        with (run/'live_evidence.jsonl').open('w') as evidence:
            while time.monotonic()-started < 1200:
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
                if state != last_state:
                    print(f'{state}: {tour.get("reason", "")}', flush=True)
                    last_state = state
                if state == 'ERROR' or speed.get('state') == 'ERROR':
                    raise RuntimeError(f'故障需人工检查：{tour.get("reason")} / {speed.get("reason")}')
                try:
                    system_ready = json.loads((run/'system/preflight.json').read_text()).get('ready') is True
                except (OSError, ValueError):
                    system_ready = False
                ready = system_ready and state == 'IDLE' and team.get('gathered') and tour.get('connected') and tour.get('is_moving') is False
                ready_since = (ready_since or time.monotonic()) if ready else None
                if not begun and ready_since is not None and time.monotonic()-ready_since > 1.0:
                    command('start'); begun = True
                elif not accepted and state == 'WAITING_CONSENT':
                    time.sleep(2)
                    command('accept'); accepted = True
                elif not straggled and state == 'NAVIGATING' and tour.get('target') == 'zone_2':
                    command('straggle'); straggled = True
                elif state == 'PAUSED' and '掉队' in tour.get('reason', ''):
                    if not pause_handled:
                        command('gather'); gathering = True; pause_handled = True
                    if team.get('gathered'):
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
                    if tour.get('visited') != ['wait','zone_1','zone_2','zone_3','zone_4','zone_5','exit'] or not all((accepted,straggled,gathering,resumed,asked)):
                        raise RuntimeError('路线或交互证据不完整')
                    qa = tour.get('qa_result') or {}
                    if qa.get('found') is not True or qa.get('spoken') is not True or team.get('count') != 3:
                        raise RuntimeError('知识回答、模拟播报或三人团队终态不完整')
                    report.update(status='PASS', final_tour=tour, final_team=team)
                    break
                time.sleep(.3)
            else:
                raise TimeoutError('完整演示超时')
    except KeyboardInterrupt:
        report.update(status='FAIL', error='演示被操作员中断')
    except Exception as error:
        report.update(status='FAIL', error=str(error))
    finally:
        report.update(events=events, elapsed_sec=time.monotonic()-started)
        (run/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({'status': report['status'], 'report': str(run/'report.json'), 'error': report.get('error')}, ensure_ascii=False), flush=True)
        try:
            if args.keep_open and report['status'] == 'PASS':
                print('演示完成，保留出口画面；按 Ctrl+C 关闭本轮系统。', flush=True)
                process.wait()
        finally:
            process.send_signal(signal.SIGINT) if process.poll() is None else None
            process.wait(timeout=30)
            handle.close()
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
