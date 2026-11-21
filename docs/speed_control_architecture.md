# 智能动态速度控制

## 架构与边界

速度策略在 `temi_speed_controller` 内独立运行，按游客距离、人群密度、障碍距离、团队状态、导航状态、定位/通信状态和讲解状态输出目标速度或停车请求。策略不控制底层电机，也不替换 temi 原生避障。

```text
融合感知输入 (JSON, ROS2)
        ↓
SpeedController 规则策略、限速、滞回、变化率限制
        ├── temi/set_navigation_speed → 当前导航会话调速
        │       ├── Gazebo: Nav2 controller + velocity smoother
        │       └── temi: Android WebSocket → setCurrentGoToSpeed()
        └── heritage/tour/pause → PAUSED 确认 → 条件稳定 → resume
                    ↓
        heritage/speed_control/status → 只读网页与事件日志
```

目标速度是导航软件请求，不是机器人实测速度。Mock 模式可显示模型计算的“模拟速度”；实体模式将此字段留空。目前 Android SDK 速度监听只报告是否运动，项目没有可校准的实体线速度传感器，因此不显示成实测数值。

## 当前 ROS 接口

| 类型 | 名称 | 说明 |
|---|---|---|
| Topic 输入 | `heritage/speed_control/input` (`std_msgs/String`) | 感知汇总 JSON：`sample_age_sec`、`nearest_person_m`、`crowd_density`、`obstacle_distance_m`、`group_state`、`navigating`、`explaining`、`navigation_error`、`safety_stop`、`position_valid`、`communication_valid`、`navigation_session_id`。每个输入必须持续刷新；距离单位 m，密度范围 0–1，`sample_age_sec` 必填并代表传感数据采集后经过的时间。 |
| Topic 输入 | `temi/navigation_status` (`temi_interfaces/NavigationStatus`) | 用于模拟场景获取活动导航会话 ID。生产融合节点必须提供与当前 Action UUID 一致的 `navigation_session_id`。 |
| Topic 输入 | `heritage/tour/status` (`std_msgs/String`) | `PAUSED` 是暂停状态机的确认；恢复由 TourManager 的 `resume` 服务执行。 |
| Service | `temi/set_navigation_speed` (`temi_interfaces/SetNavigationSpeed`) | 要求 command ID、当前导航会话 UUID、0.3–0.8 m/s 目标值和原因。旧会话会被网关和 Android 再次拒绝。 |
| Service | `temi/stop` (`temi_interfaces/StopRobot`) | 无 TourManager 时的停止后备。该操作可能终止当前导航任务。 |
| Service | `heritage/tour/pause`, `heritage/tour/resume` (`std_srvs/Trigger`) | 首选安全暂停/恢复方式；等待 `PAUSED` 和新导航会话，恢复后以 0.3 m/s 起步。 |
| Service | `heritage/speed_control/reset_error` (`std_srvs/Trigger`) | 清除锁存的 ERROR。只应在定位、通信或 SDK 故障原因处理后人工调用。 |
| Topic 输出 | `heritage/speed_control/status` (`std_msgs/String`) | 状态、目标速度、原因、感知值、停止确认、会话 ID，以及明确标记的模拟速度。 |
| Topic 输出 | `heritage/speed_control/commands` (`std_msgs/String`) | 调速命令完成/失败、软件目标和 SDK 返回码。`-2` 表示模拟后端，不是 SDK 返回码。 |

示例输入：

```json
{"sample_age_sec":0.0,"nearest_person_m":3.2,"crowd_density":0.1,"obstacle_distance_m":3.0,"group_state":"following","navigating":true,"explaining":false,"navigation_error":false,"safety_stop":false,"position_valid":true,"communication_valid":true,"navigation_session_id":"<当前导航 UUID>"}
```

## 状态与策略

状态：`IDLE`、`NORMAL`、`SLOW`、`STOPPING`、`STOPPED`、`WAITING`、`RECOVERING`、`ERROR`。危险条件不会把速度设为 0，而是请求 pause/stop 并等待确认。感知超时或无效值按保守停车处理；通信、定位、SDK 或停止失败进入锁存 `ERROR`，需显式人工复位。人工停止也锁存错误。

