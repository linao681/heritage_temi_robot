# 基线审计（2026-11-22）

## Git 基线

- 分支：`main`
- HEAD：`057761908e386f3d0ba7a779d61b860a15debbda`
- 最近五次提交：
  - `0577619` Complete Phase 2.6 dynamic safety validation
  - `9e50dd2` Use grep in Phase 2.5 startup check
  - `026906f` Complete Phase 2.5 dynamic visitor validation
  - `59d41bf` Complete Stage 2 perception and speed control
  - `721ef72` Add unified perception fusion pipeline
- tracked 工作区改动：未发现。
- 本轮开始时已有未跟踪历史运行数据；未清理、未改写。另有用户提供的 `docs/phase2_7/implementation_plan.md`。

## 资源与进程

- `/tmp` 所在文件系统：196 GiB，48 GiB 可用。
- 内存：15 GiB 总量，约 3.0 GiB available，无 swap。
- 当前进程列表没有发现 Gazebo/Nav2 运行进程（PID 可见范围受执行环境限制）。
- `ss -ltn` 返回 `Cannot open netlink socket: Operation not permitted`；不能把空列表当作端口未占用证明。每轮需在启动前 bind 检查实际使用端口。
- 本轮所有仿真使用独立 `ROS_DOMAIN_ID` 与 `ROS_LOCALHOST_ONLY=1`；不处理或终止用户进程。未连接实体 temi。

## 历史 E03/E05/E06 审计摘要

- E03 阶段 2.6 的 `approaching-232-20261122-final` 有有效人员距离触发停车和新 UUID 恢复，但 STOP 后场景脚本冻结并移除人物；人物继续接近仍未验证，报告为 PASS WITH RISK。
- E05 最新阶段 2.6 运行有人员阈值停车证据，但人物在停车后冻结；距离间隙使用模型近似半径，非实体间隙测量。
- E06 历史恢复 CLEAR 晚于新任务约 0.090 s；旧事件先后本身不足以判定安全恢复，缺少决定时新鲜样本和窗口证据需要本轮检查。
- 完整原始记录位于 `docs/phase2_6_overnight/` 和旧运行目录，保留未改动。

## 本轮运行补充（2026-11-22）

- 最终全目录回归在隔离域 230 通过 469 项，0 failed、0 skipped，包含两份 WebSocket 测试；日志：`docs/phase2_7/tests/final-suite-20261122-111526/full_suite.log`，SHA256 `4f4b10738fa291857986b84caea8eb1c2fd3b63f0617203b69f8050298822015`。WebSocket 两文件另单独运行 19 passed，日志见 `tests/websocket-targeted-20261122-032308/`。
- ROS2 七包构建两次均成功。日志：`docs/phase2_7/tests/ros2_build.log`，最近一次追加结果为 7 packages finished。
- 复核时发现 ROS 域 226 已有 `visitor_perception`、YOLOX、Nav2 导航及定位节点；未使用或停止这些节点。域 230 在全目录测试前、相机实验后和 S01 清理后均通过空域预检。
- 全系统 S01 首次因运行器将一次 4 秒 ROS 预检超时当作致命错误而失败；用失败测试复现并修复后重跑，系统启动 240 秒预检仍未就绪。采样快照记录了融合安全输入无效、机器人未连接、速度控制输入无效；导航网关日志还记录 45 秒内未同时达到有效 odom、TF 和导航 action 的启动条件。之后在完整运行器等待期间中断本轮；manifest 保留 `FAIL`，未启动导览，也未触碰其他域。
- 独立相机 A/B/C/D Gazebo 传感器冒烟运行均收到 RGB、Depth 和两路 CameraInfo；每组保存了真实原始图像样本。A/D 实测安装高 0.55 m、光轴朝前；B 的光轴为 `[0.9848, 0, -0.1736]`，即向下约 10°；C 实测安装高 0.70 m。此项只验证相机几何和图像发布，不包含 YOLOX 人体检测、RGB-D 人体测距或动态人物对照。
- 相机采集器第一次尝试因 `/clock` QoS 不兼容而留下失败数据；修正采集器后重新采集。两批数据均保留并分别标明状态，没有覆盖失败记录。
- Gazebo/Nav2 全系统运行中可用内存最低约 0.7 GiB，无 swap；关闭本轮所属进程组后恢复到约 2.6 GiB。后续长轮次需继续串行并限制运行数量。
