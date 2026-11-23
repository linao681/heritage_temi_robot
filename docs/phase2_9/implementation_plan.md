# heritage_temi_robot 阶段 2.9 实施计划：全场景验收与国赛强化

> 原始计划于2026-11-23编写。阶段2.9执行已经开始；本文件复选框只表示该项是否取得计划要求的完整证据，不因代码写完或单测通过自动勾选。最新进度、实际结果和阻塞见 [`progress.md`](progress.md)、[`validation_matrix.md`](validation_matrix.md) 与 [`blockers.md`](blockers.md)。本轮由当前会话独立执行，不调用子代理；不自动提交、推送或合并。

**Goal：**在最新阶段2.8代码上取得可追溯完整导览、动态感知和安全恢复证据，并交付诚实、可演示的六分钟国赛材料。

**Architecture：**保留七个ROS包、Nav2与Android Bridge；脚本游客业务与真实相机视觉各自验收。复用现有运行器，补统一布局、只读参数观测和记录契约；同一份真实记录服务验收、面板与回放，不新建重复业务状态机。

**Tech Stack：**Ubuntu 22.04、ROS2 Humble、Gazebo Classic、Nav2、Python虚拟环境、YOLOX-S ONNX/RGB-D、现有匿名IoU跟踪、Three.js、Kotlin/temi SDK。

## 0. 实查基线及范围

计划编写于2026-11-23，Asia/Shanghai。实查工作区 `/home/linao/heritage_workspace/heritage_temi_robot-phase28`，分支 `phase2_8-work`，HEAD `24c14231de61840a11c5462805df0cd6160af84d`；编写前工作树干净，近8条提交已核对。执行时再次检查，以实际更新的代码为准，不默认main最新，不切换或覆盖主工作树。

**执行状态更新（2026-11-23）：**上述为计划基线；当前独立worktree分支为 `phase2_9-work`，当前HEAD仍是 `24c14231de61840a11c5462805df0cd6160af84d`。阶段2.9改动未提交。当前pytest已收集607项；在排除14个本地ROS/网络集成模块和1项会阻塞的ROS节点测试后，离线子集506项通过。该结果不代替完整测试或Gazebo验收。

**13:51 CST最新执行更新：**视觉暂停handler修复已纳入最新完整`tests/`回归，624 passed、190.10秒；Domain 226在测试前后为空。运行器真实视觉run `visitor-full-20261123-133255`仍为FAIL，未人工恢复或完成导览；用户要求退出的本会话测试进程当前已不在运行。细节见`audit/full-regression-20261123-1351.log`、`experiments/WP02-vision-observation/visitor-full-20261123-133255/evidence.md`和`verification-attempts.md`。

**12:11 CST复核：**服务接口变更后ROS2七包构建7/7；网关/速度控制器定向64项通过；最终完整测试在Domain 226、`HERITAGE_TEST_ROS_DOMAIN_ID=226`下619项全部通过，186.56秒。首轮未统一域回归、游客状态集成夹具诊断及处理记录见`audit/regression-20261123-1211.md`。Gazebo与实体场景仍需逐项按本计划验收，未以完整单测替代。

已读阶段2.8 final_report、validation_matrix、progress、blockers、code_changes与阶段2.7游客实现记录。550项通过、7包构建、2项WebSocket是历史基线，不是本阶段新结果。504.840秒/7目标是阶段2.7业务脚本历史记录。单帧3人P/R=1、47次UNKNOWN不能扩展为动态视觉团队能力。

发现的具体实现缺口：

1. `scripts/run_visitor_full_demo.py`默认域229，输出写入阶段2.7；入口只有域/端口/keep-open参数。其准备条件依赖脚本team.gathered，掉队条件依赖脚本状态，不能直接当作视觉模式运行器。
2. `scripts/start_phase25_system.sh`对hall、Nav2、gateway、网页多处写死official。已有 `PHASE28_TEAM_DECISION_MODE`，应复用，不再新增同义模式变量。
3. `scripts/start_full_visitor_demo.sh`默认传入keep-open，自动验收不能沿用此默认保留进程行为。
4. `temi_bridge/nav2_transport.py`已有controller/smoother GetParameters及设速后读回，可复用；独立只读采样尚未贯通面板和采集器。
5. `scripts/record_phase2_topics.py`已有cmd_vel/odom字段，应扩展而非重复记录系统；历史WP01回放缺坐标/速度，保持缺失。
6. 阶段2.8报告中的未提交/未推送是提交前快照。阶段2.9入口应明确当前24c1423已提交推送，历史文档只加版本注释，不重写实验结论。
7. 本次扫描未发现工作区PPT/PPTX源文件；执行时重新查找用户授权目录，找不到时只创建新的材料，不能声称改了已有PPT。

竞赛日期、6+4分钟、六项权重和扣分条款采用用户提供文本，标注“用户提供的赛务要求”；正式PDF制作前对照官方文件核验。不得凭此计划声称已经独立验证2026赛务信息。

## 1. 全局约束与验收门

