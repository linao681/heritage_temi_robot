# Task 3：E06 恢复与 Nav2 安全审查

**结论：实现和针对性测试通过；E06 现场验收待做。** 未进行 Gazebo/Nav2 仿真、实体 temi 验证、提交或推送。未修改 Phase 2.6 原始记录或计划复选框。20 项审查见 [Nav2 专项审查](../safety/nav2_review.md)。

## 重放旧 E06

只读解析 `docs/phase2_6_overnight/experiments/E06/leaving-226-20261122-0226/` 下的 `events.json`、`report.json` 和 `experiment_data.csv`。以下时间均为秒，事件时刻是记录程序观测它的时间，不是控制节点实际消费时间。

| 事件 | 原始样本时间及局限 | 事件接收/记录单调时间 | CSV 的独立定期采样 |
|---|---|---:|---|
| 旧 UUID 第一次有效 STOP_CONFIRMED | 原始 odom 时间戳未保留；状态报告 odom age 0.015636 s，静止 0.590876 s | 57538.544594 | 无同条事件精确关联 |
| 恢复前最后一条已记录的有效融合变化 | 不含融合原始单调样本 ID；NO_PERSON_OBSERVED + 有效激光 1.612139 m，旧 STOP 仍确认 | 57540.813074 | 57540.873083 行保存融合年龄 0.354097 s；不同记录路径不能倒推出同一原始样本时间 |
| 请求前最后一条旧 UUID STOP_CONFIRMED | odom 原始时间戳未保留；状态报告 odom age 0.001747 s，静止 2.901778 s | 57540.855649 | 不独立关联 |
| 速度控制器恢复请求 | 旧状态输出未保存决策 ID、实际消费的样本 ID 或 clear_since | 57540.868000 | 57540.873083 行记录 recovery_requested=true |
| 原目标 zone_4 建立新 UUID | 旧 `bb30c571a019409d9b9f6a872edc326a` → 新 `fbcf914ead0b4dd8a0c16ed3801afd5b` | 57540.873104；Action going 57540.895230 | 57540.973380 行显式观察到新 UUID |
| 新 UUID 首次有效 CLEAR | 传输层建立新的 UUID 时把该 UUID 的停车状态初始化为 CLEAR；该次报告 odom age 0.000951 s | 57540.963369 | 不是恢复前的资格底稿 |

到达差为 0.090266 s。旧 STOP_CONFIRMED 和有效激光+视觉无观测在请求前已录到；两秒窗口内有 7 次融合变化记录，但记录器按变化抽样，无法证明速度控制器当时连续消费了哪批样本，也不能把 NO_PERSON_OBSERVED 解释为该人已确认离开。CLEAR 是新会话状态而非旧会话恢复先决信号；因此没有改排序/加命令延迟掩盖问题。可重复证明的原有问题是无效/倒序、断窗或 UUID 错配后仍沿用旧 hold。历史 E06 仍为原始 FAIL、复核 PASS WITH RISK。

## 实现和接口

- Speed policy 使用既有单调时间及配置的 recovery_hold_sec；失效、超时、输入倒序、定时中断和停车资格丢失重置窗口。恢复必须有当前被暂停会话的确认和新鲜静止 odom。每条融合回调（即使未到控制 timer）均可因近人、近障碍、旧 UUID 或旧样本撤销窗口；瞬时运动 odom 亦立即撤销。旧 UUID 不再接收速度命令。
- 保持原有手动 Trigger 接口和 ROS 消息定义。增加内部 Trigger `heritage/tour/pause_safety` / `resume_safety`，区分安全暂停、用户暂停和团队等待。速度输出 JSON 加入决策；Tour 状态回显资格确认 ID。速度端只发送一次与当前暂停和资格匹配的请求；服务端和恢复消费点再次验证，旧回执不会解锁新任务。请求前再次检查位姿、通信、人员与激光，拒绝旧确认、故障锁存、人工接管/待处理的取消。
- 决策在 `heritage/speed_control/status` 的 `recovery` JSON 中记录 `decision_id / stopped_session_id / original_target / evidence_sample_id / sample_age_sec / clear_since / hold_sec / odom_age_sec / position_age_sec / manual_latched / error_latched / request_sent_at / service_result / new_session_id`。样本 ID 为融合单调时间戳；position_age_sec 为保守融合龄，Nav2 侧独立检查 TF 源时钟。尚未收到服务结果/新会话时字段为 null。
- 传输层统一以连续新鲜静止 odom 确认 STOP，拒绝过期 TF，回滚并复核部分限速更新；失败不能解释为安全。odometry/STOP 校验原始 ROS 源时间和累计年龄，而非仅订阅接收时间；中断静止后重新建立窗口，若确认后实际运动（即便中间曾断流）锁存不安全。后端并发停止复用确认任务并拒绝重复 UUID。新导航等待旧调速事务结算并复核连接/STOP generation，过期速度返回失败；等待中的目标遇 STOP 不再提交；调用者取消时，已提交的 ROS 写入/回滚仍持有独立事务锁至结算，不能让新 UUID 提前通过。融合用实际来源时间或可用的单调年龄拒绝回放。
- 独立复核后进一步保留安全暂停 UUID 和 guard 直到 ROS `send_goal_async` 之前；从 checkpoint 到子任务启动，以及客户端等待服务可用后，均重新核对；若资格撤销，重新进入原安全暂停而不提交目标。并发取消优先于恢复。ROS 消息定义仍未修改。

## 复现与验证

