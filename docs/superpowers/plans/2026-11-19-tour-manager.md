# Heritage Tour Manager Implementation Plan

**Goal:** 通过真实 ROS2 Gateway 让 Mock 完成入口、五展区、互动区、出口的导览，并支持游客及异常控制。

**Architecture:** 纯 Python `TourManager` 状态机只通过导航、语音、停止协议访问机器人；ROS2 `HeritageTourNode` 适配 Action/Service/Topic。路线、文字和阈值从 YAML 读取，状态/历史记录可经 ROS2 状态 Topic 观察。

**Tech Stack:** ROS2 Humble、Python 3.10、asyncio、PyYAML、rclpy、std_msgs、std_srvs、pytest。

## Global Constraints

- 实现 IDLE/GREETING/WAITING_CONSENT/PLANNING/NAVIGATING/EXPLAINING/QA/PAUSED/RETURNING/COMPLETED/ERROR，无硬件依赖。
- 固定 8 站；五个展区主题为示例，地点是虚拟名称，不虚构真实地图坐标。
- 暂停、掉队、取消、人工接管、低电量和断线必须终止本段任务；导航未确认停止时不能恢复。低电量返回配置安全入口，不宣称充电。
- QA 只提供互动等待，不实现虚构知识问答。人工通过 ROS2 Trigger 明确同意/拒绝、恢复或结束互动；Mock 完整流程可实际运行。
- 状态转换、访问地点、故障次数和最终结果记录到报告，单次命令控制有效期及停止符合已验证 Gateway 契约。

## Task 1: YAML 与独立状态机

**Files:** `config/exhibits.yaml`、`config/system.yaml`、`heritage_tour_manager/tour_config.py`、`tour_manager.py`、`tests/test_tour_manager.py`。

- [x] 先写配置及真实 Mock 后端行为测试（完整路线、拒绝、暂停恢复、掉队、取消、低电量、断线、故障、人工接管、超时）。
- [x] 实现配置校验、显式状态转换、控制请求优先级和任务取消清理。
- [x] 验证全部 13 项纯状态机测试通过，含失败与取消竞争、未确认、异常抛出。

## Task 2: ROS2 接入与运行入口

**Files:** `ros_tour_node.py`、本包 `main.py`、`package.xml`、`setup.py`、`setup.cfg`、`resource/heritage_tour_manager`、`tests/test_tour_ros_integration.py`、`scripts/demo_mock_tour.py`。

- [x] 实现实际 ROS2 ActionClient/STOP Service/RobotStatus 和 `heritage/tour` 状态与 Trigger 控制。
- [x] 在隔离本机 Domain 执行 ROS2 Gateway + Tour Node 的 5 项真实集成测试与 1 项未知终态测试。
- [x] 构建 3 个 ROS2 包，安装后完整回归 81 项通过，实际独立双进程默认速度 Mock 导览 19.505s、0 异常；记录 8 个完整导航事件及状态历史。
