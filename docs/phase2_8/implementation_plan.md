# heritage_temi_robot 阶段 2.8 实施计划

> **执行状态：**用户随后授权按计划实施；当前进度和限制见 `progress.md` 与 `validation_matrix.md`。逐项执行，复选框只在交付物和验证证据齐全时勾选。不得自动提交、推送或调用 Astra 模型。

**Goal：**在现有七包、Android Bridge、Nav2、YOLOX/RGB-D、三人仿真与网页基础上，交付来源清晰的匿名视觉观测、保守团队决策、安全控制验证和真实记录回放。

**Architecture：**相机检测与深度关联进入匿名跟踪、团队观察器，再进入 Tour Manager；激光和感知融合继续服务既有速度控制器。Gazebo 真值独立送评估器和展示层，脚本只在显式业务模式影响团队业务。恢复仍经既有停车确认与导航事务门控。

**Tech Stack：**ROS 2 Humble、Python 3.10、Gazebo Classic、Nav2、现有 YOLOX-S ONNX/OpenCV、Three.js、Android Kotlin/temi SDK。复用已有依赖；先使用 IoU、有限预测、轨迹生命周期，只有关联实验表明必要时才引入卡尔曼滤波。

## 0. 全局约束与已知基线

- 项目根目录：`/home/linao/heritage_workspace/heritage_temi_robot`。以下代码路径均相对项目根目录，运行命令均在该目录执行。
- 计划编写日期：2026-11-22；实查分支 `main`，HEAD `bdf67d6dd1e09c503845af11e23a7f2f26b1a508`，提交说明 `Add complete visitor tour simulation demo`。执行时重新检查，不将本快照当成未来最新版本。
- 已有未提交 `visualization/ros_hall/scene.js` 地面高度调整，以及持续变化的阶段 2.7 日志。先记录 diff 与哈希；不 reset、不清理、不覆盖，不把它们当作阶段 2.8 成果。
- 旧完整三人演示为 504.840 s、7/7 目标、六次确认恢复、PASS_WITH_RISK；实际最小人机中心距约 1.270 m。来源为 `docs/phase2_7/experiments/visitor-full-20261122-202055/`，不是视觉团队跟踪证明。
- 487 项全量测试发生于游客扩展前；扩展后 97 项为定向测试。不得相加或声称扩展后全量已通过。
- 不重建项目，不新增重复大网页；不为了展示改写历史实验结论；无实体 temi，禁止实体运动。
- 不 sudo，不改全局配置，不杀非本次拥有的进程，不关闭 Nav2 安全机制。Gazebo 串行执行，域/端口占用时选择空闲资源而非停止他人服务。
- 不自动 Git 提交、推送、历史重写、force push，不删除已提交大文件及失败轮次。读写权限不足时走具体文件的授权机制，不迁回旧项目目录。
- 不伪造图像、检测框、odom、真值、日志或 TTS 成功；Mock、模拟操作员、真值、视觉、回放都明确标注。
- 默认仅规划前向相机。后向覆盖不足必须返回 UNKNOWN/OUT_OF_VIEW；后置相机仅写未来硬件方案。

## 1. 执行顺序与验收门

| 顺序 | 工作包 | 依赖及可单独验收结果 |
|---|---|---|
| 0 | 审计、证据目录与最小日志约束 | 先固定源代码/配置/既有改动，实验开始就记录来源和采样规则 |
| 1 | 01 → 02 → 05 → 03 | 实际相机观测、来源隔离、停车竞态保护后才做 E07 视觉验证 |
| 2 | 04 | 与 01 独立分析历史集合；采用 05 的安全门做新全路线对照 |
| 3 | 08 → 06、07 → 09 | 速度标定前移；未达标档不能进入对应速度的停车结论 |
| 4 | 10、11、12 | 定向测试随开发执行；最终全量在核心和展示代码稳定后收口 |
| 5 | 13 → 14 → 15 | 面板只显示已有真数据；回放与控制路径隔离；素材引用真实运行 |
| 6 | 16 → 17 → 18 → 最终回归 | 日志策略起步即采用，归档/文档/硬件准备在收口时完成 |

门 G1：视觉模式无真值控制依赖且盲区不被当作掉队；G2：并发停车、停止确认、取消优先与 UUID 测试通过；G3：对应速度档实际标定通过；G4：回放无运动控制能力；G5：最新全量测试、七包构建和证据索引完整。门失败时保存失败并继续无依赖工作，不绕过安全门。

## 2. 文件与接口设计

### 2.1 最小文件职责