仓库根目录执行。未启动任何 ROS 节点或其他域。

```bash
set -o pipefail
source /opt/ros/humble/setup.bash && source ros2_ws/install/setup.bash
export PYTHONPATH="$PWD/ros2_ws/src/temi_bridge:$PWD/ros2_ws/src/heritage_tour_manager:$PWD/ros2_ws/src/temi_speed_controller:$PWD/ros2_ws/src/visitor_perception:$PYTHONPATH"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/test_phase27_recovery.py tests/test_speed_controller.py tests/test_nav2_backend.py tests/test_nav2_arrival_stop.py tests/test_perception_fusion.py tests/test_tour_manager.py | tee /tmp/heritage-phase27-task3-targeted-final.log; archived copy: `../tests/task3-final/targeted.log` (SHA256 `657dddc3086a8873bfdb62f5479ba00528c985cb15091aa3ca922f911b7e1951`)
```

初次合并结果：退出 0，135 passed（12.30s）。独立复核与取消竞态修正后的最终合并结果：退出 0，155 passed（12.58s）。另有直接适配器回归（不启动任何 ROS 节点）：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/test_perception_ros_integration.py -k 'fused_input_source_allowance'`，退出 0，1 passed、1 deselected；项目内归档见 `../tests/task3-final/direct-adapter.log`（SHA256 `d1e08a50882fc930704900c76e61b764a054ed53e021a84471bce1f849a1d32c`）。

| 先失败的复现 | 退出/计数 | 日志 |
|---|---|---|
| `pytest -q tests/test_phase27_recovery.py`（初始 10 条） | 1 / 10 failed | `/tmp/heritage-phase27-task3-red-policy.log` |
| `pytest -q tests/test_nav2_backend.py tests/test_tour_manager.py -k 'concurrent_stop_requests or replay_task_id or automatic_resume_only or qualification_is_checked'` | 1 / 6 failed, 27 deselected | `/tmp/heritage-phase27-task3-red-tour-backend.log` |
| `pytest -q tests/test_phase27_recovery.py -k 'future or one_trigger'` | 1 / 2 failed, 11 deselected | `/tmp/heritage-phase27-task3-red-resume.log` |
| `pytest -q tests/test_nav2_arrival_stop.py` | 1 / 4 failed, 3 passed | `/tmp/heritage-phase27-task3-red-transport.log` |
| `pytest -q tests/test_perception_fusion.py -k 'delayed_clear or late_scan'` | 1 / 2 failed, 34 deselected | `/tmp/heritage-phase27-task3-red-fusion.log` |
| `pytest -q tests/test_phase27_recovery.py -k transient_invalid` | 1 / 1 failed, 13 deselected | `/tmp/heritage-phase27-task3-red-transient.log` |
| `pytest -q tests/test_tour_manager.py -k queued_at_resumed` | 1 / 1 failed, 25 deselected；修复后 1 passed | `/tmp/heritage-phase27-task3-red-goal-race.log`、`/tmp/heritage-phase27-task3-green-goal-race.log` |
| `pytest -q tests/test_phase27_recovery.py tests/test_nav2_backend.py tests/test_nav2_arrival_stop.py tests/test_perception_fusion.py -k 'between_ticks or transient_hazard or speed_transaction or stale_stamped or after_odom_gap or stale_stop_report'` | 1 / 11 failed, 2 passed, 64 deselected；修复后 13 passed | `/tmp/heritage-phase27-task3-red-review.log`、`/tmp/heritage-phase27-task3-green-review.log` |
| `pytest -q tests/test_tour_manager.py tests/test_nav2_backend.py -k 'revoked_at_resumed or waits_on_parameter'` | 1 / 2 failed, 35 deselected；修复后加测 queued_at_resumed 共 3 passed | `/tmp/heritage-phase27-task3-red-send-gate.log`、`/tmp/heritage-phase27-task3-green-send-gate.log` |
| `pytest -q tests/test_phase27_recovery.py tests/test_nav2_arrival_stop.py tests/test_perception_fusion.py -k 'source_delay or intervening_stale or never_refreshes'` | 1 / 3 failed, 68 deselected；修复后加 after_odom_gap 共 4 passed | `/tmp/heritage-phase27-task3-red-accumulated-age.log`、`/tmp/heritage-phase27-task3-green-accumulated-age.log` |
| `pytest -q tests/test_phase27_recovery.py -k navigation_guard_after_waiting` | 1 / 1 failed, 23 deselected；修复后 1 passed | `/tmp/heritage-phase27-task3-red-ros-send.log`、`/tmp/heritage-phase27-task3-green-ros-send.log` |
| `pytest -q tests/test_nav2_backend.py -k cancelled_speed_caller` | 1 / 1 failed, 10 deselected；修复后 1 passed | `/tmp/heritage-phase27-task3-red-cancelled-speed.log`、`/tmp/heritage-phase27-task3-green-cancelled-speed.log` |

上述 pytest 均用 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider` 执行，ROS 适配器测试加载上方 ROS 环境。旧 E06 数据仅通过 Python 标准库 JSON/CSV 读取。

## 交接

下一轮应在隔离域实跑 E06，并由记录器保存整条恢复 JSON 及来源时间/接收时间/采样时间，同时记录旧 UUID 的 STOP、新 UUID 接续原目标和地面真值；不要把新 UUID CLEAR 接收顺序作为硬失败条件。若新鲜 TF 门槛实际不满足，先记录 TF/odom 来源时钟和数值，不能扩大阈值掩盖未知状态。
