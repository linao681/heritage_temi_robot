# 阶段3.0最终执行报告

更新时间：2026-11-23 20:34 CST。结论按本阶段实际run与测试日志填写；`PASS_WITH_RISK`、`FAIL`和`NOT_RUN`均保留，不将软件结果外推为实体能力。

## 1. 执行版本与修改范围

- 分支：`phase2_9-work`；HEAD：`f372e3f4e0702470eb91b2a32683e62590777840`。
- 阶段3.0修改均留在工作树，没有自动提交、推送或合并。已有T00–T08修改、配置、测试及实验原始记录均保留。
- 主要改动：暂停事件与导航会话绑定；恢复操作员身份和确认接口；连续停稳证据及目标/UUID运动配对；改进前向横穿运动场景；显式Gazebo仿真时钟与演员发布者就绪；official/adaptive布局透传到Nav2、业务Tour和检查脚本；记录真实ROS轨迹/速度并生成哈希校验的只读回放。
- 主要代码文件包括`ros2_ws/src/heritage_tour_manager/`、`ros2_ws/src/temi_interfaces/`、`scripts/`、`visualization/ros_hall/`与对应`tests/`。T11收尾检查为39个tracked文件有修改、976个未跟踪文件（含实验/测试证据及新增文件），未提交；逐项状态见`git status --short`，实验源码哈希见各run manifest。
- 任务状态：T00–T03 PASS；T04–T08 PASS_WITH_RISK；T09 PASS_WITH_RISK；T10 PASS；T11报告和矩阵已完成。各阶段失败日志仍在`docs/phase3_0/experiments/`。

## 2. 视觉暂停、人工确认与导航恢复

T04视觉路线`visitor-full-20261123-160651`使用Gazebo RGB→YOLOX/RGB-D→匿名观察链。六次队伍观测不足触发的暂停均有新鲜odom停稳、测试操作员确认、同目标新UUID恢复和真实仿真运动。操作员模式为`scripted_test`；这不是现场真人接管。运行器完成官方布局入口、五区、QA和出口，Tour耗时331.287秒，整体`PASS_WITH_RISK`。

| 暂停目标 | 旧导航UUID | 新导航UUID | 确认/恢复证据 | 新会话配对cmd_vel/odom运动样本 |
|---|---|---|---|---:|
| zone_1 | `d9da137d43dd414b856f3e7bd0090b9a` | `08e0f1687e684f7fabb7b80ca9acd820` | 测试操作员确认；同目标 | 55 |
| zone_2 | `f278fd3f97e642ca932e7966368cf211` | `bbb3945aa2a6468c9a5bb271738b9790` | 测试操作员确认；同目标 | 106 |
| zone_3 | `0e9930adb29844f992d4a064acf7396b` | `f79eec94e3844bec8a4f6043b9b43da6` | 测试操作员确认；同目标 | 10 |
| zone_4 | `bea0974af2274f51bf6b99e61626e5ae` | `954afe7c59a145f587e0742aa352ffc9` | 测试操作员确认；同目标 | 115 |
| zone_5 | `06e1c573d02448be8b42d405ac9d60a6` | `af1488a2da694c049a94b7ceb44beac5` | 测试操作员确认；同目标 | 166 |
| exit | `ed59ec45afd04834852ebcd68799c1f6` | `853a8196443446cd8ce50e35524c454e` | 测试操作员确认；同目标 | 210 |


该run共记录1078条团队视觉观察，全部为`UNKNOWN`；相机覆盖为`forward_only`。因此它证明的是保守等待、停稳和测试操作员确认后的路线恢复，不证明相机成功观察整支队伍或自主判断掉队。该run报告SHA-256：`c8def186c8bc3cd6f5b67fa87e70bb6e8bd106c1fde68bb95ec786d7906f05e0`；恢复分析SHA-256：`6b60242a5fe2e656540cee20949a563a551bad4bea215527deebaf64f22b8167`。

独立的E07-A脚本业务run `visitor-full-20261123-125818`记录zone_3 `LOST→GATHERED`为21.42秒；脚本操作员确认后，目标仍为zone_3且换新UUID：停止`45d9c7474ce04eef8f9601b469649c12`，恢复`1bc8f3f47a47472789b875a637e10cd4`。该实验是Gazebo脚本队伍状态，不属于视觉判断；与此前约201.7秒部分run没有固定seed/起点/队距控制，不作因果比较。原始报告SHA-256：`5d745cb17badc728bda90cfd3f45afddd446e08c905a3681760349f914958ddd`。