| 新增/修改路径 | 职责 |
|---|---|
| `ros2_ws/src/visitor_perception/visitor_perception/person_tracker.py`（新） | 纯算法：匿名关联、预测、过期与 ID 生命周期；无 Gazebo 导入 |
| 同目录 `team_observer.py`（新） | 纯算法：视域/观测有效性、期望人数、团队不确定性与确认请求 |
| 同目录 `ros_team_observer.py`（新） | ROS 适配：订阅现有 PersonDetectionArray、相机有效性与操作员确认，发布带来源的观测 |
| `ros2_ws/src/visitor_perception/setup.py`、`launch/sensor_fusion.launch.py`、`config/team_observer.yaml`（新配置） | 注册 observer 节点及集中阈值；保留原检测与融合节点 |
| 同目录 `ros_person_detector.py`、`ros_depth_association.py`、`ros_perception_fusion.py` | 核验并必要时修复时间、坐标、有效性；增加真实诊断指标 |
| `ros2_ws/src/heritage_tour_manager/heritage_tour_manager/{tour_manager.py,ros_tour_node.py}` | 业务/视觉模式选择，保守确认与恢复门控 |
| `ros2_ws/src/temi_bridge/temi_bridge/{ros_gateway.py,nav2_backend.py,nav2_transport.py}` | 审查并修复 STOP、取消、调速和导航会话事务 |
| `ros2_ws/src/temi_speed_controller/temi_speed_controller/{speed_policy.py,speed_controller_node.py}` | 原因、新鲜度、实际停车与恢复资格；不削弱安全策略 |
| `scripts/{gazebo_visitor_team.py,visitor_trail.py,run_visitor_full_demo.py,start_phase25_system.sh}` | 模式隔离、跟随效率、场景触发和启动配置 |
| `scripts/{run_phase28_experiment.py,analyze_phase28_experiment.py}`（新） | 薄层复用阶段 2.7 运行与分析，扩展本阶段场景；不复制整套进程管理 |
| `config/phase28_experiments.yaml`（新） | 场景、种子、相机、速度档、超时、指标及验收阈值 |
| `scripts/{collect_phase28_metrics.py,archive_experiment.py}`（新） | 性能窗口与不可变归档；两者各自单一职责 |
| `scripts/visualization_bridge.py`、`visualization/ros_hall/{ros-live.js,index.html}` | 真数据面板、来源与新鲜度、模式门控 |
| `visualization/ros_hall/replay.js`、`scripts/export_phase28_replay.py`（新） | 可追溯回放数据与播放器，不创建任何机器人客户端 |
| `tests/test_phase28_*.py`（按工作包新增） | 关键算法、安全、来源隔离、评估与回放拒绝控制测试 |
| `docs/phase2_8/`、`.gitignore` | 证据、报告、状态、归档说明；不忽略必要摘要 |

### 2.2 观测与团队接口（编码前用契约测试固定）

复用现有输入 `heritage/visitor/person_detections`，类型为 `temi_interfaces/PersonDetectionArray`；其 raw 输入为 `heritage/visitor/person_detections/raw`。当前 PersonDetection 没有 Track ID 或三维位置，不修改已有消息 ABI，新增 observer 输出先沿用项目 `std_msgs/String` JSON 约定，集中 schema 校验，禁止 NaN/Infinity。

```python
# person_tracker.py 的计划公开接口；具体记录使用 frozen dataclass。
def update(self, detections, stamp_ns: int, frame_id: str) -> list:
    # detections 是本帧边界框/置信度/可选深度及位置；返回匿名 Track 列表。
    ...

# team_observer.py 的计划公开接口。
def observe(self, tracks: list, stamp_ns: int, sensor_valid: bool,
            coverage: str, expected_count: int) -> dict:
    ...
```

两处 `...` 为签名说明，不是已交付实现。每条 Track 至少含 `track_id`、归一化 `bbox`、`confidence`、`observation_state`、`last_seen_stamp_ns`、`distance_valid`、可空 `distance_m`、可空 `position_xyz_m`、`frame_id`、`source`。距离无效时不填 0 作为真实距离；只有有效内参与深度可反投影 `X=(u-cx)*Z/fx, Y=(v-cy)*Z/fy`，TF 成功且新鲜才输出目标坐标系位置。无 TF 可保留光学坐标系位置并注明。

输出 `heritage/visitor/tracks` 与 `heritage/visitor/team_observation`；团队 JSON v1 至少含：`schema_version`、`stamp_ns`、`received_monotonic_ns`（记录端）、`frame_id`、`source`、`valid`、`sample_age_sec`、`coverage`、`observation_state`、`observed_count`、`expected_count`、`track_ids`、`requires_manual_confirmation`、`reason`。source 限 `camera_observation/vision_tracker/simulation_script/manual_operator/unknown`。

控制模式参数 `team_decision_mode` 仅取 `business_script` 或 `vision_conservative`；默认保持旧业务兼容，视觉启动脚本必须显式选择后者。另设显示模式 `LIVE_ROS2/RECORDED_ROS2/DEMO_SIMULATED`，显示模式与控制模式互不替代。

### 2.3 状态与时钟的保守约定

- OBSERVED：当前有效检测关联；OCCLUDED：只有独立遮挡证据才能标记，不能因丢框直接断言遮挡。
- TEMPORARILY_LOST：原可见 Track 在短暂丢帧期限内，无充分离开视域证据。
- OUT_OF_VIEW：投影/边界退出或已知相机覆盖几何支持；UNKNOWN：无充分证据、后方队伍人数不可确认、TF/内参不足。
- STALE：超过观测期限；数据不新鲜优先于旧 OBSERVED。深度失效允许框/Track 存在，但禁止距离决策。
- 上述状态不是游客真实身份和掉队标签。只允许提出“观测减少/需要确认”；没有足够覆盖时保守等候或在固定安全点确认，不自动断言已离队，不自动旋转寻人。
- ROS 仿真时间用于跨节点配对/场景指标；单调墙钟用于进程超时和服务响应。回放不沿用当前 ROS 时钟重判历史样本。时钟回拨清理预测状态，重新建轨且记录 epoch，避免复用旧 ID。

