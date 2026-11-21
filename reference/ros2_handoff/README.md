# 非遗灵伴 · Linux ROS 2 仿真开发交接包

交接日期：2026-11-20。目标：将现有浏览器非遗展厅服务闭环迁移为可运行、可测试的 ROS 2 导览仿真，并为未来 temi 真机部署保留清晰的适配接口。

## 从这里开始

1. 阅读 `DEVELOPMENT.md` 和 `CODEX_PROMPT.md`。
2. 打开 `demo_offline.html`，体验原有五展区流程、自由参观及异常场景。
3. 阅读 `requirements/competition.docx`；赛题是功能验收依据，PPT 只作为参考。
4. `environment/layouts.json` 是从本包实际 `layout.js` 导出的官方布局及独立适配布局，`robot_model.json` 是浏览器建模配置。它们不是实测地图或实机标定数据。
5. `web_demo/` 为完整模块化源码（含资源及 Three.js），可在 Linux 用 `python3 -m http.server 8000` 启动，访问 `http://localhost:8000`。可用 `node build.cjs` 重建离线 HTML（输出在上一级）。
6. `validation/` 中为原网页仿真的已有测试记录；不是 ROS 2 或真实机器人测试结果。

## 内容

| 路径 | 用途 |
|---|---|
| `requirements/` | 原始赛题文档 |
| `web_demo/` | 自主参观服务闭环版完整源码及本地资源 |
| `demo_offline.html` | 无需网络的展示基线 |
| `environment/` | 两种布局、机器人参数及平面对照图 |
| `knowledge/` | 有来源的现有讲解内容，更多人物故事见 `web_demo/story-data.js` |
| `reference/` | 国赛图文增强版 PDF、避障视频及完整演示字幕/旁白 |
| `validation/` | 原有场景矩阵与仿真测试原始结果 |
| `export-config.cjs` | 将网页配置重新导出为 JSON |

完整版演示视频体积较大，单独保存在原项目 `outputs/2026赛题演示视频_细节修订版/具身智能非遗展厅导览应用方案演示_1080P30帧.mp4`，如需复现演示镜头可一并复制。

官方资料：<https://github.com/robotemi/sdk>；<https://github.com/robotemi/sdk/wiki/Home_chn>；<https://www.robotemi.cn/developers/>。

目前没有实体 temi 供联调；Gazebo 模型、传感器与动力学属于近似仿真，实际 temi 导航由官方 SDK 能力决定，不假定能直接向真机发送 ROS `/cmd_vel`。
