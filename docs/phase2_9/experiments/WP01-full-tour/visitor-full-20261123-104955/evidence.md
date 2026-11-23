# WP01 官方布局业务完整导览证据

## 结论

状态 **PASS（business_script/Gazebo脚本游客）**。这是阶段2.9最新代码的一轮完整业务路线，不代表视觉团队观察、真人游客、实体Temi、真实TTS或现场安全认证通过。

## 运行信息

- run_id：`visitor-full-20261123-104955`
- 开始：2026-11-23 10:49:55 CST
- 分支/HEAD：`phase2_9-work` / `24c14231de61840a11c5462805df0cd6160af84d`（dirty源文件哈希见manifest）
- 场景：`official`布局、`business_script`决策、3名Gazebo脚本演员、模拟操作员同意/集合确认
- ROS Domain/端口：取值见 `manifest.json`
- 运行器总耗时：536.929秒；Tour Manager导览计时：523.617秒
- 原始命令和预检资源：`manifest.json`、`report.json`

## 实际结果

- Tour最终状态 `COMPLETED`，访问顺序为 `wait → zone_1 → zone_2 → zone_3 → zone_4 → zone_5 → exit`（7/7）。
- 每个实际移动目标 `zone_1…zone_5, exit`均有新鲜cmd_vel与odom配对运动证据：分别55、104、153、115、165、210条，共802条。wait点起点与机器人初始位姿重合，因此不把它计入移动样本。
- 6个安全停车点均有新鲜odom、Tour状态静止，速度≤0.006m/s；后续恢复采用新导航UUID，目标保持一致。
- 3名脚本演员最终为GATHERED、count=3、lag=0；这是脚本真值业务模式结果，不是YOLOX团队观察。
- 知识问答命中`music_types`，回答为“潮州音乐大致分为广场乐和室内乐。”，来源为中国非遗网潮州音乐项目页。`spoken=true`表示模拟播报/字幕流程完成，不是实体扬声器。
- 终点状态新鲜odom为0.00591m/s、`tour.is_moving=false`；终点Nav2未继续发布cmd_vel，故报告将其单独标为过期快照，不伪造为新鲜命令。
- 未做独立人工取消优先专项；本run的QA正常结束、机器人到出口并完成导览。

## SHA-256

- `report.json`：`e3ae52bc03fb023f39b3b113b2823c15dca762be4e7c91f75e715f7ff92ac913`
- `live_evidence.jsonl`：`f2a70833de043b130a4e3682afa6ce2da7cf7e2a4fefaea133a52f60bdeaba54`
- `manifest.json`：`02b4c78b82e6213c3ea90c4b87e70853ede8742f71500122c5781e51ec4c13e6`
