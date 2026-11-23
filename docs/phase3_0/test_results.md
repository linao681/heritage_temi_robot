# 阶段3.0测试结果

## 基线与执行环境

- 时间：2026-11-23 14:55 CST
- 分支/HEAD：`phase2_9-work` / `f372e3f4e0702470eb91b2a32683e62590777840`
- ROS：Humble；Python 3.10.12；Node v24.15.0
- 资源快照：16 CPU；可用内存约6.2 GiB；`/home`可用约45 GiB
- Gazebo进程：预检未发现 `gzserver`/`gzclient`
- Git：唯一未跟踪目录为本阶段 `docs/phase3_0/`；无 tracked diff
- 未选取ROS Domain；尚未通过DDS探针证明域为空。当前TCP 7890、45247、25568、631等已有监听，阶段实验将另行选择并复查端口。

## 阶段2.9历史基线（不计入阶段3.0）

- 命令：`.venv/bin/python -m pytest -q tests`
- 结果：624 passed in 190.10s，退出码0
- 日志：`docs/phase2_9/audit/full-regression-20261123-1351.log`
- SHA-256：`609b53c935b48363831dd1cafd4200112991db64f5932cd81c179e5d5db52d74`

## 阶段3.0测试

### T01–T03

- 构建：`source /opt/ros/humble/setup.bash && bash scripts/build_ros2.sh`；7个ROS包成功，日志 `experiments/T01T02/build-20261123-1640/build.log`，SHA-256 `8e0d8cc87f13f9bd0c64cb188c0cbfc24fcff68e69bc4a032a156cf39de88be4`。
- 定向回归：在ROS overlay下执行full-demo、Tour Manager、ROS集成、控制竞态、Nav2停稳、视觉桥接及记录相关测试；`142 passed in 38.03s`，退出码0。日志 `experiments/T01T03/regression-20261123/pytest-targeted-final-overlay.log`，SHA-256 `14fc4bebc1c2364be62036a1ddc94fd0073a1b09d88489e08285c1537afda6ef`。
- 失败RED日志均保留在 `experiments/T01/`、`T01T03/`、`T02/`、`T03/`。一次省略ROS overlay导致模块导入失败，改为source overlay后才计入最终通过。

### T04 全程仿真

- `T04-vision/visitor-full-20261123-160651`：`PASS_WITH_RISK`，331.287秒，完整路线与知识问答通过；6次暂停有持续停稳及同目标新UUID/真实运动证据。相机为前向视场，团队在后方无法确认，使用模拟测试操作员、字幕而非实体TTS。
- `T04-vision/visitor-full-20261123-164811`：`FAIL`，326.806秒，路线导航配对运动完整，但7个暂停事件中入口wait暂停没有新UUID及配对cmd_vel/odom证据。报告SHA-256 `56266bdc5839195736ddc2dbff60c3d05419cbab88953db6e0f1f32e9463e4b8`，失败保留。
- `T04-business/visitor-full-20261123-162126`：`PASS`，377.088秒，官方布局wait→五区→exit及知识问答通过；脚本游客业务模式与视觉模式分开。

### T05 E04前向横穿

- 航向RED：`experiments/T05/scenario-heading-red.log`，预期因新测试所需辅助函数未实现而失败，SHA-256 `e94178329833759018ee3e73e761e20536899e55f273b85b7a1d5c4c80f03419`。
- GREEN：`experiments/T05/pytest-crossing-heading-green.log`，`63 passed in 0.40s`，退出码0，SHA-256 `5b00c94af20ebe8188fc0014a3c33ec918ce63bebf75abd6c0a2303a7bfb90ce`。配置校验 `valid:true`，SHA-256 `6fb6e38473157b522a5d5f8bbbb80618fc6a6a0f5ed9c8f93263612dea7909ae`。
- 实验 `T05/E04-CROSS-FRONT/run-004`：`PASS_WITH_RISK`；运行器PASS，导览COMPLETED，完整七站315.714秒。交叉演员3.000005m/55个Gazebo状态样本，13.159秒移动；融合人员距离有效102条、最小1.188m；控制原因含人员减速、近距离停车，激光障碍也同时有效。停车确认期间42条数据的cmd_vel为0，odom速度绝对值最大0.0063m/s。几何代理最小间隙0.544m，不是碰撞安全认证。报告、CSV、truth和日志SHA见 `experiments/T05/E04-CROSS-FRONT/run-004/evidence.md`。
- run-001、run-002、run-003失败均保留；根因分别为启动选项未支持、`start_distance_m`缺失和300秒固定路线超时。修复航向/配置后只做一次针对性run-004。实验后Domain 207 DDS探针空、Gazebo/Web端口可重新绑定。

