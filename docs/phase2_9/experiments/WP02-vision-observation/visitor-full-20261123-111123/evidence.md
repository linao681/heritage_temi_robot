# WP02 真实视觉管线初步证据

## 结论

本次 run 整体 **FAIL**，不是完整动态视觉验收。相机 → YOLOX → RGB-D → 匿名跟踪 → 团队观察管线实际输出了新鲜结果；但机器人在首个 `wait` 目标启动后，速度命令被网关拒绝并锁存 ERROR，导览没有继续。此run中的脚本游客没有移动，八阶段动态场景、人工标注和E07-B均未执行。

## 运行信息

- run_id：`visitor-full-20261123-111123`
- 分支/HEAD：`phase2_9-work` / `24c14231de61840a11c5462805df0cd6160af84d`（本地有未提交阶段2.9改动，源码哈希见 `manifest.json`）
- 布局/模式：`official` / `vision_conservative`
- ROS Domain：226；Gazebo master端口11373；网页端口8095
- 配置上限120秒；实际运行18.56秒后失败
- 预检：通过；运行前可用内存约7.78GiB，Gazebo进程0，端口可绑定
- 演示游客：3名Gazebo脚本演员，仅作场景演员；视觉算法读取相机/深度，不使用演员真值作团队结论
- 运行命令：`source /opt/ros/humble/setup.bash && source ros2_ws/install/setup.bash && export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=226 PYTHONPATH=scripts && .venv/bin/python scripts/run_visitor_full_demo.py --layout official --team-decision-mode vision_conservative --domain-id 226 --gazebo-port 11373 --web-port 8095 --timeout-sec 120 --output-dir docs/phase2_9/experiments/WP02-vision-observation`

## 实际观测

- `live_evidence.jsonl` 共32条采样记录，跨度18.56秒。
- YOLOX检测与RGB-D关联输出标记为 `source=vision_tracker`，观察中出现匿名ID `vision-e0-1` 至 `vision-e0-4`；23个有效轨迹采样含2条track，6个采样含3条track。62个有效距离样本范围约2.662–3.345米。
- 团队观察29条新鲜记录均为 `UNKNOWN`，并要求人工确认。即使观测人数达到3，也没有把前向视野推断成全队身份/覆盖，符合保守设计。
- 3名脚本演员在run记录中的进度始终为3.6、2.5、1.4米，没有实际移动；因此这些观测只证明静态场景下管线有输出，不证明稳定动态跟踪、掉队判断、遮挡、离开或重入性能。
- 新版 `team_observer` 未再因 `sample_age_sec=inf` 崩溃，且实际发布track/team观察。此修复另有定向ROS集成测试证据；不能据此推断动态行为已验证。

## 失败与安全处置

- 导览在 `WAITING_CONSENT` 后开始前往入口待命点 `wait`。当时机器人定位约为 `(-12.65390884, -7.90223695)`，官方 `wait` 目标为 `(-12.65390884, -7.90223695)`，两者几乎重合。
- 随后 `temi_speed_controller` 发出0.5m/s命令，ROS网关以“导航会话不匹配或当前任务禁止调速”拒绝；控制器锁存ERROR，run按错误退出。日志没有记录网关拒绝时的活动槽位/阻断状态，因此“零距离目标与速度命令时序竞态”目前是待核实假设，不记作已确认根因。
- 记录期间未见机器人有效移动cmd_vel或正向odom。关闭时Tour Manager报告“中断导航时停车未确认: 无法确认停止”；保留该失败，不把它写成已确认停车。
- run退出后经本机复核：ROS Domain 226为空，11373/8095端口可重新绑定，无残留Gazebo；清理仅针对本run进程。

## 证据文件及SHA-256

- `report.json`：`198123a50fd7545540d2d7cfdff67116a9508ad72c0632dc262b9edccef3fd08`
- `live_evidence.jsonl`：`167861268d055c99b96f03d51cc5c46c7945fcd7daa0e50498ecdd6eaf666834`
- `system/perception.log`：`7bb50f6ddd34442a3862f7f5db0be9e7e15669e1c2a771a6f195a5c38c4f48cf`
- `system/speed.log`：`3db7775d077f3499ac1b458f88e5d5cf3f3c64c0a0299174dcacd4afecd193c0`
- 全量实验清单、环境、地图/目标/模型哈希：`manifest.json`

## 后续验收

先定位并修复（或证伪）`wait`首目标调速请求被拒绝的时序问题，再独立运行静止观察点下的八阶段动态人物实验：三人运动、遮挡、出视野、重入、全队不可见、深度失效、检测过期。需要按场景保存原始图像、标注规则和感知指标；当前证据不覆盖这些要求。
