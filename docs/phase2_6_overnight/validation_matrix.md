# 验证矩阵（阶段 2.6–2.8）

| ID | 验证目标 | 本轮状态 | 证据 / 边界 |
|---|---|---|---|
| E01 | 正常五区导览、问答、出口 | 历史 PASS；本轮未重跑 | 阶段 2.5 [实验矩阵](../experiments/phase2_5/experiment_matrix.md)，Mock Speak Action，不代表真实播报 |
| E02 | 单人、3人、5人及局部拥挤下的保守限速 | NOT RUN | 有场景生成器；密度未标定，人数不能直接当密度；没有本轮 Nav2/odom 实验 |
| E03 | 动态人员靠近时更早减速与安全停车 | **PASS WITH RISK：一轮闭环复测** | [Domain 232 全路线复测](experiments/E03/approaching-232-20261122-final/audit_review.md)：人员距离约 1.831 m 且输入有效时触发硬停；约 1.05 s 后确认静止；停车请求后新 UUID 恢复，7/7 导航完成。减速残余阶段最小中心距 1.559 m，假设包络间隙代理 0.806 m。人物随后被冻结并移除，未测静止阶段继续接近；单速度/单站点/单次，旧 E03 间隙值不可作同条件前后对比 |
| E04 | 真实横穿、感知和避障/停车链路 | 第二轮完整 Gazebo 路线完成；复核为 PASS WITH RISK；第一次失败原样保留 | 第二轮：人物真值移动 3.000 m、7/7 导航目标、4 个有效 RGB-D 人员距离样本；36 个 LiDAR 障碍减速状态与人员因果未证实，末端 fail-closed 停车后恢复。见 [第二轮原始报告](experiments/E04/crossing-226-20261122-0213-retry1/report.json)、[归因复核](experiments/E04/crossing-226-20261122-0213-retry1/audit_review.md)、[第一轮失败](experiments/E04/crossing-226-20261122-0210/report.json) |
| E05 | 独立接近危险距离停车，识别距离阈值而非失效闭锁 | **PASS WITH RISK，限本次仿真条件** | 前五次失败仍保留；第六次 [Domain 232 停车下限 1.3 m 复测](experiments/E05/approaching-232-20261122-zone1-stop-floor-13/audit_review.md)：有效 RGB-D 距离 1.836 m 时发出人员阈值停车，Gazebo 最小中心距 1.586 m，假设包络间隙代理 0.833 m；odom 约 1.0 s 确认静止，导航用新 UUID 恢复并完成全路线。局限：单速度/单站点/单次；人物在停车请求后冻结，未测继续靠近静止机器人的间隙。上一轮负间隙代理失败见 `approaching-232-20261122-zone1-goal-bearing/audit_review.md` |
| E06 | 人员离开、CLEAR、自动恢复原目标并换新 UUID | 复核 PASS WITH RISK；原始运行器报告 FAIL 保留 | [原始报告](experiments/E06/leaving-226-20261122-0226/report.json) 的导览事件最终完成 wait→五区→exit；旧 UUID 停车确认、新 UUID 恢复原目标已观察到。停车由融合输入无效 fail-closed 触发，0.876 m 测距只证明同时存在近人观测；CLEAR 晚于新任务启动约 0.090 s。见[复核说明](experiments/E06/leaving-226-20261122-0226/audit_review.md) |
| E07 | 三人团队掉队/遮挡/重聚并人工确认 | 既有软件测试；Gazebo NOT RUN | 阶段 2.5 `visitor_assist.py` 与测试；人数恢复不能证明同一个匿名访客回归 |
| E08 | 感知断流 fail-closed | 历史 PASS；本轮未重跑 | 阶段 2.5 故障注入 CSV/报告；非本轮新运行 |
| E09 | Nav2 异常终止及旧会话隔离 | 历史 PASS；本轮未重跑 | 阶段 2.5 故障注入报告；非本轮新运行 |
| E10 | 人工取消、停车确认且不自动恢复 | 历史 PASS；本轮未重跑 | 阶段 2.5 人工取消记录；非本轮新运行 |
| E11 | 连续两人横穿 | NOT RUN | 无本轮集成运行 |
| E12 | 转弯时人物进入视场 | NOT RUN | 无本轮集成运行 |
| E13 | 短暂遮挡与过期处理 | NOT RUN | 无本轮集成运行 |
| E14 | LaserScan 有效空回波与断流区分 | NOT RUN | 无本轮集成运行 |
| E15 | 连续障碍与重新规划协同 | NOT RUN | 无本轮集成运行 |
| E16 | 游客靠近后停止与速度抖动 | NOT RUN | 无本轮集成运行 |
| E17 | 人员从侧面接近 | NOT RUN | 无本轮集成运行 |
| E18 | 低帧率、数据延迟 | NOT RUN | 无本轮集成运行 |
| E19 | 多次安全停车/恢复无旧任务残留 | NOT RUN | 无本轮集成运行 |
| E20 | 同场景重复性 | NOT RUN | 无本轮集成运行 |
| 动态相机覆盖 | URDF 视场几何分析 PASS；运行时 CameraInfo/TF 检查 NOT RUN | 脚本、SVG、报告 | 几何推算不代表 YOLOX 检测率；未更改 URDF |
| ROS2 构建 | 七个 ROS2 包构建成功 | PASS | 隔离 `/tmp` colcon 构建日志；详见最终报告 |
| ROS2/Python 回归 | **PASS：355 passed，0 failed，0 skipped，191.51 s** | 完成 | 最终日志 `/tmp/phase26_final_pytest_v10.log`；明确排除因缺少 Python `websockets` 依赖而无法运行的两个 WebSocket 测试文件；七包构建安装与日志见最终报告 |
| Android | 本轮未改 Android 源码 | NOT RUN | 不把之前阶段的 Gradle 结果当作本轮结果 |
| 实体 temi | 设备不存在 | NOT AVAILABLE | 无实机运动、制动、传感器、隐私/音频验收 |

## 测试口径

历史阶段 2.5 报告中的 341 项是旧快照。本轮最终回归为 355 passed、0 failed、0 skipped，耗时 191.51 s，原始日志 `/tmp/phase26_final_pytest_v10.log`。由于环境缺少 `websockets`，两份 WebSocket 测试文件通过 pytest 参数显式排除，不计入 355。测试运行使用仓库 `tests/` 目录并优先导入当前源码。单元测试不计入 Gazebo 实验通过数。