## 3. 审计与证据基础任务 T00

**文件：**新建 `docs/phase2_8/{progress.md,blockers.md,validation_matrix.md,audit/baseline.md}`；保存原任务为 `docs/phase2_8/source_task.md`，注明其执行命令不覆盖本次仅写计划的请求。

- [x] 执行 `git status --short`、`git branch --show-current`、`git log -5 --oneline`；记录完整状态及已有 diff 哈希，保护 scene.js 和旧日志。快照见 `audit/`；原工作区有484项状态记录且未清理。
- [x] 阅读任务指定的七份状态文档及第 2 节对应代码；把本计划的路径、话题、字段与实际代码差异写入 baseline，先修订计划再执行相关项。差异见 `audit/baseline.md`。
- [x] 检查内存、模型文件、venv、Humble、已安装消息、Gazebo、域和端口；仅扫描进程与占用，不终止旧系统。域仅在 0–232 内选择，避开运行器保留域 211/219/225；曾用 229/230 等不代表现在空闲。资源、模型、工具链和端口扫描见 `audit/baseline.md`。
- [ ] 实验运行前创建唯一 run_id；manifest 记录 HEAD、dirty diff 哈希/归档、配置/模型哈希、种子、相机、依赖版本、域/端口、拥有的 PID/进程组、原始命令和时区。
- [ ] 每轮 `status.json` 与 `summary.json` 记录退出码、阶段、失败原因和有效子结论；失败立即落盘且禁止覆盖同目录。清理后验证本次域状态；不以其他系统节点仍存在判本次清理失败。

**验收：**审计无代码改动；manifest 能区分本阶段代码与 dirty 基线；所有实验目录由运行器唯一分配。新工作包初始 NOT_RUN，环境阻塞有原始输出才标 BLOCKED。

## 4. 第一批：视觉与安全核心

### WP01 真实视觉匿名跟踪

**文件：**第 2.1 节 perception 模块，新增 `tests/test_phase28_person_tracker.py`、`tests/test_phase28_team_observer.py`；文档 `vision/{person_tracking.md,team_observation.md,blind_spot_analysis.md,detection_metrics.csv}`。

- [ ] 审计 YOLOX 实际图片/模型来源、bbox 坐标、置信度、FPS/处理延迟；检查现有深度配对阈值 0.15 s、深度过期 0.5 s 的语义、RGB/Depth CameraInfo 和 frame 一致性。阈值先保持基线，不通过增大期限掩盖延迟。
- [x] 用三条轨迹、交叉框、空帧、短丢失、长过期、时钟回拨、NaN 深度和错位内参写确定性测试；测试可用合成框，实验指标只能用实际图像。算法/契约定向测试已记录；真实图像指标仍独立处理。
- [x] 实现一对一 IoU 与有限预测关联、短时丢失/过期；ID 单调分配并带会话 epoch，不保证跨遮挡身份一致，不依据 Gazebo ID 关联。相关单测通过。
- [x] ROS 适配发布匿名 tracks/team_observation schema；异常/过期输入降级，节点已注册至 sensor_fusion，原 raw→depth→fusion 路径保留。七包构建及ROS发布测试通过。
- [x] 保存真实 Gazebo RGB/RGB-D 有人样本并人工标注代表帧；WP01-GAZEBO-CAMERA-04 保存12张RGB、5张depth，1帧3人框评估 P/R=1.0、人数误差0、均值IoU=0.923。深度误差、ID switch、推理FPS明确 NOT_COMPUTABLE；只证明静态单帧检测，不代表总体准确率或动态团队能力。

**定向验证：**`.venv/bin/python -m pytest -q tests/test_phase28_person_tracker.py tests/test_phase28_team_observer.py tests/test_ros_person_detector.py tests/test_ros_depth_association.py`。
**验收：**状态、空值、新鲜度、坐标和来源通过契约测试；实际检测与跟踪效果单独判定。前向图像缺少后队观测不得判完整视觉跟随通过。

### WP02 团队来源隔离

**文件：**`scripts/gazebo_visitor_team.py`、启动脚本、Tour Manager 两文件；测试 `tests/test_phase28_team_sources.py`。

- [x] 视觉模式忽略 `simulation_script` 团队消息且拒绝脚本直接掉队服务；ROS来源测试通过。业务模式保留原订阅和服务行为。
- [x] 增加 `--team-decision-mode business_script|vision_conservative` 明确控制脚本 lost client；视觉模式仅保留人物运动/仿真真值展示，不订阅脚本团队控制状态。来源回归通过；整路线隔离仍未运行。
- [x] observer 的不确定/覆盖不足进入明确原因的安全等待；继续服务作为操作员确认，并仅覆盖当前展区，下一站重新确认。Tour Manager与ROS集成回归通过。
- [ ] 视觉模式恢复以显式 manual_operator 确认为必要条件，并同时满足 WP05 的停止/安全资格；模拟操作员允许用于自动化，但每次事件必须标识。
- [ ] 尚未运行Gazebo图像真值分离的整系统场景；observer局部发布与脚本来源屏蔽已有ROS测试。

**验收：**从相机到业务的依赖图不包含 Gazebo 真值；`business_script` 与 `vision_conservative` 日志、启动参数及输出可区别，模式切换只允许空闲时。

