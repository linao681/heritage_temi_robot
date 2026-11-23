# 阶段2.9验证尝试记录

日期：2026-11-23（Asia/Shanghai）。保留失败尝试，修复后结果另列；没有删除旧记录。

| 尝试 | 结果 | 说明 |
|---|---|---|
| 新增runner测试先行：导入`allocate_run_directory`/`parse_args` | RED：ImportError | 目标API尚未实现；实现后对应定向测试通过 |
| 新增vision恢复门测试 | RED：缺少`resume_requires_scripted_gather` | 实现API模式门及前端分流后，测试通过 |
| 新增Nav2参数摘要测试 | RED：缺少`summarize_nav2_speed_limits` | 实现读回摘要后通过 |
| 定向pytest未source项目overlay | FAIL：`ModuleNotFoundError: temi_interfaces` | 后续构建成功并source最新overlay |
| 定向ROS测试未设置ROS日志目录 | FAIL：`~/.ros/log`只读 | 默认home日志路径不适合此执行容器 |
| ROS日志改到`/tmp`后运行ROS节点组合测试 | HUNG，60秒后向本会话pytest发送SIGINT，退出130 | 没有最终pytest摘要；不能记为通过。沙箱另行报告Fast DDS网络接口/UDP socket被拒绝 |
| 首次colcon build默认项目日志目录 | FAIL：`ros2_ws/log`只读 | 尚未编译包 |
| 使用临时日志和临时install目录的colcon build | 长时间无包日志/无安装产物，终止 | 未证明代码失败；日志缺少包stream；后改为项目install目录授权构建 |
| 七包ROS2构建（临时日志，项目install） | PASS：7/7，23.2秒，退出0 | 日志路径`/tmp/phase29-colcon-log-escalated/` |
| 定向阶段2.9/相关单测 | PASS：33 passed，0.66秒 | 不包括全仓tests和ROS transport专项 |
| JS、Shell、指定Python语法检查 | PASS，退出0 | 静态检查，不代表在线行为 |

### 环境复核原始结论

见[`recheck-20261123-0133.md`](recheck-20261123-0133.md)：内存5.2GiB、负载16.54/16、Socket PermissionError、Fast DDS参与者注册失败。ROS空域脚本虽返回empty，但因DDS无法建立transport不采信。


### 续测记录（2026-11-23，02:35 CST之后）

| 尝试 | 结果 | 说明 |
|---|---|---|
| 最新源码七包ROS2构建 | PASS：7 packages finished，54.2秒，退出0 | colcon事件/日志位于 /tmp/phase29-colcon-log-final2/；覆盖儿童问答与WebSocket失败关闭修改 |
| 定向回归（回放HTTP新测试加入前） | PASS：88 passed，1 deselected，15.09秒 | 包含知识库儿童层级、Tour Manager、可视化API、runner、观察器、UUID/停稳竞态与空listener失败关闭；排除ROS service roundtrip |
| 安全离线子集（第2轮，回放GET/HEAD限制测试加入前） | PASS：454 passed，24.88秒 | 14个含ROS节点/Fast DDS/本地网络集成模块显式排除；不代表全仓全通过 |
| WebSocket localhost监听专项 | BLOCKED，真实认证轮次不能建立监听socket | 5个前置单测通过；真实loopback返回无绑定socket。新增后端fail-closed保护和单测已通过 |
| 阶段2.9 WP01 business_script预检 | BLOCKED，0事件，启动前退出 | 可用内存5.098GiB低于6GiB；本地端口probe受PermissionError阻止；证据在experiments/WP01-full-tour/visitor-full-20261123-020925/ |
| JS、Shell、Python AST检查 | PASS | 最新ros-live.js、3个shell及7个Python文件 |

历史阶段2.7集合分析仅为离线计算；本阶段没有集合算法改动或同条件复测。

| 全仓pytest收集（第2轮） | PASS：574项收集成功 | 仅收集检查；含ROS/本地网络集成测试未全量执行 |

