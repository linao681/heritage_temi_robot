# heritage_temi_robot 阶段 2.7 Implementation Plan（执行记录）

> **执行记录（2026-11-22）：** 按用户授权读取原始阶段 2.7 任务并执行本计划。复选框仅在对应实现或证据实际完成时勾选；阶段整体尚未完成，未运行项目保持未勾选。最终状态见 `final_report.md`。

**Goal:** 将阶段 2.6 的单次停车验证升级为可重复、分来源、包含持续接近与真实离开恢复的 Gazebo 闭环实验，并完成阶段 2.7 的多人、回归、性能和展示交付。

**Architecture:** 保持现有 ROS2 七包及 Nav2 安全链，扩展人物场景、实验编排和证据分析。人物运动独立于机器人停车状态；恢复由控制策略与 Tour Manager 共同约束，实验脚本仅操作既有业务入口。复用现有网页，优先串行运行 Gazebo。

**Tech Stack:** Ubuntu 22.04、ROS2 Humble、Gazebo Classic、Nav2、Python 3.10、YOLOX-S ONNX、RGB-D、LaserScan、Three.js；WebSocket 测试使用项目虚拟环境。

## 0. 全局约束和交接基线

- 工作目录：`/home/linao/heritage_workspace/heritage_temi_robot`。
- 已知 Git 基线：`057761908e386f3d0ba7a779d61b860a15debbda`，`main`，已推送 GitHub。执行时重新核对，不能覆盖更新。
- 阶段 2.6 的 `final_report.md` 是提交前快照，其中“未提交/未推送”不是当前 Git 状态。保留旧报告，新增当前状态说明。
- 历史测试为 **355 passed**，显式排除两份 WebSocket 文件；不是整个 tests 目录全部通过。
- 本地仍有未跟踪的旧运行目录；不要 `git clean`、批量暂存、删除或改写历史原始数据。
- 不自动 commit/push/创建远程 PR；不 sudo、不修改系统 Python 或全局配置；不操作实体 temi。
- Domain 225 及其他已有域先视为用户占用。不得假设上次清空的 232 仍可用。检查空域、锁和端口再启动。
- 不关闭碰撞保护、不放宽断流停车、不伪造框/测距/人数/密度、不用删除人物制造恢复。
- 所有状态统一使用 `PASS / PASS_WITH_RISK / FAIL / NOT_RUN / BLOCKED / HARDWARE_REQUIRED`。
- 每项结论区分单测、ROS2 注入、Gazebo 集成、历史证据和实体设备依赖。
- 各包完成后记录文件变更与证据；失败不能改名为通过。建议同配置至多连续尝试 3 次；无新诊断依据时停止重复，转独立任务。

### 0.1 已核实的代码入口与风险

| 现有入口（相对项目根） | 当前职责 / Luna 要留意的事实 |
|---|---|
| `scripts/spawn_people_scenario.py` | `PeopleScenario`、`scene_positions()`、`trajectory_position()`、`trajectory_duration()`；人物通过 SetEntityState 运动，需防止跨帧穿透 |
| `scripts/run_phase25_clean_tour.py` | `TourEvidence`、动态证据及离开恢复复核；接近场景现在自动加 `--stop-on-safety-stop`，并加 `--remove-after` |
| `scripts/record_phase2_topics.py` | 已记录人员距离、人数有效性、速度输入有效性、Gazebo 真值；采样 CSV 不能代替全部事件原始时间戳 |
| `simulation/navigation.launch.py` | FollowPath 与 smoother **初始**线速度上限 0.35 m/s；运行时 Nav2Transport 可更新参数，须同时检查更新与回读结果 |
| `temi_speed_controller/speed_policy.py` | 已有动态停车模型；`SpeedConfig`、`SpeedInputs`、`SpeedController.update()`；不要重复开发 |
| `temi_speed_controller/speed_controller_node.py` | 已有停止/恢复 future，需审查请求发出与回调时安全条件是否仍有效 |
| `temi_bridge/nav2_transport.py` | 取消目标、odom 停稳、速度参数更新/回滚与回读；已有基础须先复用 |
| `heritage_tour_manager/visitor_assist.py` | 已有匿名人数去抖与团队协作；`observe()`、`tick()`、`snapshot()`；恢复服务由 `ros_tour_node.py` 接入 |
| `requirements-websocket.txt` | 目前固定 `websockets==16.1.1`，先检查现有虚拟环境与安装可用性，不猜测版本可安装 |
| `visualization/ros_hall/` | 已有展厅，`ros-live.js`、`index.html`、`style.css` 等；无需另造前端 |

