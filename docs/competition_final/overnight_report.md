# 阶段2.9国赛冲刺交接报告

更新：2026-11-23 13:51 CST。分支 `phase2_9-work`，HEAD `24c14231de61840a11c5462805df0cd6160af84d`。本阶段改动未提交、未推送、未合并。

Git发布状态补充（2026-11-23 14:19 CST）：实施与证据提交`5a3d3a51717df436b9bf0f8ce2192237b5b18d91`已推送至`origin/phase2_9-work`；该分支未合并到`main`。本报告中的13:51工作树描述是发布前快照。

## 开发与自动化验证

- 当前运行器可选官方/适配布局及`business_script`/`vision_conservative`模式，带资源、域、端口预检、超时、独立run目录和SHA清单；视觉模式将队伍观察与Gazebo脚本队伍真值分开。
- Tour Manager、ROS网关、速度控制器和游客观察器已有阶段2.9修改；包括旧导航Action调速响应隔离、ModelStates新鲜度读取、observer无效年龄安全序列化及通用安全暂停的视觉人工确认处理。
- ROS2七包构建7/7成功。最新完整`tests/`回归在最新视觉暂停handler修改后运行：**624 passed，190.10秒，退出码0**，测试前后Domain 226均由项目探针确认为空。日志：[`full-regression-20261123-1351.log`](../phase2_9/audit/full-regression-20261123-1351.log)，SHA-256 `609b53c935b48363831dd1cafd4200112991db64f5932cd81c179e5d5db52d74`。
- 本次尝试在受限运行环境内做域探针时，ROS日志目录只读导致探针无法写入；随后在授权的项目运行环境复核成功。该次权限失败记录在[`verification-attempts.md`](../phase2_9/audit/verification-attempts.md)。

## 全导览与团队恢复

1. **WP01 business_script 官方路线：PASS。**最新run `visitor-full-20261123-125818`使用三名Gazebo脚本游客及模拟操作员，完成接待、同意、wait、五区、知识库问答和出口；Tour `COMPLETED`。Tour计时381.869秒，运行器计时396.386秒。zone_1–zone_5及exit六个移动目标有新鲜cmd_vel/odom配对样本，出口odom为0.001129m/s。知识问答命中`music_types`并带来源；播报为计时字幕/Mock Speak。Tour有7次PAUSED，但report只保存了5条独立停稳证据，不能称7次均逐一验证。
2. **E07-A脚本团队闭环：PASS_WITH_RISK。**同一run在zone_3观察到脚本队伍`LOST`后，于21.42秒转为`GATHERED`；模拟操作员确认后以新UUID恢复原zone_3目标，随后完成全程。它不属于真实视觉团队恢复。
3. **WP04集合效率：PASS_WITH_RISK。**新run集合耗时比此前约201.7秒的部分run短，属于改善迹象；两轮不是固定seed、同起点/队距的受控对照，新run无actor XYZ，不据此报告新步速或因果优化结论。

## 真实视觉观察与安全

- **WP02完整动态视觉：FAIL（局部安全观察通过）。**run `visitor-full-20261123-133255`实际使用Gazebo RGB→YOLOX→RGB-D→匿名跟踪。845条团队观察均为`UNKNOWN`：818条只见1/3、21条见2/3、5条短暂见3/3仍因`forward_only`覆盖限制而为UNKNOWN、1条见0/3。848/850条深度样本新鲜；有效距离为2.224–3.345m。801条暂停样本中800条有新鲜odom停稳证据。脚本团队feed另行记录，未用于视觉决策。
- 该run停在zone_1，未进行操作员恢复、全程导览或动态八阶段验收，保留`FAIL`。运行器未识别通用原因“导航安全停车”是需视觉人工确认的暂停，现已依据observer的`requires_manual_confirmation`修复，并在vision模式传递observer而非脚本team数据。新增定向测试20/20通过；随后624项完整套件也通过。
- 未归档RGB/Depth帧或逐帧人工标注；遮挡、离场/重入、深度故障、检测过期和E07-B仍未验收。前向相机不宣称能确认后方游客。

## 其余工作包

- E02拥挤限速：0/6；E04横穿：0/3；0.3/0.5/0.7m/s独立速度标定：0/3；E07-B：未完成；adaptive布局B Nav2导航：未运行。
- 持续接近、视觉/深度/Scan失效恢复、实时浏览器检查及完整可浏览回放未完成。软件限速字段或策略测试不等于实测odom减速。
- 六分钟讲稿、分镜、页纲、图证映射、创新摘要、技术架构、指标、答辩问答、实体部署和待询价成本分类已生成；没有经验证的演示视频、用户现有PPTX源文件或最终PDF。
- 无实体Temi；真实SDK底盘运动、制动、ASR/TTS、设备电量/网络及现场安全均为`HARDWARE_REQUIRED`。Mock Speak和Gazebo几何距离不构成实体验证或碰撞认证。

## 运行清理与Git状态

用户授权结束本会话自行启动的测试。当前进程检查没有发现本项目导览/Gazebo测试进程；没有停止其他用户ROS/Gazebo进程。pytest结束后Domain 226为空。未使用sudo、未修改全局配置、未向实体temi发运动命令，也未执行Git提交、推送或合并。

12份高频游客状态原始日志已生成gzip归档，并用SHA-256逐份验证解压内容与原文件一致；清单见`docs/phase2_9/raw_archive_manifest.csv`。原始大文件保留在本机，gzip归档、实验摘要和关键证据纳入提交。pytest生成的Mock run目录由`.gitignore`排除。

逐项证据见[`final_validation_matrix.md`](final_validation_matrix.md)、[`experiment_summary.md`](experiment_summary.md)、[`evidence_index.md`](evidence_index.md)及对应run目录。
