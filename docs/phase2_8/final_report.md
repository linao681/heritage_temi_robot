# 阶段 2.8 最终执行报告（当前快照）

日期：2026-11-23（Asia/Shanghai）  
分支：`phase2_8-work`  
状态：**阶段进行中；软件核心和回归已交付，完整18工作包未完成。**  
主工作区保持原状；未提交、未推送；没有实体 temi；本阶段未修改 Android。

## 结论

匿名视觉跟踪、保守团队观察器、视觉/脚本来源隔离、停车竞态的软件保护、实时技术数据面板、日志归档，以及带来源哈希校验的离线回放均已实现并经过代码/测试验证。最新 ROS2 七包构建、完整 Python/ROS 测试和 WebSocket 专项通过。

实际视觉实验仅为三个静态 Gazebo 人形模型的 RGB-D 观测。对一帧人工框评估显示该帧 YOLOX 检出3/3；不能外推到一般准确率、动态掉队识别或完整团队覆盖。真实记录回放已导出，但未采集机器人/游客世界坐标和速度曲线，且浏览器画面验收未完成。未完成速度标定、E02–E07场景、完整三人导览、稳定性、性能、演示录屏和硬件验证，因此不能把阶段2.8称为全部完成。

## 1–20 项交付核对

| # | 核对项 | 状态 | 真实结果 |
|---:|---|---|---|
| 1 | HEAD与工作区 | 已记录 | 基线 HEAD `bdf67d6dd1e09c503845af11e23a7f2f26b1a508`，分支 `phase2_8-work`；工作树有阶段改动及测试生成的 Mock run 目录；tracked diff 哈希见下方 |
| 2 | 修改范围 | 已记录 | 新增匿名跟踪/observer、Tour来源/竞态、关闭处理、归档和回放工具、证据 API/面板与测试；文件表见[`code_changes.md`](code_changes.md) |
| 3 | 新增功能 | PASS_WITH_RISK | track ID匿名且有时效；UNKNOWN/不完整覆盖需人工确认；脚本 lost 控制与视觉模式隔离；面板显示真实结构化ROS证据；归档和回放校验来源哈希，回放没有控制端 |
| 4 | 实际完成 | PASS_WITH_RISK | WP01部分、WP02来源规则、WP05软件竞态、WP10回归、WP13部分、WP14部分、WP16归档、WP17文档与WP18静态接入清单；逐项见[`validation_matrix.md`](validation_matrix.md) |
| 5 | 未完成项 | IN_PROGRESS | WP03–04、WP06–09、WP11–12、WP15未完成；WP13浏览器长时验收缺失，WP14缺世界坐标/速度数据和浏览器画面验收；实机为HARDWARE_REQUIRED |
| 6 | E02–E07 | NOT_RUN | 本阶段未进行人群拥挤/横穿/速度贡献/完整视觉掉队与恢复场景；WP05只验证软件竞态，不算物理E06验收 |
| 7 | 真实视觉效果 | PASS_WITH_RISK | WP01-GAZEBO-CAMERA-04真实保存12 RGB、5 depth；46/46检测有效，138/138距离关联有效；一张标注帧TP=3、FP=0、FN=0、P/R=1、人数误差0、平均IoU=.923 |
| 8 | 视觉盲区 | 已记录 | 前视相机无法证明后队覆盖；47次team观察均UNKNOWN是正确的保守结果；真值没有输入视觉算法 |
| 9 | 三人掉队 | NOT_RUN | 只有静态三人模型；未运动、遮挡、离开视场或重现；不能宣称掉队识别 |
| 10 | 集合与人工确认 | NOT_RUN | 页面显示当前 observer 要求人工确认；未做“掉队—实停—人工确认—同区新UUID恢复”端到端实验 |
| 11 | 完整导览耗时 | NOT_RUN（本阶段） | 本阶段无入口到五区/出口完整路线。阶段2.7历史504.840秒是业务脚本/模拟操作员结果，保留历史，不当成本阶段证据 |
| 12 | 停车与恢复 | PASS_WITH_RISK | WP05十二类软件竞态测试；没有本阶段Gazebo odom实停/恢复时序，也无实体刹停测量 |
| 13 | 完整测试 | PASS | 最新构建7/7，`tests` 550 passed、0 failed/skip/error，196.49秒；Domain231前后为空。完整日志见[`tests/test_summary.json`](tests/test_summary.json) |
| 14 | WebSocket | PASS | `test_gateway_websocket_integration.py` 与 `test_gateway_cli.py` 专项2 passed、2.37秒；最终在Domain231前后空域运行 |
| 15 | 性能 | NOT_RUN | 未做同场景60秒CPU/内存、推理P50/P95、页面帧率或前后优化对照；消息吞吐3.06Hz不是模型推理FPS |
| 16 | 可视化 | PASS_WITH_RISK | 早先 WP13 真实页面显示 CameraInfo、匿名检测/UNKNOWN、融合、Scan、速度、安全和odom；后加深度有效像素/相机TF摘要有API测试但未重开浏览器核验。无相机视频、独立Nav2限速回读 |
| 17 | 视频/截图 | NOT_RUN | WP13浏览器状态曾核对但截图未归档；本轮播放器 `file://` 预览被浏览器策略拒绝。没有带run_id录屏或2–3分钟精华素材 |
| 18 | 日志治理 | PASS_WITH_RISK | WP01样本归档30文件、464450 bytes、逐文件哈希相同，原件保留；未完成全项目旧日志大小与采样频率统计 |
| 19 | 实体接入准备 | PASS_WITH_RISK / HARDWARE_REQUIRED | Kotlin/ROS接口静态审查清单已交付；本轮无Android改动/构建、无设备。相机/速度/制动/TTS与SDK行为均须实机确认 |
| 20 | 遗留风险 | 已记录 | 前向盲区、单帧评估、未标定密度、Nav2限速读回缺口、无完整路线与物理停止证明；详见[`blockers.md`](blockers.md) |

