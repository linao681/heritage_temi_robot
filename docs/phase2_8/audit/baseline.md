# 阶段 2.8 基线审计

审计时间：2026-11-22（Asia/Shanghai）。完整任务文本见 [`source_task.md`](../source_task.md)，逐项计划见 [`implementation_plan.md`](../implementation_plan.md)。

## Git 工作区保护

- 原工作区 `/home/linao/heritage_workspace/heritage_temi_robot`：分支 `main`，HEAD `bdf67d6dd1e09c503845af11e23a7f2f26b1a508`。审计时 `git status --short` 为484条，其中473条 untracked；`visualization/ros_hall/scene.js` 有用户现存改动，阶段2.5/2.7日志与证据大量未提交。审计时 tracked diff SHA256：`b59bc0d05ee741e527368c4b6316531b7ec66b4426ca393f868f1a04f2406510`。该区持续产生实验日志，数字与hash是该时刻快照；没有清理、复制或修改其中数据。
- 阶段2.8工作区 `/home/linao/heritage_workspace/heritage_temi_robot-phase28`：隔离分支 `phase2_8-work`，基线同为 `bdf67d6dd1e09c503845af11e23a7f2f26b1a508`，近五条历史见 [`baseline-git-history.txt`](baseline-git-history.txt)。完整 status 快照及 tracked diff hash 分别见 [`baseline-phase28-status.txt`](baseline-phase28-status.txt)、[`baseline-phase28-diff.sha256`](baseline-phase28-diff.sha256)。主工作区状态及其 diff hash 也分别保存于同目录。untracked 的本地 `.venv` 是指向原项目虚拟环境的符号链接；不纳入提交。阶段2.8源文件、测试和文档在该隔离工作区；不自动提交/推送。
- SHA256只覆盖 Git tracked diff；本轮新增文件在各自实验manifest与日志索引内另记SHA256。原工作区审计后日志持续变化，不把单个 tracked diff hash描述为长期静态值。

## 读取的阶段文档与代码基线

已读取任务指定的 `docs/PROJECT_STATUS.md`、阶段2.7 final report、validation matrix、visitor team implementation、blockers、competition demo guide 及 `docs/next_phase_plan.md`。阶段2.7事实基线为：两轮安全终点五区+出口仿真各7/7、504.840秒完整三人展示为脚本游客/模拟操作员，视觉队伍跟踪未验证；原S01失败仍保留；扩展前487项全量测试与扩展后97项定向测试不能相加；规定0.3m/s标定窗口无效；E02、E04和E07、60秒性能、回放与多轮稳定性未完成；实体 temi 缺失。

审查了计划列出的 Gazebo 游客、轨迹、完整演示、启动脚本、可视化桥及 visitor_perception、Tour Manager、Speed Controller、Temi Bridge、Heritage Knowledge、ROS Hall、simulation 与 tests 相关文件。执行前关键接口差异：

- YOLOX 使用本地 YOLOX-S ONNX 与 OpenCV DNN；原检测消息没有 track ID。RGB-D关联、CameraInfo/TF和既有 Perception Fusion 已存在，需沿用时间戳/有效性而不能伪造距离。
- `gazebo_visitor_team.py` 的 Gazebo 真值行为和脚本掉队控制必须与相机视觉决策隔离；视觉模式的 Tour Manager 不应消费模拟团队真值。
- Gateway/Nav2 已有导航 UUID、并发 STOP 合并、speed parameter 事务锁和新鲜 odom 停车确认逻辑；此阶段在这些门控上补竞态覆盖，不能用取消 ACK 当作实停。
- 现有 Three.js 页面是单一 ROS 展示入口；本阶段只计划增补真实数据和回放，不另造重复大网页。Android Bridge 存在静态可复用接口，但设备、SDK运行行为和真实底盘反馈不可验证。

## 工具链、资源与隔离

- ROS 2 Humble；Python 3.10.12；OpenCV 4.11.0；Gazebo Classic `gzserver` 位于 `/usr/bin/gzserver`。模型为本地 ONNX 文件的只读工作树链接，模型 SHA256=`c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`，CameraInfo 配置 SHA256=`0973f3b9d3b6bb0fa7c7c7f514ee18daf719a3c8275196c3eebcec48bb665a09`。虚拟环境链接原主工作区 `.venv`。
- 审计时内存15GiB、可用约5.5GiB、无swap；文件系统可用约46GiB。因此 Gazebo 按单实例串行运行，没有并发启动多个场景。
- `ss` 因沙箱 netlink 限制无法列出监听端口；改读 `/proc/net/tcp` 和 `tcp6` 的 LISTEN 条目检查11361、11363、11371、8089、8091，当时均未发现占用。每轮另做ROS domain检查。
- 相机冒烟使用 domain 213 / Gazebo 11371；实际所属进程组 `108297`、`108622` 已退出。测试使用 domain 218；WebSocket专项运行前后节点清单均为空。未停止其他 ROS/Gazebo 进程。

## 实验/测试证据解释

- 最新真实相机冒烟的完整 manifest、源码/模型hash、记录与限制见 [`../experiments/WP01-GAZEBO-CAMERA-01/`](../experiments/WP01-GAZEBO-CAMERA-01/)；原始高频文件在被忽略的 `artifacts/phase2_8/raw/`，另有gzip归档。它不含保存图像帧和人工框标签，因此不产生准确率结论。
- 528 passed 曾是竞态优先级修复前的全量测试；该结果不是最终快照结果。最终快照需在最后修改后重跑全量测试并更新摘要。
- `docs/runs/` 中由既有测试产生的 Mock 运行目录和主工作区实验记录均保留；不据其文件数量推断阶段2.8独立路线验收。
