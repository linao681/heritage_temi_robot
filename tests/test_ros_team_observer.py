import json
import sys
import time
from pathlib import Path
from threading import Thread

import rclpy
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import Int32, String
from temi_interfaces.msg import PersonDetection, PersonDetectionArray

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                        'ros2_ws/src/visitor_perception'))

from visitor_perception.ros_team_observer import TeamObserverNode


def test_observer_publishes_anonymous_tracks_and_conservative_team_state():
    owns_context = not rclpy.ok()
    if owns_context:
        rclpy.init(args=[])
    node = TeamObserverNode()
    probe = rclpy.create_node('team_observer_probe')
    received = {}
    probe.create_subscription(String, 'heritage/visitor/tracks',
                              lambda message: received.update(tracks=json.loads(message.data)), 10)
    probe.create_subscription(String, 'heritage/visitor/team_observation',
                              lambda message: received.update(team=json.loads(message.data)), 10)
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    executor.add_node(probe)
    thread = Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        node._on_expected_count(Int32(data=3))
        message = PersonDetectionArray()
        message.header.stamp.sec = int(time.time())
        message.header.frame_id = 'depth_camera_optical_frame'
        message.source = 'depth_association'
        message.sample_age_sec = 0.01
        message.valid = True
        message.people_count = 3
        for left in (0.1, 0.4, 0.7):
            item = PersonDetection()
            item.x_min, item.y_min = left, 0.1
            item.x_max, item.y_max = left + 0.15, 0.8
            item.confidence = 0.9
            message.detections.append(item)
        node._on_detections(message)
        deadline = time.monotonic() + 2.0
        while len(received) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert received['tracks']['source'] == 'vision_tracker'
        assert len(received['tracks']['tracks']) == 3
        assert received['team']['source'] == 'vision_tracker'
        assert received['team']['observation_state'] == 'UNKNOWN'
        assert received['team']['requires_manual_confirmation'] is True
    finally:
        executor.shutdown(timeout_sec=2.0)
        thread.join(timeout=2.0)
        node.destroy_node()
        probe.destroy_node()
        if owns_context:
            rclpy.shutdown()
