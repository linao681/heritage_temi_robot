"""离线视觉计数 CLI；默认只输出数值报告，无 ROS2 依赖或发布。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import cv2

from .person_detector import YoloXPersonCounter
from .video_counter import sample_video, summarize


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_reference(path, video_hash):
    """严格解析参考帧数，拒绝重复键、非规范帧号与错误视频来源。"""
    def unique_object(pairs):
        value = dict(pairs)
        if len(value) != len(pairs):
            raise ValueError('参考 JSON 含重复键')
        return value

    with Path(path).open(encoding='utf-8') as file:
        ref = json.load(file, object_pairs_hook=unique_object)
    if not isinstance(ref, dict) or not isinstance(ref.get('frames'), dict) or not ref['frames']:
        raise ValueError('参考 JSON 必须包含非空 frames 对象')
    if ref.get('video_sha256', video_hash) != video_hash:
        raise ValueError('视频 SHA-256 与参考文件不一致')
    values = {}
    for index, number in ref['frames'].items():
        if (not index.isdecimal() or str(int(index)) != index or
                type(number) is not int or number < 0):
            raise ValueError('参考帧号须为规范非负整数字符串，人数为非负整数')
        values[int(index)] = number
    return values


def main(args=None):
    parser = argparse.ArgumentParser(description='离线视频匿名人数统计（仅本地文件）')
    parser.add_argument('--video', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', required=True, help='新建 JSON 数值报告')
    parser.add_argument('--interval', type=float, default=0.5)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--reference', help='含 frames 对照计数的 JSON，可选')
    parser.add_argument('--publish', action='store_true', help='显式发布至专用本机 vision_count Topic')
    options = parser.parse_args(args)
    if options.publish:
        domain = os.environ.get('ROS_DOMAIN_ID', '')
        if (os.environ.get('ROS_LOCALHOST_ONLY') != '1' or not domain.isdecimal() or
                not 0 <= int(domain) <= 232):
            parser.error('--publish 要求 ROS_LOCALHOST_ONLY=1 和显式有效的 ROS_DOMAIN_ID')
    output_path = Path(options.output)
    if output_path.exists() or not output_path.parent.is_dir():
        parser.error('报告必须是已有目录中的新文件；不会覆盖旧报告')

    node = None
    ros = None
    samples = []
    wall_start = None
    try:
        if not Path(options.video).is_file():
            raise ValueError('本地视频不存在')
        video_hash = _sha256(options.video)
        reference = load_reference(options.reference, video_hash) if options.reference else None
        detector = YoloXPersonCounter(options.model)
        if options.publish:
            import rclpy as ros
            from rclpy.duration import Duration
            from std_msgs.msg import Int32
            ros.init(args=[])
            node = ros.create_node('offline_video_count')
            publisher = node.create_publisher(Int32, 'heritage/visitor/vision_count', 10)
            deadline = time.monotonic() + 5.0
            while not publisher.get_subscription_count():
                if time.monotonic() >= deadline:
                    raise RuntimeError('未发现本机离线人数订阅者')
                ros.spin_once(node, timeout_sec=.05)

        def record(sample):
            nonlocal wall_start
            if options.publish:
                if wall_start is None:
                    wall_start = time.monotonic() - sample['video_sec']
                # 真实播放节奏；不对旧帧补发、也不发送假零值。
                time.sleep(max(0, wall_start + sample['video_sec'] - time.monotonic()))
                publisher.publish(Int32(data=sample['people_count']))
            samples.append(sample)

        sample_video(options.video, detector.count, options.interval, options.limit, record)
        ack_confirmed = None
        if options.publish:
            ack_confirmed = publisher.wait_for_all_acked(Duration(seconds=2))
            if not ack_confirmed:
                # DDS 确认超时不等于订阅端没有收到。保留实际检测报告，由接收端核对序列。
                print('离线计数已发出，DDS 确认超时；需核对订阅端实际接收结果', file=sys.stderr, flush=True)
        report = {'success': True, 'source': 'offline_video', 'model_sha256': _sha256(options.model),
                  'video_sha256': video_hash, 'interval_sec': options.interval, 'published': options.publish,
                  'publisher_ack_confirmed': ack_confirmed,
                  'samples': samples, 'summary': summarize(samples, reference)}
        if reference is not None:
            report['reference_counts'] = reference
        with output_path.open('x', encoding='utf-8') as file:
            json.dump(report, file, indent=2, ensure_ascii=False, allow_nan=False)
        print(f"人数检测完成：{len(samples)} 个样本，报告 {output_path}", flush=True)
        return 0
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, cv2.error) as error:
        print(f'离线视频检测失败: {error}', file=sys.stderr, flush=True)
        return 1
    finally:
        if node is not None:
            node.destroy_node()
        if ros is not None:
            ros.try_shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
