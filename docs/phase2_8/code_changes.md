# 阶段 2.8 代码变更记录

所有修改位于隔离分支 `phase2_8-work`。主工作树中的 `visualization/ros_hall/scene.js`、旧日志和其他已有改动均未在此分支清理。未提交/未推送。

| 文件/组 | 变更 | 验证/限制 |
|---|---|---|
| `ros2_ws/src/visitor_perception/visitor_perception/person_tracker.py` | 新增匿名 bbox IoU 一对一关联、有限预测、短时丢失、过期与时间回拨 epoch | 纯算法测试；不维持跨遮挡身份 |
| `.../team_observer.py`、`.../ros_team_observer.py`、`tests/test_phase28_team_observer.py`、`tests/test_ros_team_observer.py` | 保守视野/人数/时效判定及 ROS team_observation 与 tracks 发布 | ROS + 单测；前向相机不足时 UNKNOWN/manual confirm |
| `ros2_ws/src/visitor_perception/visitor_perception/ros_shutdown.py` 与 `ros_person_detector.py`、`ros_depth_association.py`、`ros_perception_fusion.py`、`ros_team_observer.py` | 统一 spin/shutdown 处理 ROS context 已关闭异常，确保节点/上下文退出 | 关闭路径定向测试与最新七包构建 |
| `ros2_ws/src/visitor_perception/launch/sensor_fusion.launch.py`、`setup.py` | 注册和启动匿名团队 observer | 最新七包构建通过 |
| `ros2_ws/src/heritage_tour_manager/heritage_tour_manager/team_observation.py`、`ros_tour_node.py`、`tour_manager.py` | 视觉/脚本来源隔离，UNKNOWN 安全等待；只允许确认当前区；修复安全暂停与自动团队暂停优先级 | `test_phase28_team_sources.py`、`test_phase28_control_races.py` 等；没有全系统动态掉队闭环 |
| `scripts/gazebo_visitor_team.py`、`scripts/start_phase25_system.sh` | 增加业务脚本/视觉策略显式选择；视觉模式关闭脚本 lost service client | 18项定向来源/视觉/API测试曾通过；完整543项最终通过 |
| `scripts/visualization_bridge.py` | 增加结构化感知、安全、相机、Scan、速度、cmd_vel、odom 新鲜度快照与 LaserScan 汇总；真值与视觉分栏；缺数据标 stale/invalid | API新鲜度/距离测试；实际启动后页面可见真实ROS数据；独立Nav2限速回读接口不存在 |
| `visualization/ros_hall/ros-live.js`、`tests/test_phase28_visualization_api.py` | 增加只读技术证据面板，显示实时感知与控制证据并标数据年龄/有效性，不将结构化数据伪装成相机视频 | `node --check` 与 `test-runtime.cjs` 退出0；本阶段页面现场观察见 WP13；截图未落盘、长时断流测试未做 |
| `scripts/export_phase28_replay.py`、`visualization/ros_hall/replay.html`、`replay.js`、`tests/test_phase28_replay.py`、`test_phase28_replay.cjs` | 只从manifest/归档/源文件校验一致的run导出 `RECORDED_ROS2`；播放器校验JSON/图片SHA，支持本地时间轴/播放/暂停/倍速/事件定位；不创建控制客户端 | Python+Node测试通过；真实WP01导出186事件、12 RGB、5深度元数据；坐标/速度数据未采集，浏览器本地文件预览未完成 |
| `scripts/archive_experiment.py`、`.gitignore` | 已结束run只读 tar 归档；对原始/归档生成哈希清单；不删除源文件；忽略新raw/archive目录 | 4项测试；WP01-04归档30/30文件校验通过，大小/sha见实验manifest；`git check-ignore` 确认docs和源码不被忽略 |
| `tests/test_phase28_person_tracker.py`、`test_phase28_team_observer.py`、`test_phase28_ros_shutdown.py`、`test_phase28_team_sources.py`、`test_phase28_control_races.py`、`test_phase28_archive.py`、`test_phase28_visualization_api.py`、`test_phase28_replay.py`、`test_phase28_replay.cjs`、`test_ros_team_observer.py` | 增加匿名跟踪、保守队伍、关闭路径、来源隔离、竞态、归档、面板与回放覆盖 | 最新完整目录：550 passed；ROS域与全部失败尝试见 [`tests/test_summary.json`](tests/test_summary.json) |
| `tests/test_tour_manager.py` | 增加视觉不确定/安全暂停优先级回归 | 完整543项通过 |
| `docs/phase2_8/**` | 计划执行证据、实验、最终报告、阻塞与验证矩阵 | 仅记录实测；未执行项目仍显式 NOT_RUN/HARDWARE_REQUIRED |

## 最终源状态

- HEAD：`bdf67d6dd1e09c503845af11e23a7f2f26b1a508`；tracked diff SHA256：`c70d5bbd52283ca328e758d5e5315bd7b1d27d14336dc18147fbc241c7a2a12f`（`git diff --binary`）。此哈希不包含 untracked 新文件；最终 untracked 文件和工作区状态按 `git status` 逐项交付。
- 最终构建与测试见 [`tests/test_summary.json`](tests/test_summary.json)。
