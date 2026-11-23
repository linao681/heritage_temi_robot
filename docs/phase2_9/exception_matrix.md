# 异常处理与人机协同矩阵

截至2026-11-23。这里区分代码/单测证据、历史演示和本阶段场景。单元测试不等同Gazebo或实体异常验收。

| 异常 | 触发与期望处理 | 现有可核验依据 | 阶段2.9状态与缺口 |
|---|---|---|---|
| 游客听不清、要求重讲 | 保持静止，操作员或游客请求重讲；播报失败不得记为完成 | 未找到独立重讲闭环测试 | NOT_RUN；需补状态/接口和停稳证据 |
| 游客中途提问 | 暂停当前讲解/导航资格，完成知识查找和模拟播报后继续原站点 | tests/test_tour_manager.py QA流程与儿童层级测试 | PASS_WITH_RISK（模拟/单测）；无新Gazebo运行或实体TTS |
| 知识库未命中 | 返回明确未知/回退，不编造内容；等待游客继续或操作员处理 | tests/test_knowledge.py refusal测试 | 离线测试覆盖；需补端到端问答和播报终态证据 |
| 用户拒绝导览 | 不开始导航，结束接待流程 | tests/test_tour_manager.py::test_visitor_decline_does_not_send_navigation | 单测覆盖；无现场run |
| 游客掉队 | 请求停止、确认停稳、保留原目标，等待集合和明确确认 | Tour Manager、visitor-tour integration与控制竞态测试 | 软件测试覆盖；E07-A/B新Gazebo实验NOT_RUN |
| 短时视觉遮挡 | 观测转为 UNKNOWN，不误判游客离队；需要时安全等待/人工确认 | tests/test_phase28_team_observer.py盲区/无效传感器测试 | 离线观察逻辑覆盖；动态遮挡NOT_RUN |
| 人员横穿 | 视觉/深度与激光分别报告有效性，安全策略减速或停车 | tests/test_perception_fusion.py障碍/传感器测试 | 单元逻辑部分覆盖；E04三种Gazebo横穿NOT_RUN |
| 导航目标不可达 | 导航失败应进入错误处理，不宣称到站、不跳过目标 | Tour Manager导航失败/异常处理测试 | 状态机部分覆盖；未做地图障碍注入 |
| 定位失效 | 不继续提交依赖失效定位的目标，安全停机并请求人工处理 | 未找到阶段2.9独立定位失效注入 | NOT_RUN |
| 相机/深度/激光断流 | 失效或数据过期不得当作“无人/无遮挡”；维持安全策略 | tests/test_perception_fusion.py陈旧/无效/超时用例 | 离线测试覆盖；现场断流实验NOT_RUN |
| 电量不足 | 接待前不启动；导览中优先返回配置安全点 | tests/test_tour_manager.py低电量优先级测试 | 单测覆盖；当前为注入/模拟状态，没有真实电池 |
| 网络断开 | 停止/失效活动指令，重连时同步状态；不自动重放旧导航 | tests/test_websocket_backend.py断连/重连用例；当前运行环境不能建立本地监听 | 代码测试部分覆盖；实时WebSocket BLOCKED |
| 人工接管 | 人工优先，停止任务并释放导览控制 | Tour Manager manual takeover测试 | 状态机单测覆盖；未做Gazebo/实体操作 |
| 人工取消 | 取消优先于自动恢复；未确认停止时不报告空闲 | tests/test_phase28_control_races.py与Tour Manager取消用例 | 软件竞态单测覆盖；真实Action/odom实停NOT_RUN |
| 导览任务恢复 | 只恢复当前安全暂停和原目标；需终态、当前UUID与新鲜停稳证据 | tests/test_phase28_control_races.py恢复、旧UUID、odom新鲜度测试 | 软件级部分覆盖；无本阶段Nav2恢复run |
| 出口送别 | 仅在按顺序到达出口且导览完成后结束 | 阶段2.7历史report记录 exit 与 COMPLETED | 仅历史业务脚本证据；阶段2.9完整导览BLOCKED |

## 全局边界

- 低电量、操作员确认、游客同意如由脚本触发，必须标为模拟操作员输入。
- 模拟字幕/Mock Speak不是实体Temi播报。
- 传感器几何距离不是接触传感，也不是实体安全认证。
- 本地socket权限受限导致WebSocket集成失败不等同协议单测失败；反之，协议单测通过也不能宣称现场断网闭环通过。
