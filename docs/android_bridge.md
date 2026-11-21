# Android temi Heritage Bridge

## 工程与 SDK

应用位于 `android/temi_heritage_bridge/`，包名 `com.heritage.temibridge`，版本 `0.1.0`。构建使用官方 Maven Central `com.robotemi:sdk:1.139.0` 发布 AAR；Gradle 8.5、AGP 8.0.0、Kotlin 1.9.20、JDK 17、compileSdk 34、minSdk 23、targetSdk 30。未修改第三方 SDK 源码，未为消除 AGP/API 兼容警告升级版本。

| 文件 | 职责 |
| --- | --- |
| `BridgeProtocol.kt` | 严格 JSON、协议版本、命令 ID、截止时间和字段校验 |
| `BridgeCoordinator.kt` | ACK、去重、单个导航/播报、停止确认、过期和断线清理 |
| `WebSocketBridgeClient.kt` | OkHttp 认证客户端、心跳、重连、旧会话回调隔离 |
| `SdkTemiDriver.kt` | 官方 SDK 的 Ready、位置、电量、速度、导航、TTS 回调及动作 |
| `MainActivity.kt` | 前台连接界面，token 输入，本地停止和生命周期管理 |

## 可复现构建

从项目根目录执行：

```bash
bash scripts/build_android_bridge.sh
```

产物：`android/temi_heritage_bridge/app/build/outputs/apk/debug/app-debug.apk`。

JVM 测试报告位于 `android/temi_heritage_bridge/app/build/reports/tests/testDebugUnitTest/index.html`。测试覆盖协议及任务协调器（用明确 Fake/测试驱动模拟 SDK），真实 OkHttp 与 MockWebServer 本机 TCP/WebSocket 连接、认证、重连、失效会话及端到端协议反馈。测试不启动 Android 系统、不调用实体 SDK 服务。

## 实机连接流程（硬件到位后）

1. 提前验证 temi Launcher 与 SDK 1.139.0 的兼容性，确认安全区域、人员距离、人工停止手段及已保存的展区地点。APK 可以编译和签名验证，不代表实体 Launcher 可运行。
2. Linux `config/system.yaml` 中的 `gateway.websocket.bind_host` 改为本机实际 RFC1918 私有 IPv4，端口默认 8765。不做公网端口转发，可信隔离 LAN 使用；不可信网络须 WSS/TLS 及访问控制。
3. Linux 运行 WebSocket Gateway 并从进程环境提供至少 16 个可打印 ASCII 的 token（不要写进 YAML 或日志）。详见 README。
4. Android/temi 前台打开 Bridge，输入 `ws://<Linux私有IPv4>:8765/temi` 和同一个 token，点击连接。界面分别显示网络状态和 SDK Ready。token 仅保留在连接内存，输入框不被 Activity 状态保存。主动断开或离开前台时停止本应用正在控制的任务、关闭连接，不自动从后台重连。
5. 只有在真实 SDK Ready、实际地点名称及安全验证通过后，才允许在封闭空旷场地逐项验证 ROS2 命令；Mock `exhibit_01` 等名称须映射到真实保存地点。

## 实体安全与测试边界

- `Robot.goTo(location)` 仅使用实际已保存地点，不关闭安全避障或强制底盘速度。语音经 `TtsRequest.create` 使用 SDK UUID 关联，`cancelAllTtsRequests()` 仅在本 App 有活动播报时调用（本阶段不启用 ASR/问答）。
- STOP 调用没有同步成功返回。Bridge 只在请求后的零速度监听器证据及（存在活动导航时）匹配地点的终态 `complete/abort` 都到达后，才发送 STOP 完成。未确认的 STOP 不被报告为成功；超时后禁止新导航，保留待确认状态。已静止设备可能不再发送速度回调，此时采用保守的超时/未确认结果，而非猜测实体停止。
- 在网络断开、SDK Ready=false、命令过期、主动退出时，尽力停止或取消本 App 当前任务；SDK 恢复就绪时重试未确认安全动作，不重放导航或语音。进程被系统强制终止、Android 后台与 SDK 服务崩溃场景的实际物理停止机制须实机验证。
- 官方导航回调只带地点，不带命令 ID，Bridge 要求目标匹配且观察到进度后才认可正常终态；停止期间隔离旧任务，TTS 通过精确 UUID 匹配。相同地点的罕见迟到 SDK 回调、实机停止速度阈值须进一步验证，不能将 JVM 测试视为真实停车认证。
- SDK `Position` 数据在 `isInMapArea==true` 且数值有限时透传为 `temi_sdk_unverified` 坐标系；尚未确认真实 `x/y/yaw` 量纲与地图方向，不得用于 ROS2 metric 控制。未有效定位时 frame_id 为空，真实地图映射与坐标/单位标定为 `HARDWARE_REQUIRED`。
- SDK AAR 声明的旧外部存储权限对本桥接功能不需要，合并 Manifest 主动移除；App 不请求人脸、地图管理、Kiosk 或麦克风权限，仅为当前联网和导航/播报功能使用 INTERNET。
