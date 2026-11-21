# 开发日志

## 2026-11-19：步骤一，开发环境检查

- Ubuntu 22.04.5 LTS、x86_64、16 逻辑 CPU、15 GiB RAM，检查时剩余磁盘空间约 52 GB。
- Python 3.10.12、ROS2 Humble、colcon 0.20.1、Git 2.34.1、CMake 3.22.1 可用；`rclpy`、`std_msgs` 和接口生成工具检查通过。
- 当前执行环境默认 ROS 日志目录不可写；将本次测试日志临时指向 `/tmp` 后，节点创建及同节点消息发布/接收通过。执行环境拒绝 UDP 套接字和网络接口访问，独立进程 DDS 通信未验证。
- 系统默认 JDK 为 OpenJDK 11；未检测到 JDK 17、Android Studio、Android SDK、全局 Gradle 或 Python `websockets`。已有 Python `venv`。未进行系统安装或修改现有系统环境。

## 2026-11-19：步骤二，官方 SDK 源码核对

- 成功将 `https://github.com/robotemi/sdk.git` 的 `v1.139.0` 标签浅克隆至 `third_party/robotemi-sdk`，提交 `ae1c713cb89ccd9b1e6fe2d497a4e05c1c45edad`。
- 校验标签、提交、`VERSION_NAME` 与 README 声明一致；上游工作树无修改。
- 已阅读官方 API 签名、Listener、数据模型、权限、Sample 和构建文件；结果记录在 `sdk_api_notes.md`。
- 官方构建配置：Gradle 8.5、AGP 8.0.0、Kotlin 1.9.20、compileSdk 34；计划使用独立 JDK 17 和 Android SDK，不升级上游依赖。
- 步骤三待执行：准备 Android 构建工具链及所需许可，并运行 `./gradlew :sample:assembleDebug`。当前未构建 APK，未进行任何实体 temi 测试。

## 2026-11-19：步骤三，官方 Sample 构建（完成）

- 根据官方 SDK CI 配置，选用 Temurin JDK 17、Android platform 34 和 build-tools 34.0.0。
- 已在 `.toolchain/jdk-17` 安装 Temurin 17.0.21.1+2，归档 SHA-256 与官方 API 一致；`java`、`javac` 已运行验证，系统默认 JDK 11 保持不变。
- 官方 Gradle Wrapper 8.5 已下载并验证；`./gradlew --version` 确认 JVM 为上述 JDK 17、Gradle 8.5、Kotlin 1.9.20。缓存位于 `.toolchain/gradle`。
- 第一次实际执行 `./gradlew :sample:assembleDebug --no-daemon --stacktrace` 退出码 1，耗时 2m 39s，原因为 `SDK location not found`。尚未生成 APK。
- 用户提供 Android 官方命令行工具 ZIP，已校验 SHA-256 后解压至 `.toolchain/android-sdk/cmdline-tools/latest`；`sdkmanager --version` 返回 22.0。
- 执行 `sdkmanager --install 'platforms;android-34' 'build-tools;34.0.0'`，安装器已显示 Android SDK 许可确认提示，等待用户同意。未擅自确认许可。
- 用户明确同意 Android SDK 许可后，继续安装成功（退出码 0）。已确认 platform API Level 34、Revision 3、`android.jar` 和 Build Tools 34.0.0 存在，`aapt2` 可运行。
- 将项目独立 Android SDK、JDK 17 和 Gradle 缓存路径仅传给构建进程，再次执行 `./gradlew :sample:assembleDebug --no-daemon --max-workers=4 --console=plain --stacktrace`：退出码 0，`BUILD SUCCESSFUL in 1m 18s`，54 项任务均实际执行。构建期间 AGP 自动安装 Build Tools 30.0.3 以及 Platform Tools 37.0.1。
- 编译过程中出现 AGP 8.0.0 对 API 34 的兼容性警告、SDK XML 版本及上游弃用 API 警告，均未阻止构建；未为消除警告而修改上游仓库。
- APK：`third_party/robotemi-sdk/sample/build/outputs/apk/debug/sample-debug.apk`（6,049,669 bytes）；SHA-256：`e013e45d757ae7c91afb03ada833eeb7630c22428ca358329901a1ae8000e18a`。ZIP 完整性检查通过；`aapt` 确认包名 `com.robotemi.sdk.sample`、minSdk 23、targetSdk 30、compileSdk 34；`apksigner verify` 退出码 0，v1/v2 签名有效。
- 成功构建日志保存在 `docs/sdk_sample_build.log`。上游工作树无修改，系统默认 JDK 仍是 11。实体 temi 安装与 SDK 实际调用标记 `HARDWARE_REQUIRED`。

### 复现构建

从 `heritage_temi_robot` 项目根目录运行以下命令；环境变量仅在单次构建进程生效：

```bash
project_dir="$PWD"
cd third_party/robotemi-sdk
env JAVA_HOME="$project_dir/.toolchain/jdk-17" \
  GRADLE_USER_HOME="$project_dir/.toolchain/gradle" \
  ANDROID_HOME="$project_dir/.toolchain/android-sdk" \
  ANDROID_SDK_ROOT="$project_dir/.toolchain/android-sdk" \
  ANDROID_USER_HOME="$project_dir/.toolchain/android-user" \
  ./gradlew :sample:assembleDebug --no-daemon --max-workers=4
```

