"""命令行启动 ROS2 网关；由配置选择 Mock 或 WebSocket 代理。"""

import argparse
import logging
import os
import signal
from pathlib import Path

import rclpy
import yaml
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.signals import SignalHandlerOptions

from .mock_backend import MockConfig, MockTemiBackend
from .ros_gateway import TemiGatewayNode


def main(args=None) -> int:
    parser = argparse.ArgumentParser(description='temi ROS2 Gateway')
    parser.add_argument('--config', default='config/system.yaml', help='系统 YAML 配置路径')
    parser.add_argument('--backend', choices=('mock', 'websocket'), help='覆盖 YAML 中的后端选择')
    options, ros_args = parser.parse_known_args(args)
    try:
        with Path(options.config).open(encoding='utf-8') as file:
            gateway_config = yaml.safe_load(file)['gateway']
        mode = options.backend or gateway_config['backend']
        if mode == 'mock':
            backend = MockTemiBackend(MockConfig.from_yaml(options.config))
        elif mode == 'websocket':
            # Mock 不需要安装网络库，且 token 永远不写入配置文件。
            from .websocket_backend import WebSocketConfig, WebSocketTemiBackend
            backend = WebSocketTemiBackend(WebSocketConfig(**gateway_config['websocket']),
                                           os.environ.get('TEMI_BRIDGE_TOKEN', ''))
        else:
            raise ValueError('未知后端；请选择 mock 或 websocket')
        status_hz = float(gateway_config['status_hz'])
    except (OSError, ValueError, KeyError, ImportError, TypeError, yaml.YAMLError) as error:
        parser.error(str(error))

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    # 使用 Python 的 KeyboardInterrupt，先执行网关关闭，再关闭 ROS context。
    def shutdown_signal(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, shutdown_signal)
    rclpy.init(args=ros_args, signal_handler_options=SignalHandlerOptions.NO)
    gateway = None
    executor = None
    try:
        gateway = TemiGatewayNode(backend, status_hz=status_hz)
        executor = MultiThreadedExecutor(num_threads=4)
        executor.add_node(gateway)
        gateway.get_logger().info(f'Gateway started in {mode} mode')
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if gateway is not None:
            gateway.close()
        if executor is not None:
            executor.shutdown(timeout_sec=5.0)
        if gateway is not None:
            gateway.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
