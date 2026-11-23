# 阶段3.0执行进度

更新时间：2026-11-23 20:34 CST
分支：`phase2_9-work`
HEAD：`f372e3f4e0702470eb91b2a32683e62590777840`

状态只依据本阶段保存的测试或实验记录。`624 passed` 是阶段2.9历史基线，不计入阶段3.0通过数。

| 任务 | 状态 | 证据 |
|---|---|---|
| T00 仓库保护与记录 | PASS | 分支/HEAD、每轮资源/进程/DDS域/端口预检与收尾见 `test_results.md`、`experiments/T04-*`、`experiments/T05/`；失败记录保留 |
| T01 视觉暂停原因与确认生命周期 | PASS | 红绿测试、ROS集成与构建见 `experiments/T01/`、`experiments/T01T03/`；当前暂停事件/session绑定，安全恢复资格独立 |
| T02 仿真测试操作员 | PASS | operator模式及拒绝路径测试、视觉/业务分离报告见 `experiments/T02/`、`experiments/T04-vision/`、`experiments/T04-business/` |
| T03 持续停车与导航证据 | PASS | 连续新鲜Odom窗口与目标/UUID运动配对，142项定向回归通过，见 `experiments/T01T03/` |
| T04 视觉暂停恢复与业务回归 | PASS_WITH_RISK | vision run `160651` 全程/6次暂停有恢复证据但后方保持UNKNOWN；business run `162126` 通过。复跑 `164811` 的wait暂停缺运动证据，按FAIL保留 |
| T05 E04前方横穿 | PASS_WITH_RISK | 官方布局run-004全路线与前向横穿通过；视觉距离/减速/停车均有证据，激光同步有效且无接触传感器；见 `experiments/T05/E04-CROSS-FRONT/run-004/evidence.md` |
| T06 E02人群对照 | PASS_WITH_RISK | 空场和三人官方布局全路线PASS；实际0/1/3人视觉与Gazebo真值对照、fresh odom/cmd/限速回读已留档。稳定直行窗不达标、Nav2限速未随人数变化，物理人群调速仍未验证；单人轮失败。见 `experiments/T06/E02-evidence.md` |
| T07 布局B | PASS_WITH_RISK | adaptive静态校验82项通过；Nav2 zone_1及6/6目标路线成功；业务状态机adaptive五区/QA/出口完成。单人演员、测试同意与Mock播报见 `experiments/T07/adaptive-layout-evidence.md` |
| T08 技术面板与真实回放 | PASS_WITH_RISK | 结构化ROS快照、真实run哈希回放、只读HTTP与34项定向Python/Node测试通过；无RGB/depth帧，桌面视觉验收NOT_RUN。见 `experiments/T08/replay-evidence.md` |
| T09 六分钟国赛材料 | PASS_WITH_RISK | 14份材料更新；360秒讲稿、26问答、真实run分镜；一致性校验通过。无视频/PPTX/PDF，浏览器视觉验收仍NOT_RUN。见`competition_final/`及`experiments/T09/material-validation-final4.log` |
| T10 最终回归 | PASS | 七包构建7/7；完整tests 680 passed/0 failed/0 skipped；10组定向均通过；Domain 220前后为空。详见`experiments/T10/summary.md` |
| T11 最终报告与交付 | PASS | `final_report.md`七节交接报告完成；T00–T10状态、证据哈希、遗漏项与人工验收项已统一；见`experiments/T11/report-validation-final2.log` |

## 运行记录

T04–T07的Gazebo任务串行。T07 Domain 214、Gazebo 11400、Web 8125；adaptive业务route run结束后DDS探针为空，11400/8125可重新绑定。T08回放server仅绑定127.0.0.1:8126，验证后已关闭且端口可重新绑定。没有停止其他用户进程。最近T07启动前可用内存约8.8 GiB、磁盘约45 GiB。

阶段3.0最终全量回归：七包构建7/7；完整`tests/`为680 passed、无失败/跳过；10组定向测试分别通过。T01–T08定向记录继续保留为对应任务时的证据快照，不与最终完整套件相加。

## 本阶段执行规则

- 逐项按 `implementation_plan.md` 顺序推进；失败尝试保留原始日志和退出码。
- 每个Gazebo run 先重新做资源、进程、ROS域与端口预检；不停止非本轮进程。
- 真实感知、脚本真值、模拟操作员和Mock播报分别记录。
- 不自动提交、推送或合并Git。
- T05前三次失败run-001–003及首次端口探针转义错误均保留；修正可复现根因后只执行了run-004一次针对性复测。
- T08旧快照回放第一轮速度字段为0的run-002保留；新鲜度age映射修复后run-003成为最终真实回放证据。浏览器截图验收未运行，Node/HTTP验证不替代视觉验证。


T09材料检查退出码0，日志SHA-256 `0086435952ee02263e56e967f0bcd52835411877cc00a7381b038e9469568eb5`。首轮哈希校验失败及修正后复验均留在`experiments/T09/`；PPTX/PDF/视频没有生成，不能当作已交付成品。

T10完成：完整测试日志SHA-256 `91af50f880851a035f8d7d316a32662d7219bdd8b98ab084c92e22823f3ed837`；构建日志SHA-256 `8a4ac62610af958f6f4cdea6bb9208306e01475470b65a80c8ba8afeccd151dc`。构建及全部定向ROS测试后Domain 220均为空。详见`experiments/T10/summary.md`。

T11报告验证已完成，日志`experiments/T11/report-validation-final2.log` SHA-256 `239a16eaecf605f88cec16adc58adecfbf9a22b81672c8c38d25cc029b2c21c8`。
