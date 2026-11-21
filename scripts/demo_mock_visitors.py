"""独立游客感知进程演示：仅发布模拟人数，保留实际 ROS2 事件。"""

import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime

import rclpy
from std_msgs.msg import Int32, String
from visitor_perception.visitor_monitor import VisitorConfig

ROOT = Path(__file__).resolve().parents[1]


def main():
    run_dir = ROOT / 'docs' / 'runs' / datetime.now().strftime('mock-visitors-%Y%m%d-%H%M%S-%f')
    run_dir.mkdir(parents=True)
    os.environ.update(ROS_LOCALHOST_ONLY='1', ROS_DOMAIN_ID='224',
                      ROS_LOG_DIR=str(run_dir / 'ros-logs'))
    executable = ROOT / 'ros2_ws/install/visitor_perception/lib/visitor_perception/visitor_perception'
    system = ROOT / 'config/system.yaml'
    config = VisitorConfig.from_yaml(system)
    states, events = [], []
    start = time.monotonic()
    latest = {}
    node = None

    with (run_dir / 'visitor_perception.log').open('w', encoding='utf-8') as output:
        process = subprocess.Popen([str(executable), '--config', str(system)],
                                   cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
        try:
            rclpy.init(args=[])
            node = rclpy.create_node('mock_visitor_demo_client')
            counts = node.create_publisher(Int32, 'heritage/visitor/count', 10)
            expected = node.create_publisher(Int32, 'heritage/visitor/expected_count', 10)

            def receive_status(message):
                nonlocal latest
                status = json.loads(message.data)
                if status != latest:
                    states.append({'elapsed_sec': round(time.monotonic() - start, 3), **status})
                    print(f'状态: {status}', flush=True)
                latest = status

            def receive_event(message):
                event = {'elapsed_sec': round(time.monotonic() - start, 3), **json.loads(message.data)}
                events.append(event)
                print(f"事件: {event['event']}", flush=True)

            node.create_subscription(String, 'heritage/visitor/status', receive_status, 30)
            node.create_subscription(String, 'heritage/visitor/events', receive_event, 30)

            def wait_until(predicate, timeout=5.0):
                deadline = time.monotonic() + timeout
                while not predicate():
                    if time.monotonic() >= deadline or process.poll() is not None:
                        raise RuntimeError(f'等待感知状态失败: {latest}，查看 {run_dir}')
                    rclpy.spin_once(node, timeout_sec=0.05)

            def observe(count):
                for _ in range(config.stable_samples):
                    counts.publish(Int32(data=count))
                    time.sleep(min(0.02, config.stale_timeout_sec / 4))
                wait_until(lambda: latest.get('valid') and latest.get('people_count') == count)

            def set_group(count):
                expected.publish(Int32(data=count))
                wait_until(lambda: latest.get('expected_count') == count)

            def event_names():
                return [event['event'] for event in events]

            wait_until(lambda: latest and counts.get_subscription_count() == 1 and
                       expected.get_subscription_count() == 1 and
                       node.count_publishers('heritage/visitor/events') == 1)
            observe(0)
            observe(3)
            wait_until(lambda: 'arrival' in event_names())
            set_group(3)
            observe(3)
            wait_until(lambda: latest.get('group_state') == 'following')
            observe(2)
            wait_until(lambda: 'visitor_lost' in event_names() and latest.get('group_state') == 'lost')
            observe(3)
            wait_until(lambda: 'regrouped' in event_names() and latest.get('group_state') == 'following')
            set_group(0)
            observe(0)
            wait_until(lambda: 'departure' in event_names())
            wait_until(lambda: 'data_stale' in event_names() and not latest.get('valid'),
                       timeout=config.stale_timeout_sec + 3.0)
            observe(0)
            wait_until(lambda: 'data_restored' in event_names())
            expected_events = ['arrival', 'visitor_lost', 'regrouped', 'departure',
                               'data_stale', 'data_restored']
            success = event_names() == expected_events and latest['people_count'] == 0
            report = {'success': success, 'final_status': latest, 'states': states, 'events': events,
                      'elapsed_sec': round(time.monotonic() - start, 3)}
            (run_dir / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                                 encoding='utf-8')
            print(f"最终结果: {'通过' if success else '失败'}，事件数 {len(events)}，报告 {run_dir / 'report.json'}")
            return 0 if success else 1
        finally:
            if node is not None:
                node.destroy_node()
                rclpy.try_shutdown()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3.0)


if __name__ == '__main__':
    raise SystemExit(main())
