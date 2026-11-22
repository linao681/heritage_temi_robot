# E06 人员离开与恢复复核

原始运行器报告 `report.json` 保持 `FAIL`，错误为当时的验收器未接受“感知数据无效或过期”这一停车原因。原始报告没有被改写。

## 复核结论：PASS WITH RISK

复核器使用同一份原始 `report.json`、Gazebo 真值和 ROS 事件，确认了以下事件：

- Gazebo 真值记录人物实际移动 3.889 m；人物移动窗口为单调时钟 57536.985–57552.794 s。
- 机器人在旧导航 UUID `bb30c571a019409d9b9f6a872edc326a` 执行 `zone_4` 时进入 `STOPPING`，并于 57538.545 s 收到同一 UUID 的有效 `STOP_CONFIRMED`。
- 视觉融合在停车请求附近记录到有效人员距离字段 0.876 m，但融合整体状态因稳定人数输入无效而触发 fail-closed；因此不能把这次停车归因为人员距离阈值。
- 控制器于 57540.868 s 请求恢复；导览以新 UUID `fbcf914ead0b4dd8a0c16ed3801afd5b` 从原目标 `zone_4` 重新导航，于 57540.873 s 开始。
- 有效 `CLEAR` 于 57540.963 s 到达，比新导航开始晚约 0.090 s。该顺序与理想的“先观察 CLEAR、再恢复”证据不同，因此保留风险标记。
- 独立导览事件最终记录 `COMPLETED`，路线为 `wait → zone_1 → zone_2 → zone_3 → zone_4 → zone_5 → exit`。原报告在组装最终摘要前被验收断言中断，所以顶层 `status` 仍为 `FAIL`；这不改变其内部保存的完成事件。

后续验收逻辑仅在具备邻近人员测距、停车确认、恢复请求、原目标的新 UUID 和恢复窗口内有效 `CLEAR` 时接受该恢复链。该逻辑将此记录分类为 `PASS_WITH_RISK / FAIL_CLOSED_WITH_NEAR_PERSON_OBSERVATION`，保留输入无效原因与 CLEAR 到达顺序的限制。它不构成实体 temi 验证，也不证明距离阈值停车已通过。
