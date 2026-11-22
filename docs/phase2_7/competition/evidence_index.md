# 阶段 2.7 竞赛证据索引

基线：`057761908e386f3d0ba7a779d61b860a15debbda`。本阶段源代码未提交。以下证据来自独立 run 目录；历史阶段数据不会改标为本轮。

| 主题 | 状态 | 可复核证据（相对项目根） | 可支持的结论 | 不能支持的结论 |
|---|---|---|---|---|
| 新增三人入口至出口完整演示 | PASS_WITH_RISK | `docs/phase2_7/experiments/visitor-full-20261122-202055/{report.json,verification.json,live_evidence.jsonl,system/visitor_team.jsonl,post_domain.json}` | 504.840 秒、7/7 目标，三人实际运动、知识回答与模拟播报成功；6 次集合确认前静止及新会话恢复 | 脚本团队与模拟操作员；不证明视觉身份连续性、真实音频、实机安全或重复稳定性 |
| 构建和全量回归 | PASS | `docs/phase2_7/tests/late-fixes-20261122/ros2_build_final.log`、`full_suite_final.log`、`domain_pre_final.json`、`domain_post_final.json` | 7 包构建通过；487 passed、0 failed、0 skipped；domain230 前后空 | 不能替代 Gazebo 或 temi 实机安全验收 |
| E01 无干扰正常路线对照 | NOT_RUN | `docs/phase2_7/validation_matrix.md` | 主证据包含两轮完整动态导览 | 没有单独的无干扰对照路线 |
| 原 S01 目标 | FAIL（风险中止） | `docs/phase2_7/experiments/S01/20261122T041835Z-S01-r001/tour/scenario/truth.json` | 1.4 m 配置触发 `PREDICTED_GEOMETRY_RISK`，人物保留，受控中止 | 不能说原配置到达终点、恢复或完成路线 |
| S01 安全终点完整导览 | PASS_WITH_RISK | `docs/phase2_7/experiments/S01-SAFE-ENDPOINT/20261122T044704Z-S01-SAFE-ENDPOINT-r001/evidence_summary.json`、`docs/phase2_7/experiments/S01-SAFE-ENDPOINT/20261122T101824Z-S01-SAFE-ENDPOINT-r001/evidence_summary.json` | 两轮3.5 m安全终点，人物独立接近/持留/侧向离开；均五区路线7/7、COMPLETED | 两轮都未通过规定速度标定条件；不是7类稳定性/多速度/实机结论 |
| 人物持续接近/离开说明 | PASS_WITH_RISK | `docs/phase2_7/safety/continuous_approach.md` |
| 动态停车两轮观察 | PASS_WITH_RISK | `docs/phase2_7/safety/dynamic_stopping.md` |
| 停车距离和几何代理 | PASS_WITH_RISK | 同 run 的 `analysis/analysis.json`、`analysis/phase_timeline.csv`、`analysis/distance_speed.svg` | 请求响应约 0.901 s；真值最小中心距约 0.992 m，估算几何间隙约 0.175 m | 无接触反馈；估算间隙不是碰撞认证，也不是实体制动距离 |
| 第二轮停车分析 | PASS_WITH_RISK | `docs/phase2_7/experiments/S01-SAFE-ENDPOINT/20261122T101824Z-S01-SAFE-ENDPOINT-r001/analysis/analysis.json`、`analysis/recovery_validation.json` | 第二轮请求/确认、距离、速度条件和新 UUID 恢复均有原始来源 | 速度标定不达标且接触观测为空 |
| E06 恢复复核 | PASS_WITH_RISK | 同 run 的 `analysis/recovery_validation.json` | 旧 session 停车后，zone_1 以新 session 恢复；安全依据与原始文件哈希可追溯 | 不支持多轮恢复统计；CLEAR 的单纯接收先后不代表不安全 |
| 安全终点失败前序 | FAIL（保留） | `docs/phase2_7/experiments/S01-SAFE-ENDPOINT/20261122T042258Z-S01-SAFE-ENDPOINT-r001/`、`.../20261122T043735Z-S01-SAFE-ENDPOINT-r001/` | 前轮恢复判定失败，另一轮观察几何重叠 | 不得删除或覆盖失败轮次 |
| 速度标定 | PASS_WITH_RISK（标记未达标） | 同 run `analysis/analysis.json`、`evidence_summary.json` | 明确记录目标0.3 m/s窗口未达标，分析器保留风险 | 不可把该轮统计成0.3 m/s已校准通过 |
| E02 人数/拥挤限速 | NOT_RUN | `docs/phase2_7/validation_matrix.md` | 当前缺口有明确记录 | 不支持人数增加导致物理减速的结论 |
| E04 人物横穿 | NOT_RUN | `docs/phase2_7/validation_matrix.md` | 三种轨迹闭环未执行 | 不能用相机烟雾结果声称行人检测/避障成功 |
| E04 相机 A–D 消息链路 | PASS_WITH_RISK | `docs/phase2_7/experiments/camera_smoke_verified/{A,B,C,D}/` | 独立 RGB/Depth/CameraInfo/TF 冒烟；B 俯角 TF 已核验 | 不支持 YOLOX 召回、测距精度、配置优选或真实 temi 安装结论 |
| E07 三人团队掉队 | NOT_RUN | `docs/phase2_7/validation_matrix.md` | 未执行状态透明 | 不支持匿名成员连续性或人工重聚闭环 |
| 七轮导览稳定性 | NOT_RUN | `docs/phase2_7/stability/repeated_tours.csv`、`docs/phase2_7/final_report.md` | 14个运行尝试、2个完整动态导览、12个失败/未完成；7类配额未满足 | 不计算计划稳定性成功率 |
| 60秒性能对照 | NOT_RUN | `docs/phase2_7/validation_matrix.md` | 暂无样本 | 不报告 P50/P95、吞吐或优化收益 |
| 实时/记录可视化 | NOT_RUN | `visualization/ros_hall/`、`docs/phase2_7/competition/demo_guide.md` | 现有三维展厅可作场景页面 | 不把演示动画称为 ROS 实时/实验回放 |
| 实体 temi | HARDWARE_REQUIRED | `docs/phase2_7/final_report.md` | 本轮无硬件且未发送运动命令 | 不支持实体速度、制动、定位、SDK 或 TTS 结论 |

视频、截图和曲线只能来自这些原始记录。不要把多轮拼成单一运行，也不要把 `Mock Speak Action` 成功说成有真实声音。
