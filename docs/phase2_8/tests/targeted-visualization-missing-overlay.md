# 定向测试启动错误记录

时间：2026-11-23（Asia/Shanghai）

首次运行 `tests/test_phase28_visualization_api.py tests/test_visualization_bridge.py tests/test_phase28_replay.py` 时，只加载了 `/opt/ros/humble/setup.bash`，没有加载本工作树的 `ros2_ws/install/setup.bash`。因此 9 项需要生成 ROS 自定义消息的导入失败：`ModuleNotFoundError: temi_interfaces`；回放4项通过。测试没有创建 ROS 节点或占用ROS Domain。

按完整 ROS 环境重新运行的结果见 [`targeted-visualization-final.log`](targeted-visualization-final.log)。该错误轮次保留，不视为代码失败或通过。
