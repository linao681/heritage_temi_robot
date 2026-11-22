# Phase 2.7：Nav2 导航与安全恢复专项审查

范围：指定包源代码和针对性测试。下列“通过”指本轮静态检查或指定自动化用例通过，不代表实体 temi、端到端 DDS 或 Gazebo 验收通过。E06 原始记录仍保留原结论。

| # | 风险 | 证据和可复现用例 | 结论 / 修复 |
|---|---|---|---|
| 1 | Action 取消竞态 | `Nav2Transport.stop` 等待迟到的接受结果、取消和终态；`_RosTourRobot._settle_goal` 保持旧 Action 占用直到终态。后端用例 `test_cancelling_navigation_stops_transport_and_unlocks`。 | 单测覆盖取消后释放导航；未实测接受/取消 DDS 时序。超时、取消、普通 STOP 共享后端停止任务。 |
| 2 | 两路同时停车 | `test_concurrent_stop_requests_share_the_same_confirmation`：旧后端第二个请求返回失败。 | 已修：共享 shielded STOP future，动作确认不重复消费。外层 Gateway 对两个独立 STOP RPC 仍可回第二路失败，超出本轮文件范围。 |
| 3 | 旧停车确认与新 UUID | `test_stop_confirmation_from_old_navigation_session_is_ignored` 及 `test_recovery_interruption_restarts_hold` 的错配 UUID 参数。 | 已修：整个 hold 要求旧 UUID 的持续有效 STOP；服务端再次比较暂停 UUID 和最新融合确认。新 UUID 不继承旧停车确认。 |
| 4 | odom 过期 | `test_transport_uses_stop_odom_freshness_at_navigation_reentry`、`test_arrival_is_not_confirmed_by_stale_odom`、`test_fresh_arrival_of_stale_stamped_odom_cannot_qualify_stop`、`test_speed_adapter_odom_age_keeps_source_delay_after_receipt`。 | 已修：导航、停稳和恢复使用本地 monotonic 龄及 ROS 源时间的累计年龄；过期、倒序及重复源戳不续期。仿真时钟重置需现场验证。 |
| 5 | TF 过期 | `test_transport_rejects_stale_tf_even_if_transform_is_available`：缓冲仍可查询但数据年龄 1 s。 | 已修：按节点 ROS 时间检查 TF 源时间，超过 0.5 s 或未来时间不使用；查询间失效时返回无定位。需 Gazebo 验证配置下变换时效。 |
| 6 | 感知数据倒序 | `test_delayed_clear_person_observation_cannot_replace_newer_person`、`test_late_scan_does_not_make_previous_obstacle_safe`、恢复样本倒序与时钟回退用例。 | 已修：RGB-D、激光和融合证据拒绝倒序；hold 清零。 |
| 7 | 转弯时的角速度 | `test_recovery_interruption_restarts_hold` 中线速度为零、角速度 0.07 rad/s 的情况；Transport 双阈值。 | 角速度 ≥0.05 rad/s 不得确认连续静止，恢复二次使用新鲜线/角速度。 |
| 8 | 恢复被重复发送 | `test_only_acknowledged_recovery_can_send_one_trigger`、`test_stale_resume_future_cannot_change_new_session`、`test_new_uuid_waits_for_old_speed_transaction_and_stale_reply_is_rejected`。 | 已修：每条决策一次请求，一次一个在途 future；服务端也拒绝重复决策；新 UUID 等待旧调速事务结算。 |
| 9 | Nav2 动态参数未更新 | `test_failed_nav2_parameter_readback_rolls_back_both_servers`：服务成功回执但读回错误。 | 已修：回执及全参数读回必须一致；不一致恢复原值，不把失败当作已应用。 |
| 10 | 部分速度参数修改后的回滚 | `Nav2Transport.set_speed` 的 controller/smoother 两端更新及读回；同一回归模拟写入后的不一致；`test_new_uuid_waits_for_old_speed_transaction_and_stale_reply_is_rejected`、`test_cancelled_speed_caller_keeps_parameter_transaction_serialized_until_settlement`。 | 已修：两端统一回滚并复核；不确定的晚写入或回滚失败锁存不安全；旧事务锁跨调用者取消维持至结算，新会话不得并行。未实测远端 RPC 超时。 |
| 11 | 融合状态短时失效 | `test_transient_invalid_fused_sample_between_ticks_breaks_the_hold`、`test_tour_cannot_forget_transient_hazard_after_recovery_proposal`。 | 已修：定时读取之间收到无效融合或瞬时有效近人、近障碍、倒序数据也要重新开始；独立的导览回调保留最后中断时间。 |
| 12 | 人员距离突变 | `test_approaching_person_trend_raises_stop_distance_using_new_samples_only`、`test_regressed_person_timestamp_clears_approach_estimate`。 | 短时接近速度被限幅，增加动态制动距离；单个高读数不能替代完整 hold。跳变真实场景尚未验证。 |
| 13 | YOLOX 连续漏检 | `test_valid_empty_scene_has_no_person_distance_but_remains_control_valid`、`test_empty_camera_observation_cannot_mask_invalid_laser` 和恢复无有效激光参数。 | `NO_PERSON_OBSERVED` 只是视觉未观测；无独立有效且安全激光不得恢复。激光覆盖外的漏检仍是物理限制。 |
| 14 | LaserScan 正无穷 | `test_clear_positive_infinity_scan_is_a_valid_range_max_bound`；非法回波 `test_rejects_negative_or_nonfinite_laser_ranges_as_sensor_failure`。 | 保留现有协议：仅有效前向扇区内 +∞ 表示量程内无回波，以 range_max 作为下界；NaN/−∞/非法范围不算有效。 |
| 15 | 多 ROS 回调并发 | 速度原使用可重入回调和多线程 executor；`test_stale_resume_future_cannot_change_new_session`、transient-fusion 用例。 | 速度控制回调串行；Tour 状态只在同一 asyncio loop 更新；Nav2 odom 更新和 STOP 确认共用锁。未压测 DDS。 |
| 16 | 断线后旧任务重放 | `test_backend_does_not_replay_task_id_after_reconnect`、`test_replayed_navigation_cannot_reopen_retired_uuid`。 | 已修：进程内已处理的 UUID 不因重连而重新开放；跨进程重启的任务历史未持久化。 |
| 17 | 人工取消与自动恢复同 tick | `test_automatic_resume_only_accepts_current_safety_pause_and_not_pending_cancel`、`test_cancel_queued_at_resumed_navigation_transition_prevents_goal_submission`、`test_recovery_guard_revoked_at_resumed_transition_keeps_original_pause`、`test_ros_action_rechecks_navigation_guard_after_waiting_for_server`、`test_stop_while_new_goal_waits_on_parameter_transaction_cancels_that_goal`。 | 已修：只允许安全暂停自动恢复，拒绝人工、团队等待和高级控制；从 checkpoint 到 ROS Action 实际提交都再次核验，未提交目标可返回原安全暂停。 |
| 18 | 已暂停收到旧导航完成 | `TourManager._operate` 在进入暂停前终结旧 operation，恢复重跑当前段；`test_terminal_navigation_event_clears_old_session_id`。 | 旧完成不触发暂停解除；ROS Action 迟到跨话题到达顺序仍需现场回归。 |
| 19 | STOP_CONFIRMED 后 odom 再次有运动 | `test_confirmed_stop_after_odom_gap_requires_a_new_stationary_window`、`test_motion_after_confirmation_is_latched_even_after_intervening_stale_odom`、`test_fused_publication_never_refreshes_old_stop_odom_age`。 | 已修：断流清除旧静止资格，重新要求连续 0.5 s；确认后线/角速度运动仍须失败锁存，即使中间有无效样本；重复融合发布不能延长底层 STOP 的 odom 有效龄。 |
| 20 | 传感器恢复冷启动 | `test_idle_startup_does_not_latch_before_navigation_and_sensors_are_ready`、`test_lidar_or_depth_stream_timeout_never_means_clear_space_or_far_people`、hold 间断回归。 | 已修：收到消息不等于连续有效，缺任何一项不能开始或延续 hold；冷启动仍须真实运行确认。 |

## 未关闭的现场门槛

- 未运行 Gazebo/Nav2、未连接实体 temi。需要隔离环境实跑 E06，记录同一人物持续运动、完整连续 hold、服务确认和新 UUID 继续原目标。
- 外层 Gateway 的独立 STOP RPC 拒绝第二路、跨进程旧任务持久化以及生产 DDS 的传输/故障注入不属于本轮证明。
- ROS 位置回执没有单独暴露 TF 源时间给 speed controller；Nav2 按本地 ROS 时间单独检查 TF 新鲜度，恢复证据中的 position_age_sec 是融合输入龄（不是独立真实 TF 源龄）。
