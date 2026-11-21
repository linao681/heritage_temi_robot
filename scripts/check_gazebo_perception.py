#!/usr/bin/env python3
"""Read-only check of Gazebo scan, depth image, camera calibration and TF."""
import argparse
import json
import math
from pathlib import Path
import time

import cv_bridge
import numpy as np
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image, LaserScan
from tf2_ros import Buffer, TransformListener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=45.0)
    parser.add_argument('--output', required=True, help='新文件路径；拒绝覆盖')
    options = parser.parse_args()
    output = Path(options.output)
    if output.exists():
        parser.error('输出文件已存在；拒绝覆盖历史报告')
    rclpy.init()
    node = rclpy.create_node('gazebo_perception_readiness')
    bridge = cv_bridge.CvBridge()
    received = {}
    buffer = Buffer()
    listener = TransformListener(buffer, node)
    node.create_subscription(LaserScan, 'scan', lambda msg: received.update(scan=msg), qos_profile_sensor_data)
    node.create_subscription(Image, 'camera/depth/image_raw', lambda msg: received.update(depth=msg), qos_profile_sensor_data)
    node.create_subscription(CameraInfo, 'camera/depth/camera_info', lambda msg: received.update(info=msg), 10)
    deadline = time.monotonic() + options.timeout
    try:
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if {'scan', 'depth', 'info'} <= received.keys():
                break
        scan = received.get('scan')
        depth_msg = received.get('depth')
        info = received.get('info')
        scan_values = [] if scan is None else [x for x in scan.ranges if math.isfinite(x) and scan.range_min <= x <= scan.range_max]
        depth_metrics = {}
        if depth_msg is not None:
            image = bridge.imgmsg_to_cv2(depth_msg, desired_encoding='passthrough')
            if depth_msg.encoding == '16UC1':
                image = image.astype(np.float32) / 1000.0
            elif depth_msg.encoding != '32FC1':
                raise ValueError(f'不支持的深度图编码：{depth_msg.encoding}')
            valid = image[np.isfinite(image) & (image >= 0.2) & (image <= 8.0)]
            depth_metrics = {'encoding': depth_msg.encoding, 'width': depth_msg.width,
                             'height': depth_msg.height, 'frame_id': depth_msg.header.frame_id,
                             'valid_depth_pixel_count': int(valid.size),
                             'min_depth_m': float(valid.min()) if valid.size else None,
                             'median_depth_m': float(np.median(valid)) if valid.size else None,
                             'max_depth_m': float(valid.max()) if valid.size else None}
        camera_valid = bool(info and len(info.k) == 9 and all(math.isfinite(v) for v in info.k) and
                            info.k[0] > 0 and info.k[4] > 0 and depth_msg and
                            info.header.frame_id == depth_msg.header.frame_id)
        report = {
            'success': bool(scan_values and depth_metrics.get('valid_depth_pixel_count', 0) > 0 and
                            camera_valid and buffer.can_transform('base_link', 'depth_camera_optical_frame',
                                                                   rclpy.time.Time())),
            'scan_received': scan is not None,
            'scan_frame_id': scan.header.frame_id if scan else '',
            'scan_valid_ranges': len(scan_values),
            'scan_front_min_m': min(scan_values) if scan_values else None,
            'depth_received': depth_msg is not None,
            'camera_info_received': info is not None,
            'camera_intrinsics_valid': camera_valid,
            'base_to_depth_optical_tf': buffer.can_transform('base_link', 'depth_camera_optical_frame',
                                                              rclpy.time.Time()),
            'depth': depth_metrics,
            'data_source': 'gazebo',
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as file:
            json.dump(report, file, indent=2, ensure_ascii=False, allow_nan=False)
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report['success'] else 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