## 实验和原始证据

- [`WP01-GAZEBO-CAMERA-04`](experiments/WP01-GAZEBO-CAMERA-04/report.md)：RGB-D、人工框、指标边界、30文件归档验证和校验和。
- [`WP13-LIVE-PANEL-01`](experiments/WP13-LIVE-PANEL-01/report.md)：实时API/页面观察、启动预检、原始启动日志及范围限制。
- [`replay_export.md`](experiments/WP01-GAZEBO-CAMERA-04/replay_export.md)：真实 WP01 原始文件哈希复核后的 `RECORDED_ROS2` 回放，186事件、12 RGB、5深度元数据；无虚构位置/速度，播放器只读。
- [`WP05-CONTROL-RACES.md`](experiments/WP05-CONTROL-RACES.md)：软件竞态映射。仿真实停未完成。
- `WP01-GAZEBO-CAMERA-01`旧冒烟、02 setup失败、03采集器失败均保留；没有覆盖失败数据。
- WP13官方厅预检全部通过；ROS Domain231/Gazebo11373/Web8091；未发送导航目标，最终专用域为空。之后新增的TF/深度摘要未重新在浏览器现场核验。

## 最新验证命令与结果

| 验证 | 结果 | 原始记录 |
|---|---|---|
| `bash scripts/build_ros2.sh` | 7包通过，退出0，51.1秒 | [`ros2_build_final.log`](tests/ros2_build_final.log) |
| `HERITAGE_TEST_ROS_DOMAIN_ID=231 .venv/bin/python -m pytest -q tests` | 550 passed，0 failed/skip/error，196.49秒，退出0 | [`full_suite_final.log`](tests/full_suite_final.log) |
| `HERITAGE_TEST_ROS_DOMAIN_ID=231 .venv/bin/python -m pytest -q tests/test_gateway_websocket_integration.py tests/test_gateway_cli.py` | 2 passed，2.37秒，退出0 | [`websocket-final.log`](tests/websocket-final.log) |
| JS 语法、页面运行、播放器只读/哈希检查与真实回放文件校验 | 全部退出0；真实数据186事件、12 RGB、5 depth，controls=false | [`visualization-final.log`](tests/visualization-final.log) |
| WP01归档完整性 | 30/30成员与原始源哈希一致；原件保留 | [`archive_integrity.json`](experiments/WP01-GAZEBO-CAMERA-04/archive_integrity.json) |

最终全套测试前后使用项目预检确认 Domain231 为空。首次尝试曾因 ROS 不支持 Domain234 在 pytest 前失败；随后一轮测试漏设 `HERITAGE_TEST_ROS_DOMAIN_ID`，`test_gateway_cli.py`回退到已有用户ROS图的228而产生一个失败。该轮启动的是测试专用Mock gateway，没有向Nav2发导航目标，也未执行测试中的stop调用。另一次 Domain230 空域预检发现 ROS 命令行守护节点后，在 pytest 启动前中止。所有尝试均保留；最终550项全套与独立WebSocket专项均在231通过，前后空域。首次活动域发现后没有再向228发ROS请求。

本轮没有启动新的动态 Gazebo 场景：基线审计期间域228已有用户 Gazebo/Nav2 系统，主机没有 swap、可用内存约5.5 GiB。为避免并发仿真争抢资源或干扰用户系统，E02–E07、速度标定、整路线和长时性能实验保留为 NOT_RUN；没有停止或更改用户的 ROS/Gazebo 进程。

## Git状态与哈希

- 基线：`bdf67d6dd1e09c503845af11e23a7f2f26b1a508`
- 分支：`phase2_8-work`
- tracked diff SHA256：`c70d5bbd52283ca328e758d5e5315bd7b1d27d14336dc18147fbc241c7a2a12f`，见[`code_changes.md`](code_changes.md)；该值只覆盖Git tracked diff，不含untracked证据目录。
- 无提交SHA（未提交）；未推送。

## 后续顺序

1. 在资源允许且不干扰用户系统时，独立预检空域和端口后完成业务脚本三人入口→五区→出口；单独执行视觉E07-A/B。
2. 完成速度标定，再测E02/E04和动态停车，不用目标速度替代odom实测。
3. 完成稳定性与60秒性能对照；完善WP13截图、TF/深度证据和断源/重连。
4. 为后续真实运行增加位置/速度采样，补回放轨迹/速度曲线；手动打开离线播放器完成浏览器画面验收，再保存真实演示录屏。
5. 有设备后按清单做 Android↔ROS 和实体安全验收。