### WP05 并发 STOP/恢复专项（在运行 WP03 前完成）

**文件：**既有 gateway/backend/transport、Tour Manager、速度策略及 `tests/test_ros_gateway.py`、`tests/test_phase27_recovery.py`，新增 `tests/test_phase28_control_races.py`。

- [x] 固定十二个重现用例：安全STOP+掉队、人工暂停+自动STOP、取消+恢复、重复暂停、旧取消未确认+新导航、重复恢复、未停稳恢复、过期停止确认、恢复时传感器失效、恢复时目标更换、旧调速晚到、多次集合恢复同一展区。各项测试映射见 `experiments/WP05-CONTROL-RACES.md`。
- [x] 用可控 Future/事件屏障模拟乱序，不以 sleep 碰运气；断言人工取消优先、严重故障不自复、重复请求不产生第二导航事务、旧 UUID/调速回调无副作用。WP05 定向回归109 passed。
- [x] 保留并发 STOP 合并确认机制，失败不写成功；Action cancel ACK 不代表实停。停止证据必须含新鲜 odom、连续稳定窗口、有效旧会话关联；参数读取和旧事务收尾必须完成才建立新运动会话。软件测试覆盖通过；Gazebo实停仍未验收。
- [ ] 网页/服务的重复恢复返回明确状态；恢复中再失效立即取消恢复资格并停车。保留正确展区指针，不跳区。
- [ ] Gazebo 低速独立复现两个并发停车源、停稳前恢复拒绝、人工取消与恢复争用；保存请求/ACK/odom/旧新UUID完整时序。

**验证：**`.venv/bin/python -m pytest -q tests/test_ros_gateway.py tests/test_nav2_backend.py tests/test_nav2_arrival_stop.py tests/test_phase27_recovery.py tests/test_phase28_control_races.py`。
**验收：**十二个边界行为有断言；集成证据证明实际停稳和会话隔离，无法完成的场景不得由单测代判 PASS。

### WP03 E07 双模式验证

**文件：**本阶段运行器/配置/分析器、`tests/test_phase28_team_experiment.py`；证据 `experiments/E07/`。

- [ ] E07-A 用真实三人模型跑入口→五区→出口；脚本掉队与模拟操作员明确标注，检查实停、等待、集合确认、同目标新 UUID。
- [ ] E07-B 在机器人静止的安全观察点依次安排三人进入视场→稳定建轨→短遮挡→一人出视场→不确定→重新观测三人→人工确认；人物运动不向算法提供真值。
- [ ] 用原始图像/检测/跟踪/TF/业务事件评估，不要求保持跨遮挡 ID；不可见不输出“确定离队”。重新看见三个匿名人也不自动声称原三人归队。
- [ ] 观察点需要朝向调整时先独立验证原地转动安全；未验证则使用固定朝向的独立视觉场景，不加正常导航中的主动危险转向。
- [ ] 单独输出 A、B 与整路线后向覆盖结论；后者无覆盖证据为 NOT_VERIFIED（子能力字段），映射最终状态为 NOT_RUN 或 PASS_WITH_RISK 并解释。

**验收：**A 的完成不能替代 B；B 必须有实际相机检测和保守状态变化。检测不成功时标 FAIL/BLOCKED 并保存样本，不伪造闭环。

### WP04 三人跟随/集合优化

**文件：**`visitor_trail.py`、`gazebo_visitor_team.py`、完整演示运行器及 `tests/test_visitor_trail.py`；`team/{following_optimization.md,regroup_analysis.md,team_experiments/}`。

- [ ] 离线分析 20261122-202055 的每次暂停到确认及恢复阶段，分别计算人物追赶、寻路、等待人工确认时间，定位约 147 s 的长集合，记录未采集字段不可推断。
- [ ] 固定可重复种子、路线、速度与间距保护；采集优化前新代码基线。历史 504.840 s 作为参考，不能当作相同条件的唯一 A/B 对照。
- [ ] 对证据指出的瓶颈逐项最小修改：弧长采样/转角目标、缓存路径与重规划频率、队间让行、队尾恢复、集合去抖；禁止瞬移、取消距离保护或无限提速。
- [ ] 每改一类行为补转角/死锁/最小间距测试，然后同配置完整跑一次，保留所有失败轮。若需机器人适配队列速度，只走既有动态速度限幅路径，不另发底盘指令。
- [ ] 对照总耗时、导航耗时、集合次数/每次耗时/最大耗时、各人里程、最小人机/人人距离、重规划/绕行次数、异常、完成状态和人工延迟。

**验收：**先以最大集合耗时较同条件基线减少 ≥30% 为优化目标，总耗时不增加且原有距离保护不削弱；未达到如实标 FAIL/无改善，不能降低门槛重标。实际最小距离单列，目标余量不说成全程保证。

## 5. 第二批：动态人流与实际速度

### WP08 独立速度标定（先于动态矩阵）

**文件：**本阶段配置/运行器/分析器，必要时小改 `simulation/navigation.launch.py`、Nav2 transport；`tests/test_phase28_speed_calibration.py`。

