# Android Kotlin Bridge Implementation Plan

**Goal:** 建立连接 Linux Gateway 的 Android WebSocket 客户端，使用真实 temi SDK 1.139.0 API 并生成项目 Debug APK。

**Architecture:** Kotlin 协议/任务协调器与 OkHttp 传输均可在 JVM 测试；`SdkTemiDriver` 是唯一的 Android/temi SDK 适配层；Activity 主线程负责协调、重连和监听器生命周期。

**Tech Stack:** JDK 17、Gradle 8.5、AGP 8.0.0、Kotlin 1.9.20、Android API 34、temi SDK 1.139.0、OkHttp 4.12.0、Gson 2.9.0、JUnit 4。

## Global Constraints

- Android 主动连接 Linux 的 v1 协议，私有 LAN IPv4/loopback；Bearer token 仅内存保存，禁止公网和明文日志。
- 不使用 Mock 冒充 temi SDK，未 Ready 不发送控制；STOP Unit 返回不代表停车，必须等待实际匹配的 SDK 事件和速度证据，否则报告未确认。
- 来自旧连接的命令不重放；命令 ID 去重、Unix 毫秒过期检查、ACK 优先于执行，按目标及 SDK UUID 匹配事件。
- 使用已核实的官方 `com.robotemi:sdk:1.139.0` AAR，官方仓库源码保持原样；构建工具链在 `.toolchain` 中。
- 仅 App 前台工作，用户主动连接；离线、SDK 未就绪、App 退出时尽力停止本 App 任务并关闭 WS。所有真实物理动作、量纲、停车验证仍为 `HARDWARE_REQUIRED`。

## Task 1: Kotlin 协议、协调器和单元测试

**Files:** `BridgeProtocol.kt`、`BridgeCoordinator.kt`、`BridgeCoordinatorTest.kt`。

**Produces:** `BridgeDriver`，`BridgeCoordinator(driver, send, nowMs)` 及 socket/SDK 事件处理、`tick()`、`localStop()`。

- [x] 先写测试，缺失类时编译失败；验证握手、命令过期/去重、导航关联、STOP 证据、TTS UUID、断线保护。
- [x] 实现纯 Kotlin 契约和状态机，补齐 3 项先失败再修复的生命周期/过期回归；12 项协调器 JVM 测试通过。

## Task 2: Android WebSocket 传输

**Files:** `WebSocketBridgeClient.kt`、`WebSocketBridgeClientTest.kt`。

**Produces:** `BridgeDispatcher`、`BridgeTransportListener`、`WebSocketBridgeClient.start/stop/send/reconnectAfterProtocolError`。

- [x] 先写 JVM MockWebServer 和调度器测试。
- [x] 实现带 Bearer 认证、Ping/Pong、自动重连、会话身份、主动关闭及私有 IP 校验的客户端；5 项真实本机网络测试通过。

## Task 3: SDK 驱动、Activity 与 APK

**Files:** `settings.gradle`、`build.gradle`、`gradle.properties`、Gradle Wrapper、`app/build.gradle`、`AndroidManifest.xml`、`MainActivity.kt`、`SdkTemiDriver.kt`。

- [x] 建立已验证版本的 Android 构建工程并接入官方 SDK；UI 手动输入地址和 token，有连接、断开与本地停止控制。
- [x] SDK 监听器仅主线程注册和注销；使用 `Robot.getInstance()`、`goTo`、`stopMovement`、`speak(TtsRequest.create(...))`、`cancelAllTtsRequests` 及真实 Ready、位置、电池、速度、导航、TTS 回调。ASR/AI 问答留待后续，不申请不必要的权限。 APK Manifest 核实仅 INTERNET 权限。
- [x] 在项目工具链运行 `:app:testDebugUnitTest :app:assembleDebug`；实际 18 项 JVM 测试通过，APK ZIP 及签名完整性验证通过。
- [x] 1 项 Kotlin 协调器经真实 OkHttp/MockWebServer 与模拟 Gateway 端到端通信测试通过；文档列出部署方式和剩余实体测试项。