## 2026-11-19：步骤四，ROS2 工作空间初始化（完成）

- 创建 `ros2_ws/src` 下六个职责明确的模块目录：`temi_interfaces`、`temi_bridge`、`heritage_tour_manager`、`visitor_perception`、`heritage_knowledge`、`heritage_dashboard`；同时创建 Android Bridge、配置、测试与脚本目录。
- `test -d` 对所需目录逐项检查通过；在 `ros2_ws` 中实际运行 `colcon list --base-paths src`，退出码 0。当前尚无 `package.xml`，所以扫描结果为空，未声称接口包已完成或编译成功。
- 新增 `README.md`、`.gitignore`、`docs/architecture.md` 以及工作空间实施记录，明确 Mock / Real 分离和 `HARDWARE_REQUIRED` 边界。
- 官方 SDK 仍固定为 `v1.139.0`，工作树无修改。无系统安装、无环境变量永久修改。
- 下一步：建立 `temi_interfaces` 的 `ament_cmake` 包，生成 2 个消息、2 个 Action 和 1 个 Service，进行真实 colcon 构建和 Python API 导入测试。

## 2026-11-19：步骤五，ROS2 自定义接口包（完成）

- 新增 `temi_interfaces`（`ament_cmake` + `rosidl_default_generators`），定义 `RobotStatus`、`NavigationStatus`、`NavigateTo`、`Speak`、`StopRobot`。Action 文件严格按 Goal、Result、Feedback 顺序组织。项目源码仍未选择对外发行许可；ROS 包元数据使用 `UNLICENSED`，维护者邮箱为保留的 `.invalid` 地址，正式发行前须确认实际维护者及许可。
- 测试先行：构建前 `pytest -k robot_status` 实际失败，错误为 `ModuleNotFoundError: No module named 'temi_interfaces'`，确认测试确实依赖生成的接口。
- 初次默认构建退出码 1。排查 `/opt/ros/humble/share/rosidl_adapter/cmake/rosidl_adapt_interfaces.cmake`：生成的 `.idls` 文件中路径含 `文档` 和 `国赛`，其 `file(STRINGS ...)` 未指定 UTF-8，导致路径拆分，`rosidl_generate_interfaces.cmake` 出现 `list index: 1 out of range` 和 `Target dependency '/ChatGPT/ican' does not exist`。
- 不修改系统 ROS2，改用项目专属纯 ASCII `/tmp` CMake 构建目录，保留原始源码、安装目录和日志。实际 `colcon build` 成功：`1 package finished [5.37s]`。新增 `scripts/build_ros2.sh` 复现该方案，再次实际构建成功（`1 package finished [5.53s]`）。
- `ros2 interface list` 显示全部五个接口；`ros2 interface show` 逐一核对字段。生成包已安装在 `ros2_ws/install/temi_interfaces`，Python 可导入。
- 在隔离 ROS Domain 231、仅本机通信条件下执行 `pytest`：6 项全部通过，覆盖五类接口字段及实际序列化回环、rclpy 节点创建、自定义消息发布接收。创建了两个 ActionClient 和 StopRobot Service Client，但本阶段没有实现其任务服务端，因此未宣称 Action 或 Service 功能执行成功。
- 额外跨进程 DDS 验证：独立进程执行 `ros2 topic pub` / `ros2 topic echo`，收到 `connected: true`、`battery_percentage: 82.5`、`current_location: exhibit_01`，退出码 0。补全了步骤一未验证的本机独立进程 DDS 通信；无实机操作。
- 执行记录：`temi_interfaces_build_initial_failed.log`（初次失败）、`temi_interfaces_build.log`（成功编译）、`temi_interfaces_test.log`（6 项通过）、`temi_interfaces_dds_test.log`（独立进程通信）。
- 独立代码审查后加固：构建脚本使用 `mktemp -d` 创建私有 ASCII 目录；pytest 自身强制本地通信和测试 ROS Domain；电量未知默认值改为 `-1.0` 并增加断言，断言先失败（旧默认 0.0）再通过。最终再次实际构建成功（`1 package finished [5.32s]`）、6 项测试通过（0.20s）并复测跨进程 DDS 成功，未修改上游 SDK。
- 下一步：定义 `TemiBackend` 抽象接口，确定导航执行、停止、语音和状态快照契约，为 Mock 与 Real 后端统一接入打基础。

## 2026-11-19：步骤六，TemiBackend 抽象契约（完成）

