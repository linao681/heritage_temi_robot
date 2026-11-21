# 游客感知模块（2.1：Mock 与 2.3：离线视觉匿名人数）

`visitor_perception` 是独立 ROS2 包。它将模拟或真实离线视频人数观测转换为稳定人数、团队人数状态和去重事件，自身不调用导览控制，不连接 Android 或实体 temi。2.2 可在专用 Mock 配置下由 [导览联动策略](visitor_tour_integration.md) 订阅 Mock 状态；2.3 [离线视觉检测](vision_perception.md) 使用隔离输入 Topic，不触发导览。仅使用匿名区域人数，不采集人脸或保存个人身份。

## 接口

| Topic | 类型 | 方向与含义 |
| --- | --- | --- |
| `/heritage/visitor/count` | `std_msgs/msg/Int32` | 输入模拟区域人数（非负整数） |
| `/heritage/visitor/vision_count` | `std_msgs/msg/Int32` | 输入本地离线视频实际检测人数，仅在 `count_source=offline_video` 模式接收 |
| `/heritage/visitor/expected_count` | `std_msgs/msg/Int32` | 输入预期队伍人数；0 停止本次队伍监测 |
| `/heritage/visitor/status` | `std_msgs/msg/String` | 输出 JSON 实时状态（每 0.2 秒或输入更新时，默认配置） |
| `/heritage/visitor/events` | `std_msgs/msg/String` | 输出 JSON 状态变化事件，含 `event` 字段与当前状态 |

状态示例：

```json
{"valid": true, "people_count": 2, "expected_count": 3, "group_state": "lost", "source": "mock", "stable": true, "stable_fresh": true}
```

`group_state` 分为 `untracked`（未监测队伍）、`unknown`（未获有效稳定评估）、`following`（观测人数达到预期）、`lost`（观测人数不足）。`following` 只表示匿名人数达标，不能确认是原队伍成员或正在跟随机器人。

`source` 由启动配置 `count_source` 决定：默认 `mock` 只订阅 `/count`，专用 `offline_video` 只订阅 `/vision_count`；同一测试域只启动一个实例。两模式都发布状态，导览策略明确拒绝 `offline_video` 来源。

默认连续 3 个同值观测才能改变稳定人数；超过 2 秒未收到合法观测置为无效（`valid=false`、`people_count=null`）。在合法但不稳定的抖动输入下保留最后稳定值；`valid=true` 不代表最新原始输入与稳定人数一致。2.2 新增 `stable`、`stable_fresh`，持续变化且超过超时也判定稳定确认不新鲜。负数输入不刷新观测超时并重置连续判断。预期人数变化后等待下一次稳定观察；重复发送相同预期人数不重复报警。

| 事件 | 触发 |
| --- | --- |
| `arrival` | 首次稳定正人数或稳定零人数变为正数 |
| `departure` | 稳定正人数变为零 |
| `visitor_lost` | 已设置预期人数后，稳定人数首次低于预期 |
| `regrouped` | 掉队后稳定人数重新达到预期 |
| `data_stale` | 合法观测断流，数据过期（不当作无人） |
| `data_restored` | 过期后重新获取稳定观测 |

## 构建与运行

从项目根目录运行：

```bash
bash scripts/build_ros2.sh --packages-select visitor_perception
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
python3 scripts/demo_mock_visitors.py
```

演示自动使用仅本机通信的独立 ROS Domain 224、启动独立安装态节点，模拟 0 → 3 → 2 → 3 → 0 人及预期人数变化，再测试断流和恢复。演示退出时清理其启动的节点，不需要机器人。每次运行保存独立报告于 `docs/runs/mock-visitors-*/report.json`。

手动运行节点时需要在各终端加载 ROS2 工作空间、设置相同的本机 ROS Domain：

```bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=224
ros2 run visitor_perception visitor_perception --config config/system.yaml
```

另一终端（同一工作空间、同一 Domain，且不要同时运行演示脚本）：

```bash
ros2 topic pub --rate 5 /heritage/visitor/count std_msgs/msg/Int32 '{data: 3}'
```

通过 `ros2 topic echo /heritage/visitor/status` 和 `ros2 topic echo /heritage/visitor/events` 观察结果。独立感知模式可使用 `ros2 topic pub --once /heritage/visitor/expected_count std_msgs/msg/Int32 '{data: 3}'` 设置预期人数；联动模式由导览节点设置该 Topic。停止人数发布后会自然产生断流事件；独立感知节点不会调用导览服务。

## 实际运行记录（2026-11-19）

- 四个 ROS2 包完整重新构建成功：[构建日志](acceptance/visitor_perception/build.log)。
- 16 项纯 Python 测试及 1 项真实 ROS2 Topic 集成测试通过。
- 第一阶段 86 项及新增 17 项完整回归：**103 passed in 36.87s**，无失败或跳过。[测试日志](acceptance/visitor_perception/tests.log) · [JUnit XML](acceptance/visitor_perception/linux_junit.xml)
- 独立进程演示观察到六个预期事件：`arrival → visitor_lost → regrouped → departure → data_stale → data_restored`；最终 0 人、有效、无队伍跟踪，未发送任何机器人运动命令。[报告 JSON](runs/mock-visitors-20261119-223622-137782/report.json) · [演示日志](acceptance/visitor_perception/demo.log)

**后续：** 2.3 已完成离线视频实际检测及隔离回环（[视觉报告](vision_perception.md)）；仍需专业人工标签复核、真实展厅摄像头校准和实体物理安全验证（`HARDWARE_REQUIRED`）。
