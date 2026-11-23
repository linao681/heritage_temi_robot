# 阶段2.9执行进度

更新时间：2026-11-23 13:51 CST

## 版本与工作区

- 工作树：/home/linao/heritage_workspace/heritage_temi_robot-phase28；当前分支 phase2_9-work，基线HEAD 24c14231de61840a11c5462805df0cd6160af84d。
- 本阶段修改未提交、未推送、未合并；未修改主工作树。
- 没有实体Temi；没有向实体设备或其他用户ROS/Gazebo进程发送控制命令或发出停止命令。

## 已完成的代码、测试和材料

- 导览运行器加入官方/适配布局、业务脚本/视觉保守模式、唯一输出目录、超时、哈希清单和资源/端口预检。视觉模式不以脚本队伍真值决定恢复。
- 启动器将布局传递给地图、Nav2、网关、网页和游客演员；面板补充Tour状态历史、数据源/模式和Nav2只读参数读取。
- WebSocket服务在监听套接字缺失时关闭失败，不再让空listener导致后续索引异常；增加失败关闭单测。
- 五区知识库的15条问答新增儿童友好表达，并允许QA链路与实时网页提交 child 层级。表达为官方来源内容的简化复述，不增加传承人或合作事实。
- 已有材料包括六分钟稿、分镜、页纲、架构、创新边界、20+答辩题、成本/实体部署及证据索引。
- 增加 scripts/serve_replay.py：仅在127.0.0.1提供固定页面和单个已校验RECORDED_ROS2文件；页面对本机HTTP地址自动取数，文件选择回退仍保留。服务器没有ROS客户端或控制路由。安全单测7项通过。
- 新增异常矩阵与指标映射；阶段2.7最长集合等待离线分析记录在 team/regroup_analysis.md。
- 扩展 `scripts/record_phase2_topics.py`：增加墙钟/单调时钟/ROS时间、仅接受新鲜 map→base_link TF 的机器人位置、odom接收时间与ROS消息时间双重新鲜度，以及controller和velocity_smoother参数服务的独立速度上限读回。缺失或过期值写空并标无效。
- 新增 `scripts/analyze_phase29_experiment.py`：只从采集CSV寻找连续的速度稳定窗口，要求fresh odom/cmd_vel、独立Nav2限速读回、20条样本、2秒、最大间隔0.2秒、低角速度和误差≤0.05m/s；无空值插值。记录器契约22项、速度分析9项单测通过，但没有阶段2.9运行数据，因此速度标定仍是NOT_RUN。
- 代码与UI均未通过阶段2.9实时Gazebo/浏览器验收。

## 最新验证

- 最新七包ROS2构建：7 packages finished [54.2s]，退出码0。输出目录：/tmp/phase29-colcon-log-final3/。此后仅修改顶层Python记录器、其测试和文档；ROS包源码未再变化。
- 当前定向回归：144 passed，1 deselected，14.90秒；仅排除会在本环境初始化ROS Domain并挂起的 `test_vision_mode_ignores_scripted_team_status_in_ros_node`。
- WebSocket纯协议/失败关闭专项：5 passed，14 deselected，0.06秒。真正需要监听socket的集成用例无法运行；首次认证握手用例因服务未能绑定本机监听端口失败，后续网络用例未据此计通过。
- 可安全离线测试子集：506 passed，1 deselected，23.47秒；排除含ROS节点、Fast DDS或本地网络监听的14个测试模块，并排除上述1项ROS节点用例。这不是完整tests目录通过数。
- 全仓测试收集成功：607项；只收集，不代表全部执行。全仓ROS/网络集成测试未运行。
- 当前改动Python文件py_compile、两份网页JS语法、回放Node专项、三个启动脚本bash -n和git diff --check通过。
- WebSocket现场式本地监听受执行环境限制，无法建立localhost listener；服务已改为有界失败，协议/失败关闭测试通过，实时通信仍阻塞。
- 扩大混合回归时，真实WebSocket网络模块因socket权限有失败；包含ROS节点构造的混合回归在Fast DDS初始化阶段无输出。两次尝试分别拆开重测：纯离线子集通过，ROS节点项保持deselected，网络闭环保持BLOCKED。
- Fast DDS无法在当前环境创建UDP transport，不能据空域探针宣称某个ROS Domain空闲。

## WP01实际尝试与Gazebo状态

唯一阶段2.9实验目录为 docs/phase2_9/experiments/WP01-full-tour/visitor-full-20261123-020925/。运行器在启动任何ROS/Gazebo/Web进程前返回 BLOCKED：可用内存5.098GiB，低于6GiB；本地socket权限导致11441和8141端口均无法探测。详细原始report、manifest和SHA256在run目录的 evidence.md 中。

