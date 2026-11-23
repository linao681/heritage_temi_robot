# 阶段3.0 国赛冲刺实施计划

> 执行记录：按复选框顺序实施；每项先复现、再最小修改、再验证。不得自动 commit、push、merge。

**目标：**真实视觉暂停及恢复闭环、持续停稳证据、代表性动态交互实验、真实 ROS2 回放与六分钟决赛材料。

**架构：**沿用 Tour Manager、Gateway、Nav2、YOLOX/RGB-D、Gazebo 演员和 Three.js；仿真操作员是独立的测试输入，不替代视觉判断或安全资格。回放严格只读。

**技术栈：**ROS2 Humble、Gazebo Classic、Python 项目虚拟环境、Node.js、现有七个 ROS 包。

## 全局约束与调度

- 实际工作树 `/home/linao/heritage_workspace/heritage_temi_robot-phase28`；编写时 `phase2_9-work`，HEAD `f372e3f4e0702470eb91b2a32683e62590777840`，此前工作树干净。原项目目录 `/home/linao/heritage_workspace/heritage_temi_robot` 是另一工作树，不默认使用。
- 本文件是执行清单；完成状态以本文件复选框、`progress.md`、`experiment_matrix.md`及每项原始证据为准。624 passed 是2.9历史基线，不计为阶段3.0测试。
- 开始时HEAD为`f372e3f4e0702470eb91b2a32683e62590777840`，工作树干净；执行后保留的未提交改动见最终Git状态。禁止覆盖原有历史或自动集成。
- 不覆盖已有改动，不自动提交推送合并，不 sudo 或修改全局配置，不清理他人进程，不向实体temi发运动指令，不降低安全阈值、伪造数据或删除失败证据。
- 重型仿真串行；独立 run ID、日志、预检、超时和清理，只停止本轮自有进程。每一失败保存原始记录；同类问题三次失败后记录阻塞，切换独立任务。
- 顺序 T00→T01/T02→T03→T04→T05(E04)→T06(E02)→T07(B)；T08/T09可在资源不足时穿插；最后 T10/T11。优先局部真实视觉恢复、前方横穿、可播放回放。
- 实验状态 PASS、PASS_WITH_RISK、FAIL、NOT_RUN、BLOCKED、HARDWARE_REQUIRED。子断言缺证据用 NOT_VERIFIED/MISSING_EVIDENCE，不算整轮PASS。

## T00 仓库保护与记录（原文阶段1）

- [x] 检查当前Git状态，若分支不同或dirty，优先原工作树不冲突操作，不强制切换。当前位于 `phase2_9-work`、HEAD `f372e3f4e0702470eb91b2a32683e62590777840`；保留已有未跟踪计划目录，不切换分支。

```bash
cd /home/linao/heritage_workspace/heritage_temi_robot-phase28
git status --short
git branch --show-current
git log -3 --oneline
git diff --stat
sha256sum docs/phase2_9/audit/full-regression-20261123-1351.log
```