上述包缩写的完整根路径是 `ros2_ws/src/<包名>/<包名>/`。以下新增文件名是本计划约定，不表示仓库已经实现这些接口。

## 1. 执行顺序与停止门槛

1. A：审计、证据格式、隔离运行入口 → 核对当前源码确实被运行、进程可清理。
2. B：人物独立运动与持续接近 → 人物到达终点保留，几何风险能结束本轮、不能误报恢复。
3. C：E06 恢复依据与专项审查 → 新鲜安全窗口、停车确认、任务与人工优先级成立。
4. D：多速度、E04、E02、E07 → 逐项真实闭环；不可运行的工况留实录与原因。
5. E：完整回归、稳定性、性能、相机 A–D → P0 阻塞时仍推进独立软件任务。
6. F：可视化、素材、交付审计 → 只展示有证据的能力。

更高速度的风险运行必须在 B 的几何中止和 C 的恢复门槛完成后开展。任一工况出现保护失效、几何重叠或异常恢复，停止该配置的后续高速运行，分析后再恢复；低风险独立任务继续。

## 2. A：审计与可复现执行环境

**读取/复用：** `scripts/start_phase25_system.sh`、`scripts/phase25_preflight.py`、`scripts/build_ros2.sh`、`docs/phase2_6_overnight/`、`docs/PROJECT_STATUS.md`、`docs/next_phase_plan.md`。

**新建：** `docs/phase2_7/{progress.md,code_changes.md,validation_matrix.md,blockers.md}`、`scripts/run_phase27_experiment.py`、`config/phase27_experiments.yaml`、`tests/test_phase27_experiment_runner.py`。只有需要增强现有启动参数时才修改旧启动脚本。

- [x] 记录 `git status --short`、`git branch --show-current`、`git log -5 --oneline`、磁盘/内存、当前进程及 ROS 域/端口；只保存相关命令，不输出凭据环境变量。
- [x] 对照代码与阶段 2.6 E03/E05/E06 审计，建立 `validation_matrix.md` 初始行；本轮结果先为 NOT_RUN。
- [x] 新运行器读取 YAML 的 `id / layout / route / robot_speed_mps / actor_motion / timeouts / seed`，拒绝 NaN、负速度、不支持的场景和已存在输出目录；配置复制到唯一 `experiments/<ID>/<时间>-<配置>-r<轮次>/`。
- [x] 每轮记录 `manifest.json`：基线 SHA、dirty 文件清单/补丁摘要、配置 SHA256、模型 SHA256、解释器/依赖版本、域/端口、开始/结束时间、源码导入路径、数据来源、预定断言与资源上限。
- [x] 启动前先绑定端口、检查锁与空域；拒绝冲突。保存 PID/进程组和本轮资源名单；失败/超时也走 finally 清理，仅清理本轮拥有资源。
- [x] 复用现有 preflight 检查 clock 实际推进、定位/odom/RGB/Depth/CameraInfo/scan 新鲜度和服务/action；不能仅以进程存活视为就绪。
- [x] 写测试证明：已占用端口/非空域拒绝启动、超时保留失败记录、目录不覆盖、清理不触及外部 PID。

**验证命令：**

```bash
cd /home/linao/heritage_workspace/heritage_temi_robot
source /opt/ros/humble/setup.bash
bash scripts/build_ros2.sh
source ros2_ws/install/setup.bash
python3 -m pytest -q tests/test_phase27_experiment_runner.py
```

预期七包构建成功、新运行器边界测试通过。独立输出源码路径与 install 路径，避免旧 overlay 掩盖修改。

## 3. B：人物独立运动、终点保留和风险中止（P0-1）

**修改：** `scripts/spawn_people_scenario.py`、`scripts/run_phase25_clean_tour.py`。
**新增：** `scripts/phase27_scenario.py`（纯轨迹/状态与几何分析）、`tests/test_phase27_actor_motion.py`；补充 `tests/test_gazebo_people_scenario.py`。

