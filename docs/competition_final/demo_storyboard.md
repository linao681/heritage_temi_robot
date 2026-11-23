# 现场演示分镜（核心段120秒）

更新时间：2026-11-23 20:05 CST。分镜指引实际记录回放/录制，不是现成视频。每个片段使用对应run_id角标，不把不同实验剪成同一轮连续运行。

| 时间 | 画面/操作 | 实际证据 | 屏幕标记与旁白 |
|---|---|---|---|
| 0:00–0:25 | 展厅入口到五区再到出口，展示完整状态序列 | T04 business `visitor-full-20261123-162126`，report SHA `6afc1a912eeb3d95212ecdc643b071c6ad99e197b328e38dc93f1d7eb1be3f31` | `official / business_script / Gazebo / 3 scripted actors / Mock Speak`；Tour 377.088秒 |
| 0:25–0:50 | zone_3队伍掉队、停车、集合和恢复 | 阶段2.9 WP04 `visitor-full-20261123-125818` | `Gazebo scripted team / simulated operator`；LOST→GATHERED 21.42秒，原目标新UUID；非视觉判断 |
| 0:50–1:15 | 真实视觉观察UNKNOWN与停稳证据 | T04 vision `visitor-full-20261123-160651`，report SHA `c8def186c8bc3cd6f5b67fa87e70bb6e8bd106c1fde68bb95ec786d7906f05e0` | `vision_tracker / forward_only / UNKNOWN`；1078条观察全部UNKNOWN；6/6暂停有新鲜odom确认；脚本测试操作员介入 |
| 1:15–1:40 | 展区问答、答案来源和Mock Speak标记 | T04 business同一run，知识条目`music_types` | 展示来源为中国非遗网潮州音乐；播报显示Mock，不播放/宣称实体TTS |
| 1:40–2:00 | 切到RECORDED_ROS2回放时间轴、轨迹与速度 | T08回放 `visitor-full-20261123-125818-run-003`，`replay.json` SHA `3bb0e05025ef67fbfb63beb8d3f9d68bf0803629d295b4d8b058a0aa3372167c` | 真实ROS TF机器人轨迹、Gazebo真值游客轨迹、cmd/odom分栏；无RGB/depth帧；标注历史阶段2.9业务run |

## 本机只读回放启动命令

```bash
cd /home/linao/heritage_workspace/heritage_temi_robot-phase28
python3 scripts/serve_replay.py \
  --recording docs/phase3_0/experiments/T08/replay/visitor-full-20261123-125818-run-003/replay.json \
  --sha256 docs/phase3_0/experiments/T08/replay/visitor-full-20261123-125818-run-003/replay.json.sha256 \
  --port 8126
```

只在浏览器打开`http://127.0.0.1:8126/`；如果端口被占用，先确认其归属并选一个空闲端口。回放服务器不连接ROS、不发送控制命令。浏览器布局视觉验收仍是NOT_RUN；赛前需人工打开页面检查并录制整段。

## 拍摄与剪辑边界

- 素材来自表中四个分离run；保留run_id、场景模式、Gazebo/脚本来源、操作员介入、Mock播报标签。
- 不给未观测人物画检测框；不把Gazebo ModelStates真值当成YOLOX输出；不要填补回放中缺失的相机帧。
- 原片和失败片段应保留；倍速、剪切点和缺帧写入视频说明。
- 本轮没有生成视频或截图。