- 新建标准 `ament_python` 包 `temi_bridge`（`package.xml`、`setup.py`、`setup.cfg`、ament 索引资源）。目前包仅包含纯 Python 后端契约，不创建虚假 ROS2 节点和 SDK 调用。
- `temi_bridge/backend.py` 新增 `TemiBackend` ABC：五个异步控制方法 `connect`、`disconnect`、`navigate_to`、`stop`、`speak`，以及同步非阻塞 `get_status`。命令完成返回 `TaskResult`；导航与播报反馈关联 `task_id`。
- 新增不可变数据模型 `RobotSnapshot`、`TaskResult`、`NavigationFeedback`、`SpeechFeedback`。未知电量和未连接状态与 ROS2 `RobotStatus` 约定一致。运行时 STOP/取消与真实安全边界记录于 `architecture.md`，不提前标记实机行为为已验证。
- 测试先行：未实现时 `pytest -k requires_all_six_operations` 实际失败（`ModuleNotFoundError`），实现后源码契约 6 项通过。`colcon` 实际构建 `temi_bridge` 成功（`1 package finished [30.7s]`）。`ros2 pkg prefix temi_bridge` 指向项目安装目录，安装模块可独立导入且不加载 `rclpy`。
- 从安装后的工作空间运行后端测试和既有接口测试：12 项全部通过（0.22s），其中包括 ROS2 本地消息通信回归。记录于 `temi_backend_build.log`、`temi_backend_test.log`。
- 独立代码审查未发现阻断问题；架构文档进一步明确了 STOP 仅停止运动、断线终止两类任务、命令 ID 非空、单个活动播报及语音超时策略。上述运行时策略留待具体后端测试验证。
- 下一步：以该契约实现 `MockTemiBackend`，验证连续模拟运动、完成、停止、取消、故障注入、语音、电量和断线重连。

## 2026-11-19：步骤七，MockTemiBackend（完成）

- 新增 `temi_bridge/mock_backend.py`：实现统一后端六接口，使用单 asyncio loop、单调时钟及不可变快照，按真实经过时长、配置速度推进虚拟位置并按位移扣减电量。导航及单个播报可以并行，STOP 仅停止运动。
- 新增 `config/system.yaml` 的 `mock` 参数及八个虚拟保存地点；默认失败概率为 0。`MockConfig` 验证速度、延时、概率、电量及位置；使用已安装 PyYAML 5.4.1，无系统依赖安装。坐标仅为 `mock_map` 模拟数据，非真实地图。
- 显式注入 `inject_navigation_failure()`、`simulate_disconnect()`、`set_battery_percentage()`，支持单次失败、网络中断与重连、低电量；旧任务不会自动重发。导航/语音超时、取消、停止与冲突/无效命令均有真实测试。
- 测试先行：未实现时 Mock 测试实际失败（`ModuleNotFoundError`）；初版 16 项通过。独立审查发现 STOP 或重连后旧任务槽位占用、以及 Python 3.10 `asyncio.wait_for` 内部等待完成与外部取消同时发生时可能吞掉取消。新增 3 个回归测试，先失败再修复（释放槽位/操作身份检查、改用 `asyncio.wait` 并清理等待任务）。新增配置速度与延时的实际计时测试；20 项 Mock 测试全部通过（4.92s）。
- `temi_bridge` 重新实际构建成功（`1 package finished [0.93s]`）。已安装模块独立导入且不加载 `rclpy`。运行 `scripts/mock_backend_demo.py`：默认 1 m/s，从 `(0,0)` 连续移动，实际 `0.75s x=0.503`、`1.50s x=1.258`、`2.21s navigation=complete`；最终 `(2.0,0.0)`，电量 100%→99%，模拟语音 `started→complete`，退出码 0。
- 从安装工作空间运行完整回归：20 项 Mock + 6 项后端契约 + 6 项 ROS2 接口，共 32 项通过（5.27s）。日志：`mock_backend_build.log`、`mock_backend_demo.log`、`mock_backend_test.log`。
- 当前只验证独立模拟后端；没有真实音频输出、实体地图、导航/避障或 ROS2 Action 服务端。实机仍为 `HARDWARE_REQUIRED`。
- 下一步：建立 ROS2 Gateway，发布 RobotStatus/NavigationStatus，并将 NavigateTo、Speak、StopRobot 接入统一 Backend；实现面向 Android 的认证 WebSocket JSON 协议及故障处理。

## 2026-11-19：步骤八，ROS2 Gateway 和 WebSocket 通信（Linux 端完成）

