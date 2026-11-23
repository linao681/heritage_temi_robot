# 图表与证据映射

| 展示内容 | 证据文件/来源 | 可以说什么 | 不可以说什么 |
|---|---|---|---|
| 五区路线流程 | `config/submission_exhibits.yaml`、`config/submission_system.yaml` | 软件配置了 wait、zone_1至zone_5、exit | 不能单凭配置称真实导航成功 |
| 官方/适配展厅平面图 | `simulation/generated/{official,adaptive}.*` | 有两套独立地图与目标配置；启动代码按layout传值 | 本轮没有A/B完整Nav2验收 |
| YOLOX匿名检测/距离 | 阶段2.8报告 `docs/phase2_8/final_report.md` | 仅可引用其中历史单帧标注和样本量 | 不可作为阶段2.9动态精度或团队跟踪结论 |
| Tour Manager服务状态 | 新阶段2.9 live run未来输出 `/api/pose`与`live_evidence.jsonl` | 在时间戳/run_id一致时说明状态与事件 | 没有本阶段浏览器截图，不能称现场验收通过 |
| Nav2速度参数 | 当前新增 `GetParameters` 只读API | 显示FollowPath和velocity_smoother的参数返回 | 参数不等同有效速度，也不等同odom实速 |
| cmd_vel/odom | 本阶段未来run JSONL | 展示命令与机器人仿真里程计响应 | 仿真odom不等于实体temi物理速度 |
| 人物位置 | `Gazebo /model_states` 与真实图像两条数据流 | 分别标真值与YOLOX估计，比较误差 | 禁止把真值演员坐标当相机检测 |
| 问答答案 | `config/knowledge.yaml` 的条目与来源URL | 展示知识命中、来源和模拟播报状态 | 不宣称实体Temi TTS或真实ASR |
| 五区导览耗时 | 阶段2.7历史`504.840秒` | 可作为历史模拟流程记录并明确版本 | 不能转作阶段2.9新run或实体指标 |
| 成本 | 询价记录（目前未取得） | 说明采购类别和询价缺口 | 不编精确价格或成本优势 |

每张比赛图表应附run_id、数据时间段、版本、单位、分母、失败样本和“仿真/实体”标签。没有对应证据的图表标“待采集”，不要使用装饰性假数值。
