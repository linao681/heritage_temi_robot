# 阶段3.0代码变更记录

初始基线记录于2026-11-23 14:55 CST；以下追加阶段3.0实际改动。

| 日期 | 任务 | 文件 | 变更 | 依据 |
|---|---|---|---|---|
| 2026-11-23 | T01–T03 | `ros2_ws/src/heritage_tour_manager/heritage_tour_manager/{ros_tour_node.py,tour_manager.py}`；`ros2_ws/src/temi_interfaces/{CMakeLists.txt,srv/ConfirmTeamRecovery.srv}` | 增加按暂停事件和session绑定的队伍恢复确认、单次安全恢复凭据、停稳/Action静默状态，隔离旧导航UUID；更新ROS接口。 | RED/GREEN、ROS集成及7包构建见 `experiments/T01/`、`experiments/T01T03/`。 |
| 2026-11-23 | T02–T03 | `scripts/run_visitor_full_demo.py`、`scripts/visualization_bridge.py`、`tests/test_phase30_stop_evidence.py`、`tests/test_phase30_vision_confirmation.py` | 增加限定于本轮Gazebo的scripted_test操作员模式；记录连续新鲜Odom停稳窗口、session和配对导航运动，拒绝单帧/过期/不匹配证据。 | `142 passed`；详见 `test_results.md`。 |
| 2026-11-23 | T04 | `scripts/run_visitor_full_demo.py`、`scripts/start_nav2_gateway.py`、相关测试 | 增加资源/启动等待门、真实恢复事件核对、业务和视觉模式分别验收；修正Nav2启动等待超时。 | vision `160651` PASS_WITH_RISK、business `162126` PASS；vision复跑`164811` FAIL保留。 |
| 2026-11-23 | T05 | `scripts/spawn_people_scenario.py`、`scripts/phase27_scenario.py`、`scripts/run_phase25_clean_tour.py`、`scripts/run_phase27_experiment.py`、`config/phase30_experiments.yaml`、相关场景/运行器测试 | 横穿方向跟随实际导航目标；只在几何风险检查启用时允许演员持续运动；新增阶段3.0 E04配置/输出目录约束。 | E04 run-004 PASS_WITH_RISK及63项测试，见 `experiments/T05/`。 |
| 2026-11-23 | T06 | `scripts/record_phase2_topics.py`、`scripts/run_phase25_clean_tour.py`、`scripts/spawn_people_scenario.py`、`tests/test_phase29_recording.py`、`tests/test_gazebo_people_scenario.py` | Gazebo采集器可显式用`/clock`校验消息年龄；演员等待导航前检查ROS发布者已匹配；静态场景导航等待有界；中断时写FAIL真值。 | 100项相关测试通过；E02-0/1/3真实数据与边界见 `experiments/T06/E02-evidence.md`。 |
| 2026-11-23 | T08预备 | `visualization/ros_hall/ros-live.js` | 增加当前安全停止状态字段展示绑定数据。 | T08最终浏览器回归待执行。 |
| 2026-11-23 | T07 | `scripts/run_phase27_experiment.py`、`scripts/run_phase25_clean_tour.py`、`scripts/spawn_people_scenario.py`、`scripts/check_nav2.py`、`tests/test_phase30_layout_adaptation.py` | adaptive布局参数传递至系统启动与clean tour，目标读取对应地图；check_nav2要求显式匹配域和独立输出路径；新增地图/目标坐标、连通性和布局透传回归。 | 82 passed及adaptive实际Nav2/业务路线见 `experiments/T07/adaptive-layout-evidence.md`。 |
| 2026-11-23 | T08 | `scripts/export_phase30_tour_replay.py`、`visualization/ros_hall/{replay.html,replay.js}`、`tests/test_phase30_tour_replay.py`、`tests/test_phase28_replay.cjs` | 读取原始阶段2.9全程记录，生成RECORDED_ROS2哈希归档；输出ROS TF轨迹、独立标注Gazebo游客真值、真实cmd_vel/odom速度和状态事件；回放页按时间轴绘制位置与速度样本，缺少图像/时间段不插值。 | 8项新增回放测试、34项定向Python回归、Node校验及实际run-003回放SHA验证通过；人工浏览器截图NOT_RUN。 |

本文件只记录阶段3.0实际产生的源码、测试、配置和网页修改。文档/证据变更另见进度及实验记录。不得把已有阶段2.9实现重复算作本阶段新增。
