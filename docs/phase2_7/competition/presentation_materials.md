# 阶段 2.7 展示讲稿与素材清单

## 3 分钟讲解建议

**开场（约 20 秒）**
这是基于 ROS2 Humble、Nav2、Gazebo 和 Three.js 展厅页面的非遗导览机器人软件。本轮没有实体 temi，问答播报使用 Mock Speak Action。

**系统实现（约 40 秒）**
说明人物轨迹与机器人停车解耦、按 URDF/SDF 近似包络做风险保护、恢复前校验停车会话和安全证据。代码与软件回归证明边界逻辑，不等于硬件认证。

**本轮真实闭环（约 60 秒）**
展示 `S01-SAFE-ENDPOINT` 的两轮同配置结果：人员触发停车，人物仍继续运动并离开；恢复后同一 `zone_1` 目标使用新 UUID 继续，路线最终 COMPLETED，7/7 目标完成。指出原 S01 1.4 m 配置仍是几何风险 FAIL，安全终点变体不能覆盖它。

**量化结果和限制（约 35 秒）**
展示两轮停车请求到确认分别约 0.901 s / 0.997 s，人物最小中心距约 0.992 m / 0.989 m，二维几何间隙估算约 0.175 m / 0.172 m，接触观测均为 null。干扰前 0.3 m/s 校准窗口均未达标，因此该速度档没有通过标定。

**软件与后续（约 25 秒）**
展示七包构建及 487 项全目录测试结果。E02、E04 横穿、E07、七轮重复、性能对照、记录回放和实体 temi 尚未验收。

## 可用证据

- 两轮运行摘要：`../experiments/S01-SAFE-ENDPOINT/20261122T044704Z-S01-SAFE-ENDPOINT-r001/evidence_summary.json`、`../experiments/S01-SAFE-ENDPOINT/20261122T101824Z-S01-SAFE-ENDPOINT-r001/evidence_summary.json`。
- 动态人物真值与原始报告：同目录下 `tour/scenario/truth.json`、`tour/report.json`、`tour/events.json`。
- 停车/距离分析：`analysis/analysis.json`、`analysis/phase_timeline.csv`、`analysis/speed_comparison.csv`、`analysis/distance_speed.svg`。
- 恢复独立复核：`analysis/recovery_validation.json`，源文件 SHA256 写在 JSON 中。
- ROS2 构建与全量回归：`../tests/late-fixes-20261122/ros2_build_final.log`、`full_suite_final.log`。
- 相机消息冒烟：`../experiments/camera_smoke_verified/{A,B,C,D}/`。
- 状态与局限：`../validation_matrix.md`、`../final_report.md`、`evidence_index.md`。

## 尚无的素材

E02 多人数物理限速、E04 人物横穿 RGB 框/测距比较、E07 三人团队掉队、7 轮稳定性统计、60 秒性能基准、相机 A–D 人体检测比较、真实 ROS 回放截图和实体 temi 视频均未采集。不得制作或拼接成“实测成功”素材。
