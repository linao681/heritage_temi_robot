"""端到端：ROS2 Action 服务端 → WebSocket → 模拟 Android → 返回 ROS2。"""

import asyncio
import json
import os
from threading import Thread

import rclpy
from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from temi_interfaces.action import NavigateTo
from temi_interfaces.msg import RobotStatus
from websockets.asyncio.client import connect

from temi_bridge.ros_gateway import TemiGatewayNode
from temi_bridge.websocket_backend import WebSocketConfig, WebSocketTemiBackend


def test_ros_to_websocket_navigation_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv('ROS_LOCALHOST_ONLY', '1')
    monkeypatch.setenv('ROS_DOMAIN_ID', os.environ.get('HERITAGE_TEST_ROS_DOMAIN_ID', '229'))
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))
    rclpy.init(args=[])
    token = 'loopback-integration-token'
    backend = WebSocketTemiBackend(WebSocketConfig(port=0), token)
    gateway = TemiGatewayNode(backend, status_hz=20.0)
    client = rclpy.create_node('ws_integration_client')
    nav_client = ActionClient(client, NavigateTo, 'temi/navigate_to')
    snapshots, feedback = [], []
    client.create_subscription(RobotStatus, 'temi/robot_status', snapshots.append, 10)
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(gateway)
    executor.add_node(client)
    thread = Thread(target=executor.spin, daemon=True)
    thread.start()

    async def wait_for(predicate, timeout=3.0):
        deadline = asyncio.get_running_loop().time() + timeout
        while not predicate():
            assert asyncio.get_running_loop().time() < deadline, '等待 ROS2/WS 集成状态超时'
            await asyncio.sleep(0.01)

    async def scenario():
        async with connect(f'ws://127.0.0.1:{backend.bound_port}/temi', proxy=None,
                           additional_headers={'Authorization': f'Bearer {token}'}) as socket:
            async def send(value):
                await socket.send(json.dumps(value))

            async def receive():
                return json.loads(await asyncio.wait_for(socket.recv(), 2.0))

            await send({'type': 'hello', 'protocol_version': 1})
            assert (await receive())['type'] == 'hello_ack'
            assert (await receive())['type'] == 'state_request'
            state = {'type': 'state', 'connected': True, 'battery_percentage': 80.0,
                     'x': 0.0, 'y': 0.0, 'yaw': 0.0, 'navigation_status': 'idle',
                     'current_location': 'entrance', 'is_moving': False,
                     'error_message': '', 'frame_id': 'temi_map'}
            await send(state)
            await wait_for(lambda: snapshots and snapshots[-1].connected)
            assert nav_client.wait_for_server(timeout_sec=2.0)
            goal_future = nav_client.send_goal_async(NavigateTo.Goal(location='exhibit_01', timeout_sec=3.0),
                                                      feedback_callback=lambda entry: feedback.append(entry.feedback.status))
            await wait_for(goal_future.done)
            goal = goal_future.result()
            assert goal.accepted
            command = await receive()
            assert command['id'] == bytes(goal.goal_id.uuid).hex()
            assert command['command'] == 'navigate' and command['location'] == 'exhibit_01'
            await send({'type': 'ack', 'id': command['id'], 'accepted': True, 'message': 'ack'})
            await send({'type': 'event', 'event': 'navigation_status', 'id': command['id'],
                        'status': 'going', 'description': 'mock Android movement'})
            await send({**state, 'x': 0.5, 'is_moving': True, 'navigation_status': 'going'})
            await wait_for(lambda: snapshots[-1].x == 0.5 and 'going' in feedback)
            await send({'type': 'event', 'event': 'navigation_status', 'id': command['id'],
                        'status': 'complete', 'description': 'arrived'})
            result_future = goal.get_result_async()
            await wait_for(result_future.done)
            assert result_future.result().status == GoalStatus.STATUS_SUCCEEDED
            assert result_future.result().result.success
            await wait_for(lambda: snapshots[-1].current_location == 'exhibit_01')

    try:
        asyncio.run(scenario())
    finally:
        gateway.close()
        executor.shutdown(timeout_sec=5.0)
        thread.join(timeout=5.0)
        nav_client.destroy()
        client.destroy_node()
        gateway.destroy_node()
        rclpy.try_shutdown()
