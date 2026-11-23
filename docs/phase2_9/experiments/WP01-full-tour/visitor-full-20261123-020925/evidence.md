# WP01 启动前阻塞证据

- Run ID：`visitor-full-20261123-020925`
- 状态：`BLOCKED`。启动器在创建仿真系统进程前退出；没有启动 Gazebo、Nav2 或 Web 服务。
- 布局/模式：官方展厅 A / `business_script`；本次不是导览验收，不计作通过或失败的导览轮次。
- ROS Domain / 端口候选：240 / Gazebo 11441 / Web 8141。由于本执行环境禁止创建本地 socket，这些端口及 ROS Domain 均未被确认空闲。
- 实测预检：可用内存 5.098 GiB（门槛 6.0 GiB）；磁盘可用 45.738 GiB；负载/核心 0.663；未发现 Gazebo Classic 进程；两个端口探测均返回 `PermissionError: [Errno 1] Operation not permitted`。
- 阻塞原因：低于内存门槛，且无法验证本地端口可绑定。预检拒绝启动。
- 运行清单和启动报告：同目录 `manifest.json`、`report.json`；`system.log` 为空，因为没有启动系统进程。
- 启动器临时原件：`/tmp/phase29-wp01-blocked/visitor-full-20261123-020925/`。
- 原件 SHA256：`manifest.json` `7945f1fe5ccee51827ff8bce834583195bea3ff74aaab4d543b77ec873b5d3e9`；`report.json` `bffcbaf0b2242fa7ebd98e9642899ea546597892be394eaa3f78ea0e54606327`；空 `system.log` `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`。
- 复现命令：`PYTHONPATH=scripts .venv/bin/python scripts/run_visitor_full_demo.py --layout official --team-decision-mode business_script --domain-id 240 --gazebo-port 11441 --web-port 8141 --timeout-sec 1200 --output-dir /tmp/phase29-wp01-blocked`

该证据只说明预检保护生效，不能代替五区导览实验。此前 ROS 传输注册异常详见 `docs/phase2_9/audit/verification-attempts.md`。
