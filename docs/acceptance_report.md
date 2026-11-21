# 第一阶段统一验收与交付报告

验收日期：2026-11-19。项目：`heritage_temi_robot`（ROS2 Humble + Android Kotlin + temi SDK `v1.139.0`）。

## 验收结论

第一阶段十二步的开发、编译、Mock 测试及项目文档交付均已完成。整体自动化测试为 **104 项通过、0 失败、0 跳过**：Linux/ROS2 共 86 项，Android JVM 共 18 项。官方 Sample 和项目 Bridge 均重新编译成功并通过 APK 完整性与签名校验。真实 ROS2 独立节点的 Mock 固定导览八站完整完成，19.514 秒、0 次异常。

验收仅覆盖 Linux、Mock、通信逻辑和 Android 编译/JVM 测试。**不代表实体 temi 已通过测试或可安全在展厅部署。** 实机所需的 Launcher 服务、地图、底盘、传感器和真实语音统称 `HARDWARE_REQUIRED`。

## A–E 验收矩阵

| 验收类别 | 实际执行结果 | 证据 |
| --- | --- | --- |
| A. 环境及构建 | Ubuntu 22.04.5、Humble、colcon、Python 3.10、项目独立 JDK 17/Android SDK 34 可用；三个 ROS2 包重新构建成功；官方 Sample 重新编译成功 | [环境报告](environment_report.md)、[ROS2 构建](acceptance/ros2_build.log)、[SDK 构建](acceptance/sdk_sample_build.log) |
| B. 自定义接口 | 2 Message、2 Action、1 Service 已生成，五类 Python 接口可导入；Gateway 和 Tour Manager 节点可实际启动 | [包及接口核验](acceptance/interfaces.log)、[Linux 测试](acceptance/linux_test.log) |
| C. 通信 | ROS2 Action、Service、Topic 实际发送与接收命令和反馈；Mock 连续模拟移动、停止及语音事件；WebSocket 认证、握手、回环、命令/反馈真实测试 | [Linux 测试](acceptance/linux_test.log)、[Android JVM 测试报告](../android/temi_heritage_bridge/app/build/reports/tests/testDebugUnitTest/index.html) |
| D. 异常 | 模拟导航故障、通信中断与重新同步、不重放旧任务、任务取消、低电量安全返回、掉队、拒绝与人工接管均有实际自动化记录 | [Linux 测试](acceptance/linux_test.log)、[JUnit XML](acceptance/linux_junit.xml) |
| E. 固定导览 | 八站全部完成，最终 `COMPLETED`，22 条状态历史，31 条导航事件；8 次导航完成，19.514 秒，0 次异常 | [运行日志](acceptance/tour_demo.log)、[完整结构化报告](runs/mock-tour-20261119-175848-898487/report.json) |

## 自动化测试详情

| 测试模块 | 通过数 |
| --- | ---: |
| `temi_interfaces` | 6 |
| Backend 抽象契约 | 6 |
| MockBackend | 20 |
| ROS2 Gateway | 12 |
| WebSocket Backend | 16 |
| Gateway CLI | 1 |
| ROS2 ↔ WebSocket 集成 | 1 |
| 导览状态机 | 13 |
| 导览 ROS2 集成 | 11 |
| Linux 合计 | **86** |
| Android JVM（协调器、WebSocket、协议集成） | **18** |
| 总合计 | **104** |

Linux 测试实际用时 35.48 秒，新增的五项 ROS2 端到端用例验证掉队暂停、低电量状态触发虚拟安全返回、断线重连不恢复旧导览、拒绝及人工接管、导航故障到 ERROR 的传播。Android 的 JVM 测试使用模拟 SDK 和真实本机 WebSocket 服务，不调用实体设备。计数来自 [测试汇总](acceptance/test_counts.log)、[Linux JUnit](acceptance/linux_junit.xml) 和 `acceptance/android_junit/` 中的 JVM XML。

## 八站导览实测

| 顺序 | 虚拟地点 | 示例讲解主题 | 导航结果 |
| --- | --- | --- | --- |
| 1 | `entrance` | 展厅入口 | complete |
| 2 | `exhibit_01` | 潮绣 | complete |
| 3 | `exhibit_02` | 潮州木雕 | complete |
| 4 | `exhibit_03` | 潮州工夫茶艺 | complete |
| 5 | `exhibit_04` | 潮剧 | complete |
| 6 | `exhibit_05` | 潮州音乐 | complete |
| 7 | `interaction_zone` | 互动区 | complete |
| 8 | `exit` | 展厅出口 | complete |

报告保存最终电量 93.0%、连接正常、`is_moving=false`、`error_count=0`。上述数字、位置和播报均为 Mock；19.514 秒是加速的演示任务时间，不是实体展厅典型导览时长。互动区 QA 为人工结束或超时继续的状态，尚无知识库问答。

## 构建与 APK 产物

