# 固定路线导览管理器

## 状态与流程

`heritage_tour_manager` 只使用 ROS2 Action/Service，不直接调用 Mock、Android 或 SDK。用户通过 ROS2 控制服务触发导览；目前不虚构游客到来检测、人数感知或知识问答。

```text
IDLE → GREETING → WAITING_CONSENT → PLANNING
                       │ 拒绝/超时 → IDLE
                       ▼
       NAVIGATING ↔ EXPLAINING（入口及五展区）
                       ↓
           NAVIGATING → EXPLAINING（互动区） → QA
                       ↓
                 RETURNING → EXPLAINING（出口） → COMPLETED

活动状态 ──暂停/游客掉队──→ PAUSED ──明确恢复──→ 被中断的阶段
活动状态 ──取消/人工接管（停车确认）──→ IDLE
活动状态 ──导航/语音/通信失败、停车未确认──→ ERROR
活动状态 ──低电量──→ RETURNING（配置安全地点）──→ ERROR（提醒人工）
```

每次到达位置后才启动下一段讲解，导航和讲解均等待 Action 最终成功，而非客户端请求确认。暂停时先停止当前运动并结算 Action；恢复后重启当前段（导航从当前位置重新前往目标，讲解从头播报），不自动跳过地点。取消和人工接管不继续原路线；掉队事件目前通过人工控制服务注入，后续游客感知模块接入同一控制接口。

ROS Action 必须返回终态（SUCCEEDED/CANCELED/ABORTED），未知状态和超时未确认终止不能进入正常 IDLE/PAUSED；迟到接受响应由后台尝试取消并阻止同类新 Goal。真实语音取消是否已物理完成和停车是否实际确认仍由 Android/实体测试验证，ROS Action CANCELED 不等同于物理安全。ERROR 后不会自动重试，须人工检查及明确开始新导览。

QA 是人工互动等待状态：工作人员可以明确结束互动，或等待配置的 `qa_timeout_sec`；不声称已经支持实时知识库问答。

## 展区配置

`config/exhibits.yaml` 明确 8 个地点以及每站 `id`、`name`、`temi_location`、`guide_content`、`guide_level`。五个非遗主题是初期样例，最终实际展厅名称、展品内容与真实 temi 保存地点应由工作人员确认。文件不包含真实地图坐标。

示例内容参考中国非物质文化遗产数字博物馆 [潮州非遗知多少](https://www.ihchina.cn/project_details/21784)、[潮州木雕](https://www.ihchina.cn/project_details/14022.html)、[茶艺（潮州工夫茶艺）](https://www.ihchina.cn/Article/Index/detail?id=15247) 和 [潮州音乐](https://www.ihchina.cn/project_details/12554.html)，为本项目自行编写的基础导览文字，不代表实物展陈清单。

| 顺序 | 示例主题 | 虚拟地点 |
| --- | --- | --- |
| 1 | 展厅入口 | `entrance` |
| 2 | 潮绣 | `exhibit_01` |
| 3 | 潮州木雕 | `exhibit_02` |
| 4 | 潮州工夫茶艺 | `exhibit_03` |
| 5 | 潮剧 | `exhibit_04` |
| 6 | 潮州音乐 | `exhibit_05` |
| 7 | 互动区 | `interaction_zone` |
| 8 | 展厅出口 | `exit` |

`config/system.yaml` 的 `tour` 节配置迎宾文本、单段超时、通信超时、同意/互动等待、低电量阈值和安全返回地点。默认阈值 20%，安全返回地点为虚拟入口而非充电桩。低电量时停止常规任务，连接且电量大于 0 时尝试安全返回，成功则 `ERROR/low_battery_returned` 并通知人工；无法返回、通信中断或电量耗尽则 `ERROR/error`，不得宣称已经停车或充电。实际耗电阈值和充电桩映射为 `HARDWARE_REQUIRED`。

## 控制与状态 ROS2 接口

控制服务统一使用 `std_srvs/srv/Trigger`，响应表示是否接收控制请求，不表示导览已完成。实际状态通过 `heritage/tour/status`（`std_msgs/msg/String`，JSON）持续发布。

| 服务（相对 `heritage/tour/`） | 行为 |
| --- | --- |
| `start` | 从已连接且静止状态开始新导览 |
| `accept` / `refuse` | 在 WAITING_CONSENT 同意 / 拒绝 |
| `pause` / `resume` | 暂停 / 显式恢复 |
| `visitor_lost` | 人工注入游客掉队，停车并等待重新集合 |
| `cancel` | 取消当前导览 |
| `manual_takeover` | 请求停车并退出导览，为人工接管留出控制权 |
| `finish_qa` | 结束互动并前往出口 |

状态包含 `state`、`reason`、`outcome`、`target`、`route_index`、`visited`、`elapsed_sec`、`error_count`、`connected`、电量、当前位置、`is_moving`、`safe_return_completed` 和 `history`。`error_count` 记录掉队和终端异常，主动暂停不计异常。

## 运行完整 Mock 导览

从项目根目录构建并加载：

```bash
bash scripts/build_ros2.sh --packages-up-to heritage_tour_manager temi_bridge
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
python3 scripts/demo_mock_tour.py
```

演示脚本仅启动 Mock 后端，在独立本机 ROS Domain 226 启动 Gateway 和 Tour Manager 两个进程；测试客户端真实发送 start、accept、finish_qa，记录状态转换及导航事件。在 `docs/runs/mock-tour-<时间>/report.json` 保存报告和两个节点的日志。停止脚本只结束其启动的进程。

实际最终运行 `docs/runs/mock-tour-20261119-174542-511842/report.json`：COMPLETED，按顺序访问 8 站，8 个独立导航完成事件，22 条状态历史、31 条导航事件、耗时 19.505s、异常 0 次。

也可以单独启动 Gateway 和 `ros2 run heritage_tour_manager tour_manager --config config/system.yaml --exhibits config/exhibits.yaml`；两个终端需加载同一工作空间及相同隔离 ROS Domain。真实导航、语音、避障、游客感知、真实地图、停车与实体恢复仍须获得 temi 后验证。
