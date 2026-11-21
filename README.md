# heritage_temi_robot

潮汕非遗文化展厅智能导览机器人项目：ROS2 Humble + Android Kotlin + temi SDK。

当前处于第二阶段（Mock 优先，第一阶段已验收）。由于尚无实体 temi，真实导航、语音、传感器和避障验证均标记为 `HARDWARE_REQUIRED`。

## 当前进度

- [x] 开发环境检查：Ubuntu 22.04、ROS2 Humble、Python 3.10、colcon。
- [x] 官方 temi SDK `v1.139.0` 源码核对。
- [x] 官方 Sample 编译及 APK 完整性验证。
- [x] ROS2 工作空间及项目模块目录初始化。
- [x] ROS2 自定义接口包构建（2 Message、2 Action、1 Service）；6 项测试通过。
- [x] `TemiBackend` 统一抽象契约及 `temi_bridge` Python 包构建；新增 6 项契约测试。
- [x] MockTemiBackend 独立仿真（持续移动、故障、停止、取消、低电量、语音及断线重连）；20 项 Mock 测试通过。
- [x] ROS2 Gateway 节点（Mock 接入 Action、Service 和 Topic）。
- [x] Linux WebSocket Gateway、认证 JSON 通信、模拟 Android 客户端测试。
- [x] Android Kotlin Bridge 基础 App 编译与 18 项 JVM 测试；实体 SDK 运行仍为 `HARDWARE_REQUIRED`。
- [x] 基础导览状态机及固定八站配置；真实 ROS2 Mock 导览闭环完成。
- [x] 第一阶段统一验收和下一阶段计划（86 项 Linux/ROS2 + 18 项 Android JVM 测试全部通过）。
- [x] 第二阶段 2.1 游客感知：模拟匿名人数、稳定判断、掉队/集合及断流，独立 ROS2 节点和演示（新增 17 项测试，全套 Linux 103 项通过）。
- [x] 第二阶段 2.2 游客感知与导览状态机联动（一次迎宾、人工同意、掉队/失效停车、人工恢复，新增 18 项测试，全套 Linux 121 项通过）。
- [x] 第二阶段 2.3 离线视频/真实视觉人数检测及隔离接入（YOLOX-S 实际推理，20 帧探索性 MAE 0.40 人，新增 35 项测试，全套 Linux 156 项通过；正式人工复核及真实展厅待验）。
- [x] 第三阶段 3.1 非遗知识库与离线问答（五个主题、15 个问答意图、178 项 Linux 测试通过；展陈内容待人工审校）。
- [x] 第三阶段 3.2 知识问答与导览状态机联动（新增 6 项测试，全套 184 项通过，八站独立 Mock 演示完成）。
- [x] 第四阶段 4.1 本机监控与 Mock 人工接管（新增 13 项测试，全套 197 项通过，实际 Tk 窗口与 ROS2 联动已验收）。
- [x] 第四阶段 4.2 本机 Mock 一键启动、健康检查与关停（新增 3 项测试，全套 200 项通过，五节点图形演示完成）。
- [x] 第四阶段 4.3 本机 Mock 连续导览与故障恢复验证（六轮 48 次访问，新增 4 项测试，全套 204 项通过）。

## 项目目录

```text
heritage_temi_robot/
├── ros2_ws/src/
│   ├── temi_interfaces/          # 消息、服务、Action 的接口定义
│   ├── temi_bridge/              # Backend 和 ROS2 / WebSocket Gateway
│   ├── heritage_tour_manager/    # 固定路线导览状态机
│   ├── visitor_perception/       # Mock / 离线视觉人数、队伍与断流状态
│   ├── heritage_knowledge/       # 非遗知识库（下一阶段）
│   └── heritage_dashboard/       # 本机 Tk 监控与 Mock 人工接管
├── android/temi_heritage_bridge/ # Android / temi SDK 接入
├── third_party/robotemi-sdk/     # 官方 SDK v1.139.0
├── config/                       # 项目配置
├── tests/                        # 自动化测试
├── scripts/                      # 开发和运行脚本
├── docs/                         # 架构、API、开发记录
└── .toolchain/                   # 本项目独立 Android 工具链与缓存
```

以上模块目录会逐步变成实际 ROS2 包，只有存在完整 ROS2 包描述和实现，并通过相应验证的模块才标记为完成。

## ROS2 工作空间

在项目根目录中执行：

```bash
bash scripts/build_ros2.sh --packages-select temi_interfaces
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
ros2 interface list | grep temi_interfaces
```

ROS2 Humble 的 rosidl 在中文构建路径中存在兼容性问题，因此 `scripts/build_ros2.sh` 每次创建独立、私有的纯英文 `/tmp` 构建目录并输出其路径；源码、安装产物与日志仍在原工作空间内，不需要修改系统 ROS2。原生 colcon 默认中文构建目录曾实际失败，详见开发日志。

接口测试（独立 ROS Domain，限制为本机通信）：

```bash
ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=231 ROS_LOG_DIR="$PWD/ros2_ws/log/interface_test" \
  python3 -m pytest -q tests/test_temi_interfaces.py
```

构建和验证统一后端抽象：

```bash
bash scripts/build_ros2.sh --packages-select temi_bridge
source ros2_ws/install/setup.bash
python3 -m pytest -q tests/test_temi_backend.py
```

## 独立 Mock 演示

不需要 Android、WebSocket 或实体机器人。修改 `config/system.yaml` 中的 `mock` 配置可调整速度、延迟、故障概率和电量。**所有地点坐标仅用于虚拟地图 `mock_map`**，不会作为真实 temi 地图坐标使用。

