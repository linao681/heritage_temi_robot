# ROS2 Gateway and WebSocket Protocol Implementation Plan

**Goal:** 使用真实 ROS2 Action、Service 和 Topic 驱动 Mock，并提供认证、异步反馈与断线恢复的 Android 通信入口。

**Architecture:** `TemiGatewayNode` 使用独立 asyncio 后端线程和 ROS2 MultiThreadedExecutor；Mock 与 Linux `WebSocketTemiBackend` 同样实现 `TemiBackend`。JSON 协议独立定义，Android 客户端后续按协议实现真正 SDK 调用。

**Tech Stack:** ROS2 Humble、Python 3.10、rclpy、asyncio、websockets 16.1.1、pytest。

## Global Constraints

- 默认 `mock`，不依赖 Android、WebSocket 服务或实体设备；控制端口默认只绑定 `127.0.0.1`，显式私有 IPv4 局域网地址可用，不允许公网或通配绑定。
- 独立 `.venv` 安装 `websockets==16.1.1`，不改变系统 Python；认证 token 不写入 YAML 或日志。
- ROS2 命名：`temi/robot_status`、`temi/navigation_status`、`temi/navigate_to`、`temi/speak`、`temi/stop`。Action 真实反馈和终态，STOP 高优先级且不停止语音。
- WS Android 客户端主动连接、单客户端、认证、版本握手、状态同步、WebSocket ping/pong、命令 UUID、ACK、超时、过期、重复命令拒绝、断线不重放。
- 无实体设备：所有真实 SDK 调用、Android 自动重连和真实安全行为仍标记 `HARDWARE_REQUIRED` 或后续阶段。

## Task 1: ROS2 Gateway

**Files:** `ros2_ws/src/temi_bridge/temi_bridge/ros_gateway.py`、`tests/test_ros_gateway.py`。

**Produces:** `TemiGatewayNode(backend: TemiBackend, status_hz: float=10.0)`，`close()`。

- [x] 先编写真正的 rclpy client/server 测试，初始缺失模块测试失败。
- [x] 实现 ROS2 Topic、ActionServer、Service 和后端事件循环线程；单独验证 Mock 导航、状态、语音、STOP、异常与取消。审查后补齐 12 项测试。

## Task 2: WebSocket JSON 协议和代理后端

**Files:** `protocol.py`、`websocket_backend.py`、`tests/test_websocket_backend.py`（Python 文件均位于 `temi_bridge/temi_bridge` 中，测试在项目根 `tests`）。

**Produces:** `WebSocketConfig(...)`、`WebSocketTemiBackend(config, token)`，通过 `/temi` 连接，符合 `TemiBackend` 契约。

- [x] 先编写真实 loopback WebSocket 测试，初始缺失模块测试失败：认证、状态握手、命令 ACK、反馈、重复和失效 ID、超时、STOP、取消、连接状态恢复。
- [x] 实现 JSON 验证与客户端会话，限制私有绑定、消息大小和认证，保留已发送 ID 有限时间，按单调时间判定 ACK/结果期限；补齐审查发现的停车确认和状态同步异常。
- [x] 16 项真实 WebSocket 客户端测试使用模拟 Android 客户端，不连接硬件或外网。

## Task 3: 项目集成和回归

**Files:** `gateway_main.py`、`package.xml`、`setup.py`、`requirements-websocket.txt`、`config/system.yaml`、`docs/communication_protocol.md`、`README.md`、`docs/development_log.md`。

- [x] 添加 CLI `temi_gateway --config config/system.yaml [--backend mock|websocket]`，用配置切换，不改导览逻辑。
- [x] 实际构建两个 ROS2 包，安装后 62 项测试全部通过；运行独立 ROS2 Gateway 进程、跨进程 action/service/topic 客户端，以及 ROS2 → WS → 模拟 Android 端到端闭环。
- [x] 记录构建、实际通信、异常测试结果及 Android H/W 边界。
