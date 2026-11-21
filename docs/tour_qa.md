# 3.2 导览知识问答联动

导览进入互动区 `QA` 状态后，接受一次文字提问；查询现有离线知识服务，通过原有 `temi/speak` Action 播报答案或拒答，成功结算后自动继续前往出口。无需网络模型，不需要实体设备。没有提问仍可使用原有 `finish_qa` 或等待 `qa_timeout_sec` 到期。

- 入口：`/heritage/tour/ask`，`temi_interfaces/srv/SubmitQuestion`，字段 `question`、可选 `exhibit`、`level`（默认 basic）；响应 `accepted` 和 `message` 仅表示接收，不等于已完成播报。
- 问题必须非空、最多 256 字符；仅 QA 等待时接收一次。重复请求、导航期间、暂停、播报中等均拒绝。仅可选五个现有展区 ID，层级 basic/advanced。
- 导览内部查询 `/heritage/knowledge/ask`，受 `communication_timeout_sec` 限制。来源不明确或服务异常时播报明确回退提示，不生成事实。已有暂停、恢复、取消、人工接管、低电量、断线控制保留优先级，播报失败保留既有错误处理。若暂停打断问答，恢复时重新执行当前问答段，不自动播放迟到结果。
- `/heritage/tour/status` 增加 `qa_waiting` 和 `qa_result`；后者记录 `found`、`entry_id`、`answer`、`source` 和 `spoken`。收到请求并不代表语音已完成；仅 Action 成功后 `spoken=true`。

## 独立演示

从项目根目录启动：

```bash
bash scripts/build_ros2.sh
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
python3 scripts/demo_mock_tour.py --question '潮剧用什么语言'
```

演示只在本机隔离 ROS Domain 226 启动 Mock Gateway、离线知识节点和导览管理器。无参数时仍按原有手动结束 QA 的路线运行。报告存于 `docs/runs/mock-tour-*/report.json`，包含完整状态和问答结果。

手动测试可在同一运行域内于 `qa_waiting=true` 时调用：

```bash
ros2 service call /heritage/tour/ask temi_interfaces/srv/SubmitQuestion '{question: "潮剧用什么语言", level: "basic"}'
```

本阶段是文本输入、Mock 播报事件与导航测试，非实体语音合成或 ASR 验证；真实摄像头及机器人安全仍需独立验收。知识内容仍须展厅工作人员审校。

## 本机验收（2026-11-20）

- 5 包构建成功（62 秒），[构建日志](acceptance/tour_qa/build.log)。
- 新增 6 项测试（3 状态机及 3 真实 ROS2 联动），全量 **184 passed in 77.71s**，零失败、零跳过。[测试日志](acceptance/tour_qa/tests.log) · [JUnit](acceptance/tour_qa/linux_junit.xml)
- 三独立进程演示：进入互动区后提交“潮剧用什么语言”，命中 `opera_language`，答复“潮剧以潮州方言演唱。”，携带官方资料来源；Mock Action 成功确认 `spoken=true`，随后前往出口。8/8 站，19.965 秒，0 异常。[演示日志](acceptance/tour_qa/demo.log) · [完整报告](runs/mock-tour-20261120-130513-217273/report.json)
- 测试覆盖未知问题、服务不可用回退、重复及非法提问拒绝、取消查询不发送迟到回答。原有手动结束 QA 和超时继续功能仍通过。
