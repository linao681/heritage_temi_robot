# 证据索引

## 阶段3.0材料用证据（2026-11-23）

- **business_script完整官方导览/知识问答**：[`T04-business/visitor-full-20261123-162126`](../phase3_0/experiments/T04-business/visitor-full-20261123-162126/)。报告SHA `6afc1a912eeb3d95212ecdc643b071c6ad99e197b328e38dc93f1d7eb1be3f31`；实时证据SHA `b75511a7f5fff7f3e8d66bf60fbd8c0d8781f2afd18f2d8c709fde616535bbe0`；Tour 377.088秒，五区及出口COMPLETED，知识库命中`music_types`。三名游客为Gazebo脚本演员，Mock Speak。
- **vision_conservative完整导览/六次停稳确认**：[`T04-vision/visitor-full-20261123-160651`](../phase3_0/experiments/T04-vision/visitor-full-20261123-160651/)。报告SHA `c8def186c8bc3cd6f5b67fa87e70bb6e8bd106c1fde68bb95ec786d7906f05e0`；实时证据SHA `0db3d47740b109f4ee4ab42382681470d38c6c33120fdc8435f3a7a95b47515d`；Tour 331.287秒。1078条视觉团队观察均为UNKNOWN；6/6安全暂停有新鲜odom停稳证据并由测试操作员确认。
- **E07-A掉队恢复**：[`阶段2.9 WP04 run证据`](../phase2_9/experiments/WP04-regroup/visitor-full-20261123-125818/evidence.md)。报告SHA `5d745cb17badc728bda90cfd3f45afddd446e08c905a3681760349f914958ddd`；源`live_evidence.jsonl` SHA `047ba41027a4dd84641855181170bf2ec27d144e98e9f4ab52f0861472f5d601`。脚本演员在zone_3 LOST→GATHERED为21.42秒，模拟确认后新UUID恢复同一目标。
- **E04前向横穿**：[`T05 run-004证据`](../phase3_0/experiments/T05/E04-CROSS-FRONT/run-004/evidence.md)。报告SHA `cfdba1e6ea9278715322b993cce1546a3f7af40e3aa3d8793df98e4fbd9cbdf2`；CSV SHA `190d73af1b6e47afbc5c22a36853d8ee05d3b765002d160df7abaa56db57cdd1`；几何间隙0.544m仅为仿真代理。
- **E02**：[`T06实测记录`](../phase3_0/experiments/T06/E02-evidence.md)：空场与三人全程PASS，单人失败；限速未随人数变化，速度窗不足；所有原始CSV与失败报告SHA列于记录。
- **adaptive布局B**：[`T07布局证据`](../phase3_0/experiments/T07/adaptive-layout-evidence.md)：六目标Nav2报告SHA `b8b2dccedee1a4216e63c6b758590fd64b3113fb8396452fcccc93a399aca7b5`；业务Tour报告SHA `378ce074c4488bdbc045618e770fad23996b4f2efe7b5b7b40c4a983ec3114d6`。
- **真实只读回放**：[`T08回放证据`](../phase3_0/experiments/T08/replay-evidence.md)：`replay.json` SHA `3bb0e05025ef67fbfb63beb8d3f9d68bf0803629d295b4d8b058a0aa3372167c`；来源归档SHA `e70414c30b269101f4f47ebcdbc6220f8885a7c26466a7a2e274575727071eaf`；浏览器视觉检查NOT_RUN。
- **T10最终回归**：[`experiments/T10/summary.md`](../phase3_0/experiments/T10/summary.md)：七包构建7/7、完整`tests/` 680 passed；pytest日志SHA `91af50f880851a035f8d7d316a32662d7219bdd8b98ab084c92e22823f3ed837`，构建日志SHA `8a4ac62610af958f6f4cdea6bb9208306e01475470b65a80c8ba8afeccd151dc`。
- **T11最终交接报告**：[`docs/phase3_0/final_report.md`](../phase3_0/final_report.md)，七节报告含T04六组视觉恢复UUID、停稳证据、E02/E04/B、T10构建/全量测试和材料/硬件边界。交叉核验日志SHA-256 `239a16eaecf605f88cec16adc58adecfbf9a22b81672c8c38d25cc029b2c21c8`。
- **没有比赛成品文件**：本工作树未发现`.pptx`、`.pdf`或`.mp4/.webm`；因此当前材料是Markdown讲稿、页纲、分镜与图证索引，不是已导出的PPT/PDF/视频。

