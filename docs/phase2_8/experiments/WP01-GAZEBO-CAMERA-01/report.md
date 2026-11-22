# WP01-GAZEBO-CAMERA-01：真实 Gazebo 相机链路冒烟

## 判定

**PASS_WITH_RISK（仅限相机推理与观测发布冒烟）**。这不是视觉跟随验收，也不是完整团队导览闭环。

## 运行条件与结果

- 官方展厅 Gazebo，ROS 域 213、Gazebo 端口 11371；三名静态 Gazebo mannequin，场景 `group_static`、种子 281；观测约 12 秒。
- 使用本地 YOLOX-S ONNX、OpenCV DNN CPU 推理，输入 `/depth_camera/image_raw`；模型与相关源文件哈希见 [manifest.json](manifest.json)。场景真值来自 Gazebo `/model_states`，只用于记录 actors，不作为视觉检测输入。
- 共收到 41 帧检测记录，其中 40 帧有效、37 帧检测到人；单帧最多检测到 3 人。深度关联输出在可见样本中为约 3.05–3.14 m，但未人工标框/测量，不能视作准确度指标。
- 团队观察器 41 帧全部为 `UNKNOWN`。这是当前 `forward_only` 覆盖策略的保守结果：看见最多三个人不能证明所有队员都在相机视场内。
- 原始日志末尾记录了结束 ROS context 时的 `ExternalShutdownException` 和发布器 context invalid 异常；节点所属进程组已退出。该清理异常未隐藏，后续需单独检查退出顺序。

## 没有测得的指标

原始记录未保存 RGB 图像帧，也没有逐帧人工框标注。因此 Precision、Recall、人数误差、深度误差、ID switch、可复现的推理 FPS、前/后向覆盖率均不可计算。单次短样本也不证明持续跟踪、遮挡恢复、脚本真值隔离或 Tour Manager 停车/恢复闭环。

## 证据

- [汇总 JSON](summary.json)
- [原始哈希索引](SHA256SUMS)
- 忽略目录中的完整输出：`artifacts/phase2_8/raw/WP01-GAZEBO-CAMERA-01/`（hall、perception、actors、vision samples、Gazebo truth 与 summary）
- 关闭异常可在原始 `perception.log` 末尾核查。
