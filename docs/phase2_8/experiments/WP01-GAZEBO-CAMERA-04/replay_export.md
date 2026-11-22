# WP01-GAZEBO-CAMERA-04 离线回放导出

导出器：[`scripts/export_phase28_replay.py`](../../../../scripts/export_phase28_replay.py)  
播放器：[`visualization/ros_hall/replay.html`](../../../../visualization/ros_hall/replay.html) 与 `replay.js`

## 已导出记录

- 输入：WP01-GAZEBO-CAMERA-04 原始 `capture.json`、30文件归档清单及已校验 tar.gz。
- 模式：`RECORDED_ROS2`；run_id：`WP01-GAZEBO-CAMERA-04`。
- 事件：186；嵌入同源时间戳 RGB 帧：12；Depth 帧元数据：5。
- 回放 JSON：`artifacts/phase2_8/replays/WP01-GAZEBO-CAMERA-04.json`，文件 SHA256：`823bf0a13d6b0f5433f0e84afc26e2b2da027bdbe3e6a06fe703c9861611a3d6`。
- 校验清单：同名 `.json.sha256`；其本身 SHA256：`25d4aab8c916a959d815f41d188f73ef042d147530f8cfb8c69589cba0d3e7d8`。
- 来源归档 SHA256：`c6d55b3144e3b64a4e13896e653b2c622b9606de897768fd5ad0e57e8e7ca064`。
- 记录中没有采集 wall-clock 对照、机器人坐标/速度或游客世界坐标；这些数组和映射明确为空，回放不插值补造。匿名检测框仅在与时间戳匹配的已保存 RGB 图上显示。

## 校验与只读边界

导出器拒绝 run ID/路径不匹配、路径穿越、归档哈希或文件哈希不一致，以及无效run状态。播放器要求同时选择 JSON 与 SHA256 sidecar，重新验证文件、来源 manifest、归档摘要和图片内容哈希。播放器页面没有 fetch/XHR/ROS 控制客户端；播放、暂停、倍速和事件定位只改变浏览器内的本地游标。

Python 定向导出测试 4 项通过，Node 播放器哈希/只读检查通过；用实际 WP01 导出文件再次校验得到 186 events、12 RGB、5 Depth。浏览器 `file://` 预览被本机浏览器策略拒绝，因此本轮没有截图验收；没有尝试绕过该策略。页面可由用户在本机文件管理器打开后手动选择 JSON 与 `.sha256` 文件。
