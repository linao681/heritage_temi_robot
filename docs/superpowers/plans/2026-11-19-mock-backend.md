# MockTemiBackend Implementation Plan

**Goal:** 让统一后端在无实体机器人、无 Android 和无网络的情况下完成可观测的定时导航、语音及故障恢复。

**Architecture:** `MockTemiBackend` 使用单一 asyncio 事件循环、不可变 `RobotSnapshot`、每类活动任务独立的中断事件；虚拟位置与全部模拟参数由 `MockConfig` 和 `config/system.yaml` 提供。

**Tech Stack:** Python 3.10、asyncio、dataclasses、PyYAML、pytest、ROS2 Humble ament_python。

## Global Constraints

- 保持 `TemiBackend` 六操作契约；单个导航和单个播报可并行，STOP 仅停止运动；断线同时终结二者。
- 模拟地图坐标仅用于 `mock_map`，不能作为实体 temi 地图坐标使用。
- 默认导航异常概率为 0，提供显式 `inject_navigation_failure()`、`simulate_disconnect()` 与 `set_battery_percentage()`。
- 按真实单调时钟与速度更新位置，停止/取消/超时后不得继续移动；重连不重复执行旧命令。
- 仅安装或运行项目内包，不改系统 Python，不连接 Android 或实体机器人。

## Task 1: 配置和 Mock 后端

**Files:** `ros2_ws/src/temi_bridge/temi_bridge/mock_backend.py`、`ros2_ws/src/temi_bridge/package.xml`、`ros2_ws/src/temi_bridge/setup.py`、`config/system.yaml`、`tests/test_mock_backend.py`、`scripts/mock_backend_demo.py`。

**Produces:** `MockConfig.from_yaml(path)`、`MockTemiBackend(config)` 实现现有 `TemiBackend`，以及以上三个故障注入方法。

- [x] 编写配置、持续移动、停止、超时、故障、低电量、断线/重连、语音和取消测试；未实现时实际报 `ModuleNotFoundError`。
- [x] 实现 Mock 配置与异步状态机；不引入 ROS2 运行时对象。
- [x] 运行 Mock 测试并修复复核发现的立即重连/替换任务与并发取消竞态；20 项通过，`temi_bridge` 实际构建成功。
- [x] 从安装后的工作空间执行全部现有测试，实际 32 项通过；运行独立演示，记录连续位置、状态反馈、电量与语音结果。
- [x] 更新 README、架构和开发日志；标明此阶段只验证纯 Mock 后端，不声称已实现 ROS2 Action 服务端或实机驾驶。