- [ ] 比对旧窗口相对于导航受理、起动、转弯、停车、目标到达和限速事件的时序，核实 ROS/墙钟混用及 odom 年龄。
- [ ] 在官方地图选择长度足够、无障碍的直线，确认净空和停止缓冲；若地图不足以达到稳态，该档 NOT_RUN/BLOCKED，不强行直发 cmd_vel 绕过 Nav2。
- [ ] 分别请求 0.3/0.5/0.7 m/s，回读 controller、smoother 与有效速度限制；真实 Nav2 导航开始且新鲜 odom 连续运动后采样。每档独立 run。
- [ ] 预先固定稳定窗 ≥2.0 s、有效 odom ≥20 帧、最大间隙 ≤0.2 s、角速度绝对值 ≤0.05 rad/s、中位速度误差 ≤0.05 m/s；不满足为该档 FAIL，记录实际可达速度。
- [ ] 输出请求/回读上限、cmd_vel、odom、中位速度、误差、稳定窗口、样本数、暂停/限速原因；分析器测试覆盖启动前零速和混合时间戳拒绝。

**验收：**只有标定成功档可计入相应已验证动态工况；仿真速度不作为 temi 许可速度。超时失败保留，禁止不断延长直到碰巧达标。

### WP06 E02 人数增减与限速贡献

**文件：**本阶段场景配置/运行器/分析器、现有 `spawn_people_scenario.py`，`tests/test_phase28_crowd_analysis.py`；`experiments/E02/`。

- [ ] 按相同起点、路线、导航参数与种子设计无人/1/3/5 人、渐增、渐离六场景；先用标定成功低速档，人物与路线不制造不可避的重叠。
- [ ] 真值人数、检测人数、最近视觉距离、density_valid、目标速度、Nav2限速回读、cmd_vel、odom 分栏记录。无区域面积和标定时 density_valid=false，不由人数生成假密度。
- [ ] 无人和有人对照在相同路径弧长区间评估，排除转弯/停车窗口；若 Nav2 自身已低于限速，标“物理贡献不可确认”，不硬说减速成功。
- [ ] 保存 YOLOX 实际帧、深度有效性、Scan 与融合理由，分别判检测、策略、参数执行、实际速度变化四个子目标。

**验收：**六场景独立结果，人数/密度不混淆；上限变化只证明策略，真实减速需要相同时空条件下 odom 支持。

### WP07 E04 三类横穿

**文件：**本阶段场景/分析器、`tests/test_phase28_crossing_analysis.py`；`experiments/E04/{A,B,C}/`。

- [ ] 配置 A 前向相机有效横穿、B 相机外激光范围内横穿、C 双源范围横穿；所有安全传感器保持开启，不能为“视觉主导”关闭激光。
- [ ] 实跑确认各场景实际覆盖成立；A 若控制主要由激光触发，则如实记触发来源，不能仅凭预设名称称视觉主导通过。
- [ ] B 中 Scan 只报告障碍，禁止输出人员身份；C 对齐首个有效检测、视觉距离、Scan、限速/STOP、odom停稳、离开和恢复时刻。
- [ ] 每类独立保存最小距离、触发原因、实际速度及新会话恢复；分析器用缺视觉/缺激光/延迟样本测试拒绝不成立结论。

**验收：**A/B/C 分别判定感知覆盖、决策来源和控制结果，不合并为一个模糊 PASS。

### WP09 E03/E05/E06 多工况停车与恢复

**文件：**本阶段运行器/分析器及 `tests/test_phase28_stopping_analysis.py`；`experiments/{E03,E05,E06}/`。

- [ ] 在标定通过档上配置缓慢/快速靠近、横穿、持续靠近静止机器人、离开、突然停止、短暂视觉消失、深度失效八工况；低风险低速先行，逐档扩展，明确每档是否执行。
- [ ] 人物轨迹独立于机器人 STOP；先做预测几何风险检查，危险时受控中止并记录 FAIL。不能冻结人物制造安全余量；若保护动作使工况提前结束，保留并注明。
- [ ] 计算首次有效刺激→策略响应→命令变化→新鲜odom停稳时间，积分 odom 减速路程；按接近/制动/持留/离开/恢复分段计算中心距和几何间隙。
- [ ] 分清人员距离、Scan、深度失效与数据陈旧触发原因；E06 必须有人工/安全资格、旧新 UUID 和同目标，不以 ACK 代实停。
- [ ] 缺接触反馈保留 `contact_observed=null`；采样间最小值不是连续时间安全证明，记录采样频率与漏测风险。

**验收：**每档×每工况有 PASS/FAIL/NOT_RUN 明细，未达标速度不进已验证统计；风险中止不叫工况通过。

## 6. 第三批：可靠性与性能

### WP10 最新完整回归

**文件：**新增相关 tests、`docs/phase2_8/tests/{ros2_build.log,full_suite.log,test_summary.json}`；WebSocket 专项日志。

- [x] 核实项目 `.venv`、ROS Humble、Python 3.10.12、OpenCV 4.11.0、本地 ONNX 模型与源码哈希；最终选择 Domain 231，执行前/后均为空。依赖与初始 dirty 基线见 `audit/baseline.md`，最终测试摘要见 `tests/test_summary.json`。
- [x] 最后源码变更后执行七包构建，7/7成功、退出码0；日志 `tests/ros2_build_final.log`。
- [x] source 最新 install 后完整执行 `tests`，无 ignore/排除，550 passed、0 failed/skip/error；ROS Domain 231 前后空图。域234不兼容、域228用户活动图发现及230命令行守护节点预检均有记录，最终结果见 `tests/full_suite_final.log` 与前后域 JSON。
- [x] `tests/test_summary.json` 统计550 collected/passed、0 failed/skip/error、196.49 s、退出0、完整命令；WebSocket+gateway两文件专项2 passed/2.37 s，JS语法、运行、真实回放文件完整性检查退出0。

