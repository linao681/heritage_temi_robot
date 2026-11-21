"""Pair YOLOX boxes with a stamped, calibrated depth image."""
import copy
import time

from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from temi_interfaces.msg import PersonDetectionArray

from .depth_association import associate_person_depth


def _stamp_ns(stamp):
    return stamp.sec * 1_000_000_000 + stamp.nanosec


class DepthAssociationNode(Node):
    def __init__(self, simulation_mode=False):
        super().__init__('person_depth_association')
        self.declare_parameter('simulation_mode', simulation_mode)
        self.declare_parameter('max_pair_delta_sec', 0.15)
        self.declare_parameter('max_depth_age_sec', 0.5)
        self._simulation_mode = self.get_parameter('simulation_mode').value
        self._max_pair_delta = self.get_parameter('max_pair_delta_sec').value
        self._max_depth_age = self.get_parameter('max_depth_age_sec').value
        self._bridge = CvBridge()
        self._detections = None
        self._depth = None
        self._camera_info = None
        self._publisher = self.create_publisher(
            PersonDetectionArray, 'heritage/visitor/person_detections', 10)
        self.create_subscription(PersonDetectionArray,
            'heritage/visitor/person_detections/raw', self._on_detections, 5)
        self.create_subscription(Image, 'camera/depth/image_raw', self._on_depth, 5)
        self.create_subscription(CameraInfo, 'camera/depth/camera_info', self._on_camera_info, 5)

    def _on_detections(self, message):
        self._detections = (message, time.monotonic())
        self._associate()

    def _on_depth(self, message):
        self._depth = (message, time.monotonic())
        self._associate()

    def _on_camera_info(self, message):
        self._camera_info = message
        self._associate()

    def _associate(self):
        if self._detections is None or self._depth is None or self._camera_info is None:
            return
        raw, received = self._detections
        image, depth_received = self._depth
        raw_stamp, depth_stamp = _stamp_ns(raw.header.stamp), _stamp_ns(image.header.stamp)
        if (raw_stamp <= 0 or depth_stamp <= 0 or
                abs(raw_stamp - depth_stamp) / 1e9 > self._max_pair_delta or
                time.monotonic() - depth_received > self._max_depth_age):
            return
        if raw.header.frame_id and image.header.frame_id and raw.header.frame_id.split('/')[0] != image.header.frame_id.split('/')[0]:
            return
        info = self._camera_info
        fx, fy, cx, cy = info.k[0], info.k[4], info.k[2], info.k[5]
        try:
            depth = self._bridge.imgmsg_to_cv2(image, desired_encoding='passthrough')
            if image.encoding == '16UC1':
                depth = depth.astype('float32') / 1000.0
            elif image.encoding == '32FC1':
                depth = depth.astype('float32', copy=False)
            else:
                raise ValueError(f'不支持的深度编码：{image.encoding}')
            result = copy.deepcopy(raw)
            result.source = 'gazebo_rgbd' if self._simulation_mode else 'temi_rgbd'
            result.sample_age_sec = max(0.0, time.monotonic() - min(received, depth_received))
            for detection in result.detections:
                distance = associate_person_depth(
                    (detection.x_min, detection.y_min, detection.x_max, detection.y_max),
                    depth, fx=fx, fy=fy, cx=cx, cy=cy)
                detection.distance_valid = distance is not None
                detection.distance_m = float(distance or 0.0)
            distances = [item.distance_m for item in result.detections if item.distance_valid]
            result.person_distance_valid = bool(result.valid and result.detections and
                len(distances) == len(result.detections))
            result.nearest_person_m = min(distances) if result.person_distance_valid else 0.0
            # Preserve only a calibrated upstream occupancy value; never infer density from box size.
            result.crowd_density_valid = bool(result.valid and result.crowd_density_valid and
                isinstance(result.crowd_density, (int, float)) and
                0.0 <= result.crowd_density <= 1.0)
            if not result.crowd_density_valid:
                result.crowd_density = 0.0
            if not result.person_distance_valid:
                result.error = '至少一名检测人员没有足够有效深度像素'
            self._publisher.publish(result)
        except (ValueError, TypeError, RuntimeError) as error:
            result = copy.deepcopy(raw)
            result.valid = False
            result.person_distance_valid = False
            result.nearest_person_m = 0.0
            result.crowd_density_valid = False
            result.error = f'深度图关联失败：{error}'
            self._publisher.publish(result)


def main(args=None):
    import rclpy
    rclpy.init(args=args)
    node = DepthAssociationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