- [x] 在现有轨迹函数外增加小型人物阶段逻辑：`WAIT_NAV → APPROACH → HOLD_TARGET → LEAVE → HOLD_CLEAR`；仅因风险或显式取消进入 `ABORTED`。机器人 STOPPING/STOP_CONFIRMED 是被记录事件，独立运动模式不以它作为冻结条件。
- [x] 运行器增加显式 `--continue-after-robot-stop`、`--hold-at-target-sec`、`--leave-after-hold` 和配置入口；保留旧命令兼容性。新阶段 2.7 配置必须显式启用持续接近，并停用自动 `--remove-after`；最后由实验统一清理，清理后的 CLEAR 不计入恢复证据。
- [x] `target_distance_m` 定义为接近阶段开始时机器人位姿坐标系中的终点中心距离，默认 0.60 m；整个轨迹固定锚点，不随机器人位置反复追踪。另记录实时中心距离，防止把终点参数当成实际停车间隙。
- [x] HOLD_TARGET 保留模型；LEAVE 必须真实移动到预定义可通行位置并经 Gazebo 回读确认，HOLD_CLEAR 持续观察。到达终点不是“感知恢复”。
- [x] 每次 move 前做上一真实位姿到下一指令位姿的扫掠距离检查，并在回读后复核；SetEntityState 可以绕过动力学接触，不能只靠 SDF collision 标签防穿透。
- [x] 几何包络来自 URDF/SDF 的 collision 外形及其姿态；无法精确表达时用保守近似并在 manifest 标明假设。预计扫掠相交时停人物于上一验证位置，停止本轮实验并请求机器人业务停车。记录“预测几何风险/已观测重叠/接触未知”，不将它算作完整轨迹成功。
- [x] 可用时采集接触反馈；不可用时 `contact_observed=null`。不能把没有反馈填成 false，不能把几何间隙当接触认证。
- [x] 人物停止更新不能截断传感器记录；保持观察，直到实测停车确认、持留窗口完成、离开恢复完成或总超时。

**建议接口（新增纯逻辑，单位写入 docstring）：**

```python
# scripts/phase27_scenario.py
# pose = (x_m, y_m, yaw_rad); phases 仅使用上文名称
# 配置由运行器验证后传入；纯函数不发 ROS 命令
# 实现时返回值采用下列键，分析器及测试共享同一契约
# actor_step(config: dict, elapsed_sec: float, anchor: tuple) -> dict
# {"phase": str, "pose": tuple, "finished": bool}
# swept_gap(previous_pose: tuple, next_pose: tuple,
#           robot_pose: tuple, envelope: dict) -> float
```

**具体测试：** 机器人停车事件发生后人物下一步仍前进；终点位置不变且模型存在；短路径不会跨过机体；预计接触中止不触发 LEAVE/PASS；只有真实离开才进入 HOLD_CLEAR；非有限参数被拒绝。

**Gazebo 验收：** 先以机器人 0.3、人物 0.1 m/s 做一轮；确认停车后至少两个独立新鲜真值样本仍显示人物位移。如果 0.60 m 终点会触发包络风险，应保留风险中止结果，不修改验收冒充到达成功。至少一个安全终点配置完成“接近→持留→真实离开→恢复”。

**本轮状态：** 代码与定向测试完成。原 S01 的 1.4 m 目标因 `PREDICTED_GEOMETRY_RISK` 安全中止（FAIL）；3.5 m 安全终点、左向离开变体完成两轮真实 Gazebo 人物接近/持留/离开及五区路线。两轮速度标定未达标，整体 `PASS_WITH_RISK`；前序失败和真值均保留，详见 `validation_matrix.md` 与主运行 `experiments/S01-SAFE-ENDPOINT/20261122T044704Z-S01-SAFE-ENDPOINT-r001/`。

## 4. C：E06 恢复依据及导航安全审查（P0-3、P1-8）

**审查/最小修改：**

- `ros2_ws/src/temi_speed_controller/temi_speed_controller/{speed_policy.py,speed_controller_node.py}`
- `ros2_ws/src/visitor_perception/visitor_perception/{perception_fusion.py,ros_perception_fusion.py}`
- `ros2_ws/src/temi_bridge/temi_bridge/{nav2_transport.py,nav2_backend.py}`
- `ros2_ws/src/heritage_tour_manager/heritage_tour_manager/{tour_manager.py,ros_tour_node.py}`
- `tests/{test_speed_controller.py,test_nav2_backend.py,test_nav2_arrival_stop.py,test_perception_fusion.py,test_tour_manager.py}`；新增 `tests/test_phase27_recovery.py`。

