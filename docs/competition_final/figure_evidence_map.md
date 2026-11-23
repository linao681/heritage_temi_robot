# 图表与证据映射（阶段3.0）

| 图表/画面 | 实际来源 | 可以表达 | 不能表达 |
|---|---|---|---|
| 官方五区业务路线 | T04 `visitor-full-20261123-162126/report.json` SHA `6afc1a912eeb3d95212ecdc643b071c6ad99e197b328e38dc93f1d7eb1be3f31` | Gazebo业务状态机从wait经过五区到exit，Tour COMPLETED、377.088秒；知识问答命中 | 不可说实体temi、真实游客自主同意或真实TTS |
| 视觉UNKNOWN及安全暂停 | T04 `visitor-full-20261123-160651/report.json` SHA `c8def186c8bc3cd6f5b67fa87e70bb6e8bd106c1fde68bb95ec786d7906f05e0` | 1078条观察UNKNOWN；六个停稳证据有新鲜odom和测试操作员恢复 | 不可说视觉队伍检测成功；测试操作员输入不代表自主恢复 |
| E07-A掉队 | 阶段2.9 WP04 run `visitor-full-20261123-125818` report SHA `5d745cb17badc728bda90cfd3f45afddd446e08c905a3681760349f914958ddd` | 脚本演员 LOST→GATHERED 21.42秒，人工确认后新UUID恢复原目标 | 不是视觉掉队识别；非受控前后实验 |
| E04前向横穿 | T05 `E04-CROSS-FRONT/run-004`，CSV SHA `190d73af1b6e47afbc5c22a36853d8ee05d3b765002d160df7abaa56db57cdd1` | Gazebo演员移动；YOLOX/RGB-D人距与Scan共存，策略响应、停车、odom停稳 | 未做纯视觉/纯激光消融；0.544m是几何代理，不是碰撞认证 |
| E02人数对照 | T06 `E02-evidence.md`及各run CSV | 0/3人路线成功、1人轮失败；可报告视觉人数、限速读回和采样窗 | 三人限速仍0.300m/s，稳定窗不足；不得说人群增多引发实速减慢；5人未测 |
| adaptive布局B | T07六目标报告SHA `b8b2dccedee1a4216e63c6b758590fd64b3113fb8396452fcccc93a399aca7b5`；业务报告SHA `378ce074c4488bdbc045618e770fad23996b4f2efe7b5b7b40c4a983ec3114d6` | 6/6 Nav2目标及独立业务全程完成；地图和目标配置对应B | 不代表实体地图、三人视觉跟随或五区业务与导航为同一个run |
| 轨迹/速度回放 | T08 `replay.json` SHA `3bb0e05025ef67fbfb63beb8d3f9d68bf0803629d295b4d8b058a0aa3372167c` | 1269 ROS TF位姿、3813 Gazebo真值游客位姿、2250 cmd/odom样本 | 源数据没有RGB/depth图像；阶段2.9历史business_script，不是T04实时画面 |
| 检测框/真实相机画面 | 当前素材未采集/未导出；T08回放未含图像 | 标注“当前无图像帧” | 不得画伪造bbox或用ModelStates位置伪装YOLOX |
| 成本与实体部署 | [`real_temi_deployment.md`](real_temi_deployment.md)、[`cost_estimate.md`](cost_estimate.md) | 说明依赖、步骤和待询价项目 | 不得编造精确价格或称硬件已有 |

每幅图应带来源、时间、run_id、模式、单位、分母及Gazebo/ROS/脚本/Mock标签。T10完整套件680 passed，七包构建7/7；阶段2.9的624 passed为历史记录。