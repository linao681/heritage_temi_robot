# 阶段3.0阻塞与风险

更新时间：2026-11-23 19:59 CST

| 事项 | 状态 | 证据/影响 | 后续 |
|---|---|---|---|
| Gazebo/ROS实验域与端口 | 本阶段run均已预检/收尾 | T04/T05选择前执行DDS和端口探针；T05 Domain 207结束后为空，11395/8120已释放。首个端口探针的转义失败已保留并通过独立重检修正 | 每轮继续重新选择，不照抄旧值 |
| T04 wait暂停恢复证据 | FAIL（后续复跑） | `visitor-full-20261123-164811`的route_index=0暂停没有后续同目标新UUID或配对cmd_vel/odom；其它6个暂停有证据。前一轮`160651`完整路线6个暂停通过 | 保留失败；T10回归并在报告中明确限制，不把Tour COMPLETED当作全部暂停通过 |
| 视觉全队确认 | 已知限制 | 阶段2.9的845条视觉观察全为UNKNOWN；本阶段前向相机不能确认后方队伍，`vision_conservative`继续UNKNOWN并需测试操作员确认 | 不扩大相机视野能力声明 |
| E04传感器归因 | PASS_WITH_RISK | run-004人员距离与激光障碍距离在接近停车时同时有效；几何最小间隙0.544m来自URDF/SDF代理，没有接触传感器，不能给出碰撞安全认证 | 后续可做激光盲区/传感器消融；不重跑已通过的同一场景强求更强结论 |
| E02稳定速度对照 | NOT_VERIFIED | 空场/单人/三人数据已采集；同一zone_1段的最长有效稳定窗仅14/16/10样本，均不足2秒/20样本；Nav2限速读回均0.300m/s。未证明人数变化导致物理减速，密度没有独立有效值。见 `experiments/T06/E02-evidence.md` | 之后若有足够资源，单独设计更长的有效直行对照；不得降低分析门槛 |
| E02单人全程 | FAIL | 初轮演员子进程漏听导航；匹配门修复后演员truth PASS，但Tour因“机器人通信中断，停止状态未确认”失败。相关日志已保留 | 不重复相同路线强求通过；T10检查通信/停车证据后再决定是否作新专项 |
| 布局B适配 | PASS_WITH_RISK | 静态映射82项通过；adaptive单点、6目标Nav2路线与Tour Manager完整路线均完成。业务模式为business_script、一名Gazebo演员、模拟同意与Mock播报；不代表三人视觉掉队或实机适配。见 `experiments/T07/adaptive-layout-evidence.md` | 后续需实体temi/现场地图验证；本阶段无其他布局B阻塞 |
| T08浏览器视觉验收 | NOT_RUN | 桌面CUI连接两次超时；独立Firefox临时profile启动两次失败；检测到用户Firefox仍在运行，未连接或改动该profile。Node/HTTP验证已通过，未获得截图 | 用户验收时用已打开浏览器访问回放页，人工检查中文、轨迹/速度Canvas和console；详见 `experiments/T08/replay/verification/browser-visual-check.md` |
| T08录制图像 | NOT_COLLECTED | 选定阶段2.9来源run有真实ROS观测/位姿/速度和Gazebo游客位置，但没有RGB/depth图像帧；因此不能将bbox叠到不存在的画面 | 后续单独启用图像采集并验证隐私/哈希；本次回放明确标缺失、不造帧 |
| 资源 | 可用但临界 | T05启动时可用内存6.2 GiB，运行时约4.6 GiB；无swap。重型实验仍需串行并使用runner现有资源门 | 下轮预检低于门槛则转离线任务 |
| 实体Temi/真实播报 | HARDWARE_REQUIRED | 无实体硬件；Timed subtitles/Mock Speak仅仿真反馈 | 不声称实体验证或实体TTS |

若同一实验问题三次失败，新增具体日志、根因和替代任务；保留全部失败记录。
