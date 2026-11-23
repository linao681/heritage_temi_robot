# E04 前向横穿复测证据

状态：`PASS_WITH_RISK`（本轮官方布局五区导览与前向横穿闭环完成；接触安全未经认证）  
时间：2026-11-23（本地时区，UTC 记录见 `manifest.json`）  
分支/基线：`phase2_9-work`，HEAD `f372e3f4e0702470eb91b2a32683e62590777840`；记录同时包含本地未提交源码。  
实验：`E04-CROSS-FRONT`，run `run-004`，ROS Domain 207，Gazebo 11395，Web 8120，`ROS_LOCALHOST_ONLY=1`。

## 结果

- 运行器状态 `PASS`；导览状态 `COMPLETED`，实际路线为 `wait → zone_1 → zone_2 → zone_3 → zone_4 → zone_5 → exit`，总耗时 315.714 秒。
- 中途知识问答命中知识库条目 `music_types`，来源为中国非物质文化遗产网“潮州音乐”；模拟播报状态为 `spoken=true`。本结果不代表实体 temi TTS。
- 横穿演员在收到 `zone_1` 活动导航 UUID `cc43550ddb5647a0af3900a9098268fd` 和新鲜运动里程计后启动。演员航向按当前导航目标方位修正为 1.269947 rad，轨迹来自 Gazebo `/model_states` 回读：55 个样本、累计 3.000005 m，移动约 13.159 秒。
- 横穿时间窗内记录 131 条实验采样：YOLOX/RGB-D融合的人员距离有效 102 条，检测人数为 1 的 101 条；最近人员距离 1.188 m。距离降至 1.922 m 时出现“接近游客，按距离减速”；约 1.280 m 时出现“近距离人员停车”，同时激光障碍距离约 1.075 m。
- 随后 Nav2 安全停车被确认。确认窗口内 42 条样本均为 `cmd_vel_linear_x=0`，里程计线速度绝对值最大约 0.0063 m/s。演员继续运动；Gazebo碰撞包络代理显示横穿阶段最小间隙 0.544 m、停车后最近中心距 1.424 m；未触发几何风险中止，未观察接触传感器（系统没有接触传感器）。
- 视觉人员距离与激光障碍距离在近距离停车时同时有效，因此本轮能证明检测、人员距离调速、停车和停稳，但不能把最终停止归因成“纯视觉”或碰撞认证。
- `zone_1` 安全暂停后使用新 UUID `9292323b7db74279a451f3da767e077f` 到站；出口附近另有一轮安全暂停并恢复，最终到达出口。其余关键 UUID/状态和时间戳见 `tour/report.json` 与原始 CSV。

## 失败尝试保留

- `run-001`：启动器拒绝当时未开放的 crossing 连续运动选项。
- `run-002`：演员启动遇到缺少 `start_distance_m` 字段。
- `run-003`：场景采集有效，但运行器按固定七站路线执行，300 秒超时。
- `scenario-heading-red.log`：航向辅助函数尚未实现时的预期 RED。
- `preflight-E04-run4/preflight.txt`：首次端口探针命令转义错误；随后独立的 `port-bind-check.txt` 成功。未将上述失败记录覆盖。

## 可复核证据与 SHA256

- `manifest.json`：`72328a6dcadf7bc79900beaa7c685eedfbb6047629eb032139faf34aaf9f11bf`
- `config.yaml`：`d0f7ab5de19b6a30e8bd596b5456215f8dc459aaa0a218ba1454f974d2804761`
- `tour/report.json`：`cfdba1e6ea9278715322b993cce1546a3f7af40e3aa3d8793df98e4fbd9cbdf2`
- `tour/experiment_data.csv`：`190d73af1b6e47afbc5c22a36853d8ee05d3b765002d160df7abaa56db57cdd1`
- `tour/scenario/truth.json`：`dd589d2586fa2153ffa072051a1c4501888e5270ab6ce3d11b87f7d1cbdbfccc`
- `logs/system/navigation.log`：`90dd4d529fbec80d1a25f083a51d8848f659b04ee1883715be62a4454caf857e`
- 收尾复核：Domain 207 DDS 探针为空；11395/8120 均可重新绑定，记录在 `postflight-domain.json`、`postflight-ports.txt`。

复现实验命令：

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
.venv/bin/python scripts/run_phase27_experiment.py \
  --config config/phase30_experiments.yaml \
  --experiment E04-CROSS-FRONT \
  --domain-id 207 --gazebo-port 11395 --web-port 8120 \
  --output-dir docs/phase3_0/experiments/T05/E04-CROSS-FRONT/run-005
```

复跑前须选择新的空目录并重新检查空闲 Domain 和端口，不能照抄本记录的资源值而不复核。
