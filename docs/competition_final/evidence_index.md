# 证据索引

## 阶段2.9真实仿真

- **原始游客状态流归档**：12份`system/visitor_team.jsonl`均有同目录gzip副本；[`raw_archive_manifest.csv`](../phase2_9/raw_archive_manifest.csv)列出原始/压缩大小与SHA-256，并验证解压后哈希与原文件完全一致。原始大文件保留在本机且不纳入Git；压缩副本、运行报告和证据哈希随项目推送。

- **WP01完整业务路线 PASS**：[`visitor-full-20261123-104955`](../phase2_9/experiments/WP01-full-tour/visitor-full-20261123-104955/)。包括`manifest.json`、`report.json`、`live_evidence.jsonl`及同目录`evidence.md`。报告哈希：`e3ae52bc03fb023f39b3b113b2823c15dca762be4e7c91f75e715f7ff92ac913`；原始JSONL哈希：`f2a70833de043b130a4e3682afa6ce2da7cf7e2a4fefaea133a52f60bdeaba54`。
- **WP02失败尝试1**：[`visitor-full-20261123-110241`](../phase2_9/experiments/WP02-vision-observation/visitor-full-20261123-110241/)，保留observer序列化崩溃和timeout日志。
- **WP02失败尝试2/静态真实感知数据**：[`visitor-full-20261123-111123`](../phase2_9/experiments/WP02-vision-observation/visitor-full-20261123-111123/)。解释、局部统计和哈希见该目录`evidence.md`。report SHA-256：`198123a50fd7545540d2d7cfdff67116a9508ad72c0632dc262b9edccef3fd08`；`live_evidence.jsonl` SHA-256：`167861268d055c99b96f03d51cc5c46c7945fcd7daa0e50498ecdd6eaf666834`。
- **WP02诊断尝试3**：[`visitor-full-20261123-113050`](../phase2_9/experiments/WP02-vision-observation/visitor-full-20261123-113050/)，保留“无活动导航Action”与Action取消先后关系的日志；统计与文件SHA见该run的`evidence.md`。
- **WP02启动前域检查**：[`visitor-full-20261123-114400`](../phase2_9/experiments/WP02-vision-observation/visitor-full-20261123-114400/)，发现此前CLI域检查遗留的发现节点后安全拒绝启动；事件数0、无Gazebo。
- **WP02保守视觉停稳复测**：[`visitor-full-20261123-114541`](../phase2_9/experiments/WP02-vision-observation/visitor-full-20261123-114541/)，完整run FAIL（等待外部人工确认超时），但含真实YOLOX/RGB-D、UNKNOWN团队判断、确认停稳与旧调速隔离的局部证据。各原始文件SHA-256见`evidence.md`。
- **WP02真实视觉暂停部分run**：[`visitor-full-20261123-133255`](../phase2_9/experiments/WP02-vision-observation/visitor-full-20261123-133255/evidence.md)，真实YOLOX/RGB-D观察845条均为UNKNOWN、前向相机覆盖限制及新鲜odom停稳记录；run在zone_1保持FAIL，未人工恢复或完成全程。report SHA-256 `aa5de4b0583e2d969c5bc887700bbed97615cf1aec65777a15b8f2e6b9ea7155`；manifest `43b3391e6740f3ea9dbd57abe30d31288ad8576e54ef19a154b29880a4f00770`；live evidence `3983c14f05e7bae667444776aece3625c13571704a556cd6aff651bfdbc39e63`；team log `76a9dc4dd729f27acd2c9ea70d178d3a1467ea1da8ad90b689e0db3780a5b34f`。
- **E07-A业务脚本部分运行**：[`visitor-full-20261123-121915`](../phase2_9/experiments/WP03-E07-A/visitor-full-20261123-121915/)，按用户要求在zone_5途中中止；六段暂停和长集合等待的样本分析、原始证据SHA及清理检查见`evidence.md`。状态FAIL，不计完整路线通过。
- **WP04修复后完整导览及E07-A脚本闭环**：[`visitor-full-20261123-125818`](../phase2_9/experiments/WP04-regroup/visitor-full-20261123-125818/evidence.md)，业务Tour PASS；E07-A业务闭环PASS_WITH_RISK；集合效率改善迹象PASS_WITH_RISK。report SHA-256 `5d745cb17badc728bda90cfd3f45afddd446e08c905a3681760349f914958ddd`；manifest `062ed7853c21fa30e141498ecc950e29e2766ee75090421a9a11cac14ff51bf3`；live evidence `047ba41027a4dd84641855181170bf2ec27d144e98e9f4ab52f0861472f5d601`；team log `368185adbbaeac5174eaf6ba4448e339a25a2eafd485f2dca9b91261aa29d06e`。E07-A摘要 [`experiments/E07-A/visitor-full-20261123-125818/evidence.md`](../phase2_9/experiments/E07-A/visitor-full-20261123-125818/evidence.md)。
- **WP18最新完整回归**：[`full-regression-20261123-1351.log`](../phase2_9/audit/full-regression-20261123-1351.log)：624 passed，190.10秒，退出码0，包含视觉pause-handler修复；运行前后Domain 226均空，SHA-256 `609b53c935b48363831dd1cafd4200112991db64f5932cd81c179e5d5db52d74`。早期622项回归与失败尝试仍保留；七包构建7/7和历史诊断见[`regression-20261123-1211.md`](../phase2_9/audit/regression-20261123-1211.md)和[`verification-attempts.md`](../phase2_9/audit/verification-attempts.md)。
- **仿真中断清理复核**：[`process-shutdown-fix-20261123.md`](../phase2_9/audit/process-shutdown-fix-20261123.md)：记录E07-A中断后的自有进程清理、运行器会话隔离修复、测试前后结果及尚未做的Gazebo端到端复测。
- 阶段2.7历史集合分析：[`regroup_analysis.md`](../phase2_9/team/regroup_analysis.md)，含历史源哈希和口径。
- 阶段2.9集合耗时及读回根因、修复后局部观察见[`regroup_analysis.md`](../phase2_9/team/regroup_analysis.md)；修复前XYZ原始轨迹和哈希见旧run证据，修复后完整run的状态日志、SHA和限制见新run `evidence.md`。固定条件对照仍待执行。

