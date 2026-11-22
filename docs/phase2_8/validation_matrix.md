# 阶段 2.8 验证矩阵

状态限定在 `phase2_8-work` 当前快照；阶段 2.7 历史路线结果不计作本阶段测试。

| 工作包 | 状态 | 证据与限制 |
|---|---|---|
| T00 审计 | PASS_WITH_RISK | [`audit/baseline.md`](audit/baseline.md) 保存工作树、工具链、模型、差异与历史限制；各实验的 run manifest 完整度仍按各目录记录 |
| WP01 匿名跟踪/真实图像 | PASS_WITH_RISK | 新匿名跟踪器与保守 observer；实际 RGB-D 见 [`WP01-GAZEBO-CAMERA-04`](experiments/WP01-GAZEBO-CAMERA-04/report.md)。12 RGB、5 depth、单帧人工框3人；该帧 P/R=1.0、均值 IoU=.923。模型推理 FPS、深度误差、ID switch 不可计算。静态人物和前视覆盖不证明掉队 |
| WP02 来源隔离 | PASS_WITH_RISK | `vision_conservative` 隔离脚本团队消息和 lost 服务调用；来源/策略测试在完整 543 项回归中通过。无视觉整路线 E07 验收 |
| WP03 E07 双模式 | NOT_RUN | 未运行真实三人移动 E07-A；未运行机器人静止、人员进出/遮挡/重现、操作员确认的 E07-B |
| WP04 跟随/集合优化 | NOT_RUN | 无阶段2.8同条件完整路线基线与优化对照 |
| WP05 STOP/恢复竞态 | PASS_WITH_RISK | 12 类软件竞态覆盖，修复自动暂停优先级；定向测试 109 passed。没有 Gazebo 低速真实停稳与时序证据 |
| WP06 E02 拥挤限速 | NOT_RUN | 无人数对照、密度标定和实际 odom 贡献测量 |
| WP07 E04 横穿 | NOT_RUN | 本阶段没有 A/B/C 视觉/激光/双源横穿对照 |
| WP08 速度标定 | NOT_RUN | 没有新独立直线路段 0.3/0.5/0.7 m/s 标定与 Nav2 参数读回 |
| WP09 动态停车矩阵 | NOT_RUN | 缺少八类接近/横穿/停止/遮挡/失效/恢复的独立实跑 |
| WP10 最终回归 | PASS_WITH_RISK | [`ros2_build_final.log`](tests/ros2_build_final.log)：7包退出0；[`full_suite_final.log`](tests/full_suite_final.log)：550 passed，0 fail/skip/error，196.49s；[`websocket-final.log`](tests/websocket-final.log)：2 passed；[`visualization-final.log`](tests/visualization-final.log)：语法、运行与真实回放哈希检查退出0。最终用空域231完成且前后确认为空 |
| WP11 七类稳定性 | NOT_RUN | 本阶段无七类独立三人完整路线分母 |
| WP12 性能窗口 | NOT_RUN | 无相同三人场景的预热+60秒 CPU/内存/时延/页面帧率基线与对照 |
| WP13 真数据面板 | PASS_WITH_RISK | ROS API、深度有效像素/相机TF、新鲜度与 LaserScan 测试；实际页面检查 [`WP13-LIVE-PANEL-01`](experiments/WP13-LIVE-PANEL-01/report.md) 早于新增深度/TF字段。仍缺新字段浏览器复核、截图、≥60秒断源/重连、视频及 Nav2 独立限速回读 |
| WP14 三模式回放 | PASS_WITH_RISK | 真实 WP01 run 已校验导出 `RECORDED_ROS2`：186事件、12 RGB、5深度元数据；独立播放器有时间轴、倍速、播放/暂停和事件定位，哈希/只读测试通过。现有源无世界坐标/速度曲线；`file://`浏览器预览受策略阻止，未完成画面验收 |
| WP15 演示素材 | NOT_RUN | 本阶段无可追溯的完整录屏或精华视频；旧演示不计入本阶段 |
| WP16 日志归档 | PASS_WITH_RISK | [`archive-final.log`](tests/archive-final.log)：归档单测4 passed；WP01-04 30/30 文件 SHA256/字节复核一致，归档大小464,450 bytes，原文件保留。常规状态采样频率策略与历史大文件统计仍未完成 |
| WP17 状态文档 | PASS_WITH_RISK | 本阶段进度、矩阵、阻塞、变更与最终报告已更新；老报告作为历史快照未重写 |
| WP18 实体 temi 接入 | HARDWARE_REQUIRED | [`real_temi_integration_checklist.md`](real_temi_integration_checklist.md) 为代码审查/准备清单；无设备、无 Android 改动或实体行为验证 |

## 回归运行事实

- 首次全套测试的隔离设置遗漏 `HERITAGE_TEST_ROS_DOMAIN_ID`，其中 `test_gateway_cli.py` 回退到域228；当时该域已有用户的 Gazebo/Nav2 图。首轮结果 542 passed / 1 failed，失败是 mock gateway 状态超时。单独改用域230后该测试通过；之后阶段代码与回放新增后，最终整套550 passed。失败轮次与分析均保留。
- 曾试探域234，但 ROS中间件拒绝其端口范围；该次在 pytest 开始前终止，记录在 `full_suite_domain-precheck-234.log`。
- 最终全套使用 Domain 231，执行前和执行后均为空；独立 WebSocket 专项同样在231前后空域运行。一次230空域预检发现ros2cli守护节点后在pytest启动前中止。没有停止或改写域228中的用户系统。首次域228尝试只启动测试专用 Mock temi gateway、未调用 Nav2，也未到达测试中的 stop 调用。