| 工程 | 本次构建 | 产物 |
| --- | --- | --- |
| ROS2 | 3 packages finished [6.09s] | `ros2_ws/install/` |
| 官方 SDK Sample | BUILD SUCCESSFUL in 31s | [sample-debug.apk](../third_party/robotemi-sdk/sample/build/outputs/apk/debug/sample-debug.apk)，6,049,669 bytes |
| Android Bridge | BUILD SUCCESSFUL in 17s；36 项 Gradle 任务执行 | [app-debug.apk](../android/temi_heritage_bridge/app/build/outputs/apk/debug/app-debug.apk)，3,069,871 bytes |

SDK 源码固定 tag `v1.139.0`（`ae1c713cb89ccd9b1e6fe2d497a4e05c1c45edad`），官方工作树洁净。两个 APK 的 ZIP 完整性及 v1/v2 调试签名验证均通过，minSdk 23、targetSdk 30、compileSdk 34；Bridge 包名 `com.heritage.temibridge`，仅声明 INTERNET 权限。证据：[Sample APK 校验](acceptance/sample-debug_verification.log)、[Bridge 构建](acceptance/android_build.log)、[Bridge APK 校验](acceptance/app-debug_verification.log)。Debug APK 尚未安装到任何 Android 或 temi 设备。

## 十二项交付清单

| 交付要求 | 对应项目内容 |
| --- | --- |
| 完整项目目录 | [README 和目录说明](../README.md) |
| 官方 SDK 编译结果 | [SDK API 核对](sdk_api_notes.md)、[重新编译日志](acceptance/sdk_sample_build.log) |
| ROS2 工作空间 | `ros2_ws/`、[构建脚本](../scripts/build_ros2.sh) |
| 自定义 ROS2 接口 | `ros2_ws/src/temi_interfaces/` |
| MockTemiBackend | `ros2_ws/src/temi_bridge/temi_bridge/mock_backend.py`、[独立演示](../scripts/mock_backend_demo.py) |
| WebSocket 通信模块 | `temi_bridge` 的 ROS2 Gateway + WebSocketTemiBackend、[协议](communication_protocol.md) |
| Android Bridge 工程 | `android/temi_heritage_bridge/`、[编译及配置](android_bridge.md)，包含基于真实 SDK 的 SdkTemiDriver |
| 基础导览状态机 | `ros2_ws/src/heritage_tour_manager/`、[导览说明](tour_manager.md)、[展厅配置](../config/exhibits.yaml) |
| 自动化测试 | `tests/`、Android `app/src/test/`、本报告所列实际结果 |
| 环境检查报告 | [环境报告](environment_report.md) |
| 架构设计文档 | [架构](architecture.md)、[开发日志](development_log.md) |
| 下一阶段开发计划 | [下一阶段计划](next_phase_plan.md) |

Linux 的 Mock 后端可以完全独立运行；实体接入方向为 ROS2 Gateway → WebSocketTemiBackend → 私有网络 → Android Bridge → SdkTemiDriver → temi SDK。Android 与 Linux 的协议逻辑分别通过测试，但尚未以实体 Android 设备进行跨设备联调。

## 复现方式

从项目根目录运行：

```bash
bash scripts/build_ros2.sh
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=225 .venv/bin/python -m pytest -q tests
python3 scripts/demo_mock_tour.py
bash scripts/build_android_bridge.sh --rerun-tasks --offline --console=plain
```

官方 Sample 的独立工具链复现步骤见 [开发日志](development_log.md)。固定导览脚本自动生成新的运行目录和结构化报告，不覆盖历史记录。

## 剩余事项与边界

- **已实现并实际验证：** ROS2 接口及三个包、统一 Backend、Mock 导航/停止/播报事件、ROS2 Gateway、私有网络 WebSocket 协议、导览状态机、固定路线及异常处理逻辑、Android 协议/JVM 逻辑和 APK 编译。
- **仅在编译或模拟层验证：** SdkTemiDriver 的真实 SDK 调用、实体 Launcher Ready 和监听器事件、连接实体后的 ROS2 跨设备闭环。`HARDWARE_REQUIRED`：物理运动/停止、真实地图与坐标量纲、避障、传感器、电量及充电、真实 TTS 和 ASR。
- **后续开发，尚未实现：** `visitor_perception`、`heritage_knowledge`、`heritage_dashboard` 三个保留目录；真实游客识别、人数估计、分层讲解、知识问答和可视化控制台。当前低电量只返回虚拟安全入口，不是实机充电。
- **当前阻塞：** 缺少实体 temi；Android Studio 未安装但不阻塞 CLI 构建。生产网络的 TLS、安全权限及长时间运行需要后续专项验证，当前只用于受控本机/私有局域网，不开放公网。
- **下一阶段首选：** 获得 temi 后先做实机通信和安全验证；设备到位前，优先建立可离线测试的游客感知模块，再推进知识库和控制台。见 [下一阶段开发计划](next_phase_plan.md)。