| 回放HTTP固定资源安全专项 | PASS：5 passed | 记录校验、固定路由、路径穿越拒绝、哈希错误、symlink和控制字段拒绝；没有在沙箱实际绑定HTTP端口 |
| 回放页面Node只读检查初次运行 | FAIL，旧断言拒绝任何fetch | 页面只在127.0.0.1发GET请求；更新断言只允许两条固定记录GET，仍拒绝控制API/POST；Node回归通过 |
| 新回放安全测试首次夹具 | FAIL，临时父目录未创建 | 修复夹具后5项通过，未改产品行为 |
| Python py_compile首次尝试 | BLOCKED，默认pycache路径只读 | 设置PYTHONPYCACHEPREFIX=/tmp后重新做语法检查 |

| 最终离线回归（新增回放处理器GET/HEAD限制后） | PASS：455 passed，24.86秒 | 14个ROS节点/本地网络测试模块排除；包括6项回放服务安全测试 |
| 最终全仓pytest收集 | PASS：575项收集 | 不代表全仓执行通过 |
| 回放脚本/页面静态检查 | PASS | PYTHONPYCACHEPREFIX指向/tmp的py_compile、Node语法和回放完整性Node专项均通过 |

| 最终定向回归（含只读回放服务器测试） | PASS：94 passed，1 deselected，15.06秒 | 含回放路由/校验和儿童问答；排除ROS service roundtrip |
| 最终七包构建 | PASS：7 packages finished，54.2秒，退出0 | /tmp/phase29-colcon-log-final3/ |

| 回放来源manifest异常形状回归 | RED→修复→PASS | 首次暴露list manifest触发未处理AttributeError；增加JSON object校验后专项7 passed |
| 最终定向回归（来源manifest异常形状修复后） | PASS：95 passed，1 deselected，15.24秒 | 排除ROS service roundtrip；包括7项回放HTTP安全测试 |
| 最终安全离线测试子集 | PASS：456 passed，25.01秒 | 14个ROS节点/本地网络集成模块排除 |
| 最终全仓pytest收集 | PASS：576项收集 | 仅收集检查，未全量执行 |

### 记录器扩展后的阶段回归（2026-11-23）

新增的地图位姿测试以fake TF Buffer验证代码路径，不启动ROS节点；覆盖新鲜`map`变换、过期/未来时间、错误frame、非有限位姿和缺失变换。记录器定向测试为13 passed。

| 尝试 | 结果 | 证据/限制 |
|---|---|---|
| WP14记录器契约专项 | PASS：13 passed，0.22秒 | `tests/test_phase29_recording.py`；无ROS运行数据 |
| WP18定向回归 | PASS：126 passed，1 deselected，14.81秒 | 排除`test_vision_mode_ignores_scripted_team_status_in_ros_node`；原始stdout `/tmp/phase29-wp18-targeted-20261123-final.log`，SHA256 `9037587b2784d061fb28a1cd80640f760b7a2c25462b72026159c44b8c478e31` |
| WP18安全离线子集 | PASS：488 passed，1 deselected，23.32秒 | 明确忽略14个ROS/本地网络集成模块，另排除上述ROS节点用例；stdout `/tmp/phase29-wp18-offline-20261123-final.log`，SHA256 `182579519a68f4be1b7671dcad2ec8e0ec6614dfa1fc3fff14744ede57d323ad` |
| WebSocket无监听协议/失败关闭测试 | PASS：5 passed，14 deselected，0.06秒 | 仅纯协议、私网bind约束、空listener失败关闭；不代表loopback服务成功 |
| WebSocket本地认证握手 | FAIL / BLOCKED：5 passed后首个真实握手用例失败 | `RuntimeError: WebSocket 服务未启动`；stderr称没有成功绑定监听端口。其余需socket的用例没有记为通过 |
| 包含ROS节点初始化的混合回归 | BLOCKED，手动中止，退出130 | `test_vision_mode_ignores_scripted_team_status_in_ros_node`停在`rclpy.init`/Fast DDS环境；后续以`-k`排除此项后重跑 |
| 全仓pytest收集 | PASS：589项 | 仅收集，未全量执行；收集检查在记录器新增6项地图测试后完成 |

