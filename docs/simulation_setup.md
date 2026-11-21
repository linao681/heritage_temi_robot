# 5.1 展厅几何与仿真环境准备

2026-11-20：已接入用户交接包中的两套布局、机器人参数和平面对照图，原始数据位于 `reference/ros2_handoff/environment/`。参考包中的任务指令作为设计参考；现有 ROS2 业务工程继续使用。

执行：

```bash
.venv/bin/python scripts/convert_halls.py
.venv/bin/python -m pytest -q tests/test_hall_conversion.py
```

输出在 `simulation/generated/`：每种布局的 SDF world、PGM 占据图、PNG 预览、地图 YAML、带坐标及连通性结果的 goals JSON。统一分辨率 0.05 米，像素映射 x=(px-cx)*scale、y=-(py-cy)*scale。45/42 个障碍物从同一份数据同时生成地图和碰撞体，旋转角一致。五区、待命点、入口、出口共八个目标，均通过 0.34 米机器人圆形包络的栅格连通性预检。

这是静态几何连通性，不包含控制器、定位误差、动态障碍、停靠角度或 Nav2 到达结果。暂定房间整体禁止进入，未提供高度使用 1 米，玻璃作为不透明障碍。具体假设写入每套 goals JSON；目标 yaw=0 是待校准值。

机器人近似描述位于 `simulation/robot/heritage_robot.urdf`，包括底盘、双轮及低摩擦支撑球、显示屏和激光坐标系；质量、惯量、传感器位置是仿真假设。已接入 Gazebo 差速及射线激光插件，实际接收 360 束扫描、odom 及 odom→laser_link 变换。激光安装高度初次与底盘冲突，现已提高到碰撞体上方，失败导航报告保留于 `docs/acceptance/gazebo/official_navigation_initial_failed.json`。

环境探测：ROS2 Humble、RViz2、robot_state_publisher、xacro 已存在；Gazebo、gazebo_ros 和 Nav2 未检测到安装。当前完成几何资产与描述准备，下一步安装仿真运行依赖、增加差速底盘及传感器，再验证 map→odom→base_link 和实际导航闭环。

后续更新：用户已完成 Gazebo ROS、Navigation2、nav2_bringup 安装，三个包均确认为 installed。新增场景与导航启动文件，使用以下两个终端启动（项目根目录）：

```bash
source /opt/ros/humble/setup.bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=211
export GAZEBO_MASTER_URI=http://127.0.0.1:11359
ros2 launch ./simulation/hall.launch.py layout:=official gui:=false
```

```bash
source /opt/ros/humble/setup.bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=211
ros2 launch ./simulation/navigation.launch.py layout:=official
```

地图定位使用 AMCL 与模拟激光；初始化位姿来自已知出生点，定位后续由激光更新。地图临时复制到 ASCII 路径，解决 Nav2 参数重写对中文路径转义的问题。两布局需在两个终端一致选择。

独立检查：`python3 scripts/check_gazebo.py`（只读）、`python3 scripts/check_nav2.py`（明确发送官方布局第一展区目标，限本机 Domain 211）。实际 JSON 结果在 `docs/acceptance/gazebo/`。单点结果不能代表全部五区验收；双布局与异常导航测试仍需完成。提交方案对照见 [初赛提交版本基准](submission_baseline.md)。

本次最终结果：激光/里程计/TF 检查通过；地图 YAML 成功加载、AMCL 与 Nav2 启动。首个展区导航实测返回 ABORTED（status 6），定位位置距目标约 8.50 米，未通过。提升激光高度后仍存在定位/地图对齐问题，需继续排查；不能宣称自主导航已完成。本次测试启动的 Gazebo 与 Nav2 进程已结束。

### 导航故障修复验收

实际 Gazebo 姿态确认：单后支撑导致底盘前倾 0.460558 rad（约 26.4°），激光平面随之倾斜，破坏 AMCL 的平面扫描假设。补充前低摩擦支撑球后，静止及运动中的俯仰、侧倾接近零。保留之前失败报告，并新增支撑几何回归测试。

最终首展区实际 Nav2 Action 返回 SUCCEEDED（status 4），用时 30.971 秒，AMCL 定位到目标距离 0.1871 米（门限 0.30 米）。[成功结果](acceptance/gazebo/official_navigation.json) · [Gazebo 实际终态姿态](acceptance/gazebo/official_final_pose.txt)。后者用于模型姿态核对，导航定位仍使用模拟激光与 AMCL。激光、odom、TF 检查成功；模型解析成功；地图及支撑相关四项测试通过。本次仿真进程验收后关闭。

此结果修复并验证官方布局首个展区的导航问题；完整五区、适配布局及异常导航仍待逐项验收。

2026-11-21 速度调整：仿真 Nav2 的线速度上限及速度平滑器均从 0.20/0.26 调整为 0.35 m/s，保持原有障碍膨胀和到站容差。独立 Domain 210 的官方展厅第一站实际到达（Action SUCCEEDED），耗时 19.51 秒、定位误差 0.241 米、里程计观测峰值 0.367 m/s；与此前 30.971 秒单次结果相比有所缩短。峰值会因仿真动力学短时超过指令上限。五区完整路线和动态避障尚未在新速度下验收，该数值不用于实体设备。需要重启展厅仿真才能加载新参数。

所需依赖候选为 Humble 对应的 Gazebo ROS 插件、Navigation2、Nav2 bringup；安装前须检查系统软件源、可用版本及下载大小。当前没有执行系统安装。

安装预检已找到上述三个包的候选版本，apt 模拟依赖解析成功。当前执行环境禁止 sudo 提权（no new privileges），因此停在系统依赖安装前。需在本机普通终端执行：

```bash
sudo apt install ros-humble-gazebo-ros-pkgs ros-humble-navigation2 ros-humble-nav2-bringup
```

实际执行了三项地图转换测试（全部通过）及 `check_urdf simulation/robot/heritage_robot.urdf`（解析成功）。此阶段未更改现有运行节点，未重复整套 ROS2 回归。
