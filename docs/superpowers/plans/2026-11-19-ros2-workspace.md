# ROS2 Workspace Initialization Implementation Plan

**Goal:** 在独立的 `heritage_temi_robot` 项目中建立 ROS2 Humble 工作空间和所需模块目录，并证明 colcon 能够扫描该工作空间。

**Architecture:** Linux 提供 ROS2 应用及 WebSocket Gateway；Android 负责与官方 temi SDK 通信。当前仅建立包目录和职责边界，不宣称未实现的模块为 ROS2 包。

**Tech Stack:** Ubuntu 22.04、ROS2 Humble、colcon、Python 3.10、Android Kotlin。

## Global Constraints

- 不安装系统软件、不修改全局环境、不修改官方 `v1.139.0` 源码。
- `ros2_ws/src` 是 colcon 的唯一源码扫描位置；构建产物留在该工作空间。
- 除已经验证的官方 Sample，所有实机功能均保持 `HARDWARE_REQUIRED`，空目录不视为已实现功能。

## Task 1: 初始化目录和项目入口

**Files:** `README.md`、`.gitignore`、`docs/architecture.md`、`docs/development_log.md`。

**Produces:** `ros2_ws/src/`、六个模块目录、Android Bridge 目录和配置、测试及脚本目录。

- [x] 创建前以 `test -d ros2_ws/src` 验证目录不存在（预期退出码 1）。
- [x] 创建目录：

```bash
mkdir -p ros2_ws/src/{temi_interfaces,temi_bridge,heritage_tour_manager,visitor_perception,heritage_knowledge,heritage_dashboard} android/temi_heritage_bridge config tests scripts
```

- [x] 记录模块职责及当前进度，并添加本地依赖与构建缓存的忽略规则。
- [x] 在 `ros2_ws` 中执行 `colcon list --base-paths src`，实际退出码 0，当前无已实现的包。下一阶段须编写并构建 `temi_interfaces`，不能将空工作空间扫描当作 ROS2 接口编译通过。
- [x] 验证官方 SDK 工作树没有变更，写入开发日志。

本项目尚未初始化独立 Git 仓库，本步骤不进行提交或修改外部仓库。
