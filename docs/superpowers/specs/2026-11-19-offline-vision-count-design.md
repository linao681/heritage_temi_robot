# 2.3 离线视觉游客人数检测设计

## 目标与环境

将真实录制视频中的匿名行人检测结果接入已经验证的 `visitor_perception` 数据接口，记录实际人数误差与推理耗时。本地已有 Python 3.10、OpenCV 4.11.0、NumPy 1.23.5 和 ROS2 Humble；未检测到 PyTorch、Ultralytics、ONNX Runtime 或可用视频设备，当前项目内无可用测试视频和模型文件。

不采集人脸、识别身份、持续跟踪个人、默认打开摄像头或用户其他视频文件。输入必须是显式选择的本地公开视频或经授权素材。离线录像不代表现场游客，不允许触发机器人自动迎宾、同意或运动。

## 方案选择

- **推荐：OpenCV DNN + OpenCV Zoo YOLOX-S ONNX。** 使用已有 OpenCV 和 CPU，无需安装 PyTorch、GPU 运行环境或改动系统 Python。官方预训练模型支持 COCO 目标检测，筛选 person 类并做去重，只输出人数。官方说明要求 OpenCV 4.8 及以上，该目录采用 Apache 2.0；模型文件约 34.2 MB。来源：[官方模型](https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_yolox)、[模型文件](https://github.com/opencv/opencv_zoo/blob/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx)。实际运行速度须在本机测量，不提前保证实时 FPS。
- 备选：OpenCV 内置 HOG/SVM 人体检测。无需下载权重，但对于遮挡、俯视、小尺度人群适用性较弱；本轮优先验证深度检测，不并行增加第二套模型。

模型只从官方来源获取，固定版本/提交及 SHA-256，保留许可证和使用来源，保存至项目内单独的视觉资产目录；不采用不明来源权重。

## 实现与数据流

1. `visitor_perception/person_detector.py`：OpenCV DNN 的纯检测适配器，加载固定 YOLOX-S ONNX，在 640×640 输入上按官方模型预处理、解码并筛选 person 置信度及 NMS。默认阈值 0.5、NMS IoU 0.5。区域内每帧人数为当前有效检测框个数，不跨帧累计人次或识别身份。兼容 CPU，检测失败明确报错而不是返回 0。
2. `visitor_perception/video_counter.py`、`video_main.py`：仅显式的本地 AVI/MP4 等视频文件，逐帧解码按可配置采样间隔进行检测，默认每 0.5 秒采样；记录帧号、视频时间、人数、单帧推理耗时和汇总 JSON，不保存视频帧或人脸照片。视频 EOF 正常结束；打不开文件、缺失权重、读帧/推理异常应记录并停止发布，不能把失败误当作无人。
3. 现有 `VisitorMonitor` 增加显式输入源配置：默认 `mock` 仍订阅 `/heritage/visitor/count`；专用离线 `offline_video` 模式订阅 `/heritage/visitor/vision_count`（同样为 `std_msgs/Int32`），均发布现有 `/heritage/visitor/status` 和 `/heritage/visitor/events`，状态 `source` 如实区分。视频 CLI 仅在指定 ROS2 发布模式时发送真实匿名计数，要求仅本机隔离测试域；停止播放后按现有规则标记数据过期。
4. 保持 `VisitorAssist` 仅接受 `source=mock` 的边界。离线录像数据与 Mock 计数分 Topic，在本阶段只能观察感知状态，不参与自动迎宾或控制；测试证明视频数据不能误触发 Mock/实体导航。真实摄像头接入及基于现场视觉的辅助导览需后续单独授权、标定和验收。

## 测试素材与验收

若用户不提供测试视频，优先使用 OpenCV 官方教程提供的公开 `vtest.avi` 行人测试录像（约 7.75 MB，[样本来源](https://github.com/opencv/opencv/blob/4.x/samples/data/vtest.avi)、[教程用途](https://github.com/opencv/opencv/blob/5.x/doc/tutorials/others/background_subtraction.markdown)）。仅在本地测试，固定来源和 SHA-256；不将录像默认作为项目发布素材。其内容不代表实际非遗展厅摄像头视角。

- 自动化：模型输入与输出形状校验、置信度/类别筛选、NMS 去重、空结果、输入错误、采样和统计逻辑；ROS2 模拟与离线源隔离、正确计数发布、EOF/错误后 stale、非 Mock 源不触发导览。
- 实际模型：抽取至少 20 个预先确定、覆盖不同时间段的真实视频帧，由人工独立标注可见行人数，不记录身份；运行模型得到逐帧人数，并汇总 MAE、RMSE、精确计数比例、实际无人帧误报比例（无真实空场样本时明确标为未测）、漏报为零的比例以及平均/P95 推理延迟。可用合成空白图像验证无人控制样本，但不得与真实视频测试混算。
- 实际 ROS2 回环：本地视频检测输出 `vision_count`、离线监测节点发布 `source: offline_video` 及稳定人数，结束后 `valid=false`，监控节点可接收；验证既有人工导览/Mock 联动回归通过。无需实体机器人，且不实际发送导航命令。
- 保存模型/视频来源及哈希、计数标注文档、JSON 运行结果、实际构建与测试日志。复跑此前 121 项 Linux 测试与新增用例。报告实际指标及局限，若性能或准确性不足则记录原因和下一步，而非冒称通过实际展厅部署验收。

实施记录：本机没有独立专业人工标注者，本轮预先选帧后由 Codex 目视作探索性参考，保存数值和规则；正式人工复核仍是后续验收门。最终 [2.3 实际结果](../../vision_perception.md) 明确区分该限制与真实 CPU 推理、ROS2 回环测试。
