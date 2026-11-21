# Visitor Perception 2.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建可独立验证的匿名模拟游客感知 ROS2 包。

**Architecture:** 纯 Python `VisitorMonitor` 实现稳定人数及队伍状态；单线程 ROS2 节点只对接 Topic，独立演示进程产生测试数据。

**Tech Stack:** Python 3.10、ROS2 Humble、ament_python、std_msgs、PyYAML、pytest。

## Global Constraints

- 仅 Mock 人数，不接入摄像头、身份识别、Android 或实机，不调用任何导览或运动服务。
- 采用既有项目专用工具链、独立本机 ROS Domain；不修改系统环境或之前三个 ROS2 包。
- 默认连续 3 个相同合法观测才稳定；2 秒无合法观测标为过期。未知不是零人。掉队/重新集合事件只在显式设置预期人数后发出。
- 当前工程无可用 Git 工作树，不创建仓库或提交；原地保留所有测试与日志。

### Task 1：纯 Python 感知判断

**Files:** `tests/test_visitor_monitor.py`、`ros2_ws/src/visitor_perception/visitor_perception/visitor_monitor.py`、`__init__.py`。

**Interfaces:** `VisitorConfig(stable_samples=3, stale_timeout_sec=2.0)`；`VisitorMonitor(config)`；`observe(count: int, now: float) -> list[str]`、`set_expected_count(count: int, now: float) -> list[str]`、`tick(now: float) -> list[str]`、`snapshot() -> dict`。状态及事件名见已批准 [设计](../specs/2026-11-19-visitor-perception-design.md)。

- [x] 写测试覆盖初始未知、稳定到来、单次噪声、离开、显式队伍、去重、重集合、非法输入、断流与恢复和配置校验。例：连续 `observe(3, 0.1)`、`observe(3, 0.2)`、`observe(3, 0.3)` 只在第三次返回 `['arrival']`。
- [x] `PYTHONPATH=ros2_ws/src/visitor_perception python3 -m pytest -q tests/test_visitor_monitor.py`，预期缺少模块而失败。
- [x] 实现配置验证与单调时间状态逻辑，按设计保持最后稳定值但过期时对外为 null。运行相同测试，所有用例通过。

### Task 2：ROS2 包与节点

**Files:** `tests/test_visitor_ros.py`、`ros2_ws/src/visitor_perception/{package.xml,setup.py,setup.cfg,resource/visitor_perception}`、`visitor_perception/{ros_visitor_node.py,main.py}`、`config/system.yaml`。

**Interfaces:** `VisitorPerceptionNode(config: VisitorConfig)`，订阅 `heritage/visitor/count`、`heritage/visitor/expected_count` 类型 Int32，发布 `heritage/visitor/status`、`heritage/visitor/events` 类型 String JSON。事件 JSON 加入 `event` 字符串，状态字段为 monitor 快照。

- [x] 测试真实 ROS2 节点与话题：启动本地域 232，发送 3 次 3 人观测，等待 `arrival` 与稳定状态；设置预期 3 后按顺序送 2、3 人，断流观察失效，恢复不误报。
- [x] `source /opt/ros/humble/setup.bash; PYTHONPATH=ros2_ws/src/visitor_perception python3 -m pytest -q tests/test_visitor_ros.py`，预期模块缺失。
- [x] 实现 ROS2 单线程节点回调、定时器和 YAML 加载，标准 ament_python 包与可执行 `visitor_perception`；默认配置 `visitor_perception: {stable_samples: 3, stale_timeout_sec: 2.0}`。`bash scripts/build_ros2.sh --packages-select visitor_perception`，加载安装目录并运行测试，预期通过。

### Task 3：独立演示与回归

**Files:** `scripts/demo_mock_visitors.py`、`docs/visitor_perception.md`、`docs/development_log.md`、`README.md`。

- [x] 演示使用隔离本地域 224，启动安装态节点，等待 Topic discovery，再发布 0 → 3 → 2 → 3 → 0 和预期人数 3/0；等待 `arrival`, `visitor_lost`, `regrouped`, `departure`，再验证 `data_stale`, `data_restored`，状态符合预期。写报告及独立节点日志到新建 `docs/runs/mock-visitors-...` 目录。
- [x] `source /opt/ros/humble/setup.bash; source ros2_ws/install/setup.bash; python3 scripts/demo_mock_visitors.py`，退出 0；从日志确认事件顺序与最终人数。
- [x] `ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=225 .venv/bin/python -m pytest -q tests`，Linux 全套回归及新增测试通过；记录本次构建、测试与演示日志。
- [x] 更新文档，注明视觉准确率、真实传感器和自动导览联动未完成。