因此本阶段Gazebo实际导航run为0，WP01完整路线没有运行。E02/E04/E07、动态视觉、三档速度、动态停车恢复与A/B真实导航均为NOT_RUN。阶段2.7的504.840秒只作为历史业务脚本记录。

## 下一步

需在每次启动前复核资源、ROS域与端口；视觉handler修复后的完整视觉复测及其他动态实验尚未运行。没有可确认空域/端口时不运行ROS/Gazebo。详细未完成项与命令见 validation_matrix.md、blockers.md、audit/verification-attempts.md。


## 2026-11-23 09:21 运行环境刷新

- 新证据：`audit/runtime-refresh-20261123-0921.md`。可用内存回升至6.8GiB，磁盘余量46GiB；本轮端口11441/8141绑定检查通过。
- ROS域232/231/230/229/227/226/225经实时探测为空；域228仍有整套Nav2、Gazebo、传感器和项目节点。为遵守重型仿真串行要求，没有启动另一套Gazebo，也没有操作域228。原先5.098GiB阻断记录继续保留。
- 实时本机WebSocket集成专项19/19通过；vision_conservative忽略脚本队伍真值的ROS节点测试在域232通过1/1。二者均不替代动态相机追踪或完整Gazebo路线。
- WP01保持BLOCKED，原因现为现有完整仿真在线；待其结束后重新检查资源、域和端口，再启动business_script官方布局路线。阶段2.9 Gazebo导航run数仍为0。


## 2026-11-23 09:26 最终启动门结果

- 以官方布局、`business_script`、三名脚本游客尝试启动WP01。域232为空、端口11441/8141可用，内存6.763GiB、负载0.8825/CPU、磁盘45.30GiB；但运行器检测到现存`gzserver`，依据资源门在启动任何组件前返回`BLOCKED`，事件数0。报告位于`experiments/WP01-full-tour/visitor-full-20261123-092632/`。没有干预现有进程。
- 此后再次确认域232为空，域228仍有Nav2/项目ROS节点。WP01依然未运行；阶段2.9 Gazebo导航run数为0。必须等现有Gazebo结束后重做资源、端口和域检查，再启动完整路线。


## 2026-11-23 09:29 阻断复核

- 等待后于09:29:52只读复核仍检测到`gzserver`；可用内存6.9GiB但无swap，负载17.57/16核=1.10/CPU，超过运行器门槛。停止本轮Gazebo启动尝试，不发送信号、不清理现有进程。完整记录见`audit/runtime-refresh-20261123-0921.md`。


## 2026-11-23 11:15 CST 运行环境刷新与真实仿真进展

- 当前工作区仍为 `/home/linao/heritage_workspace/heritage_temi_robot-phase28`，分支 `phase2_9-work`，HEAD `24c14231de61840a11c5462805df0cd6160af84d`；阶段2.9改动未提交、未推送、未合并。
- 用户确认可退出本会话为测试启动的Gazebo。此前自有仿真已退出；没有停止其他ROS/Gazebo进程。
- 本机复核：ROS Domain 226为空，Gazebo/Web端口11373/8095可绑定，可用内存约7.8GiB、磁盘余量约44.8GiB，未发现其他Gazebo。后续实验可串行运行。
- WP01最新 `business_script` + official 完整路线run `visitor-full-20261123-104955` 状态PASS：入口接待/同意、wait/五区/出口、知识库问答、模拟字幕播报、最终COMPLETED；每个实际移动目标都有新鲜cmd_vel与odom配对运动样本（zone_1…zone_5、exit各≥55条），停站有新鲜静止odom。报告记录6次停车/恢复、旧/新UUID、同目标恢复；Tour Manager计时523.617秒、run总计时536.929秒。脚本游客/模拟操作员与模拟播报边界见run报告，不代表实体Temi或视觉团队通过。其余WP01人工取消专项未运行。
- WP02旧run `visitor-full-20261123-110241` 保留FAIL：完整演示超时，`team_observer`因非有限样本年龄JSON序列化崩溃。修复后构建7个ROS包通过，`test_ros_team_observer.py`与`test_phase29_dynamic_vision.py`定向测试3项通过。
- 修复后新run `visitor-full-20261123-111123` 仍整体FAIL：首个wait目标调速请求被ROS网关拒绝，控制器锁存ERROR。同期相机真实管线实际输出YOLOX/RGB-D轨迹，团队观察29条均保守为UNKNOWN；脚本演员在本run没有移动。八阶段动态实验没有完成。逐条指标、失败条件和SHA见该run的 `evidence.md`。
- 新run退出后复核226域为空、11373/8095端口可绑定、无本run残留Gazebo；关闭过程中Tour Manager未确认停车，因此该项失败证据保留。
- 当前结论：最新代码的业务脚本完整路线通过；静态相机管线已获得部分真实图像证据；视觉模式在导航起步调速时仍有阻断。不得将以上合并成“视觉完整导览通过”。


