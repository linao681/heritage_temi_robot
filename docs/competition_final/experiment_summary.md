# 阶段2.9实验摘要

## 阶段3.0权威更新（2026-11-23 20:10 CST）

当前工作树：`phase2_9-work`，HEAD `f372e3f4e0702470eb91b2a32683e62590777840`；本轮阶段3.0改动未提交、未推送、未合并。旧的阶段2.9文字和624项测试均为历史快照，不覆盖下表结论。

| 证据项 | 阶段3.0结果 | 边界 |
|---|---|---|
| official/business_script完整导览与知识问答 | PASS，`visitor-full-20261123-162126`：入口同意、五区、QA、出口，COMPLETED，377.088秒；3名Gazebo脚本游客，5次停稳后新UUID同目标恢复 | 同意、脚本游客、集合操作员输入为模拟；播报是Mock/字幕 |
| vision_conservative整路线与保守停车 | PASS_WITH_RISK，`visitor-full-20261123-160651`：官方布局完整到出口，331.287秒，6次视觉UNKNOWN安全暂停均有新鲜odom停稳确认 | 1078条团队观察均UNKNOWN；使用测试操作员确认；不能声称视觉队伍跟踪成功或自动掉队识别 |
| E07-A掉队恢复 | PASS_WITH_RISK，阶段2.9原始run `visitor-full-20261123-125818`：zone_3 LOST→GATHERED为21.42秒，模拟操作员确认后同目标新UUID恢复并完成导览 | Gazebo脚本团队，不是视觉判断；非固定条件前后对照 |
| E04前向横穿 | PASS_WITH_RISK，T05 `E04-CROSS-FRONT/run-004`：YOLOX/RGB-D人员距离、激光障碍同时有效，近人策略响应、Nav2停车、odom停稳、演员继续移动 | 视觉/激光未做独立消融；0.544m是仿真几何代理，无接触传感器或实机认证 |
| E02人群 | PASS_WITH_RISK，T06空场/三人全程PASS，单人失败 | 三人限速仍为0.300m/s；稳定直行窗未达门槛，无证据证明人数增加导致实速降低；5人/散开未跑 |
| adaptive布局B | PASS_WITH_RISK：Nav2六目标6/6、172.510秒；独立业务全程COMPLETED、194.035秒 | 一名入口演员，业务同意由测试脚本触发，Mock Speak；非视觉团队/E07验收 |
| ROS记录回放 | PASS_WITH_RISK：真实旧run导出6050事件、1269个ROS TF机器人位姿、3813个Gazebo真值游客位姿、2250个cmd/odom速度样本；SHA验证及只读HTTP检查通过 | 来源为阶段2.9业务脚本run；无RGB/depth原图，桌面浏览器视觉验收NOT_RUN |
| 全量回归 | PASS：阶段3.0完整`tests/` 680 passed、0 failed、0 skipped；七包构建7/7 | Domain 220前后为空；pytest SHA `91af50f880851a035f8d7d316a32662d7219bdd8b98ab084c92e22823f3ed837`；624 passed仍是阶段2.9历史快照 |
| 实体Temi | HARDWARE_REQUIRED | 当前无实体机器人；SDK底盘运动、实体制动、ASR/TTS和现场安全未验证 |

数字用途仅限对应run及其来源。T10全量自动化回归已通过；历史阶段数据不能补齐阶段3.0未运行的E02/E04子场景或浏览器/硬件验收。

---


## 核心仿真实验

