# Gazebo Nav2 后端接入进展

`temi_bridge.nav2_backend.Nav2Backend` 新增可注入传输层的适配核心：保存地点映射、单任务限制、超时停止、取消停止和只返回模拟播报事件。其 `transport` 必须提供真实导航结果、停止确认、新鲜状态和就绪状态。

已增加 ROS Nav2 Action 传输层（`nav2_transport.py`）及 Gateway 入口 `scripts/start_nav2_gateway.py`：导航经过真实仿真 Action，停止需等待取消终态及新鲜里程计连续静止；未确认则锁定传输层，不能继续发目标。电量为仿真占位值；播报成功仅是模拟事件，不产生音频。

实际 Gazebo 验证：Gateway 接受第一站并到达，前往第二站途中发出 STOP 后收到取消终态、里程计静止且原任务未成功；导览状态机可开始、等待模拟同意并导航，主动取消后返回 IDLE。网页只读接口接收导览状态；问答文字区域已添加，但未在完整导览中实测。[网关验收](acceptance/gazebo/nav2_gateway.json)。

完整五区联动首次实际运行完成入口和前四区；从传承故事前往互动区时 Nav2 多次报告无法前进，最终 ABORTED，状态机进入 ERROR 且记录停止。该次未进入问答或出口；原结构化报告被后续复测覆盖，失败记录保留在 Nav2 日志和本次开发记录中。

后续修复：官方布局的第四至第五区之间加入交接布局中两个通道参考点。实际 Gazebo 全程复测完成入口、五区、知识问答及出口，0 异常，最终静止，总耗时 577.489 秒（包含从互动区回到入口的初始回程）。问题命中并返回来源，播报为无音频模拟。参考点通过真实 Nav2 Action 到达，不更改站点访问顺序。完整报告在 `docs/acceptance/gazebo/submission_tour.json`。本次原始报告的 success 字段因 Python 布尔表达式写成了来源 URL 字符串，后续脚本已修正为布尔值；以状态、访问顺序、问答来源和退出码综合核验本次结果。暂停/恢复、节点失联及多轮稳定性尚待实测。

在已运行 `bash scripts/start_visualization.sh official` 的环境中，另开终端运行 `bash scripts/start_submission_tour.sh official`，该脚本启动网关、知识节点、五区状态机，默认等待人工开始，不自动同意。实际全程自动模拟演练使用 `source /opt/ros/humble/setup.bash && source ros2_ws/install/setup.bash && ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=211 python3 scripts/check_submission_tour.py`；当前已知互动区导航可能失败。
