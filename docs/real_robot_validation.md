# temi 实机部署与验证清单

当前没有实体 temi。本文件是后续现场步骤，不是已完成的实机验收结论。

## 部署前确认

- Android 工程依赖固定为 `com.robotemi:sdk:1.139.0`；APK 编译通过不代表机器人 Launcher 一定支持该功能。
- 在目标机器人确认 Launcher/temi OS 版本、机器人型号、地图、已保存地点和 SDK 服务 Ready 状态。
- 确认目标 Launcher 支持 `Robot.setCurrentGoToSpeed(float)`。目标源码范围为 0.3–1.5 m/s，返回码 200 才表示成功；0、400、408 均按失败处理。
- temi Android 平板与 ROS2 主机置于可信的私有 IPv4 局域网。Android 输入 Gateway 地址 `ws://<ROS 主机私有 IPv4>:8765/temi` 及至少 16 位 ASCII token。Gateway 只监听配置指定地址；不要使用公网或通配监听。
- 编译并安装 `android/temi_heritage_bridge/app/build/outputs/apk/debug/app-debug.apk`，在 temi Launcher 启动前台 Bridge，确认 SDK Ready 和 WebSocket 状态同步。
- 从 ROS2 侧启动 Gateway 的 `websocket` backend、`temi_speed_controller` 和 tour manager；调速输入必须持续提供 `heritage/speed_control/input`，并带真实测量年龄、当前 ROS 导航 Goal UUID、人员距离、人群密度、障碍距离、定位/通信和讲解状态。数据未接入前应保持策略停用/停车状态，不能用 Mock 发布器替代现场感知。

## 有人监护下的低速步骤

1. 清空走道并安排一名操作员站在 temi 原生急停/人工控制附近。不要先接待真实游客。
2. 确认 `/temi/robot_status` Connected、位置有效、导航任务 UUID 出现在输入中，且所有距离值有新鲜时间戳。
3. 在 0.3 m/s 目标速度下启动一个最短的已保存地点 GoTo。观察 WebSocket `speed_status` 及 `sdk_return_code=200`；其他返回码立即结束自动调速验证并转人工接管。
4. 用独立测速工具记录目标速度变化的时间、实际速度、定位、地面条件和测量误差。ROS 目标值及 SDK 返回 200 不能代替实际速度测量。
5. 逐步验证从 0.3 到 0.5 m/s 的小幅变化，然后验证游客接近和拥挤时减速。每次只改变一个输入，并记录真实采集时间。
6. 在没有游客、使用软障碍/安全布置的情况下测量障碍减速距离、暂停确认时间和真实制动距离。逐步校准停止阈值及滞回；当前 YAML 数值只是开发初值，不是安全标准。
7. 验证 pause 到 `PAUSED` 后才进入 WAITING；障碍/队伍恢复持续达到配置窗口后，TourManager 启动新的导航 Goal UUID；低速指令只作用于新 UUID。
8. 分别验证讲解、人工暂停、人工停止、ROS/Android 网络断开、Launcher 返回不支持/400/408、定位失效和传感数据过期。任一情况下都不得自动重放旧导航或继续加速。
9. 结束后核对事件日志、导航任务 ID、SDK 返回码及独立测速记录；只有现场测量和风险评估完成后，才能讨论是否开放真实游客测试。

## 失败处理

- SDK 返回 0/400/408 或执行超时：进入 ERROR 并请求暂停；保持人工监护，不回退到反复 `goTo()` 或电机直控。
- 停车/PAUSED 状态未确认：不能宣称机器人已经停稳；由现场人员使用 temi 原生控制确认状态。
- 传感器无数据或采集超时：策略按保守停车处理；若通信也中断，软件无法保证命令送达，现场人员须介入。
- 修复故障后，由操作员检查停稳、定位、输入数据及 SDK 状态，再调用 `heritage/speed_control/reset_error`。
- 未验证的项目保持 Mock 模式，不以 Mock 成功替代实机验证。
