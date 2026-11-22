import sys
from pathlib import Path

import pytest
from rclpy._rclpy_pybind11 import RCLError
from rclpy.executors import ExternalShutdownException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros2_ws/src/visitor_perception'))

from visitor_perception.ros_shutdown import spin_node


class FakeNode:
    def __init__(self):
        self.destroyed = False

    def destroy_node(self):
        self.destroyed = True


class FakeRclpy:
    def __init__(self, error, context_ok):
        self.error = error
        self.context_ok = context_ok
        self.shutdown_called = False

    def spin(self, _node):
        raise self.error

    def ok(self):
        return self.context_ok

    def try_shutdown(self):
        self.shutdown_called = True


@pytest.mark.parametrize('error', [KeyboardInterrupt(), ExternalShutdownException()])
def test_expected_ros_shutdown_exits_without_traceback_and_cleans_node(error):
    ros = FakeRclpy(error, context_ok=False)
    node = FakeNode()

    spin_node(ros, node)

    assert node.destroyed
    assert ros.shutdown_called


def test_invalid_context_publish_error_is_suppressed_after_cleanup():
    ros = FakeRclpy(RCLError('publisher context is invalid'), context_ok=False)
    node = FakeNode()

    spin_node(ros, node)

    assert node.destroyed
    assert ros.shutdown_called


def test_runtime_error_while_ros_context_is_live_is_not_hidden():
    ros = FakeRclpy(RuntimeError('unexpected callback failure'), context_ok=True)
    node = FakeNode()

    with pytest.raises(RuntimeError, match='unexpected callback failure'):
        spin_node(ros, node)

    assert node.destroyed
    assert ros.shutdown_called
