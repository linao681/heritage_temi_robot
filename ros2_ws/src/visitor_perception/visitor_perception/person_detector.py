"""OpenCV Zoo YOLOX-S 的本地 CPU 人数适配器，只统计 person 类。

输入尺度与解码依据 OpenCV Zoo object_detection_yolox (Apache 2.0)，
不保存帧、不跨帧追踪，也不输出身份信息。
"""

import math
from pathlib import Path

import cv2
import numpy as np


INPUT_SIZE = 640


def preprocess(frame):
    """BGR 转 RGB，保持宽高比并以 114 填充；模型输入为 float32 NCHW。"""
    if (not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3 or
            not frame.size or frame.dtype != np.uint8):
        raise ValueError('需要非空 BGR uint8 三通道图像')
    height, width = frame.shape[:2]
    ratio = min(INPUT_SIZE / height, INPUT_SIZE / width)
    size = (max(1, int(width * ratio)), max(1, int(height * ratio)))
    resized = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), size)
    canvas = np.full((INPUT_SIZE, INPUT_SIZE, 3), 114, dtype=np.float32)
    canvas[:size[1], :size[0]] = resized
    return np.ascontiguousarray(canvas.transpose(2, 0, 1)[None]), ratio


def _grids():
    coords, strides = [], []
    for stride in (8, 16, 32):
        dimension = INPUT_SIZE // stride
        x, y = np.meshgrid(np.arange(dimension), np.arange(dimension))
        coords.append(np.column_stack((x.ravel(), y.ravel())))
        strides.append(np.full(dimension * dimension, stride))
    return np.concatenate(coords), np.concatenate(strides)


GRID, STRIDE = _grids()


def _threshold(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 < value < 1:
        raise ValueError('置信度与 NMS 阈值必须在 0 到 1 之间')


def decode_person_boxes(output, ratio, frame_shape, confidence=0.5, nms=0.5):
    """解码三个 stride，仅返回 person 类的原图有效框及置信度。"""
    _threshold(confidence)
    _threshold(nms)
    if (not isinstance(output, np.ndarray) or output.shape != (1, 8400, 85) or
            not np.isfinite(output).all()):
        raise ValueError('YOLOX 模型输出形状或数值错误')
    if not math.isfinite(ratio) or ratio <= 0 or min(frame_shape[:2]) <= 0:
        raise ValueError('无效图像尺寸或缩放比例')
    rows = output[0]
    if np.any(rows[:, 4:] < 0) or np.any(rows[:, 4:] > 1):
        raise ValueError('YOLOX 概率张量超出 0~1，模型不兼容')
    probabilities = rows[:, 5:]
    score = rows[:, 4] * probabilities[:, 0]
    indices = np.flatnonzero((np.argmax(probabilities, axis=1) == 0) & (score > confidence))
    if not len(indices):
        return []
    stride = STRIDE[indices, None]
    centers = (rows[indices, :2] + GRID[indices]) * stride
    with np.errstate(over='ignore', invalid='ignore'):
        sizes = np.exp(rows[indices, 2:4]) * stride
    xy0, xy1 = (centers - sizes / 2) / ratio, (centers + sizes / 2) / ratio
    if not np.isfinite(xy0).all() or not np.isfinite(xy1).all():
        raise ValueError('YOLOX 检测框解码异常')
    height, width = frame_shape[:2]
    xy0 = np.clip(xy0, (0, 0), (width, height))
    xy1 = np.clip(xy1, (0, 0), (width, height))
    extent = xy1 - xy0
    valid = (extent[:, 0] > 0) & (extent[:, 1] > 0)
    boxes = np.column_stack((xy0[valid], extent[valid])).tolist()
    scores = score[indices][valid].tolist()
    if not boxes:
        return []
    keep = cv2.dnn.NMSBoxes(boxes, scores, confidence, nms)
    return [(*boxes[i], scores[i]) for i in np.asarray(keep).reshape(-1)]


class YoloXPersonCounter:
    def __init__(self, model, confidence=0.5, nms=0.5):
        _threshold(confidence)
        _threshold(nms)
        path = Path(model)
        if not path.is_file() or path.suffix.lower() != '.onnx':
            raise ValueError('必须指定存在的本地 YOLOX ONNX 文件')
        self._net = cv2.dnn.readNetFromONNX(str(path))
        self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self.confidence = confidence
        self.nms = nms

    def detect(self, frame):
        """返回当前帧 person 框；距离由后续标定深度关联提供。"""
        blob, ratio = preprocess(frame)
        self._net.setInput(blob)
        output = self._net.forward()
        return decode_person_boxes(output, ratio, frame.shape, self.confidence, self.nms)

    def count(self, frame) -> int:
        """一次推理按当前画面计算匿名人数。推理错误原样传播。"""
        return len(self.detect(frame))
