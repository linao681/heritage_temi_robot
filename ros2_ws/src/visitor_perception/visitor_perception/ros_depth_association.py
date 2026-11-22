"""Pair YOLOX boxes with a stamped, calibrated depth image."""
import copy
from collections import deque
import math
import time

from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from temi_interfaces.msg import PersonDetectionArray

from .depth_association import associate_person_depth


def _stamp_ns(stamp):
    return stamp.sec * 1_000_000_000 + stamp.nanosec


def nearest_stamped_sample(samples, target_stamp_ns, max_delta_sec):
    if target_stamp_ns <= 0:
        return None
    candidates = []
    for sample in samples:
        message, _received = sample
        stamp = _stamp_ns(message.header.stamp)
        if stamp > 0:
            candidates.append((abs(stamp - target_stamp_ns) / 1e9, sample))
    if not candidates:
        return None
    delta, sample = min(candidates, key=lambda item: item[0])
    return sample if delta <= max_delta_sec else None


def _calibration_error(rgb_info, depth_info, raw, image):
    frames = (raw.header.frame_id, rgb_info.header.frame_id,
              image.header.frame_id, depth_info.header.frame_id)
    if not all(frames) or len(set(frames)) != 1:
        return 'RGB 与深度图坐标系不同，未做投影变换'
    if ((rgb_info.width, rgb_info.height) != (depth_info.width, depth_info.height) or
            (image.width, image.height) != (depth_info.width, depth_info.height)):
        return 'RGB、深度图和 CameraInfo 分辨率不一致'
    for info in (rgb_info, depth_info):
        if (len(info.k) != 9 or not all(math.isfinite(value) for value in info.k) or
                info.k[0] <= 0 or info.k[4] <= 0):
            return 'CameraInfo 内参无效'
    same_k = all(math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5)
                 for a, b in zip(rgb_info.k, depth_info.k))
    same_d = (rgb_info.distortion_model == depth_info.distortion_model and
              len(rgb_info.d) == len(depth_info.d) and
              all(math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5)
                  for a, b in zip(rgb_info.d, depth_info.d)))
    if not same_k or not same_d:
        return 'RGB 与深度相机内参/畸变不一致，未做像素投影'
    return ''


