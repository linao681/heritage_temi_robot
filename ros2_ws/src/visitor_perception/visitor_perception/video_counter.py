"""本地离线视频逐帧采样和数值评估，不保存原始帧。"""

import math
from pathlib import Path
import time

import cv2
import numpy as np


def sample_video(path, count, interval_sec=0.5, limit=None, on_sample=None):
    """每个选中帧仅推理一次；正常 EOF 或显式 limit 结束，不补发零人数。"""
    path = Path(path)
    if not path.is_file() or path.suffix.lower() not in ('.avi', '.mp4', '.m4v', '.mov', '.mkv', '.webm'):
        raise ValueError('请显式指定存在的本地视频文件，不接受摄像头或网络流')
    if type(interval_sec) not in (int, float) or not math.isfinite(interval_sec) or interval_sec <= 0:
        raise ValueError('采样间隔必须为有限正数')
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError('采样数量必须为正整数')
    cap = cv2.VideoCapture(str(path))
    samples = []
    try:
        if not cap.isOpened():
            raise ValueError('视频无法打开')
        fps = cap.get(cv2.CAP_PROP_FPS)
        declared_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError('视频帧率未知，无法进行时间采样')
        index, next_sec = 0, 0.0
        while True:
            ok, frame = cap.read()
            if not ok:
                if math.isfinite(declared_frames) and declared_frames > 0 and index < round(declared_frames):
                    raise ValueError(f'视频提前结束/解码失败: frame {index} of {declared_frames:g}')
                break
            if frame is None or not frame.size:
                raise ValueError(f'视频帧 {index} 解码为空')
            video_sec = index / fps
            if video_sec + 1e-9 >= next_sec:
                start = time.perf_counter()
                people = count(frame)
                latency_ms = (time.perf_counter() - start) * 1000.0
                if type(people) is not int or people < 0:
                    raise ValueError('检测结果必须为非负整数')
                sample = {'frame_index': index, 'video_sec': video_sec,
                          'people_count': people, 'latency_ms': latency_ms}
                samples.append(sample)
                if on_sample is not None:
                    on_sample(sample)
                if limit is not None and len(samples) >= limit:
                    break
                # 不对同一帧重复推理，也不因非整数帧率而累积取整漂移。
                next_sec = (math.floor((video_sec + 1e-9) / interval_sec) + 1) * interval_sec
            index += 1
        if not samples:
            raise ValueError('视频没有可解码样本')
        return samples
    finally:
        cap.release()


def summarize(samples, reference=None):
    if not samples:
        raise ValueError('没有可用于汇总的样本')
    latency = np.asarray([sample['latency_ms'] for sample in samples], dtype=float)
    result = {'sample_count': len(samples), 'mean_latency_ms': float(np.mean(latency)),
              'p95_latency_ms': float(np.percentile(latency, 95))}
    if reference is None:
        return result
    indices = [sample['frame_index'] for sample in samples]
    if len(set(indices)) != len(indices) or set(reference) != set(indices):
        raise ValueError('参考计数必须与所采样帧号完全一致')
    if any(type(n) is not int or n < 0 for n in reference.values()):
        raise ValueError('参考人数必须为非负整数')
    actual = np.array([reference[i] for i in indices])
    predicted = np.array([sample['people_count'] for sample in samples])
    delta = predicted - actual
    empty, nonempty = actual == 0, actual > 0
    result['metrics'] = {
        'mae': float(np.mean(np.abs(delta))), 'rmse': float(np.sqrt(np.mean(delta ** 2))),
        'exact_count_ratio': float(np.mean(delta == 0)),
        'empty_reference_frames': int(np.count_nonzero(empty)),
        'empty_false_positive_ratio': float(np.mean(predicted[empty] > 0)) if empty.any() else None,
        'nonempty_reference_frames': int(np.count_nonzero(nonempty)),
        'nonempty_zero_ratio': float(np.mean(predicted[nonempty] == 0)) if nonempty.any() else None,
    }
    return result
