# 阶段2.9验证矩阵

更新至2026-11-23 13:51 CST。构建、单测和静态检查不能替代Gazebo、浏览器或实体实验。

| 项目 | 状态 | 已有新证据 | 缺少证据 |
|---|---|---|---|
| T00基线 | PASS_WITH_RISK | 当前分支/HEAD、资源检查；WP02复测前后Domain 226由项目探针确认为空，端口11377/8101复测后可绑定 | 域227曾由`ros2 node list`遗留发现节点并触发预检拒绝；已保留记录，未强停ROS进程 |
| G0重型仿真门 | PASS | 11:45复测前可用内存7.844GiB、负载0.084/16核、磁盘44.760GiB、端口空闲、无其他Gazebo；运行后域空、端口可绑定且无本run残留进程 | 每次新实验仍需独立重查资源、域和端口 |
| WP01五区导览 | PASS | 最新官方布局业务run `visitor-full-20261123-125818`访问wait/五区/exit（Tour 381.869s；runner 396.386s）、知识库QA命中；zone_1–5及exit六个移动目标均有配对cmd_vel+odom样本，终点新鲜odom 0.00113m/s；脚本游客及模拟播报 | 独立人工取消优先专项未运行；视觉模式不能借用业务脚本PASS；7次PAUSED中report收录5条停稳样本 |
| WP02动态视觉 | FAIL（真实视觉UNKNOWN与安全停稳通过） | 新run `visitor-full-20261123-133255`含845条团队观察，全部UNKNOWN；818条观察到1/3、21条2/3、5条短暂3/3但因`forward_only`仍UNKNOWN；848/850条深度新鲜。801条paused样本中800条有新鲜odom停稳。运行器曾漏记通用安全暂停；TDD修复后full-demo测试20/20通过 | run停在zone_1、未人工恢复或完成路线；未存RGB/Depth图像；八阶段移动/遮挡/离场重入/深度失效/过期场景与人工标注仍未完成。真实视觉结果与脚本团队分开 |
| WP03 E07-A/B | PASS_WITH_RISK（A脚本闭环通过，B未完成） | 新run `visitor-full-20261123-125818`完成zone_3脚本掉队→停稳→集合→模拟操作员确认→同目标新UUID恢复，并完成出口；专门摘要见`experiments/E07-A/visitor-full-20261123-125818/evidence.md`。此前用户中止run仍保留FAIL | E07-B视觉观察后人工确认恢复；每个暂停均匹配停稳样本；重复/陈旧确认与恢复中断专项 |
| WP04集合效率 | PASS_WITH_RISK（改善迹象，未完成对照） | 修复后run的zone_3 `LOST`→`GATHERED`为21.42s，峰值lag 4.7428m；此前同布局脚本run末次集合约201.7s。完整导览已完成。旧读回根因与fresh ModelStates修复有单测及Gazebo复测证据 | 固定seed/同起点同队距的重复对照；本次团队日志无actor XYZ，不能报告新实测步速；全路线集合耗时、安全间距与稳定性 |
| WP05 E02人群限速 | NOT_RUN | 只读Nav2参数接线；融合逻辑单测 | 0/1/3/5人及渐增/渐散动态实验与odom归因 |
| WP06 E04横穿 | NOT_RUN | 感知融合传感器失效/激光代码单测 | 视觉主导、激光主导、双源三个Gazebo场景 |
| WP07速度标定 | NOT_RUN | 新增CSV稳定速度窗分析器和采集器新鲜度字段，相关单测通过；无阶段2.9有效实测窗口 | 0.3/0.5/0.7 m/s独立直线运行与实读 |
| WP08停车/恢复 | PASS_WITH_RISK | WP01有6次安全暂停、停稳与新UUID恢复；WP02视觉UNKNOWN安全暂停由新鲜odom确认停稳；过期调速响应没有锁存ERROR | 持续接近、视觉/深度/Scan失效恢复、并发STOP及人工确认恢复闭环 |
| WP09布局A/B | PASS_WITH_RISK | official布局A已在WP01完成业务完整路线，地图/目标哈希见manifest | adaptive布局B真实Nav2关键站点、窄通道与页面坐标核验未运行 |
| WP10游客类型 | NOT_RUN | 儿童友好问答层级代码和单测 | 散客/团体/亲子状态机及场景运行 |
| WP11异常协同 | PASS_WITH_RISK | exception_matrix.md关联当前单测/历史记录 | 16项全部触发注入和Gazebo闭环 |
| WP12内容与问答 | PASS_WITH_RISK | 15条儿童友好内容、知识校验、QA层级接口及回归 | 内容馆方审核、未知问题到模拟播报的全链路Gazebo验证 |
| WP13技术面板 | PASS_WITH_RISK | 来源/模式、Tour历史、Nav2只读读回代码与定向测试 | 实时浏览器、断源重连、相机叠框截图 |
| WP14记录回放 | PASS_WITH_RISK | WP01新run `live_evidence.jsonl`含机器人状态、目标、UUID、cmd_vel/odom、感知和事件；6个移动目标共802条配对运动样本。只读HTTP实现及哈希安全测试仍有效 | 完整回放生成、原始文件清单/哈希联动、时间轴及浏览器实际验收未完成；WP02失败run未生成完整动态轨迹 |
| WP15六分钟演示 | PASS_WITH_RISK | 讲稿、分镜、页纲和证据映射 | run对应录屏及最终PPTX/PDF |
| WP16创新/答辩 | PASS_WITH_RISK | 架构、创新边界、20+答辩题和指标口径 | 新实验指标与官方终稿逐项核对 |
| WP17实体落地 | HARDWARE_REQUIRED | Bridge清单、部署路线和待询价成本分类 | 实体Temi、真实安全/SDK/TTS/ASR验收 |
| WP18回归 | PASS_WITH_RISK | ROS2七包构建7/7；最新视觉暂停handler修复后的完整suite 624 passed、190.10秒、退出码0；运行前后Domain 226为空。日志SHA `609b53c935b48363831dd1cafd4200112991db64f5932cd81c179e5d5db52d74` | Gazebo中断清理端到端复测、动态八阶段、布局B、浏览器和硬件实验仍未完成 |