class DepthAssociationNode(Node):
    def __init__(self, simulation_mode=False):
        super().__init__('person_depth_association')
        self.declare_parameter('simulation_mode', simulation_mode)
        self.declare_parameter('max_pair_delta_sec', 0.15)
        self.declare_parameter('max_depth_age_sec', 0.5)
        self.declare_parameter('min_detection_confidence', 0.5)
        self.declare_parameter('rgb_camera_info_topic', 'depth_camera/camera_info')
        self.declare_parameter('depth_camera_info_topic', 'camera/depth/camera_info')
        self._simulation_mode = self.get_parameter('simulation_mode').value
        self._max_pair_delta = self.get_parameter('max_pair_delta_sec').value
        self._max_depth_age = self.get_parameter('max_depth_age_sec').value
        self._min_detection_confidence = self.get_parameter('min_detection_confidence').value
        self._bridge = CvBridge()
        self._detections = deque(maxlen=20)
        self._depth = deque(maxlen=20)
        self._rgb_camera_info = deque(maxlen=20)
        self._depth_camera_info = deque(maxlen=20)
        self._publisher = self.create_publisher(
            PersonDetectionArray, 'heritage/visitor/person_detections', 10)
        self.create_subscription(PersonDetectionArray,
            'heritage/visitor/person_detections/raw', self._on_detections, 20)
        self.create_subscription(Image, 'camera/depth/image_raw', self._on_depth, 20)
        self.create_subscription(CameraInfo, self.get_parameter('rgb_camera_info_topic').value,
                                 self._on_rgb_camera_info, 20)
        self.create_subscription(CameraInfo, self.get_parameter('depth_camera_info_topic').value,
                                 self._on_depth_camera_info, 20)

    def _on_detections(self, message):
        self._detections.append((message, time.monotonic()))
        self._associate()

    def _on_depth(self, message):
        self._depth.append((message, time.monotonic()))
        self._associate()

    def _on_rgb_camera_info(self, message):
        self._rgb_camera_info.append((message, time.monotonic()))
        self._associate()

    def _on_depth_camera_info(self, message):
        self._depth_camera_info.append((message, time.monotonic()))
        self._associate()

    def _complete_detection(self, raw):
        if self._detections and self._detections[0][0] is raw:
            self._detections.popleft()

    def _associate(self):
        if not self._detections:
            return
        raw, received = self._detections[0]
        now = time.monotonic()
        raw_stamp = _stamp_ns(raw.header.stamp)
        if not raw.valid:
            self._publish_invalid(raw, raw.error or 'YOLOX 图像输入或推理无效')
            return
        if raw_stamp <= 0:
            self._publish_invalid(raw, 'YOLOX 图像时间戳无效')
            return
        fresh_depth = [sample for sample in self._depth
                       if now - sample[1] <= self._max_depth_age]
        depth_sample = nearest_stamped_sample(fresh_depth, raw_stamp, self._max_pair_delta)
        if depth_sample is None:
            fresh_stamps = [_stamp_ns(message.header.stamp)
                            for message, _ in fresh_depth]
            latest_stamp = max(fresh_stamps, default=0)
            if (latest_stamp > raw_stamp and
                    (latest_stamp - raw_stamp) / 1e9 > self._max_pair_delta and
                    now - received >= self._max_depth_age):
                nearest_delta = min((abs(stamp - raw_stamp) / 1e9
                                     for stamp in fresh_stamps), default=float('inf'))
                nearest_history = min(self._depth,
                    key=lambda sample: abs(_stamp_ns(sample[0].header.stamp) - raw_stamp),
                    default=None)
                history_delta = (abs(_stamp_ns(nearest_history[0].header.stamp) - raw_stamp) / 1e9
                                 if nearest_history else float('inf'))
                history_age = now - nearest_history[1] if nearest_history else float('inf')
                self._publish_invalid(raw,
                    f'RGB 与深度图时间戳不匹配（最近差值 {nearest_delta:.3f}s，'
                    f'全缓存最近差值 {history_delta:.3f}s/年龄 {history_age:.3f}s，'
                    f'有效缓存 {len(fresh_stamps)}/{len(self._depth)} 帧，'
                    f'等待 {now - received:.3f}s）')
            elif now - received > self._max_depth_age:
                self._publish_invalid(raw, '在时效窗口内找不到匹配的深度帧')
            return
        image, depth_received = depth_sample
        depth_stamp = _stamp_ns(image.header.stamp)
        if now - depth_received > self._max_depth_age or now - received > self._max_depth_age:
            self._publish_invalid(raw, 'RGB 或深度图输入过期')
            return
        fresh_rgb_info = [sample for sample in self._rgb_camera_info
                          if now - sample[1] <= self._max_depth_age]
        fresh_depth_info = [sample for sample in self._depth_camera_info
                            if now - sample[1] <= self._max_depth_age]
        rgb_info_sample = nearest_stamped_sample(fresh_rgb_info, raw_stamp, self._max_pair_delta)
        depth_info_sample = nearest_stamped_sample(fresh_depth_info, depth_stamp, self._max_pair_delta)
        if rgb_info_sample is None or depth_info_sample is None:
            if now - received > self._max_depth_age:
                self._publish_invalid(raw, '在时效窗口内找不到匹配的 CameraInfo')
            return
        rgb_info, _ = rgb_info_sample
        depth_info, _ = depth_info_sample
        error = _calibration_error(rgb_info, depth_info, raw, image)
        if error:
            self._publish_invalid(raw, error)
            return
        if not (math.isfinite(raw.sample_age_sec) and raw.sample_age_sec >= 0):
            self._publish_invalid(raw, 'YOLOX 样本年龄无效')
            return
        if raw.people_count != len(raw.detections):
            self._publish_invalid(raw, 'YOLOX 人数与检测框数量不一致')
            return
        result = copy.deepcopy(raw)
        result.source = 'gazebo_rgbd' if self._simulation_mode else 'temi_rgbd'
        result.sample_age_sec = max(raw.sample_age_sec + now - received, now - depth_received)
        try:
            fx, fy, cx, cy = depth_info.k[0], depth_info.k[4], depth_info.k[2], depth_info.k[5]
            depth = self._bridge.imgmsg_to_cv2(image, desired_encoding='passthrough')
            if image.encoding == '16UC1':
                depth = depth.astype('float32') / 1000.0
            elif image.encoding == '32FC1':
                depth = depth.astype('float32', copy=False)
            else:
                raise ValueError(f'不支持的深度编码：{image.encoding}')
            if depth.shape != (depth_info.height, depth_info.width):
                raise ValueError('深度图数组尺寸与 CameraInfo 不一致')
            if not result.detections:
                result.observation_state = 'NO_PERSON_OBSERVED'
                result.person_distance_valid = False
                result.nearest_person_m = 0.0
                result.error = ''
                self._publisher.publish(result)
                self._complete_detection(raw)
                self._associate()
                return
            if any(not math.isfinite(item.confidence) or
                   not self._min_detection_confidence <= item.confidence <= 1
                   for item in result.detections):
                raise ValueError('检测框置信度无效或低于阈值')
            distances = []
            for detection in result.detections:
                distance = associate_person_depth(
                    (detection.x_min, detection.y_min, detection.x_max, detection.y_max),
                    depth, fx=fx, fy=fy, cx=cx, cy=cy)
                detection.distance_valid = distance is not None
                detection.distance_m = float(distance or 0.0)
                if distance is not None:
                    distances.append(distance)
            result.person_distance_valid = len(distances) == len(result.detections)
            result.observation_state = ('PERSON_DISTANCE_VALID' if result.person_distance_valid
                                        else 'PERSON_DISTANCE_UNKNOWN')
            result.nearest_person_m = float(min(distances)) if result.person_distance_valid else 0.0
            # Preserve only a calibrated upstream occupancy value; never infer density from box size.
            result.crowd_density_valid = bool(result.crowd_density_valid and
                isinstance(result.crowd_density, (int, float)) and
                math.isfinite(result.crowd_density) and 0.0 <= result.crowd_density <= 1.0)
            if not result.crowd_density_valid:
                result.crowd_density = 0.0
            if not result.person_distance_valid:
                result.error = '检测到人员但没有足够有效深度像素'
            self._publisher.publish(result)
            self._complete_detection(raw)
            self._associate()
        except Exception as error:
            self._publish_invalid(raw, f'深度图关联失败：{error}')

    def _publish_invalid(self, raw, error):
        result = copy.deepcopy(raw)
        result.source = 'gazebo_rgbd' if self._simulation_mode else 'temi_rgbd'
        result.valid = False
        result.observation_state = 'SENSOR_INVALID'
        result.person_distance_valid = False
        result.nearest_person_m = 0.0
        result.crowd_density_valid = False
        result.crowd_density = 0.0
        result.error = error
        self._publisher.publish(result)
        self._complete_detection(raw)
        self._associate()


def main(args=None):
    import rclpy
    from .ros_shutdown import spin_node
    rclpy.init(args=args)
    node = DepthAssociationNode()
    spin_node(rclpy, node)
