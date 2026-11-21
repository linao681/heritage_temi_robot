"""ROS2 自定义接口的实际 Python 类型和通信验收测试。"""

import time

from rclpy.serialization import deserialize_message, serialize_message
from std_msgs.msg import Header


def assert_roundtrip(message):
    """确认生成的 Python 类型支持真实 ROS2 序列化与反序列化。"""
    assert deserialize_message(serialize_message(message), type(message)) == message


def test_robot_status_schema_and_roundtrip():
    from temi_interfaces.msg import RobotStatus

    assert RobotStatus.get_fields_and_field_types() == {
        'header': 'std_msgs/Header', 'connected': 'boolean',
        'battery_percentage': 'float', 'x': 'double', 'y': 'double', 'yaw': 'double',
        'navigation_status': 'string', 'current_location': 'string',
        'is_moving': 'boolean', 'error_message': 'string',
    }
    assert RobotStatus().battery_percentage == -1.0
    message = RobotStatus(
        header=Header(frame_id='mock_map'), connected=True, battery_percentage=75.5,
        x=1.25, y=2.5, yaw=0.5, navigation_status='going',
        current_location='exhibit_01', is_moving=True, error_message='',
    )
    assert isinstance(message.header, Header)
    assert_roundtrip(message)


def test_navigation_status_schema_and_roundtrip():
    from temi_interfaces.msg import NavigationStatus

    assert NavigationStatus.get_fields_and_field_types() == {
        'header': 'std_msgs/Header', 'task_id': 'string', 'target': 'string',
        'status': 'string', 'description': 'string',
    }
    assert_roundtrip(NavigationStatus(
        header=Header(frame_id='mock_map'), task_id='task_001',
        target='exhibit_01', status='complete', description='抵达展区一',
    ))


def test_perception_interfaces_roundtrip_without_inventing_invalid_distances():
    from temi_interfaces.msg import PerceptionInput, PersonDetection, PersonDetectionArray

    detection = PersonDetection(x_min=0.125, y_min=0.25, x_max=0.5, y_max=0.75,
                                confidence=1.0, distance_valid=False, distance_m=0.0)
    people = PersonDetectionArray(header=Header(frame_id='camera_color_optical_frame'),
                                  source='temi_rgb', valid=True, people_count=1,
                                  detections=[detection], person_distance_valid=False,
                                  crowd_density_valid=False)
    fused = PerceptionInput(header=Header(frame_id='base_link'), source='temi_sensor_fusion',
                            data_sources=['camera', 'temi_rgbd', 'temi_lidar'],
                            sample_timestamp_monotonic_sec=12.5, sample_age_sec=0.0,
                            valid=False, error='人员距离无效', person_distance_valid=False,
                            nearest_person_m=0.0, obstacle_distance_valid=True,
                            obstacle_distance_m=1.0, safety_stop_valid=False, safety_stop=True)

    assert_roundtrip(detection)
    assert_roundtrip(people)
    assert_roundtrip(fused)


def test_navigate_to_goal_result_and_feedback():
    from temi_interfaces.action import NavigateTo

    assert NavigateTo.Goal.get_fields_and_field_types() == {
        'location': 'string', 'timeout_sec': 'double',
    }
    assert NavigateTo.Result.get_fields_and_field_types() == {
        'success': 'boolean', 'message': 'string',
    }
    assert NavigateTo.Feedback.get_fields_and_field_types() == {
        'status': 'string', 'description': 'string',
    }
    assert_roundtrip(NavigateTo.Goal(location='exhibit_01', timeout_sec=15.0))
    assert_roundtrip(NavigateTo.Result(success=True, message='完成'))
    assert_roundtrip(NavigateTo.Feedback(status='going', description='导航中'))


def test_speak_goal_result_and_feedback():
    from temi_interfaces.action import Speak

    assert Speak.Goal.get_fields_and_field_types() == {'text': 'string'}
    assert Speak.Result.get_fields_and_field_types() == {'success': 'boolean', 'message': 'string'}
    assert Speak.Feedback.get_fields_and_field_types() == {'status': 'string'}
    assert_roundtrip(Speak.Goal(text='欢迎来到潮汕非遗文化展厅'))
    assert_roundtrip(Speak.Result(success=True, message='播报完成'))
    assert_roundtrip(Speak.Feedback(status='started'))


def test_stop_robot_request_and_response():
    from temi_interfaces.srv import StopRobot

    assert StopRobot.Request.get_fields_and_field_types() == {'stop': 'boolean'}
    assert StopRobot.Response.get_fields_and_field_types() == {
        'success': 'boolean', 'message': 'string',
    }
    assert_roundtrip(StopRobot.Request(stop=True))
    assert_roundtrip(StopRobot.Response(success=True, message='运动已停止'))


def test_ros_node_publishes_and_receives_custom_message(monkeypatch, tmp_path):
    """创建真实 ROS2 节点和通信实体，确认类型支持可用。"""
    # 测试自身也必须限制通信范围，避免使用开发者的日常 ROS Domain。
    monkeypatch.setenv('ROS_LOCALHOST_ONLY', '1')
    monkeypatch.setenv('ROS_DOMAIN_ID', '231')
    monkeypatch.setenv('ROS_LOG_DIR', str(tmp_path))

    import rclpy
    from rclpy.action import ActionClient
    from temi_interfaces.action import NavigateTo, Speak
    from temi_interfaces.msg import RobotStatus, NavigationStatus
    from temi_interfaces.srv import StopRobot

    rclpy.init(args=[])
    node = rclpy.create_node('temi_interface_probe')
    try:
        received = []
        publisher = node.create_publisher(RobotStatus, 'interface_probe/status', 10)
        node.create_subscription(RobotStatus, 'interface_probe/status', received.append, 10)
        node.create_publisher(NavigationStatus, 'interface_probe/navigation', 10)
        nav_client = ActionClient(node, NavigateTo, 'interface_probe/navigate')
        speak_client = ActionClient(node, Speak, 'interface_probe/speak')
        node.create_client(StopRobot, 'interface_probe/stop')
        try:
            message = RobotStatus(connected=True, current_location='exhibit_01')
            deadline = time.monotonic() + 5.0
            while not received and time.monotonic() < deadline:
                publisher.publish(message)
                rclpy.spin_once(node, timeout_sec=0.1)
            assert received, '未在超时前收到 RobotStatus'
            assert received[0] == message
        finally:
            nav_client.destroy()
            speak_client.destroy()
    finally:
        node.destroy_node()
        rclpy.shutdown()