## 运行数量与测试口径

- WP01 official/business_script完整路线2轮PASS（`104955`与`125818`）；WP02 vision_conservative至少5次Gazebo尝试。`133255`提供真实前向相机/YOLOX/RGB-D UNKNOWN与安全停稳证据，但未做人工恢复并在zone_1结束，整体FAIL保留。运行器handler已修复，20项专项及最新624项全量suite通过；修复后的视觉路线待单独复测。`114400`因域预检拒绝且没有启动仿真。另有专用E07-A中断run `121915`保留FAIL，最新完整E07-A业务闭环见`125818`。
- E02 0/6，E07-A业务闭环1轮PASS_WITH_RISK（此前中断run单独保留FAIL），E04 0/3，E07-B 0/1，速度档0/3，adaptive布局B Nav2路线0/1。
- 全仓pytest收集607项但未全量执行。506项是显式排除14个集成模块后的安全离线子集，不是全仓通过数；定向回归另排除1个ROS节点用例。
- WebSocket实时loopback被本地socket限制阻断；未把该轮记作通过。
- 阶段2.7/2.8数据只作为历史证据，不能并入阶段2.9实验数。


## 2026-11-23 11:15 CST 状态校正

本表已纳入最新证据：WP01业务脚本完整路线PASS；WP02完整动态场景仍NOT_RUN，但已有一次真实相机管线静态观测run（其整体run FAIL）；WP03仅部分脚本恢复证据；布局A通过业务路线，布局B未运行。较早“0条Gazebo导航run”是当时快照，不再代表当前状态。
