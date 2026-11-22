# 阶段 2.7 最终报告

## 2026 年 11 月 22 日游客完整演示补充

新增三人 Gazebo 游客完整展示已完成一次入口到出口运行，证据为 `experiments/visitor-full-20261122-202055/{report.json,verification.json,live_evidence.jsonl}`。原始运行 PASS，504.840 秒、7/7 导航目标；三人实际移动约 83.406/82.296/91.146 m。知识问答 found=true、spoken=true，6 次集合确认前停止样本及同目标新导航会话已复核。演示启动：`bash scripts/start_full_visitor_demo.sh`，网页默认 `http://127.0.0.1:8098/`。

这是脚本游客与模拟操作员控制的真实 Gazebo 运行，综合评定 PASS_WITH_RISK；团队状态来自仿真脚本，不能替代后视视觉团队跟踪，实体音频与硬件安全未验证。实测最小人机中心距 1.270 m，不将 2.05 m 目标选择余量说成全程保证。多次失败轮保留，尚无重复稳定性结论。详细范围见 `visitor_team_implementation.md`。

下文 487 项全量测试是游客扩展前的代码基线；新增网关并发停车、静止讲解停车路由、游客目标与网页接口已通过 97 项最终定向回归（`tests/visitor-full/targeted_final.log`）。此次未重新执行全量测试，不能把旧全量结果当作新增代码的完整回归。下文 E07 的 NOT_RUN 描述保留为旧阶段基线；新增单次脚本团队演示尚不满足视觉团队跟踪与广泛情景验收。

---

日期：2026-11-22
项目：`heritage_temi_robot`
代码基线：`main` / `057761908e386f3d0ba7a779d61b860a15debbda`
交付状态：**阶段 2.7 部分完成。软件构建和全量自动化测试通过；两轮安全终点 Gazebo 五区导览与人员离开恢复通过（带速度标定风险）；多人、横穿、多速度矩阵、性能、回放展示和实体 temi 验收尚未完成。**

未提交或推送 GitHub。本文把实现、自动化验证、两轮 Gazebo 结果和实体设备限制分开报告。

## 执行摘要

- ROS 2 Humble 七包构建成功。全 `tests` 目录最新结果为 **487 passed、0 failed、0 skipped**，无 `--ignore`；测试使用隔离 Domain 230，运行前后节点清单均为空。
- 实验运行器、独立人物运动阶段、保守几何风险中止、动态速度上限参数、恢复资格与 UUID 校验、性能/距离分析和相机外参参数化均有代码及测试证据。
- 原始 S01 配置曾因准备阶段失败；在真实运动验证中，1.4 m 目标以 `PREDICTED_GEOMETRY_RISK` 安全中止，保留为 FAIL。不得把它改写成成功。
- 变更为 3.5 m 安全终点并让人物向左侧离开后，Gazebo 已完成两轮含人物接近、机器人安全停车、持留、真实侧向离开、新 UUID 继续 zone_1、五区导览和出口的完整运行。路线均为 `COMPLETED`、7/7 目标，分别用时 320.976 s 和 325.411 s。两轮的分析均为 **PASS_WITH_RISK**：规定的 0.3 m/s 干扰前速度标定窗口未达标，且 Gazebo 无可用接触传感器。
- 这两轮不能证明多速度策略、重复导览稳定性、人物横穿/人群/团队闭环或实机安全。全局项目仍未完成阶段 2.7。

## 验证矩阵摘要

