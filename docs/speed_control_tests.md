# 动态速度控制验证记录

验证日期：2026-11-21。测试范围为 ROS 策略、Mock 后端、ROS 集成、Android 本地构建；无 temi 实机。

| 项目 | 结果 | 范围 |
|---|---|---|
| 完整项目自动化回归 | 通过，237 项 | 含导览、ROS Gateway、WebSocket、Mock 和速度策略；耗时 177.84 秒 |
| 速度策略及 Mock 后端 | 通过，37 项 | 纯 Python 输入/决策与虚拟导航；不代表 Gazebo 实时物理性能 |
| ROS2 工作空间构建 | 通过，7 个包 | 包含新接口生成、速度控制 ROS 节点；运行时 Nav2 动态参数联调未在本次完成 |
| Android 单元测试及 Debug APK | 通过 | 编译使用项目 SDK 1.139.0 缓存依赖；Launcher 与实机不在此验证范围 |
| WebSocket 调速链路 | 通过 | 运行项目 `.venv` 中的 WebSocket 集成测试，校验当前会话 UUID、命令字段和 SDK 结果回执 |
| 完整 Mock 五区加动态场景 | 通过 | Domain 219 跑完 8/8 站，拥挤/危险模拟输入触发 pause/resume，知识问答完成，error_count=0，64.177 秒；报告：`docs/runs/mock-system-20261121-130953-893828/report.json` |
| Gazebo/Nav2 动态限速运行时 | 未执行 | ROS 构建通过，但本轮没有在 Gazebo 实时调用 `/controller_server/set_parameters` 验证参数生效 |
| temi 实机安全 | 未验证 | 没有实体 temi；目标速度与真实速度、制动性能、传感器距离阈值均未测量 |

本项目根目录当前没有 `.git` 元数据，无法提供 Git 状态或提交基线；SDK 子目录是单独固定版本的上游仓库，不代表项目自身有版本历史。
