# 阶段2.9最终验证矩阵

状态说明：PASS仅适用于表中明确的证据范围；PASS_WITH_RISK表示软件或局部证据通过、完整验收仍有缺项；FAIL表示实际尝试失败；NOT_RUN表示指定场景未执行；HARDWARE_REQUIRED表示缺少实体设备。

| 工作包 | 状态 | 最新可核验结果 | 尚缺证据 |
|---|---|---|---|
| WP01 完整导览 | PASS | 最新官方布局业务run `visitor-full-20261123-125818`：wait/五区/exit完成、知识库QA、COMPLETED；五区与exit六个移动目标均有cmd_vel+odom运动配对样本，出口新鲜odom 0.001129m/s。脚本游客与模拟播报 | 视觉模式路线、独立人工取消优先run、真人和实体设备；7次PAUSED历史中report收录5个停稳证据 |
| WP02 动态视觉 | FAIL（真实视觉UNKNOWN与安全停稳通过） | `visitor-full-20261123-133255`：845条团队观察全部UNKNOWN（多数只见1/3）；5条短暂3/3仍因前向覆盖不足留为UNKNOWN；848/850条深度新鲜；801条暂停样本中800条有新鲜odom停稳。新runner专项测试20/20通过 | 该run停在zone_1、未恢复或完成全程；八阶段动态场景、图像归档、标注、操作员恢复后视觉路线仍未完成 |
| WP03 E07-A/B | PASS_WITH_RISK（A脚本闭环通过，B未完成） | `visitor-full-20261123-125818`记录zone_3掉队、停稳、21.42秒后集合、模拟操作员恢复同目标新UUID，并完成exit；此前用户中止run仍保留FAIL | E07-B视觉确认恢复和所有暂停完整停稳映射；视觉盲区限制 |
| WP04 集合效率 | PASS_WITH_RISK（改善迹象） | freshness修复后完整run的`LOST`→`GATHERED`为21.42秒，峰值lag4.7428m；旧partial run约201.7秒。新run没有actor XYZ，未报告新步速 | 固定seed/起点/队距重复对照、队伍实测路径与最小间距、整路线集合耗时统计；不能作受控因果结论 |
| WP05 E02人群限速 | NOT_RUN | 有融合/只读限速字段及策略软件测试 | 0/1/3/5人、渐增渐散、Nav2参数读回和实际odom归因 |
| WP06 E04横穿 | NOT_RUN | 有视觉/深度/激光融合代码 | 视觉主导、激光主导、双源三个独立横穿run |
| WP07 速度标定 | NOT_RUN | CSV稳定速度窗分析器有单测 | 独立直线0.3/0.5/0.7m/s真实仿真标定 |
| WP08 安全停车与恢复 | PASS_WITH_RISK | WP01六次Nav2安全暂停有新鲜odom停稳和UUID恢复；WP02视觉UNKNOWN暂停有新鲜odom停稳确认，旧调速响应未导致ERROR | 持续接近、视觉/深度/Scan失效恢复、并发STOP与操作员恢复闭环 |
| WP09 布局A/B | PASS_WITH_RISK | official布局A完成WP01业务全路线；地图/目标哈希在run manifest | adaptive布局B Nav2关键站点/通道/坐标验证 |
| WP10 游客类型 | PASS_WITH_RISK | 大众/儿童/深度讲解层级已有实现与软件验证 | 散客/团体/亲子真实端到端场景；儿童模式仅用户选择，不自动识别儿童 |
| WP11 异常与协同 | PASS_WITH_RISK | 异常矩阵和多个状态机/软件故障测试 | 全部异常逐一注入并记录停稳、接管和恢复 |
| WP12 非遗内容与问答 | PASS_WITH_RISK | WP01知识库QA命中`music_types`并附来源；模拟播报结束，儿童表达/层级代码通过软件验证 | 馆方审核、未知问题回退和完整现场问答交互验证 |
| WP13 技术面板 | PASS_WITH_RISK | ROS API含状态、来源、感知和导航字段；相关接口测试 | 实时浏览器视觉检查、断流/过期表现和检测框叠加截图 |
| WP14 记录回放 | PASS_WITH_RISK | WP01 `live_evidence.jsonl`含机器人位置/状态、UUID、cmd_vel/odom、感知；只读HTTP回放服务与哈希安全测试已实现 | 完整可浏览回放、完整原始文件索引和浏览器时间轴/倍速实测 |
| WP15 六分钟演示 | PASS_WITH_RISK | 讲稿、分镜、页纲、图证映射已形成 | 约2分钟实录片段、最终可编辑PPTX与PDF检查 |
| WP16 技术创新与答辩 | PASS_WITH_RISK | 创新边界、架构、指标、20+问答材料已形成 | 依据最新动态实验更新指标，逐项核对最终官方赛务文件 |
| WP17 实体部署 | HARDWARE_REQUIRED | temi/ROS2/Kotlin Bridge部署方案和待询价分类 | 实体Temi、SDK许可、底盘/感知/TTS/ASR及现场安全测试 |
| WP18 全量回归 | PASS_WITH_RISK | ROS2七包构建7/7；视觉暂停handler修复后的最新完整`tests/`为624 passed、190.10秒、退出码0；运行前后Domain 226均为空。日志SHA-256 `609b53c935b48363831dd1cafd4200112991db64f5932cd81c179e5d5db52d74` | 动态Gazebo场景、布局B、浏览器和硬件验收仍未完成；WebSocket专项需按本轮环境条件单列口径 |

具体证据和失败原始日志路径见[`evidence_index.md`](evidence_index.md)与`docs/phase2_9/validation_matrix.md`。测试数字按各自运行时间和排除项解释，不能相加成全仓通过数。
