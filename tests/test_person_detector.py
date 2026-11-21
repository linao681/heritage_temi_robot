"""YOLOX 输入及解码验证，无摄像头或模型下载依赖。"""

import math
import numpy as np
import pytest

from visitor_perception.person_detector import YoloXPersonCounter, decode_person_boxes, preprocess


def test_rgb_letterbox_shape_and_padding():
    frame = np.full((2, 4, 3), (10, 20, 30), dtype=np.uint8)
    blob, ratio = preprocess(frame)
    assert blob.shape == (1, 3, 640, 640) and blob.dtype == np.float32
    assert ratio == 160
    assert tuple(blob[0, :, 0, 0]) == (30, 20, 10)
    assert tuple(blob[0, :, 639, 639]) == (114, 114, 114)


@pytest.mark.parametrize('frame', [None, np.zeros((0, 64, 3), np.uint8),
                                   np.zeros((64, 64), np.uint8), np.zeros((64, 64, 3), np.float32)])
def test_bad_input_frames_rejected(frame):
    with pytest.raises(ValueError):
        preprocess(frame)


def output():
    return np.zeros((1, 8400, 85), dtype=np.float32)


def set_row(rows, x, y, cx, cy, *, person=0.9, bike=0.0, obj=0.9, width=40, height=80):
    row = rows[0, y * 80 + x]
    row[:5] = (cx / 8 - x, cy / 8 - y, math.log(width / 8), math.log(height / 8), obj)
    row[5:7] = (person, bike)


def test_only_person_and_nms_removes_duplicate():
    rows = output()
    set_row(rows, 10, 10, 80, 80)
    set_row(rows, 11, 10, 81, 80, person=.85)
    set_row(rows, 30, 10, 240, 80)
    set_row(rows, 40, 10, 320, 80, person=.75, bike=.95)
    set_row(rows, 50, 10, 400, 80, person=.9, obj=.2)
    boxes = decode_person_boxes(rows, 1, (640, 640, 3))
    assert len(boxes) == 2
    assert sorted(round(box[0]) for box in boxes) == [60, 220]
    assert all(box[4] == pytest.approx(.81) for box in boxes)


def test_multiscale_grid_and_clips_boxes_to_original_frame():
    rows = output()
    # stride 16 grid (40 x 40); center in model coordinates (4, 12), partly outside image.
    row = rows[0, 6400]
    row[:6] = (4 / 16, 12 / 16, math.log(32 / 16), math.log(40 / 16), .9, .9)
    boxes = decode_person_boxes(rows, .5, (100, 100, 3))
    assert len(boxes) == 1
    assert boxes[0][:4] == pytest.approx((0, 0, 40, 64))


def test_padding_only_does_not_count():
    rows = output()
    set_row(rows, 40, 70, 320, 560, width=20, height=30)
    assert decode_person_boxes(rows, 1, (320, 640, 3)) == []


def test_valid_empty_model_output_counts_zero():
    assert decode_person_boxes(output(), 1, (640, 640, 3)) == []


@pytest.mark.parametrize('bad', [np.zeros((8400, 85)), np.full((1, 8400, 85), np.nan)])
def test_invalid_model_output_is_error_not_zero(bad):
    with pytest.raises(ValueError):
        decode_person_boxes(bad, 1, (640, 640, 3))


def test_missing_weights_is_error(tmp_path):
    with pytest.raises(ValueError):
        YoloXPersonCounter(tmp_path / 'missing.onnx')


def test_incompatible_model_probability_tensor_rejected():
    rows = output()
    rows[0, 0, 4] = 2.0
    with pytest.raises(ValueError):
        decode_person_boxes(rows, 1, (640, 640, 3))