## 2026-11-23 11:49 CST 视觉安全暂停复测与接口竞态修复

- 用户允许退出本会话为测试启动的Gazebo；此前实验进程已自行退出。本次复测结束后确认Domain 226为空、端口11377/8101可绑定、没有残留Gazebo或演示进程；未停止其他用户ROS/Gazebo进程。
- 发现网关在导航Action已由保守视觉安全逻辑取消后，仍可能收到旧调速请求。新增服务字段`stale_session`，仅在活动导航Action已不存在时标记过期；速度控制器记录并丢弃该结果，不声称速度已应用。STOP阻断、活动会话不匹配、STOP执行中及语音占用等拒绝继续走原有错误处理。
- ROS2七包重建通过；`tests/test_ros_gateway.py`与`tests/test_speed_controller.py`合计64项通过。
- 11:44的run `visitor-full-20261123-114400`在启动前因域227仍发现`ros2 node list`创建的CLI发现节点而拒绝；没有启动Gazebo，记录保留在run目录。
- 11:45的run `visitor-full-20261123-114541`整体FAIL：45秒上限结束时仍等待外部操作员确认，未恢复或完成全程。但实时视觉管线有110条团队观察均为UNKNOWN（1/3：108条观察到1人、2条观察到2人），112条有效RGB-D轨迹距离2.241–3.346米；Nav2安全暂停、目标保留、odom静止和STOP_CONFIRMED均有记录。网关两条无活动Action的旧调速请求标记并丢弃，未因此进入ERROR。Gazebo真值显示演员只在8.5–11.3秒短暂脚本重排，之后停留；没有受控遮挡、离场或重入测试。关机时传感器停止后进入ERROR作为失效保护记录保留。
- 新run证据及SHA-256见`experiments/WP02-vision-observation/visitor-full-20261123-114541/evidence.md`。WP02八阶段动态人员场景仍未执行；人工确认后恢复、完整视觉导览和E07-B仍未验证。
- 完整`tests/`目录最终回归：619 passed，186.56秒，无排除项。第一次未统一测试域的诊断运行和业务恢复测试夹具修复见`audit/regression-20261123-1211.md`；服务接口变更后的64项网关/速度控制器定向回归也已通过。
- 全量运行前后项目探针确认Domain 226为空；测试结束后没有残留pytest、ROS或Gazebo进程。

## 2026-11-23 12:28 CST E07-A部分运行与仿真清理

- 在确认Domain 226空闲、7.779 GiB可用内存和端口11379/8102可用后，启动专用E07-A `business_script` 官方布局run `visitor-full-20261123-121915`。该模式使用三名Gazebo脚本演员及模拟操作员；不计为视觉团队验证。
- 运行447.396秒，完成入口接待/同意、入口待命点及zone_1–zone_4，正在前往zone_5时用户要求结束该测试。报告保留`FAIL`及“演示被操作员中断”，没有出口或全程完成结论。
- 六段暂停期间均有与暂停session匹配的新鲜`STOP_CONFIRMED`和odom；确认后每段最大线速度为0.0071 m/s，六段均≤0.02 m/s。最后一次队尾滞后4.735 m，`LOST`持续到约351.9秒才`GATHERED`，模拟resume于353.79秒接受；该次集合等待约201.7秒，初始追赶路径68个0.2m网格waypoint。它暴露了WP04效率问题，但不是优化前后对照实验。
- 终止时最新样本处于zone_5导航中，`stop_confirmed=false`；没有声称该run的结束停稳验证通过。SIGINT后发现并清理了本次运行遗留的Gazebo/ROS launch子进程，仅对本次运行独有的进程组发送SIGTERM。随后项目探针确认Domain 226空、端口11379/8102未监听、本次记录PID均退出；未干预其他用户进程。
- 原始数据和SHA-256见`experiments/WP03-E07-A/visitor-full-20261123-121915/evidence.md`。WP03专用E07-A/B尚未完整验收；WP04未实施优化或同条件复测。
- 复盘本次SIGINT后残留子进程，将完整演示器启动系统管理脚本的`Popen`改为`start_new_session=True`。新增回归用例先失败、修复后通过；`tests/test_phase29_full_demo.py`为18 passed，启动脚本语法与`git diff --check`通过。12:11全量619项结果早于此修改，完整套件还需重跑；真实Gazebo中断清理复测也未做。详见`audit/process-shutdown-fix-20261123.md`。
- 进一步分析本run的队尾轨迹：654个Gazebo actor位置样本覆盖约199.2秒，采样路径长度下界12.971m，平均0.0651m/s；脚本循环中位3.30ms、ModelStates为20Hz，而旧读回容差20mm可接受小于容差的旧缓存样本。已修改`PeopleScenario.move()`要求服务确认后新鲜ModelStates，并以现有`GetEntityState`作为超时读回；TDD新增两项用例从失败到通过，`test_gazebo_people_scenario.py`、`test_visitor_trail.py`与`test_phase29_full_demo.py`合计55 passed。修复后的Gazebo速度/集合时间仍待复测。

