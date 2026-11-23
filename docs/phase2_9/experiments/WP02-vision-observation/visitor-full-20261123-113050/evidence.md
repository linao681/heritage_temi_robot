# WP02导航取消与调速请求时序诊断

- 状态：FAIL（调速控制进入ERROR，且关闭时没有停稳确认）。
- 时间：2026-11-23 11:30:50 CST；运行器用时19.451秒。
- 版本/场景：HEAD `24c14231de61840a11c5462805df0cd6160af84d` + 阶段2.9未提交修改；official、vision_conservative、3名Gazebo脚本游客；ROS Domain 226、Gazebo端口11375、Web端口8097；最长45秒。
- 资源预检通过：可用内存7.718 GiB、磁盘44.776 GiB、负载0.033/16核、无其他Gazebo，端口可绑定。

## 观测与故障顺序

- 游客接待和同意请求成功，随后尝试前往`wait`入口待命目标。
- 实时数据35条，其中29条含新鲜视觉团队观察，全部为`UNKNOWN`：26条可观察到1人、3条观察到2人；期望人数3。37条跟踪记录含32条有效RGB-D距离，范围2.242–3.345米；出现匿名ID `vision-e0-1`、`vision-e0-3`。这不是人工标注精度结果。
- Nav2日志：`Goal canceled`时间戳1795404669.208107667。随后Gateway在1795404669.344457022拒绝调速请求，原因“没有活动导航Action”，相差约136毫秒。该证据显示旧速度请求在导航Action已结束后才到达网关。
- 当时速度控制器将拒绝锁存为ERROR；run最终报告`故障需人工检查`，Tour仍处于前往wait的NAVIGATING状态，`stop_confirmed=false`。因此此run不证明安全暂停或停稳成功。
- 此后在另一次run中，用`stale_session`将“没有活动导航Action”的旧请求与真正的安全拒绝区分；新run确认旧请求被丢弃，但视觉导览仍因等待操作员确认未完整完成。
- 本run没有三人动态移动、遮挡、离场/重入专项，也没有人工确认恢复。

## 复现命令

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
export ROS_LOCALHOST_ONLY=1
timeout 120s .venv/bin/python -u scripts/run_visitor_full_demo.py \
  --layout official --team-decision-mode vision_conservative \
  --domain-id 226 --gazebo-port 11375 --web-port 8097 \
  --timeout-sec 45 \
  --output-dir docs/phase2_9/experiments/WP02-vision-observation
```

## 原始证据SHA-256

- `report.json`: `86bdccb23e8ef01414b413189b8287df4a2e07b97a9694304cdb6eac22158c16`
- `manifest.json`: `d949f48e5d6e1c6fb606d9d9b0ba85cfa4b0635677f38efea80b9dd57b01b9d1`
- `live_evidence.jsonl`: `00d6db62a087a9607a2e204c11012bbd14e59ed02f9165db5cab8dd080dc80cc`
- `system.log`: `dbed903e151369f4a01d7a2abaf53287c2c38ddfd41b1fadd79b46e7202c7f86`

