# E05 zone_1 人员停车阈值前后对比

比较对象：Domain 232 上两次 `approaching` 场景。两轮均使用 official layout、zone_1 导航目标、0.25 m/s 人形速度、相同目标朝向生成方式和 0.65 m 轨迹终点。主要控制差异是人员硬停下限由 0.65 m 提高到 1.3 m。每个设置只有一轮，结果用于定位与验证，不代表统计显著性或实体安全测量。

| 指标 | 调整前：`zone1-goal-bearing` | 调整后：`zone1-stop-floor-13` |
|---|---:|---:|
| Gazebo 人形移动路径 | 2.707 m | 1.459 m（收到安全停车后冻结） |
| 有效人员测距最小值 | 1.095 m，随后丢失 | 1.693 m；请求停车时约 1.836 m |
| 人员距离硬停 | 未触发 | 触发，控制原因 `近距离人员停车` |
| 停车时人员距离通道 | 无效 | 有效；融合总状态也有效 |
| 最小 Gazebo 中心距 | 0.436 m | 1.586 m |
| 假设包络间隙代理 | −0.317 m | +0.833 m |
| 实际停车原因 | LaserScan 障碍约 0.080 m 后触发；人员距离无效 | 人员距离输入下的阈值硬停 |
| odom 静止确认 | 有；但发生于极近交会之后 | 请求后约 1.0 s |
| 原导航恢复 | 有 | 有；zone_1 使用新 UUID 并完成原路线 |

## 解释

在本次仿真中，提高硬停下限后，停车请求从视觉测距丢失之后的近场障碍停车，提前到有效人员测距约 1.836 m 时的人员距离停车。最小中心距从 0.436 m 增至 1.586 m，按相同 0.753 m 假设包络总半径计算的间隙代理增约 1.150 m。

该差异来自一次调整前与一次调整后运行；人物轨迹在安全停车后被冻结，故它不包含真人持续靠近静止机器人时的后续距离变化。间隙代理依赖仿真位姿和尺寸假设，没有实体 temi 的制动、相机外参、SDK 延迟或碰撞接触测量。不能把这项仿真改善描述为实机安全认证，也不能用它替代 E03 独立复测、E05 多工况/重复性测试或 E06 的人员离开恢复验收。

## 证据

- 调整前审计：[`experiments/E05/approaching-232-20261122-zone1-goal-bearing/audit_review.md`](experiments/E05/approaching-232-20261122-zone1-goal-bearing/audit_review.md)
- 调整后审计：[`experiments/E05/approaching-232-20261122-zone1-stop-floor-13/audit_review.md`](experiments/E05/approaching-232-20261122-zone1-stop-floor-13/audit_review.md)
- 控制参数：`ros2_ws/src/temi_speed_controller/config/speed_config.yaml`