## 2026-11-23 13:10 CST 修复后完整导览与E07-A复测

- 在复核Domain 226为空、端口11379/8102释放及7.776 GiB可用内存后运行 `visitor-full-20261123-125818`。official / `business_script` / 三名Gazebo脚本游客；接待、同意、入口待命、zone_1–zone_5、QA与exit均完成，Tour `COMPLETED`。Tour计时381.869秒、runner计时396.386秒。知识问答命中`music_types`；播报是计时字幕/Mock Speak，不是实体音频。
- report的导航运动证据覆盖zone_1–zone_5和exit六个目标，每目标均有新鲜cmd_vel/odom配对样本；出口新鲜odom为0.001129m/s、age 0.0332s。Tour历史有7次PAUSED，但report仅有5条独立停稳证据，明确记录这一覆盖差异，不声称7次全部逐一确认。
- 同一run记录zone_3掉队最高lag 4.7428m，`LOST`持续21.42s至`GATHERED`；模拟操作员随后恢复原zone_3目标，导航session从`45d9c7474a47472789b875a637e10cd4`换为`1bc8f3f47a47472789b875a637e10cd4`。此前部分run约201.7s等待有积极对比，但非固定seed/逐帧XYZ的受控前后实验；WP04状态改为`PASS_WITH_RISK`，不报告新队尾实测速度。
- 原始证据、SHA、重现命令和限制见`experiments/WP04-regroup/visitor-full-20261123-125818/evidence.md`；E07-A摘要在`experiments/E07-A/visitor-full-20261123-125818/evidence.md`。视觉模式E07-B、八阶段动态感知及其他P0场景仍未验收。
- run退出后发现其自有Domain 226 ROS CLI daemon（启动时间12:58:19），按本项目实验清理停止该daemon；随后项目探针报告Domain 226 empty，11379/8102未监听，无本run自有Gazebo/导览进程。未停止其他用户进程。

## 2026-11-23 13:42 CST 视觉模式真实观察与运行器修复

- run `visitor-full-20261123-133255`在official / `vision_conservative` / 三名Gazebo脚本演员下启动。845条视觉团队观察全部为`UNKNOWN`（818次1/3、21次2/3、5次短暂3/3、1次0/3）；5次3/3也因`forward_only`覆盖保守返回UNKNOWN。848/850条深度样本为fresh，有效距离2.224–3.345m。
- 机器人在zone_1保持`PAUSED`；801条暂停telemetry中800条有`stop_confirmed`、新鲜odom且速度≤0.02m/s，最大0.0000416m/s。脚本团队流另报count=3和gathered，但未用于视觉决策；该log不含人物XYZ。没有完成操作员恢复、全程导览或八阶段动态视觉验收；run保留`FAIL`和原始report。
- 根因为runner只按暂停reason中“视觉/观察”字样触发handler，实际Tour reason为通用“导航安全停车”。TDD复现先得到1失败/1通过；最小修复改用observer `requires_manual_confirmation`，并确保vision分支传observer数据而不是脚本队伍真值。`tests/test_phase29_full_demo.py`现20 passed。
- 修复前run报告没有`pause_stop_evidence`字段采集，但live JSONL有停稳数据；完整说明、失败边界及SHA见`experiments/WP02-vision-observation/visitor-full-20261123-133255/evidence.md`。运行器修复后的完整视觉复测仍待运行。
- 随后确认Domain 226为空、11379/8102端口释放、没有本run遗留进程。最新全量622项测试在此runner补丁之前；修复后已通过full-demo模块20项，完整测试套件需再执行。

## 2026-11-23 13:51 CST 最新验证与进程状态

- 视觉pause-handler修改后完整`tests/`通过624项，190.10秒，退出码0；运行前后由`phase25_preflight.py`确认Domain 226为空。日志：`audit/full-regression-20261123-1351.log`；SHA-256 `609b53c935b48363831dd1cafd4200112991db64f5932cd81c179e5d5db52d74`。
- 受限运行环境的首次域预检因ROS日志目录只读失败；该失败未执行测试，随后按项目授权运行的预检和全量测试均成功。尝试记录见`audit/verification-attempts.md`。
- 用户允许退出本会话测试进程。当前检查未发现本项目Gazebo/导览测试进程；没有停止其他用户进程，也没有重新启动Gazebo。
- `visitor-full-20261123-133255`仍保留FAIL：845条视觉团队观察均为UNKNOWN，未人工恢复或走完路线。WP02八阶段、E02/E04、三档速度、E07-B和布局B保持未完成。
