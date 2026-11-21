# 开发环境检查报告

检查日期：2026-11-19（首次检查及第一阶段验收复查）。项目路径：`/home/linao/文档/ChatGPT/ican国赛/heritage_temi_robot`。

## 系统与 Linux 开发环境

| 项目 | 初次检查 | 验收复查 |
| --- | --- | --- |
| Ubuntu | 22.04.5 LTS | 22.04.5 LTS |
| CPU | x86_64，16 逻辑核心 | 同左 |
| 内存 | 15 GiB | 15 GiB |
| 可用磁盘 | 约 52 GB | 约 49 GB |
| Python | 3.10.12（`/usr/bin/python3`） | 同左 |
| ROS2 | Humble（`/opt/ros/humble`） | 直接使用；`rclpy` 3.3.21 |
| colcon | 0.20.1 | 可用 |
| Git | 2.34.1 | 可用 |
| CMake | 3.22.1 | 可用 |
| PyYAML | 5.4.1 | 可用 |
| pytest | 6.2.5 | 可用 |
| websockets | 未安装 | 项目 `.venv` 内 16.1.1，系统 Python 仍未安装 |

初始目录仅有历史 colcon 日志，未发现已有项目代码。本工程在独立子目录初始化，未覆盖已有项目。ROS2 Humble 无需重复安装；使用官方 `rosidl_default_generators` 生成接口。项目目录含中文，已实际定位 Humble 内部 CMake 读取生成路径兼容问题，使用 `scripts/build_ros2.sh` 每次创建私有 ASCII 临时构建目录，源码、安装目录、日志保留在项目中，未修补系统 ROS2。

## Android 工具链

| 项目 | 初次检查 | 验收复查 |
| --- | --- | --- |
| 系统默认 Java/JDK | OpenJDK 11 | 仍为 OpenJDK 11，未替换 |
| 构建 JDK | 缺少 17 | `.toolchain/jdk-17`，Temurin 17.0.21.1+2 |
| Android Studio | 未检测到 | 未检测到，当前使用官方命令行 Gradle/SDK 完成构建 |
| Android SDK | 未检测到 | `.toolchain/android-sdk`，API 34 revision 3 |
| SDK 命令行工具 | 缺少 | 22.0（用户提供官方 ZIP，经 SHA-256 校验） |
| Build Tools | 缺少 | 34.0.0，AGP 自动补装 30.0.3 |
| Gradle | 未检测到全局安装 | 项目 Wrapper 8.5，缓存 `.toolchain/gradle` |
| AGP / Kotlin | 未知 | 官方 SDK 配置 8.0.0 / 1.9.20 |
| temi SDK | 尚未克隆 | 官方 `v1.139.0`，`ae1c713cb89ccd9b1e6fe2d497a4e05c1c45edad` |

Android SDK 安装在用户明确同意许可后进行，SDK、JDK 和 Gradle 均位于本项目独立工具链目录，系统 Java、系统 Python、ROS2 及全局环境变量未被修改，不使用未经批准的 sudo。

Android Studio 缺失不阻塞命令行构建；若未来需要界面调试，可另行安装官方 Android Studio 并打开 `android/temi_heritage_bridge/`，Gradle JDK 选择上述 JDK 17，SDK 路径使用项目 SDK。当前没有实体 temi、Android 模拟器或 Launcher 服务运行记录。

## 实际核验记录

- [环境验收原始日志](acceptance/environment.log)
- [ROS2 包与接口核验](acceptance/interfaces.log)
- [ROS2 构建日志](acceptance/ros2_build.log)
- [SDK 源码核对与版本](sdk_api_notes.md)
- [Android Bridge 构建说明](android_bridge.md)