### T06 E02人群对照

- 时钟RED/GREEN：未启用模拟时钟的odom freshness错误失败保留；显式Gazebo `/clock` 后相关回归 `96 passed`，日志 `experiments/T06/odom-clock-green.log`，SHA-256 `7b0e4717a1312fddc19589902c51fc246eba775ccb142156b267bcef2af34ac0`。
- 静态场景发布者匹配RED/GREEN：新增等待 `temi/navigation_status`、`odom`、`/gazebo/model_states`匹配后才放行导览；100项相关回归通过，日志 `experiments/T06/scenario-readiness-green.log`，SHA-256 `f9aa4aa4149734d0dbbf6b876ec010d25671b8181c22bf745a5dbc55ba155175`。
- `E02-0/run-002`与`E02-3/run-002`分别0人/3人真值，全程七目标PASS，分别318.037秒/324.187秒；真实CSV内odom freshness和cmd_vel有效，独立Nav2 controller限速0.300m/s。原始CSV、truth、report、manifest及postflight SHA在 `experiments/T06/E02-evidence.md`。
- 单人`run-002`尽管管理器及七个Nav2目标走到COMPLETED，整体因人物子进程没观察到导航而FAIL；发布者匹配修复后的`run-003`确认1个Gazebo模型和视觉人员距离，但Tour进入“机器人通信中断，停止状态未确认”而FAIL。两轮失败均保留，未据此宣称单人完整导览通过。
- 空/单/三人同一zone_1路线窗均按既有稳定条件执行分析；最长窗口分别1.305秒/14样本、1.524秒/16样本、0.907秒/10样本，均低于2秒/20样本。三轮Nav2速度上限读回都为0.300m/s；未获得可归因的稳定odom减速证据，故E02动态人群调速结论为NOT_VERIFIED。没有降低验收条件。
- 首批`run-001`虽完整路线通过，但记录器比较了系统时间与Gazebo时间，odom freshness无效；保留但不用于速度结论。五人/散开场景未运行。

### T07 adaptive布局B

- RED/GREEN：`tests/test_phase30_layout_adaptation.py`及hall转换、运行器、Gazebo人物回归先因布局透传辅助函数缺失而失败；最终`82 passed in 0.98s`，日志`experiments/T07/layout-green.log`，SHA-256 `9e5c40eff39bab4fa7c905b9a9922a5291caedc12f4bb5dfa1e3a6447fee725a`。
- ROS实际运行：Domain 214，Gazebo 11400，Web 8125。adaptive zone_1 Nav2 status 4、误差0.2226m、停稳通过；adaptive zone_1–5及exit为6/6成功、总目标耗时172.510s。完整报告与SHA见`experiments/T07/adaptive-layout-evidence.md`。
- 新配置通过validate-only。随后用`run_phase27_experiment.py`完成adaptive business_script路线wait→五区→exit；Tour `COMPLETED`、error_count=0、194.035s；QA命中知识条目并触发Mock Speak Action。一个Gazebo入口演员，脚本运行器调用同意服务；不属于三人掉队或视觉团队验收。runner manifest状态PASS。运行后Domain空且11400/8125释放。

### T08实时面板、记录回放与只读服务

- RED/GREEN：新增导出器测试先`5 failed`（模块不存在），实现后经历临时目录相对路径错误、实际历史快照缺少显式odom/cmd接收时间等失败；均保留早期日志及未使用的export目录。以快照中实际`elapsed_sec-age_sec`恢复记录时刻并按唯一时间去重后，新增测试`8 passed`，日志`experiments/T08/replay/export-green-04.log`，SHA-256 `1698cf53738fece3fc128f68a2005bf90098cb09ffc528d80a18fe683159d622`。
- ROS overlay定向回归：回放导出、phase28回放、phase29只读服务、可视化API和bridge测试`34 passed in 0.29s`，退出码0。未source ROS overlay的一次运行13项因找不到`temi_interfaces`失败、21项通过，留档但不计最终通过；source overlay后重跑全部通过。日志SHA-256 `6d739408342262b5e9dc5d2d6494c6eb9e99f4f5a192928df3e2db7143c3608e`。
- Node：`node --check ros-live.js`、`node --check replay.js`、`test-runtime.cjs`、`test_phase28_replay.cjs`通过；阶段2.9原始business_script记录经页面RECORDED_ROS2校验器哈希/manifest/只读校验通过，得到6050事件、1269机器人TF位置、3813 Gazebo游客真值位置和2250速度样本。最终replay SHA `3bb0e05025ef67fbfb63beb8d3f9d68bf0803629d295b4d8b058a0aa3372167c`。
- `serve_replay.py`仅绑定127.0.0.1。固定页、JS、记录与SHA GET=200；路径穿越和未知API GET=404；HEAD页=200；POST控制请求=501。导出源压缩包三文件逐项SHA一致。详细日志/来源hash在`experiments/T08/replay-evidence.md`。
- 实时面板HTTP快照在完成后获取，一些传感器字段显示过期/无数据，不能算活动过程截图。桌面浏览器视觉检查`NOT_RUN`；当前主机有用户Firefox进程，未连接或改动。Node/HTTP验证不替代中文布局、Canvas或console的视觉验收。