- [x] 阅读 `docs/competition_final/{final_validation_matrix,blockers,evidence_index}.md`、`docs/phase2_9/experiments/WP02-vision-observation/visitor-full-20261123-133255/evidence.md`、现有启动/runner和感知、Tour、速度、bridge模块。核对624项及旧失败，禁止重复开发已实现功能。
- [x] 建立 `docs/phase3_0/{progress,changes,test_results,experiment_matrix,blockers,final_report}.md`；新实验放 `docs/phase3_0/experiments/<ID>/<run_id>/`。每项记录HEAD/dirty源哈希、时间、配置哈希、域、端口、数据来源、预期、实际、命令、退出码、原始路径和SHA、清理结果。初始未执行项为NOT_RUN。
- [x] 每次运行前检查资源、依赖、Gazebo进程、候选端口；ROS探针必须实际初始化DDS成功才采信空域。保持现有 `run_visitor_full_demo.py` 资源门及 `start_phase25_system.sh` 自有进程清理逻辑。T04/T05各run均有预检与收尾复核；失败的命令与实验记录保留。

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
free -h
df -h /home
ps -eo pid,ppid,pgid,comm
ss -lntup
: "${PHASE30_DOMAIN:?先检查并选择候选域}"
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID="$PHASE30_DOMAIN"
export HERITAGE_TEST_ROS_DOMAIN_ID="$PHASE30_DOMAIN"
.venv/bin/python scripts/phase25_preflight.py --check-domain-empty
```

每次重新确定域与端口，不照抄226/228等旧值。预检不满足即BLOCKED，转离线工作。

## T01 视觉暂停原因与确认生命周期（阶段2.1–2.2）

文件：`ros2_ws/src/heritage_tour_manager/heritage_tour_manager/{ros_tour_node,tour_manager}.py`、`scripts/run_visitor_full_demo.py`。仅必要时修改原 Gateway/速度层。测试 `tests/{test_tour_manager,test_tour_ros_integration,test_phase29_full_demo,test_phase28_control_races}.py`。

- [x] 阅读 `_on_vision_team`、`_check_vision_team_freshness`、`_pause_for_vision_uncertainty`、`_on_control`、`visitor_uncertain`、`resume`、`resume_safety`，追踪实际 Action取消、停稳、暂停、操作员确认、恢复路径及并发时序。
- [x] 回归 observer 的 `requires_manual_confirmation`、同展区新视觉不确定事件与旧确认隔离；不以原因文案授权恢复。
- [x] 明确控制优先级和恢复门：团队不确定可要求独立确认；安全暂停仍需新鲜感知/速度恢复资格；取消、人工接管、低电量和断线走独立控制路径，团队确认不能解除它们。代码保留UNKNOWN观测。
- [x] 确认绑定当前 `team_pause_event_id`/`paused_session_id`，安全恢复使用单次decision ID、目标与session校验；已退役导航UUID不可复用，实际恢复由导航Action发新UUID，不直接发cmd_vel。
- [x] TDD与ROS集成回归覆盖不安全/过期/重复确认、旧会话、停稳证据、同目标恢复和运动回读；红灯及最终绿灯原始日志见 `experiments/T01/`、`experiments/T01T03/`。
- [x] ROS包构建及定向回归通过：7包构建成功；`142 passed`，见 `experiments/T01T02/build-20261123-1640/build.log`、`experiments/T01T03/regression-20261123/pytest-targeted-final-overlay.log`。

## T02 仿真测试操作员（阶段2.3–2.4）

文件：`scripts/run_visitor_full_demo.py`、`scripts/start_full_visitor_demo.sh`，必要时扩展原操作员接口；对应 `tests/test_phase29_full_demo.py` 和 T01 测试。

- [x] 新增 `--operator-mode external|scripted_test`，默认 external。scripted_test仅在本运行器自有 Gazebo `vision_conservative` 场景启用，模式不符时CLI拒绝；manifest与事件分开标记脚本操作员输入。
- [x] 操作员确认绑定当前暂停事件/旧UUID/目标，仅经现有恢复接口提交；需有效连续停稳及恢复条件，报告另核对新UUID与真实cmd_vel/odom。未使用Gazebo团队真值作视觉判断。
- [x] `vision_conservative` 与 `business_script` 分开验收；分别保存全程结果。视觉完整路线有PASS_WITH_RISK记录及后续一次缺暂停恢复证据的失败记录，不将失败项抹去。
- [x] CLI默认、无效参数、模式拒绝、确认门和恢复证据测试通过；相关定向测试纳入142项回归。

## T03 持续停车与导航证据（阶段3）

文件：`scripts/run_visitor_full_demo.py::pause_stop_evidence/summarize_navigation_motion`、`scripts/visualization_bridge.py`、复用 `scripts/record_phase2_topics.py` 的时间戳和freshness规则。测试：`tests/{test_phase29_full_demo,test_visualization_bridge,test_phase29_recording,test_nav2_arrival_stop}.py`。

- [x] `pause_stop_evidence()` 使用连续窗口，并同时记录线/角速度、新鲜度与停止session；门槛为 |v|≤0.02m/s、|ω|≤0.05rad/s、持续≥0.5s，未放宽底层安全资格。
- [x] 增加单帧/重复样本、连续停稳、速度边界/非有限值、过期/未来时间、session不符、停止确认/Action静默和新运动cmd_vel测试。

```python
import math