- 在项目 `.venv`（系统包可见）安装 `websockets==16.1.1`，确认 Python 3.10 与 ROS2 可用；系统 Python 仍未安装 websockets。新增 `requirements-websocket.txt`，Mock 模式没有该可选网络依赖。
- `ros_gateway.py` 实现真实 ROS2 `RobotStatus`、`NavigationStatus` Topic，`NavigateTo`、`Speak` ActionServer 和 `StopRobot` Service；ROS2 多线程 executor 驱动后端独立 asyncio loop。使用 ROS Goal UUID 关联任务与反馈、限制同类并发、保持 STOP 可执行；支持成功、失败、取消与状态发布。
- `protocol.py` 和 `websocket_backend.py` 实现 Linux WebSocket 服务端、Bearer 认证、v1 握手与首次状态超时、单客户端、完整状态同步、Ping/Pong 心跳、ID、ACK 和终态关联、过期、重复及输入校验。默认 loopback，并拒绝通配和公网地址；允许显式私有 LAN IPv4。未暴露公网控制端口。
- 实现 STOP 独立优先处理、ACK/导航超时后补发 STOP；未确认停车时阻止新导航，未确认语音取消时阻止新语音。断线终止旧任务且禁止重放，重连后完整状态同步。真实 Android 客户端主动重连/SDK 断线保护会在步骤九实现；Linux 模拟客户端测试不证明实体停车。
- 回归审查：先增加失败测试，再解决已接受未执行 Goal 在 STOP/重连后启动的问题（`connection_epoch`）、反馈发布异常中断任务、并发 STOP 占用执行线程、STOP 完成与迟到导航终态竞争、未确认 STOP 安全门、首次状态超时及非法数值。继续验证缺失 pong、ACK 拒绝与缺失、语音取消未确认、主动关闭过程。
- CLI `gateway_main.py`、ROS2 入口 `temi_gateway` 和 `config/system.yaml` 配置支持 mock/websocket 后端切换；默认 Mock。构建实际退出码 0，`Summary: 2 packages finished [6.01s]`。`ros2 run temi_bridge temi_gateway --help` 输出正确。
- 实际环回 ROS2 Gateway 12 项集成测试、认证 WebSocket 16 项测试，以及 ROS2 Action 经 WS 到模拟 Android 的端到端 1 项测试全部通过。独立进程测试验证跨进程 Topic、Action 与 Service、活动导航时 SIGTERM 有序退出（退出码 0）。
- 最终从已安装工作空间执行 `pytest tests`：**62 项通过（19.01s）**；含之前 32 项接口、抽象和 Mock 行为回归。日志：`gateway_build.log`、`gateway_test.log`、`gateway_cli_test.log`。测试均使用本机隔离 DDS Domain 和回环 WebSocket，无实体机器人调用。
- 新增 `communication_protocol.md`，记录 Android 客户端需实现的 JSON 字段、事件顺序、认证、心跳、重连、过期处理和安全约束。官方 SDK 源码未修改，系统 Python/Java/ROS 环境未永久修改。
- 当前限制：Android Kotlin Bridge 尚未实现；认证未替代 TLS 或 ROS2 网络访问控制，`ws://` 只适用于可信隔离开发局域网。实体设备的 SDK Ready、导航完成确认、坐标量纲、真实停止、断线保护与语音均为 `HARDWARE_REQUIRED`。ROS2 Action 取消不等于确认实机停车。
- 下一步：建立 Android Kotlin Bridge App，使用已验证的 JDK 17、Gradle 8.5、temi SDK 1.139.0 和本协议；编译 APK，通过虚拟客户端或 JVM 单元测试验证协议并明确实机测试边界。

## 2026-11-19：步骤九，Android Kotlin Bridge（基础工程及 APK 完成）

- 新建独立 Android 项目 `android/temi_heritage_bridge`，包名 `com.heritage.temibridge`、版本 0.1.0，使用项目专属 JDK 17.0.21.1+2、Gradle Wrapper 8.5、AGP 8.0.0、Kotlin 1.9.20、compileSdk 34、minSdk 23、targetSdk 30。实际 `debugRuntimeClasspath` 解析 `com.robotemi:sdk:1.139.0`、OkHttp 4.12.0、Gson 2.9.0；官方第三方源码无变动。
- `BridgeProtocol.kt`、`BridgeCoordinator.kt` 实现严格 v1 JSON、命令截止时间/ACK/去重、目标与 SDK UUID 关联、STOP 和语音取消、未确认停止/断线的动作隔离。`WebSocketBridgeClient.kt` 执行 Bearer 认证、私有 IPv4 限制、OkHttp Ping/Pong、重连与旧连接回调过滤；token 不写入日志或持久配置。
- `SdkTemiDriver.kt` 编译接入真实 `Robot.getInstance()`、已保存地点 `goTo`、`stopMovement`、`speak`、`cancelAllTtsRequests` 和实际监听器；`MainActivity` 前台连接界面及本地 STOP、离开前台断开。纯 JVM 测试不调用实体 SDK。通过 Manifest 合并去除 SDK AAR 的旧存储权限，实际 APK 仅 INTERNET。
- 测试先行的初次 `:app:testDebugUnitTest` 因缺少实现类而实际编译失败（`android_bridge_test_initial.log`）；首轮 14 项 JVM 测试通过。追加 3 个迟到 STOP/TTS 回调、新连接 STOP 隔离、SDK Ready 恢复后的安全重试用例，确认均先失败（`android_bridge_edge_initial.log`）后修复；新增真实本机 OkHttp/MockWebServer 的协调器与协议端到端 1 项测试。
- 最终执行 `./gradlew :app:testDebugUnitTest :app:assembleDebug --rerun-tasks --offline --no-daemon --max-workers=4 --console=plain`，退出码 0，`BUILD SUCCESSFUL in 17s`、36 项任务实际执行；18 项 JVM 测试全部通过，0 失败、0 跳过（12 协调器、5 WebSocket、1 协议整合）。AGP/API 34 警告保留，不升级官方依赖。
- APK `android/temi_heritage_bridge/app/build/outputs/apk/debug/app-debug.apk`，3,069,871 bytes，SHA-256 `55a2ad61b6c47e75ec0d7eaeecf455bfbaeb4a4d0e6ac4d0f79a85ff2f249e2d`。ZIP 完整性、`aapt` 包名与 Manifest、`apksigner verify` v1/v2 签名均实际通过。日志：`android_bridge_build.log`、`android_bridge_verification.log`、`android_bridge_dependencies.log`；JVM HTML 测试报告在 app/build/reports/tests/testDebugUnitTest/index.html。
- 新增 `scripts/build_android_bridge.sh` 和 `docs/android_bridge.md`，记录构建、配置及实机准备；README 与通信协议已同步。系统默认 JDK 仍为 11。
- 当前仅证明 Kotlin 协议/网络逻辑与 APK 编译：没有 Android 模拟器、设备或 temi 真实 Launcher 运行记录。真实坐标、监听器时序、速度/停车证据、断线保护及真实 TTS 均为 `HARDWARE_REQUIRED`。SDK 位置以 `temi_sdk_unverified` 帧标记，不假设已验证真实量纲。ASR/知识问答留待后续。
- 下一步：实现 `heritage_tour_manager` 导览状态机以及固定五展区路线、互动区与出口配置，接入现有 ROS2 Gateway，先在 Mock 中完整跑通导览与异常恢复。

