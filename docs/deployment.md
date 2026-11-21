# 4.2 本机 Mock 一键部署与联调

## 操作手册

在项目根目录先构建（首次安装或修改 ROS2 包后）：

```bash
bash scripts/build_ros2.sh
bash scripts/start_mock_system.sh
```

默认仅本机通信，使用 ROS Domain 218、虚拟机器人、模拟感知和只读监控台；不会自动迎宾、接受游客同意、启动导览或采集真实摄像头。显示「系统就绪」后进入待机。关闭监控窗口或按 Ctrl+C 结束运行。

自动演示（仅模拟游客）：

```bash
bash scripts/start_mock_system.sh --demo
```

无图形环境：

```bash
bash scripts/start_mock_system.sh --headless --demo
```

演示明确模拟 3 名游客、迎宾、同意、八站导览、互动区问题「潮剧用什么语言」、知识库带来源的答案及播报、继续到出口。完成后自动结束进程。无 `--demo` 时不发布模拟人数、不自动调用导览服务。

连续演练（同一组节点，1–6 轮；不重置虚拟位置或电量）：

```bash
bash scripts/start_mock_system.sh --headless --demo --rounds 6
```

每轮必须完成八站、问答、三名稳定模拟游客以及出口静止检查，并观察终态一秒；只有本次明确指定的下一轮才开始，不重试失败任务。默认仍只演示一轮。

## 手动操作

如需在待机模式显式开始模拟导览，在另一终端进入项目根目录：

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=218
ros2 service call /heritage/tour/start std_srvs/srv/Trigger '{}'
# 界面显示 WAITING_CONSENT 后，明确同意本次模拟导览
ros2 service call /heritage/tour/accept std_srvs/srv/Trigger '{}'
# QA 状态才允许文字提问
ros2 service call /heritage/tour/ask temi_interfaces/srv/SubmitQuestion "{question: '潮剧用什么语言', level: 'basic'}"
```

## 健康检查与日志

启动程序先检查指定 Domain 中是否已有其他节点，避免干扰现有系统；如需使用另一个独立本机 Domain，可添加 `--domain 217`（手动控制终端需使用相同值）。

运行期间检查节点发现、导览控制和知识问答服务可用、三路新鲜状态、Mock 坐标系、初始 IDLE，以及知识库实际查询和来源。待机和演示持续监控心跳与子进程退出。节点异常退出或启动超时会结束本次系统，不自动重启或重放任务。

每次运行独立生成 `docs/runs/mock-system-*/`：

- `system.yaml`：该次强制 Mock 配置副本，原始项目配置不变；
- 各节点独立日志及 ROS 日志；
- `report.json`：模式、节点就绪、导览/游客/机器人状态、错误及子进程退出码。连续演练保留每轮独立快照与总耗时；故障报告中的状态是关停前最后收到的状态，不代表已确认停车。

退出顺序为监控台、导览管理器、游客感知、知识库、Gateway；保留 Gateway 供导览管理器完成关闭期间的取消/停止处理。只结束本次脚本启动的进程。异常或被迫终止时报告失败。

**当前验收边界：** 仅本机 Mock 系统。此启动入口不支持实体 SDK 后端、跨机网络控制、自动接管真实机器人或生产部署认证，实体安全验证另行进行。

## 实际验收

- 图形演示：五节点就绪，八站全部完成，19.956 秒，0 次异常，知识问答有来源且模拟播报成功，三名模拟游客，最终虚拟机器人位于出口且静止，全部子进程正常退出。[运行报告](runs/mock-system-20261120-170735-903000/report.json)
- 终端演示：[运行报告](runs/mock-system-20261120-170713-749564/report.json)
- 默认待机及正常退出：[运行报告](runs/mock-system-20261120-170737-162906/report.json)
- 全量测试：**200 passed in 104.27s**。新增配置隔离、完整一键演示、默认待机关停 3 项测试。
- 图形演示初次退出发现导览线程关停竞争，修复 SIGINT/SIGTERM 的处理方式后再次完整演示通过。[历史失败报告](runs/mock-system-20261120-170636-020223/report.json)