- [x] 先回放旧 E06 约 90 ms 的事件窗口：原始样本时间、接收时间、记录时间分别列出。检验究竟是到达次序还是决策依据缺失；不能仅重排事件让报告通过。
- [x] 为每次恢复记录 `decision_id / stopped_session_id / original_target / evidence_sample_id / sample_age_sec / clear_since / hold_sec / odom_age_sec / position_age_sec / manual_latched / error_latched / request_sent_at / service_result / new_session_id`。有字段就复用，仅添加缺失字段；优先增加 JSON 状态字段，避免无必要修改 ROS 消息定义。
- [x] 安全窗口以单调时间计算；新鲜人员状态、有效激光、定位/通信、匹配 UUID 的停车确认连续满足既有 recovery_hold_sec 才可请求恢复。任一失效/倒序/时间回退重置窗口。有效 NO_PERSON_OBSERVED 不等于确定人员离开；视觉盲区下还需激光有效且安全。
- [x] 恢复请求前再次核对当前任务仍存在、暂停来源允许自动恢复、没有人工/团队确认等待和故障锁存。恢复期间新危险撤销资格并保持停车；无法撤销的旧异步回调不得解锁新任务。
- [x] `_resume_future` 一次只允许一个在途请求；以决策与会话关联回执，不因旧 future 成功或旧 STOP_CONFIRMED 修改新会话。业务实际恢复入口也需校验当前资格，不能仅在发送端检查。
- [x] 若既有 Trigger 无法关联竞态，在保持服务兼容的前提下先用双方可读取的当前安全状态/会话进行二次核验；确需新接口时明确 schema 并同步调用方测试，不能依靠任意 sleep 规避竞态。
- [x] 逐项审查附件 P1-8 的 20 个问题，写 `safety/nav2_review.md` 的“证据→可复现用例→结论→修复”表。无证据不重构。额外验证角速度大但线速度小不能确认停稳，停车确认后再次运动应撤销静止资格。

**必须先失败再修复的测试：** 安全样本过期、乱序旧 CLEAR、窗口被中断、取消与恢复同 tick、旧 future 返回、新 UUID 收到旧停稳、两路停车同时请求、恢复重复调用、参数部分更新回滚、TF/odom 过期、冷启动没有完整观测。每个缺陷先保留基线复现日志。

**E06 验收：** 同一人物真实接近/持留/离开；恢复前已存在足够新鲜安全依据；停车确认关联旧 UUID，新 UUID 继续原目标；不删除人物、不手动注入 CLEAR。CLEAR 接收先后不作为单独通过门槛。

## 5. D1：动态停车多工况与距离/速度分析（P0-2）

**修改：** `simulation/navigation.launch.py`、`scripts/start_phase25_system.sh`（必要参数透传）、`config/phase27_experiments.yaml`、新运行器。
**新增：** `scripts/analyze_phase27_experiment.py`、`tests/test_phase27_analysis.py`；复用现有速度策略，只有复现缺陷才修改策略。

- [x] 将 Nav2 初始线速参数改为可配置且默认仍为 0.35；同步 FollowPath.max_vel_x、max_speed_xy 与 smoother.max_velocity[0]，不改角速/避障保护。
- [ ] 每轮保存初始参数、每次运行时限速请求/结果/回读与 odom；未知密度默认速度也会限制速度，0.7 m/s 工况通过显式仿真配置设置合适巡航上限，仍保持密度未知且所有距离保护生效。
- [x] 对 0.3 m/s 档记录了干扰前窗口并按门槛标记 `speed_condition_not_met`；窗口 20 个样本、覆盖 1.903 s、中位数约 0.0000198 m/s，故速度条件未通过。尚未完成其他速度档校准。
- [ ] 最小配置矩阵如下，先从低风险组向高风险组推进；速度单位 m/s。每组先做一次，高风险门槛通过后再复测，时间允许各补到 3 次。

| 配置 ID | 机器人设定 | 人物设定 | 用途 |
|---|---:|---:|---|
| S01 | 0.3 | 0.1 | 低低，持续接近与真实离开 |
| S02 | 0.3 | 0.5 | 低快 |
| S03 | 0.5 | 0.25 | 中中 |
| S04 | 0.7 | 0.25 | 较快中，需先确认实际速度达标 |

