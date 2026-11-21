# 提交版五区连续导航

路线：非遗概览、传统工艺、代表作品、传承故事、互动体验，最后到出口。使用同一运行中的 Gazebo、AMCL、Nav2，逐站发送 NavigateToPose；目标来自对应布局生成文件。

每站验收：Action SUCCEEDED，AMCL 定位与目标距离不超过 0.30 米，且新鲜 odom 线速度绝对值小于 0.02 m/s、角速度绝对值小于 0.05 rad/s。任一站失败即中止，不跳过、不伪造完成。此位置误差属于定位估计误差，不能替代物理地面真值或实机停靠验收。

在项目根目录分别运行三个终端：

```bash
source /opt/ros/humble/setup.bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=211
export GAZEBO_MASTER_URI=http://127.0.0.1:11359
ros2 launch ./simulation/hall.launch.py layout:=official
```

```bash
source /opt/ros/humble/setup.bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=211
ros2 launch ./simulation/navigation.launch.py layout:=official
```

```bash
source /opt/ros/humble/setup.bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=211
python3 scripts/check_nav2.py --layout official --full-tour
```

每站实际输出 JSON，结束写入 `docs/acceptance/gazebo/official_full_tour.json`；单点检查仍可不带 `--full-tour` 使用。另一布局可在三个终端都选择 adaptive。导航验收只覆盖运动闭环，讲解、问答及游客同意仍由原有导览模块负责，尚未连接此次 Gazebo 路线。

## 官方布局实测

六个目标全部通过、逐站确认静止，总耗时 557.628 秒。五区依次定位误差为 0.225、0.203、0.229、0.246、0.228 米；出口 0.239 米。互动区路段耗时 219.463 秒，期间发生控制器进展不足并触发恢复，虽最终成功，仍需优化。

首次运行前两区成功、第三站失败；检查发现定位与模拟真实位置偏离，调整仿真 AMCL 里程计噪声参数后重新完整执行通过。这是针对当前仿真的参数，并非实机标定。

[完整报告](acceptance/gazebo/official_full_tour.json) · [首次失败报告](acceptance/gazebo/official_full_tour_initial_failed.json) · [导航日志](acceptance/five_zone/nav2.log) · [回归测试日志](acceptance/five_zone/tests.log)。完整 Linux 回归 209 项通过；回归运行期间随后调整了仅供仿真使用的 AMCL 噪声参数，该最终参数通过本次完整导航实测。
