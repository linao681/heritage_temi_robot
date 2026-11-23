# T08实时面板与ROS记录回放证据

状态：`PASS_WITH_RISK`；headless/交互浏览器视觉验收为 `NOT_RUN`。  
代码版本：`phase2_9-work`，HEAD `f372e3f4e0702470eb91b2a32683e62590777840`。

## 实时技术面板

页面沿用现有Three.js展厅与 `visualization_bridge.py`。`ros-live.js`显示定位与布局、访客类型/位置来源、YOLOX匿名track与bbox坐标、RGB-D/CameraInfo/TF/Scan有效期、速度控制、Nav2参数回读、cmd_vel/odom、停止状态和导览历史。视觉估计与Gazebo脚本真值分开标注；没有保存相机视频时，页面明确说明未接入相机画面。

在 T07 实际运行期间读取 `http://127.0.0.1:8125/` 与 `/api/pose`；快照显示adaptive布局、`business_script`、游客Gazebo位置、Tour/QA真实状态、YOLOX匿名track、RGB-D、Scan和ROS速度源。快照是在导览完成后采集：部分视觉/深度/Scan/cmd/odom字段年龄超过阈值并返回 `fresh:false`/空值，页面代码把这些状态显示为无效/过期，不能继续冒充实时值。快照及页面响应在 `experiments/T08/live-panel/run-001/`；该快照不是视觉截图。

## 真实记录导出

来源为原有阶段2.9真实记录目录 `docs/phase2_9/experiments/WP04-regroup/visitor-full-20261123-125818/`，status为PASS，业务模式为 `business_script`。原始manifest、report和live_evidence只读打包；来源文件逐项SHA验证。最终导出位于 `experiments/T08/replay/visitor-full-20261123-125818-run-003/`：

- `replay.json` SHA256：`3bb0e05025ef67fbfb63beb8d3f9d68bf0803629d295b4d8b058a0aa3372167cc`
- SHA sidecar SHA256：`24f512a76fe17cd524871804ace99ca37e2353604a4d3f4ddfd8af0c9d41fde1`
- 源证据压缩包 SHA256：`e70414c30b269101f4f47ebcdbc6220f8885a7c26466a7a2e274575727071eaf`
- 导出来源manifest SHA256：`3f9c1d19d33fc56f22a075e7703cca9da47b8a7de2021aa2d24c7b6fa6ca47a9`
- 6050条事件：1273条odom、977条cmd_vel、1268条视觉团队观察、1266条匿名轨迹、1126条安全状态变化、106条Gazebo团队真值变化、34条导览状态变化。
- 实际轨迹：1269个机器人ROS TF位置点，3813个Gazebo `ModelStates` 游客位置点，明确标记ground truth；实际速度序列2250点，其中odom 1273、cmd_vel 977。
- 历史记录没有逐帧保存odom/cmd_vel接收时间。导出器以采样快照中的真实 `elapsed_sec - age_sec`恢复每个已有ROS样本时刻，并按原始odom stamp/唯一接收时刻去重；不插值、不从Gazebo真值构造机器人速度。
- RGB/depth视频未被来源run采集；回放标记其缺失，视觉bbox事件没有叠到不存在的图像上。没有wall clock映射时保持缺失。

浏览器页面的RECORDED_ROS2校验器已对真实导出执行SHA、manifest与只读模式检查；结果 `6050 events / 1269 robot pose / 3813 visitor pose / 2250 speed samples / controls_available=false`，见 `verification/t08-real-recording-node.log`。归档内manifest、report、live_evidence三个文件已解包逐项SHA/尺寸校验，见 `verification/archive-extract-check.json`。

## 本机只读HTTP服务

使用 `scripts/serve_replay.py`、仅绑定 `127.0.0.1:8126`；不创建ROS客户端，代码没有POST控制接口。固定资源 `/`、`/replay.js`、已校验 `/recording/replay.json` 和 `.sha256` 均返回200；路径穿越和 `/api/stop` GET返回404；POST `/api/stop`返回501。完整响应状态与SHA在 `verification/http-probe-run-002.json`。服务经Ctrl+C关闭，端口随后可重新绑定。

## 测试及保留的失败

- 新增 `tests/test_phase30_tour_replay.py` 先记录5项缺少导出器的RED；最终8项通过，覆盖来源一致性、单调事件、ROS TF与Gazebo真值分栏、命令/里程计样本、旧快照freshness-age映射、输出路径边界和源归档校验。最终日志 `replay/export-green-04.log` SHA256 `1698cf53738fece3fc128f68a2005bf90098cb09ffc528d80a18fe683159d622`。
- 定向Python回归在source ROS overlay后 `34 passed`，含导出器、现有回放、只读服务、可视化API与bridge；日志SHA256 `6d739408342262b5e9dc5d2d6494c6eb9e99f4f5a192928df3e2db7143c3608e`。未source overlay的一次运行因 `temi_interfaces` 不可导入而13项失败、21项通过，保留 `verification/t08-python.log`；它是环境调用缺overlay，不是最终代码结果。
- `node --check` 两个JS文件、`test-runtime.cjs`、`test_phase28_replay.cjs`通过；日志SHA256 `86a28c0ed5f4983a332f135275ab42291b4b62e0bf3a164978958e8ad82a211a`。
- 回放页面自身对真实run的校验器通过，另见上文。真实记录服务端HTTP检查通过。
- 修复导出器时发现较早采集的快照没有 `stamp_ns`/`received_monotonic_sec`；第一份真实导出run-002因此速度序列为0，未用作最终证据。新增根据已记录age映射并去重后，run-003得到2250个样本。早期相对路径导出错误与测试fixture错误分别保存在原日志及run-001/002输出目录，未覆盖或删除。

## 视觉验收限制

两次桌面自动化连接超时；Firefox 157.0.1的独立临时profile截图启动两次失败。本机另有用户Firefox进程（PID 500081），为保护用户会话，没有连接、关闭或改动它的profile。`verification/browser-visual-check.md`记录该结果。因而页面中文布局、Canvas曲线和console的人工浏览器检查仍为 `NOT_RUN`，不把Node/HTTP检查表述为视觉通过。
