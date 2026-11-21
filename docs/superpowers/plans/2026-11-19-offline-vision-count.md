# Offline Vision Visitor Count 2.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以真实公开视频验证匿名行人计数、误差与延迟，并隔离接入现有 ROS2 感知接口。

**Architecture:** OpenCV DNN 本地 CPU 推理适配器 + 视频逐帧采样和报告 + 可选仅本机 ROS2 离线计数发布；现有 VisitorMonitor 保持 Mock 默认，通过专用输入 Topic 区分录像。

**Tech Stack:** Python 3.10、OpenCV 4.11.0、NumPy 1.23.5、ROS2 Humble、pytest。

## Global Constraints

- 设计经用户确认：[2.3 设计](../specs/2026-11-19-offline-vision-count-design.md)；不打开摄像头、不处理用户未指定文件、不保存人脸或图像、不跟踪身份；所有机器人运动仍禁用。
- 官方 YOLOX-S ONNX 固定 OpenCV Zoo 提交 `48b10fa505aeb51fbd127fc60a5c660040e823b7`，SHA256 `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063`；测试视频 OpenCV 4.11.0 `vtest.avi`，记录本地哈希及来源许可。
- 默认 Mock Topic、导览规则与实体 SDK 均保持。工程内无可用 Git 仓库；不初始化或创建提交。

### Task 1: 真实检测适配器

**Files:** `ros2_ws/src/visitor_perception/visitor_perception/person_detector.py`, `tests/test_person_detector.py`。

**Interfaces:** `preprocess(frame) -> (blob, ratio)`；`decode_person_boxes(output, ratio, frame_shape, confidence=0.5, nms=0.5)`；`YoloXPersonCounter(model, confidence=0.5, nms=0.5).count(frame) -> int`。

- [x] 写失败测试：BGR uint8 变为 RGB NCHW 640×640，padding=114；构造 8400×85 输出含同一人的重叠框、另外一个人、非 person 类和低置信度行，期望两人；形状/NaN/空帧/缺模型失败，不产生假零。
- [x] 运行新增用例，确认模块不存在。
- [x] 依官方模型实现 CPU DNN、640 letterbox、8/16/32 stride、类别分数与 NMS；再次运行相同测试，加固概率张量检查。

### Task 2: 本地视频采样与指标

**Files:** `ros2_ws/src/visitor_perception/visitor_perception/{video_counter.py,video_main.py}`, `setup.py`, `tests/test_video_counter.py`。

**Interfaces:** `sample_video(path, count, interval_sec=0.5, limit=None, on_sample=None)` 产生记录 `frame_index`, `video_sec`, `people_count`, `latency_ms`；`summarize(samples, reference=None)` 输出延迟和计数误差；CLI `offline_video_count --video FILE --model FILE --output JSON [--interval SEC --limit N --reference JSON --publish]`。

- [x] 写真实合成 AVI 的采样/EOF/错误用例及计数指标用例（样本参考 0/2/3、预测 1/0/3：MAE 1、精确比例 1/3、空图误报 1/1、非空判零 1/2）；非法路径/间隔/参考不完整应报错。
- [x] 运行新增用例，确认缺失实现失败。
- [x] 实现显式文件读取、采样、停止原因、数值报告（不储存帧），CLI 可选 `--publish` 要求 `ROS_LOCALHOST_ONLY=1` 和明确 ROS Domain，按视频时间节奏向 `/heritage/visitor/vision_count` 发布匿名人数；测试通过。参考 JSON 结构、唯一帧号和哈希检查；DDS 确认单独记录。

### Task 3: ROS2 输入隔离

**Files:** `ros2_ws/src/visitor_perception/visitor_perception/{visitor_monitor.py,ros_visitor_node.py}`, `config/system.yaml`, `tests/test_vision_ros.py`。

**Interfaces:** `VisitorConfig.count_source` 为 `mock`/`offline_video`；两种模式订阅各自的 Int32 Topic，status 中 source 正确标记。`VisitorAssist` 仍只接受 Mock 来源。

- [x] 真实 ROS2 测试两种输入模式隔离：同时发原有 count 与 vision_count，错误 Topic 不应影响状态；离线正确输入稳定人数并在停流后过期；三节点测试只启用离线感知时辅助导览 arm 拒绝且不运动。
- [x] 执行测试先失败（缺失 source 配置）。实现配置、Topic 选择及来源标记后，`bash scripts/build_ros2.sh --packages-select visitor_perception`，安装后回归新增用例；新增 SIGTERM 退出回归。

### Task 4: 真实模型验证、ROS2 演示与完整回归

- [x] 在推理前从公开录像固定抽取 20 个预先确定帧号（10fps，0、40、…、760），由 Codex 目视计数，记录参考 JSON、来源、哈希及标注局限（未经人工复核）。
- [x] 实际执行 `offline_video_count --video assets/vision/vtest.avi --model assets/vision/object_detection_yolox_2022nov.onnx --interval 4 --limit 20 --reference assets/vision/vtest_reference.json --output docs/acceptance/offline_vision/benchmark.json`，输出真实逐帧人数、MAE、RMSE、精确比例、零误报、非空零漏报和平均/P95耗时；另运行合成空帧控制。真值参考于推理前已保存；本批没有真实空场，明确未测。
- [x] 新增并执行 `scripts/demo_offline_vision.py`，独立监测进程 + 实际视频计数进程仅在 Domain 221 发布和接收，验证 20/20 匿名数值对应、source offline_video、停止后过期；未启动 Gateway 或 Tour，不发送运动命令。报告 `docs/runs/offline-vision-20261120-001026-631467/`。
- [x] 四包构建、全量回归（156 passed）及 JUnit，检查模型哈希、独立报告、测试结论；更新 README、架构、感知说明、视觉使用说明及开发日志，标明真实展厅/硬件待验证。
- [ ] 后续正式验收：安排独立人工标注复核、实际无人场景及真实展厅摄像头的数据集评估；不能以本次探索性测试替代。
