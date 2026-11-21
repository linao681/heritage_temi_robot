# 阶段 2.5 实验矩阵

## 汇总

**4 PASS / 1 PASS WITH RISK / 1 FAIL / 4 NOT RUN；将带风险的 E03 计入时为 5/10（50%）。** 通过项中包含一条完整五区路线、一次动态靠近路线和三项实际 ROS 2 故障/停止注入。单元测试不计作 Gazebo 集成试验。所有失败数据保留在独立目录。

| 编号 | 初始状态与实际输入 | 预期 | 实际结果 | 状态 | 证据 |
|---|---|---|---|---|---|
| E01 | 官方展厅新启动；相机入口计数稳定；测试操作员在等待同意后接受；提交一条潮州音乐文本问题 | 正常巡航、逐站到达与停稳、问答后继续至出口 | `wait → zone_1..zone_5 → exit`，7/7 Nav2 完成，272.552 s，最终 `COMPLETED`、error_count 0；一段安全停车确认后自动恢复。TTS 为 Mock Action | PASS | [report](clean_tour/20261121-222535/report.json)、[events](clean_tour/20261121-222535/events.json)、[CSV](clean_tour/20261121-222535/experiment_data.csv)、[曲线](clean_tour/20261121-222535/speed_curve.png) |
| E02 | 没有在运行导航期间完成稳定的 crowd 增加注入 | 人数增加时降低速度，必要时停车 | 有 `crowded` 场景生成器，但没有可验收的 Nav2 导航期 Crowd 实验记录 | NOT RUN | 生成器：[`spawn_people_scenario.py`](../../../scripts/spawn_people_scenario.py) |
| E03 | zone_3 导航中，从 Gazebo 位姿锚定人物并以 0.2 m/s 实际移动；seed 0；RGB→YOLOX→RGB-D 链路接收 | 正常/减速/停车确认/等待，人员离开或恢复后继续路线 | 相机候选检出 110/117（94.0%）；最近 RGB-D 估计 1.201 m；感知失效后真实安全停车确认；确认时 `cmd_vel=0`。Gazebo 中心距最小 0.883 m、估算表面间隙 0.269 m。之后完整路线 7/7 完成、无人工故障复位。人物离开视场后由失效停车触发，近距离仍是风险 | PASS（有距离风险） | [tour report](clean_tour/20261122-0008-e03-late-stop-fix-delay8/report.json)、[truth](dynamic_people/approaching/20261122-0008-late-stop-fix-delay8/truth.json)、[monitor](dynamic_people/approaching/20261122-0008-late-stop-fix-delay8/monitor.json)、[CSV](dynamic_people/approaching/20261122-0008-late-stop-fix-delay8/segment.csv)、[speed](dynamic_people/approaching/20261122-0008-late-stop-fix-delay8/speed_curve.png)、[distance](dynamic_people/approaching/20261122-0008-late-stop-fix-delay8/distance_curve.png) |
| E04 | zone_4 横穿试验；实际启动 crossing 人物模型服务 | YOLOX 检出横穿、Nav2 避让或停车、无碰撞并安全恢复 | 首次试验未能从 `/gazebo/model_states` 确认人物位姿；后续监测器启动时已错过 zone_4，没有产生有效输入；不把这次结果算作感知通过 | FAIL | [失败真值](dynamic_people/crossing/20261121-224015/truth.json)、[未运行监测](dynamic_people/crossing/20261122-0011-e04-run2/monitor.json) |
| E05 | 没有独立执行危险距离注入；E03 的靠近实验被安全停车冻结 | 人进入危险距离时在碰撞前停车并确认 | E03 的记录出现 0.269 m 估算表面间隙，但停止由人物离开视觉有效区后的感知失效触发；未验证专门的危险阈值试验 | NOT RUN | 关联证据：[E03 truth](dynamic_people/approaching/20261122-0008-late-stop-fix-delay8/truth.json)、[E03 CSV](dynamic_people/approaching/20261122-0008-late-stop-fix-delay8/segment.csv) |
| E06 | 监测窗口要求机器人在 `RETURNING/exit` 段且满足位置与朝向条件 | 人离开后确认人数稳定、按策略恢复导航，新 UUID 生效 | 未捕获符合条件的动态注入窗口，没有伪造人物离开或恢复结果 | NOT RUN | [monitor](dynamic_people/leaving/20261122-0013-e06-run1/monitor.json) |
| E07 | 3 人团队掉队与重新集合的 Gazebo 试验未运行 | 稳定人数变化暂停；队伍稳定恢复后由人工确认继续；不推断身份 | `camera` 计数 + `map` 帧 + 缺员暂停/人工恢复已有回归用例通过，但没有 Gazebo 团队轨迹、检测日志或真实 ROS 运行记录，故不计集成通过 | NOT RUN | [单元测试](../../../tests/test_tour_manager.py)、[`visitor_assist.py`](../../../ros2_ws/src/heritage_tour_manager/heritage_tour_manager/visitor_assist.py) |
| E08 | Domain 225 项目进程组内，对 visitor_perception 实际执行 SIGSTOP/SIGCONT 3.004 s，覆盖数据记录 | 断流不能当作空场；停稳等待，数据恢复后按策略恢复 | 真实 ROS 记录覆盖 3.004 s 故障，融合无效输入触发停车；恢复后回到等待/恢复链路 | PASS | [故障注入](robustness/sensor_dropout/20261121-2258/fault_injection.json)、[CSV](robustness/sensor_dropout/20261121-2258/experiment_data.csv)、[状态](robustness/sensor_dropout/20261121-2258/state_transitions.json)、[曲线](robustness/sensor_dropout/20261121-2258/speed_curve.png) |
| E09 | 调用实际 Nav2 `NavigateToPose` 目标 `(100,100)`；随后提交旧导航 UUID 调速命令 | Nav2 异常进入终态，旧会话命令拒绝，速度状态保持安全 | Nav2 接受后以状态 6 `ABORTED` 结束；旧 UUID 命令拒绝、返回码 -1；记录最大里程计线速度 0.0543 m/s | PASS | [原始报告](robustness/navigation_failure/20261121-2305/report.json)、[odom](robustness/navigation_failure/20261121-2305/odom_samples.json) |
| E10 | Nav2 正在运动时调用实际 `heritage/tour/cancel` 服务 | 取消当前任务、确认停车、保持人工取消终态且不自动继续 | 取消请求接受；记录到停止确认（平均请求至确认 0.900 s）；导览进入 IDLE，速度故障锁存等待人工复位，没有自动恢复 | PASS | [取消请求](robustness/manual_stop/20261121-2300/manual_cancel.json)、[CSV](robustness/manual_stop/20261121-2300/experiment_data.csv)、[状态](robustness/manual_stop/20261121-2300/state_transitions.json) |

## 指标边界

- E03 相机候选帧是把 Gazebo 模型中心投影到相机水平视场和深度范围估计出来的候选集合；它不是人工标注的完整数据集。
- E03 最小表面间隙用记录器的圆形支撑半径近似计算，不是经过真实底盘碰撞标定的物理安全余量。
- E09、E10、E08 作用于隔离 Domain 225 的实际 ROS 2/Gazebo 软件链路；它们不等同于实体底盘断电、硬件急停或实机停车。
