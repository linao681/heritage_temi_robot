"""ROS adapter for anonymous tracks and conservative team visibility."""
import json
import math

from rclpy.node import Node
from std_msgs.msg import Int32, String
from temi_interfaces.msg import PersonDetectionArray

from .person_tracker import PersonTracker
from .team_observer import TeamObserver


def stamp_ns(header):
    return header.stamp.sec * 1_000_000_000 + header.stamp.nanosec


class TeamObserverNode(Node):
    def __init__(self):
        super().__init__('anonymous_team_observer')
        self.declare_parameter('detections_topic', 'heritage/visitor/person_detections')
        self.declare_parameter('expected_count_topic', 'heritage/visitor/expected_count')
        self.declare_parameter('coverage', 'forward_only')
        self.declare_parameter('max_missed_sec', 0.5)
        self.declare_parameter('max_sample_age_sec', 0.5)
        self.coverage = str(self.get_parameter('coverage').value)
        self.expected_count = 0
        self.tracker = PersonTracker(max_missed_sec=float(
            self.get_parameter('max_missed_sec').value))
        self.observer = TeamObserver(max_age_sec=float(
            self.get_parameter('max_sample_age_sec').value))
        self.tracks_pub = self.create_publisher(String, 'heritage/visitor/tracks', 10)
        self.team_pub = self.create_publisher(String, 'heritage/visitor/team_observation', 10)
        self.create_subscription(Int32, self.get_parameter('expected_count_topic').value,
                                 self._on_expected_count, 10)
        self.create_subscription(PersonDetectionArray,
                                 self.get_parameter('detections_topic').value,
                                 self._on_detections, 10)

    def _on_expected_count(self, message):
        self.expected_count = max(0, int(message.data))

    def _on_detections(self, message):
        stamp = stamp_ns(message.header)
        valid_age = (math.isfinite(message.sample_age_sec) and
                     0 <= message.sample_age_sec <= float(
                         self.get_parameter('max_sample_age_sec').value))
        valid = bool(message.valid and valid_age and stamp > 0)
        if valid:
            detections = [{'bbox': (item.x_min, item.y_min, item.x_max, item.y_max),
                           'confidence': item.confidence,
                           'distance_valid': item.distance_valid,
                           'distance_m': item.distance_m}
                          for item in message.detections]
            try:
                tracks = self.tracker.update(detections, stamp, message.header.frame_id)
            except ValueError as error:
                self.get_logger().warning(f'rejected non-monotonic vision sample: {error}')
                valid = False
                tracks = []
        else:
            tracks = []
        serialized_tracks = [{
            'track_id': item.track_id,
            'bbox': list(item.bbox),
            'confidence': item.confidence,
            'observation_state': item.observation_state,
            'last_seen_stamp_ns': item.last_seen_stamp_ns,
            'frame_id': item.frame_id,
            'source': item.source,
            'distance_valid': item.distance_valid,
            'distance_m': item.distance_m,
        } for item in tracks]
        team = self.observer.observe(tracks, stamp, valid, self.coverage,
                                     self.expected_count, stamp if valid else None)
        team['frame_id'] = message.header.frame_id
        team['sample_age_sec'] = message.sample_age_sec
        tracks_json = json.dumps({'schema_version': 1, 'stamp_ns': stamp,
                                  'source': 'vision_tracker', 'valid': valid,
                                  'tracks': serialized_tracks}, allow_nan=False)
        self.tracks_pub.publish(String(data=tracks_json))
        self.team_pub.publish(String(data=json.dumps(team, allow_nan=False)))


def main(args=None):
    import rclpy
    from .ros_shutdown import spin_node
    rclpy.init(args=args)
    node = TeamObserverNode()
    spin_node(rclpy, node)
