import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros2_ws/src/visitor_perception'))

from builtin_interfaces.msg import Time as RosTime
from std_msgs.msg import Header
from sensor_msgs.msg import CameraInfo, Image
from temi_interfaces.msg import PersonDetection, PersonDetectionArray
from visitor_perception.ros_depth_association import DepthAssociationNode, nearest_stamped_sample


FRAME = 'depth_camera_optical_frame'


class FakeBridge:
    def __init__(self, depth):
        self.depth = depth

    def imgmsg_to_cv2(self, _image, desired_encoding):
        assert desired_encoding == 'passthrough'
        return self.depth.copy()


class CapturePublisher:
    def __init__(self):
        self.last = None
        self.messages = []

    def publish(self, message):
        self.last = message
        self.messages.append(message)


def stamped_header(sec=10):
    return Header(stamp=RosTime(sec=sec), frame_id=FRAME)


def camera_info(sec=10):
    info = CameraInfo()
    info.header = stamped_header(sec)
    info.width, info.height = 64, 48
    info.distortion_model = 'plumb_bob'
    info.d = []
    info.k = [100.0, 0.0, 31.5, 0.0, 100.0, 23.5, 0.0, 0.0, 1.0]
    return info


def detection(box, confidence=0.9):
    item = PersonDetection()
    item.x_min, item.y_min, item.x_max, item.y_max = box
    item.confidence = confidence
    return item


def run_association(boxes=(), *, depth=None, raw_valid=True, raw_sec=10,
                    depth_sec=10, received_age=0.0, rgb_info=None, depth_info=None):
    raw = PersonDetectionArray()
    raw.header = stamped_header(raw_sec)
    raw.source = 'yolox_rgb'
    raw.sample_age_sec = 0.0
    raw.valid = raw_valid
    raw.people_count = len(boxes)
    raw.detections = [detection(*box) if isinstance(box, tuple) and len(box) == 2
                      else detection(box) for box in boxes]
    image = Image()
    image.header = stamped_header(depth_sec)
    image.width, image.height, image.encoding = 64, 48, '32FC1'
    node = DepthAssociationNode.__new__(DepthAssociationNode)
    node._simulation_mode = True
    node._max_pair_delta = 0.15
    node._max_depth_age = 0.5
    node._min_detection_confidence = 0.5
    node._processed_detection_stamp = None
    node._bridge = FakeBridge(np.full((48, 64), 2.0, dtype=np.float32) if depth is None else depth)
    node._detections = deque([(raw, time.monotonic() - received_age)], maxlen=20)
    received = time.monotonic()
    node._depth = deque([(image, received)], maxlen=20)
    node._rgb_camera_info = deque([(rgb_info or camera_info(raw_sec), received)], maxlen=20)
    node._depth_camera_info = deque([(depth_info or camera_info(depth_sec), received)], maxlen=20)
    node._publisher = CapturePublisher()
    node._associate()
    return node._publisher.last


def test_empty_yolox_frame_is_valid_no_person_observation_without_distance():
    result = run_association()

    assert result.valid
    assert result.observation_state == 'NO_PERSON_OBSERVED'
    assert not result.person_distance_valid
    assert result.nearest_person_m == 0.0
    assert not result.error


def test_single_person_uses_rgb_box_and_calibrated_depth():
    result = run_association(boxes=[(0.4, 0.2, 0.6, 0.8)])

    assert result.valid
    assert result.people_count == 1
    assert result.observation_state == 'PERSON_DISTANCE_VALID'
    assert result.person_distance_valid
    assert result.detections[0].distance_m == pytest.approx(2.0, abs=0.02)


def test_multiple_people_report_the_nearest_valid_depth_measurement():
    depth = np.full((48, 64), 2.5, dtype=np.float32)
    depth[:, :32] = 1.5
    result = run_association(boxes=[(0.05, 0.1, 0.45, 0.9), (0.55, 0.1, 0.95, 0.9)],
                             depth=depth)

    assert result.valid and result.person_distance_valid
    assert len(result.detections) == 2
    assert result.nearest_person_m == pytest.approx(result.detections[0].distance_m)
    assert result.nearest_person_m < result.detections[1].distance_m


def test_visible_person_with_invalid_depth_is_unknown_not_far_away():
    result = run_association(boxes=[(0.4, 0.2, 0.6, 0.8)],
                             depth=np.full((48, 64), np.nan, dtype=np.float32))

    assert result.valid
    assert result.observation_state == 'PERSON_DISTANCE_UNKNOWN'
    assert not result.person_distance_valid
    assert result.nearest_person_m == 0.0
    assert result.detections[0].distance_m == 0.0


def test_detection_below_yolox_confidence_threshold_fails_closed():
    result = run_association(boxes=[((0.4, 0.2, 0.6, 0.8), 0.2)])

    assert not result.valid
    assert result.observation_state == 'SENSOR_INVALID'
    assert '置信度' in result.error


