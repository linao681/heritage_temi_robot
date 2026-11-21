"""启动独立 Mock Gateway + Tour Manager，并用真实 ROS2 服务完成八站导览。"""

import argparse
import json
import os
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path

import rclpy
from std_msgs.msg import String
from std_srvs.srv import Trigger
from temi_interfaces.msg import NavigationStatus
from temi_interfaces.srv import AskHeritage, SubmitQuestion


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--question', help='在互动区提交一次知识库问题')
    options = parser.parse_args()
    # 仅本次演示进程生效；绝不启动 WebSocket/实体后端。
    run_dir = ROOT / 'docs' / 'runs' / datetime.now().strftime('mock-tour-%Y%m%d-%H%M%S-%f')
    run_dir.mkdir(parents=True)
    os.environ['ROS_LOCALHOST_ONLY'] = '1'
    os.environ['ROS_DOMAIN_ID'] = '226'
    os.environ['ROS_LOG_DIR'] = str(run_dir / 'ros-logs')
    gateway_exe = ROOT / 'ros2_ws/install/temi_bridge/lib/temi_bridge/temi_gateway'
    tour_exe = ROOT / 'ros2_ws/install/heritage_tour_manager/lib/heritage_tour_manager/tour_manager'
    system = ROOT / 'config/system.yaml'
    exhibits = ROOT / 'config/exhibits.yaml'
    processes = []
    knowledge_process = None
    handles = []
    node = None
    latest = {}
    events = []
    printed = 0

    def launch(executable, arguments, log_name):
        handle = (run_dir / log_name).open('w', encoding='utf-8')
        handles.append(handle)
        process = subprocess.Popen([str(executable), *map(str, arguments)], cwd=ROOT,
                                   stdout=handle, stderr=subprocess.STDOUT, env=os.environ.copy())
        processes.append(process)
        return process

    def receive_status(message):
        nonlocal latest, printed
        latest = json.loads(message.data)
        history = latest['history']
        for entry in history[printed:]:
            print(f"{entry['elapsed_sec']:7.3f}s {entry['state']:16} {entry['reason']}", flush=True)
        printed = len(history)

    def receive_navigation(message):
        events.append({'task_id': message.task_id, 'target': message.target,
                       'status': message.status, 'description': message.description})

    def wait_until(predicate, timeout=30.0):
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= deadline or any(proc.poll() is not None for proc in processes):
                raise RuntimeError('导览等待超时或进程已退出，请检查运行日志')
            rclpy.spin_once(node, timeout_sec=0.05)

    try:
        launch(gateway_exe, ['--config', system, '--backend', 'mock'], 'gateway.log')
        if options.question is not None:
            knowledge_process = launch(ROOT / 'ros2_ws/install/heritage_knowledge/lib/heritage_knowledge/knowledge_node',
                                       ['--config', ROOT / 'config/knowledge.yaml'], 'knowledge.log')
        launch(tour_exe, ['--config', system, '--exhibits', exhibits], 'tour_manager.log')
        rclpy.init(args=[])
        node = rclpy.create_node('mock_tour_demo_client')
        node.create_subscription(String, 'heritage/tour/status', receive_status, 50)
        node.create_subscription(NavigationStatus, 'temi/navigation_status', receive_navigation, 50)
        services = {name: node.create_client(Trigger, 'heritage/tour/' + name)
                    for name in ('start', 'accept', 'finish_qa')}

        def call(name):
            if not services[name].wait_for_service(timeout_sec=5.0):
                raise RuntimeError(f'{name} 服务未就绪')
            future = services[name].call_async(Trigger.Request())
            wait_until(future.done, 5.0)
            if not future.result().success:
                raise RuntimeError(future.result().message)

        wait_until(lambda: latest.get('connected', False), 10.0)
        call('start')
        wait_until(lambda: latest.get('state') == 'WAITING_CONSENT', 30.0)
        call('accept')
        wait_until(lambda: latest.get('state') == 'QA', 90.0)
        if options.question is None:
            call('finish_qa')
        else:
            knowledge = node.create_client(AskHeritage, 'heritage/knowledge/ask')
            submit = node.create_client(SubmitQuestion, 'heritage/tour/ask')
            if not knowledge.wait_for_service(timeout_sec=5) or not submit.wait_for_service(timeout_sec=5):
                raise RuntimeError('知识问答服务未就绪')
            future = submit.call_async(SubmitQuestion.Request(question=options.question, level='basic'))
            wait_until(future.done, 5)
            if not future.result().accepted:
                raise RuntimeError(future.result().message)
        wait_until(lambda: latest.get('state') in ('COMPLETED', 'ERROR'), 60.0)
        success = latest['state'] == 'COMPLETED' and latest['outcome'] == 'completed'
        if options.question is not None:
            success = success and bool((latest.get('qa_result') or {}).get('spoken'))
        report = {'success': success, 'tour': latest, 'navigation_events': events}
        (run_dir / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"最终结果: {latest['outcome']}，访问 {len(latest['visited'])} 站，耗时 {latest['elapsed_sec']}s，异常 {latest['error_count']} 次")
        print(f'运行报告: {run_dir / "report.json"}', flush=True)
        return 0 if success else 1
    finally:
        # 先停导览进程，让 Gateway 仍能处理取消/STOP；只停止本脚本启动的进程。
        for process in reversed(processes):
            if process.poll() is None:
                process.send_signal(signal.SIGINT if process is knowledge_process else signal.SIGTERM)
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
