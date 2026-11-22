# 代码变更记录

本轮工作树修改尚未提交。没有自动提交或推送。

| 范围 | 修改 | 验证 |
|---|---|---|
| `temi_speed_controller/speed_policy.py` | 加入单调时钟人员测距趋势、接近速度上限、动态停车距离、保守 odom 速度回退及停车确认锁存；将有效人员观测与稳定游客人数计数解耦；把人员距离硬停、障碍物硬停及双源硬停分开记录；根据 E05 近场丢测与制动记录将人员停车下限设为保守开发默认 1.3 m，并同步纯 Python 默认与 ROS 参数 | 七包 ROS2 构建；76 项速度控制/场景证据定向测试；第六轮 E05 隔离 Gazebo 闭环 |
| `temi_speed_controller/speed_controller_node.py`、`config/speed_config.yaml`、`package.xml` | 读取新鲜 odom，发布动态停止距离、接近速度、来源和独立的 `visitor_count_valid`；按传感器来源和分通道有效性判定运动输入；新增 `nav_msgs` 依赖 | ROS2 七包构建、速度/融合定向测试 |
| `visitor_perception/perception_fusion.py` | `sample_age_sec` 只反映周期更新的运动与安全输入；稳定人数和 Nav2 状态转移事件不作为传感器心跳，仍分别影响群组/导航状态与总体有效性 | `tests/test_perception_fusion.py` 边界回归、七包 ROS2 构建、E05 Domain 232 全路线与动态场景 |
| `scripts/replay_e03_safety_policy.py`、`docs/phase2_6_overnight/stopping_distance.csv` | 对既有 E03 输入轨迹运行策略反事实回放并保留逐样本决策 | 回放脚本输出 23 行；不作为 Gazebo 闭环实测 |
| `scripts/analyze_camera_coverage.py`、`camera_coverage.md`、`camera_coverage.svg` | 从 URDF 计算相机水平/垂直视场、地面/头顶几何范围并对比假设方案 | 工具运行、SVG XML 解析；没有视觉检测回归 |
| `scripts/spawn_people_scenario.py` | 加入模型状态新鲜度和 `GetEntityState` 回读、移动后目标坐标确认、活动导航 UUID/目标/odom 门控、人物移动绝对单调时间戳 | E04/E06 Gazebo 真值已核查；`tests/test_gazebo_people_scenario.py` |
| `scripts/run_phase25_clean_tour.py` | 增加 crossing/approaching/leaving 运行参数；E06 检查近人距离、旧 UUID 停车确认、恢复原目标新 UUID 和恢复窗口 CLEAR；动态证据按人员减速、人员停车、障碍响应、双源停车和模糊停车分别归类，不把障碍停车当成人员停车 | E04/E06/E05 原始数据复核；动态场景和事件捕获定向用例通过 |
| `scripts/record_phase2_topics.py` | 记录动态停车距离、接近速度、odom 速度；新增稳定访客计数有效位、人员观测/测距有效位、原始检测状态和速度输入有效位。`person_observation_state` 现在只来自融合消息 | 记录器字段与人员/访客有效性分离测试 |
| `tests/test_gazebo_people_scenario.py`、`tests/test_phase2_recording_analysis.py`、`tests/test_perception_ros_integration.py`、`tests/test_speed_controller.py` | 覆盖动态场景联动证据、fail-closed 风险归类、CLEAR 次序、新旧恢复 UUID、测距/访客计数分离、CSV 字段以及人员/障碍硬停归因 | 控制器与场景证据定向回归 74 passed；最终全量结果见 `validation_matrix.md` |

此外，已有 `start_phase25_system.sh` 在当前基线使用 `grep` 检查 readiness，兼容未安装 `rg` 的终端 PATH；该修复不属于本轮未提交代码。