def bounded_velocity(value, limit):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= limit
```

- [x] 停稳窗口由唯一新鲜odom时间戳驱动；时间倒退/长间隔/数据无效/session变化/新运动cmd_vel都会重置。终点停稳与暂停session分别报告，缺样本不通过。
- [x] pause事件记录请求、确认、Action静默、odom线/角速度及年龄、稳定时长、恢复session、目标和配对运动；未取得证据保留NOT_VERIFIED。
- [x] `summarize_navigation_motion` 汇总目标对应的导航session与cmd_vel/odom配对；历史缺失值不补造。
- [x] T01–T03构建后定向回归通过，最终overlay测试为142项全通过。

```bash
.venv/bin/python -m pytest -q tests/test_phase29_full_demo.py tests/test_tour_manager.py tests/test_tour_ros_integration.py tests/test_phase28_control_races.py tests/test_nav2_arrival_stop.py tests/test_visualization_bridge.py tests/test_phase29_recording.py
```

## T04 真实视觉恢复与业务回归（P0）

- [x] 预检通过、七包构建/source overlay 后运行business_script与vision_conservative；变量均经本轮域/端口复核。

```bash
: "${PHASE30_DOMAIN:?预检空域}" "${PHASE30_GAZEBO_PORT:?空闲端口}" "${PHASE30_WEB_PORT:?空闲端口}"
bash scripts/start_full_visitor_demo.sh --layout official \
  --team-decision-mode vision_conservative --operator-mode scripted_test \
  --domain-id "$PHASE30_DOMAIN" --gazebo-port "$PHASE30_GAZEBO_PORT" \
  --web-port "$PHASE30_WEB_PORT" --timeout-sec 900 \
  --output-dir docs/phase3_0/experiments/T04-vision
