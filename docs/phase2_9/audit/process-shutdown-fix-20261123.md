# E07-A中断后的仿真进程清理复核

日期：2026-11-23（Asia/Shanghai）

## 发现

用户要求结束由本会话启动的E07-A run `visitor-full-20261123-121915`后，完整演示器记录为“演示被操作员中断”。仅向主进程发送Ctrl+C后，`start_phase25_system.sh`管理的Gazebo、速度控制、感知和可视化进程仍有残留。检查进程启动时间、ROS_DOMAIN_ID、PGID及命令行后，确认这些进程均由本次run启动；没有向其他ROS/Gazebo进程发信号。

根因依据：`scripts/run_visitor_full_demo.py`通过`subprocess.Popen`启动系统管理脚本时未创建独立会话；交互终端Ctrl+C可能同时投递给主程序和系统管理脚本，使其`EXIT`清理流程被打断。`scripts/start_phase25_system.sh`把各组件放在独立会话中运行，正常清理需要管理脚本接收中断并按顺序停止这些组件组。

## 修复与测试

- 完整演示器启动系统管理脚本时新增`start_new_session=True`，让主运行器单独控制其退出流程。
- 先新增`test_phase25_supervisor_starts_in_an_owned_session`并运行，测试按预期失败：启动调用缺少`start_new_session=True`。
- 最小修复后，新增用例通过；完整`tests/test_phase29_full_demo.py`为18 passed（其中含该回归用例）。`bash -n`检查两个启动脚本及`git diff --check`通过。
- 12:11时的全量回归619 passed早于此修复。完整`tests/`目录需要在本修复后重新运行；还没有用第二次Gazebo运行验证Ctrl+C端到端清理。

## 本次运行收尾证据

对已确认归属本次run的会话组先发SIGINT，再对仍存活的组发SIGTERM。之后只读检查：

- `scripts/phase25_preflight.py --check-domain-empty`：Domain 226返回`other_nodes: []`, `empty: true`。
- Gazebo端口11379和网页端口8102无监听者。
- 本次run保存的Gazebo/ROS/可视化进程PID均已退出。
- 清理只作用于该run启动的进程组。

该收尾验证证明当前没有残留进程；不能代替对新修复版本的真实Gazebo中断复测。