- [x] 单轮分析输出 MOVING / BRAKING / STOP_CONFIRMED_HOLD / ACTOR_LEAVING / RECOVERED 阶段计数与时间线；人物运动阶段独立记录。证据：安全终点运行 `analysis/phase_timeline.csv`、`analysis/analysis.json`。
- [x] 单轮分析记录首次有效视觉、RGB-D候选样本有效性、人员减速、匹配停车请求/确认的时间与距离；RGB-D稳定人数无效样本明确标无效，没有把它当有效测距。证据：`analysis/analysis.json`。
- [ ] 输出停车响应、从请求到确认的 odom 路程积分、各阶段真值最小中心距与几何间隙、视觉丢测、激光距离、停车原因和新 UUID；机器人里程计距离与 Gazebo 真值距离分别报告。
- [ ] 距离真值已被旧生成器清理截断时标为未知，不用旧模型位置延展；人物还在靠近时不得将机器人归零解释为所有风险解除。
- [ ] 输出 `safety/speed_comparison.csv` 与独立 PNG/SVG 速度、距离、状态曲线；新旧算法需要同配置复现或明确不能比较，不比较不同条件的最小值来宣称提升。

**分析器断言例：** STOPPING 后未有匹配 STOP_CONFIRMED 时响应耗时为 null/失败；采样重复不算新安全证据；所有几何重叠轮为 FAIL；运行结束与人工中止不能等同 COMPLETED；速度条件失败独立显示。

## 6. D2：E04 三类真实横穿（P0-4）

**修改：** `scripts/spawn_people_scenario.py` 的横穿锚点/轨迹配置、新配置与分析器；仅定位到具体视觉缺陷才改 detector/depth 代码。
**检查文件：** `ros2_ws/src/visitor_perception/visitor_perception/{ros_person_detector.py,person_detector.py,ros_depth_association.py,depth_association.py}`。

- [ ] 记录实际 RGB/深度配对时间、CameraInfo、TF、推理耗时、全部帧数及有/无检测帧，解释旧“4 条样本”是抽样、去重还是视觉真的不足。
- [ ] 设计 A 前方视场内、B 视觉盲区激光覆盖、C 双源同时覆盖三条真实轨迹。B 的保护依据是障碍，不能认定激光识别了人。
- [ ] 先离线几何检查轨迹，再固定机器人起点/方向/导航目标，用活动 UUID 与 odom 触发；最低覆盖低速和中速横穿。真实 RGB 框及深度关联保存可核查片段。
- [ ] 为视觉检测、视觉测距、激光有效性、限速生效、实际避障/停车、恢复分别判定。渐进调速必须有目标上限回读变化与 cmd_vel/odom 对照；Nav2 自主绕行则按真实行为记录。
- [ ] 同条件无人路线作为对照。感知状态变化但实际速度原本已低于上限时，仅判“策略响应已证实、物理减速贡献未证实”。

验收产物：`experiments/E04/<A|B|C>-<速度>-<轮次>/` 的配置、RGB 证据、真值、原始事件、六项独立结论。人数/框不能从 Gazebo 真值生成。

## 7. D3：E02 人数增加与可解释限速（P0-5）

**修改/测试：** 新场景配置与运行器；按需修改 `visitor_monitor.py`、`perception_fusion.py`、`speed_policy.py` 及对应测试。

- [ ] 同一通行直线路段独立运行无人、1、3、5人和局部拥挤，并另跑 0→1→3→5→散开序列。真实模型位置不能占据静态展柜，保持有意义的可通行路径。
- [ ] 保留真实 YOLOX 稳定人数、最近人员距离、激光障碍距离和各自有效位。人群局部占用若实现，先定义区域、面积/单位和有效期，字段命名为仿真估计，`crowd_density` 未标定时维持未知。
- [ ] 先确认现有策略是否在“人数变多但密度未知”下会变化；若无此功能，增加显式有效人数的保守限速分支与配置，并先测试缺失/过期人数不能提高速度。不要把 5 人编码为密度 1.0。
- [ ] 留下“计数变化→策略决策→Nav2 参数回读→cmd_vel→odom”全过程。对照组采用同路线/初始条件，改变最近距离时单独标记混杂因素。
- [ ] 对散开场景验证持续确认与限速滞回，不因单帧零人立即提速；记录速度命令次数/目标变化幅度，评估抖动。

