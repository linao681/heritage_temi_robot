"""真实本地合成 AVI 读取与人数指标（不依赖外部模型或网络）。"""

import cv2
import numpy as np
import pytest

from visitor_perception.video_counter import sample_video, summarize
from visitor_perception.video_main import main


@pytest.fixture
def local_video(tmp_path):
    path = tmp_path / 'sample.avi'
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 10.0, (64, 48))
    assert writer.isOpened()
    try:
        for value in range(10):
            writer.write(np.full((48, 64, 3), value * 20, dtype=np.uint8))
    finally:
        writer.release()
    return path


def test_real_video_sampling_at_known_indices(local_video):
    received = []
    samples = sample_video(local_video, lambda frame: 2, interval_sec=.4, on_sample=received.append)
    assert received == samples
    assert [s['frame_index'] for s in samples] == [0, 4, 8]
    assert [s['video_sec'] for s in samples] == pytest.approx([0, .4, .8])
    assert [s['people_count'] for s in samples] == [2, 2, 2]
    assert all(s['latency_ms'] >= 0 for s in samples)


def test_limit_ends_sampling_without_false_zero(local_video):
    samples = sample_video(local_video, lambda frame: 4, interval_sec=.2, limit=2)
    assert [s['frame_index'] for s in samples] == [0, 2]
    assert [s['people_count'] for s in samples] == [4, 4]


def test_detection_failure_does_not_publish_zero(local_video):
    def fail(_frame):
        raise RuntimeError('model error')
    samples = []
    with pytest.raises(RuntimeError, match='model error'):
        sample_video(local_video, fail, on_sample=samples.append)
    assert not samples


@pytest.mark.parametrize('kwargs', [{'interval_sec': 0}, {'interval_sec': float('nan')},
                                     {'limit': 0}, {'limit': True}])
def test_invalid_sampling_parameters_fail(local_video, kwargs):
    with pytest.raises(ValueError):
        sample_video(local_video, lambda frame: 2, **kwargs)


def test_only_explicit_existing_local_video(tmp_path):
    with pytest.raises(ValueError):
        sample_video(tmp_path / 'not-found.avi', lambda frame: 2)
    with pytest.raises(ValueError):
        sample_video('https://example.invalid/video.avi', lambda frame: 2)


def test_count_metrics_and_latency():
    samples = [dict(frame_index=i, people_count=n, latency_ms=t) for i,n,t in
               [(0, 1, 10.0), (40, 0, 20.0), (80, 3, 30.0)]]
    result = summarize(samples, {0: 0, 40: 2, 80: 3})
    assert result['sample_count'] == 3
    assert result['mean_latency_ms'] == pytest.approx(20)
    assert result['p95_latency_ms'] == pytest.approx(29)
    metrics = result['metrics']
    assert metrics['mae'] == pytest.approx(1)
    assert metrics['rmse'] == pytest.approx((5/3)**.5)
    assert metrics['exact_count_ratio'] == pytest.approx(1/3)
    assert metrics['empty_false_positive_ratio'] == 1
    assert metrics['nonempty_zero_ratio'] == .5


def test_no_empty_ground_truth_is_reported_unavailable():
    samples = [dict(frame_index=0, people_count=3, latency_ms=5)]
    assert summarize(samples, {0: 3})['metrics']['empty_false_positive_ratio'] is None
    with pytest.raises(ValueError):
        summarize(samples, {1: 3})


def test_publish_requires_explicit_local_domain(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv('ROS_LOCALHOST_ONLY', raising=False)
    monkeypatch.delenv('ROS_DOMAIN_ID', raising=False)
    with pytest.raises(SystemExit) as error:
        main(['--video', 'nothing.avi', '--model', 'nothing.onnx', '--output', str(tmp_path/'out.json'), '--publish'])
    assert error.value.code == 2
    assert 'ROS_LOCALHOST_ONLY' in capsys.readouterr().err


@pytest.mark.parametrize('text', ['[]', '{"frames": []}', '{"frames":{"01":3}}',
                                  '{"frames":{"1":-1}}', '{"frames":{"0":1,"0":2}}'])
def test_malformed_reference_rejected_before_inference(tmp_path, text):
    from visitor_perception.video_main import load_reference
    path = tmp_path / 'reference.json'
    path.write_text(text, encoding='utf-8')
    with pytest.raises(ValueError):
        load_reference(path, 'digest')


def test_reference_hash_and_valid_frame_indices(tmp_path):
    from visitor_perception.video_main import load_reference
    path = tmp_path / 'reference.json'
    path.write_text('{"video_sha256":"digest","frames":{"0":3,"40":4}}', encoding='utf-8')
    assert load_reference(path, 'digest') == {0: 3, 40: 4}
    with pytest.raises(ValueError):
        load_reference(path, 'other')
