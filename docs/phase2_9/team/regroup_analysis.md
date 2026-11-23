# 历史集合耗时分析（阶段2.7）

日期：2026-11-23（Asia/Shanghai）

## 范围与口径

只分析已归档的阶段2.7记录，不把它当作阶段2.9实验。输入为 docs/phase2_7/experiments/visitor-full-20261122-202055/ 下的 report.json、verification.json、live_evidence.jsonl 与 system/visitor_team.jsonl。暂停区间由现有采样中 Tour 状态 PAUSED 的首末时间计算；人物路程由相邻Gazebo真值位置的欧氏距离累计。未对稀疏事件做插值。

## 结果

- 历史业务脚本导览状态为 PASS_WITH_RISK，路线7/7，耗时504.840秒；游客同意、集合确认与字幕播报均为模拟流程。
- 记录中有6次 PAUSED 集合等待，总暂停时长约175.602秒，占全程34.78%。
- 其中最长一次在 zone_3，约141.034至288.374秒，共147.340秒，占全程29.19%。脚本操作员在141.088秒发出集合请求，模拟队尾随后沿生成的追赶路径移动，到达后才恢复原目标。
- 该次暂停开始时，脚本队尾落后约4.668米；记录的追赶路径有71个A*点，路径折线长度约13.910米。按484个现存Gazebo位置样本离线累计，行走折线约13.965米、净位移约6.579米，样本间平均速度约0.095米/秒。
- 这说明长等待与绕行追赶同时出现，但现有数据不能单独判定根因是路径形状、人物速度、避让/让行还是Gazebo运行节奏；不能据此直接调整安全阈值或宣称优化完成。

## 可复核数据

原始文件SHA256：

- report.json：975aae4fcd0a8e51ff98dc3f1a95ef52914b9566c52d8823de5b9011b1c250be0
- verification.json：7a32693bc13a9a97dcdc7343458c423e0c8cf595b4afdb36482da9a3cbb56d7b
- live_evidence.jsonl：4fafd3bbd60d93f945c4580d0a5dc88554d92f25dee746d2e1fffe664f54943f
- system/visitor_team.jsonl：98d1788fe343d7421f9eecd38f75faf8bb4600b95a6ae0783183040d36068ffb

## 结论与下一步

这是脚本演员的Gazebo真值和阶段2.7业务状态记录，不是相机视觉跟踪结果，也不是阶段2.9新基线。尚未修改跟随速度、追赶路径或集合条件；当前没有同条件复跑，优化状态为 NOT_RUN。下一轮应固定地图、随机种子、路径、队伍间距和操作员确认条件，并记录路径长度、等待分段、Nav2 UUID、cmd_vel/odom及最小几何距离，再比较修改前后数据。

## 阶段2.9 dedicated E07-A 部分运行

来源：[`visitor-full-20261123-121915/evidence.md`](../experiments/WP03-E07-A/visitor-full-20261123-121915/evidence.md)。official布局，`business_script`，三名Gazebo脚本演员；运行在zone_5途中被用户要求结束。与阶段2.7不是相同代码/固定条件比较。

- zone_3队尾达到`LOST`时落后4.735 m；暂停从约152.4 s开始，团队在约351.6 s重新`GATHERED`，暂停等待约199.2 s，随后等待模拟操作员恢复；整段Tour暂停约201.7 s。
- 第三名脚本演员的初始追赶路径有68个0.2 m网格waypoint。按654个实时位置样本累加的折线长度下界为12.971 m，净位移6.762 m，样本间隔均值约0.30 s，路径速度下界约0.065 m/s。未对稀疏位置插值。
- 原始`visitor_team.jsonl`有86,459行/440.617 s，循环平均约196.2 Hz、中位更新间隔3.30 ms；official Gazebo model-state插件频率为20 Hz。`advance()`以循环间隔计算约2.8 mm中位步长，而`move()`的位姿确认容差为20 mm；旧代码接受0.5 s内的缓存位姿，因此一个Gazebo状态样本可能被多次当作移动读回，命令反复基于旧位置。
- 已为读回加入服务确认后的时间边界：只接受晚于`SetEntityState`服务确认时间的Gazebo ModelStates，超时仍使用`GetEntityState`直接读回。新增freshness单测和`move()`参数测试通过；尚未做修改后的Gazebo同场景复测。

此数据支持“状态采样与脚本高频更新混叠造成队尾实际步速远低于配置值”的根因解释。后续修复复测见下节。

## 2026-11-23 12:58 CST freshness修复后复测

run [`visitor-full-20261123-125818`](../experiments/WP04-regroup/visitor-full-20261123-125818/evidence.md)使用official布局、三名Gazebo脚本游客和`business_script`，完整完成wait、五区与exit。zone_3掉队状态`LOST`持续21.42秒后返回`GATHERED`，最高lag 4.7428m；模拟操作员确认后原`zone_3`目标以新navigation session继续。前一部分run在zone_3末次集合约201.7秒；这次等待较短是改善迹象，但随机路径/起点/状态未固定，且新run的team JSONL记录状态与progress而无actor XYZ，所以不能由它计算队尾物理步速，也不能将两次差异当作受控因果结论。run Tour计时381.869秒，最终出口新鲜odom停稳。

**WP04结论：PASS_WITH_RISK。** fresh-after-ack读回修复已由新Gazebo完整路线运行验证可完成；长等待问题出现明显减小迹象。固定seed/起点/队距下重复对照、逐帧Gazebo XYZ采集、队伍最小间距与整路线集合耗时仍待补测。未调整游客步速、安全距离、追赶路线寻路与人工确认门槛。
