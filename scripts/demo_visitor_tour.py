"""三个独立本机 ROS2 进程演示 Mock 游客联动与完整八站导览。"""

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import time

import rclpy
from std_msgs.msg import Int32, String
from std_srvs.srv import Trigger
from temi_interfaces.msg import NavigationStatus
import yaml


ROOT = Path(__file__).resolve().parents[1]


def main():
    run_dir = ROOT / 'docs' / 'runs' / datetime.now().strftime('visitor-tour-%Y%m%d-%H%M%S-%f')
    run_dir.mkdir(parents=True)
    os.environ.update(ROS_LOCALHOST_ONLY='1', ROS_DOMAIN_ID='223',
                      ROS_LOG_DIR=str(run_dir / 'ros-logs'))
    system = yaml.safe_load((ROOT / 'config/system.yaml').read_text(encoding='utf-8'))
    system['gateway']['backend'] = 'mock'
    system['tour']['visitor_assist_enabled'] = True
    config = run_dir / 'system_mock.yaml'
    config.write_text(yaml.safe_dump(system, allow_unicode=True), encoding='utf-8')
    processes, handles, controls, visitor_events, navigation_events = [], [], [], [], []
    latest, visitor = {}, {}
    observed_count = 0
    printed = 0
    node = None
    started = time.monotonic()

    def launch(package, executable, arguments):
        path = ROOT / 'ros2_ws' / 'install' / package / 'lib' / package / executable
        handle = (run_dir / f'{executable}.log').open('w', encoding='utf-8')
        handles.append(handle)
        processes.append(subprocess.Popen([str(path), *map(str, arguments)], cwd=ROOT,
                                          stdout=handle, stderr=subprocess.STDOUT))

    def receive_tour(message):
        nonlocal latest, printed
        latest = json.loads(message.data)
        history = latest['history']
        for entry in history[printed:]:
            print(f"{entry['elapsed_sec']:7.3f}s {entry['state']:16} {entry['reason']}", flush=True)
        printed = len(history)

    def receive_visitor(message):
        nonlocal visitor
        visitor = json.loads(message.data)

    def receive_event(message):
        event = json.loads(message.data)
        visitor_events.append(event)
        print(f"游客事件: {event['event']}", flush=True)

    def receive_navigation(message):
        navigation_events.append({'task_id': message.task_id, 'target': message.target,
                                  'status': message.status, 'description': message.description})

    def wait_until(predicate, timeout=12.0):
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= deadline or any(proc.poll() is not None for proc in processes):
                raise RuntimeError(f'联动等待超时或进程退出：{latest.get("state")}，日志 {run_dir}')
            rclpy.spin_once(node, timeout_sec=0.05)

    def assisting():
        return latest.get('visitor_assist', {})

    try:
        launch('temi_bridge', 'temi_gateway', ['--config', config, '--backend', 'mock'])
        launch('visitor_perception', 'visitor_perception', ['--config', config])
        launch('heritage_tour_manager', 'tour_manager', ['--config', config,
                                                       '--exhibits', ROOT / 'config/exhibits.yaml'])
        rclpy.init(args=[])
        node = rclpy.create_node('visitor_tour_demo_client')
        counts = node.create_publisher(Int32, 'heritage/visitor/count', 10)
        node.create_timer(0.1, lambda: counts.publish(Int32(data=observed_count)))
        node.create_subscription(String, 'heritage/tour/status', receive_tour, 100)
        node.create_subscription(String, 'heritage/visitor/status', receive_visitor, 50)
        node.create_subscription(String, 'heritage/visitor/events', receive_event, 50)
        node.create_subscription(NavigationStatus, 'temi/navigation_status', receive_navigation, 100)
        services = {name: node.create_client(Trigger, 'heritage/tour/' + name)
                    for name in ('arm_visitor', 'accept', 'resume', 'finish_qa')}

        def call(name, want=True):
            if not services[name].wait_for_service(timeout_sec=5.0):
                raise RuntimeError(f'{name} 服务未就绪')
            future = services[name].call_async(Trigger.Request())
            wait_until(future.done, 5.0)
            response = future.result()
            controls.append({'command': name, 'success': response.success,
                             'elapsed_sec': round(time.monotonic() - started, 3)})
            print(f'人工控制 {name}: {response.message}', flush=True)
            if response.success != want:
                raise RuntimeError(f'{name} 返回非预期结果: {response.message}')

        wait_until(lambda: latest.get('connected') and visitor.get('stable') and
                   visitor.get('people_count') == 0 and assisting().get('can_arm') and
                   node.count_publishers('heritage/visitor/events') == 1)
        call('arm_visitor')
        wait_until(lambda: assisting().get('armed') and assisting().get('observed_empty'))
        observed_count = 3
        wait_until(lambda: latest.get('state') == 'WAITING_CONSENT' and assisting().get('can_accept'))
        if latest['is_moving'] or latest['visited'] or any(
                entry['state'] == 'NAVIGATING' for entry in latest['history']):
            raise RuntimeError('同意前不应启动导航')
        call('accept')
        wait_until(lambda: latest.get('state') == 'NAVIGATING' and
                   latest.get('target') == 'exhibit_01' and latest.get('is_moving'))
        observed_count = 2
        wait_until(lambda: latest.get('state') == 'PAUSED' and not latest.get('is_moving'))
        paused_target = latest['target']
        call('resume', False)
        observed_count = 3
        wait_until(lambda: assisting().get('can_resume'))
        # 数据恢复后仍必须保持暂停，不能自动继续运动。
        hold = time.monotonic() + 0.5
        while time.monotonic() < hold:
            rclpy.spin_once(node, timeout_sec=0.05)
            if latest['state'] != 'PAUSED' or latest['is_moving']:
                raise RuntimeError('集合后未经确认恢复运动')
        call('resume')
        wait_until(lambda: latest.get('state') == 'NAVIGATING' and latest.get('target') == paused_target)
        wait_until(lambda: latest.get('state') in ('QA', 'ERROR'), timeout=90.0)
        if latest['state'] != 'QA':
            raise RuntimeError(latest['reason'])
        call('finish_qa')
        wait_until(lambda: latest.get('state') in ('COMPLETED', 'ERROR'), timeout=60.0)
        wait_until(lambda: visitor.get('expected_count') == 0)
        route = ['entrance', *(f'exhibit_{index:02d}' for index in range(1, 6)), 'interaction_zone', 'exit']
        success = (latest['state'] == 'COMPLETED' and latest['visited'] == route and
                   not assisting().get('active') and latest['error_count'] == 1 and
                   not latest['is_moving'] and paused_target == 'exhibit_01')
        report = {'success': success, 'tour': latest, 'visitor': visitor,
                  'controls': controls, 'paused_target': paused_target,
                  'visitor_events': visitor_events, 'navigation_events': navigation_events,
                  'elapsed_sec': round(time.monotonic() - started, 3)}
        (run_dir / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"联动结果: {'通过' if success else '失败'}，访问 {len(latest['visited'])} 站，报告 {run_dir / 'report.json'}", flush=True)
        return 0 if success else 1
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=12.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3.0)
        if node is not None:
            node.destroy_node()
            rclpy.try_shutdown()
        for handle in handles:
            handle.close()


if __name__ == '__main__':
    raise SystemExit(main())