| 实验 | 结果 | 证据摘要 |
|---|---|---|
| WP01 official/business_script完整导览 | PASS，1轮 | `visitor-full-20261123-104955`。三名Gazebo脚本演员、模拟操作员同意/集合；wait/五区/exit 7/7，QA命中，最终COMPLETED。6个移动目标802条新鲜cmd_vel/odom配对样本；6次停稳/恢复有新旧UUID。Tour计时523.617秒，run总计时536.929秒。 |
| WP02视觉模式尝试1 | FAIL | `visitor-full-20261123-110241`。完整演示120秒超时；真实相机输出`sample_age_sec=inf`导致TeamObserver JSON严格序列化崩溃，关停阶段停车未确认。原始失败保留。 |
| WP02视觉模式尝试2 | FAIL（局部真实视觉输出） | `visitor-full-20261123-111123`。实际YOLOX/RGB-D获得track；32条接口采样，29条团队观察UNKNOWN，2–3个可见track、4个匿名ID、62个有效距离值；演员没有移动。wait目标启动时调速命令被网关拒绝，控制器ERROR，关闭时停车未确认。 |
| WP02诊断尝试3 | FAIL | `visitor-full-20261123-113050`保留导航Action取消与“无活动导航Action”调速拒绝日志；该次只定位，不计为动态视觉通过。 |
| WP02域预检尝试 | FAIL（未启动） | `visitor-full-20261123-114400`因域227仍发现此前`ros2 node list`创建的CLI条目，在启动前拒绝；无Gazebo、事件数0。 |
| WP02视觉安全暂停复测 | FAIL（局部安全观察通过） | `visitor-full-20261123-114541`。118条实时采样，110条真实视觉团队观察均UNKNOWN（108次1/3，2次2/3），112条有效RGB-D距离2.241–3.346米。安全暂停并确认停稳；两条无活动Action的过期调速响应被标记丢弃，没有因此锁存ERROR。45秒时仍等待外部操作员确认，演员仅有短暂脚本重排，没有受控动态情景，未完成视觉导览。 |
| WP02视觉真实相机复测 | FAIL（真实UNKNOWN与安全停稳子结果） | `visitor-full-20261123-133255`：845条视觉团队观察全部UNKNOWN，818条只见1/3、21条2/3、5条短暂3/3但因forward_only仍UNKNOWN；848/850条深度样本新鲜，距离2.224–3.345m。暂停样本801条，800条有新鲜odom停稳证据。运行停在zone_1，未外部恢复或完成路线；handler漏记已定位并修复，见run内`evidence.md`。 |
| E07-A专用业务脚本部分运行 | FAIL（操作员中止） | `visitor-full-20261123-121915`。用户要求结束时已完成入口及zone_1–4，正在前往zone_5。六段暂停都有匹配session的停稳/新鲜odom；末次队尾落后4.735m，约201.7秒后才集合，初始追赶路径68个0.2m网格waypoint。恢复后仍在导航时中止，没有出口、完整E07-A或终端停稳结果。该次用Gazebo脚本演员/模拟操作员，不属于视觉验收。 |
| WP04 freshness修复后完整路线 / E07-A脚本闭环 | PASS（完整Tour）/ PASS_WITH_RISK（集合效率） | `visitor-full-20261123-125818`完成wait/五区/exit；Tour 381.869s、runner 396.386s。zone_3 `LOST`→`GATHERED` 21.42s、峰值lag4.7428m，模拟操作员确认后同目标以新UUID恢复。出口新鲜odom 0.001129m/s。三名脚本演员与模拟字幕；新run team log没有actor XYZ，非固定seed对照。详细证据和SHA见WP04 run `evidence.md`。 |

WP02八阶段动态人员场景仍未运行。当前实验没有测试遮挡、出视野、重入或深度故障，也没有人工标注准确率。视觉run虽证明真实图像管线能返回UNKNOWN并触发安全停稳，不能表述为动态团队观察或完整视觉导览通过。

## 其他工作包结果

- E02拥挤限速：0/6；E04横穿：0/3；速度标定：0/3；E07-B：0/1；adaptive布局B Nav2：0/1；实体Temi：0。
- WP03有WP01脚本团队集合与恢复局部证据，以及本次被中止的专用E07-A部分run；视觉模式人工确认后恢复仍未完成。WP08未做持续接近/故障注入；WP09官方布局A随WP01通过，布局B未跑。
- WP04修复前partial run观察到约201.7秒集合等待；654个Gazebo位置样本显示路径速度下界0.0651m/s。修复要求读回样本晚于SetEntityState服务确认后，在`visitor-full-20261123-125818`完整导览中zone_3 LOST→GATHERED为21.42秒；这是改善迹象而非固定条件因果比较。新run没有actor XYZ，不报告新步速；安全距离和人工确认未放宽。

## 自动化与软件验证

- 最新ROS2七包构建：7/7通过。
- 服务接口变更后网关/速度控制器定向回归64项通过。
- 最新完整`tests/`目录624 passed，190.10秒，退出码0；包含视觉pause-handler修复，运行前后Domain 226均由项目探针确认为空。日志SHA-256 `609b53c935b48363831dd1cafd4200112991db64f5932cd81c179e5d5db52d74`，见`docs/phase2_9/audit/full-regression-20261123-1351.log`。此前622项及pause-handler专项20项保留为历史验证，不与最新全量结果相加。
- ROS2七包构建7/7；接口变更后的网关/速度控制器定向64项通过。619 passed（12:11）是早期修复前回归，不再作为最新结果；此前中断修复专项18项和失败记录仍保留。
- 定向回归144项、离线测试子集506项、WebSocket本机专项19项、全仓607项收集均保留为历史运行记录，不与最新全量测试重复累加。
- 全仓607项曾成功收集；“收集”不代表执行。当前执行完成的完整套件为624项。
- 速度窗分析器9项、记录器契约22项、只读回放安全7项的软件测试及JS/Shell/Python语法记录见`docs/phase2_9/progress.md`与`audit/verification-attempts.md`。

## 数据来源边界

WP01演员状态来自Gazebo脚本业务模拟；WP02跟踪来自真实Gazebo相机图像经过YOLOX/RGB-D，演员仅短暂脚本重排、样本量短，团队真值未用于视觉结论。视觉模式返回UNKNOWN是正确的保守结果。阶段2.7的504.840秒属于历史演示，不计入阶段2.9。
