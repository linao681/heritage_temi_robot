# 阶段3.0实验矩阵

状态按本阶段证据记录；`NOT_RUN`不引用历史阶段结果代替。

| 实验 | 预期/范围 | 状态 | Run ID / 日志 | 证据SHA | 限制 |
|---|---|---|---|---|---|
| T04 视觉暂停恢复局部 | 视觉UNKNOWN→停稳→测试操作员确认→同目标新UUID/运动 | PASS_WITH_RISK；后续复跑存在失败 | `T04-vision/visitor-full-20261123-160651`；失败复跑`164811` | `c8def186c8bc3cd6f5b67fa87e70bb6e8bd106c1fde68bb95ec786d7906f05e0`；失败报告`56266bdc5839195736ddc2dbff60c3d05419cbab88953db6e0f1f32e9463e4b8` | 前向相机无法证明后方队伍；复跑wait暂停无新UUID/运动证据 |
| T04 视觉完整路线 | 视觉模式官方五区和出口 | PASS_WITH_RISK；后续复跑FAIL | `T04-vision/visitor-full-20261123-160651`；复跑`164811` | 同上 | 6次暂停有配对证据；后续7事件中wait事件MISSING_EVIDENCE |
| T04 business_script | 官方布局接待、五区、问答、出口业务回归 | PASS | `T04-business/visitor-full-20261123-162126` | `6afc1a912eeb3d95212ecdc643b071c6ad99e197b328e38dc93f1d7eb1be3f31` | Gazebo脚本游客、timed subtitles；不是视觉团队验证或实体TTS |
| T05 E04前方横穿 | Gazebo演员与真实相机/YOLOX/RGB-D/Scan/Nav2/cmd_vel/odom对齐 | PASS_WITH_RISK | `T05/E04-CROSS-FRONT/run-004` | report `cfdba1e6ea9278715322b993cce1546a3f7af40e3aa3d8793df98e4fbd9cbdf2`；CSV `190d73af1b6e47afbc5c22a36853d8ee05d3b765002d160df7abaa56db57cdd1`；truth `dd589d2586fa2153ffa072051a1c4501888e5270ab6ce3d11b87f7d1cbdbfccc` | 102条有效人员距离；人员减速和停车时激光障碍也有效；0.544m为几何代理，不是接触安全认证 |
| T05 E04其他方向/独立激光盲区 | 横穿、视觉+激光与激光盲区专项 | NOT_RUN | — | — | run-004有视觉和激光同时观测，未做传感器独立消融 |
| T06 E02-0空场 | 官方完整路线；0人真值/视觉、10Hz odom与速度参数回读 | PASS | `T06/E02-0/run-002` | CSV `4d611cac53b90075fdb6019ba675c24638fe9342bf8eb5d5ca732fc6c37a0623`；truth `53d33a42db1b3a02638425ac7ef25c1164753e9037e72f1fb23d8e46bd47ed3b` | 318.037秒；zone_1稳定窗仅1.305秒，不能作速度校准对照 |
| T06 E02-1单人 | 单人真值/视觉/距离与全路线 | FAIL | `T06/E02-1/run-002`、`run-003` | run-002 CSV `18032a0ac27d95f75c2503f7131b6b6838a78224b5f52658f78d916eacf30cb5`；run-003 report `0c6a1d314a41c4b2589c8c91488efd0c45da353ba138c53be93e2df3b4388989` | run-002 Nav2七站完成但 actor waiter 超时；run-003发布者和真值通过，Tour因通信中断/未确认停车失败 |
| T06 E02-3三人 | 官方完整路线；三人真值/相机人数/距离与ROS控制记录 | PASS_WITH_RISK | `T06/E02-3/run-002` | CSV `50ac55b4122e976f46eb711dd8748f24140f8b8ef6bb700d63b3e2f76840abb5`；report `52c11ce64b9a1abc824f09e62fa4347935ce91781fc7183599e632d8f0eff7d2`；truth `153269d93160145f816fc656ec4d9d47d9220308e3edf78070f3777a03ba0f95` | 324.187秒；Nav2限速恒0.300m/s；稳定直行窗仅0.907秒；不得称已验证动态减速 |
| T06 E02稳定速度对照 | zone_1相同导航目标窗，按≥2秒/20样本/fresh odom/cmd/低角速度/独立读回 | FAIL | `T06/E02-evidence.md`；对应三个run CSV | analyzer原始条件无放宽 | 空/单/三人最长合格候选分别14/16/10样本，全部未满足稳定窗 |
| T06 E02-5/散开 | 五人及逐渐散开场景 | NOT_RUN | — | — | 只完成0/1/3静态人口；人数不等于密度 |
| T07 adaptive静态地图/坐标一致性 | official/adaptive map/goals生成、净空/连通性、页面到ROS目标变换 | PASS | `T07/layout-green.log`，82项测试 | `9e5c40eff39bab4fa7c905b9a9922a5291caedc12f4bb5dfa1e3a6447fee725a` | map YAML `a47880970c529e4f7efbbc6d928c800e2578fa307cd194e1fc35a0528383e82f`；adaptive goals `e01a6ed814ebb745a23f86d0ca6266fe1134fa65c71fe804d625a3c8747ed25a` |
| T07 adaptive Nav2关键目标 | adaptive map实际加载，zone_1到达并停稳 | PASS | `T07/adaptive-key-target/run-001/navigation.json` | `85eb9bba87c1f4a7de17796a062e921f76e9aa731ec47a787a835b4084f77aa9` | 状态4，误差0.223m；Domain214，odom停稳 |
| T07 adaptive Nav2六目标路线 | zone_1–5及出口 | PASS | `T07/adaptive-key-target/run-001/full-navigation.json` | `b8b2dccedee1a4216e63c6b758590fd64b3113fb8396452fcccc93a399aca7b5` | 6/6成功，172.510s；仅导航验收 |
| T07 adaptive业务全程 | wait/入口接待/同意/五区讲解/知识问答/出口 | PASS_WITH_RISK | `T07/adaptive-business-tour/run-001/tour/report.json` | `378ce074c4488bdbc045618e770fad23996b4f2efe7b5b7b40c4a983ec3114d6` | 194.035s；一名Gazebo演员；测试脚本同意；Mock播报；非视觉团队/非E07 |
| T08实时面板数据源 | API、结构化字段、新鲜度、真值分栏 | PASS_WITH_RISK | `T08/live-panel/run-001/pose.json` | `b941e41b7784d433f069475760d7eb6af2bdc434b0abf3551ff2d5ff15a1f0a7` | API快照在完成后，部分来源已经过期；GUI视觉检查NOT_RUN |
| T08真实ROS回放与只读预览 | 来源SHA、真实位置/速度/状态事件、loopback HTTP | PASS_WITH_RISK | `T08/replay/visitor-full-20261123-125818-run-003/` | replay `3bb0e05025ef67fbfb63beb8d3f9d68bf0803629d295b4d8b058a0aa3372167c`；archive `e70414c30b269101f4f47ebcdbc6220f8885a7c26466a7a2e274575727071eaf` | 6050事件、1269机器人TF、3813游客Gazebo真值、2250 cmd/odom；无RGB/depth帧，浏览器截图NOT_RUN |
| T08实时Three.js浏览器视觉 | 中文、数据刷新、Canvas/console人工浏览器检查 | NOT_RUN | `T08/replay/verification/browser-visual-check.md` | — | CUA超时；现有Firefox用户profile未触碰；无安全截图 |
| T10 构建/全量测试 | 七包构建、完整`tests/`及专项 | PASS | Domain 220；七包构建7/7；`tests/` 680 passed；10组定向测试全通过 | build SHA `8a4ac62610af958f6f4cdea6bb9208306e01475470b65a80c8ba8afeccd151dc`；pytest SHA `91af50f880851a035f8d7d316a32662d7219bdd8b98ab084c92e22823f3ed837` | 构建/测试后Domain为空；Gazebo动态专项本轮未作为全量pytest替代或宣称完成 |

每次仿真记录布局、地图/目标哈希、运行配置SHA、ROS Domain、Gazebo/Web端口、数据来源、实际状态、退出码、原始日志SHA和清理复核。run-001–003失败证据仍保留。