## 2026-11-19：步骤十，固定路线导览状态机（完成）

- 新建 `config/exhibits.yaml`：入口、潮绣、潮州木雕、潮州工夫茶艺、潮剧、潮州音乐、互动区、出口；保留用户指定五个字段，`temi_location` 全为虚拟名称。示例非遗主题及简介依据中国非遗数字博物馆公开资料自行编写，不冒充实际展陈；链接见 `tour_manager.md`。`system.yaml` 添加导览运行参数、20% 低电量阈值与虚拟安全入口（非充电点）。
- `heritage_tour_manager` 标准 `ament_python` 包包含 `tour_config.py`、纯 Python `tour_manager.py`（11 状态、控制优先级、状态/任务历史）、`ros_tour_node.py`（实际 `NavigateTo`/`Speak` ActionClient、STOP Service、RobotStatus 订阅与通信 watchdog）和 `main.py`。不导入 Android SDK 或具体 Mock 实现。
- 九个 `heritage/tour/*` Trigger 控制：start、accept、refuse、pause、resume、cancel、visitor_lost、manual_takeover、finish_qa；`heritage/tour/status` 发布状态/已访问地点/耗时/错误次数及历史。QA 当前仅人工互动等待，不声称知识问答功能。
- 状态机实现暂停/掉队停车、恢复重启当前段、拒绝/取消/人工接管、低电量安全返回、断线或错误结束；未确认 STOP 或旧 Action 终止时 ERROR，禁止正常宣告 IDLE/PAUSED。ROS adapter 处理迟到接受响应、只接受真实 Action 终态。实体停车、TTS 物理取消、真实电量和地图仍 `HARDWARE_REQUIRED`。
- 测试先行：模块缺失时实际测试失败；初版纯状态机 9、真实 ROS2 集成 5 项通过。再添加停止未确认、取消清理未确认、失败与取消竞态及低电量 target 等先失败后修复测试，并补导航异常 STOP 与 UNKNOWN Action 不视为终态用例。最终新增 13 状态机 + 6 ROS adapter/集成测试，共 19。
- 实际构建 `temi_interfaces`、`temi_bridge`、`heritage_tour_manager` 成功（3 packages finished [33.2s]），审查加固后单包重新构建成功（0.77s），CLI `ros2 pkg executables heritage_tour_manager` 识别 `tour_manager`。
- 最终安装态执行全套 Python 测试：**81 passed in 33.01s**（62 既有 + 19 导览新增）。记录在 `tour_manager_test.log`；构建记录 `tour_manager_build.log`、`tour_manager_rebuild.log`。
- 实际运行 `scripts/demo_mock_tour.py`，独立 Domain 226 的两个 ROS2 进程，默认速度 1m/s、真实 Topic/Action/Service，按顺序访问入口→五展区→互动区→出口，**COMPLETED，19.505s，8/8 导航完成，异常 0 次**。结构化报告 `docs/runs/mock-tour-20261119-174542-511842/report.json`，包含 22 条状态历史、31 条导航事件、8 个状态 complete；同目录节点日志和 `tour_demo.log` 留存。仅 Mock，无真实机器人操作。
- 下一步：统一执行环境、接口、通信、故障、导览与 Android 验收，输出覆盖矩阵、实际运行记录和仍需实机的清单；最后补全第一阶段总交付报告与下一阶段开发计划。

## 2026-11-19：步骤十一、十二，第一阶段统一验收与交付（完成）

