# temi SDK 官方源码核对（v1.139.0）

核对日期：2026-11-19。以下内容依据项目中克隆的官方源码，而非旧版教程。

## 版本与构建基线

- 仓库：https://github.com/robotemi/sdk
- 标签：`v1.139.0`；提交：`ae1c713cb89ccd9b1e6fe2d497a4e05c1c45edad`。
- SDK 发布坐标：`com.robotemi:sdk:1.139.0`。
- Gradle Wrapper：8.5；Android Gradle Plugin：8.0.0；Kotlin 插件：1.9.20。
- SDK 与 Sample 的 `compileSdk` 均为 34，`minSdk` 均为 23；Sample 的 `targetSdk` 为 30。
- 两个模块的 Java/Kotlin 字节码目标均为 1.8，这与运行 Gradle 所需的 JDK 17 不矛盾。
- Sample 使用 `implementation project(':sdk')`，因此构建 Sample 会同时编译仓库中的 SDK 源码。
- 已使用独立 Temurin JDK 17.0.21.1+2、Android SDK API 34（rev. 3）及官方 Gradle Wrapper 执行 Sample 构建。AGP 默认选择 Build Tools 30.0.3，同时按官方 CI 安装了 34.0.0。
- 2026-11-19 构建成功（`BUILD SUCCESSFUL in 1m 18s`，54 项任务执行），完整日志见 `sdk_sample_build.log`；APK 位于 `third_party/robotemi-sdk/sample/build/outputs/apk/debug/sample-debug.apk`（6,049,669 bytes）。

源码路径以下均相对于 `third_party/robotemi-sdk/`。

## 关键接口

定义文件：`sdk/src/main/java/com/robotemi/sdk/Robot.kt`。

| API | v1.139.0 Kotlin 签名 |
| --- | --- |
| `getInstance` | `fun getInstance(): Robot` |
| `goTo` | `fun goTo(location: String, backwards: Boolean? = null, noBypass: Boolean? = null, speedLevel: SpeedLevel? = null, highAccuracyArrival: Boolean? = null, noRotationAtEnd: Boolean? = null)` |
| `goToPosition` | `fun goToPosition(position: Position, backwards: Boolean? = null, noBypass: Boolean? = null, speedLevel: SpeedLevel? = null, highAccuracyArrival: Boolean? = null)` |
| `stopMovement` | `fun stopMovement()` |
| `speak` | `fun speak(ttsRequest: TtsRequest)` |
| `getPosition` | `fun getPosition(): Position`（`@WorkerThread`） |
| `addOnRobotReadyListener` | `fun addOnRobotReadyListener(onRobotReadyListener: OnRobotReadyListener)` |
| `addOnCurrentPositionChangedListener` | `fun addOnCurrentPositionChangedListener(listener: OnCurrentPositionChangedListener)` |
| `addOnGoToLocationStatusChangedListener` | `fun addOnGoToLocationStatusChangedListener(listener: OnGoToLocationStatusChangedListener)` |
| `addOnBatteryStatusChangedListener` | `fun addOnBatteryStatusChangedListener(listener: OnBatteryStatusChangedListener)` |

`Robot.isReady` 表示 SDK 服务是否就绪。`Robot.locations` 返回已保存地点名称。`Robot.batteryData` 为可空的 `BatteryData`。

## 回调及数据模型

| 回调 | 签名及含义 |
| --- | --- |
| RobotReady | `onRobotReady(isReady: Boolean)`；注册时立即通知当前就绪状态 |
| GoTo | `onGoToLocationStatusChanged(location: String, status: String, descriptionId: Int, description: String)`；状态为 `start`、`calculating`、`going`、`complete`、`abort`、`reposing` |
| Position | `onCurrentPositionChanged(position: Position)`；注册时会立即尝试获取当前位置 |
| Battery | `onBatteryStatusChanged(batteryData: BatteryData?)`；可空，不能将空值当作电量 0 |
| TTS | `Robot.TtsListener.onTtsStatusChanged(ttsRequest: TtsRequest)`；通过 `addTtsListener` 注册 |
| ASR | `Robot.AsrListener.onAsrResult(asrResult: String, sttLanguage: SttLanguage)`；通过 `addAsrListener` 注册 |

- `Position`（`navigation/model/Position.kt`）含 `x`、`y`、`yaw`（Float）、`tiltAngle`（Int）及可为空的 `isInMapArea`。服务不可用时 `getPosition()` 可能返回默认零值，不能视为经过测量的有效位置。
- `BatteryData.kt` 中 Kotlin 电量属性是 `level: Int`，另有 `isCharging: Boolean` 和可空的 `battery2Level`。
- `TtsRequest.kt` 中 `TtsRequest.create(speech, isShowOnConversationLayer, language, showAnimationOnly, cached)` 创建请求，`id: UUID` 可关联播报状态。状态包含 `PENDING`、`PROCESSING`、`STARTED`、`COMPLETED`、`ERROR`、`NOT_ALLOWED`、`CANCELED`。中文语言枚举为 `ZH_CN`。
- ASR 可通过 `wakeup(...)`、`askQuestion(...)` 等官方语音流程触发，`finishConversation()` 可结束会话。本阶段只核对接口，不实现语音识别业务。

## 权限与生命周期

- 官方 Sample Manifest 使用 `com.robotemi.sdk.metadata.SKILL` 让应用出现在 temi Launcher 中，并通过 SDK 权限 metadata 声明权限。
- SDK 的 `Permission` 枚举包括 `FACE_RECOGNITION`、`MAP`、`SETTINGS`、`SEQUENCE`、`MEETINGS`；按实际功能需要最小化申请。`checkSelfPermission(permission)` 返回 `GRANTED` 或 `DENIED`；`requestPermissions(permissions, requestCode)` 后通过 `OnRequestPermissionResultListener` 获取结果。
- 多个 Listener 的注册、注销接口标记为 `@UiThread`；官方 `MainActivity` 在 `onStart()` 注册、在 `onStop()` 中注销。
- `TemiSdkContentProvider` 初始化 Android Context，`TemiSdkServiceConnection` 通过 Android Binder 绑定中国版或美国版 temi Launcher 的 `com.roboteam.teamy.sdk.SdkService`。普通 Linux/Python 进程无法直接调用这些 SDK 服务。

## 对 Bridge 架构的约束

1. 未获得 RobotReady 时不执行导航，不把没有抛出异常视作执行成功。
2. `goTo()`、`stopMovement()` 和 `speak()` 都没有同步任务结果；通过回调及超时形成异步任务结果。
3. 导航回调携带地点而不携带 ROS2 任务 ID。Bridge 应保证一次只有一个活动导航任务，并可靠关联命令 ID；终止、超时和断线时不得使用过期回调完成新任务。
4. TTS 通过 SDK UUID 关联 ROS2 播报命令 ID。
5. 导航使用已保存的地点名称；真实地点、坐标、物理运动、避障、传感器及语音体验全部标为 `HARDWARE_REQUIRED`。

## 核对范围

已检查 README、Gradle 配置、Robot API、导航/语音/位置/电量 Listener、Android Manifest、权限定义和官方 Sample 生命周期。官方 SDK 源码与 Sample 已成功编译并生成经 ZIP 和签名验证的 Debug APK；未安装至实体 temi，也未验证实机 API 调用。