执行时使用的原生命令（由记录器捕获 stdout/stderr/退出码；避免管道掩盖失败）：

```bash
cd /home/linao/heritage_workspace/heritage_temi_robot-phase28
source /opt/ros/humble/setup.bash
bash scripts/build_ros2.sh
source ros2_ws/install/setup.bash
# PHASE28_TEST_DOMAIN 需先在 0–232 内预检，并确认运行前后空图。
export ROS_DOMAIN_ID="$PHASE28_TEST_DOMAIN" ROS_LOCALHOST_ONLY=1
HERITAGE_TEST_ROS_DOMAIN_ID="$PHASE28_TEST_DOMAIN" .venv/bin/python -m pytest -q tests
HERITAGE_TEST_ROS_DOMAIN_ID="$PHASE28_TEST_DOMAIN" .venv/bin/python -m pytest -q tests/test_gateway_websocket_integration.py tests/test_gateway_cli.py
```

**验收：**七包构建退出 0，最终全量无 FAIL/error；SKIP 不能当 PASS，存在则整体保留风险和原因。测试数量以实际收集为准。

### WP11 七类完整三人稳定性

**文件：**本阶段运行器/配置、`team/team_experiments/`、`stability/repeated_tours.csv`。

- [ ] 分配七个独立场景：正常三人、无掉队、一人掉队、短遮挡、中途问答、人工暂停、导航异常。为正常与无掉队明确区别：前者允许自然保守确认，后者不注入掉队并记录是否意外暂停。
- [ ] 优先前三类，资源允许完成全部；配置明确 A 业务或 B 视觉模式。导航异常使用本次拥有的节点/可控目标拒绝注入，不伤及旧系统。
- [ ] 每轮记录完成/预期目标数、耗时、人员里程、停车/集合/恢复次数、最小几何距离、死锁、重复导航、人工介入与失败原因；导航异常可验收安全处理，但不能把未完成路线标为完成。
- [ ] 统计全部尝试及各场景结果，准备失败也保留；七类各一次只证明场景覆盖，不宣称统计可靠性。

**验收：**每轮独立唯一目录且原始失败入分母；至少前三项实跑，未跑其余明确 NOT_RUN，阶段总体仍注明不足。

### WP12 性能窗口与局部优化

**文件：**`collect_phase28_metrics.py`、`tests/test_phase28_metrics.py`；`performance/{latency_report.md,resource_metrics.csv,before_after_comparison.md}`。

- [ ] 在同一三人场景预热 10 s 后连续采样 ≥60 s；记录机器、模型、种子、渲染模式、Gazebo实时因子与 CPU/内存，不能拿不同环境比较。
- [ ] 记录 YOLOX推理FPS及P50/P95、RGB-D关联/融合延迟、控制周期/参数事务延迟、日志吞吐、页面更新帧率与丢帧、人物路径计算和服务等待耗时；墙钟处理耗时与仿真时延分栏。
- [ ] 检查每帧 A*、缓存增长、Gazebo同步调用、JSON重复输出；先数据定位，再只优化首要瓶颈，保持碰撞/停止证据采样需求。
- [ ] 同条件复测 ≥60 s，输出样本数、缺失比例和前后差值；P95 不够样本或窗口无效时不发布改善百分比。

**验收：**测量覆盖规定窗口，优化有可比数据；未改善可交付诚实结论，不能以“已加缓存”替代实测。

## 7. 第四批：国赛展示与回放

### WP13 真数据技术面板

**文件：**`visualization_bridge.py`、`ros-live.js`、`index.html`、必要样式；`tests/test_visualization_bridge.py`、新增 `tests/test_phase28_visualization_api.py`。

- [x] 复用 ROS 订阅快照，加入检测框/匿名ID/视觉人数/距离/观测状态、CameraInfo/Camera TF/深度有效像素比例、Scan最近障碍和数据年龄。深度/TF新增定向测试通过；实际刷新页截图未重新归档。
- [x] 并列显示 target_speed、Nav2独立回读状态、cmd_vel、odom速度、动态停车阈值、原因和安全会话UUID；缺数据显式无效。当前 Nav2 SetNavigationSpeed 接口没有独立回读，面板明确标明接口缺失。
- [x] 团队面板并列视觉与真值/脚本来源、判断模式、人工确认需求，缺少真值时明确显示陈旧；真实页面观察已核验这些结构化字段。
- [ ] 技术事件时间线按真实事件排序，重复/乱序有事件ID，不把未发生步骤提前画成成功。
- [x] 视频无法接入时只展示真实结构化结果，不把检测框叠到无关画面；Mock播报、模拟操作员和实机未验证有明确说明。
- [ ] 检查并尊重现有 scene.js 地面闪烁修复；在目标浏览器旋转/俯视、断源和重连下观察 ≥60 s，保存带 run_id 的真实截图/录屏。语法通过不能替代画面验收。

