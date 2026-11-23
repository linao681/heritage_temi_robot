# WP02视觉模式启动前检查记录

- 状态：FAIL（启动前检查拒绝；Gazebo、Nav2和网页系统均未启动）
- 时间：2026-11-23 11:44 CST；代码HEAD `24c14231de61840a11c5462805df0cd6160af84d`
- 配置：official、vision_conservative、ROS Domain 227、Gazebo端口11377、Web端口8101、最长45秒。
- 实际耗时：2.016秒；事件数0；实时数据文件为空。
- 运行器资源预检：可用内存7.844 GiB、磁盘44.760 GiB、负载0.084/16核、端口可绑定、无Gazebo进程。
- 启动器拒绝原因：Domain 227发现节点`_ros2cli_daemon_227_00b22d170be14de7855ceffcce0df259`。该节点由此前检查域时调用`ros2 node list`所创建；本次记录保留为预检失败，不计仿真结果。项目自带探针仍观察到该发现条目，因此改用经项目探针验证为空的Domain 226。
- 原始证据：`report.json`、`manifest.json`、`system.log`；未尝试停止或杀死任何ROS进程。

