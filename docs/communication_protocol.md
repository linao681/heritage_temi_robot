# ROS2 ↔ Android temi Bridge 通信协议 v1

## 接入与安全边界

Linux `TemiGatewayNode` 通过 `TemiBackend` 接入 Mock 或 `WebSocketTemiBackend`。Android 是 WebSocket 客户端，主动连接 Linux `ws://<私有IPv4>:8765/temi`。只有 Android 可以调用官方 temi SDK。当前 Linux 端、模拟 Android 测试客户端与 Android Bridge App 均已实现；实际 Android Launcher、真实 SDK 回调及停车行为仍须实体设备验证。

- 默认配置 `gateway.backend: mock`，无网络监听；WebSocket 模式默认只绑定 `127.0.0.1`。
- 允许显式绑定本机的 RFC1918 IPv4 地址，不允许 `0.0.0.0`、主机名或公网地址。不要配置公网转发。开发时仅限可信、隔离的局域网；`ws://` 不加密，真实部署到不可信网络前必须使用 WSS/TLS 及网络访问控制。
- WebSocket HTTP Upgrade 请求必须带 `Authorization: Bearer <token>`。token 来自进程环境变量 `TEMI_BRIDGE_TOKEN`（至少 16 个无空白 ASCII 字符），不得写入 YAML、代码或日志。Linux 只接受一个活动客户端。
- WebSocket 文本帧最大 64 KiB；不接受 JSON NaN/Infinity、无效版本、错误 JSON 或非法状态字段。错误会话关闭并记录日志。

## 握手和状态同步

1. Android 建立带认证头的连接，立即发送：`{"type":"hello","protocol_version":1}`。
2. Linux 返回 `{"type":"hello_ack","protocol_version":1}`，随后发送 `{"type":"state_request"}`。
3. Android 必须在配置的 `ack_timeout_sec` 内返回**完整状态**。SDK 尚未 Ready 时仍应返回 `connected:false` 和真实可知数据，不允许发出控制命令。Ready 后主动推送完整状态。

```json
{
  "type": "state",
  "connected": true,
  "battery_percentage": 82.5,
  "x": 0.0,
  "y": 0.0,
  "yaw": 0.0,
  "navigation_status": "idle",
  "current_location": "",
  "is_moving": false,
  "error_message": "",
  "frame_id": "temi_map"
}
```

电量为 `0~100` 或 `-1`（未知），ROS 标准位置为米、yaw 为弧度；Android 实际 SDK 原始位置量纲尚未实机核实，因此当前仅以 `frame_id=temi_sdk_unverified` 透传，未定位时为 `""`，不得将其用于 metric 控制。示例仅为协议数据，不是真实展厅坐标。每次新的 Ready 会话有 Linux 内部连接代数；旧 ROS Goal 即使已被接受但尚未执行，也不发送到新连接。

## Command、ACK、Event

Linux 发出命令，`expires_at_ms` 为 Unix 毫秒绝对截止时间。双方应同步系统时钟；Android 必须在调用 SDK 前检查过期时间与已处理 ID。ID 由 ROS Goal UUID 或 Linux 产生的独立 UUID 提供，跨连接不得复用。以下 ID 与时间仅为示例，实际由 Gateway 自动生成。

```json
{"type":"command","id":"task_001","command":"navigate","location":"exhibit_01","expires_at_ms":1795069800000}
```

```json
{"type":"ack","id":"task_001","accepted":true,"message":"accepted"}
```

```json
{"type":"event","event":"navigation_status","id":"task_001","status":"going","description":"navigating"}
```

```json
{"type":"event","event":"navigation_status","id":"task_001","status":"complete","description":"arrived"}
```

| Command | 额外字段 | 事件类型 | 终态 |
| --- | --- | --- | --- |
| `navigate` | `location` | `navigation_status` | `complete`, `abort`, `stopped`, `timeout`, `disconnected` |
| `speak` | `text` | `speech_status` | `complete`, `error`, `not_allowed`, `canceled` |
| `stop` | `target_id`（活动任务 ID，无目标时空字符串） | `stop_status` | `complete`, `error` |
| `cancel_speech` | `target_id`（语音任务 ID） | `speech_cancel_status` | `complete`, `error` |

