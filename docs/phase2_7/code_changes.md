# 阶段 2.7 修改记录

代码基线 `057761908e386f3d0ba7a779d61b860a15debbda`，分支 `main`。本阶段修改仍在工作树，没有 commit/push。以下列出与本阶段任务直接相关的改动和证据。

| 文件/范围 | 修改 | 验证/状态 |
|---|---|---|
| `scripts/phase27_scenario.py`、`scripts/spawn_people_scenario.py`、`scripts/run_phase25_clean_tour.py` | 人物独立 WAIT/APPROACH/HOLD/LEAVE/HOLD_CLEAR 阶段、固定锚点、几何扫掠风险中止、真实 Gazebo 位姿回读、侧向离开选项与保留风险人物 | `tests/test_phase27_actor_motion.py`、`tests/test_gazebo_people_scenario.py`；S01 原配置预测风险失败保留；安全终点最终轮在 Gazebo 完成真实离开 |
| `config/phase27_experiments.yaml`、`scripts/run_phase27_experiment.py` | YAML 场景/速度/时限/方向校验，隔离域与端口、唯一 run 目录、manifest/资源/源码摘要、失败记录和本轮资源清理；安全终点变体指定左向离开 | `tests/test_phase27_experiment_runner.py`、`safe_endpoint_validate.json`；最终运行 `evidence_summary.json` |
| `scripts/analyze_phase27_experiment.py`、`tests/test_phase27_analysis.py` | 从原始事件、采样和 Gazebo truth 生成阶段时间线/距离/速度曲线；限定人物事件窗口；按匹配会话关联停车请求；输出合法 JSON 和明确速度条件 | `analysis_tests_final.log`、`full_suite_final.log`；最终输出 `analysis/{analysis.json,phase_timeline.csv,speed_comparison.csv,distance_speed.svg}` |
| `simulation/navigation.launch.py`、`scripts/start_phase25_system.sh` | Nav2 初始线速度参数透传；同步 FollowPath/smoother 上限；隔离运行日志与启动参数 | `tests/test_phase27_nav_speed_cap.py`；七包构建通过 |
| `ros2_ws/src/temi_bridge/temi_bridge/nav2_transport.py`、`nav2_backend.py` | 将短时未来 TF/odom stamp 控制在有界 150 ms 容忍内，拒绝过期/超边界数据；连接/就绪等待改为有限重试 | `tests/test_nav2_backend.py`、future-skew 日志、全量测试；实际安全终点仿真已通过 readiness |
| `ros2_ws/src/temi_speed_controller/temi_speed_controller/speed_controller_node.py`、`speed_policy.py` | 速度控制同样容忍有界未来时间戳；保留数据新鲜度保护并测试时间偏差边界 | `tests/test_speed_controller.py`、`transport_future_skew_green.log`、全量回归 |
| `ros2_ws/src/heritage_tour_manager/`、`ros2_ws/src/visitor_perception/` | 恢复/状态 UUID 校验与时间门槛；稳定游客启动门控；暂停超时预算覆盖人物路径；融合安全输入时间戳处理 | `tests/test_tour_manager.py`、`tests/test_perception_fusion.py`、`tests/test_phase27_pause_budget.py`；最终单轮完成同目标新 UUID 恢复 |
| `simulation/hall.launch.py`、相机测试 | 临时 URDF 同时供 robot_state_publisher 和 Gazebo 使用；相机高度/俯角配置 | `tests/test_phase27_camera_config.py`；独立 A–D RGB/Depth/CameraInfo/TF 冒烟 |
| ROS 集成测试域选择及相关测试 | 测试支持注入 `HERITAGE_TEST_ROS_DOMAIN_ID`，避免写死占用用户域 | 最新全 tests 目录 487 passed、0 failed、0 skipped；domain230 前后为空 |
| 恢复证据验证与报告 | 按速度控制器 STOP 请求补足请求事件；由原始报告/真值校验近人停车、旧 UUID 确认、新 UUID 同目标恢复；不因 CLEAR 接收晚于新 UUID 单独失败 | `recovery_evidence_red.log`、`recovery_evidence_green.log`、最终 `analysis/recovery_validation.json`；不改写原始 report/truth |

## 明确未验证

- D1 仅有一个安全终点动态运行；0.3 m/s 干扰前标定窗口未达标，未验证 S02–S04。
- E02/E04 横穿/E07、7 轮稳定性、60 秒性能、真实记录回放和实体 temi 未完成。
- 单轮中的几何间隙是二维包络代理，Gazebo 接触观测为 null。