- 禁止sudo、全局配置修改、实体temi运动、关闭Nav2保护、人物瞬移、冻结持续靠近人物来制造安全、伪造检测或缺失历史轨迹。
- 不终止他人/历史进程。即使名称相同，只能清理本run记录的PID/进程组；退出后再次检查所属域和端口。
- 所有重型Gazebo实验串行；没有空域、端口或足够资源则记录BLOCKED并转离线任务。域仅在0–232内选，避开运行器保留域，任何旧域都重新探测。
- 用户不在线时的游客同意、集合、监护确认均写 `simulated_operator`；真人确认与模拟确认在证据中分开。
- 视觉算法仅接图像/深度/标定/TF与显式操作员配置；Gazebo人物ID、lag_m、真值人数仅作评估/显示。未知覆盖保持UNKNOWN。
- 所有代码步骤先写有意义的行为/故障测试，复现失败，再最小修改；不要为了测试数量添加镜像实现测试。完成后自查差异，不自动提交。
- 原始失败不删、不覆盖；同原因连续两次失败后先离线诊断，不盲目重跑；超时失败不得不断延长掩盖。
- 初次完整业务验收采用现有保守限速，不扩大到未标定高档；0.5/0.7动态工况必须等待对应速度标定通过。

| 门 | 进入条件 | 不满足时 |
|---|---|---|
| G0 环境 | 空域/端口、依赖、磁盘、资源、所属进程记录齐全 | 不启动重仿真，转WP04离线分析、WP10–17 |
| G1 可追溯记录 | manifest/时钟/采集器预检成功，原始文件可落盘 | 保存准备失败，修采集器后新run |
| G2 安全控制 | 软件STOP/取消/旧UUID/陈旧odom回归通过 | 不运行运动故障注入，继续只读/静态工作 |
| G3 速度 | 对应速度档稳态窗口通过、参数实读 | 该档动态验收NOT_RUN，不能降门槛 |
| G4 视觉来源 | 注入脚本真值不影响视觉决策，盲区保守 | 阻断视觉控制闭环，仍可独立采样 |
| G5 展示 | 新字段来源/时间/失效可辨，回放无控制路径 | 不把页面当验收证据 |
| G6 收口 | 最后代码变更后新构建/全套/专项和证据索引 | 报告不能声称最终通过 |

## 2. 执行批次与资源分支

先完成T00、记录契约与最小运行器改造。资源可用时：WP01业务基线 → WP02/WP03独立视觉 → WP04同条件优化 → WP07标定 → WP05/WP06/WP08低速动态；WP09–12随依赖穿插，最后完整复跑与WP18。WP13/14采集基础应前置，避免跑完才发现缺轨迹和速度。

资源不允许时：完成WP04历史分析、WP09静态布局验证、WP10–12状态机测试、WP13/14代码和只读离线验证、WP15–17材料；将每个未跑场景独立标NOT_RUN/BLOCKED。不能因Gazebo受阻而停止所有工作，也不能用单测代替Gazebo结果。

建议单次上限：准备240秒、完整路线1200秒、独立视觉180秒、单档标定180秒、单个动态场景240秒、清理20秒。超时记录当前阶段、资源与日志；仅在明确定位后修改下一run配置。每个窗口用单调墙钟限制，不能用会暂停的仿真时钟控制进程超时。

## 3. T00：执行审计及证据基础

**文件：**新增 `docs/phase2_9/{audit/baseline.md,progress.md,validation_matrix.md,blockers.md}`、`config/phase29_experiments.yaml`；新增 `scripts/run_phase29_experiment.py`、`tests/test_phase29_experiment_runner.py`，复用 `scripts/run_phase27_experiment.py` 的预检/锁/拥有进程清理函数。

- [ ] 再执行git status/branch/log -8/diff --stat，保存完整HEAD、dirty patch及新增源码哈希；不要只哈希tracked diff而遗漏untracked实现。
- [ ] 记录date、ROS/Python/OpenCV/模型SHA、free -h、df、CPU与Gazebo/ROS进程及监听端口。先做进程只读检查，再在候选域运行项目空域探针；不靠ROS命令行缓存图判空。
- [ ] 资源策略：已有非本run Gazebo且资源不足就不再启动；本计划建议启动前至少6GiB MemAvailable、至少5GiB磁盘余量，无持续换页/高负载。此为执行资源门槛，可因测量提高，不用于降低实验成功标准。
- [ ] 为每轮创建 `docs/phase2_9/experiments/<experiment_id>/<unique_run_id>/`，使用exist_ok=False；raw写 `artifacts/phase2_9/raw/<run_id>/`，归档写同阶段archive，摘要/哈希进Git。
- [ ] 运行器先校验配置，再预检域/端口/资源，再启动；finally只清理所属进程组，记录清理后域和端口。SIGINT/超时/启动失败都写status/summary。
- [ ] 用进程替身测试：忙域不启动、端口冲突不启动、无效模式/布局拒绝、输出目录不得覆盖、子进程超时必清理、失败保留。通过后才接Gazebo。

每轮manifest至少记录：run_id、实验ID、HEAD、dirty源码归档SHA、配置/模型/地图/目标点SHA、seed、布局、控制模式、游客类型、相机配置、原始命令、域/端口、起止UTC与本地时区、依赖、拥有PID/PGID、状态、采样策略。status/summary记录退出码、失败阶段、六个子结论（条件/感知/决策/实执行/恢复/路线）及原始文件索引。

### 3.1 统一记录契约（在首次新实验前完成）