离线子集复现范围：在`tests`上运行pytest，显式`--ignore`以下14个模块：`test_gateway_cli.py`、`test_gateway_websocket_integration.py`、`test_perception_ros_integration.py`、`test_phase28_ros_shutdown.py`、`test_ros_depth_association.py`、`test_ros_gateway.py`、`test_ros_person_detector.py`、`test_ros_team_observer.py`、`test_system_startup.py`、`test_tour_ros_integration.py`、`test_visitor_ros.py`、`test_visitor_tour_integration.py`、`test_vision_ros.py`、`test_websocket_backend.py`；并用`-k 'not test_vision_mode_ignores_scripted_team_status_in_ros_node'`排除一个会初始化ROS Domain的节点用例。该子集不是完整tests目录通过。

### 最终记录器/速度分析回归（2026-11-23）

之后新增`odom`ROS消息头时间与单调接收时间双重验证、稳定速度窗分析器。两份代码只对CSV记录工作，不创建ROS节点或伪造实验数据。新增9项速度分析测试和9项记录时间戳测试；记录器合计22项测试。

| 尝试 | 结果 | 证据/限制 |
|---|---|---|
| WP14记录器契约专项 | PASS：22项记录器测试 | fresh/stale/future/wrong frame/nonfinite/missing TF和Nav2读回解码；不代表在线采样 |
| WP07速度窗分析 | PASS：9项纯数据分析测试 | 包含停车零速、陈旧数据、短窗、长间隔、速度偏差、缺速度上限和混run/乱序拒绝；不代表0.3/0.5/0.7实测 |
| 定向回归 | PASS：144 passed，1 deselected，14.88秒 | stdout `/tmp/phase29-wp18-targeted-20261123-final2.log`；SHA256 `bd4a38266eff0958271a7340b046d24434a733a0be0fa4172d16e0254374cff2` |
| 安全离线子集 | PASS：506 passed，1 deselected，23.45秒 | 同样排除14个集成模块和1项ROS节点；stdout `/tmp/phase29-wp18-offline-20261123-final2.log`；SHA256 `d815d6d367e4b9e7d9e51d918b66663d51f00a09466a59b8b4b990b71abed66f` |
| 全仓pytest收集 | PASS：607项收集，退出0 | 仅收集、不执行；stdout `/tmp/phase29-wp18-collect-20261123-final2.log`；SHA256 `d588f4f8db4fb5d9083398091e3295db399be1c46297630c734e6e0b0f7d85fd` |

速度分析复现命令：

```bash
.venv/bin/python scripts/analyze_phase29_experiment.py --input <recorded-experiment.csv> --target-speed 0.3
```

`<recorded-experiment.csv>`须替换为真实`record_phase2_topics.py`输出；本阶段没有符合条件的CSV，因此没有执行0.3/0.5/0.7速度档并保持NOT_RUN。

最终确认（代码格式整理后重跑，2026-11-23）：定向回归144 passed、1 deselected、14.90秒，stdout `/tmp/phase29-wp18-targeted-20261123-final3.log`，SHA256 `e98f3a404449396cad0c9a378b54503222f9dc879cf36365de181756782ad9c0`；安全离线子集506 passed、1 deselected、23.47秒，stdout `/tmp/phase29-wp18-offline-20261123-final3.log`，SHA256 `406873a1a5b40f14b5ed339c1e14c471003f16ff4907aad1e01893e28c894999`；pytest收集607项，stdout `/tmp/phase29-wp18-collect-20261123-final3.log`，SHA256 `08aa7d684699b5623b56f94e77cf9dd3bc31ccd0527514e431492c00490a1d9a`。当前改动Python文件语法、网页JS语法与回放Node检查、三个脚本bash语法以及`git diff --check`均通过。ROS包源码未在最近一次7包构建后改变。


### 运行权限恢复后的补测（2026-11-23，09:21 CST之后）