```

- [x] 视觉模式完成完整路线，run `visitor-full-20261123-160651` 记录了UNKNOWN保守处理、显式脚本测试操作员、6次暂停的停稳和同目标新UUID/运动；状态PASS_WITH_RISK，不宣称前向相机看到后方队伍。
- [x] 视觉模式和business_script均运行wait/zone_1–5/exit，问答命中知识库，模拟播报明确标记。后续视觉复跑 `visitor-full-20261123-164811` 有一个wait暂停缺少恢复UUID/运动证据，保留为FAIL，不覆盖前次证据。
- [x] 独立 business_script run `visitor-full-20261123-162126` 完整通过，未启用scripted_test；每轮日志、超时、资源和域收尾记录已保存。

## T05 E04前方横穿（阶段4.2，动态首优）

复用 `scripts/{spawn_people_scenario,record_phase2_topics,run_phase27_experiment,analyze_phase27_experiment}.py` 与 `config/phase27_experiments.yaml`；必要时新增 `config/phase30_experiments.yaml`、`tests/test_phase30_dynamic_scenarios.py`。

- [x] 阅读并回归 `crossing`、Gazebo真值输出、导航目标触发和几何风险中止；修复横穿轨迹沿当前Nav2目标方位，而非初始机器人朝向。静态配置验证与定向测试通过。
- [x] run-004完成官方布局完整路线及前向横穿；保留人物继续移动、Nav2与安全保护。实测Gazebo演员3.000 m/55个模型回读；时间窗内YOLOX/RGB-D融合人员距离有效102条，检测人数1共101条，最小距离1.188 m；记录Scan障碍、速度原因、Nav2 UUID、cmd_vel/odom与暂停恢复。
- [x] 按单调时钟对齐传感器与演员：先出现人员距离减速，随后近距离人员停车；此时激光距离也有效，故停止不能归因为纯视觉。42条确认停稳采样cmd_vel为0、odom线速度绝对值最大0.0063 m/s。几何风险保护未触发；保留无接触传感器风险说明。完整证据及SHA见 `experiments/T05/E04-CROSS-FRONT/run-004/evidence.md`。其它方向/激光盲区未跑，继续NOT_RUN。

## T06 E02人群对照（阶段4.1）

- [x] 沿用 T05 编排执行 E02-0/1/3，实际Gazebo真值分别为0/1/3模型；三轮同官方地图、路线、seed31、zone_1触发点和配置限速0.3m/s。E02-0及E02-3全程PASS；单人两次失败均按原样保留。详见 `experiments/T06/E02-evidence.md`。
- [x] 使用10Hz `record_phase2_topics.py`记录相机检测/真值、人员与Scan距离、目标速度、Nav2参数读回、cmd_vel、odom和控制原因；为Gazebo显式使用模拟时钟，freshness有效。人物真值独立于视觉结果；不把人数当密度。
- [ ] 已按同一zone_1路线段执行 `analyze_phase29_experiment.py` 稳定窗分析，但空/单/三人最长有效窗分别仅1.305s/14样本、1.524s/16样本、0.907s/10样本，均未达到2s/20样本；三轮Nav2限速读回均0.300m/s。保留分析FAIL，不报告人群导致的物理减速或速度档达标。完整四层数据与SHA见 `experiments/T06/E02-evidence.md`。
- [x] 无人和三人各有一轮完整五区路线PASS；单人轮有真实演员/视觉采集但完整系统失败，故不计入通过轮。五人/散开未运行。所有失败、独立日志与postflight清理证据保留。

**T06结果：PASS_WITH_RISK。**视觉与数据记录链路可见实际0/1/3人，空场与三人路线完成；本轮速度稳定窗不足、Nav2限速没有随人数改变，E02动态人群调速效果仍未验证。不要把本状态包装为E02速度验收通过。

## T07 布局B（阶段4.3）

- [x] 静态校验 `simulation/generated/{official,adaptive}.{world,yaml,pgm}` 和 `<layout>_goals.json`：地图origin/分辨率/坐标变换、目标净空、连通性、页面目标坐标一致；错误layout/缺目标由转换与配置测试覆盖。相关回归82 passed，见 `experiments/T07/layout-green.log`。
- [x] 使用现有layout启动接口启动adaptive；zone_1独立Nav2目标与六目标导航路线均成功，报告含实际地图/目标SHA、Action状态、误差和停稳odom。随后通过T04参数模板运行adaptive `business_script`完整状态机，实际wait→五区→exit、问答来自知识库、播报是Mock。业务/操作员/单人演员限制与原始运行证据见 `experiments/T07/adaptive-layout-evidence.md`。

## T08 技术面板与真实回放（阶段5，P0）

文件：`visualization/ros_hall/{index.html,ros-live.js,replay.html,replay.js}`、`scripts/{visualization_bridge,export_phase28_replay,serve_replay}.py`；测试 `tests/{test_phase28_replay,test_phase29_replay_server,test_phase28_visualization_api,test_visualization_bridge}.py` 与 `tests/test_phase28_replay.cjs`。

- [x] 核对现有三维页面结构化面板字段、源/新鲜度标记、真实时间线及脚本真值/视觉分栏；T07实际ROS页面快照及过期字段见 `experiments/T08/live-panel/run-001/`。浏览器绘制未截图，不能称视觉通过。
- [x] 对计划指定full-demo JSONL新增 `scripts/export_phase30_tour_replay.py`，输出既有RECORDED_ROS2 schema、只读控制标记、来源manifest/归档/文件SHA、单调事件、ROS TF/Gazebo ModelStates轨迹和真实cmd_vel/odom样本；保留未采集RGB/depth空字段，无插值。导出、验证和SHA见 `experiments/T08/replay-evidence.md`。
- [x] 复用 `serve_replay.py` 的固定只读资源，localhost GET/HEAD通过，路径穿越及未知API拒绝、POST返回501；Python/Node定向测试通过。具体状态与日志见 `experiments/T08/replay-evidence.md`。
- [x] 尝试桌面自动化及独立Firefox临时profile；未获得安全截图，记录为 `NOT_RUN`，未影响现有用户Firefox。Node语法、页面运行时、真实run哈希校验均通过。中文/Canvas/console人工浏览器验证仍未完成，见 `experiments/T08/replay/verification/browser-visual-check.md`。

```bash
node --check visualization/ros_hall/ros-live.js
node --check visualization/ros_hall/replay.js
node visualization/ros_hall/test-runtime.cjs
node tests/test_phase28_replay.cjs
.venv/bin/python -m pytest -q tests/test_phase28_replay.py tests/test_phase29_replay_server.py tests/test_phase28_visualization_api.py tests/test_visualization_bridge.py
# 实际记录与SHA生成后，用 scripts/serve_replay.py --recording <记录> --sha256 <校验文件> --port <空闲端口>
```

## T09 六分钟国赛材料（阶段6）

- [x] 更新国赛指标、验证矩阵、实验摘要、证据索引、进度、阻塞、交接报告和`docs/PROJECT_STATUS.md`；明确624为阶段2.9历史结果，并写入T04–T08真实记录。
- [x] 更新讲稿、页纲和分镜，分配40/50/120/70/50/30秒共360秒；链接完整导览、E07-A掉队恢复、视觉停稳、知识问答及本机只读回放命令。没有录像工具输出，故保留可复现分镜；未生成视频。
- [x] 更新创新边界、数据源架构图、图证映射和26项答辩问答；区分成熟开源组件、Gazebo脚本游客、真实视觉观察、测试操作员、Mock Speak与实体Temi。未发现PPTX/PDF源，本轮没有声称修改或生成。材料检查日志`experiments/T09/material-validation-final4.log`退出码0，SHA-256 `0086435952ee02263e56e967f0bcd52835411877cc00a7381b038e9469568eb5`；首轮哈希笔误及失败日志保留。

## T10 最终回归（阶段7）

- [x] 代码修改全部结束后，预检新空域、七包构建、source新overlay、不排除完整pytest。保存stderr/stdout/实际退出码；失败不以tee成功冒充。不得同时运行重型仿真，结束后再次确认本轮域空。

```bash
set -o pipefail
source /opt/ros/humble/setup.bash
bash scripts/build_ros2.sh 2>&1 | tee docs/phase3_0/build.log
# 构建失败则停止并记录
source ros2_ws/install/setup.bash
: "${PHASE30_DOMAIN:?重新预检空闲域}"
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID="$PHASE30_DOMAIN" HERITAGE_TEST_ROS_DOMAIN_ID="$PHASE30_DOMAIN"
.venv/bin/python scripts/phase25_preflight.py --check-domain-empty
.venv/bin/python -m pytest -q tests 2>&1 | tee docs/phase3_0/pytest-full.log
```

- [x] 单列定向 full_demo、tour_manager、tour_ros_integration、dynamic_vision、recording、speed_calibration、replay_server、WebSocket、安全竞态、新增测试。检查Python/Shell/JS语法、ROS接口兼容、`git diff --check`、`git status --short`。原始日志尾空格不改写，不能删失败断言或排除用例。改代码后重新验证相关测试及最终全量。
- [x] 大日志用gzip逐文件验证解压SHA，沿用2.9 raw_archive_manifest方法；不删除失败数据，不提交Git。T10新日志最大2055字节，不需要压缩；过去阶段的失败证据原样保留。


T10摘要：`experiments/T10/summary.md`；完整测试680 passed，Domain 220运行前后为空。
## T11 最终报告与交付（阶段8–9）

- [x] `final_report.md` 分七节：实际修改及文件/版本；视觉暂停恢复（old/new UUID、原目标、确认与实际运动）；停车证据（线/角速度、freshness、每次暂停覆盖）；E02/E04/布局B独立结果；构建7/7与实际pass/fail/skip、日志、HEAD；浏览器/回放/视频/PPTX/PDF是否具备与人工项；软件/仿真/设备/展示遗留问题。
- [x] `experiment_matrix.md` 分列视觉局部/全程、业务全程、前方/可选横穿、E02无人/单人/三人及可选人数、B单目标/全程、浏览器、全量回归；逐项关联run和SHA，缺项保持真实状态。
- [x] `progress.md` 更新所有复选框，只勾证据满足者；逐项检查原任务九阶段覆盖。每次尝试都有命令和证据；同类失败三次后转独立任务。最终交付至少瞄准局部真实停复、连续停稳、一个动态交互、真实回放、六分钟材料和验收报告，受阻如实交接，不为通过降低安全门。


最终交付：`final_report.md` 七节报告已按原始实验日志核对；视觉暂停UUID/停稳窗口、E02/E04/B与回放/材料状态均列明。报告校验日志`experiments/T11/report-validation-final2.log`退出码0，SHA-256 `239a16eaecf605f88cec16adc58adecfbf9a22b81672c8c38d25cc029b2c21c8`。

## 执行方法

每一项：阅读 → 测试/复现 → RED记录 → 最小实现 → GREEN → 必要构建/仿真 → 保存原始证据 → 更新进度。T00–T11均已按清单核对状态；未通过或未运行的具体子场景保持FAIL/NOT_RUN并保留证据。T06稳定速度对照未通过，T08浏览器视觉验收NOT_RUN。复选框只代表对应的代码、测试、过程处理或实验有证据，不代表证据中的失败子项自动通过。