## 软件、架构与材料

- 当前进度/逐项状态/阻塞：[`docs/phase2_9/progress.md`](../phase2_9/progress.md)、[`validation_matrix.md`](../phase2_9/validation_matrix.md)、[`blockers.md`](../phase2_9/blockers.md)。
- 异常处理映射：[`exception_matrix.md`](../phase2_9/exception_matrix.md)。指标和证据边界：[`key_metrics.md`](key_metrics.md)。
- 只读回放实现与安全测试：`scripts/serve_replay.py`、`tests/test_phase29_replay_server.py`、`tests/test_phase28_replay.cjs`。
- 记录器与速度分析：`scripts/record_phase2_topics.py`、`scripts/analyze_phase29_experiment.py`、相应`tests/test_phase29_recording.py`与`tests/test_phase29_speed_calibration.py`。
- 国赛六分钟讲稿、分镜、页纲、图证映射、创新摘要、技术架构、答辩问答、实体部署和成本分类均在本目录。
- ROS2七包构建最新成功；详细输出目录和既往pytest排除边界见`docs/phase2_9/progress.md`与`docs/phase2_9/audit/verification-attempts.md`。

## 尚待补交

1. WP02八阶段动态视觉和逐帧人工标注；E02/E04/E07-B/三档速度及adaptive布局Nav2数据。
2. 对视觉模式执行有明确操作员输入的恢复专项；本次45秒run未执行确认，完整导览保持FAIL。
3. 实时浏览器截图、完整只读回放浏览器验收。
4. 可编辑PPTX、最终PDF、源自真实Gazebo run的演示视频及组委会最终赛务通知。
5. 实体Temi、真实ASR/TTS、设备安全和现场部署验证。
