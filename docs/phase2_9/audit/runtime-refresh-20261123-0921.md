# 2026-11-23 09:21 CST 运行环境刷新检查

代码版本：`phase2_9-work`，HEAD `24c14231de61840a11c5462805df0cd6160af84d`。

## WP01 重型仿真门

状态：`BLOCKED`（有其他完整 ROS/Gazebo 系统在运行；不并发启动第二套仿真）。

- 可用内存：6.8 GiB；无 swap。
- 磁盘可用：46 GiB。
- 1/5/15 分钟负载：12.46/13.26/14.98，16 CPU；本次检查未超过项目负载门槛。
- 本轮专用 TCP 端口 11441、8141 均成功绑定 `127.0.0.1` 后释放。
- ROS 域逐一探测：232、231、230、229、227、226、225 为空；228 返回现存 Nav2/Gazebo/感知/导览节点（含 `map_server`、`controller_server`、`gazebo`、`depth_camera_ros`、`heritage_tour_manager` 等）。
- 未向域 228 发布任何命令，没有停止任何现有节点；也未启动本轮 Gazebo。域 232 虽为空，但由于另一套完整系统仍在线且没有 swap，本轮不启动并行重型场景。
- 较早的 5.098 GiB 内存不足和端口权限失败证据仍保存在 `experiments/WP01-full-tour/visitor-full-20261123-020925/`，未覆盖。

## 可安全完成的独立集成测试

1. 命令：`source /opt/ros/humble/setup.bash && source ros2_ws/install/setup.bash && .venv/bin/python -m pytest -q tests/test_websocket_backend.py`。本机模拟客户端与 loopback 服务进行真实握手，`19 passed in 1.97s`。这不代表 Android 实机或 temi SDK 验收。
2. 命令：`ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=232 timeout 45s .venv/bin/python -m pytest -q tests/test_phase28_team_sources.py::test_vision_mode_ignores_scripted_team_status_in_ros_node`（运行前加载 ROS Humble 与工作区）。结果 `1 passed in 0.32s`。此测试仅创建短时 ROS 节点，确认 `vision_conservative` 忽略脚本游客真值；不代表相机视觉或 Gazebo动态跟踪验收。

## 结论

内存及 loopback 端口条件已恢复，空闲 ROS 域也可被确认；WP01 仍需等现有域 228 的系统结束后再串行启动。当前阶段 2.9 Gazebo 导航 run 数仍为 0。

## 09:26 CST：运行器最终门复核

启动命令为官方布局、`business_script`、3名脚本游客、ROS域232、Gazebo端口11441、Web端口8141，超时1200秒。域232再次报告为空。运行器在创建仿真系统前完成资源预检并返回`BLOCKED`：`available_memory_gib=6.76297`、`free_disk_gib=45.29858`、`load_per_cpu=0.8825`、端口检查通过，但系统进程检查检测到`gzserver`。报告`events=[]`、`elapsed_sec=0.0195`，说明本轮没有启动任何ROS/Gazebo/Web组件。完整报告、manifest和system.log：`experiments/WP01-full-tour/visitor-full-20261123-092632/`。没有终止或操作检测到的进程。

随后ROS图复核：域232为空；域228仍有Nav2和项目ROS节点在线。


## 09:29 CST：失败后只读复查

等待后于09:29:52再次检查，`gzserver`仍在线；可用内存6.9GiB、无swap，1分钟load 17.57/16 CPU = 1.10/CPU，高于运行器1.0门槛。未启动或停止任何进程。由于现有Gazebo未退出且负载超限，不再重试WP01。