**修改：**`scripts/record_phase2_topics.py`；新增 `scripts/analyze_phase29_experiment.py`、`tests/test_phase29_recording.py`。记录采用JSONL，以事件和采样分别保存，原始消息及来源文件保持可追溯。

```python
# 计划新增的纯分析接口，禁止调用ROS控制服务。
def analyze_speed_window(samples: list[dict], target_mps: float) -> dict: ...
def analyze_recovery(events: list[dict], odom: list[dict]) -> dict: ...
```

以上为接口签名，实际实现必须有拒绝缺失/错时钟/陈旧样本测试。记录共同信封：`schema_version, run_id, event_id, source, ros_stamp_ns, received_monotonic_ns, received_wall_utc, frame_id, valid, reason, data`。缺字段用null和缺失原因，不能用0代未知。

数据包含：map坐标机器人pose（新鲜TF）、Gazebo游客pose真值（单列）、原始cmd_vel与odom、tour_state、navigation_uuid、独立speed_limit读回、control_reason、sensor_state、检测框/匿名tracks、STOP事件/人工确认、知识命中/模拟播报终态。坐标必须记录frame和转换来源，不能把odom直接标map。分别保留消息发生时间和接收时间；ROS回拨建立epoch，不跨epoch计算时延。

- [ ] 测试空值、NaN、过期TF、重复事件、乱序、epoch回拨、缺时钟映射；分析器拒绝给出不成立指标。
- [ ] 首次导航前做短采样，确认cmd_vel/odom/TF/UUID/读回字段确实入盘；未满足则不消耗一次完整验收。

## 4. 第一批：完整导览、动态视觉与安全

### WP01（P0）最新完整导览

**修改：**`scripts/run_visitor_full_demo.py`、`scripts/start_full_visitor_demo.sh`、`scripts/start_phase25_system.sh`；新增 `tests/test_phase29_full_demo.py`。

- [x] 为运行器新增 `--layout official|adaptive`、`--team-decision-mode business_script|vision_conservative`、`--output-dir`、`--timeout-sec`；保留旧参数兼容，自动验收默认不keep-open，交互演示才显式保留。代码与CLI/路径测试通过；不代表运行器完整路线通过。
- [x] 业务模式保持现有team.gathered启动与脚本掉队逻辑；视觉模式独立准备条件和操作员确认，禁止用脚本gathered作为视觉成功。两个模式分别运行，视觉模式真值隔离测试和最新完整suite通过；business_script只按对应业务run报告，不合并视觉证据。
- [x] 在最新代码跑一轮official/business_script入口→同意→wait/五区/exit，含知识库问答和有标记的模拟播报；同时采集当前可用的业务证据。run `visitor-full-20261123-104955` PASS；6个移动目标各有≥55条配对新鲜cmd_vel/odom样本，6次停车/恢复记录新旧UUID；采集契约3.1尚未全部贯通，故下一项拆分记录器验收。
- [x] 验证official/business_script入口→wait/五区/exit、讲解/知识库QA、cmd_vel+odom运动和终点新鲜停稳；最新run `visitor-full-20261123-125818`有7站访问序列，六个运动目标具备配对样本，Tour COMPLETED。Tour历史7次PAUSED中report仅包含5条停稳证据，需按局限披露。
- [ ] 独立验证人工STOP/取消优先和每个暂停session的停稳证据完整性；不以完整Tour替代该专项。
- [ ] 视觉模式独立验收：早期run `visitor-full-20261123-111123`和`113050`保留调速拒绝证据。新run `visitor-full-20261123-114541`证明实际YOLOX/RGB-D返回UNKNOWN时触发安全暂停并确认停稳；Action已取消后的旧调速请求通过`stale_session`被丢弃。45秒时仍等待外部操作员确认，故完整导览FAIL；演员只有短暂脚本重排，动态场景与恢复未通过。证据和哈希见run目录 `evidence.md`。

**验收：**至少一轮最新代码业务完整路线有可复核原始证据；任何缺项保留子结论，单一COMPLETED不自动整轮PASS。

### WP02（P0）动态真实视觉

**阶段2.9执行记录：**run `visitor-full-20261123-110241`发现 `sample_age_sec=inf` 导致ROS TeamObserver严格JSON序列化崩溃；在 `ros_team_observer.py`将无效年龄映射为null并保持观测无效/UNKNOWN，新增ROS节点回归。七包重新构建成功，定向3项通过。run `visitor-full-20261123-111123`证实节点不再崩溃且输出真实YOLOX/RGB-D匿名轨迹；脚本演员静止，29条团队观察为UNKNOWN。run整体因调速请求拒绝失败；动态八阶段仍NOT_RUN。详见同名实验目录 `evidence.md`。

**11:49补充执行记录：**新接口仅在Gateway确认无活动导航Action时标记过期调速响应；STOP阻断等拒绝不变。七包构建与网关/速度控制器64项测试通过。`visitor-full-20261123-114541`取得110条UNKNOWN视觉团队观察、112条有效距离、安全暂停与停稳确认；完整run等待外部操作员确认至45秒后FAIL。演员只在8.5–11.3秒短暂脚本重排；没有执行计划要求的八阶段动态视觉场景。

