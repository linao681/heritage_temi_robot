# 游客人数检测：离线评估与实时 ROS 输入

本阶段使用真实公开视频、官方 OpenCV Zoo YOLOX-S ONNX，在本机 CPU 上实际进行匿名 person 类计数。不是 Mock 数字推演，也不是实体 temi 摄像头测试。Python 3.10、OpenCV 4.11.0、NumPy 1.23.5；未额外安装 PyTorch/GPU 推理环境。模型、录像、许可证及 SHA-256 详见 [视觉资产说明](../assets/vision/README.md)。

## 实现与运行

- `person_detector.py`：按固定 YOLOX 模型 640×640 RGB letterbox 输入、8/16/32 多尺度解码，筛选 person 与置信度，NMS 去除重复框；只输出当前帧人数，无人脸识别、身份跟踪、跨帧去重或原始图像输出。
- `video_counter.py`：逐帧解码本地视频，按名义 FPS 计算帧索引时间、选定采样点；无检测结果为 0，推理或解码错误则停止。可变帧率视频的真实时间戳未专项验证，若视频帧总数元数据缺失，OpenCV 无法可靠区分 EOF 与部分解码故障，不能由此推断无人。
- `video_main.py`：CLI 默认只产生 JSON 数值报告；显式 `--publish` 才发布匿名人数。报告保存人数、帧号、视频时间、推理耗时、资产哈希及可选参考计数；已有报告拒绝覆盖。非法模型、视频或参考数据应报错。

从项目根目录执行（目标报告请使用不存在的文件名）：

```bash
bash scripts/build_ros2.sh --packages-select visitor_perception
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
ros2 run visitor_perception offline_video_count \
  --video assets/vision/vtest.avi \
  --model assets/vision/object_detection_yolox_2022nov.onnx \
  --interval 4 --limit 20 \
  --reference assets/vision/vtest_reference.json \
  --output docs/runs/my_vision_benchmark.json
```

默认置信度与 NMS IoU 均 0.5；默认视频采样间隔 0.5 秒，也可使用显式 `--interval`。仅支持本地文件，不接受摄像头索引或网络流。无 `--publish` 时无需 ROS 网络。

## ROS2 输入隔离

| 模式 | 输入人数 Topic（Int32） | 状态 `source` |
| --- | --- | --- |
| 默认 | `/heritage/visitor/count` | `mock` |
| 离线录像专用 | `/heritage/visitor/vision_count` | `offline_video` |
| 相机帧检测 | `/heritage/visitor/camera_count` | `camera` |

三种模式共用 `/heritage/visitor/status` 和 `/heritage/visitor/events`。同一测试域只启动一个感知实例。项目默认 `visitor_perception.count_source: mock` 与 `tour.visitor_assist_enabled: false` 不变；离线录像不会冒充实时摄像头。离线视频不能 arm 或触发导览；录像结束或检测失效，不补发假零人数，状态自然变为 `valid=false`。

## 实时 ROS 图像与深度关联

- `yolox_person_detector` 订阅 RGB `sensor_msgs/Image`，默认 topic 为 Gazebo 实测的 `/depth_camera/image_raw`；`model_path` 默认指向仓库已有 `assets/vision/object_detection_yolox_2022nov.onnx`。launch 参数 `image_topic` 和 `model_path` 可覆盖默认值。
- 节点只发布匿名人数以及 `PersonDetectionArray` 归一化框，不输出图像或身份。默认模型不存在或无法加载时明确报错，不发布伪造计数。
- `depth_association` 配对 RGB 检测与 `/camera/depth/image_raw`、`/camera/depth/camera_info`。只用匹配帧和 CameraInfo 内参计算检测框中心 ROI 的深度中值；深度像素不足或帧不匹配时标记距离无效。未用框大小估算距离。
- `perception_fusion` 汇总稳定游客状态、人员距离、LaserScan、机器人/导航/导览/安全状态，发布类型化 `heritage/perception/fused`。可用下列方式在当前 Gazebo 配置运行感知节点（不会启动 temi 运动）：

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=211 ros2 launch visitor_perception sensor_fusion.launch.py \
  simulation_mode:=true \
  model_path:=assets/vision/object_detection_yolox_2022nov.onnx \
  image_topic:=depth_camera/image_raw
