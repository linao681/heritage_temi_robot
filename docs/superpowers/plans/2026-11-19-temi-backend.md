# Temi Backend Contract Implementation Plan

**Goal:** 建立可供 Mock 和 WebSocket Real 后端共同实现的 Python 抽象契约，不依赖 Android 或 ROS2 运行时对象。

**Architecture:** `temi_bridge` 为 ROS2 `ament_python` 包。`TemiBackend` 使用 `asyncio` 风格的抽象方法，`get_status()` 返回不可变快照，导航和播报以命令 ID 及反馈回调形成异步结果。真实硬件 API 仅在 Android 端实现。

**Tech Stack:** Python 3.10、ABC、dataclasses、asyncio、ament_python、pytest。

## Global Constraints

- 保持 `connect()`、`disconnect()`、`navigate_to()`、`stop()`、`speak()`、`get_status()` 六个必要接口；不实现在本轮之外的感知、知识库或实体操作。
- 导航、播报和停止均可异步等待；停止不能等待活动导航完成后才执行。
- `task_id` 为调用方生成的唯一命令 ID；状态中电量为 `0~100` 或未知 `-1`，位置单位与 ROS2 `RobotStatus` 一致。
- 本阶段仅验证抽象接口和类型；Mock 实现、ROS2 Action 服务端及 Android 实机均不冒充完成。

## Task 1: 后端契约及 ament_python 包

**Files:** `ros2_ws/src/temi_bridge/package.xml`、`setup.py`、`setup.cfg`、`resource/temi_bridge`、`temi_bridge/__init__.py`、`temi_bridge/backend.py`、`tests/test_temi_backend.py`。

**Produces:** `TemiBackend`、`RobotSnapshot`、`TaskResult`、`NavigationFeedback`、`SpeechFeedback`。

- [x] 先编写 ABC、签名、数据模型及不可变状态的验收测试，未实现时实际失败且报 `ModuleNotFoundError`。
- [x] 实现上述最小 Python 类型及六个抽象方法，配置标准 `ament_python` 包，不添加无效节点或入口。
- [x] 执行 `bash scripts/build_ros2.sh --packages-select temi_bridge`，实际 `1 package finished [30.7s]`。
- [x] 载入工作空间 `source ros2_ws/install/setup.bash`，与接口包测试回归执行，实际 12 项通过。
- [x] 使用 `ros2 pkg prefix temi_bridge` 确认安装，更新架构与开发日志。

项目尚无独立 Git 仓库，本阶段不提交、不修改第三方仓库。