```bash
bash scripts/build_ros2.sh --packages-select temi_bridge
source ros2_ws/install/setup.bash
python3 scripts/mock_backend_demo.py
python3 -m pytest -q tests/test_mock_backend.py
```

演示输出实时虚拟位置、电量及导航和 TTS 事件；不产生实际声音或调用机器人硬件。

## ROS2 Gateway

先构建并加载工作空间。默认运行 Mock 后端，不打开网络控制端口：

```bash
bash scripts/build_ros2.sh --packages-up-to temi_bridge
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=230 ros2 run temi_bridge temi_gateway --config config/system.yaml
```

另一个终端载入同一工作空间，设置相同测试 Domain 和 localhost，只在 Mock 下运行：

```bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=230
ros2 topic echo /temi/robot_status
ros2 action send_goal /temi/navigate_to temi_interfaces/action/NavigateTo '{location: exhibit_01, timeout_sec: 15.0}' --feedback
ros2 action send_goal /temi/speak temi_interfaces/action/Speak '{text: 欢迎来到展厅}' --feedback
ros2 service call /temi/stop temi_interfaces/srv/StopRobot '{stop: true}'
```

WebSocket 模式需要项目专属 `.venv`（Mock 不需要该网络依赖）。认证 token 必须通过环境传入；不要写到配置中。默认仍只监听 `127.0.0.1`。

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements-websocket.txt
read -rsp '输入本次 Bridge token: ' bridge_token
TEMI_BRIDGE_TOKEN="$bridge_token" ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=230 \
  .venv/bin/python -m temi_bridge.gateway_main --config config/system.yaml --backend websocket
```

切换 WebSocket 后，须等 Android 握手与 SDK Ready 状态同步才能接受控制；当前 Linux 端已通过模拟客户端的真实回环测试，Android Bridge 工程亦已编译，尚未在实机运行。完整格式见通信协议文档。

## Android Bridge

使用项目现有 Android 工具链构建应用（不修改默认系统 JDK）：

```bash
bash scripts/build_android_bridge.sh
```

APK 位于 `android/temi_heritage_bridge/app/build/outputs/apk/debug/app-debug.apk`。
App 支持手动输入私有 LAN Gateway 地址和 token、认证连接、自动重连、前台控制以及实体 SDK 监听器。18 项 JVM 测试通过（包括真实本机 OkHttp 连接测试与模拟 SDK 反馈）；尚未启动实体 temi，真实导航、停车、坐标量纲与 TTS 为 `HARDWARE_REQUIRED`。

## 完整固定路线 Mock 导览

```bash
bash scripts/build_ros2.sh --packages-up-to heritage_tour_manager temi_bridge
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
python3 scripts/demo_mock_tour.py
```

脚本在本机隔离 ROS Domain 启动两个独立节点，真实执行入口、五个展区、互动区和出口的 Mock 导览，并保存逐状态、导航事件和最终报告。第一阶段独立成功运行：8 站、19.514s、0 次异常。需要人工控制时，可用 `heritage/tour/{start,accept,refuse,pause,resume,cancel,visitor_lost,manual_takeover,finish_qa}` 的 Trigger 服务，详见导览文档。

## 游客感知与导览联动（Mock）

```bash
bash scripts/build_ros2.sh
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
python3 scripts/demo_visitor_tour.py
```

该独立三节点演示使用专用 Mock 配置，完成主动迎宾、显式同意、掉队暂停、拒绝不符合条件的恢复、重新集合、显式恢复及八站导览。实际 8/8 站、导览耗时 20.635s，1 次预设掉队，无未预期错误。默认联动关闭，不连接实体机器人。详见 [2.2 使用说明](docs/visitor_tour_integration.md)。

## 离线真实视觉人数检测

```bash
bash scripts/build_ros2.sh --packages-select visitor_perception
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
python3 scripts/demo_offline_vision.py
```

使用项目本地官方 YOLOX-S 模型及公开视频，实际推理并在隔离测试 Topic 发布匿名人数。收到 20/20 个计数，结束后感知失效，不发运动命令。20 帧探索性目视参考 MAE 0.4 人、精确计数 60%、CPU 平均 143.62ms；未获专业人工复核，不代表真实展厅测评。详见 [2.3 视觉说明](docs/vision_perception.md)。

## 文档

- [游客感知（2.1）](docs/visitor_perception.md)
- [游客感知与导览联动（2.2）](docs/visitor_tour_integration.md)
- [离线视觉人数检测（2.3）](docs/vision_perception.md)
- [非遗知识库（3.1）](docs/heritage_knowledge.md)
- [导览问答联动（3.2）](docs/tour_qa.md)
- [可视化监控与人工接管（4.1）](docs/dashboard.md)
- [本机 Mock 一键部署与操作手册（4.2）](docs/deployment.md)
- [本机 Mock 连续导览与异常恢复验收（4.3）](docs/stability.md)
- [展厅地图转换与仿真环境准备（5.1 进行中）](docs/simulation_setup.md)
- [第一阶段统一验收与交付报告](docs/acceptance_report.md)
- [开发环境检查报告](docs/environment_report.md)
- [第二阶段开发计划](docs/next_phase_plan.md)
- [架构设计](docs/architecture.md)
- [官方 SDK 核对和构建结果](docs/sdk_api_notes.md)
- [ROS2 ↔ Android 通信协议](docs/communication_protocol.md)
- [Android 工程、构建与实机准备](docs/android_bridge.md)
- [固定导览状态机及运行说明](docs/tour_manager.md)
- [开发日志](docs/development_log.md)
