# Temi ROS2 Interface Implementation Plan

**Goal:** 使用 ROS2 Humble rosidl 生成两个 Message、两个 Action 和一个 Service，验证 Python 导入及通信类型支持。

**Architecture:** `temi_interfaces` 是唯一接口定义包，通过 `ament_cmake` 和 `rosidl_default_generators` 构建。不包含业务功能，也不依赖 temi SDK。

**Tech Stack:** ROS2 Humble、ament_cmake、rosidl、std_msgs、action_msgs、rclpy、pytest。

## Global Constraints

- 使用现有 ROS2 Humble 和 Python 3.10，不升级依赖、不修改系统环境。
- 接口字段按用户需求原样保留，坐标与角度使用双精度，电量与超时使用明确的数值类型。
- Action 文件顺序依次为 Goal、Result、Feedback，符合 ROS2 规范。
- 节点测试只使用隔离 ROS Domain 和本地通信，不连接实体 temi。

## Task 1: 自定义接口与验收测试

**Files:**

- `ros2_ws/src/temi_interfaces/package.xml`
- `ros2_ws/src/temi_interfaces/CMakeLists.txt`
- `ros2_ws/src/temi_interfaces/msg/RobotStatus.msg`
- `ros2_ws/src/temi_interfaces/msg/NavigationStatus.msg`
- `ros2_ws/src/temi_interfaces/action/NavigateTo.action`
- `ros2_ws/src/temi_interfaces/action/Speak.action`
- `ros2_ws/src/temi_interfaces/srv/StopRobot.srv`
- `tests/test_temi_interfaces.py`

**Produces:** `temi_interfaces.msg.{RobotStatus,NavigationStatus}`、`temi_interfaces.action.{NavigateTo,Speak}`、`temi_interfaces.srv.StopRobot`。

- [x] 先编写接口契约、序列化回环及 rclpy 节点创建测试。
- [x] 未构建接口时运行 `python3 -m pytest -q tests/test_temi_interfaces.py -k robot_status`，实际因未生成 `temi_interfaces` Python 模块而失败。
- [x] 添加五个接口定义及 ament_cmake 包描述，`std_msgs/Header` 用于带时间戳的状态消息，`rosidl_generate_interfaces()` 声明五个接口文件。
- [x] 常规 colcon 构建因上游 rosidl 中文构建路径解析失败；添加 `scripts/build_ros2.sh` 使用纯英文独立构建缓存，实际得到 `1 package finished`。
- [x] `source ros2_ws/install/setup.bash` 后运行 `python3 -m pytest -q tests/test_temi_interfaces.py`，实际 6 项全部通过。
- [x] 使用 `ros2 interface list`、`ros2 interface show` 核对生成类型；另实际运行两个独立进程 `ros2 topic pub` / `ros2 topic echo`，收到预期消息。记录真实构建和测试日志。

项目尚无独立 Git 仓库，不创建提交或修改第三方仓库。
