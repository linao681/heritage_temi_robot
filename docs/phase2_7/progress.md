# 阶段 2.7 执行进度

基线：`057761908e386f3d0ba7a779d61b860a15debbda`（`main`）。截至 2026-11-22，工作树包含本阶段未提交修改；未创建 commit、未推送 GitHub。

## 当前状态

1. **A 审计与可复现运行器：PASS。** 运行器输入校验、隔离域/端口、唯一运行目录、manifest 和失败保留已有实现及测试。
2. **B 人物独立运动与风险防护：PASS_WITH_RISK。** 原 S01 的 1.4 m 目标以预测几何风险中止；保留 FAIL。采用 3.5 m 安全终点和向左离开后，两轮人物继续运动、停车、持留、离开并完成五区导览。几何间隙为保守代理，接触状态未知。
3. **C E06/Nav2 安全审查：PASS_WITH_RISK。** 20 项审查、软件回归通过；两轮真实 Gazebo 运行均以新 UUID 继续同一 zone_1，恢复依据单独从原始报告/真值复核。尚无多轮稳定性和实体验证。
4. **D1 速度和距离分析：PASS_WITH_RISK（范围有限）。** 阶段时间线、请求/响应和距离图已生成；规定的干扰前 0.3 m/s 校准条件未满足，S02–S04 和完整制动里程积分/跨档比较未完成。
5. **E1 全目录回归与构建：PASS。** 最新全 `tests` 回归 487 passed、0 failed、0 skipped，187.89 s；七个 ROS2 包构建成功。Domain 230 前后为空。
6. **E04 相机 A–D 传感器冒烟：PASS_WITH_RISK。** RGB/Depth/CameraInfo/TF 通过；没有带人的 YOLOX/RGB-D 准确度比较。
7. **E02、E04 横穿、E07、7 轮稳定性、60 s 性能、RECORDED 可视化：NOT_RUN。** 已留存 14 个 S01 系列 run_id，2 完整、12 失败/未完成；不符合计划的 3+2+1+1 场景配额。分母见 `stability/repeated_tours.csv`。不能由两次相同配置安全终点导览或相机冒烟代替。
8. **实体 temi：HARDWARE_REQUIRED。** 本轮没有设备或实体运动命令。

## 关键运行和测试台账

| 日期/运行 | 项目 | 结果 | 证据 |
|---|---|---|---|
| 2026-11-22 | ROS2 七包构建 | 7 packages finished，退出码 0 | `tests/late-fixes-20261122/ros2_build_final.log`，SHA256 `a8c2cbc09ecf76690e7e7dcd7ceb9aaa70efdc39340651cac209cdc7797b243d` |
| 2026-11-22 | 全目录 Python/ROS 测试 | 487 passed，0 failed，0 skipped；187.89 s | `tests/late-fixes-20261122/full_suite_final.log`，SHA256 `4b301ea5a8db35af23711a2b9d0c04fd7997ea9f52b82664c3a75c1e36163e2b` |
| 2026-11-22 | ROS 测试域清理检查 | Domain 230 前后均空 | `tests/late-fixes-20261122/domain_pre_final.json`、`domain_post_final.json` |
| 2026-11-22 | 原 S01 系列 | 7 次尝试；6 次未通过启动/游客准备门槛，1 次预测几何风险 FAIL | `experiments/S01/` 各自的 `status.json`、Tour 报告和 truth |
| 2026-11-22 | 安全终点前两轮 | 一轮恢复判定失败、一轮观察到几何重叠 FAIL | `experiments/S01-SAFE-ENDPOINT/20261122T042258Z-S01-SAFE-ENDPOINT-r001/`、`20261122T043735Z-S01-SAFE-ENDPOINT-r001/` |
| 2026-11-22 | S01-SAFE-ENDPOINT 两次完整轮次 | 分别 46.038 s / 45.436 s 人物运动；路线均 7/7；320.976 s / 325.411 s；分析均 PASS_WITH_RISK | `experiments/S01-SAFE-ENDPOINT/20261122T044704Z-S01-SAFE-ENDPOINT-r001/evidence_summary.json`、`experiments/S01-SAFE-ENDPOINT/20261122T101824Z-S01-SAFE-ENDPOINT-r001/evidence_summary.json` |
| 2026-11-22 | S01 系列运行分母 | 14 个独立 run_id，2 个完整路线、12 个失败/未完成 | `stability/repeated_tours.csv` |
| 2026-11-22 | WebSocket 两文件专项 | 19 passed；最新全量测试也包含这些文件 | `tests/websocket-targeted-20261122-032308/websocket.log` |
| 2026-11-22 | 相机 A–D 传感链路 | 四组独立 Gazebo RGB/Depth/CameraInfo/TF 冒烟通过 | `experiments/camera_smoke_verified/{A,B,C,D}/` |

## 仍未通过的阶段门

- 0.3 m/s 干扰前标定窗口未达到门槛；高速档及跨配置比较未运行。
- E02 人数/拥挤闭环、E04 三种横穿、E07 三人掉队未运行。
- 没有完成计划中的 7 个独立导览、60 秒性能基线/优化对照和性能统计。
- A–D 相机尚未完成仿真人物 YOLOX 检出及 RGB-D 误差比较。
- 展示网页没有完成真实记录回放和 LIVE/RECORDED/DEMO 验收。
- 无实体 temi，不得把 Gazebo、Mock Speak Action 或软件测试描述为硬件安全验证。

所有后续结论仅在真实执行并保存记录后更新。详见 [`final_report.md`](final_report.md) 与 [`validation_matrix.md`](validation_matrix.md)。
