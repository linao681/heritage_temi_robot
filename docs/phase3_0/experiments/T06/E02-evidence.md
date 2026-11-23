# E02 空场/单人/三人实测记录

**任务状态：PASS_WITH_RISK（感知采集和空场/三人全程通过；人群速度因果对照未通过稳定窗门槛）**  
**基线：** `phase2_9-work`，HEAD `f372e3f4e0702470eb91b2a32683e62590777840`；运行时工作树为dirty，详见每轮manifest。  
**数据性质：** Gazebo模型位姿为仿真真值；检测人数/距离来自运行中的视觉/RGB-D链路；cmd_vel、odom和Nav2参数为ROS记录器数据。操作员同意和Mock Speak不属于自主视觉或实体TTS。

## 为何重跑

最初E02-0/1/3的 `run-001` 均走完路线，但记录器用系统ROS时钟减Gazebo仿真时钟，`odom_message_age_sec` 被判成过期，不能用于物理速度结论。修复为Gazebo导览显式启用 `/clock`，实体采集默认保持系统时钟。`odom-clock-red.log` 是预期失败，修复后96项相关测试通过。

后续单人 `run-002` 复现了参与者子进程竞态：Nav2七个目标和Tour Manager均到COMPLETED，但静态人物进程没有在发布者发现前订阅，最终报告 `FAIL` 且未写人物真值。加入 `/odom`、`temi/navigation_status`、`/gazebo/model_states` 发布者匹配门，并将目标等待限制在120秒；修复后100项相关测试通过。新单人 `run-003` 已确认三路发布者和1个演员真值，但Tour Manager随后进入 `机器人通信中断，停止状态未确认`，该轮仍按FAIL保留。

RED/GREEN日志：

- 时钟：`odom-clock-red.log`（预期缺少选项，退出码1，SHA-256 `6c2596d3399d37ba1dff407b6da3c5c95febdc65aeaf742afc5e7f388f4a8d3f`）；`odom-clock-green.log`（96 passed，SHA-256 `7b0e4717a1312fddc19589902c51fc246eba775ccb142156b267bcef2af34ac0`）。
- 发布者就绪：`scenario-readiness-red.log`（预期辅助函数缺失，退出码2，SHA-256 `722742a91b2c1c68fbb13439952d1862a9729d41d2f18a22bbfc673373adc670`）；`scenario-readiness-green.log`（100 passed，SHA-256 `f9aa4aa4149734d0dbbf6b876ec010d25671b8181c22bf745a5dbc55ba155175`）。

## 可比配置与真实场景结果

配置三轮均使用官方布局、`zone_1`触发点、wait→zone_1…zone_5→exit路线、seed 31、机器人限速配置0.3m/s、相机高0.55m/俯角0°。地图/目标SHA：world `275c0b66222ff9dede2f1c9104f51fc755801169f28cfd70f3c2823237e8541e`；map YAML `039fdaf1dd600daece245f0d558c1221a5fa7b407afd8f73319e32170cb89f0c`；PGM `69793ba58c6a8f69ca28c75b2b524cfed006c664019a3e02cbcbb6ea1a5ec615`；goals `4bac876b5c3287a62eded8ec38546b66f5e2ed8ab204924396064e6816332e6f`。

分析窗口取每轮场景模型完成生成后、Nav2目标为zone_1且状态going的记录；无插值。检测人数与Gazebo相机视锥候选人数只做逐样本对照，不把人数称为密度。数值为原始10Hz CSV统计：

| 场景 | 外层/导览状态 | Gazebo真值人数 | zone_1样本数 | 视觉估计人数分布 | 有效人员距离 | 接近人员减速原因 | 独立Nav2限速读回 | cmd_vel中位数 | odom中位数 |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|
| E02-0 空场 | PASS / PASS，7站 | 0 | 221 | 0:221 | 0 | 0 | 0.300m/s，221条有效 | 0.300m/s | 0.2933m/s |
| E02-1 单人 | FAIL / FAIL，业务状态到COMPLETED但失败收尾另见下文 | 1 | 320 | 0:271，1:49 | 50 | 25 | 0.300m/s，316/320条有效 | 0.2842m/s | 0.2824m/s |
| E02-3 三人 | PASS / PASS，7站 | 3 | 261 | 0:200，1:21，2:17，3:23 | 62 | 19 | 0.300m/s，261条有效 | 0.300m/s | 0.2950m/s |

