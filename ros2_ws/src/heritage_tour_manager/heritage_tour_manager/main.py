"""启动导览 ROS2 节点，关闭时先等待控制任务结算。"""

import argparse
import logging
import signal
from threading import Event, Thread

import rclpy
import yaml
from rclpy.executors import MultiThreadedExecutor
from rclpy.signals import SignalHandlerOptions

from .ros_tour_node import HeritageTourNode
from .tour_config import TourConfig


def main(args=None) -> int:
    parser = argparse.ArgumentParser(description='非遗展示固定路线导览管理器')
    parser.add_argument('--config', default='config/system.yaml')
    parser.add_argument('--exhibits', default='config/exhibits.yaml')
    options, ros_args = parser.parse_known_args(args)
    try:
        config = TourConfig.from_yaml(options.exhibits, options.config)
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as error:
        parser.error(str(error))

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

    stop_requested = Event()

    def shutdown_signal(_signum, _frame):
        stop_requested.set()

    signal.signal(signal.SIGTERM, shutdown_signal)
    signal.signal(signal.SIGINT, shutdown_signal)
    rclpy.init(args=ros_args, signal_handler_options=SignalHandlerOptions.NO)
    node = HeritageTourNode(config)
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    # 保持 ROS executor 活动，让关闭期间的 STOP 与 Action 取消响应仍可被处理。
    thread = Thread(target=executor.spin, daemon=True)
    thread.start()
    try:
        node.get_logger().info('Tour Manager ready; awaiting explicit start')
        while thread.is_alive() and not stop_requested.wait(timeout=0.2):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        executor.shutdown(timeout_sec=5.0)
        thread.join(timeout=5.0)
        node.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
