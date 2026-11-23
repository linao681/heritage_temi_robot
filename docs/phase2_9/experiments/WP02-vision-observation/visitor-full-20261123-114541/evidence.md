# WP02保守视觉观察与安全暂停复测

## 实验定义

- 状态：FAIL（完整视觉导览未完成；局部的相机观察、保守停车和过期调速隔离路径得到有效证据）。
- 代码版本：`24c14231de61840a11c5462805df0cd6160af84d` + 未提交的阶段2.9工作树；源码变更摘要见根目录进度文档。
- 运行时间：2026-11-23 11:45:41 CST；45.023秒后由运行器超时结束。
- 场景：official，vision_conservative，3名Gazebo脚本游客。ROS Domain 226；Gazebo端口11377；网页端口8101。
- 数据链：Gazebo RGB → 实际YOLOX检测 → RGB-D距离 → `vision_tracker`匿名轨迹 → `team_observation` → Tour Manager安全暂停。脚本游客真值仅用于场景和网页演示；manifest标记`team_truth_used_for_decision=false`。
- 预期：前向相机不能确认全队时返回UNKNOWN、取消/暂停当前导航、停稳并等待人工确认，不得自动恢复。

## 实际结果

- 运行器完成资源预检：可用内存7.844 GiB、磁盘44.760 GiB、负载0.084/CPU（16核）、无其他Gazebo进程，端口通过绑定检查；ROS Domain 226启动前经项目探针确认为空。
- 接待与同意状态机启动；从入口待命目标开始导航后，在前往zone_1阶段因视觉无法确认队伍而进入`PAUSED`，`pause_source=safety`，目标保留为zone_1，tour记录`team_recovery_required=true`。
- 118条实时面板采样中，110条包含新鲜的视觉团队观察，全部为`UNKNOWN`；其中108条只观察到1人、2条观察到2人，期望人数为3。前向视场范围被明确标注，人工确认标记为true。
- 实际匿名track ID为`vision-e0-1`、`vision-e0-2`；112条有效RGB-D距离记录范围2.241–3.346米。Gazebo真值姿态显示演员仅在8.5–11.3秒有短暂脚本重排，采样路径约1.706、0.301、2.169米；之后停留在初始会合位置。本run没有安排遮挡、离场/重入等受控变化，因此不构成动态团队跟踪验收，也未计算检测精度。
- 网关记录两次“没有活动导航Action”的过期调速请求。服务字段`stale_session=true`后，速度控制器只记录并丢弃这些旧响应，没有将其误报为调速成功，也没有因这两条响应锁存ERROR。STOP阻断、会话不匹配等其他网关拒绝仍按原有错误路径处理。
- 观测不足期间未自动恢复。新鲜odom显示机器人保持静止，融合状态记录`stop_confirmed=true`。这支持本次几何/里程计代理下的仿真停稳结论，不是实体制动认证。
- 完整run在45秒上限处因等待外部操作员确认而超时，未完成后续展区、人工恢复、问答或出口，因此整体FAIL。超时关机后感知数据停止，控制器按失效保护进入ERROR；这是关机期间的传感器过期记录，不是两条过期调速响应导致的ERROR。游客脚本在Gazebo关闭时的`SetEntityState`服务调用失败也记录在`system/visitor_team.log`，不作为游客运动证据。

## 复现命令

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
export ROS_LOCALHOST_ONLY=1
timeout 120s .venv/bin/python -u scripts/run_visitor_full_demo.py \
  --layout official --team-decision-mode vision_conservative \
  --domain-id 226 --gazebo-port 11377 --web-port 8101 \
  --timeout-sec 45 \
  --output-dir docs/phase2_9/experiments/WP02-vision-observation
```

## 证据哈希（SHA-256）

- `live_evidence.jsonl`: `1bf586a2b6d0692dcc5e26bcb33be9f71d7c46363c14775f3841f53a39994e6`
- `manifest.json`: `85b073eeaf5fdb886c44a351f2633fbf0a00fe7f6f7b59d57fe399b63b3c3958`
- `report.json`: `c1b013ae159143f9d9a1457adf1ccae19753ad8effe2e43151ddf2c9b5eaca3c`
- `system.log`: `aa9e4ceb74d666e335eda803de80d6a05943b441471a2fb72296669b61862342`

实验退出后，Domain 226再次由项目探针确认为空，端口11377/8101可重新绑定，未发现残留的本次Gazebo或演示进程。