| 尝试 | 结果 | 证据/限制 |
|---|---|---|
| WebSocket console-script入口 | FAIL：`.venv/bin/pytest`不存在 | 改用`.venv/bin/python -m pytest`执行，同一测试模块未因此更改产品代码 |
| WebSocket真实本机集成模块 | PASS：19 passed，1.97秒 | `tests/test_websocket_backend.py`；loopback服务与模拟客户端；不代表Android或实体temi验收 |
| vision_conservative ROS节点来源隔离 | PASS：1 passed，0.32秒 | 域232；验证脚本团队真值不影响视觉模式，不代表相机或动态跟踪 |
| WP01最新官方业务演示启动 | BLOCKED，events=0，0.0195秒 | `visitor-full-20261123-092632/report.json`；资源数值和端口均通过，但运行器发现`gzserver`并在启动前拒绝；无组件由本轮创建 |
| WP01测试后域核验 | PASS_WITH_RISK | 域232为空；域228仍有Nav2/项目ROS节点；未停止现有进程 |
| WP01失败后资源复查（09:29 CST） | BLOCKED，未重试 | `gzserver`仍在线；6.9GiB可用、无swap、load 1.10/CPU超限；没有对现有进程发信号 |

### 修复后完整回归（2026-11-23）

| 尝试 | 结果 | 证据/限制 |
|---|---|---|
| 初次启动完整套件 | FAIL：ROS setup在`set -u`下访问未绑定变量`AMENT_TRACE_SETUP_FILES` | pytest未启动，未改产品代码 |
| 第二次启动完整套件 | FAIL：仓库没有`.venv/bin/pytest`入口 | 命令返回127，未收集测试；保存原始输出`docs/phase2_9/audit/full-regression-20261123-1312.log` |
| `.venv/bin/python -m pytest -q tests` | PASS：622 passed，188.86秒，无排除项 | Domain环境变量固定226；原始完整输出`full-regression-20261123-1316.log`；随后项目探针确认Domain 226为空。覆盖shutdown隔离与新鲜ModelStates读回修复；不替代Gazebo专项目标验收 |

### 视觉暂停handler复现与修复（2026-11-23）

| 尝试 | 结果 | 证据/限制 |
|---|---|---|
| `visitor-full-20261123-133255` vision_conservative | FAIL（部分真实观测） | report保留完整：tour停在zone_1；845条团队观察均UNKNOWN，800条暂停样本有fresh odom停稳记录；运行器按通用reason未进入视觉operator-handler，因此未记录runner侧暂停窗口/恢复；未完成全程。详见run `evidence.md`。 |
| 新增generic safety pause回归测试（修改前） | RED：1 failed、1 passed | `test_vision_runner_handles_generic_pause_from_unconfirmed_observation`复现reason文案不含“视觉/观察”时返回false；另一项“3/3且无需人工确认”仍按预期不触发。 |
| `tests/test_phase29_full_demo.py`（修改后） | GREEN：20 passed | runner依据真实observer的`requires_manual_confirmation`字段处理视觉暂停，并只传observer payload，不读取脚本team真值。完整`tests/`尚未纳入此次runner补丁，需重跑。 |

### 视觉handler修复后的全量回归与测试进程收尾（2026-11-23 13:51 CST）

| 尝试 | 结果 | 证据/限制 |
|---|---|---|
| 沙箱内ROS域探针 | BLOCKED：`rclpy.init`无法写入`/home/linao/.ros/log/`（只读文件系统） | 未启动pytest、Gazebo或ROS应用。随后使用获准的项目验收运行环境重试；不是域占用结果。 |
| 最新完整测试前域预检 | PASS：Domain 226 `other_nodes: []`, `empty: true` | 项目`phase25_preflight.py --check-domain-empty --timeout-sec 1` |
| `.venv/bin/python -u -m pytest -q tests` | PASS：624 passed，190.10秒，退出0 | 日志`full-regression-20261123-1351.log`；SHA-256 `609b53c935b48363831dd1cafd4200112991db64f5932cd81c179e5d5db52d74`。包含视觉暂停handler修复后的全部测试。 |
| 全量测试后域预检 | PASS：Domain 226 `other_nodes: []`, `empty: true` | 与测试前为同一域；没有保留测试ROS节点。 |
| 用户要求退出本会话自启动测试进程后的检查 | PASS：未发现本项目导览/Gazebo测试进程 | 未停止其他用户ROS/Gazebo进程；未重启Gazebo。 |
