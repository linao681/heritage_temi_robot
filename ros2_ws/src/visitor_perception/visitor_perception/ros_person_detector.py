"""YOLOX-S ROS image adapter; publishes boxes and anonymous frame counts only."""
import time

from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Int32
from temi_interfaces.msg import PersonDetection, PersonDetectionArray

from .person_detector import YoloXPersonCounter


class YoloXPersonNode(Node):
    def __init__(self):
        super().__init__('yolox_person_detector')
        self.declare_parameter('model_path', 'assets/vision/object_detection_yolox_2022nov.onnx')
        self.declare_parameter('confidence', 0.5)
        self.declare_parameter('nms', 0.5)
        self.declare_parameter('image_topic', 'depth_camera/image_raw')
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
        self.create_subscription(Image, self.get_parameter('image_topic').value, self._on_image, 5)

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
            self._count.publish(Int32(data=len(boxes)))
        except Exception as error:
            output.valid = False
            output.error = f'YOLOX 单帧检测失败：{error}'
            self.get_logger().warning(output.error)
        output.sample_age_sec = max(0.0, time.monotonic() - started)
        self._detections.publish(output)


def main(args=None):
    import rclpy
    rclpy.init(args=args)
    node = YoloXPersonNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
