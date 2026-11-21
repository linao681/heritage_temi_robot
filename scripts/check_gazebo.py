"""Read-only Gazebo sensor/TF readiness check; no movement commands."""
import json
import math
from pathlib import Path
import time

import rclpy
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener


def main():
    rclpy.init()
    node = rclpy.create_node('hall_readiness_check')
    received = {}
    node.create_subscription(Odometry, 'odom', lambda msg: received.update(odom=msg), 10)
    node.create_subscription(LaserScan, 'scan', lambda msg: received.update(scan=msg),
                             qos_profile_sensor_data)
    buffer = Buffer()
    listener = TransformListener(buffer, node)
    deadline = time.monotonic() + 30
    success = False
    try:
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if {'odom', 'scan'} <= received.keys() and buffer.can_transform(
                    'odom', 'laser_link', rclpy.time.Time()):
                scan = received['scan']
                success = len(scan.ranges) == 360 and any(
                    math.isfinite(value) and scan.range_min <= value <= scan.range_max
                    for value in scan.ranges)
                if success:
                    break
        report = {'success': success, 'scan_samples': len(received['scan'].ranges) if 'scan' in received else 0,
                  'scan_frame': received['scan'].header.frame_id if 'scan' in received else '',
                  'odom_received': 'odom' in received,
                  'odom_to_laser': buffer.can_transform('odom', 'laser_link', rclpy.time.Time())}
        directory = Path(__file__).resolve().parents[1] / 'docs/acceptance/gazebo'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'readiness.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
        return 0 if success else 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
