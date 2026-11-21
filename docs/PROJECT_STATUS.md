# 项目状态与阶段0审计

审计日期：2026-11-21。范围：按本轮任务完成阶段0工程审计及阶段1统一感知输入接口；不包含阶段2开发。

## 当前结论

ROS2 软件侧的感知接口、深度关联、激光前向距离、来源隔离和速度控制接入已实现并在本机通过构建与测试。Gazebo 的 RGB、深度、标定、TF 和激光传感器已运行核验；YOLOX ROS 节点也从 Gazebo RGB 图像收到帧并发布匿名人数。**这些结果不代表实体 temi 摄像头、底盘、速度调节或现场安全验证通过。** 目前没有实体 temi。

Git 基线：任务开始时 `main` 位于 `e4e86c8`，与 `origin/main` 同步且工作树干净。当前阶段改动尚未提交，也未推送。

## 模块状态

| 模块 | 现状 | 本轮核验与边界 |
|---|---|---|
| `temi_interfaces` | 5 个消息、2 个 Action、4 个 Service | 新增人员检测、检测数组、统一感知输入；ROS 接口生成和序列化测试通过 |
| `visitor_perception` | Mock、离线视频、相机人数模式；YOLOX ROS 图像适配、RGB/深度关联、感知融合 | 构建通过；纯 Python 与 ROS2 Topic 测试通过；Gazebo RGB 上实际加载 ONNX 并发布计数 0（空场仿真，不是行人检测效果评测） |
| `temi_speed_controller` | 保留原 JSON 输入，增加 `PerceptionInput` 输入 | 来源、有效性、时效、传感器标志和导航会话进入原策略；策略与集成测试通过。输出是软件目标/停车请求，不是底盘实测速度 |
| `temi_bridge` | ROS2 Gateway、Mock 与 WebSocket 后端已存在 | 本轮未改 Android/Gateway；完整 Python 回归包含既有 Mock、Gateway 和 WebSocket 用例 |
| `heritage_tour_manager` | 导览状态机、暂停/恢复、游客联动已存在 | 本轮未重写状态机；感知融合通过状态 Topic 解耦读取 |
| `heritage_knowledge`、`heritage_dashboard` | 已有离线知识库及本机监控 | ROS2 包随全工作空间构建；不属于本轮扩展范围 |
| Gazebo / Nav2 | 五区展厅、Nav2 启动配置、差速底盘、360° 激光已有；新增 Gazebo 深度/RGB 相机 | 本轮实测传感器 Topic 和 TF；没有把传感器检查等同为 Nav2 路线或 temi 运动验收 |
| Android Bridge | Kotlin/temi SDK 工程仍在仓库，未修改 | 本轮在线构建访问 Google Maven 超时；离线检查确认依赖缓存缺少 AGP `builder-8.0.0.jar`、`bundletool-1.13.2.jar`，因此本轮 Android JVM 测试和 APK 构建未完成 |

## 依赖与接口审计

- ROS2 工作空间有 7 个包：`temi_interfaces`、`temi_bridge`、`heritage_tour_manager`、`visitor_perception`、`heritage_knowledge`、`heritage_dashboard`、`temi_speed_controller`。
- Python/ROS 依赖包括 ROS2 Humble、`rclpy`、`std_msgs`、`sensor_msgs`、`std_srvs`、`cv_bridge`、NumPy、OpenCV、PyYAML；Linux WebSocket 依赖由项目 `.venv` 的 `requirements-websocket.txt` 固定 `websockets==16.1.1`。构建脚本为 `scripts/build_ros2.sh`，会在临时英文路径隔离 colcon 构建缓存。
- 感知输入与输出：游客稳定状态 `heritage/visitor/status`；YOLOX 原始检测 `heritage/visitor/person_detections/raw`；深度关联检测 `heritage/visitor/person_detections`；激光 `scan`；机器人、导航、导览和停车状态分别通过 `temi/robot_status`、`temi/navigation_status`、`heritage/tour/status`、`heritage/safety_stop` 输入。融合输出 `heritage/perception/fused` (`temi_interfaces/PerceptionInput`)。
- 速度控制仍接收旧的 `heritage/speed_control/input` JSON，并额外订阅 `heritage/perception/fused`，保持已有 ROS Topic/Service/WebSocket 合约兼容。
- Android 工具链曾在先前阶段安装并验收；本轮无法从 Google Maven 下载两个缺失构件。不是 Android 源码编译失败，也没有本轮 APK 通过结果。