导航中间态为 `start`、`calculating`、`going`、`reposing`；语音中间态为 `started`。所有事件均含 `type:event`、`id`、`event`、`status`，`description` 为可选说明。ACK 中 `accepted:false` 表示拒绝，不调用 SDK；ACK 成功**不等于任务成功**。错误事件类型、未 ACK 的事件、旧连接、过期或已终结事件不执行新状态变更。

### STOP 与取消

- STOP 不与普通导航共享等待队列，必须优先处理；Android 收到合法未过期 STOP 应立即调用 `Robot.stopMovement()`，仅确认停止后反馈 `stop_status:complete`。导航被停止时不再报成功。误入后续目标的迟到 STOP 必须按目标 ID 检查并拒绝过期任务。
- 导航执行或 ACK 超时，Linux 尝试独立 STOP；STOP 超时或拒绝则保持“停车未确认”，禁止新导航。普通状态更新不会自动解除此安全门；须成功 STOP 或建立新的 Ready 状态同步。
- `cancel_speech` 仅针对对应活动语音；Android 使用 `Robot.cancelAllTtsRequests()`（仅允许一个应用播报任务），仅匹配 SDK UUID 的终态才确认取消。未确认取消时 Linux 拒绝新语音，直至重连；Android 仍保留待确认语音槽位，避免重复播报。
- ROS2 Action CANCELED 代表应用取消请求完成，不等价于实体已经停车；不得在未获停止确认时宣称硬件安全。

## 心跳、超时、重复和断线

- RFC6455 WebSocket ping/pong 心跳：Linux 默认每 5 秒 ping，3 秒内无 pong 则连接关闭（Android OkHttp WebSocket 须正常响应）。
- Linux ACK 超时默认 1s，语音完成默认 10s，STOP/语音取消默认 2s；NavigateTo Goal 提供总超时。任务超时可能额外花费有限 STOP 确认时间。
- Linux 保留近期已发送 ID（默认至少 300s 或该任务超时时长），拒绝重复，不自动重发。Android 应维护近期命令 ID 的去重记录，重连不自动执行历史命令；过期命令必须拒绝。
- 连接丢失或 SDK Ready=false 时，Linux 终止活动任务、拒绝离线命令、不缓存控制请求。Android 前台启用连接时自动重连，重新握手并推送完整状态，同时尝试本地停止/取消活动任务，保留尚未确认的隔离状态。连接丢失的 `is_moving:false` 只是不可确认状态，不能证明实机已停车。
- Linux 主动退出时，尽可能先发 STOP 和语音取消，再关闭连接。Android 已实现通信失败、丢失心跳及 SDK 未就绪时的安全调用与状态隔离；真实物理安全策略仍必须实体测试（`HARDWARE_REQUIRED`）。

## ROS2 接口映射（相对名称）

| ROS2 | 类型 | 用途 |
| --- | --- | --- |
| `temi/robot_status` | `temi_interfaces/msg/RobotStatus` | 周期状态快照（默认 10 Hz） |
| `temi/navigation_status` | `temi_interfaces/msg/NavigationStatus` | ID 关联事件 |
| `temi/navigate_to` | `temi_interfaces/action/NavigateTo` | 导航 Goal/Feedback/Result |
| `temi/speak` | `temi_interfaces/action/Speak` | 语音 Goal/Feedback/Result |
| `temi/stop` | `temi_interfaces/srv/StopRobot` | 高优先级运动停止 |

Mock 与 WebSocket 后端共享这些 ROS2 名称，不需要修改导览业务节点。ROS2 本身在本机开发时应限制到独立 Domain 与 loopback；WebSocket 认证并不替代 ROS2 网络访问控制。