- 复查 Ubuntu 22.04.5 / Humble / Python 3.10 / colcon 及独立 Android SDK、JDK 17、Gradle，系统 Python 未安装 websockets、默认 JDK 仍为 11，上游 SDK 工作树洁净；Android Studio 未检测到。结果见 `environment_report.md` 和 `acceptance/environment.log`。
- 重新实际构建三套工程：ROS2 3 packages finished [6.09s]，官方 `:sample:assembleDebug` BUILD SUCCESSFUL in 31s，Android Bridge BUILD SUCCESSFUL in 17s（36 项任务实际执行）。两个 APK 的 ZIP 完整性、包名、版本和调试签名检查通过，哈希与阶段九及第三步的对应产物一致。
- `tests/test_tour_ros_integration.py` 新增五项实际 ROS2 异常集成用例：掉队、低电量、断线重连无旧任务重放、拒绝/人工接管、导航故障传播。安装态完整 Linux 测试 **86 passed in 35.48s**；Android JVM **18 passed**。共 104 项通过、0 失败、0 跳过。
- 独立 ROS2 进程再次完整执行固定八站 Mock 导览，最终 COMPLETED、8/8、19.514s、0 次异常，保存 22 条状态历史、31 条导航事件；报告：`runs/mock-tour-20261119-175848-898487/report.json`。本次构建、测试 XML、APK 验证及运行日志集中保留于 `acceptance/`。
- 新增 `acceptance_report.md`（A–E 覆盖矩阵、十二项交付清单、复现命令与验证边界）、`environment_report.md` 和 `next_phase_plan.md`；README 更新第一阶段完成状态。没有任何实体设备测试，真实导航、地图、停车、避障、传感器和语音仍为 `HARDWARE_REQUIRED`。
- 第二阶段：获得设备后以物理安全与通信验证为首要验收门；无实体设备期间优先开发可离线测试的 `visitor_perception`，后续推进知识库、真实语音交互和监控控制台。

## 2026-11-19：第二阶段 2.1，独立 Mock 游客感知（完成）

- 经用户确认先完成匿名人数逻辑，再推进导览联动和视觉。设计和实施计划保存在 `docs/superpowers/specs/2026-11-19-visitor-perception-design.md`、`docs/superpowers/plans/2026-11-19-visitor-perception.md`。不调用导览/运动服务、不使用摄像头或身份识别。
- 新建标准 `ament_python` 包 `visitor_perception`，包含纯 Python `VisitorMonitor`、`VisitorConfig`、`VisitorPerceptionNode` 与 CLI 入口；`system.yaml` 增加 3 个连续稳定样本与 2 秒断流阈值；四个 ROS2 Topic 以 Int32 输入、String JSON 输出匿名人数、预期队伍和事件。
- 测试先行：未实现时新测试实际报 `ModuleNotFoundError`，实现后 16 项独立逻辑测试全过，真实 ROS2 Topic 集成测试 1 项通过；分别覆盖去抖、到来/离开、队伍不足与集合去重、非法输入、断流恢复，以及未知不等于零人。
- 初次回归受进程本机网络权限限制（Fast DDS UDP socket `Operation not permitted`）；在允许本机通信的环境中重新执行，既有 86 项全部通过（35.40s），原有代码无修改。独立代码审查未发现核心逻辑缺陷，演示和集成测试补充事件 Topic 发现检查并遵循配置样本数。演示第一次使用新 Domain 233 时端口超限，另一次使用了 Humble 不存在的 Subscription 方法，分别修正为独立 Domain 224 和 Humble 的 `Node.count_publishers()`；原始失败日志保存在 `acceptance/visitor_perception/`。
- 实际完整重构建四个 ROS2 包成功（`4 packages finished [1min 2s]`）。独立进程运行 `scripts/demo_mock_visitors.py`，成功按顺序产生 `arrival`、`visitor_lost`、`regrouped`、`departure`、`data_stale`、`data_restored`，报告 `docs/runs/mock-visitors-20261119-223622-137782/report.json`，最终稳定 0 人、无队伍跟踪。完整 Linux 回归验收 **103 passed in 36.87s**（86 既有 + 17 新增），本阶段未改动 Android，未重复执行其 18 项 JVM 测试。
- 新增 [游客感知使用说明](visitor_perception.md)，更新 README 和架构图，保留真实运行日志与 JUnit XML。下一步 2.2：将感知事件接入导览状态机，明确游客同意、人工接管、暂停恢复和感知断流边界；真实视觉检测及实体测试仍未完成。

## 2026-11-19：第二阶段 2.2，Mock 感知与导览联动（完成）

- 经用户确认实施 [联动设计](superpowers/specs/2026-11-19-visitor-tour-integration-design.md)；原工程基线实际复测 103 项通过（36.81s）。保留手动模式，默认 `tour.visitor_assist_enabled: false`；仅本机 Mock 配置开启联动。
- `VisitorMonitor` 状态新增 `stable` 和 `stable_fresh`，持续合法但不稳定观测亦会失效。`VisitorAssist` 在导览节点同一 asyncio loop 内实现一次性 `arm_visitor`、arm 后确认空场及游客到来、预期人数确认、同意和恢复守卫、感知断流/异常暂停、会话终态清理；`mock_map` 仅为 Mock 标识，不是生产认证。拒绝、取消、人工接管、机器人断线或感知心跳中断后不自动启动新任务。
- 测试先行：初次新用例因缺失稳定字段与配置字段失败；实现后首轮 10 项 ROS2 三节点测试通过。独立代码审查复现恢复请求失效后可能被重用、低电量 STOP 等待中优先级命令被覆盖两类竞争；新增失败复现再修复，撤销尚未消费的旧恢复授权并维护 STOP 期间最高优先级。另新增心跳断开解除 arm、非法 JSON、预期人数不一致及就绪状态 `can_arm` 等覆盖。第一次完整回归因故障注入中测试观察者错误解析非法 JSON 终止 executor（120 通过、1 失败），首次独立演示因准备条件尚未同步拒绝 arm；均定位后修复观察者与就绪等待，保留初次日志。
- 实际完整重新构建四包成功（`4 packages finished [1min 2s]`）；最终修改后导览包重构建 0.78s。最终完整 Linux/ROS2 回归 **121 passed in 56.41s**，新增 18 项（13 ROS 集成、4 状态机、1 感知稳定新鲜度），无失败或跳过。Android 未修改亦未重复测试。
- 独立 `scripts/demo_visitor_tour.py` 启动三个本机 ROS2 进程，Domain 223，成功完成迎宾→同意→潮绣途中掉队暂停→拒绝不安全 resume→重新集合等待→人工 resume→继续八站至出口。`COMPLETED`，20.635s，8/8，9 次导航启动、1 次 STOP/中断、8 次完成，1 次预设掉队计数，无未预期错误。报告 `docs/runs/visitor-tour-20261119-232612-152286/report.json`；`acceptance/visitor_tour/` 保存构建、测试日志和 JUnit。
- 更新 README、感知说明、架构及 [联动使用说明](visitor_tour_integration.md)。下一步 2.3 使用离线视频验证真实视觉人数检测；仅匿名人数，不启用人脸识别或实体自动导航，继续保留人工确认和 Mock 独立路径。