```

实体相机驱动的 RGB/深度 topic、CameraInfo、帧坐标和密度标定仍需 temi 硬件适配及实测；`simulation_mode:=true` 只允许 Gazebo/测试来源进入模拟策略，不是实体运行参数。

独立实际视频回环演示：

```bash
python3 scripts/demo_offline_vision.py
```

演示在本机隔离 Domain 221，启动真实视频计数与监测节点，不启动 Gateway 或导览控制节点。`--publish` 必须同时显式设置 `ROS_LOCALHOST_ONLY=1` 和 `ROS_DOMAIN_ID`。若 DDS 确认超时，CLI 报告 `publisher_ack_confirmed=false`，不把未确认冒称为送达；独立演示逐个核对实际收到的匿名人数和推理结果。最终报告存入 `docs/runs/offline-vision-*`。

## 实际视觉评估（2026-11-20）

视频：OpenCV 4.11.0 `vtest.avi`，768×576、795 帧、10FPS。选择 0、40、…、760 帧共 20 帧，在运行模型前由 Codex 对完整画面独立目视计数。参考文件 [vtest_reference.json](../assets/vision/vtest_reference.json) 只包含数字及计数规则；未由专业人工标注者复核，不是正式金标准。当前报告因此为探索性指标。

| 指标 | 本机实际值 |
| --- | ---: |
| 真实视频采样帧数 | 20 |
| 人数 MAE | 0.40 人/帧 |
| 人数 RMSE | 0.6325 人/帧 |
| 精确计数比例 | 12/20，60% |
| 非空帧被判为零 | 0/20 |
| 单帧平均推理耗时 | 143.62 ms |
| P95 推理耗时 | 155.68 ms |

8 帧少计 1 人，其他 12 帧计数与参考一致；画面遮挡、远处及边缘人群是可能的漏计来源。计数一致不代表逐个人员检测精确率或召回率，也不代表真实展厅准确率。该录像选定样本没有真实空场，故真实无人场景误报率标记未测；另用三个纯色合成空帧分别推理，均输出 0，单独记录，不能外推实际误报率。耗时为本机 OpenCV CPU 单帧预处理+推理+解码的实测时间，不等于实时摄像头端到端延迟。

- [逐帧预测与误差报告](acceptance/offline_vision/benchmark.json)
- [独立合成空帧控制](acceptance/offline_vision/blank_control.json)

## 构建与本机回环验收

- 四个 ROS2 包重新构建成功，最终 `visitor_perception` 包重新安装。[构建](acceptance/offline_vision/build.log) · [重新构建](acceptance/offline_vision/rebuild.log)
- 新增 35 项测试（13 检测、17 视频/指标、5 ROS2 隔离和生命周期）；全量 Linux/ROS2 **156 passed in 59.40s**，无失败、无跳过。[测试日志](acceptance/offline_vision/tests.log) · [JUnit XML](acceptance/offline_vision/linux_junit.xml)
- 独立真实视频回环收到 20 个计数，序列与实际模型预测完全一致；稳定人数从 4 更新至 6，视频停止后状态 `valid=false, people_count=null, source=offline_video`，产生 `arrival` 和 `data_stale`，没有假离开事件，总耗时 12.553 秒。[回环报告](runs/offline-vision-20261120-001026-631467/report.json) · [推理报告](runs/offline-vision-20261120-001026-631467/predictions.json) · [演示日志](acceptance/offline_vision/demo.log)
- DDS 的 `wait_for_all_acked` 在本机超时，但实际订阅端完整接收 20 项；报告保留 `publisher_ack_confirmed=false`，不宣称底层 ACK 已确认。节点退出竞争已通过新增 SIGTERM 生命周期用例验证干净退出。

实际展厅数据、多角度/遮挡校准、专业人工复核、真实空场评估、设备摄像头和实机运动仍待验证；视觉结果不授权移动。下一步无实机期间可开发非遗知识库和离线问答。

## 阶段1 Gazebo 输入检查（2026-11-21）

- Gazebo 实际发布 `/depth_camera/image_raw`、`/camera/depth/image_raw`、CameraInfo 和 `/scan`；深度图为 320×240 `32FC1`，对应 optical frame 和 TF。[传感器报告](runs/phase0-phase1-20261121/gazebo_sensors.json)
- YOLOX ROS 节点用上述 RGB topic 和仓库 ONNX 模型运行，收到一帧人数 `0`。[实际 Topic 输出](runs/phase0-phase1-20261121/yolox_gazebo_count.log) 场景没有行人，这只是模型启动/空场数据通路验证，不是检测精度验证。
- 另一次融合到速度策略的检查使用了明确标记的合成 YOLOX 检测框和标定密度夹具；该结果不等于模型从 Gazebo 图像检测出人。[融合报告](runs/phase0-phase1-20261121/gazebo_fusion.json)