| 项目 | 状态 | 实际结果 |
|---|---|---|
| E01：无干扰正常路线对照 | NOT_RUN | 主证据路线包含动态人物，未另跑正常无干扰路线 |
| A：审计、隔离运行器与边界测试 | PASS | 已有配置校验、隔离域/端口、唯一目录、失败记录与自有进程清理测试 |
| B：人物持续运动与风险中止 | PASS_WITH_RISK | 原 S01 因预测几何风险 FAIL；两轮安全终点均记录停车后人物继续运动、真实离开与正几何间隙；无接触反馈 |
| C：E06 软件恢复与竞态审查 | PASS_WITH_RISK | 20 项审查及软件回归；安全终点两轮均由旧 UUID 停车、新 UUID 继续同一目标；CLEAR 在新 UUID 启动后到达，依据原始事件另行复核 |
| D1：速度/距离分析 | PASS_WITH_RISK | 两轮同一安全终点配置均有阶段、距离、速度分析；0.3 m/s 规定标定窗口均不合格，S02–S04 与跨配置对照未运行 |
| E03/S01 原始目标配置 | FAIL | 1.4 m 终点预测几何风险，人物留场并安全中止；详见原始 truth |
| E03/S01 安全终点变体 | PASS_WITH_RISK | 两轮完整路线及动态人物恢复；配置不同于原 S01，不能覆盖原失败 |
| E02：人数增加/拥挤限速 | NOT_RUN | 没有同路线无人/多人对照及物理速度贡献证据 |
| E04：A/B/C 人物横穿 | NOT_RUN | 相机链路冒烟不等于人物横穿；未取得三类横穿闭环数据 |
| E05：危险距离停车 | PASS_WITH_RISK | 两轮综合场景观察到人员距离触发 STOP；不是独立 E05 多工况验收 |
| E06：真实离开后恢复 | PASS_WITH_RISK | 两轮恢复复核 PASS；仍是单一配置的重复运行，接触传感缺失，不能外推为广泛稳定性 |
| E07：三人团队掉队 | NOT_RUN | 无真实三人 Gazebo 和人工确认流程记录 |
| E1：全量测试和 WebSocket | PASS | 487 passed / 0 failed / 0 skipped；另有 WebSocket 专项 19 passed |
| E2：7 轮连续导览 | NOT_RUN | 计划 7 个独立场景；目前完成 2 轮同配置动态安全终点导览，未完成稳定性统计 |
| E3：60 秒性能基准及优化对照 | NOT_RUN | 未采集规定窗口、P50/P95 或前后对照 |
| E4：相机 A–D 传感器冒烟 | PASS_WITH_RISK | 独立 Gazebo RGB/Depth/CameraInfo/TF 样本通过；未进行 YOLOX 和测距准确率比较 |
| F1：LIVE/RECORDED 数据可视化 | NOT_RUN | 现有展厅页面可用；显式模式、事件回放与评审用实测截图未完成 |
| F2：文档与证据索引 | PASS_WITH_RISK | 本报告、计划状态、矩阵、指南和索引已更新；缺失素材按未执行列明 |
| 实体 temi | HARDWARE_REQUIRED | 无设备；未发送实体运动命令 |

逐项输入、来源和限制见 [`validation_matrix.md`](validation_matrix.md)。

## 构建与自动化测试

- 构建命令：`bash scripts/build_ros2.sh`。七包完成，退出码 0。日志：[`tests/late-fixes-20261122/ros2_build_final.log`](tests/late-fixes-20261122/ros2_build_final.log)，SHA256 `a8c2cbc09ecf76690e7e7dcd7ceb9aaa70efdc39340651cac209cdc7797b243d`。
- 全量命令：`python -m pytest -q tests`（项目虚拟环境，完整目录，无 `--ignore`）。**487 passed in 187.89s**，退出码 0、无失败和跳过。日志：[`tests/late-fixes-20261122/full_suite_final.log`](tests/late-fixes-20261122/full_suite_final.log)，SHA256 `4b301ea5a8db35af23711a2b9d0c04fd7997ea9f52b82664c3a75c1e36163e2b`。
- Domain 230 前后均为空：[`domain_pre_final.json`](tests/late-fixes-20261122/domain_pre_final.json)、[`domain_post_final.json`](tests/late-fixes-20261122/domain_post_final.json)。Domain 226 未使用。
- WebSocket 专项历史日志 [`tests/websocket-targeted-20261122-032308/websocket.log`](tests/websocket-targeted-20261122-032308/websocket.log)：19 passed。最新全目录回归也包含相应 WebSocket 文件。
- 定向运行器/Nav2/速度测试日志为 [`targeted_nav_speed_runner.log`](tests/late-fixes-20261122/targeted_nav_speed_runner.log)，102 passed；更新恢复证据校验后又执行了上面的全目录回归。
- 运行环境为 Python 3.10 / ROS 2 Humble。测试日志记录最终结果；自动化通过不等于完整 Gazebo 场景或硬件验收。

## Gazebo 动态导览运行

两轮证据目录：[`20261122T044704Z-S01-SAFE-ENDPOINT-r001/`](experiments/S01-SAFE-ENDPOINT/20261122T044704Z-S01-SAFE-ENDPOINT-r001/) 和 [`20261122T101824Z-S01-SAFE-ENDPOINT-r001/`](experiments/S01-SAFE-ENDPOINT/20261122T101824Z-S01-SAFE-ENDPOINT-r001/)。第二轮已离线生成 `analysis/analysis.json`、`analysis/recovery_validation.json`、`analysis/distance_speed.svg`、`analysis/phase_timeline.csv` 和 `evidence_summary.json`；每轮摘要均含原始文件 SHA256。

配置：官方展厅，机器人设定上限 0.3 m/s，人物 0.1 m/s，人物目标 3.5 m；到达后持留，再向左离开 3.1 m。Gazebo 真值显示人物实际路径约 4.10 m，阶段为 `WAIT_NAV → APPROACH → HOLD_TARGET → LEAVE → HOLD_CLEAR`，人物在安全停车后仍继续移动并最终留在场景中。

