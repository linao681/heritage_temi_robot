# 阶段 2.8 执行进度

执行分支：`phase2_8-work`，基线 HEAD `bdf67d6dd1e09c503845af11e23a7f2f26b1a508`。工作区 `/home/linao/heritage_workspace/heritage_temi_robot-phase28`。未提交、未推送；未修改 Android；没有实体 temi。本报告是阶段快照，阶段 2.8 **仍未完成**。

## 本轮已完成并验证

- **T00 基线审计：**隔离工作树、主工作树快照、tracked diff 哈希、依赖/模型/ROS与资源审计见 [`audit/baseline.md`](audit/baseline.md)。原主工作树和其网页/实验数据没有被编辑。
- **WP01 跟踪与观测：**匿名 IoU 跟踪器、有限预测/短时丢失/时钟回拨 epoch、保守团队观察器与 ROS 发布节点已接入。RGB-D 采样 [`WP01-GAZEBO-CAMERA-04`](experiments/WP01-GAZEBO-CAMERA-04/report.md)：官方厅、3 个静态模型、12 RGB/5 depth 帧；46/46 检测消息有效、138/138 距离关联有效。一个手工标注帧得到 TP=3、FP=0、FN=0、人数误差 0、IoU 均值 0.923；该单帧不代表总体准确率。47 条观察全为 UNKNOWN 是符合前视覆盖限制的保守结果。推理 FPS、深度误差和 ID switch 均不可计算。归档 30 个文件逐项校验通过，原件保留。
- **ROS 关闭清理：**新增统一节点 spin/关闭处理并接入四个感知节点；关机时 ROS context 已失效不再输出 traceback。定向测试通过；最新七包构建也覆盖该改动。
- **WP02 来源隔离：**`business_script` / `vision_conservative` 模式分离；视觉模式禁用脚本 lost 服务调用并不订阅脚本真值作控制依据；操作员继续只确认当前区。对全系统视觉掉队/恢复仍未验收。
- **WP05 软件竞态：**修复自动团队暂停覆盖安全暂停的优先级；覆盖取消、重复恢复、旧 UUID、陈旧里程计等 12 类竞态。定向回归曾为 109 passed；最新 543 项全套也通过。没有 Gazebo 实停时序证据。
- **WP10 最终回归：**最新七包构建 7/7、退出码 0；完整 `tests` 目录 550 passed、0 failed、0 skipped、0 errors，用 ROS Domain 231 并在运行前/后确认空图。WebSocket/网关两文件专项 2 passed；页面 JavaScript、只读回放和真实记录哈希检查均退出 0。完整命令及失败尝试见 [`tests/`](tests/) 和 [`test_summary.json`](tests/test_summary.json)。
- **WP13 实时页面：**技术证据 API 与只读浏览器面板已实现；官方厅整套系统的早期页面观察覆盖相机内参、视觉人数/UNKNOWN、真值新鲜度、融合、Scan、目标速度、cmd_vel、odom 和安全状态。之后新增深度有效像素与相机TF摘要并通过测试，但未重开浏览器核验新字段。无导航目标，运行后专用域231为空；截图未存档，60秒断源/重连未做。
- **WP14 记录回放：**新增独立离线 `RECORDED_ROS2` 导出和播放器。真实 WP01 样本通过 manifest、归档、原文件、图片及输出SHA校验，导出186事件、12 RGB、5深度元数据；播放器含本地时间轴/播放暂停/倍速/事件定位，不连接ROS/API。没有坐标和速度曲线数据；本机浏览器拒绝本地文件预览，因此未作画面验收。证据见 [`replay_export.md`](experiments/WP01-GAZEBO-CAMERA-04/replay_export.md)。
- **WP16 归档：**新增只归档已结束 run 的工具及拒绝覆盖/活动目录/越界路径等测试；WP01 大型 RGB-D run 压缩包 464,450 bytes，SHA256 `c6d55b3144e3b64a4e13896e653b2c622b9606de897768fd5ad0e57e8e7ca064`，30/30 文件与源逐字节校验一致，未删除原始文件。
- **WP17/18：**更新阶段状态、变更、阻塞、验证矩阵和最终报告；Android/实体接入清单仍明确区分静态代码审查与硬件验证。

## 视觉实验轮次

| run_id | 结果 | 说明 |
|---|---|---|
| `WP01-GAZEBO-CAMERA-01` | PASS_WITH_RISK | 旧短时冒烟；无已保存 RGB 帧，不能计算图像指标；保留原记录 |
| `WP01-GAZEBO-CAMERA-02` | FAIL | ROS setup 在 `set -u` 环境下提前失败，Gazebo 未启动 |
| `WP01-GAZEBO-CAMERA-03` | FAIL | 采集器缺 `rclpy.node.Node` 导入；本轮进程组均清理，无图像样本 |
| `WP01-GAZEBO-CAMERA-04` | PASS_WITH_RISK | 实际 RGB-D/YOLOX/匿名 tracks/observer 输出与一张人工标注图；指标边界见实验报告 |

失败轮次没有覆盖或删除。WP13 页面观察不是人群检测或导览闭环试验。

## 尚未完成

- WP03–04、WP06–09、WP11–12、WP15 未运行或未完成：视觉 E07-A/B、动态游客/掉队、速度标定与贡献、横穿、停车风险矩阵、稳定性、多速度性能和最终演示素材均不能宣称完成。
- WP13 面板当前没有相机视频、真实事件时间线、独立 Nav2 限速回读或保存的带 run_id 浏览器截图；新加 TF/深度字段未在浏览器现场复核；短时网页检查不满足 60 秒验收。
- WP14 回放没有轨迹/速度曲线，且浏览器预览未完成；当前真实样本不包含这些数据，不能插补或伪造。
- WP16 大日志频率统计/采样策略审查未全部完成。
- WP18 实体 SDK、相机、TTS、底盘调速、制动与现场安全为 **HARDWARE_REQUIRED**。

## 最终报告与状态入口

逐项状态见 [`validation_matrix.md`](validation_matrix.md)，原因与后续动作见 [`blockers.md`](blockers.md)，文件级范围见 [`code_changes.md`](code_changes.md)，总结见 [`final_report.md`](final_report.md)。