通过要求：至少一组人数/区域因素的策略上限确实约束了实际速度，并有无人对照。路径本身限速导致证据不足则换直线路段，不能只凭状态标签给完整 PASS。

## 8. D4：E07 三人匿名团队掉队（P0-6）

**复用/修改：** `visitor_assist.py`、`visitor_monitor.py`、`tour_manager.py`、`ros_tour_node.py`、`scripts/spawn_people_scenario.py`。
**测试：** `tests/test_visitor_tour_integration.py`、`tests/test_visitor_monitor.py`、新增 `tests/test_phase27_group.py`。

- [ ] 真实三人模型通过相机得到稳定人数，由现有协作入口确认 expected_count=3，再启动真实 Tour Manager；显式记录操作员同意事件。
- [ ] 使用可见性合适的长路段，让一人落后；短遮挡不足以掉队，持续稳定不足触发等待；odom 必须确认停车。
- [ ] 三人重新集合只进入“可人工确认”，不得自动调用普通安全恢复。确认调用现有业务服务并记时间/操作员来源/当前任务，不能直接发 Nav2 Goal。
- [ ] 覆盖未确认保持等待、陌生人加入、确认与取消竞争、旧 UUID complete、超时和取消；陌生人与原成员在匿名感知中无法区分，报告必须写身份未知。
- [ ] 检查自动速度恢复不会绕过团队暂停来源；人工确认也不能绕过人员近距、断流或故障锁存。

验收：至少一轮真实三人→掉队→实停→重聚→未确认仍等待→操作员确认→新 UUID 继续原展区；另有取消优先级证据。软件注入边界测试与真实三人 Gazebo 结果分列。

## 9. E1：补齐 WebSocket 与全目录回归（P1-7）

**复用：** `.venv`、`requirements-websocket.txt`、`tests/test_gateway_websocket_integration.py`、`tests/test_websocket_backend.py`；只在版本确有错误时修改依赖声明并解释依据。