---

## 阶段3.0权威更新（2026-11-23 20:10 CST）

当前工作树：`phase2_9-work`，HEAD `f372e3f4e0702470eb91b2a32683e62590777840`；本轮阶段3.0改动未提交、未推送、未合并。旧的阶段2.9文字和624项测试均为历史快照，不覆盖下表结论。

| 证据项 | 阶段3.0结果 | 边界 |
|---|---|---|
| official/business_script完整导览与知识问答 | PASS，`visitor-full-20261123-162126`：入口同意、五区、QA、出口，COMPLETED，377.088秒；3名Gazebo脚本游客，5次停稳后新UUID同目标恢复 | 同意、脚本游客、集合操作员输入为模拟；播报是Mock/字幕 |
| vision_conservative整路线与保守停车 | PASS_WITH_RISK，`visitor-full-20261123-160651`：官方布局完整到出口，331.287秒，6次视觉UNKNOWN安全暂停均有新鲜odom停稳确认 | 1078条团队观察均UNKNOWN；使用测试操作员确认；不能声称视觉队伍跟踪成功或自动掉队识别 |
| E07-A掉队恢复 | PASS_WITH_RISK，阶段2.9原始run `visitor-full-20261123-125818`：zone_3 LOST→GATHERED为21.42秒，模拟操作员确认后同目标新UUID恢复并完成导览 | Gazebo脚本团队，不是视觉判断；非固定条件前后对照 |
| E04前向横穿 | PASS_WITH_RISK，T05 `E04-CROSS-FRONT/run-004`：YOLOX/RGB-D人员距离、激光障碍同时有效，近人策略响应、Nav2停车、odom停稳、演员继续移动 | 视觉/激光未做独立消融；0.544m是仿真几何代理，无接触传感器或实机认证 |
| E02人群 | PASS_WITH_RISK，T06空场/三人全程PASS，单人失败 | 三人限速仍为0.300m/s；稳定直行窗未达门槛，无证据证明人数增加导致实速降低；5人/散开未跑 |
| adaptive布局B | PASS_WITH_RISK：Nav2六目标6/6、172.510秒；独立业务全程COMPLETED、194.035秒 | 一名入口演员，业务同意由测试脚本触发，Mock Speak；非视觉团队/E07验收 |
| ROS记录回放 | PASS_WITH_RISK：真实旧run导出6050事件、1269个ROS TF机器人位姿、3813个Gazebo真值游客位姿、2250个cmd/odom速度样本；SHA验证及只读HTTP检查通过 | 来源为阶段2.9业务脚本run；无RGB/depth原图，桌面浏览器视觉验收NOT_RUN |
| 全量回归 | PASS：阶段3.0完整`tests/` 680 passed、0 failed、0 skipped；七包构建7/7 | Domain 220前后为空；pytest SHA `91af50f880851a035f8d7d316a32662d7219bdd8b98ab084c92e22823f3ed837`；624 passed仍是阶段2.9历史快照 |
| 实体Temi | HARDWARE_REQUIRED | 当前无实体机器人；SDK底盘运动、实体制动、ASR/TTS和现场安全未验证 |

数字用途仅限对应run及其来源。T10全量自动化回归已通过；历史阶段数据不能补齐阶段3.0未运行的E02/E04子场景或浏览器/硬件验收。

---


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
