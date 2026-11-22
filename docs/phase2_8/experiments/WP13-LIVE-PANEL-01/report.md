# WP13-LIVE-PANEL-01：实时技术证据面板观察

## 结果

**PASS_WITH_RISK：**官方展厅的整套 ROS2/Gazebo 软件启动通过预检，浏览器实际加载实时页面并显示结构化数据。没有发送导航目标，机器人保持待命；启动进程退出后，专用 ROS Domain 231 返回空图。

## 运行配置

- 时间：2026-11-22 23:22:59 起，Asia/Shanghai
- ROS Domain 231，Gazebo Master 11373，网页 `http://127.0.0.1:8091/`
- 团队策略：`vision_conservative`
- 预检：所有启动检查通过（见 manifest 与 `/tmp/heritage-phase28-wp13-system/preflight.json`）。
- 入口：`bash scripts/start_phase25_system.sh 231 11373 8091`
- 未发送路线/导航目标。预检与网页均显示 robot stationary / Tour idle。

## 浏览器中实际观察到

- RGB 与 Depth CameraInfo 均为 320×240，`depth_camera_optical_frame`；数据新鲜度在数十毫秒量级。
- YOLOX 匿名跟踪当前 0 人；视觉团队状态为 `UNKNOWN`，0/0，人工确认 required，原因是当前视场不能确认团队人数。
- Gazebo 脚本真值在该观察时刻没有新鲜数据；面板与视觉观测分开显示。
- 感知融合有效；LaserScan 最近障碍约 3.05 m；odom 实际线速度约 0.00 m/s。
- Tour/速度状态为 IDLE，没有导航任务；`cmd_vel` 无数据/过期；Nav2 独立限速回读明确标注当前接口未提供。
- 页面说明当前只显示结构化数据，没有相机视频。

## 限制

本观察验证的是 API 与页面对真实 ROS 快照的呈现，不是视觉检测有人或导览效果测试。未执行 60 秒断源/重连、相机画面接入、截图/录屏归档、ROS 事件时间线重放或控制权限攻击测试。浏览器状态曾以工具截图核查，但图像未保存到项目文件；不能据此勾选 WP13 的画面留档与 60 秒验收项。完整 WP13 状态仍为 PASS_WITH_RISK。

进程 PID、配置和源码 SHA256 见 [`manifest.json`](manifest.json)。启动日志保留在本机 `/tmp/heritage-phase28-wp13-system/`。
