# 持续接近与离开恢复证据

## 验收范围

只评估阶段 2.7 的 Gazebo 人物运动与安全恢复闭环。人物由 Gazebo 模型真值/SetEntityState 回读确认；控制器感知值、机器人状态和人员真值分别保留。没有实体 temi，也没有接触传感器结果。

## 原 S01 失败

原始 S01 在 1.4 m 目标配置运行到人物靠近期间，轨迹包络检查预测几何风险，进入 `PREDICTED_GEOMETRY_RISK` 并中止。人物模型被保留供复核。这是安全保护触发的 FAIL，不是完整场景成功。证据：`../experiments/S01/20261122T041835Z-S01-r001/tour/scenario/truth.json`。

## 安全终点变体

最终运行 `../experiments/S01-SAFE-ENDPOINT/20261122T044704Z-S01-SAFE-ENDPOINT-r001/` 使用官方布局、机器人上限 0.3 m/s、人物 0.1 m/s、终点 3.5 m、到达后持留 2 s，再向左离开 3.1 m。Gazebo 真值确认人物依次经过 `WAIT_NAV → APPROACH → HOLD_TARGET → LEAVE → HOLD_CLEAR`，真实路程约 4.10 m；机器人进入安全停车后人物仍继续运动，最后人物仍留在场景中。

- 机器人停稳附近 Gazebo 真值中心距：1.182 m。
- 整个运动期最小中心距：0.992 m（LEAVE）。
- 保守二维外接圆间隙最小值：0.175 m（LEAVE）；正间隙不是接触认证。
- `geometry_risk=null`，`contact_observed=null`。
- 原 session `bc36466931b44206a9b7c7359f799a3e` 停车后，恢复证据通过独立复核；同一 `zone_1` 以新 session `b87d0b3078564615a36e2af390964441` 继续。CLEAR 接收在新 UUID 启动后，按验收计划不单独判失败。
- 路线 `wait → zone_1…zone_5 → exit` 完成 7/7 个目标，Tour Manager 状态 `COMPLETED`，用时 320.976 s。

详见 `../experiments/S01-SAFE-ENDPOINT/20261122T044704Z-S01-SAFE-ENDPOINT-r001/evidence_summary.json`、`tour/scenario/truth.json`、`analysis/recovery_validation.json`。前两次安全终点尝试仍分别保留恢复判定失败和几何重叠失败。

## 速度条件限制

规定的干扰前 2 s 速度窗口未形成：0.3 m/s 目标、20 个样本、覆盖 1.903 s、中位数约 0.0000198 m/s。分析器记录 `met=false`。因此这个闭环验证了持续运动/停车/恢复行为，但不能算 0.3 m/s 标定通过；其余速度档没有运行。
