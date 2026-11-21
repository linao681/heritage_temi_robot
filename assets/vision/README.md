# 离线视觉测试资产

仅本项目离线匿名人数测试。模型与视频二进制文件从官方仓库下载，未用来识别身份，也不属于项目发布素材。

| 文件 | 来源与版本 | SHA-256 |
| --- | --- | --- |
| `object_detection_yolox_2022nov.onnx` | [OpenCV Zoo 固定提交](https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/object_detection_yolox)，从 [OpenCV 官方镜像](https://huggingface.co/opencv/object_detection_yolox/blob/main/object_detection_yolox_2022nov.onnx) 续传；35,858,002 bytes，哈希与上游 Git LFS 指针一致 | `c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063` |
| `vtest.avi` | [OpenCV 4.11.0 官方教程测试录像](https://github.com/opencv/opencv/blob/4.11.0/samples/data/vtest.avi)，795 帧、10fps、768×576 | `45cddc9490be69345cbdab64ca583be65987e864ca408038e648db99e10516cf` |

模型目录官方 Apache 2.0 许可见 [YOLOX_LICENSE](YOLOX_LICENSE)。公开视频仅供本地研究及测试，实际展厅采集须遵循授权及隐私要求。录像不是非遗展厅的实际场景；不要对外重新分发录像。`vtest_reference.json` 仅保存 20 帧匿名目视计数，由 Codex 在未执行模型推理前检查视频作参考，非独立专业人员复核的标签。