### T09–T11

T09决赛材料、T10最终全量回归及T11最终交接报告均已完成。阶段2.9的624项历史基线不算本阶段最终测试。


### T09 国赛材料一致性检查

- 检查日志：`experiments/T09/material-validation-final4.log`，退出码0，SHA-256 `0086435952ee02263e56e967f0bcd52835411877cc00a7381b038e9469568eb5`。
- 检查14份国赛材料存在且非空；讲稿6段合计360秒；答辩问答26项；分镜包含4个真实证据片段及127.0.0.1只读回放命令。
- 核验T04 business/vision、T07 business和T08 replay四份源文件SHA与实际文件一致。首轮检查发现回放SHA引用笔误，保留首轮失败日志`experiments/T09/material-validation.log`，修正文档后复验通过。
- 本工作树未找到PPTX、PDF或视频；本轮只形成Markdown讲稿、页纲、分镜、架构和证据材料，未生成/修改演示文件。


## T10 最终回归（阶段3.0）

- 运行域：ROS_LOCALHOST_ONLY=1、ROS_DOMAIN_ID=220、HERITAGE_TEST_ROS_DOMAIN_ID=220。运行前/后由`phase25_preflight.py --check-domain-empty`实测为空；测试后无残留Gazebo/Nav2项目进程，端口11399、11401、8126、8127可绑定。
- 构建：七包成功，9.01秒，退出码0。日志`experiments/T10/build.log`，SHA-256 `8a4ac62610af958f6f4cdea6bb9208306e01475470b65a80c8ba8afeccd151dc`。
- 完整回归命令：`.venv/bin/python -m pytest -q tests`（ROS Humble与新install overlay已source），没有排除用例；`680 passed in 189.75s`，0 failed、0 skipped，退出码0。日志`experiments/T10/pytest-full.log`，SHA-256 `91af50f880851a035f8d7d316a32662d7219bdd8b98ab084c92e22823f3ed837`。
- 独立定向组均退出码0：full-demo 28、tour-manager 31、tour ROS integration 17、dynamic vision/tracking 23、recording 26、speed calibration/controller 64、replay 19、WebSocket/gateway 36、安全竞态/ROS shutdown 22、新增phase30测试26。分组有覆盖重叠，不与680相加。逐组原始输出、退出码和SHA见`experiments/T10/targeted-summary.json`及同目录日志。
- 静态/接口：17个Python文件AST解析、全部scripts shell语法、两份网页JS语法、Node回放runtime与contract、ROS `ConfirmTeamRecovery`接口生成读取、`git diff --check`全通过；各日志和sha列于`experiments/T10/static-checks.sha256`。
- 本轮T10目录61个归档文件最大2055字节，不存在需要压缩的本阶段大日志；未删除旧失败证据。没有启动Gazebo或向机器人发送命令。
- 汇总：`experiments/T10/summary.md`。原始失败记录如T09早期材料哈希和空白检查失败继续留在目录，仅最终修复后通过状态用于结论。


## T11 最终交接报告核验

- 报告为七节；六组视觉旧/新导航UUID、同目标和配对运动样本逐项与`pause-resume-analysis.json`比对；6组暂停stop evidence均确认且odom新鲜。E07-A时间和UUID与历史run证据相符。
- T10 build/pytest、T04 business/vision和T08 replay的SHA与源文件复算一致；矩阵NOT_RUN与PASS状态、T09–T11复选框和本地证据链接通过检查。
- 最终校验日志`experiments/T11/report-validation-final2.log` SHA-256 `239a16eaecf605f88cec16adc58adecfbf9a22b81672c8c38d25cc029b2c21c8`，退出码0；最终`git diff --check`退出码0。