## 2026-11-19 至 2026-11-20：第二阶段 2.3，真实离线视觉人数检测（本机实现与探索性评估完成）

- 经用户确认采用 [2.3 设计](superpowers/specs/2026-11-19-offline-vision-count-design.md)，本地已有 OpenCV 4.11.0 / NumPy 1.23.5，无需安装 PyTorch 或更改系统 Python。现有 121 项基线实际通过。仅本地 CPU、明确文件，无摄像头、身份识别或实际运动。
- 官方 OpenCV Zoo 固定提交 `48b10fa505aeb51fbd127fc60a5c660040e823b7` 的 YOLOX-S ONNX，官方 Git LFS SHA256 `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`，经官方 Hugging Face 同哈希镜像续传成功，35,858,002 bytes。OpenCV 4.11.0 官方 `vtest.avi` 视频 SHA256 `45cddc9490be69345cbdab64ca583be65987e864ca408038e648db99e10516cf`，795 帧、10FPS、768×576。保留官方许可与来源，模型、录像默认不纳入 Git 发布；详见 `assets/vision/README.md`。
- 新增 `person_detector.py`（YOLOX RGB letterbox、固定 shape、person 置信度/NMS）、`video_counter.py`（显式视频采样、错误断流、计数误差与延迟）、`video_main.py` 及 `offline_video_count` 执行入口；`VisitorConfig.count_source` 默认 mock，离线专用 `vision_count` Topic 发 `source=offline_video`，既有协作策略只接受 mock，不向离线录像开放控制。无保存人脸/跟踪；仅保留数值输出。
- 预先选择每 40 帧一次的 20 个参考帧，在运行模型前由 Codex 目视计数并保存 `assets/vision/vtest_reference.json`（非专业人工复核标签，正式基准尚待安排），临时抽帧检查图片清理。最终实际模型 MAE 0.40、RMSE 0.6325 人，精确计数 12/20（60%）、非空判零 0/20、平均 143.62ms、P95 155.68ms；8 帧各少计 1 人。无真实空场，独立三张合成纯色空帧输出均 0。计数指标仅探索性，不是逐人检测精度或真实展厅测评。
- 测试先行：缺失模块/配置时明确失败，实现后首轮纯逻辑 + ROS Topic 测试通过；独立审查认可模型与源隔离，新增非法概率张量及参考 JSON 结构/重复键/视频哈希检查，先失败后修复。首次真实 ROS2 回环收到 20 项但 DDS ACK 超时，旧 CLI 将确认超时误判推理失败；改为分别记录 ACK 状态与实际接收核验。复现独立监测节点 SIGTERM 时 ROS context 竞争，新增回归并安排显式信号处理；初次失败日志保留。
- 完整四包实际构建（`4 packages finished [33.3s]`），最终游客感知包重新构建（30.2s）。最终 **156 passed in 59.40s**（新增 35：检测 13、视频/指标 17、ROS 5），0 失败/跳过。本机独立 `scripts/demo_offline_vision.py` Domain 221（只启动感知和视频计数，无机器人控制节点）实际收到 20/20 模型计数且完全一致，12.553s 后成功退出；历史 `arrival`、`data_stale`，最终 `source=offline_video, valid=false, people_count=null`，没有假离开。DDS ACK 仍未确认如实保留，实际订阅序列通过。原始报告 `docs/runs/offline-vision-20261120-001026-631467/report.json`、`predictions.json`；文件集中于 `docs/acceptance/offline_vision/`。
- 更新 [视觉使用说明](vision_perception.md)、README、架构与源隔离说明。Android/实机未改动也未复测。下一步 P2 `heritage_knowledge` 非遗文本知识库与可追溯离线问答；真实摄像头、专业标注、真实空场/展厅、传感器与实体移动仍待验证。

## 2026-11-20：第三阶段 3.1 非遗知识库与离线问答

