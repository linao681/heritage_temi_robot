"""YOLOX-S ROS image adapter; publishes boxes and anonymous frame counts only."""
import math
import time

from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Int32
from temi_interfaces.msg import PersonDetection, PersonDetectionArray

from .person_detector import YoloXPersonCounter


def image_sample_age_sec(image_stamp_ns, ros_now_ns, processing_sec):
    if (type(image_stamp_ns) is not int or image_stamp_ns <= 0 or
            type(ros_now_ns) is not int or ros_now_ns <= 0 or
            type(processing_sec) not in (int, float) or not math.isfinite(processing_sec) or
            processing_sec < 0):
        return float('inf')
    capture_age = max(0.0, (ros_now_ns - image_stamp_ns) / 1e9)
    return capture_age + processing_sec


class YoloXPersonNode(Node):
    def __init__(self):
        super().__init__('yolox_person_detector')
        self.declare_parameter('model_path', 'assets/vision/object_detection_yolox_2022nov.onnx')
        self.declare_parameter('confidence', 0.5)
        self.declare_parameter('nms', 0.5)
        self.declare_parameter('image_topic', 'depth_camera/image_raw')
        self.declare_parameter('max_image_age_sec', 0.5)
        self._max_image_age = self.get_parameter('max_image_age_sec').value
        try:
            self._counter = YoloXPersonCounter(
                self.get_parameter('model_path').value,
                self.get_parameter('confidence').value,
                self.get_parameter('nms').value)
        except (OSError, ValueError) as error:
            raise RuntimeError(f'YOLOX 本地模型不可用：{error}') from error
        self._bridge = CvBridge()
        self._count = self.create_publisher(Int32, 'heritage/visitor/camera_count', 10)
        self._detections = self.create_publisher(
            PersonDetectionArray, 'heritage/visitor/person_detections/raw', 10)
        self.create_subscription(Image, self.get_parameter('image_topic').value, self._on_image, 1)

    def _on_image(self, message):
        started = time.monotonic()
        output = PersonDetectionArray()
        output.header = message.header
        output.source = 'yolox_rgb'
        try:
            image = self._bridge.imgmsg_to_cv2(message, desired_encoding='bgr8')
            boxes = self._counter.detect(image)
            output.valid = True
            output.people_count = len(boxes)
            output.observation_state = ('NO_PERSON_OBSERVED' if not boxes
                                        else 'PERSON_DISTANCE_UNKNOWN')
            for x, y, width, height, confidence in boxes:
                detection = PersonDetection()
                detection.x_min = max(0.0, min(1.0, x / image.shape[1]))
                detection.y_min = max(0.0, min(1.0, y / image.shape[0]))
                detection.x_max = max(0.0, min(1.0, (x + width) / image.shape[1]))
                detection.y_max = max(0.0, min(1.0, (y + height) / image.shape[0]))
                detection.confidence = float(confidence)
                detection.distance_valid = False
                detection.distance_m = 0.0
                output.detections.append(detection)
        except Exception as error:
            output.valid = False
            output.observation_state = 'SENSOR_INVALID'
            output.error = f'YOLOX 单帧检测失败：{error}'
            self.get_logger().warning(output.error)
        output.sample_age_sec = image_sample_age_sec(
            message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec,
            self.get_clock().now().nanoseconds,
            time.monotonic() - started)
        if not math.isfinite(output.sample_age_sec) or output.sample_age_sec > self._max_image_age:
            output.valid = False
            output.observation_state = 'SENSOR_INVALID'
            output.error = 'YOLOX 输入图像已过期，拒绝发布人员观测'
        if output.valid:
            self._count.publish(Int32(data=output.people_count))
        self._detections.publish(output)


def main(args=None):
    import rclpy
    from .ros_shutdown import spin_node
    rclpy.init(args=args)
    node = YoloXPersonNode()
    spin_node(rclpy, node)
