# 游客感知与导览联动（2.2：Mock 专用）

联动策略由 `heritage_tour_manager/visitor_assist.py` 执行，与原有导览状态机在同一 asyncio loop 串行处理。`visitor_perception` 仍只提供匿名人数、状态和事件；不控制运动。导览节点使用感知状态快照而非重复、迟到的事件命令，并复用已验证的 ROS2 导航 Action、STOP Service 及控制优先级。

## 工作流程

| 操作/感知 | 结果 |
| --- | --- |
| 工作人员 `arm_visitor` | 准备一次迎宾；必须在此后观测稳定空场 |
| 稳定 0 人 → 稳定正人数 | 进行一次迎宾，记录并发布预期队伍人数 |
| 明确人工 `accept` | 感知确认预期队伍、新鲜且稳定，机器人连接/静止/电量正常时开始路线 |
| `refuse` 或同意超时 | 结束会话、清除预期人数，不重复迎宾 |
| 人数不足、数据失效、心跳中断或持续抖动 | 暂停辅助导览，确认既有停车及 Action 清理 |
| 人数恢复/感知恢复 | 只更新恢复条件，仍保持 PAUSED |
| 明确人工 `resume` | 若恢复条件仍满足，继续中断的同一段路线；失效的旧请求不会自动生效 |
| 人工接管、取消、异常或完成 | 清除队伍，必须重新 arm 才能触发下一次自动迎宾 |

默认保持人工导览；显式手动 `start` 解除尚未使用的 arm，不会把活动的辅助任务换成手动任务。低电量、机器人断线与人工接管等既有保护保留更高优先级；迎宾阶段未获得同意前的低电量会终止辅助任务，不发导航。

## 配置与接口

项目 `config/system.yaml` 中 `tour.visitor_assist_enabled` 默认为 `false`，`visitor_status_timeout_sec` 默认 1 秒。仅显式启用时导览节点增加 `heritage/tour/arm_visitor`（Trigger），订阅 `/heritage/visitor/status`，发布 `/heritage/visitor/expected_count`。辅助模式由导览节点负责设置预期人数，不要同时手工发布该 Topic。

辅助导览状态仍在 `/heritage/tour/status`（String JSON），增加 `visitor_assist` 对象：

- `can_arm`、`armed`、`observed_empty`：能否准备一次迎宾、是否已准备、是否确认过空场。
- `active`、`expected_count`：本次辅助导览是否有效、预期人数。
- `can_accept`、`can_resume`、`waiting_reason`：当前人工操作条件及等待原因。

感知端原有状态兼容新增 `stable`（本次连续样本确认）、`stable_fresh`（最近稳定确认未超过感知超时）。断流由感知状态、稳定确认新鲜度和本机接收时钟 watchdog 共同检测。短时原始人数噪声不会立即当作掉队，但持续不稳定会暂停；未知无效数据不代表无人。

**边界：** `mock_map` 标识和本机测试 Topic 是开发环境边界，不是身份认证或生产安全协议。人数达标也不能证明原队伍成员真正跟随；必须由人工确认恢复。整个联动尚未与实体 temi 或真实摄像头联合验证，生产安全评估仍为 `HARDWARE_REQUIRED`。

## 独立三节点演示

从项目根目录执行：

```bash
bash scripts/build_ros2.sh
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
python3 scripts/demo_visitor_tour.py
```

演示创建专用 Mock 配置、仅在本机隔离 ROS Domain 223 启动 Gateway、游客感知和导览管理器，模拟游客人数并明确调用人工控制服务。流程为迎宾 → 同意 → 掉队停车 → 不满足条件时拒绝恢复 → 重新集合但仍保持暂停 → 人工恢复 → 八站完成。退出仅清理本脚本启动的三个进程；不改变项目的默认关闭配置。每次保存日志和 `report.json` 到 `docs/runs/visitor-tour-*`。

需要人工操作时，应在仅本机的专用 Mock 测试域内启动相同三节点和人数发布器，并先查看 `/heritage/tour/status` 的 `can_arm`，再调用 `ros2 service call /heritage/tour/arm_visitor std_srvs/srv/Trigger '{}'`；`accept`、`refuse`、`resume`、`manual_takeover` 等仍使用既有 Trigger 服务。只有专用 Mock 配置开启联动时该入口存在。

## 实际验收（2026-11-19）

- 四个 ROS2 包完整构建成功；审查加固后导览包再次构建成功。 [构建日志](acceptance/visitor_tour/build.log) · [重新构建](acceptance/visitor_tour/rebuild.log)
- 新增 18 项用例（13 真实 ROS2 三节点、4 状态机竞争回归、1 感知新鲜度），全量 Linux/ROS2 **121 passed in 56.41s**，0 失败、0 跳过。[测试日志](acceptance/visitor_tour/tests.log) · [JUnit XML](acceptance/visitor_tour/linux_junit.xml)
- 独立演示 8/8 站、导览耗时 20.635 秒、全程 21.807 秒（含启动），最终 COMPLETED。第一个展区掉队后确认停止，错误恢复请求被拒，重新集合后人工恢复同一目标。报告记录 9 次导航启动（含重试中断路段）、1 次停止、8 次完成。异常计数 1 是刻意注入的掉队，无未预期错误。 [演示日志](acceptance/visitor_tour/demo.log) · [完整报告 JSON](runs/visitor-tour-20261119-232612-152286/report.json)

2.3 已完成 [公开视频离线行人计数及隔离 ROS2 接口](vision_perception.md)，离线来源不会进入本联动控制；保留 Mock 路径及人工确认门槛。实体安全和真实展厅视觉精度仍未验收。