**13:42补充：**新run `visitor-full-20261123-133255`在zone_1的通用“导航安全停车”暂停；845条真实视觉团队观察全部为UNKNOWN，机器人停稳。发现运行器只按暂停原因字符串识别视觉事件，因而没记录该次暂停/外部操作员等待；全程保留为FAIL，不伪装通过。先新增回归测试、观察到1失败/1通过，再修复为依据视觉observer `requires_manual_confirmation`判断，并在vision模式只将observer数据传入暂停处理器、不读取脚本团队真值。`tests/test_phase29_full_demo.py`修复后20/20通过。完整动态八阶段和视觉路线仍未完成。

**修改：**`scripts/spawn_people_scenario.py`、`visitor_perception/{person_tracker.py,team_observer.py,ros_team_observer.py}`（后者路径均在 `ros2_ws/src/visitor_perception/visitor_perception/`）；新增 `tests/test_phase29_dynamic_vision.py`。

- [x] 视觉导览运行器在暂停原因是通用安全文案时，仍能根据observer的`requires_manual_confirmation`记录视觉待确认状态；新增测试先失败后通过，运行器vision分支传递的是observer payload而非Gazebo脚本team payload。专项20/20通过，不代表动态八阶段或视觉导览通过。

- [ ] 在机器人静止且已验证安全观察点配置三人进入/运动/短遮挡/出视域/重入、全队不可见、深度失效、检测过期八阶段；人物实际Gazebo回读，算法只接真实相机管线。当前已有静态相机观测子结果但八阶段均未执行。
- [ ] 遮挡用真实几何或人物互遮，不通过删除检测框冒充遮挡；深度/检测断流用本run可控隔离转发或自有节点暂停，原始相机仍记录，并标故障注入。
- [ ] 保存RGB/Depth、raw检测、关联检测、tracks、observer、TF、真值；按每阶段抽取至少5帧独立人工标注（尽可能40帧），记录可见遮挡状态和样本选择规则。
- [ ] 计算可计算的计数误差、P/R、可见连续段ID切换、轨迹碎片/失效延迟、有效距离率；没有人工身份时不计算ID准确率，没有独立表面距离参考时不报深度误差。
- [ ] 测试临时丢失不永久掉队、过期优先、重入不保跨遮挡身份、无全覆盖保持UNKNOWN、脚本真值注入不改变视觉输出。

**验收：**八阶段有实际记录和解释；检测失败可交付FAIL并定位，不能用人工框作为YOLOX输出。

### WP03（P0）E07-A与E07-B

**修改：**`gazebo_visitor_team.py`、`run_visitor_full_demo.py`、Tour Manager的 `ros_tour_node.py/tour_manager.py/team_observation.py`；新增 `tests/test_phase29_e07.py`。

- [x] E07-A：三名脚本游客在zone_3掉队至LOST、机器人安全停稳、集合后模拟操作员确认；原zone_3目标以新UUID恢复，Tour完成exit。证据：`experiments/E07-A/visitor-full-20261123-125818/evidence.md`；五条停稳记录覆盖七次PAUSED，状态PASS_WITH_RISK。
- [ ] E07-B：复用WP02真实视觉变化，触发保守安全等待→重新观测→操作员确认→安全资格检查→恢复；未运动时明确“静态观察恢复”，不得称导航恢复。
- [ ] 覆盖重复确认、陈旧确认、确认中取消、恢复中断流、旧目标响应迟到；测试不跳区、不重用UUID、重新见到3人不自动认定原3人身份。
- [ ] 分别写 `experiments/E07-A/` 与 `E07-B/` 报告；视觉和脚本lag不合并指标。

**验收：**A证明业务停车恢复；B证明真实感知驱动的保守交互，前向盲区仍明确未验证。

### WP04（P0）跟随与集合效率

**修改：**`scripts/visitor_trail.py`、`scripts/gazebo_visitor_team.py`、`tests/test_visitor_trail.py`；产物 `docs/phase2_9/team/regroup_analysis.md`。

- [x] 解析阶段2.7历史504.840秒的事件和live_evidence，按现存暂停状态及演员轨迹拆解，定位约147秒来源；未采集分段不推算。记录：team/regroup_analysis.md。
- [ ] 用当前代码固定seed/地图/速度/队距/操作员规则取得新基线，再改进最高耗时来源：优先弧长转角目标、暂停追赶路径、必要路径缓存或集合去抖；一次只改一类。
- [x] freshness读回修复后取得official完整Tour复测：zone_3 `LOST`→`GATHERED` 21.42秒，对比修复前部分run约201.7秒有改善迹象；新run无actor XYZ且非固定seed对照，不报告新物理步速或因果改善。证据：`experiments/WP04-regroup/visitor-full-20261123-125818/evidence.md`。
- [ ] 对转角、通道、队尾、停步、重复掉队加测试，验证步速有界、占据/人机/人人距离保护仍启用，不能跳坐标或跳过确认。
- [ ] 同条件复跑比较全耗时、最长/总集合、人物里程、重规划、距离、人工延迟与失败轮；目标最长集合降低≥30%且全耗时不增、安全保护不削弱。未达到保留无改善结论。
- [ ] 资源不足时至少运行纯几何转角/集合测试，结果仅标软件测试通过，完整路线比较NOT_RUN。

### WP07（P0，先于WP05/06高档）独立速度标定

**修改：**`scripts/record_phase2_topics.py`、`scripts/analyze_phase29_experiment.py`；复用现有Nav2 GetParameters读回；新增 `tests/test_phase29_speed_calibration.py`。沿用现有全场导览运行器做WP01，不复制阶段2.7通用runner。

