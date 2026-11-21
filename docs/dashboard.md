# 4.1 本机可视化监控与人工接管

`heritage_dashboard` 为本机 Tk 桌面应用，不开网络控制端口。默认只读；订阅机器人、导航、游客感知和导览状态。虚拟八站地图来自 `config/system.yaml` 的 Mock 地点，不代表真实展厅地图；仅 `mock_map` 有效时绘制机器人位置。过期或不合法的数据标为未知，不继续显示为实时值。

功能包括连接、电量、匿名人数、任务状态、路线访问进度、运行耗时、异常数、机器人告警、近期导航事件、问答结果和来源、最近状态历史。

## 启动

从项目根目录执行：

```bash
bash scripts/build_ros2.sh
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=226
ros2 run heritage_dashboard dashboard
```

只读模式不创建控制服务客户端。显式本机 Mock 调试时才启用人工操作：

```bash
ros2 run heritage_dashboard dashboard --enable-mock-controls
```

两模式均订阅 `/temi/robot_status`、`/temi/navigation_status`、`/heritage/visitor/status`、`/heritage/tour/status`。控制需要本机明确 ROS Domain、新鲜 `mock_map` 机器人和正在运行的导览状态，且机器人连接正常；暂停、恢复、取消及人工接管复用 `/heritage/tour/*` 服务，不发底盘指令。恢复同时要求静止，辅助导览还需 `can_resume`。服务确认/超时不等于机器人已停车；实际状态为准，不自动重试。实体/未知坐标系及过期数据不能操作。`mock_map` 只是测试标志，不是生产认证；实际展厅授权、网络安全和实机验证仍待完成。

## 实际本机演示与验收

```bash
python3 scripts/demo_dashboard.py
```

脚本只在本机 Domain 226 启动独立 Mock Gateway、导览、知识库与游客感知；实际 Tk 窗口接收 ROS2 实时消息，模拟匿名人数 3，保存自身窗口截图及状态报告，结束后关闭本次进程。截图使用系统 `xwd` 与 `ffmpeg`，不是全桌面截图。

- [导航截图](runs/dashboard-20261120-165718-197347/navigation.png)
- [问答截图](runs/dashboard-20261120-165718-197347/qa.png)
- [运行报告](runs/dashboard-20261120-165718-197347/report.json)
- [构建日志](acceptance/dashboard/build.log) · [重新构建](acceptance/dashboard/rebuild.log) · [演示日志](acceptance/dashboard/demo.log)
- 6 个 ROS2 包成功构建；新增 13 项测试（12 模型、1 实际 ROS2 控制），全量 **197 passed in 77.92s**，0 失败、0 跳过。[测试日志](acceptance/dashboard/tests.log) · [JUnit](acceptance/dashboard/linux_junit.xml)

真实 ROS2 集成测试验证监控节点请求暂停并确认虚拟机器人停止，恢复导览后发起人工接管并确认任务结束及静止；首次属性命名冲突已定位并修复，原失败日志保留。运行演示验证实际窗口路线、3 名模拟游客和互动区问答结果。没有实体导航、实机急停、真实游客检测或生产安全认证。
