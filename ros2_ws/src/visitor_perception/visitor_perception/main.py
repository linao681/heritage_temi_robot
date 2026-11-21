"""启动独立游客人数感知节点。"""

import argparse
import signal

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.signals import SignalHandlerOptions
import yaml

from .ros_visitor_node import VisitorPerceptionNode
from .visitor_monitor import VisitorConfig


def main(args=None):
    parser = argparse.ArgumentParser(description='匿名游客人数感知（Mock / 离线视频）')
    parser.add_argument('--config', default='config/system.yaml')
    options, ros_args = parser.parse_known_args(args)
    try:
        config = VisitorConfig.from_yaml(options.config)
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as error:
        parser.error(str(error))
    def shutdown_signal(_signum, _frame):
        raise KeyboardInterrupt

    # 避免默认 SIGTERM 在 executor 等待时并发销毁 ROS context。
    signal.signal(signal.SIGTERM, shutdown_signal)
    rclpy.init(args=ros_args, signal_handler_options=SignalHandlerOptions.NO)
    node = VisitorPerceptionNode(config)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
