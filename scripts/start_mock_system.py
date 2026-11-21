"""本机 Mock 部署入口：默认待机，显式 --demo 执行模拟导览。"""

import argparse
import copy
import json
import os
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def mock_config(config):
    result = copy.deepcopy(config)
    result['gateway']['backend'] = 'mock'
    result['tour']['visitor_assist_enabled'] = False
    result['visitor_perception']['count_source'] = 'mock'
    return result


def valid_round(tour, robot, visitor, route):
    qa = tour.get('qa_result') or {}
    return bool(tour.get('state') == 'COMPLETED' and tour.get('outcome') == 'completed' and
                tour.get('visited') == route and tour.get('error_count') == 0 and
                qa.get('spoken') and qa.get('found') and qa.get('source', {}).get('url') and
                robot.get('connected') and robot.get('moving') is False and
                robot.get('frame') == 'mock_map' and robot.get('location') == route[-1] and
                visitor.get('valid') and visitor.get('stable_fresh') and
                visitor.get('source') == 'mock' and visitor.get('people_count') == 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--headless', action='store_true', help='不启动图形监控台')
    parser.add_argument('--demo', action='store_true', help='显式模拟游客同意、提问及完整导览')
    parser.add_argument('--speed-scenarios', action='store_true', help='完整导览期间注入明确标记的动态调速模拟感知场景')
    parser.add_argument('--rounds', type=int, default=None, help='同一组节点连续演示轮数（1–6）')
    parser.add_argument('--domain', type=int, default=218)
    args = parser.parse_args()
    if not 0 <= args.domain <= 232:
        parser.error('ROS Domain 必须在 0 到 232 之间')
    if args.speed_scenarios and not args.demo:
        parser.error('--speed-scenarios 需要 --demo')
    if args.rounds is not None and not args.demo:
        parser.error('--rounds 需要 --demo')
    if args.rounds is not None and not 1 <= args.rounds <= 6:
        parser.error('--rounds 必须在 1 到 6 之间')

    run_dir = ROOT / 'docs/runs' / datetime.now().strftime('mock-system-%Y%m%d-%H%M%S-%f')
    run_dir.mkdir(parents=True)
    os.environ.update(ROS_LOCALHOST_ONLY='1', ROS_DOMAIN_ID=str(args.domain),
                      ROS_LOG_DIR=str(run_dir / 'ros-logs'))
    import rclpy
    from rclpy.signals import SignalHandlerOptions
    from std_msgs.msg import Int32, String
    from std_srvs.srv import Trigger
    from temi_interfaces.msg import RobotStatus
    from temi_interfaces.srv import AskHeritage, SubmitQuestion

    report = {'success': False, 'mode': 'demo' if args.demo else 'idle',
              'domain': args.domain, 'headless': args.headless, 'children': [],
              'tour': {}, 'visitor': {}, 'robot': {}, 'error': '', 'rounds': [],
              'requested_rounds': (args.rounds or 1) if args.demo else 0}
    processes = []
    node = None
    stopping = False
    closed = False
    ready = False
    timestamps = {}
    started_at = time.monotonic()
    tour_shutdown_timeout = 25.0

    def request_stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    def receive(key, msg):
        report[key] = json.loads(msg.data)
        timestamps[key] = time.monotonic()

    def receive_robot(msg):
        report['robot'] = {'connected': msg.connected, 'frame': msg.header.frame_id,
                           'moving': msg.is_moving, 'location': msg.current_location,
                           'battery_percentage': msg.battery_percentage}
        timestamps['robot'] = time.monotonic()

    def check_children():
        nonlocal closed
        for name, process, _handle in processes:
            code = process.poll()
            if code is not None:
                if name == 'dashboard' and code == 0 and ready and not args.demo:
                    closed = True
                else:
                    raise RuntimeError(f'{name} 提前退出 ({code})')

    def wait_until(predicate, description, timeout=20):
        deadline = time.monotonic() + timeout
        while True:
            if stopping:
                raise InterruptedError('收到停止请求')
            check_children()
            if ready and any(time.monotonic() - timestamps.get(key, 0) > 5
                             for key in ('tour', 'visitor', 'robot')):
                raise RuntimeError('状态心跳中断')
            if predicate():
                return
            if time.monotonic() >= deadline:
                raise RuntimeError(f'{description} 超时')
            rclpy.spin_once(node, timeout_sec=0.05)

    def call(client, request):
        future = client.call_async(request)
        wait_until(future.done, '服务响应', 5)
        return future.result()

    def launch(package, executable, arguments):
        path = ROOT / 'ros2_ws/install' / package / 'lib' / package / executable
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RuntimeError(f'缺少可执行文件: {path}')
        handle = (run_dir / f'{executable}.log').open('w', encoding='utf-8')
        try:
            process = subprocess.Popen([str(path), *map(str, arguments)], cwd=ROOT,
                                       stdout=handle, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        except Exception:
            handle.close()
            raise
        processes.append((executable, process, handle))

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    try:
        config = mock_config(yaml.safe_load((ROOT / 'config/system.yaml').read_text()))
        # STOP(1×)、取消 Action(2×)、旧任务清理(1×)及 executor 最多两次 5s 等待。
        tour_shutdown_timeout = 4 * float(config['tour']['communication_timeout_sec']) + 13
        system = run_dir / 'system.yaml'
        system.write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')
        exhibits = ROOT / 'config/exhibits.yaml'
        route = [item['temi_location'] for item in yaml.safe_load(exhibits.read_text())['exhibits']]
        rclpy.init(args=[], signal_handler_options=SignalHandlerOptions.NO)
        node = rclpy.create_node('heritage_system_supervisor')
        end = time.monotonic() + 1.5
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.1)
            if stopping:
                raise InterruptedError('收到停止请求')
            if node.get_node_names().count(node.get_name()) > 1 or any(
                    name != node.get_name() for name in node.get_node_names()):
                raise RuntimeError('该 ROS Domain 已有其他节点，请更换 --domain')
        node.create_subscription(RobotStatus, 'temi/robot_status', receive_robot, 10)
        node.create_subscription(String, 'heritage/tour/status', lambda msg: receive('tour', msg), 10)
        node.create_subscription(String, 'heritage/visitor/status', lambda msg: receive('visitor', msg), 10)
        services = {name: node.create_client(Trigger, 'heritage/tour/' + name)
                    for name in ('start', 'accept', 'finish_qa', 'manual_takeover')}
        knowledge = node.create_client(AskHeritage, 'heritage/knowledge/ask')
        submit = node.create_client(SubmitQuestion, 'heritage/tour/ask')
        launch('temi_bridge', 'temi_gateway', ['--config', system, '--backend', 'mock'])
        launch('heritage_knowledge', 'knowledge_node', ['--config', ROOT / 'config/knowledge.yaml'])
        launch('visitor_perception', 'visitor_perception', ['--config', system])
        launch('heritage_tour_manager', 'tour_manager', ['--config', system, '--exhibits', exhibits])
        launch('temi_speed_controller', 'speed_controller',
               ['--ros-args', '--params-file', ROOT / 'ros2_ws/src/temi_speed_controller/config/speed_config.yaml',
                '-p', 'mock_mode:=true'])
        if not args.headless:
            launch('heritage_dashboard', 'dashboard', ['--config', system, '--exhibits', exhibits])
        required = {'temi_gateway', 'heritage_knowledge', 'visitor_perception',
                    'heritage_tour_manager', 'temi_speed_controller'}
        if not args.headless:
            required.add('heritage_dashboard')
        wait_until(lambda: required <= set(node.get_node_names()) and
                   all(client.service_is_ready() for client in [*services.values(), knowledge, submit]) and
                   report['robot'].get('connected') and report['robot'].get('frame') == 'mock_map' and
                   report['tour'].get('state') == 'IDLE' and report['visitor'].get('source') == 'mock' and
                   all(time.monotonic() - timestamps.get(key, 0) < 2 for key in ('tour', 'visitor', 'robot')),
                   '系统就绪')
        response = call(knowledge, AskHeritage.Request(question='潮剧用什么语言', level='basic'))
        if not response.found or not json.loads(response.source_json).get('url'):
            raise RuntimeError('知识库自检失败')
        ready = True
        report['ready_nodes'] = sorted(required)
        print(f'系统就绪: Mock / Domain {args.domain} / {len(required)} 个运行节点', flush=True)
        if args.demo:
            publisher = node.create_publisher(Int32, 'heritage/visitor/count', 10)
            node.create_timer(0.1, lambda: publisher.publish(Int32(data=3)))
            wait_until(lambda: report['visitor'].get('valid'), '模拟人数')
            for round_number in range(1, (args.rounds or 1) + 1):
                for name, state in [('start', 'WAITING_CONSENT'), ('accept', 'QA')]:
                    response = call(services[name], Trigger.Request())
                    if not response.success:
                        raise RuntimeError(response.message)
                    if state == 'QA' and args.speed_scenarios and round_number == 1:
                        wait_until(lambda: report['tour'].get('state') in ('NAVIGATING', 'EXPLAINING'),
                                   '开始移动后注入速度场景', 10)
                        handle = (run_dir / 'mock_speed_scenarios.log').open('w', encoding='utf-8')
                        process = subprocess.Popen([str(ROOT / 'scripts/mock_speed_scenarios.py'),
                                                    '--scenario', 'cycle', '--seconds-per-stage', '2'],
                                                   cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
                                                   env=os.environ.copy())
                        processes.append(('mock_speed_scenarios', process, handle))
                    wait_until(lambda: report['tour'].get('state') == state, state, 90)
                response = call(submit, SubmitQuestion.Request(question='潮剧用什么语言', level='basic'))
                if not response.accepted:
                    raise RuntimeError(response.message)
                wait_until(lambda: report['tour'].get('state') in ('COMPLETED', 'ERROR'), '导览终态', 60)
                tour = report['tour']
                if tour['state'] != 'COMPLETED':
                    raise RuntimeError('八站及知识问答核验不通过')
                wait_until(lambda: report['robot'].get('connected') and
                           not report['robot'].get('moving', True) and
                           report['robot'].get('location') == route[-1], 'Mock 机器人静止')
                # 终态后观察一秒，确认没有自动重启旧任务，再显式发起下一轮。
                end = time.monotonic() + 1
                def settled():
                    if not valid_round(report['tour'], report['robot'], report['visitor'], route):
                        raise RuntimeError('终态观察中八站、知识问答或状态核验不通过')
                    return time.monotonic() >= end
                wait_until(settled, '终态稳定观察')
                report['rounds'].append({'round': round_number, 'tour': copy.deepcopy(report['tour']),
                                         'robot': copy.deepcopy(report['robot']),
                                         'visitor': copy.deepcopy(report['visitor'])})
                print(f"第 {round_number} 轮完整导览: {len(tour['visited'])}/{len(route)} 站，"
                      f"{tour['elapsed_sec']} 秒，异常 0 次", flush=True)
        else:
            print('待机中，未自动开始导览；Ctrl+C 或关闭监控台退出。', flush=True)
            while not stopping and not closed:
                check_children()
                rclpy.spin_once(node, timeout_sec=0.1)
                if any(time.monotonic() - timestamps.get(key, 0) > 5
                       for key in ('tour', 'visitor', 'robot')):
                    raise RuntimeError('状态心跳中断')
        report['success'] = True
    except (Exception, KeyboardInterrupt) as error:
        report['error'] = str(error) or type(error).__name__
        print(f"运行中止: {report['error']}", flush=True)
    finally:
        # 先退出监控和 Tour，再退出 Gateway，使取消/STOP 可正常处理。
        for name, process, handle in reversed(processes):
            forced = False
            if process.poll() is None:
                process.send_signal(signal.SIGINT if name in ('knowledge_node', 'speed_controller', 'mock_speed_scenarios') else signal.SIGTERM)
                try:
                    process.wait(timeout=tour_shutdown_timeout if name == 'tour_manager' else 12)
                except subprocess.TimeoutExpired:
                    forced = True
                    process.kill()
                    process.wait(timeout=3)
            report['children'].append({'name': name, 'pid': process.pid,
                                       'exit_code': process.returncode, 'forced': forced})
            handle.close()
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()
        report['success'] = report['success'] and all(
            child['exit_code'] == 0 and not child['forced'] for child in report['children'])
        if not report['success'] and not report['error']:
            report['error'] = '一个或多个子进程未正常退出'
        report['wall_time_sec'] = round(time.monotonic() - started_at, 3)
        report['status_snapshot_note'] = 'tour、robot、visitor 是关停前最后收到的状态，不是停车确认。'
        path = run_dir / 'report.json'
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'运行报告: {path}', flush=True)
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
