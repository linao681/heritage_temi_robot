# Visitor Tour Integration 2.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mock 游客感知、Gateway 与导览状态机形成一次性迎宾及可人工恢复的安全闭环。

**Architecture:** 感知节点发布带稳定新鲜度的匿名人数；导览节点持有 `VisitorAssist` 协作策略，在既有 asyncio loop 内消费状态、调用既有导览控制。状态机本身负责守卫接受/恢复、防止未经同意的低电量返回。

**Tech Stack:** ROS2 Humble、Python 3.10、ament_python、pytest、现有 Action/Topic/Trigger。

## Global Constraints

- `tour.visitor_assist_enabled=false` 默认关闭；本轮只允许 Mock，ROS2 本机隔离通信，现有手动接口与 Android 不修改。
- 一次 arm 只触发一次迎宾；必须观察到 arm 后零到正变化；自动同意、自动恢复均禁止。
- 匿名人数不是身份验证；感知失效暂停但不抢占既有通信、低电量、人工接管等高优先级控制。
- 设计已确认：[2.2 设计](../specs/2026-11-19-visitor-tour-integration-design.md)。工程未初始化 Git，不创建仓库或提交。

### Task 1：稳定人数新鲜度

**Files:** `ros2_ws/src/visitor_perception/visitor_perception/visitor_monitor.py`, `tests/test_visitor_monitor.py`。

**Interface:** 现有 `snapshot()` 新增 `stable: bool`、`stable_fresh: bool`。`observe` 在稳定样本时刷新最后稳定确认时刻；`tick` 即使持续合法抖动也使其过期。

- [x] 写失败测试：稳定人数 3 后交替送 2/3 超过超时，`valid` 仍为真但 `stable_fresh` 为假；再次连续 3 人恢复两字段。
- [x] 运行新增用例，确认缺少字段失败。
- [x] 实现两个字段并复测，原有事件行为不变。

### Task 2：辅助导览策略与状态机守卫

**Files:** `ros2_ws/src/heritage_tour_manager/heritage_tour_manager/{visitor_assist.py,tour_manager.py,tour_config.py,ros_tour_node.py}`、`tests/test_visitor_tour_integration.py`、`tests/test_tour_manager.py`、`config/system.yaml`。

**Interfaces:** `VisitorAssist(manager, publish_expected, timeout)` 同一 loop 运行 `observe(snapshot)`、`robot_frame(frame)`、`tick()`、`arm()`、`manual_start()`、`cancel()`、`manual_takeover()`、`snapshot()`；`TourManager.start(*, visitor_guard=None)` 在辅助路径保存 guard，`consent(True)`、`resume()`及 PAUSED 恢复边界重验；`TourManager.visitor_source_lost()` 请求既有通信失效终止；`returning_low`、`consent_accepted` 提供只读状态。`heritage/tour/arm_visitor` 与 `visitor_assist` 状态只在启用时提供。

- [x] 写真实 ROS2 三节点集成测试：未 arm 不迎宾，arm 后 0→3；同意前无导航、预期未确认时拒绝 accept；队伍减少暂停/停止，人数恢复不自动继续，显式 resume 才继续。追加断流、心跳中断、持续抖动、禁用模式、拒绝及人工接管、低电量和源不符测试。
- [x] 运行新增用例（加载 Humble/项目 install），确认缺少配置/联动服务失败。
- [x] 实现守卫、策略和 ROS 订阅/发布，默认 false；`bash scripts/build_ros2.sh --packages-select visitor_perception heritage_tour_manager` 后从安装目录运行新增测试，通过。审查后增加 `can_arm`、旧恢复授权撤销和 STOP 等待期间优先级回归。

### Task 3：独立演示与完整回归

**Files:** `scripts/demo_visitor_tour.py`、`docs/visitor_tour_integration.md`、`README.md`、`docs/development_log.md`、`docs/architecture.md`。

- [x] 执行三独立进程（Mock Gateway、感知、导览）与模拟人数发布器：arm 后零→三人、显式 accept、导航期间两人触发 PAUSED、验证 resume 拒绝、重新集合后仍暂停、人工 resume、互动区显式 finish_qa、八站完成。使用独立 Domain 223 的仅本机通信；每次独立日志与 JSON 报告，专用配置启用模式。
- [x] `bash scripts/build_ros2.sh` 完整构建；`ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=225 .venv/bin/python -m pytest -q tests` 完整回归并保存 JUnit；验收独立演示报告中状态变化与明示控制（121 项通过）。
- [x] 更新使用说明、设计、日志、验收结果及下一阶段未完成内容。所有结果只陈述 Mock 行为。