## 3. 停车证据与边界

T04视觉run的六次暂停都由6个新鲜odom样本构成，稳定窗口约0.505–0.522秒。线速度绝对值范围约0.00004–0.00555 m/s，角速度绝对值范围约0.00001–0.02057 rad/s；里程计age范围约0.0035–0.0348秒。各目标、旧UUID、样本数与时间见同目录`report.json`和`pause-resume-analysis.json`。

出口终态另外记录6个样本、0.519秒稳定窗口、odom age 0.00903秒；线速度0.00667 m/s、角速度−0.01381 rad/s，Tour为不移动。这里的静止是Gazebo odom判据，不是Temi实体制动或接触安全认证。E04 run的停车确认窗口内42条样本`cmd_vel=0`，odom线速度绝对值最大0.0063 m/s；无接触传感器。

## 4. E02、E04、官方布局A与适配布局B

### E02 人数场景

| 场景 | Tour结果 | zone_1稳定速度窗口 | 结论 |
|---|---|---|---|
| 空场0人 | PASS，7站，318.037秒 | 1.305秒/14样本 | Nav2限速读回0.300 m/s；不满足2秒/20样本门槛 |
| 单人 | FAIL（两次失败run均保留） | 1.524秒/16样本 | 一次演员等待超时；修复后run出现通信中断/停稳未确认，不能记完整通过 |
| 三人 | PASS，7站，324.187秒 | 0.907秒/10样本 | Nav2限速仍为0.300 m/s；样本不足以证明拥挤导致实速下降 |
| 五人/散开 | NOT_RUN | — | 未运行；人数不等于密度 |

相关原始数据和哈希见[`T06/E02-evidence.md`](experiments/T06/E02-evidence.md)。E02总体`PASS_WITH_RISK`：视觉人数/真值对照和空场、三人路线有记录，但人群密度未标定、稳定窗不达标，也没有可归因的实际减速结论。

### E04前向横穿

T05 `E04-CROSS-FRONT/run-004`为`PASS_WITH_RISK`：3名Gazebo演员之一按活动导航UUID横穿；55个模型状态样本累计移动3.000005 m。真实YOLOX/RGB-D人员距离有102条有效样本，最小1.188 m；速度策略依次记录人员接近减速与近距离停车。停车时LaserScan障碍也有效，因此不能归因于纯视觉；独立激光盲区横穿和其他方向横穿`NOT_RUN`。几何包络最小间隙0.544 m仅为代理值。证据见[`run-004/evidence.md`](experiments/T05/E04-CROSS-FRONT/run-004/evidence.md)，报告SHA-256 `cfdba1e6ea9278715322b993cce1546a3f7af40e3aa3d8793df98e4fbd9cbdf2`。

### 官方布局A与适配布局B

- 官方A业务全程：T04 `business_script` run `visitor-full-20261123-162126`完成入口同意、wait、zone_1–zone_5、知识库问答和exit，377.088秒；3名Gazebo脚本游客，测试流程触发同意/集合，Mock Speak；Tour `PASS`。报告SHA-256 `6afc1a912eeb3d95212ecdc643b071c6ad99e197b328e38dc93f1d7eb1be3f31`。
- 适配B Nav2：zone_1关键目标到达且停稳；zone_1–zone_5和exit分别成功，6/6目标、172.510秒。另一个独立adaptive业务run完成wait、五区、QA和exit，194.035秒，1名入口演员、测试脚本同意、Mock播报。布局静态一致性82项通过。导航与业务是分开运行的证据，整体`PASS_WITH_RISK`，不代表实体地图或三人视觉跟随。

## 5. ROS2构建、自动化测试与代码检查

