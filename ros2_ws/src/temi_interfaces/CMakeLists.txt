cmake_minimum_required(VERSION 3.8)
project(temi_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(action_msgs REQUIRED)

# 使用 ROS2 官方 rosidl 工具生成 Python、C/C++ 等接口类型。
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/RobotStatus.msg"
  "msg/NavigationStatus.msg"
  "msg/PersonDetection.msg"
  "msg/PersonDetectionArray.msg"
  "msg/PerceptionInput.msg"
  "msg/SafetyStopStatus.msg"
  "action/NavigateTo.action"
  "action/Speak.action"
  "srv/StopRobot.srv"
  "srv/AskHeritage.srv"
  "srv/SubmitQuestion.srv"
  "srv/SetNavigationSpeed.srv"
  DEPENDENCIES std_msgs action_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