**验收：**来源/陈旧/缺测可辨，网页 API 边界与控制权限测试通过，断流不保留“实时有效”标志。

### WP14 三种模式与真实实验回放

**文件：**`export_phase28_replay.py`、`replay.js`、bridge/API门控；`tests/test_phase28_replay.py`，网页现有 `test-runtime.cjs` 按现有方式扩展。

- [x] 导出只接受manifest与tar/源文件哈希一致的真实记录；包含run_id、源文件SHA256、ROS时间/已采集monotonic映射、事件与RGB帧。此真实run没有wall-clock映射、机器人/游客世界坐标或速度采样，字段标记not collected并留空，未补造数据。
- [x] 主页面明确显示 `LIVE_ROS2` 或 `DEMO_SIMULATED`，独立离线播放器在校验后显示 `RECORDED_ROS2`、原始实验ID与来源；回放读取本地JSON，不连接实时API。
- [x] 实现本地时间轴、播放/暂停、0.5/1/2倍速与事件定位；Node单测覆盖时间戳对应帧选择与事件跳转。
- [ ] 轨迹与速度曲线需新增真实世界坐标/速度源数据后实现；当前样本未采集，保持空数据，不插值或虚构。
- [x] 离线回放是独立静态页面，不建立HTTP/ROS控制客户端；Node测试检查无fetch/XHR/API入口，播放/暂停/seek仅改变本地游标。不存在回放后端控制会话。
- [x] ROS实时运行与离线回放使用独立入口；导出/播放器拒绝无效manifest、归档/图片SHA及路径越界，未能校验时不显示 `RECORDED_ROS2`。

**验收：**G4 的来源校验与控制隔离已通过；播放器具备可离线打开的入口，但本轮浏览器策略拒绝 `file://` 预览，因此尚未完成画面验收。seek/倍速/暂停不改变原始事件，不发任何运动/恢复/问答控制请求。

### WP15 完整与精华演示素材

**文件：**沿用 `start_full_visitor_demo.sh`，按需新建 `scripts/start_phase28_demo.sh`；`competition/{demo_guide.md,short_demo_storyboard.md,visualization_guide.md,evidence_index.md}`。

- [ ] 保留完整入口→五区→问答→出口流程；启动脚本预检依赖/域/端口/模式，失败可定位日志，只关闭本次进程。
- [ ] 按实际证据制作2–3分钟精华：识别/同意/跟随/掉队或观测不确定/实停/人工确认/恢复/问答/出口；每段标原始run_id和原始时间区间。
- [ ] 剪辑或倍速用 RECORDED_ROS2 与倍速标签，不声称2分钟实时跑完。相机实际未识别时不得剪出“识别成功”字幕。
- [ ] 可录屏则交付真实完整/精华文件和哈希；不可录屏则交付可复现入口、操作说明、真实记录、曲线、实际截图与分镜，说明缺失媒体。

**验收：**素材时间线与原事件一致；浏览器模拟语音和 Mock Speak 的区别清楚；来源索引不依赖机器临时目录。

## 8. 第五批：工程交付

### WP16 大型日志与可追溯归档

**文件：**`.gitignore`、`archive_experiment.py`、`tests/test_phase28_archive.py`、`docs/phase2_8/archive_policy.md`。

- [ ] 先统计 tracked/untracked大文件、重复字段与频率。历史原文件保持原样，尤其已提交66MB记录；本轮不历史重写，不擅自 git rm。
- [x] 新实验高频原始数据放 `artifacts/phase2_8/` 并忽略；Git保留配置、run manifest、summary、SHA256索引、小型结果和必要测试报告。测试输出/打包前扫描凭据，不公开私有运行环境秘密。本阶段 raw 与 archive 路径已加入 `.gitignore`。
- [ ] 显示状态采样与安全证据采样分离：普通重复状态建议2Hz+事件触发，odom/STOP/UUID/感知原始时序按测量所需保存；任何降采样不改变原算法订阅频率，不凭降采样数据作更细时间分辨率结论。
- [x] 归档脚本只读已结束run，生成原文件/归档SHA256、相对路径、大小和恢复说明，不删除原始文件。WP01-GAZEBO-CAMERA-04归档30个文件，464,450 bytes；逐文件哈希复核见 `experiments/WP01-GAZEBO-CAMERA-04/archive_integrity.json`，原文件保留。
- [x] 测试字节一致、重复归档不覆盖、进行中run拒绝、失败轮保留、路径越界拒绝；验证 `.gitignore` 仅作用新原始数据，不吞摘要和源码。新增归档定向测试4 passed。

**验收：**新实验不再大量入Git；历史证据可追溯，压缩不是删除；归档路径和恢复步骤能在新机器按索引找到数据。

### WP17 状态与历史报告整理

**文件：**`docs/PROJECT_STATUS.md`、`docs/next_phase_plan.md`、阶段2.8所有总结文档，阶段2.7报告仅追加明确日期更正说明。