单人真值与视锥候选逐样本人数相等315/320；三人组237/261。三人组视锥候选为3人的23帧、2人的10帧、1人的26帧、0人的209帧；相机只朝前，未观测到的后方游客仍应作未知处理。`crowd_density`没有独立有效记录；控制原因多次为“人群密度未标定，采用默认限速”。所以结果支持“检测链路在部分视野内工作、近距离原因被触发”，不支持自动人数即密度，也不支持已完成E02人群密度调速验收。

采用 `scripts/analyze_phase29_experiment.py` 的原稳定窗条件（至少2秒、20样本、间隔≤0.2秒、低角速度、fresh odom/cmd_vel、独立限速读回），对上述同一zone_1窗口计算：空场最长窗1.305秒/14样本，单人1.524秒/16样本，三人0.907秒/10样本，三者均为 `FAIL: insufficient_stable_window`。三人最长合格候选的odom中位数0.21282m/s、标准差0.03931m/s，误差0.08718m/s；不能用于稳定速度对照。空场、单人、三人Nav2 controller限速读回都保持0.300m/s。因无共同稳定直行窗，且单人轮失败、三人中位odom未低于空场，**没有证据证明人数增加导致物理减速**。不放宽门槛，不把配置值或控制原因当成实测效果。

## Run、失败与清理证据

三轮均用隔离Domain 214、Gazebo端口11400、Web端口8125，串行执行；每轮启动前/后探测域和端口，postflight均为 `other_nodes=[]`、端口可绑定。运行命令模板：

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
.venv/bin/python scripts/run_phase27_experiment.py \
  --config config/phase30_experiments.yaml \
  --experiment E02-0|E02-1|E02-3 --domain-id 214 \
  --gazebo-port 11400 --web-port 8125 --output-dir <新的run目录>
```

- 空场通过：`E02-0/run-002`，运行器/导览均PASS，318.037秒。CSV SHA `4d611cac53b90075fdb6019ba675c24638fe9342bf8eb5d5ca732fc6c37a0623`；report SHA `bc2766239bbe4cffdbab0e9853f3e2613a930ef09556b420b94ebe6edbc50aae`；truth SHA `53d33a42db1b3a02638425ac7ef25c1164753e9037e72f1fb23d8e46bd47ed3b`；manifest SHA `541da0f67dad197159f6d93f4e89c9d6cebc404117d6056ec92dea27048644f8f`（以文件`sha256sum`为准）。
- 单人首次失败：`E02-1/run-002`，Tour Manager日志和CSV有7/7 Nav2完成、最终COMPLETED；但演员子进程未观察到目标并于结束后被超时中断，整体外层/导览报告FAIL，缺人物场景truth。失败CSV SHA `18032a0ac27d95f75c2503f7131b6b6838a78224b5f52658f78d916eacf30cb5`，report SHA `b783ee207140301e2ef9367efc3b15eddfb61634550db5d32bc28220d0274722`，场景日志SHA `352885d9c4e8e47625166e5e15d377b824dff0570cb29a04103ed4d00f11eec4`。
- 单人修复后复测：`E02-1/run-003`，发布者计数均为1，场景truth确认1模型且传感器有50条有效人员距离；Tour Manager随后报告机器人通信中断、停止未确认而FAIL。CSV SHA `fc5544108ea44a9cf303f6499fc4e09245d3fdb090c920c0f52f8b6f25b0b034`；report SHA `0c6a1d314a41c4b2589c8c91488efd0c45da353ba138c53be93e2df3b4388989`；truth SHA `feb3ae93c83cae468a0b3a6d0f7e58471a58e7db56bc254f7e9cda64194db2a1`。
- 三人通过：`E02-3/run-002`，运行器/导览均PASS，324.187秒，7站。CSV SHA `50ac55b4122e976f46eb711dd8748f24140f8b8ef6bb700d63b3e2f76840abb5`；report SHA `52c11ce64b9a1abc824f09e62fa4347935ce91781fc7183599e632d8f0eff7d2`；truth SHA `153269d93160145f816fc656ec4d9d47d9220308e3edf78070f3777a03ba0f95`；manifest SHA `b44533382a78c80b5e4da8a26313313f91dec18930eab7d0486c7ebb8745f544`。

上述运行器日志、manifest、pre/postflight、完整CSV、report、Gazebo truth、scenario/system logs均按run归档。首次无模拟时钟的 `run-001` 数据也保留，但不用于速度真实性结论；五人/散开场景未运行。三人障碍最近距离和人员距离存在混合影响；无接触传感器，不作碰撞安全声明。
