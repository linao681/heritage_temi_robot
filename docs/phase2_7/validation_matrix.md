# 阶段 2.7 验证矩阵

基线：`057761908e386f3d0ba7a779d61b860a15debbda`。本轮工作树有未提交修改。此表把历史证据、自动化测试和 Gazebo 实验分开；状态不能由代码实现或单测替代。

| 范围 | 初始条件/预期 | 实际结果 | 数据源 | 状态 | 限制/备注 |
|---|---|---|---|---|---|
| 新增三人完整服务展示 | 入口接待、五区、掉队集合、问答、出口 | 实跑 504.840 s；7/7；三人实际移动约 83.406/82.296/91.146 m；QA 命中并模拟播报；6 次确认前实停及新会话恢复 | `experiments/visitor-full-20261122-202055/{report.json,verification.json,live_evidence.jsonl}` | PASS_WITH_RISK | 脚本游客/操作员，非视觉团队跟踪；不能覆盖下方独立 E07 广泛验收或多轮稳定性缺口 |
| A 运行器与隔离 | 非空域/端口冲突、无效配置、失败保留及只清理自有进程 | 边界测试通过；实验用隔离域和独立目录 | `tests/test_phase27_experiment_runner.py`、`tests/late-fixes-20261122/` | PASS | 不代表任意现场端口均可见；启动前实际 bind 校验 |
| ROS2 七包构建 | ROS 2 Humble | 7 packages finished，退出码 0 | `tests/late-fixes-20261122/ros2_build_final.log` | PASS | SHA256 `a8c2cbc09ecf76690e7e7dcd7ceb9aaa70efdc39340651cac209cdc7797b243d` |
| 全量 Python/ROS 回归 | 完整 `tests` 目录，不忽略文件；Domain 230 | 487 passed，0 failed，0 skipped；187.89 s | `tests/late-fixes-20261122/full_suite_final.log` | PASS | SHA256 `4b301ea5a8db35af23711a2b9d0c04fd7997ea9f52b82664c3a75c1e36163e2b`；Domain 前后为空 |
| WebSocket 缺口专项 | 项目虚拟环境，两个 WebSocket 测试文件 | 19 passed；且包含于最新全量回归 | `tests/websocket-targeted-20261122-032308/websocket.log`、全量回归 | PASS | 不代表 temi 实际连接 |
| E01 无干扰正常五区对照 | 本阶段应单独运行清洁路线 | 两轮均不是独立无人物路线；主证据路线包含动态人物干扰 | `experiments/S01-SAFE-ENDPOINT/20261122T044704Z-S01-SAFE-ENDPOINT-r001/tour/report.json` | NOT_RUN | 不把动态集成路线重复计算为正常对照 |
| 原 S01 readiness/游客准备 | 官方展厅，原 S01 配置 | 7 次尝试：6 次未通过启动或游客状态门槛；1 次进入人物运动后几何中止 | `experiments/S01/` 各 run 的 `status.json`、Tour 报告和真值 | FAIL | 失败记录保留；不可把准备失败计成闭环成功 |
| 原 S01 动态接近 | 人物持续接近，预设终点 1.4 m | `PREDICTED_GEOMETRY_RISK`；实验安全中止、人物保留 | `experiments/S01/20261122T041835Z-S01-r001/tour/scenario/truth.json` | FAIL | 这是几何风险保护行为；不是人物到达终点或恢复通过 |
| S01 安全终点完整导览 | 机器人上限 0.3、人物 0.1 m/s、目标 3.5 m、侧向离开 3.1 m | 两轮人物继续运动、持留和侧向离开；五区/出口均 `COMPLETED`、7/7 目标，用时 320.976 s / 325.411 s | 两个 run 的 `status.json`、`tour/report.json`、`tour/scenario/truth.json`、`evidence_summary.json` | PASS_WITH_RISK | 同一配置两轮；速度标定窗口均不达标；无接触传感 |
| 第二次完整安全终点轮次 | 机器人0.3、人物0.1 m/s，目标3.5 m，向左离开 | Tour `PASS/COMPLETED`；请求至停稳 0.9968 s；最小中心距0.98894 m、几何代理间隙0.17166 m；新 UUID 恢复同一 zone_1 | `experiments/S01-SAFE-ENDPOINT/20261122T101824Z-S01-SAFE-ENDPOINT-r001/{evidence_summary.json,tour/report.json,analysis/analysis.json,analysis/recovery_validation.json}` | PASS_WITH_RISK | 速度条件未达标；接触观测 null；复核源 SHA256 在 recovery JSON 中 |
| 几何风险后的安全终点前序轮次 | 目标 3.5 m，原先向前离开/恢复流程 | 一轮未通过当时恢复判定；一轮报告 `OBSERVED_GEOMETRY_OVERLAP` | `experiments/S01-SAFE-ENDPOINT/20261122T042258Z-S01-SAFE-ENDPOINT-r001/`、`20261122T043735Z-S01-SAFE-ENDPOINT-r001/` | FAIL | 原始目录保留，后续版本才改为侧向离开；不得重标通过 |
| 停车响应/距离 | 与人员距离阈值触发 STOP | 第一轮 0.90065 s，第二轮 0.99681 s；第二轮请求中心距 1.31719 m、事件确认距 1.20457 m、最小中心距 0.98894 m | 两轮的 `analysis/analysis.json` 和 `tour/scenario/truth.json` | PASS_WITH_RISK | 两轮同一配置；几何代理值，不是接触认证 |
| E05 独立危险距离矩阵 | 独立近距场景和重复工况 | 未独立运行；上方两轮综合场景均观察到人员阈值停车 | 主运行分析 | NOT_RUN | 可引用为集成停车事件，不能据此宣称 E05 矩阵验收 |
| E06 离开后恢复 | 停车会话旧 UUID，恢复前安全依据新鲜；原目标继续 | 两轮均同一 `zone_1` 新 UUID 恢复并复核 PASS：`b87d0b…` 与 `a99328…` | 两个 run 的 `tour/report.json`、`analysis/recovery_validation.json`，包含源 SHA256 | PASS_WITH_RISK | 两次同一配置运行；CLEAR 接收顺序按计划不单独作为失败；软件竞态审查见下方 |
| E06 软件与 Nav2 安全审查 | 过期、乱序、并发停车/恢复、UUID、参数回滚等 | 审查 20 项；定向套件 155 passed，适配器 1 passed；本轮全量 487 也通过 | `safety/nav2_review.md`、`audit/task-3-report.md`、`tests/late-fixes-20261122/recovery_evidence_green.log` | PASS_WITH_RISK | 软件边界测试不能替代更多 Gazebo 情景和人工优先级实测 |
| D1 速度标定 | 0.3 m/s 配置；干扰前连续 2 s，容许差 0.05 m/s | 两轮各 20 个样本，覆盖 1.903/1.900 s，中位 `0.0000198/0.0000363 m/s`，均 `met=false` | 两轮 `analysis/analysis.json`、`evidence_summary.json` | PASS_WITH_RISK | 按要求标为速度条件未满足；该档不计已标定通过 |
| D1 多速度矩阵 | S01–S04：机器人 0.3/0.3/0.5/0.7，人物 0.1/0.5/0.25/0.25 | 仅有 S01 安全终点变体两轮；无可比跨档矩阵 | `config/phase27_experiments.yaml` 与上述运行记录 | NOT_RUN | 不报告跨配置速度优劣 |
| D1 阶段/曲线 | MOVING、BRAKING、停车持留、人物离开和恢复 | 阶段计数与 CSV/SVG 已生成 | 主运行 `analysis/phase_timeline.csv`、`analysis/speed_comparison.csv`、`analysis/distance_speed.svg` | PASS_WITH_RISK | 单一工况；未输出满足计划要求的制动 odom 积分和跨配置速度比较 |
| E02 人数增减与限速 | 无人/1/3/5 人及增减序列；感知→策略→Nav2→odom | 未运行 | `config/phase27_experiments.yaml`、本矩阵 | NOT_RUN | 没有真实 YOLOX 人数对照和策略物理贡献证据 |
| E04 A/B/C 人物横穿 | 视觉、激光、双源三种真实轨迹并分别判定子目标 | 未运行 | 本矩阵 | NOT_RUN | 相机传感器冒烟不代表横穿验收 |
| E04 A–D 相机消息冒烟 | 独立 Gazebo RGB/Depth/CameraInfo/TF | 四组消息和 TF 检查通过；B 光轴约向下 10° | `experiments/camera_smoke_verified/{A,B,C,D}/` | PASS_WITH_RISK | 无仿真人物检测、测距误差、召回率或最优安装结论 |
| E07 三人匿名团队掉队 | 稳定计数、真实停等、人工确认、取消优先 | 未运行 | 本矩阵 | NOT_RUN | 未识别个人身份；没有 Gazebo 人工确认记录 |
| 七轮重复导览 | 正常3、动态2、QA1、多人1 个独立 run | 计划 7 种场景配额；共 14 个 S01 系列 run_id，2 个完整路线、12 个失败/未完成；配额未满足 | `stability/repeated_tours.csv` 与各原始 run | NOT_RUN | 不计算稳定性完成率；preflight/启动失败保留并计入分母 |
| 60 s 性能与优化比较 | 同场景/机器/模型窗口，P50/P95 和前后对照 | 未运行 | 本矩阵 | NOT_RUN | 不报告性能收益 |
| LIVE/RECORDED/DEMO 可视化 | ROS 实时/原始记录回放，模式清晰 | 页面保留；回放与模式验收未完成 | `visualization/ros_hall/` | NOT_RUN | 页面静态/演示状态不作为实验数据 |
| 实体 temi | SDK、真实制动、传感器、音频 | 无设备、未运行 | 项目设备状态 | HARDWARE_REQUIRED | 未发送实体运动命令 |

两轮详细摘要及每个原始文件的 SHA256：`experiments/S01-SAFE-ENDPOINT/20261122T044704Z-S01-SAFE-ENDPOINT-r001/evidence_summary.json`、`experiments/S01-SAFE-ENDPOINT/20261122T101824Z-S01-SAFE-ENDPOINT-r001/evidence_summary.json`。历史阶段 2.6 的 355 项回归明确排除 WebSocket 文件，不作为本阶段完整回归口径。
