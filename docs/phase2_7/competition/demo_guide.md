# 阶段 2.7 展示操作指南

## 新增入口到出口三人完整演示

```bash
cd /home/linao/heritage_workspace/heritage_temi_robot
bash scripts/start_full_visitor_demo.sh
```

打开 `http://127.0.0.1:8098/`。脚本完成构建与全系统预检，然后自动演示入口三人接待、同意导览、五区讲解、队尾放慢、停车集合、模拟操作员确认继续、知识问答和出口告别。可在网页点击“开启浏览器演示语音”；无语音支持时仍显示字幕。自动演示期间不要重复点击流程控制按钮。

一次完整实跑为 `experiments/visitor-full-20261122-202055/`，504.840 秒、7/7 目标；原始报告 PASS，派生验证 PASS_WITH_RISK。三个游客均有 Gazebo 实际运动记录；游客行为和操作员确认是脚本模拟，非视觉团队身份跟踪或实体 temi 认证。最终 97 项定向回归通过。

演示完成后保留出口画面；按 Ctrl+C 关闭本轮组件。完整证据与限制见 `../visitor_team_implementation.md`。下方保留先前阶段的展示入口和历史证据说明。

## 本轮可展示内容

- Three.js 官方展厅三维页面与五区布局。
- 两轮真实 Gazebo 动态导览记录：人物接近、机器人安全停车、人物持留并侧向离开、以新 UUID 继续原展区，随后完成五区和出口路线。
- 主运行的阶段、距离、速度曲线，以及停车和恢复原始记录。展示时明确是**同一配置的两轮仿真**，0.3 m/s 规定标定窗口未通过。
- A–D 相机 RGB/Depth/CameraInfo/TF 冒烟结果，明确不含人体检测性能对照。

不能展示为本阶段已通过的内容：原 S01 1.4 m 终点（该轮风险中止）、E02 多人数限速、E04 A/B/C 横穿、E07 三人掉队、七轮稳定性、60 s 性能比较、RECORDED ROS 回放或实体 temi。问答播报为 Mock Speak Action，没有真实音频。

## 启动展厅页面

在项目根目录运行：

```bash
cd /home/linao/heritage_workspace/heritage_temi_robot
source /opt/ros/humble/setup.bash
bash scripts/start_visualization.sh official
```

浏览器访问 `http://127.0.0.1:8088/`。页面是当前项目的仿真展示入口；连接状态不新鲜或 ROS 未连接时，应按离线/过期显示，不把内置演示视觉说成实时传感结果。不要重复启动同一实例，也不要结束非本轮启动的用户进程。

## 展示真实运行证据

最新主运行目录：
`docs/phase2_7/experiments/S01-SAFE-ENDPOINT/20261122T101824Z-S01-SAFE-ENDPOINT-r001/`

第一轮对照记录：
`docs/phase2_7/experiments/S01-SAFE-ENDPOINT/20261122T044704Z-S01-SAFE-ENDPOINT-r001/`

建议依次展示：

1. `evidence_summary.json`：配置、路线终态、关键距离/耗时、速度条件与限制。
2. `tour/scenario/truth.json`：人物各阶段真值、运动路径、几何代理和接触反馈缺失。
3. `analysis/distance_speed.svg` 与 `analysis/phase_timeline.csv`：本轮曲线和阶段。
4. `analysis/recovery_validation.json`：旧 session 停车、同目标新 session 恢复及原始数据哈希。
5. `docs/phase2_7/validation_matrix.md`：其余 NOT_RUN/FAIL 的分项状态。

## 面向评审的讲解顺序

1. 说明 ROS2 Humble/Nav2/Gazebo 软件系统，无实体 temi。
2. 展示五区场景与完整路线，说明这是两轮同配置安全终点变体，不覆盖原 S01 的风险失败。
3. 播放真实事件时间线，展示距离停车、人物仍移动、几何间隙代理及新 UUID 恢复。
4. 主动说明 0.3 m/s 干扰前标定未达标、接触反馈为空、Mock Speak Action 无真实声音。
5. 展示 487 项自动化测试和七包构建，再区分软件回归与未执行的 E02/E04/E07、性能、回放和硬件验收。

只引用 [`evidence_index.md`](evidence_index.md) 列出的记录。禁止用静态动画、历史阶段记录或跨轮拼接弥补缺失实验。
