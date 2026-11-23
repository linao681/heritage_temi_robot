# 阶段 2.9 基线与执行前环境审计

时间：2026-11-23 01:00 CST  
工作区：`/home/linao/heritage_workspace/heritage_temi_robot-phase28`（现有隔离Git worktree）  
基线分支/HEAD：`phase2_8-work` / `24c14231de61840a11c5462805df0cd6160af84d`  
实施分支：`phase2_9-work`，从以上HEAD创建。主worktree `/home/linao/heritage_workspace/heritage_temi_robot` 仍位于 main / `bdf67d6`。

## Git与代码基线

开始时 `git status --short` 只有本阶段计划目录 `?? docs/phase2_9/`；无 tracked diff，`git diff --stat` 为空。最近8条历史包含阶段2.8提交 `24c1423`。阶段2.8本地/远程分支未移动，不合并。计划原文件保存在本分支，未复制覆盖任何已有文档。仓库内未发现适用于本项目的 `AGENTS.md`；扫描到的 `/home/linao/ros2_ws/AGENTS.md` 属于另一个工作区。

源码基线含阶段2.8匿名IoU跟踪、保守team observer、来源隔离、停车竞态、技术面板、归档器与 `RECORDED_ROS2` 回放。上阶段报告记录七包构建成功、550项pytest通过、WebSocket专项2项通过。它们是阶段2.8历史结果，本阶段修改后必须重跑。

## 工具链

- 系统：Ubuntu 22.04主机，x86_64；内核报告为6.8.0-149-generic。
- ROS：Humble；RMW `rmw_fastrtps_cpp`；ROS安装 `/opt/ros/humble`。
- 项目venv Python：3.10.12。
- 项目ROS install overlay：`ros2_ws/install/setup.bash`。

## 资源与活动进程

审计时 `free -h`：总内存15 GiB，available约5.3 GiB，无swap；根盘可用46 GiB；CPU 16核；load average约13.67/15.80/16.07。`ps -C gzserver,gzclient`发现两个运行中 `gzserver`（约510/477 MiB RSS，各约35% CPU）和一个 `gzclient`（约499 MiB RSS、约18% CPU）。世界命令路径属于主项目目录。未查询或清理其ROS话题、未向其发送控制请求、未终止进程。

候选端口只做localhost bind可用性检查：11361占用；11367、11371、11373、11375空闲。网页端口8098、8091、8093、8095空闲。测试用ROS Domain 232经仓库 `scripts/phase25_preflight.py --check-domain-empty` 实测为空。域232当前只作候选；每次ROS运行前必须重新预检，不能凭本次快照长期复用。

主机当前CPU负载高于可用核数的保守门槛，可用内存低于计划门槛6 GiB，且已经有两套Gazebo。依据阶段2.9计划G0，本轮不启动任何新重型Gazebo实验；此为BLOCKED资源结论，不代表任何实验PASS/FAIL。可并行完成的纯代码审计、状态机/数据测试、离线内容和国赛材料继续推进。

## 端口/域与安全

- 域232：01:00 CST空域探针返回 `other_nodes=[]`。
- Gazebo master 11361已占用；禁止复用。
- 已知运行中的非本次Gazebo服务：PID 19650 gzserver、PID 74958 gzserver、PID 74960 gzclient；仅记录，不拥有，不清理。
- 尚未执行导航、演示、人员生成或实体temi命令；本阶段无实体设备。

## 运行限制

受限执行环境无法读取netlink socket统计，`ss`/`ros2 doctor`网络接口报告给出权限告警；因此端口占用使用localhost绑定探针，ROS域状态使用项目自己的rclpy空域预检。没有因此更改系统权限/网络设置。