- ROS2 Humble七包构建：7/7成功，colcon 9.01秒，退出码0。日志[`T10/build.log`](experiments/T10/build.log)，SHA-256 `8a4ac62610af958f6f4cdea6bb9208306e01475470b65a80c8ba8afeccd151dc`。
- 未排除完整命令`.venv/bin/python -m pytest -q tests`：680 passed，0 failed，0 skipped，189.75秒，退出码0。测试前后Domain 220为空。日志[`T10/pytest-full.log`](experiments/T10/pytest-full.log)，SHA-256 `91af50f880851a035f8d7d316a32662d7219bdd8b98ab084c92e22823f3ed837`。阶段2.9的624 passed是旧基线，不能替代本轮测试。
- 定向回归均退出码0：full-demo 28、tour-manager 31、tour ROS integration 17、dynamic vision/tracking 23、recording 26、speed calibration/controller 64、replay 19、WebSocket/gateway 36、安全竞态/ROS shutdown 22、阶段3.0新增测试26。套件相互覆盖，不与680相加。逐组日志、退出码和SHA见[`T10/targeted-summary.json`](experiments/T10/targeted-summary.json)。
- 静态检查：17个Python文件AST解析、`scripts/*.sh` bash语法、两份页面JS语法、Node回放完整性/只读测试、ROS `ConfirmTeamRecovery`接口读取和`git diff --check`均通过；详情见`experiments/T10/static-checks.sha256`。
- T10日志目录最大文件2055字节，没有新增大体积日志需要gzip；历史失败材料未删除。T10没有启动Gazebo，也没有向实体机器人发送命令。

## 6. 回放、浏览器、视频与比赛文件

- T08只读回放从阶段2.9真实业务run导出6050事件、1269个ROS TF机器人位置、3813个Gazebo ModelStates游客真值位置和2250个cmd/odom速度样本；回放SHA-256 `3bb0e05025ef67fbfb63beb8d3f9d68bf0803629d295b4d8b058a0aa3372167c`。loopback HTTP固定资源及哈希检查通过，服务仅绑定`127.0.0.1`，无控制接口。
- T08来源run没有RGB/depth帧；回放不插值、不用Gazebo真值伪造YOLOX轨迹。桌面浏览器GUI布局、Canvas和console视觉验收`NOT_RUN`，没有截图；自动化连接超时，未触碰用户Firefox会话。
- 工作树中未找到PPTX、PDF或MP4/WebM；本轮没有生成、修改或声称验收这些成品。已有Markdown讲稿、页纲、分镜和答辩题；6分钟稿分配40/50/120/70/50/30秒，共360秒，答辩问答26项。分镜命令见[`competition_final/demo_storyboard.md`](../competition_final/demo_storyboard.md)。
- 没有实体Temi。Android SDK导航、实体速度、制动、真实ASR/TTS、相机接口、低电量/断网现场处置、接触安全均为`HARDWARE_REQUIRED`；Mock Speak与浏览器语音不等于实体播报。

## 7. 未完成项与验收建议

1. 受控动态遮挡、离开/重入、深度/检测过期以及视觉E07-B完整恢复未完成；前向视角无法确认后方队伍，UNKNOWN必须保留。
2. E02五人/散开、稳定速度因果对照及0.3/0.5/0.7 m/s独立标定未完成。不得把0.300 m/s配置或`cmd_vel`命令当成实测速度变化。
3. E04纯视觉、纯激光盲区和其他方向横穿未完成；联合传感结果不能支持单源归因。Gazebo几何间隙不构成碰撞认证。
4. 官方/适配布局实验已分别验证，但B的完整Nav2路线和业务Tour是两个独立run；多游客视觉导览与实地场馆坐标仍待验证。
5. 只读回放已经生成且服务端通过验证，但无GUI视觉检查和录屏；赛前需人工打开页面核验画面，再按分镜录制视频。PPT/PDF需在取得可编辑源文件后另行制作和逐页检查。
6. 实体部署还需Temi、SDK许可与设备接口核验、真实地图、感知标定、限速/制动测试、网络与电量故障注入、操作员接管流程和场馆安全审批。

**最终结论：**阶段3.0软件实现、仿真证据整理和全量自动回归已完成。整体只能按各工作包状态交付：关键业务与布局B路线有仿真完成证据；视觉团队观察保持UNKNOWN但能触发停稳与操作员恢复；E02实速调节和若干传感专项未通过或未运行；实体设备、现场安全和演示成品仍未验收。请按此报告和`experiment_matrix.md`逐项验收。最终报告交叉校验日志为`experiments/T11/report-validation-final2.log`，SHA-256 `239a16eaecf605f88cec16adc58adecfbf9a22b81672c8c38d25cc029b2c21c8`；六组旧/新UUID、停稳数据、build/pytest/replay哈希和复选框均已对照原始文件检查，最终`git diff --check`退出码0。