- [x] 最新状态写实际HEAD与tracked dirty补丁哈希；说明阶段2.8没有完整三人路线、静态视觉与脚本真值的差异、Mock与实体TTS差异及最终回归范围，见 `final_report.md` 与根目录项目状态。
- [x] 保留阶段2.7/旧报告历史快照，在 `docs/PROJECT_STATUS.md` 与 `docs/next_phase_plan.md` 增加阶段2.8最新入口；不改写旧487项记录。
- [x] 核对WP01四次视觉尝试、失败轮、归档30文件路径/哈希、WP13截图未存档限制与NOT_RUN项；未虚构提交SHA，见 `validation_matrix.md`、`blockers.md` 与 `final_report.md`。
- [x] 更新 `code_changes.md`、`progress.md`、`blockers.md` 与验证矩阵，逐项链接代码/测试/实验，保留未完成范围。

**验收：**项目入口状态与本轮报告一致，历史结论未被改写，未验证能力不会在宣传中变成“完成”。

### WP18 实体 temi 接入准备

**文件：**只读审查 Android 的 `BridgeCoordinator.kt`、`SdkTemiDriver.kt`、`BridgeProtocol.kt`、`WebSocketBridgeClient.kt`、`TemiSpeedManager.kt` 与 ROS gateway/websocket；写 `real_temi_integration_checklist.md`。

- [x] 逐接口列复用范围和仿真替换：地点/地图、导航会话、SDK停止、速度反馈、ASR/TTS、外部相机/深度/Scan、人员跟踪、断线保护。清单逐项记录实机依赖与限制。
- [x] 以Android/ROS实际代码审查复用和硬件依赖；未假定SDK公开原始摄像头或可认证的物理实停。源码清单已写入 `real_temi_integration_checklist.md`。
- [x] 写出 Android↔ROS2 首次接入和逐级验收清单；设备网络、凭据、地图与停止值仍需实机确认。
- [x] 本轮未修改 Android，因此未执行 Android build/tests；实体 SDK/依赖/设备限制和静态代码审查结论列于 `real_temi_integration_checklist.md`，未称实机 PASS。

**验收：**需求列出的十类接入问题均有条目，制动标定/相机能力/安全验收为 HARDWARE_REQUIRED；本阶段无实体运动命令。

## 9. 统一实验/判定契约

每轮至少保存：`manifest.json`、冻结配置、`status.json`、`summary.json`、来源哈希、事件时序、分析结果；高频原始日志位于归档路径，docs 下索引引用。事件字段至少含 `run_id,event_id,stamp_ns,received_monotonic_ns,source,type,target_id,navigation_uuid,reason`；数值字段带单位与有效性。

| 状态 | 使用条件 |
|---|---|
| PASS | 该项预设条件成立、原始证据齐全且全部验收门满足 |
| PASS_WITH_RISK | 子目标有证据但范围/速度/覆盖/接触反馈等存在明确限制，不覆盖未验收能力 |
| FAIL | 运行完成或中止且触发失败条件；预测风险中止也保留原工况失败 |
| NOT_RUN | 未执行；包括未获合格前置速度档的后续工况 |
| BLOCKED | 有具体环境/依赖阻塞及实际失败证据，记录可继续的独立任务 |
| HARDWARE_REQUIRED | 缺实体设备的验证，仿真与Mock不能替代 |

E02–E07 的结果必须包含条件有效性、感知、决策、物理执行、恢复、路线完成六个子结论；某子目标成功不把整轮抬成PASS。视觉完整后队跟踪额外保留 `verification=NOT_VERIFIED` 与盲区说明。

重试采用新run_id，连续两次同原因失败先离线诊断，不无限重复；修复有定向验证后再复跑。超时、ROS服务ACK失败、原始数据缺失都保留退出与阶段，禁止覆盖失败目录。

## 10. 最终交付与自检

完整目录遵循原任务：`vision/`、`team/team_experiments/`、`experiments/E02`至`E07`、`tests/`、`performance/`、`competition/`、实机接入清单，以及 progress/code_changes/blockers/validation_matrix/final_report。增加 `audit/`、`stability/`、归档索引不改变原交付范围。未执行实验不创建伪结果文件。

- [x] WP01–18各有状态、证据入口和未验证限制，见 `validation_matrix.md`；未运行实验保持 NOT_RUN，硬件项保持 HARDWARE_REQUIRED。
- [x] 最后源码修改后完成七包构建、全目录543项回归、WebSocket专项与JS检查；源码此后未改，原始结果和最终文件哈希已留存。
- [x] `final_report.md`逐项列出HEAD/dirty、改动、新功能、完成/未完成、E02–E07、视觉/盲区/掉队、集合/耗时、停车恢复、测试/WebSocket、性能、可视化/媒体、日志、实机准备与遗留风险，并链接证据。
- [x] 最终报告分别标记业务脚本/视觉E07、全轮次分母、目标限速/odom实际速度、人工/模拟操作员、Mock/实体音频与Gazebo真值/传感器观测。
- [x] 审查代码diff仅涉及阶段2.8任务；隔离分支未修改主工作树的 `scene.js` 或旧日志；未提交、未推送。

**执行状态自检（2026-11-23）：**原任务18工作包逐项保留；已验证的步骤已勾选并附直接证据。WP03–04、WP06–09、WP11–12、WP15仍未运行或未完成；WP13缺少新字段浏览器复核、事件时间线和长时断源截图；WP14缺世界坐标/速度曲线和浏览器预览；WP18硬件验证仍需实体设备。阶段2.8整体未完成，详见 `validation_matrix.md` 与 `final_report.md`。