默认速度上限为 0.8 m/s，起步正常速度 0.5 m/s，空旷区 0.7 m/s，人群密集 0.3 m/s；临近游客/障碍按距离插值减速。距离和时间阈值仅为开发调试初值，不是安全标准，必须在真实地图和受控场地标定。减速/加速变化率和指令间隔可在 `ros2_ws/src/temi_speed_controller/config/speed_config.yaml` 配置。

游客组状态 `lost` 连续达到配置时长会暂停。恢复状态持续满足滞回距离和恢复时间后请求 TourManager 恢复，恢复后必须观察到新的活动导航 UUID，再向新会话发低速命令。SDK 不支持暂停时，后备 `stopMovement` 会结束导航，机器人不会在原 SDK GoTo 中自动续跑；需要导览管理器接受恢复并发起新的导航段。

## SDK 兼容性

项目依赖为 temi SDK `1.139.0`。官方仓库在本工作区固定版本的源码中定义 `Robot.setCurrentGoToSpeed(float)`，注释范围 0.3–1.5 m/s，返回 200、0、400 或 408；并注明该 API 仅适用于当前由本应用启动的 GoTo。SDK 示例也先 `goTo()` 再设置当前 GoTo 速度。[官方 SDK 仓库](https://github.com/robotemi/sdk)

本项目额外施加 0.3–0.8 m/s 软件限速。返回码只有 200 才视作成功；其他值不会回退到反复 `goTo()` 或将 0 当停车，而是报错并请求暂停。Launcher 是否实现该接口、SDK/Launcher 版本兼容、实际线速度和制动距离目前都未在实体机器人验证。

## 启动与 Mock 演示

先构建：

```bash
cd ~/heritage_workspace/heritage_temi_robot
bash scripts/build_ros2.sh
bash scripts/build_android_bridge.sh
```

启动 Gazebo 五区模拟和速度控制节点（仿真实际速度模型明确标记为模拟）：

```bash
bash scripts/start_visualization.sh official
bash scripts/start_submission_tour.sh official
```

导览需要按现有流程启动、接受游客同意后才会移动。Mock 调试也可运行 `bash scripts/start_mock_system.sh --headless --domain 219`，它会启动 Mock 机器人和速度控制节点。另开终端发布明确标记的模拟感知值：

```bash
cd ~/heritage_workspace/heritage_temi_robot
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=211
python3 scripts/mock_speed_scenarios.py --scenario cycle --seconds-per-stage 5
```

也可一条命令运行完整 Mock 五区路线并注入调速场景（会触发模拟 pause/resume）：

```bash
bash scripts/start_mock_system.sh --headless --demo --domain 219 --speed-scenarios
```

本轮完整运行记录位于 `docs/runs/mock-system-20261121-130953-893828/report.json`。可观察网页顶部速度状态、目标速度、模拟速度和调速原因，也可查看：

```bash
ros2 topic echo /heritage/speed_control/status
ros2 topic echo /heritage/speed_control/commands
```

模拟输入包括空旷、人群、障碍、危险距离、掉队和清空恢复。它们不是视觉检测输出，不能作为实机验证证据。

## 测试

- `tests/test_speed_controller.py`：速度区间、拥挤/接近、障碍停车、掉队计时、感知超时、讲解停车、错误锁存、节流和恢复。
- `tests/test_mock_backend.py`：Mock 活动任务调速与过期导航会话拒绝。
- `tests/test_websocket_backend.py`：速度命令字段及软件限速校验。
- Android `BridgeCoordinatorTest`：当前导航会话才允许调速，SDK 400/0 等非 200 结果作为失败处理；`TemiSpeedManager` 校验 0.3–0.8 范围。

## 实机验证清单

1. 确认 Android 设备/temi Launcher、temi SDK 版本及支持动态 GoTo 速度接口。
2. 先验证 Android WebSocket 握手和导航会话 UUID，再在空旷区域、有人监护下以 0.3 m/s 测试调速。
3. 用 temi SDK 反馈或独立测量设备记录实际速度，核对 SDK 目标速度变化和实际速度变化是否一致。
4. 逐项验证暂停、等待确认、恢复新导航段、讲解禁行、人工停止优先级和通信断开行为。
5. 测量真实制动距离并标定障碍/人员阈值；未完成前不得宣称具备可靠人群安全防护能力。
6. SDK/Launcher 返回不支持或其他非 200 时，保持暂停/人工接管，不自动切换另一种运动 API。
7. 发生异常时通过应用停止导览和 temi 原生人工操作撤销自动导览；确认物理停止后再复位 ROS `ERROR`。
