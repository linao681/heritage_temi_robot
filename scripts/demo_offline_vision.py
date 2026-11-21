"""实际公开视频计数→ROS2 离线感知；不启动任何机器人控制节点。"""

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import time

import rclpy
from std_msgs.msg import Int32, String
import yaml


ROOT = Path(__file__).resolve().parents[1]


def main():
    run_dir = ROOT / 'docs/runs' / datetime.now().strftime('offline-vision-%Y%m%d-%H%M%S-%f')
    run_dir.mkdir(parents=True)
    os.environ.update(ROS_LOCALHOST_ONLY='1', ROS_DOMAIN_ID='221', ROS_LOG_DIR=str(run_dir / 'ros-logs'))
    settings = yaml.safe_load((ROOT / 'config/system.yaml').read_text(encoding='utf-8'))
    settings['visitor_perception']['count_source'] = 'offline_video'
    settings['tour']['visitor_assist_enabled'] = False
    config = run_dir / 'system_offline.yaml'
    config.write_text(yaml.safe_dump(settings, allow_unicode=True), encoding='utf-8')
    executables = ROOT / 'ros2_ws/install/visitor_perception/lib/visitor_perception'
    predictions = run_dir / 'predictions.json'
    processes, handles = [], []
    states, events, counts = [], [], []
    latest = {}
    node = None
    start = time.monotonic()

    def launch(name, args):
        handle = (run_dir / f'{name}.log').open('w', encoding='utf-8')
        handles.append(handle)
        process = subprocess.Popen([str(executables / name), *map(str, args)], cwd=ROOT,
                                   stdout=handle, stderr=subprocess.STDOUT)
        processes.append(process)
        return process

    def receive_state(msg):
        nonlocal latest
        value = json.loads(msg.data)
        if value != latest:
            states.append({'elapsed_sec': round(time.monotonic() - start, 3), **value})
            print(f'感知状态: {value}', flush=True)
        latest = value

    def receive_event(msg):
        value = json.loads(msg.data)
        events.append({'elapsed_sec': round(time.monotonic() - start, 3), **value})
        print(f"感知事件: {value['event']}", flush=True)

    def receive_count(msg):
        counts.append(msg.data)
        print(f'视频匿名人数: {msg.data}', flush=True)

    def wait_until(predicate, timeout=8.0):
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= deadline or monitor.poll() is not None:
                raise RuntimeError(f'离线计数回环超时或监测进程已退出：{run_dir}')
            rclpy.spin_once(node, timeout_sec=.05)

    try:
        monitor = launch('visitor_perception', ['--config', config])
        rclpy.init(args=[])
        node = rclpy.create_node('offline_vision_demo_observer')
        node.create_subscription(Int32, 'heritage/visitor/vision_count', receive_count, 30)
        node.create_subscription(String, 'heritage/visitor/status', receive_state, 50)
        node.create_subscription(String, 'heritage/visitor/events', receive_event, 30)
        wait_until(lambda: latest.get('source') == 'offline_video' and
                   node.count_publishers('heritage/visitor/events') == 1)
        assert not latest['valid'] and latest['people_count'] is None
        counter = launch('offline_video_count', [
            '--video', ROOT / 'assets/vision/vtest.avi',
            '--model', ROOT / 'assets/vision/object_detection_yolox_2022nov.onnx',
            '--interval', '0.5', '--limit', '20', '--output', predictions, '--publish'])
        wait_until(lambda: counter.poll() is not None, 60.0)
        if counter.returncode != 0:
            raise RuntimeError(f'视觉推理失败: {run_dir / "offline_video_count.log"}')
        result = json.loads(predictions.read_text(encoding='utf-8'))
        expected = [sample['people_count'] for sample in result['samples']]
        wait_until(lambda: len(counts) >= len(expected))
        wait_until(lambda: not latest.get('valid') and latest.get('people_count') is None and
                   any(event['event'] == 'data_stale' for event in events))
        success = bool(result['success'] and len(expected) == 20 and counts == expected and
                       any(state['valid'] for state in states) and
                       all(state['source'] == 'offline_video' for state in states) and
                       not any(event['event'] == 'departure' for event in events))
        report = {'success': success, 'source': 'offline_video', 'counts': counts,
                  'states': states, 'events': events, 'final_status': latest,
                  'prediction_report': predictions.name,
                  'elapsed_sec': round(time.monotonic() - start, 3)}
        (run_dir / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"实际视频 ROS2 回环: {'通过' if success else '失败'}，收到 {len(counts)} 个匿名计数，报告 {run_dir / 'report.json'}", flush=True)
        return 0 if success else 1
    finally:
        if node is not None:
            node.destroy_node()
            rclpy.try_shutdown()
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
        for handle in handles:
            handle.close()


if __name__ == '__main__':
    raise SystemExit(main())
