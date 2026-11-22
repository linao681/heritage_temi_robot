# WP05 STOP / 恢复竞态软件验收

## 结果

**PASS_WITH_RISK（软件状态机与 ROS adapter 回归）**。定向套件 109 passed，日志为 [`tests/wp05-control-races.log`](../tests/wp05-control-races.log)。没有在 Gazebo 中采集完整请求/ACK/odom/UUID实停时序，所以物理停车竞态仍 NOT_RUN。

竞态回归发现并修复一个优先级缺陷：普通自动 `team_pause` 曾可替换正在等待确认的 `safety_pause`，从而丢失被停车的导航会话。现将安全暂停优先级置于自动团队暂停之上，同时用户暂停、取消、人工接管与故障仍按原有更高等级覆盖。

## 十二项用例映射

| # | 场景与判据 | 证据 | 结果 |
|---|---|---|---|
| 1 | 安全停车等待期间到达自动掉队消息，不得丢失安全暂停会话 | `test_phase28_control_races.py::test_automatic_team_pause_cannot_downgrade_safety_stop` | PASS |
| 2 | 人工暂停可覆盖自动安全暂停 | `test_phase28_control_races.py::test_manual_pause_supersedes_automatic_safety_pause` | PASS |
| 3 | 已发恢复后用户取消，不能再提交恢复导航 | `test_tour_manager.py::test_automatic_resume_only_accepts_current_safety_pause_and_not_pending_cancel[safety]` | PASS |
| 4 | 同一控制请求重复到达不重复排队 | `test_phase28_control_races.py::test_duplicate_pause_does_not_enqueue_another_control` | PASS |
| 5 | cancel ACK 不等于旧 Action 已进入终态；未确认旧任务时不释放事务 | `test_phase28_control_races.py::test_action_cancel_ack_alone_does_not_settle_old_goal`；`test_tour_manager.py::test_unconfirmed_action_cancellation_cannot_claim_idle` | PASS |
| 6 | 同一安全暂停的恢复服务只接受一次 | `test_phase28_control_races.py::test_safety_resume_requires_stationary_robot_and_is_one_shot` | PASS |
| 7 | 机器人仍运动时拒绝恢复 | `test_phase28_control_races.py::test_safety_resume_requires_stationary_robot_and_is_one_shot` | PASS |
| 8 | 陈旧、倒序里程计不能确认停车 | `test_phase28_control_races.py::test_stale_or_future_odom_cannot_confirm_a_stop`；`test_nav2_arrival_stop.py::test_arrival_is_not_confirmed_by_stale_odom` | PASS |
| 9 | 恢复期间传感器失效/样本过期清除连续安全窗口 | `test_phase27_recovery.py::test_recovery_interruption_restarts_hold`；`test_phase27_recovery.py::test_transient_invalid_fused_sample_between_ticks_breaks_the_hold` | PASS |
| 10 | 停车后路线目标改变，拒绝旧目标恢复资格 | `test_phase28_control_races.py::test_recovery_is_rejected_if_tour_target_changed_since_stop` | PASS |
| 11 | 旧调速事务晚到不能写入新导航会话 | `test_nav2_backend.py::test_new_uuid_waits_for_old_speed_transaction_and_stale_reply_is_rejected`；`test_nav2_backend.py::test_cancelled_speed_caller_keeps_parameter_transaction_serialized_until_settlement` | PASS |
| 12 | 同一展区重复集合两次仍保持路线指针和目标，不跳区 | `test_phase28_control_races.py::test_repeated_team_recovery_reuses_the_same_exhibit_without_skipping_route` | PASS |

现有 `tests/test_ros_gateway.py::test_concurrent_stops_wait_for_the_same_confirmation` 与 `::test_duplicate_stop_service_waits_for_active_stop_confirmation` 另外覆盖并发 STOP 合并；未把 service 成功 ACK 单独等同于真实停车。

## 边界

以上为确定性 Future/事件/ROS 软件测试，不是 Gazebo 真实里程计停车证据，不替代完整导览运行。相关代码仍需复验完整七包构建与最终全量测试；实体 temi 不在本轮测试范围。