- 核对中国非物质文化遗产网五个主题公开资料，录入 `config/knowledge.yaml` 的 15 个问答意图，记录出处与日期；所有内容为示例知识，未获展厅工作人员审核。
- 新建 `heritage_knowledge` ament_python 包、离线 CLI、知识库验证及关键词检索，新增 `temi_interfaces/srv/AskHeritage.srv` 与独立 ROS2 服务；无模型/API 依赖，不调用运动或播报。
- 测试先行：模块缺失时确认失败；五包构建成功（36.5s），新增 22 项用例含实际独立进程 Service 回环。完整 Linux 回归 **178 passed in 59.85s**，记录于 `acceptance/knowledge/`。实际 CLI 验证进阶答案来源与无依据拒答。
- 参见 [知识库使用说明](heritage_knowledge.md)。下一步 3.2 接入导览 QA；真实语音、实机及人员审校仍待验证。

## 2026-11-20：第三阶段 3.2 导览 QA 联动

- 新增 `SubmitQuestion.srv` 与 `heritage/tour/ask` 服务，QA 等待期一次提交文本问题；异步调用独立知识节点，超时或失败明确回退并使用原有播报 Action，成功后继续路线。状态记录来源、命中及播报确认，拒绝迟到、非法、重复问题，保留原有控制优先级。
- 新增 6 项测试，首轮未实现提交接口时确认失败；最终五包重建成功（62s），完整回归 **184 passed in 77.71s**，0 失败/跳过，新增实际 ROS2 服务联动、拒答/不可用回退及状态机取消测试。
- `scripts/demo_mock_tour.py --question '潮剧用什么语言'` 独立三节点成功，命中 `opera_language`，播报确认、八站全部完成、19.965s、0 异常。实际结果见 `docs/runs/mock-tour-20261120-130513-217273/report.json`，日志及测试 XML 在 `docs/acceptance/tour_qa/`。真实 Android ASR/TTS、导航及传感器仍未验证。

## 2026-11-20：第四阶段 4.1 本机可视化监控与人工接管

- 实现 `heritage_dashboard` 标准 Python ROS2 包及 Tk 界面：机器人与匿名游客状态、虚拟八站地图、任务进度、耗时/异常/告警、导航事件、问答及来源。默认只读，无网络控制端口；显式本机 Mock 控制复用现有导览暂停、恢复、取消和人工接管服务，过期、未知或实体坐标系禁止操作。
- 新增 12 纯模型测试及 1 实际 ROS2 操作测试；测试先行、首次节点属性 `clients` 与 rclpy 属性冲突已复现并修复为 `_control_clients`，历史失败日志保留。6 包构建成功（32.0s），最终监控包重构建 30.4s，全量 **197 passed in 77.92s**（0 失败/跳过）。
- `scripts/demo_dashboard.py` 实际 Tk 窗口联动本机独立 Mock 导览、知识库、Gateway 与游客感知，记录模拟人数 3、导航和 QA 来源。首次截屏遮挡后重新定位窗口并检查完整截图；最终报告 `docs/runs/dashboard-20261120-165718-197347/report.json` 和两张截图，实际操作测试验证暂停/恢复/人工接管。参见 [监控说明](dashboard.md)。实体设备和生产安全验证未开展。

## 2026-11-20：第四阶段 4.2 本机 Mock 一键部署与联调

- 新增 `scripts/start_mock_system.sh` 和 Python 进程管理入口，默认只读监控、待机、隔离本机 ROS Domain，强制 Mock 配置副本且不启动实体后端。明确演示参数才模拟三名游客、接受同意、提问并完成八站。检查服务、状态新鲜度、知识库查询及各进程退出情况。
- 新增三个测试覆盖配置隔离、真实 ROS2 一键导览、默认待机退出。首次图形联调发现导览线程关闭竞争，改用停止事件通知并正常等待线程退出；监控窗口也支持信号关闭。两个变更 ROS2 包重建通过，全量回归 **200 passed in 104.27s**。
- 实际五节点图形运行：8/8 站、19.956s、0 次异常、知识答案带来源且模拟播报成功、三名模拟游客、全部子进程退出码 0。默认待机测试验证没有导览访问、游客人数仍未知、机器人虚拟静止。详见 [部署手册及验收报告](deployment.md)。下一步本地长时间运行与故障演练，实机仍须单独验收。

## 2026-11-20：第四阶段 4.3 本机 Mock 连续导览与故障恢复

- 复用一键启动新增显式 `--demo --rounds 1–6`，同一组节点保留模拟位置、电量；每轮检查八站、知识答案及来源、三名稳定模拟游客、出口虚拟静止及终态观察，逐轮保存报告。默认不自动导览，不重试失败任务。待机和演示均检查心跳及进程退出。
- 运行中 Gateway 退出的首轮测试复现 12 秒关停期限不足，导览进程被迫结束；确认 STOP、取消 Action、旧任务清理各有独立通信超时，按其预算延长监督等待。最终故障明确标为失败、全部子进程正常退出，仍记录停车及旧 Action 未确认；显式重新启动后待机且不重放。代码复核进一步收严终态状态和心跳判断。
- 最终六轮演练 48/48 次访问、六次知识播报、0 导览异常、总运行 151.476 秒、四节点退出码 0；独立待机 300.403 秒无状态心跳超时、无自动导览、四节点正常退出。新增四项测试，完整回归 **204 passed in 176.46s**。见 [稳定性报告](stability.md)。仅限本机 Mock，真实场地与设备长时间稳定性仍待现场验收。