## 构建与测试结果

| 类型 | 本轮结果 | 说明 |
|---|---|---|
| ROS2 构建 | 7 个包通过，最终构建 9.15 秒 | 含新增 ROS 接口与 Launch 文件；[构建日志](runs/phase0-phase1-20261121/ros2_build_complete.log) |
| 完整 Python/ROS2 回归 | **264 passed，0 failed，0 skipped，178.73 秒** | 修改后完整执行；[日志](runs/phase0-phase1-20261121/tests_complete.log) |
| 单元测试 | 通过，属于上述 264 项 | 覆盖融合/深度计算、速度策略、游客稳定状态和接口序列化等纯逻辑 |
| ROS2 感知集成 | 完整回归中的融合→速度策略用例通过；相机来源隔离 5 项通过 | Topic 测试输入为测试发布器，不是实体传感器 |
| Mock | 完整测试集中的 Mock 后端、Gateway、导览和速度策略用例通过 | 仿真/Mock 用例不能证明物理运动或制动距离 |
| Gazebo 传感器 | 激光与 RGB-D Topic、内参、光学 TF 实际收到 | 激光 288 个有效量程；深度图 320×240 `32FC1`，有效像素 44,123，中位数 2.960 m；[报告](runs/phase0-phase1-20261121/gazebo_sensors.json) |
| Gazebo 融合管线 | 端到端策略检查通过 | 真实 Gazebo scan/depth 加显式合成检测框、标定密度和机器人/安全/导览测试夹具；[报告](runs/phase0-phase1-20261121/gazebo_fusion.json)。该框不是 YOLOX 模型输出 |
| Gazebo RGB→YOLOX | 节点加载仓库 ONNX 模型并发布一帧人数 `0` | 相机观察为空场；证明 Topic、模型加载和推理发布路径可运行，不证明有人时精度；[实际输出](runs/phase0-phase1-20261121/yolox_gazebo_count.log) |
| Android | 未完成 | 在线 Maven 读取超时；离线依赖缺失证据：[日志](runs/phase0-phase1-20261121/android_build_offline.log) |
| 实体 temi | 未测试 | 没有实体设备、真实相机/激光驱动或物理停止记录 |

## 104 项与 237 项历史记录

- **104 项**来自 [2026-11-19 验收报告](acceptance_report.md)：Linux/ROS2 86 项 + Android JVM 18 项。其原始 Linux/JUnit、Android JUnit XML、构建与 Mock 路线证据仍保留在 `docs/acceptance/` 和 `docs/runs/`。
- **237 项**来自后续 [速度控制验证记录](speed_control_tests.md)，指 Linux/Python/ROS2 项目测试，不包括 Android JVM 的 18 项；文档记录耗时约 177.84 秒。该历史记录没有独立原始 pytest 日志或可追溯的提交 SHA，不能据此断言它是 104 项测试的简单扩充，也不能把二者相加。
- 本轮开始时在干净基线 `e4e86c8` 重新运行，记录 **237 passed**；本轮新接口和测试加入后最终为 **264 passed**。最终日志保留于本轮独立运行目录。历史 104、文档中的 237 和本轮 264 是不同时间/范围的测试快照，不作加总。

## 尚未完成与风险

1. 实体 temi RGB/深度/激光话题映射、相机内参与外参、人员距离精度、密度定义和展厅阈值均需真实设备标定。
2. `heritage/safety_stop` 当前没有本轮实现的生产者；融合节点会把停车状态缺失视作无效并要求安全停车，不能因此直接启用运动。
3. 完整融合→速度控制 Gazebo 报告中，人员框、密度及部分机器人状态是明确标注的测试夹具；真实 Gazebo 空场 YOLOX 只输出了 0 人。尚无“有模拟行人时由真实 YOLOX 检测到人并与深度配对”的实测。
4. 密度未标定时输出 warning，并按保守拥挤速度限速；人员距离、前向激光、定位、通信、停车确认、当前导航会话任一缺失或过期仍触发保守停车/等待确认。
5. temi SDK 调速调用、Android 运行时、机器人实测速度、制动距离、原生避障、真实停车确认和游客隐私现场流程都需设备和受控场地验证。
6. Android Maven 依赖可下载后，需重新执行 `./gradlew testDebugUnitTest assembleDebug`。本轮没有更新其测试或 APK。

依赖关系和数据流图见[阶段1报告](phase1_report.md)及[架构说明](architecture.md)。