@pytest.mark.parametrize('mismatch', ['frame', 'resolution', 'intrinsics'])
def test_unaligned_camera_info_fails_closed(mismatch):
    rgb, depth = camera_info(), camera_info()
    if mismatch == 'frame':
        depth.header.frame_id = 'other_optical_frame'
    elif mismatch == 'resolution':
        depth.width = 32
    else:
        depth.k[0] = 80.0
    result = run_association(boxes=[(0.4, 0.2, 0.6, 0.8)],
                             rgb_info=rgb, depth_info=depth)

    assert not result.valid
    assert result.observation_state == 'SENSOR_INVALID'
    assert not result.person_distance_valid


def test_rgb_and_depth_timestamp_mismatch_fails_closed():
    result = run_association(boxes=[(0.4, 0.2, 0.6, 0.8)], depth_sec=12,
                             received_age=0.6)

    assert not result.valid
    assert result.observation_state == 'SENSOR_INVALID'
    assert '时间戳' in result.error


def test_depth_timestamp_mismatch_waits_for_sensor_delivery_window():
    result = run_association(boxes=[(0.4, 0.2, 0.6, 0.8)], depth_sec=12,
                             received_age=0.2)

    assert result is None


def test_waits_for_matching_depth_frame_before_failing_a_new_detection():
    raw = PersonDetectionArray()
    raw.header = stamped_header(10)
    raw.source = 'yolox_rgb'
    raw.sample_age_sec = 0.0
    raw.valid = True
    raw.people_count = 1
    raw.detections = [detection((0.4, 0.2, 0.6, 0.8))]
    late_image = Image(header=stamped_header(11))
    late_image.width, late_image.height, late_image.encoding = 64, 48, '32FC1'
    matched_image = Image(header=stamped_header(10))
    matched_image.width, matched_image.height, matched_image.encoding = 64, 48, '32FC1'
    received = time.monotonic()
    node = DepthAssociationNode.__new__(DepthAssociationNode)
    node._simulation_mode = True
    node._max_pair_delta = 0.15
    node._max_depth_age = 0.5
    node._min_detection_confidence = 0.5
    node._processed_detection_stamp = None
    node._bridge = FakeBridge(np.full((48, 64), 2.0, dtype=np.float32))
    node._detections = deque([(raw, received)], maxlen=20)
    node._depth = deque([(late_image, received)], maxlen=20)
    node._rgb_camera_info = deque([(camera_info(10), received)], maxlen=20)
    node._depth_camera_info = deque([(camera_info(10), received)], maxlen=20)
    node._publisher = CapturePublisher()

    node._associate()
    assert node._publisher.last is None

    node._depth.append((matched_image, time.monotonic()))
    node._associate()

    assert node._publisher.last.valid
    assert node._publisher.last.observation_state == 'PERSON_DISTANCE_VALID'


def test_detection_queue_preserves_and_processes_matching_rgbd_frames_in_order():
    received = time.monotonic()
    detections = []
    images = []
    for stamp in (10, 11):
        raw = PersonDetectionArray()
        raw.header = stamped_header(stamp)
        raw.source = 'yolox_rgb'
        raw.sample_age_sec = 0.0
        raw.valid = True
        raw.people_count = 0
        detections.append((raw, received))
        image = Image(header=stamped_header(stamp))
        image.width, image.height, image.encoding = 64, 48, '32FC1'
        images.append((image, received))

    node = DepthAssociationNode.__new__(DepthAssociationNode)
    node._simulation_mode = True
    node._max_pair_delta = 0.15
    node._max_depth_age = 0.5
    node._min_detection_confidence = 0.5
    node._bridge = FakeBridge(np.full((48, 64), 2.0, dtype=np.float32))
    node._detections = deque(detections, maxlen=20)
    node._depth = deque(images, maxlen=20)
    node._rgb_camera_info = deque([(camera_info(stamp), received) for stamp in (10, 11)], maxlen=20)
    node._depth_camera_info = deque([(camera_info(stamp), received) for stamp in (10, 11)], maxlen=20)
    node._publisher = CapturePublisher()

    node._associate()

    assert [message.header.stamp.sec for message in node._publisher.messages] == [10, 11]
    assert all(message.observation_state == 'NO_PERSON_OBSERVED'
               for message in node._publisher.messages)


def test_yolox_dropout_and_depth_timeout_fail_closed():
    dropped = run_association(raw_valid=False)
    timed_out = run_association(boxes=[(0.4, 0.2, 0.6, 0.8)], received_age=1.0)

    assert not dropped.valid and dropped.observation_state == 'SENSOR_INVALID'
    assert not timed_out.valid and timed_out.observation_state == 'SENSOR_INVALID'


def test_delayed_yolox_uses_matching_buffered_depth_instead_of_latest_frame():
    old = Image(header=stamped_header(10))
    latest = Image(header=stamped_header(11))
    samples = [(old, 4.75), (latest, 5.0)]

    selected = nearest_stamped_sample(samples, 10_000_000_000, 0.15)

    assert selected == samples[0]


def test_depth_buffer_refuses_frames_outside_pairing_tolerance():
    only_late = Image(header=stamped_header(12))

    assert nearest_stamped_sample([(only_late, 5.0)], 10_000_000_000, 0.15) is None