- [ ] 对旧窗口与Nav2受理/WAIT/起动/转弯/STOP时序对齐，确认近零中位数来源；不只移动采样窗直到成功。
- [ ] 在地图选足够长直线，先验证净空、制动缓冲和路径；Nav2仍负责运动，不直发cmd_vel，不关避障。直线不足则该档NOT_RUN/BLOCKED。
- [ ] 0.3/0.5/0.7分别独立run；受理并真实起动后采新鲜odom，记录controller/smoother上限及其他限速源、cmd_vel、odom和角速度。
- [ ] 固定稳定窗≥2.0s、≥20条有效odom、间隙≤0.2s、|角速度|≤0.05rad/s、速度中位误差≤0.05m/s；输出波动、原因、窗口起止。空窗/混时钟/陈旧/起动前零速不能通过。
- [x] 实现CSV稳定速度窗分析及freshness/run/timestamp拒绝规则；22项记录器与9项速度分析软件测试通过。此项是分析器和数据契约，不是速度档实验。

阶段2.9续做：已实现离线CSV分析器，严格要求odom接收时间与ROS消息头时间均新鲜、cmd_vel新鲜、速度上限独立读回、连续20样本/2秒、间隔≤0.2秒及低角速度；报告均值误差/离散度与窗口。速度分析9项、记录器22项契约测试通过。没有阶段2.9CSV运行记录，三个标定档仍NOT_RUN；未实现或验证通用动态实验编排器。

**验收：**每档单独PASS/FAIL/NOT_RUN，未通过档不进入该档动态结论。

### WP05（P0）E02人群限速

**修改：**`spawn_people_scenario.py`、统一运行器/分析器/采集器；新增 `tests/test_phase29_crowd.py`。

- [ ] 同seed/路径/速度档设置无人、1/3/5人、渐增、渐散六独立场景，先使用通过标定低档；人物起点不与机器人重叠。
- [ ] 每样本分别记录ground_truth人数、detected人数、视觉距离、Scan距离、target_speed、独立参数上限、cmd_vel、odom、reason及valid/age；未标定面积则density_valid=false。
- [ ] 在相同路径弧长/直行窗口作无人对照，排除转弯、到达和STOP；Nav2本就更慢时标“实际减速贡献不可确认”。
- [ ] 分别判检测、策略、参数执行、实际速度四个子结果；参数成功不自动算物理减速。

### WP06（P0）E04三类横穿

**修改：**`spawn_people_scenario.py`、统一运行器/分析器；新增 `tests/test_phase29_crossing.py`。

- [ ] A前相机横穿、B相机外激光内、C双源各一个独立run，固定相机/轨迹和安全包络。
- [ ] 保持全部安全传感器开启；按实际首触发源解释，A若激光先触发不能改写成视觉主导通过。
- [ ] 对齐YOLOX、RGB-D、Scan、限速、odom、取消/停止/新会话恢复；B仅称障碍回波，不能称人员识别。
- [ ] 保存最小几何间隙及采样频率，缺接触反馈写null；几何风险中止为FAIL并保留，不冻结人物改标成功。

### WP08（P0）安全停车恢复复核

**修改：**按定位最小修改 `temi_bridge/{nav2_transport.py,nav2_backend.py,ros_gateway.py}`、速度控制和Tour Manager；新增 `tests/test_phase29_safety_recovery.py`。

- [ ] 先跑已有 `test_nav2_arrival_stop.py`、`test_phase27_recovery.py`、`test_phase28_control_races.py`；为发现的新竞态加重现测试。
- [ ] 独立注入持续靠近静止机器人、视觉/深度/Scan失效及恢复、人工停止、并发STOP、Action取消、定位失效；每项在config中明确刺激和预期结果。
- [ ] 只有Action终态、当前会话关联、新鲜odom连续静止和既有安全资格齐全才允许恢复；旧参数事务/旧UUID晚到无作用，取消优先于恢复。
- [ ] 记录刺激→策略→命令→实停、制动积分路程、各阶段几何间隙、旧新UUID、操作员；持续接近继续采样直至离开/风险中止。

**验收：**软件、Gazebo停稳、实体安全分别报告；几何代理不称碰撞认证。

## 5. 第二批：多布局、游客体验和交互

### WP09（P0）布局A/B贯通

**修改：**`start_phase25_system.sh`、`run_visitor_full_demo.py`、`simulation/{hall.launch.py,navigation.launch.py}`、`scripts/start_nav2_gateway.py`、`scripts/visualization_bridge.py`及对应配置加载；新增 `tests/test_phase29_layouts.py`。

- [x] 统一解析一个layout选项，映射 `simulation/generated/{official,adaptive}.{world,yaml,pgm}` 和 `<layout>_goals.json`；hall/Nav2/gateway/网页/游客/运行器全部接收同值。代码接线完成并有静态接口测试；资产净空/坐标/Nav2运行验收仍未完成。
- [ ] 固定业务站点ID wait、zone_1–5、exit；坐标从所选goals加载，讲解语义不变。验证地图分辨率/origin/yaw与ROS坐标转换、目标占据和机器人半径净空、入口出口可达；网页变换同源。
- [ ] 测试不支持布局拒绝、漏图/漏目标拒绝、官方坐标不泄漏进B、七个站点/五展区语义完整；静态连通性不能标Nav2成功。
- [ ] A复用最新完整验收；B至少入口到若干关键展区/窄通道真实Nav2，再资源允许完整路线；分别保存地图/目标SHA和结果。

