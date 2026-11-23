# 阶段2.9当前阻塞与风险

最新状态：2026-11-23 13:51 CST。视觉暂停handler修复后的完整`tests/`已624项通过；Gazebo视觉run没有重启，动态视觉仍是实景验收阻塞。

## 直接阻塞

1. **视觉模式完整导览未完成**：旧调速竞态已通过`stale_session`隔离。最新run `visitor-full-20261123-133255`实际视觉观察到的团队状态保守为UNKNOWN，触发zone_1安全暂停；运行器未识别通用暂停文案，导致run没有进入人工恢复流程并保留FAIL。handler现已依据observer `requires_manual_confirmation`修复，定向20/20及最新完整suite 624/624通过；尚无修复后的完整视觉路线run。
2. **动态视觉尚未验证**：`visitor-full-20261123-133255`有845条团队观察全部UNKNOWN（前向相机视野限制），848/850条深度样本新鲜，801条暂停记录中800条有新鲜odom停稳证据。未进行受控遮挡、离场/重入、深度/检测断流和逐帧人工标注；Gazebo真值未用于视觉判断。原始材料见该run的`evidence.md`。
3. **高优先级实验缺失**：E02 0/6；E04 0/3；速度标定0/3；E07-B未运行；持续靠近与传感器失效恢复、adaptive布局B Nav2路线未完成。WP01业务脚本成功不代表这些工作包通过。
4. **自动化回归已通过；实场景专项仍待完成**：视觉暂停handler修复后的完整`tests/`为624项通过（190.10秒、退出码0）；日志SHA见`docs/phase2_9/audit/full-regression-20261123-1351.log`。ROS2七包构建7/7。动态Gazebo、布局B、浏览器和硬件验收不由pytest替代。
5. **展示素材不齐**：已有六分钟稿、分镜、页纲和答辩材料；没有经验证的演示视频、最终PPTX/PDF和实时浏览器画面证据。
6. **实体Temi缺失**：硬件、SDK、底盘执行、物理制动、实体传感器、ASR/TTS、断网/电量处理现场验证均为`HARDWARE_REQUIRED`。

## 安全边界

Gazebo几何间隙不等于碰撞认证；激光回波不等于人员识别；前向相机不可确认被遮挡/位于身后的游客；配置限速不等于实测速度。没有真实设备、ASR/TTS或接触传感器时，材料必须保留这些限制。

## 环境状态

视觉仿真结束后已核对ROS Domain 226为空、端口11379和8102释放；最新pytest前后Domain 226也为空。用户授权退出本会话自启动用于测试的进程；最新进程检查没有发现本项目导览/Gazebo测试进程，没有停止其他用户进程。最新可用内存约7.7GiB，资源不再是主要阻塞。

## 2026-11-23 13:26 CST状态

- 最新official/business_script完整run `visitor-full-20261123-125818`和E07-A脚本掉队/集合/模拟人工恢复环节通过；其脚本游客和Mock Speak不属于视觉或实体验收。zone_3 LOST→GATHERED为21.42秒，对比此前约201.7秒为改善迹象，但没有固定seed控制对照，new run未记录actor XYZ。WP04为`PASS_WITH_RISK`。
- 完整`tests/`回归最新为622 passed，日志和SHA见`docs/phase2_9/audit/full-regression-20261123-1316.log`。测试后Domain 226由项目探针确认为空；本run端口11379/8102已释放，无run自有Gazebo/导览进程。
- E07-B视觉确认恢复、八阶段动态感知、E02/E04、三档速度标定、adaptive布局B、实时浏览器/回放仍待执行；真实temi/ASR/TTS与硬件安全保持`HARDWARE_REQUIRED`。
- 视觉部分run `visitor-full-20261123-133255`记录845条真实团队观察均为UNKNOWN、前向相机只见1–2人居多、800条暂停记录有新鲜odom停稳。运行器handler漏记通用安全暂停，现已修复并通过20项专项；run因未做人工恢复而保留FAIL，修复后完整视觉复测待做。原始数据与SHA见该run的`evidence.md`。

## 2026-11-23 13:51 CST状态

- 完整自动化回归已在最新代码上完成：624 passed，190.10秒；运行前后Domain 226均空。日志为`docs/phase2_9/audit/full-regression-20261123-1351.log`，SHA-256 `609b53c935b48363831dd1cafd4200112991db64f5932cd81c179e5d5db52d74`。
- 用户允许退出本会话测试进程；当前检查没有发现本项目导览/Gazebo测试仍在运行。未终止其他用户进程，也没有重新启动Gazebo。
- 最新视觉handler修复已纳入624项suite；仍缺修复后的视觉模式恢复run、动态八阶段、E02/E04、速度标定、E07-B、adaptive布局B及浏览器验收。
