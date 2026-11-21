"""从已安装入口启动独立 ROS2 进程，验证通信和退出生命周期。"""

import os
from pathlib import Path
import signal
import subprocess
import time

import rclpy
from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient
from temi_interfaces.action import NavigateTo, Speak
from temi_interfaces.msg import RobotStatus
from temi_interfaces.srv import StopRobot


def test_gateway_process_commands_and_sigterm_shutdown(monkeypatch, tmp_path):
    monkeypatch.setenv('ROS_LOCALHOST_ONLY', '1')
    monkeypatch.setenv('ROS_DOMAIN_ID', '228')
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    root = Path(__file__).resolve().parents[1]
    entrypoint = root / 'ros2_ws/install/temi_bridge/lib/temi_bridge/temi_gateway'
    log = tmp_path / 'gateway.log'
    with log.open('w') as output:
        process = subprocess.Popen([str(entrypoint), '--config', str(root / 'config/system.yaml'),
                                    '--backend', 'mock'], stdout=output, stderr=subprocess.STDOUT,
                                   env=os.environ.copy())
        rclpy.init(args=[])
        node = rclpy.create_node('gateway_cli_client')
        navigation = ActionClient(node, NavigateTo, 'temi/navigate_to')
        speech = ActionClient(node, Speak, 'temi/speak')
        stop = node.create_client(StopRobot, 'temi/stop')
        snapshots = []
        node.create_subscription(RobotStatus, 'temi/robot_status', snapshots.append, 10)

        def wait_until(predicate, timeout=5.0):
            deadline = time.monotonic() + timeout
            while not predicate():
                assert time.monotonic() < deadline, log.read_text()
                rclpy.spin_once(node, timeout_sec=0.05)

        def wait_future(future):
            wait_until(future.done)
            return future.result()

        def start_navigation(location):
            goal = wait_future(navigation.send_goal_async(NavigateTo.Goal(location=location, timeout_sec=10.0)))
            assert goal.accepted
            wait_until(lambda: snapshots and snapshots[-1].is_moving)
            return goal

        try:
            assert navigation.wait_for_server(timeout_sec=5.0), log.read_text()
            assert speech.wait_for_server(timeout_sec=5.0)
            assert stop.wait_for_service(timeout_sec=5.0)
            wait_until(lambda: snapshots and snapshots[-1].connected)
            moving_goal = start_navigation('exhibit_01')
            assert wait_future(stop.call_async(StopRobot.Request(stop=True))).success
            result = wait_future(moving_goal.get_result_async())
            assert result.status == GoalStatus.STATUS_ABORTED and not result.result.success
            spoken = wait_future(speech.send_goal_async(Speak.Goal(text='跨进程播报')))
            assert spoken.accepted and wait_future(spoken.get_result_async()).result.success
            start_navigation('exhibit_03')
            process.send_signal(signal.SIGTERM)
            assert process.wait(timeout=8.0) == 0, log.read_text()
            assert 'Gateway started in mock mode' in log.read_text()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2.0)
            navigation.destroy()
            speech.destroy()
            node.destroy_node()
            rclpy.try_shutdown()