- [x] 检查 `.venv/bin/python -V`、是否能 import rclpy/pytest/websockets 及相关版本。优先现有 `.venv`；若不兼容 ROS 系统包，创建独立项目测试 venv，使用 `--system-site-packages`，不动系统 Python。
- [x] 在项目 venv 安装 requirements；网络/版本不可用先保存安装失败日志，再查依赖兼容，不删测试或 ignore。测试代码使用现代 `websockets.asyncio` 与 `proxy=None`，版本选择要验证 API。
- [x] 单跑两份缺口测试，再运行整个 tests 目录。部分测试硬编码 Domain 229 等，执行前审查所有测试域；避免与 Gazebo 同时运行。冲突时给测试提供可注入隔离域，不能终止外部节点。
- [x] 按项目虚拟环境执行全量序列；最终 `487 passed / 0 failed / 0 skipped`，七包构建退出码 0。证据和 SHA256 见 `tests/late-fixes-20261122/`：

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
.venv/bin/python -m pip install -r requirements-websocket.txt
.venv/bin/python -m pytest -q tests/test_gateway_websocket_integration.py tests/test_websocket_backend.py
# 新建唯一日志目录并 export ROS_LOG_DIR 后执行，确保不在用户域
.venv/bin/python -m pytest -q tests
```

- [x] 禁止 `--ignore`/只选局部目录冒充全量。采集确切 PASS/FAIL/SKIP；SKIP 列理由，collection error 也写入结果。
- [x] 报告使用基线 SHA + 当前修改摘要标识待提交代码，不编造新提交号。保存完整日志到 `docs/phase2_7/tests/` 或可复查的外置原始目录并给 SHA256，不能只引用易失 `/tmp`。

## 10. E2：连续导览与失败统计（P1-9）

**新增/复用：** 新运行器、`scripts/run_phase25_clean_tour.py`、`scripts/analyze_phase27_experiment.py`。

- [ ] 目标 7 个独立轮次：正常 3、动态人物 2、专门问答 1、多人 1。正常轮也可以包含问答，但不得把一次运行重复算成两个独立轮次。
- [ ] 每轮独立 reset/清理并复核初始状态；无需每次重启 Gazebo，但必须记录复用与重置策略，失败重启另建 run_id。
- [ ] 每轮记录预期7目标、实际目标/UUID/终态、停稳讲解/问答、COMPLETED、自动停车/恢复、人工确认/接管/取消、问答知识来源及 Mock Speak Action 结果。
- [ ] `stability/repeated_tours.csv` 保存全部尝试，包括 preflight 失败；汇总区分启动成功率、有效启动后的导览完成率和全部尝试完成率，明确分母。
- [ ] 导航目标成功率明确是否包含取消后重发任务；7/7站点完成率与 UUID 任务成功率分别统计。平均/最大耗时只用完成轮次，失败耗时独立列。
- [ ] 内存/磁盘不足时减少轮次，报告“计划7、尝试N、完成M”，不能写达标。每轮有有限总超时和资源清理。

## 11. E3：性能采集与有依据的优化（P1-10）

**新增：** `scripts/record_phase27_performance.py`、`tests/test_phase27_performance.py`。
**按证据修改：** `ros_person_detector.py`、`ros_depth_association.py`、`ros_perception_fusion.py`、`speed_controller_node.py`、`nav2_transport.py`。

- [ ] 在推理开始/结束、RGB/深度匹配、融合输入/输出、策略 tick、参数 service 请求/回执添加可关闭、节流统计。记录真实调用边界，不用日志接收间隔冒充耗时。
- [ ] 采集各节点 CPU/RSS、系统内存、消息输入/输出率、缓存长度、Gazebo `/clock` 相对墙钟比率；CPU 数据写清进程/整机、核数与采样窗口。
- [ ] ROS 仿真时间、墙钟 UTC、单调时间分字段；不能将不同进程的 CPU 时钟相减或把跨时钟差作为延迟。
- [ ] 同一机器、模型、场景、随机种子，至少相同 60 s 窗口输出原始样本与 P50/P95/最大值、丢帧/旧帧数量；启动预热不混入稳态。
- [ ] 仅对已证实瓶颈做一次最小优化，如最新帧处理/有界缓存/避免重复 CameraInfo 计算；复跑同配置及相关回归。没有优化后数据就只报告基线。
- [ ] 监测代码开/关做短对照，确认没有明显挤占控制时序；安全检查频率不能为性能而降低。

## 12. E4：相机 A–D 实测（P1-11）

**修改：** `simulation/hall.launch.py`、`simulation/robot/heritage_robot.urdf`（保持默认配置）；必要时新建等价默认 xacro，仅在依赖与展开验证齐全时迁移。
**复用：** `scripts/analyze_camera_coverage.py`、视觉/深度测试与新配置矩阵。

- [x] 由 launch 参数生成本次临时 URDF，确保 robot_state_publisher 与 Gazebo 使用同一描述、RGB/Depth 共用一致外参，不简单替换所有数字。
- [ ] 固定 A：现有高度0.55 m/俯仰0°；B：高度不变、向下10°；C：高度0.70 m/俯仰0°；D：A 的相机，使用现有激光近场保护并补足独立证据。B 的实际 optical axis 方向需 TF 验证，不能只凭 RPY 正负号认定向下。
- [ ] 每组相同模型、路线、速度、距离范围和随机种子；验证 CameraInfo/TF、新鲜帧、实际RGB、YOLOX总帧/有效帧、RGB-D有效帧/误差和近距离丢失时刻。
- [ ] D 不得通过关闭 A 的既有激光保护制造性能差距；若没有额外实现差异，D 是传感互补实验，不报告相对 A 的算法提升。
- [ ] 测距误差以对应检测时刻与 Gazebo 真值对齐，有无检测分母分别保存；不能只用成功测距帧报告总体召回率。
- [ ] 四组各有独立数据后再选建议配置；不具备未来 temi 安装依据时仍标“仿真设计候选”，不默认替换部署参数。

## 13. F1：国赛可视化与真实数据回放（P2-12）

**修改：** `scripts/visualization_bridge.py`、`visualization/ros_hall/{ros-live.js,index.html,style.css}`；按模块职责仅扩展必要文件。
**测试：** `tests/test_visualization_bridge.py`、`visualization/ros_hall/test-runtime.cjs`；按需新增回放解析测试。

- [ ] 保留三维展厅、机器人/路径/五区/导航目标；加入真实 Gazebo 人物位置，明确真值与算法估计来源。
- [ ] 右侧显示人数及有效位、RGB-D距离、激光距离、目标上限、odom实际速度、动态停车阈值、原因、UUID、恢复依据与样本年龄；未知填“未知”，失联保留“过期”标识。
- [ ] 底部显示游客到来、同意、导航、检测、减速、请求停车、STOP_CONFIRMED、真实离开、安全窗口、恢复事件，附时间和来源。
- [ ] 顶部固定显示 `LIVE_ROS2 / RECORDED_ROS2 / DEMO_SIMULATED`。无实时连接不得静默切换为演示动画。
- [ ] 回放读取本轮原始事件/CSV并沿记录时间推进，可暂停与定位；不能读取预设动画生成“实验数据”。优先只读数据入口，保留原有业务控制安全边界。

验证：桥接字段测试、断流/旧帧显示测试、现有前端 runtime 测试；浏览器实看实时与回放两模式并留真实截图，确认页面操作没有新增直接底盘控制通道。

## 14. F2：展示素材、文档和验收（P2-13/14）

**新增/更新：** `docs/phase2_7/competition/{demo_guide.md,evidence_index.md,presentation_materials.md}`、`docs/phase2_7/final_report.md`；更新 `docs/PROJECT_STATUS.md`、`docs/next_phase_plan.md` 的当前状态，保留历史报告结论。

- [ ] 素材涵盖完整五区、E03/E04/E05/E06/E07、E08断流、E10人工取消。每项标本轮/历史、场景、配置、代码版本、数据来源、曲线和局限；未运行则无“实测素材”。
- [x] 已从真实安全终点日志生成速度/距离 SVG 曲线和阶段/停车/恢复时间线；没有将多轮拼接。其余场景的曲线和视频仍未采集。
- [ ] 每个运行目录最少有配置、manifest、原始数据、报告、复核结论；原始大文件外置时有绝对位置、大小、SHA256和取回说明，仓库内保留必要代表样本。
- [x] `validation_matrix.md` 已逐项列条件、结果、数据源、状态、限制和路径；将原 S01 风险失败与安全终点集成结果分开。
- [x] 报告、矩阵、证据索引按实际状态更新；测试数字和日志哈希来自本轮文件；实现、自动化和仿真实测分开。文档注明仿真、Mock 和无实体设备限制。
- [x] 最终报告列明完成、失败、未执行；E02–E07、单轮响应/距离、多轮数量与未完成状态、含 WebSocket 全目录测试、性能/相机/可视化缺项、阻塞和实机依赖。
- [x] 已检查无本轮 Gazebo/ROS 实验进程残留，Domain 230 前后为空，Domain 226 未触碰；`git diff --check` 通过。保留已有工作树改动，只交付文件与报告，未 commit/push。

## 15. Luna 的最小验收清单

- [x] 单轮安全终点真值显示停车后人物继续运动，原 S01 风险中止有原始证据，两轮安全终点均真实离开后恢复；见 `validation_matrix.md`。
- [ ] 多速度表含0.3/0.5/0.7和人物0.1/0.25/0.5的规定组合，实际未达速度有明确失败/限制说明。
- [x] 两轮 E06 新 UUID 恢复均有可追溯安全依据；人工/故障/团队暂停边界有软件回归证据，但相关独立 Gazebo 专项未执行。
- [ ] E04 A/B/C 六个子目标独立验收；E02 有匹配对照及物理限速证据；E07 有真实三人和人工确认。
- [x] 全 tests 目录实际执行，无隐式忽略；487 passed、无失败/跳过，环境限制如实列出。
- [x] 已留存 14 个独立运行尝试（7 个原 S01、7 个安全终点变体），2 个完整路线、12 个失败/未完成；逐轮分母见 `stability/repeated_tours.csv`。但未满足 3+2+1+1 场景配额，E2 仍未通过。
- [ ] 性能数据来自实际测量；相机 A–D 来自独立 Gazebo 运行；网页区分实时/回放/演示。
- [x] 最终报告逐项对应原始记录；未声明实体 temi 已验证，未自动提交或推送。

## 16. 执行记录

已按用户指令读取原始阶段 2.7 附件并执行可运行项目项。每个未通过的 run_id 均保留，阶段 2.6 的 355 项与本轮 487 项口径分开。阶段仍有多个 NOT_RUN 项；见 `blockers.md`。本轮只更新工作树和报告，未自动 commit/push。