### WP10（P1）散客、小团体、亲子

**修改：**Tour Manager、`config/submission_system.yaml`、`config/submission_exhibits.yaml`、网页现有选择入口；新增 `tests/test_phase29_visitor_modes.py`。

- [ ] 先审查现有游客类型/讲解层级字段，复用原值；显式用户选择三模式，不从图像推儿童身份。
- [ ] 散客覆盖迎宾/同意拒绝/导览/QA/送别；团队覆盖人数确认/转角队尾/掉队/集合；亲子覆盖监护确认、儿童友好内容、较慢目标节奏与互动提问。
- [ ] 对每模式执行状态机或ROS集成，验证模式参数进入业务与速度上限，但不绕过安全更低限速。优先散客/小团体各完整Gazebo，未跑的明确标注。

### WP11（P1）16类异常人机协同

**修改：**复用Tour Manager、Gateway、Knowledge和既有故障注入；新增 `tests/test_phase29_exception_matrix.py`；产物 `docs/phase2_9/exception_matrix.md`。

- [ ] 为听不清重讲、中途QA、未知问题、拒绝、掉队、遮挡、横穿、不可达、定位失效、断流、低电、断网、接管、取消、恢复、出口逐项列触发/响应/停稳/人工/恢复/失败处理。
- [ ] 重讲及QA前验证已有静止门，不在运动中播报成功后直接跳站；未知问题用知识库回退，不编造答案。
- [ ] 电量/网络/ASR条件不足则标模拟故障输入，不能改全局网络或影响用户连接；测试取消压过接管/恢复，拒绝后无导航。
- [ ] 每行关联测试和实际run；无法Gazebo复现的仅声称状态机/ROS测试，不能声称现场异常已覆盖。

### WP12（P1）五区内容与知识交互

**修改：**`config/knowledge.yaml`、`config/submission_exhibits.yaml`、`ros2_ws/src/heritage_knowledge/`与现有QA联动；测试扩展 `tests/test_knowledge.py` 及新增 `tests/test_phase29_content.py`。

- [ ] 五区逐项核对大众/儿童友好/深度内容、引用来源、主题差异与重复文本；补内容必须先有可查来源，不编传承人故事或合作关系。
- [ ] 每区测试一个已知问题、一个边界/未知问题，验证命中来源和回退；讲解层级选择实际改变内容。
- [ ] 验证打断→停稳→知识命中→模拟Speak终态→正确展区/同目标恢复，异常播报不能写spoken=true。
- [ ] 浏览器中文语音仅附加展示并标浏览器TTS；无实际ASR/temi音频证明始终保留。

## 6. 第三批：技术面板、回放和决赛材料

### WP13（P1）真实技术面板

**修改：**`scripts/visualization_bridge.py`、`visualization/ros_hall/{ros-live.js,index.html}`；新增 `tests/test_phase29_visualization_api.py`；复用现有页面样式，不重建展厅。

- [ ] 左侧同源地图/robot pose/目标/路径/游客真值/类型；右侧视觉框、ID、距离、传感器有效性/视野限制/Scan与UUID/Nav2/target/实读上限/cmd_vel/odom/STOP原因。
- [ ] 将只读GetParameters观测接入API/采集：controller的FollowPath.max_vel_x/max_speed_xy与smoother.max_velocity分别显示，带请求/响应时间、age、有效性；还要展示其他限速来源或标未知，不能将参数最小值直接称完整有效速度。
- [ ] 底部事件从真实业务/观测消息产生event_id+时间+来源，按epoch和序号排序去重；不能预播尚未发生的成功步骤。
- [ ] 有余量时限帧/限尺寸传实际RGB并叠同时间戳检测；无匹配图则显示结构化结果，不能叠到三维假画面。读接口不获得控制权限。
- [ ] API测试过期/乱序/缺参数服务/断源/未授权控制；浏览器观察≥60秒旋转/俯视/断源/重连，保存run_id截图与真实画面。

### WP14（P1）未来记录完整回放与只读HTTP

**修改：**`scripts/export_phase28_replay.py`、`visualization/ros_hall/{replay.html,replay.js}`；新增 `scripts/serve_replay.py`、`tests/test_phase29_replay.py`、`tests/test_phase29_replay.cjs`。

- [ ] 保持阶段2.8导出兼容，新增schema版本消费3.1真实记录；历史空字段保持空，轨迹图明确“源未采集”。
- [ ] 新样本回放map机器人轨迹、游客真值轨迹、odom/cmd_vel/上限曲线、状态/UUID/原因/关键事件；插值仅展示且注明，不作为指标原始点。
- [ ] SHA校验覆盖manifest、raw、归档、导出和嵌入图片；损坏、不一致、路径越界拒绝进入RECORDED_ROS2。
- [x] 本地HTTP服务实现绑定127.0.0.1、固定播放器资源、校验回放来源/SHA、GET/HEAD白名单；7项安全单测覆盖路径越界、symlink、错误哈希、控制字段和handler方法。当前沙箱未能实际bind socket。
- [x] `RECORDED_ROS2`回放校验及控制隔离有单测和Node检查；不接ROS、不接收控制请求。
- [ ] 实际HTTP监听/浏览器回放、seek/倍速及本阶段新run截图；需要本机端口和真实采集记录。