第一轮的主要结果见第一目录摘要，路线用时 320.976 s、最小中心距 0.992 m、估算几何间隙 0.175 m。第二轮的主要结果如下：

- 第二轮 Tour Manager 状态 `COMPLETED`；路线为 `wait → zone_1 → zone_2 → zone_3 → zone_4 → zone_5 → exit`，7/7 目标完成，用时 325.411 s。
- 第二轮有效视觉首次检测约 3.801 m。分析器记录到较早的 RGB-D 候选样本，但稳定人数状态无效，因此没有把它当作有效 RGB-D 检测距离。第一轮同样只报告有效视觉距离，RGB-D 候选无效。
- 第二轮人员距离控制器停车请求中心距约 1.317 m；匹配停稳响应约 0.997 s，事件确认距离约 1.205 m，真值停稳附近中心距约 1.205 m。第一轮对应数据为请求约 1.309 m、响应约 0.901 s、确认约 1.203 m。
- 第二轮真值最小中心距：接近 1.180 m、持留 1.179 m、离开 0.989 m；按 URDF/SDF 外接圆与 0.1 m 余量估算的最小几何间隙为 0.172 m。第一轮最小中心距 0.992 m、间隙 0.175 m。两轮均未记录预测风险或几何重叠。该数值是保守二维几何代理，**不是接触检测或碰撞认证**；`contact_observed=null`。
- 两轮安全恢复复核均为 PASS：第一轮旧/新会话为 `bc36466931b44206a9b7c7359f799a3e` → `b87d0b3078564615a36e2af390964441`；第二轮为 `891d3c2b0604404cb8971eae01521071` → `a99328e6634642d3a9cc20367a33fd8b`，两轮均恢复同一 `zone_1`。本轮恢复 JSON 记录源报告与真值哈希。CLEAR 接收先后按计划不单独作为失败门槛。
- 两轮速度标定门槛均未通过：第一轮窗口中位数 `0.0000198 m/s`、覆盖 1.903 s；第二轮中位数 `0.0000363 m/s`、覆盖 1.900 s，目标均为 0.3 m/s。因此两轮都不能作为已达标速度档证据。运行中的速度曲线不替代规定标定窗口。
- 问答来源为中国非遗官网条目；`spoken=true` 代表 Mock Speak Action 成功，**没有真实音频/TTS 验收**。

## 保留的失败与尝试分母

- 原 `S01` 目录保留了 7 次尝试：前 6 次分别受启动/游客准备/同意状态门槛阻断，没有完整动态路线；第 7 次在 1.4 m 目标处以 `PREDICTED_GEOMETRY_RISK` 安全中止。原始失败见 `experiments/S01/20261122T041835Z-S01-r001/tour/scenario/truth.json`。
- `S01-SAFE-ENDPOINT` 共 7 次：前 5 次失败或未完成，后 2 次侧向离开后完成五区路线，均保留各自原始记录。
- 因此报告 **2 次完整动态导览**，均为同一安全终点配置且分析为 PASS_WITH_RISK；不计算 7 轮稳定性成功率或多速度成功率。原 S01 FAIL 与安全终点变体分开计数。

## 相机与展示

A/B/C/D 各有一次独立 Gazebo 传感器冒烟记录，RGB、Depth、CameraInfo 和 TF 链路均通过；B 的 TF 约向下 10°。这些结果证明传感器消息与几何链路，不证明有人的 YOLOX 召回、RGB-D 误差、A–D 优劣或实体安装位置。详情见 [`competition/evidence_index.md`](competition/evidence_index.md)。

现有 Three.js 展厅仍可用于场景展示，但本轮没有交付 ROS 实测数据回放、LIVE/RECORDED/DEMO 固定标识的验收截图或完整感知面板。展示操作见 [`competition/demo_guide.md`](competition/demo_guide.md)。

## 未完成工作与下一步

1. 先修正实验启动时序，使人物开始前完成独立直线速度校准；按实际 odom 结果决定该速度条件是否达标，再做 S02–S04 和可比对照。
2. 按相同路线与起点执行 E02 无人/1/3/5 人对照和人数渐变；不把人数伪装成密度。
3. 执行 E04 A/B/C 横穿及 E07 三人掉队/人工确认，保存视觉、激光、速度、恢复的独立证据。
4. 补足计划的 7 个独立导览运行、60 秒性能基线/优化对照、相机 A–D 有人场景比较以及真实数据回放。
5. 获得实体 temi 后再做 SDK、真实制动、传感器标定和真实音频验收。

环境可用内存有限且没有 swap，Gazebo 应串行运行。全过程未使用实体 temi、未触碰 Domain 226、未自动提交或推送 GitHub。
