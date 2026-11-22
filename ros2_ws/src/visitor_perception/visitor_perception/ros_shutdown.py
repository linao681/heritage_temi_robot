"""Shared ROS executor shutdown handling for perception nodes."""
from rclpy._rclpy_pybind11 import RCLError
from rclpy.executors import ExternalShutdownException


def spin_node(rclpy, node):
    """Treat external context shutdown as normal, but surface live-context errors."""
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except RCLError:
        if rclpy.ok():
            raise
    finally:
        try:
            node.destroy_node()
        finally:
            rclpy.try_shutdown()