计划新增的预览命令：

```bash
.venv/bin/python scripts/serve_replay.py --recording artifacts/phase2_9/replays/<run_id>.json --port 8099
```

此命令需WP14实现后才存在，`<run_id>`替换真实run。此前本对话浏览器明确拒绝本地文件并禁止替代路由绕过；开发与CLI验证HTTP服务器可以开展，不能借新HTTP地址绕过该次工具策略。浏览器工具仍受阻则保留证据，让用户本机手动验收，报告不能标画面通过。
阶段2.9续做：scripts/serve_replay.py已实现127.0.0.1固定资源服务，并校验RECORDED_ROS2模式、来源manifest和回放SHA；页面仅从127.0.0.1自动GET回放JSON与校验文件。7项不绑定socket的安全单测通过。采集器补充墙钟/单调/ROS时间、新鲜map→base_link TF位姿、odom接收与ROS消息头双重时效以及Nav2 controller/smoother参数服务读回，22项契约测试通过；这些字段尚无本阶段ROS运行记录。记录延续现有CSV格式以保持当前分析工具兼容。因当前环境拒绝本地socket，实际HTTP监听与浏览器截图仍未验证；WP14整体验收复选框保持未勾。

### WP15（P1）六分钟演示

**新增：**`docs/competition_final/{slides_outline.md,six_minute_script.md,demo_storyboard.md,figure_evidence_map.md}`。

- [x] 编写0:00–0:45痛点、0:45–1:30架构、1:30–3:20演示、3:20–4:30实验、4:30–5:20鲁棒性/部署、5:20–6:00价值；合计360秒，标这是建议编排。另备240秒答辩。六分钟稿已创建；真实视频仍待录制。
- [ ] 约2分钟重点素材来自实际run：迎宾/感知/停车/集合/问答；每段标run_id、源时间、剪辑/倍速与RECORDED_ROS2，保留完整实验。
- [ ] 无录屏能力交付实际截图、可复现命令、分镜和缺失说明，不能说视频已完成。用户提供赛务文件须在最终提交前核对。
- [ ] 再查PPT源；无源时新建材料不称改原稿。可选新PPTX/PDF需可靠工具、每页渲染检查/无裁切/中文字体/引用/可打开，最终PDF另验哈希与页数。

### WP16（P1）创新、指标、答辩

**新增：**`docs/competition_final/{innovation_summary.md,technical_architecture.md,key_metrics.md,jury_qa.md}`。

- [ ] 贡献表分已有实现/采用开源/设计待验，绑定具体源码和run：不确定观测与安全分离、匿名交互、动态上限、UUID恢复、配置布局、SDK迁移与可追溯验证；ROS2/Nav2/YOLOX本身不称原创。
- [ ] 指标表每项含版本/run/单位/分母/统计窗口/失败/限制；550与504.840秒只在历史栏，新失败仍计入分母。
- [x] jury_qa至少20问，逐项覆盖用户列出的temi/ROS2/Android衔接、无设备、YOLOX、掉队、后视盲区、失效/实停、动画区别、创新、布局、成本、知识幻觉、隐私、低电、亲子、价值和落地缺口；每答绑定证据和不具备能力。已写24题并标出验证边界；后续随新实验补充对应run链接。
- [ ] 按20/20/20/15/15/10六评分维度建立证据映射；不编造专家评分或预估获奖概率。

### WP17（P2）实体部署与成本

**新增：**`docs/competition_final/{real_temi_deployment.md,cost_estimate.md}`；参考阶段2.8实机清单与Android MainActivity.kt、Bridge通信/停止代码。

- [x] Mermaid架构图区分Ubuntu ROS2、Nav2仿真后端、WebSocket、Android Kotlin/SDK、保存地点、感知、知识库/语音、操作员；明确实体后端使用SDK地点导航，不能暗示Nav2直接控制temi底盘。
- [x] 部署步骤涵盖网络/认证、SDK权限/Ready、地图地点、只读握手、断线保护、停止/接管、感知标定、知识内容、版本更新与逐级现场验收。
- [x] 成本表区分已有/采购/可选/未询价；缺报价写“待询价”，报价若查得则标来源日期/币种/含税范围，不编精确数。
- [ ] 无实体全部设备行为HARDWARE_REQUIRED；不发实体运动。修改Android才运行相应构建/测试，依赖失败保留，不能复用旧APK通过结论。

## 7. WP18（P2）最终回归、治理和交接

**修改：**`docs/PROJECT_STATUS.md`、`docs/next_phase_plan.md`、阶段2.9计划/进度；新增 `docs/competition_final/{final_progress.md,final_validation_matrix.md,overnight_report.md,blockers.md,evidence_index.md,experiment_summary.md}`。素材大文件在artifacts，摘要及SHA索引保留。

