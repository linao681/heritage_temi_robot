# ROS 2 开发实施与验收

## 一、工程边界

Ubuntu 22.04 + ROS 2 Humble；以已有安装环境为准检查 Gazebo、Nav2、RViz、Python、colcon/rosdep。先复用现有 Linux `heritage_temi_robot` 工作区（如果存在），避免重建或覆盖。Gazebo 版本与桥接插件通过环境检查确定。不要将 temi Android SDK 误当成 Linux ROS 驱动。

## 二、目标架构（建议）

| 模块 | 职责 |
|---|---|
| heritage_description | URDF/Xacro、底盘、碰撞体、传感器坐标系 |
| heritage_simulation | 官方展厅和适配展厅 Gazebo 场景、游客及异常注入 |
| heritage_navigation | Nav2、地图/定位、规划与控制、停靠 |
| heritage_perception | 模拟传感器与游客感知事件，明确数据来源 |
| heritage_tour | 导览任务状态机、自由参观、分层讲解、事件恢复 |
| heritage_interfaces | 跨模块消息、服务或 action |
| heritage_temi_adapter | 模拟后端与未来 Android SDK 后端间的抽象接口 |
| heritage_bringup | 一键启动、参数配置及 RViz 展示 |

## 三、地图转换

- `layouts.json` 内 `PLAN` 为像素基准与比例，`PLAN_W`、`PLAN_D` 单位为米；`PLAN_ZONES` 为五区多边形、目标及展品像素坐标；`MAP_FIXTURES` 为带尺寸、方向的障碍物；`PLAN_WAIT`、`PLAN_PORTALS`、`PLAN_APPROACH` 对应待命点、入口出口、参考路线。
- 采用 ROS map x = (px-center_x)*scale，y = -(py-center_y)*scale，即网页 x→ROS x、网页 z→ROS -y。浏览器 fixture `angle` 可用于此映射的平面旋转；对每个旋转展柜和分区墙进行可视化核对。
- 必须由同一份布局生成 SDF/world、占据地图与停靠目标；不可把旧 `scene-plan-data.json` 当最新版，也不要把网页路径直接作为真机轨迹。检查入口出口开口、中心柱、墙玻璃柜、转弯通道、目标点的可达性。Gazebo 碰撞高度/激光安装高度必须一致。未给出的高度标记为假设。
- 机器人外观来源与运动参数见 `robot_model.json`，机器人尺寸、速度、传感器配置均需核实或在未来实机中标定。导航仿真禁止直接使用网页的 ground truth 作为最终定位证据。

## 四、实现顺序

1. P0：环境诊断、两种地图、机器人模型；`map→odom→base_link` 正确，模拟激光与里程计可用，RViz 显示完整。
2. P0：Nav2 在静态场景中自主抵达五展区、互动点、出口并完成停靠。用实际导航反馈而非预设动画判断到达。
3. P0：迎宾、人数估计、散客/小团体确认、五展区导览、讲解完成后推进、自由参观选择、出口结束。离散事件可先用 mock，但应标记来源。
4. P1：动态行人阻挡、持续驻足绕行、队伍掉队、听不清时停车确认、低电量、定位异常与人工协同；异常恢复后任务不重复、不丢失。可测模拟故障不能冒充真实识别。
5. P1：基于来源明确的知识内容做儿童/大众/深度讲解、有限问答；未知问题转人工。再加入 ROS 与 SDK 共同认可的服务接口。
6. P2：批量场景测试、录制 Gazebo+RViz+状态监控联合演示、输出报告与运行指令。

## 五、评估证据

为两种布局分别运行单人、小团体、自由参观及混合异常场景；重复试验并保存随机种子。记录目标到达率、停靠位置/角度误差、最小人机间距、碰撞、规划失败、绕行和等待次数、异常恢复率、任务完成耗时；阈值在测试前明确，未通过项必须保留。数据来自 ROS 2 日志、rosbag 或结构化指标，不能复制网页测试结果充当 ROS 2 成绩。安全间距和速度为仿真设计值，实机需独立验收。

## 六、temi 真机迁移

统一 `navigate_to`, `stop`, `speak`, `get_pose`, `get_battery`, `get_status` 等逻辑接口，通过 mock 后端先跑通。实机使用 Android/Kotlin + 官方 temi SDK，实际调用能力、事件监听及网络通信方式逐项查阅官方文档，不编造 API。ROS 2 Nav2 仿真验证和 temi 自带导航是不同后端；实机部署前重新测绘、标定和测试，不直接搬运仿真坐标或控制命令。
