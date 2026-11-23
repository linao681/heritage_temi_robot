# T07 adaptive布局B实际验证

时间：2026-11-23（本机日志时间；UTC起始时间见运行器 manifest）  
分支/HEAD：`phase2_9-work` / `f372e3f4e0702470eb91b2a32683e62590777840`  
状态：`PASS_WITH_RISK`

## 静态地图与网页坐标

- 使用 `tests/test_phase30_layout_adaptation.py`、`tests/test_hall_conversion.py`、`tests/test_phase27_experiment_runner.py`、`tests/test_gazebo_people_scenario.py`；共 `82 passed`，日志 `layout-green.log`，SHA256 `9e5c40eff39bab4fa7c905b9a9922a5291caedc12f4bb5dfa1e3a6447fee725a`。
- RED日志 `layout-red.log` 保留新增布局运行器辅助函数尚不存在的失败，SHA256 `ca54eda5b0022b3c4d8a194f3bc68dfd5cb83a780a3bbd922f14dbd0b2805426`。
- 静态校验重建的 official/adaptive 世界、地图图像、YAML和目标点；检查地图原点/分辨率、机器人净空、目标坐标映射和连通分量，并将 Three.js 页面布局目标坐标与 ROS goal 坐标逐点比对。world 生成文件只容许结尾换行差异。
- Adaptive 地图 YAML SHA256：`a47880970c529e4f7efbbc6d928c800e2578fa307cd194e1fc35a0528383e82f`；目标 SHA256：`e01a6ed814ebb745a23f86d0ca6266fe1134fa65c71fe804d625a3c8747ed25a`；见 `adaptive-key-target/run-001/layout-hashes.txt`。
- `run_phase27_experiment.py` 将布局传给现有系统启动器与 clean-tour；TourEvidence、静态人物布置和check_nav2显式读取对应布局文件。配置拒绝未知布局仍由现有布局/实验验证测试覆盖。

## 实际 Nav2 导航

启动前使用 Domain 214、Gazebo 11400、Web 8125；ROS DDS检查为空、端口可绑定、当时没有其他 Gazebo/Nav2。可用内存和磁盘记录在 `adaptive-key-target/run-001/resources-before.txt`。运行后 Domain 214 空，11400/8125可重新绑定。

独立站点检查命令：

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=214
.venv/bin/python scripts/check_nav2.py --layout adaptive --domain-id 214 \
  --output docs/phase3_0/experiments/T07/adaptive-key-target/run-001/navigation.json
```

zone_1 Nav2结果状态4（SUCCEEDED），实际停稳，目标误差 `0.2226 m`，耗时 `16.916 s`；报告SHA256 `85eb9bba87c1f4a7de17796a062e921f76e9aa731ec47a787a835b4084f77aa9`。同一系统随后 `--full-tour` 六个目标全部成功，均有新鲜odom停稳证据：

| 目标 | Nav2状态 | 目标误差 | 用时 |
|---|---:|---:|---:|
| zone_1 | 4 | 0.223 m | 2.638 s |
| zone_2 | 4 | 0.227 m | 29.534 s |
| zone_3 | 4 | 0.235 m | 35.792 s |
| zone_4 | 4 | 0.218 m | 27.788 s |
| zone_5 | 4 | 0.204 m | 45.615 s |
| exit | 4 | 0.209 m | 31.143 s |

全路线Nav2耗时 `172.510 s`，报告SHA256 `b8b2dccedee1a4216e63c6b758590fd64b3113fb8396452fcccc93a399aca7b5`。地图与目标SHA被写入每份Nav2报告。此段是导航验收，不代替业务状态机验收。

## Adaptive完整业务路线

使用新配置 `adaptive-business-tour.yaml`，运行器 `run_phase27_experiment.py` 通过预检后将 adaptive 参数传入系统，Tour Manager采用 `business_script`。运行器结果 `PASS`；状态机访问顺序为 `wait → zone_1 → zone_2 → zone_3 → zone_4 → zone_5 → exit`，耗时 `194.035 s`，error_count为0。导览入口同意由测试运行器调用accept服务，仿真系统报告一名到达演员（Gazebo模型真值）；本轮不是三人掉队闭环。

互动区问题“潮州音乐有哪些类型？”命中知识条目 `music_types`，回答“潮州音乐大致分为广场乐和室内乐。”，来源为中国非物质文化遗产网·潮州音乐；Speak Action标记为模拟播报，未验证实体temi TTS。

- Run：`adaptive-business-tour/run-001`
- 独立运行manifest SHA256：`746a8cea244b667000a794512e6484b31f4e35af638637012933eb2017f3f7ef`
- Tour report SHA256：`378ce074c4488bdbc045618e770fad23996b4f2efe7b5b7b40c4a983ec3114d6`
- 真实记录CSV SHA256：`3e54819859ee5e87ff3503b80f74c3f4e3cc734034ec8dd1fbce8ffba75caf6e`
- Gazebo入口演员真值 SHA256：`f02123c2ac8e7fdd2264a779be3030ab36b6cc3feb5689b38a92301ff295b731`
- 系统启动日志 SHA256：`665e7a4201137096d0064fefb404f7a3870b98a52fc1087c81a5d6325bd5eafc`
- 运行前空域与端口记录在 `run-001/preflight.json`；收尾在 `postflight-domain.json`、`postflight-ports.txt`：DDS `other_nodes=[]`，两端口可绑定。

## 失败与限制

- 最初安全shell预检因ROS setup尚未执行时启用未绑定变量检查而退出；随后按正确顺序重新预检并启动。未创建仿真进程。
- 完整Nav2独立路线与完整业务路线分别运行，不能把前者当成后者。业务路线中的“团队模式”为 `business_script`，但只确认一个入口Gazebo演员；没有执行视觉团队判断、E07掉队或三人协作。
- 仿真地图/轨迹成功不等于实体temi地图或硬件导航验证；实体设备仍为 `HARDWARE_REQUIRED`。