- [x] 最后主要源码修改后构建七包、source最新overlay、完整tests目录不排除用例；最新ROS包构建7/7，视觉暂停handler修复后的完整`tests/`为624 passed、190.10秒、退出码0。完整回归日志`audit/full-regression-20261123-1351.log`；早期完整回归和失败诊断见`audit/regression-20261123-1211.md`。
- [ ] 独立跑WebSocket、视觉/E07、安全停止恢复、布局A/B、API、回放SHA和JS运行专项；用实际存在的新测试文件名，失败修复后重新决定必要回归范围。
- [x] 固定所有ROS测试使用同一预检空域环境变量，运行前后用项目探针检查；最新完整回归通过`ROS_DOMAIN_ID=226`和`HERITAGE_TEST_ROS_DOMAIN_ID=226`固定域226，运行前后项目探针均确认域空。
- [ ] 归档run时校验源/归档逐文件SHA、不覆盖旧包、不删除失败轮；检查Git是否误包含原始视频/模型/凭据。只读回放要连同校验文件给出本机使用说明。
- [ ] 汇总每个工作包的代码/测试/run和状态，附全部尝试分母；至少分别列official完整路线、adaptive关键导航、E02六场景、E04三场景、E07两模式、速度三档及稳定性轮次。
- [ ] 稳定性预设正常三人/无掉队/掉队/短遮挡/中途QA/人工暂停/导航异常七类；每类独立run。资源不够优先正常/无掉队/掉队，未跑保持NOT_RUN，七类一次也不称统计可靠性。
- [ ] 短时性能测量至少预热10秒+采样60秒，记录CPU/内存/实时因子、推理P50/P95、页面更新/丢帧；无同条件优化前后数据不声称性能改善。
- [ ] 当前分支/HEAD和修改文件数按git实际计算。说明24c1423已提交推送、本阶段变更未提交；历史快照保留加注，禁止混成“当前全部未推送”。

执行已有命令模板（候选域必须实际检查，不把变量空值或旧域直接用于测试）：

```bash
cd /home/linao/heritage_workspace/heritage_temi_robot-phase28
source /opt/ros/humble/setup.bash
bash scripts/build_ros2.sh
source ros2_ws/install/setup.bash
: "${PHASE29_TEST_DOMAIN:?先选择并预检空闲域}"
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID="$PHASE29_TEST_DOMAIN"
export HERITAGE_TEST_ROS_DOMAIN_ID="$PHASE29_TEST_DOMAIN"
python3 scripts/phase25_preflight.py --check-domain-empty
.venv/bin/python -m pytest -q tests
.venv/bin/python -m pytest -q tests/test_gateway_websocket_integration.py tests/test_gateway_cli.py
node --check visualization/ros_hall/ros-live.js
node --check visualization/ros_hall/replay.js
node visualization/ros_hall/test-runtime.cjs
node tests/test_phase28_replay.cjs
python3 scripts/phase25_preflight.py --check-domain-empty
```

以上为命令顺序说明。实际运行器需捕获每条命令stdout/stderr/退出码，任何失败不能继续写PASS；使用tee时保存PIPESTATUS而非tee退出码。ROS setup不要置于set -u中source。不要通过停止他人的ros2cli daemon让忙域看起来空闲。

## 8. 验收状态和最终交付定义

| 状态 | 使用条件 |
|---|---|
| PASS | 本项预设条件与全部验收门成立，原始证据齐全 |
| PASS_WITH_RISK | 子目标有真实证据但覆盖、样本、几何代理等限制明确 |
| FAIL | 运行失败/安全风险中止/不满足固定条件，原始记录保留 |
| NOT_RUN | 没有执行；前置速度档不合格的后续场景也在此列 |
| BLOCKED | 具体资源/依赖/工具策略阻止，附实际检查或失败记录 |
| HARDWARE_REQUIRED | 实体设备缺失；Mock/仿真不可替代 |

最终中文交接必须包括：分支/HEAD/dirty及修改数、18项完成未完成、具体修复、完整路线/E02/E04/E07/视觉/速度/停恢/A-B/稳定性结果、新构建与完整测试和专项原始路径、六分钟稿/视频/面板/回放/PPTX/PDF/答辩材料有无与人工操作项、盲区/跟踪/动态缺口/无实体/无真实ASR-TTS/现场安全限制。每项链接来源，不用完成比例掩盖P0未验收。

## 9. 执行检查清单

- [ ] T00和G0/G1通过或有可核验BLOCKED记录；未影响用户进程。
- [ ] WP01–08逐项存在代码、测试或真实实验产物，所有未跑场景明确列出。
- [ ] WP09–12覆盖布局、游客模式、16异常和五区内容，不拿网页切图代替Nav2。
- [ ] WP13–14断源可辨、真值分栏、回放来源校验、控制隔离；浏览器受阻不得宣称视觉QA通过。
- [ ] WP15–17所有约定Markdown存在且证据链接有效，至少20条答辩，成本/原创/实机表述真实。
- [ ] WP18在最后源码修改后执行新回归，保留失败和新结果；没有自动Git提交/推送/合并。

**执行更新（13:51 CST）：**原任务18个工作包均已映射；采集和速度标定依赖前置，保留用户编号。已取得WP01 business_script完整路线、WP03 E07-A脚本闭环、WP04 freshness修复后完整路线观察等证据；WP02运行器暂停处理修复后完整`tests/`为624 passed。所有仍缺实验、覆盖或浏览器/硬件证据的复选框继续保持未勾选；详细状态见`docs/phase2_9/validation_matrix.md`和`docs/competition_final/final_validation_matrix.md`。
