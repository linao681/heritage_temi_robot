# T10 最终回归摘要

- 日期：2026-11-23；分支`phase2_9-work`，HEAD `f372e3f4e0702470eb91b2a32683e62590777840`。
- 环境：Ubuntu 22.04 / ROS2 Humble；Domain 220，经实际空域探测确认后使用；可用内存约8.5 GiB，磁盘可用45 GiB。未发现Gazebo/Nav2用户进程；没有启动重型Gazebo。测试前后Domain `other_nodes=[]`，回归使用的端口均可绑定。
- ROS2构建：`bash scripts/build_ros2.sh`，7/7包通过，colcon 9.01秒；日志`build.log`，SHA-256 `8a4ac62610af958f6f4cdea6bb9208306e01475470b65a80c8ba8afeccd151dc`，退出码0。
- 完整命令：`source /opt/ros/humble/setup.bash && source ros2_ws/install/setup.bash && ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=220 HERITAGE_TEST_ROS_DOMAIN_ID=220 .venv/bin/python -m pytest -q tests`；未排除测试，`680 passed in 189.75s`，退出码0；日志`pytest-full.log`，SHA-256 `91af50f880851a035f8d7d316a32662d7219bdd8b98ab084c92e22823f3ed837`。输出没有failed或skipped项。
- 独立定向套件：full-demo 28、tour-manager 31、tour ROS integration 17、dynamic vision/tracking 23、recording 26、speed calibration/controller 64、replay 19、WebSocket/gateway 36、安全竞态/ROS shutdown 22、新增phase30测试26；各组退出码均为0。日志与单项SHA保存在本目录；这些组与完整套件覆盖有交集，不相加作为额外总测试数。JSON摘要SHA-256 `1703cd1b1df85fc90cd9a38deacfb88b9c24b818bee124a02001865eebea1bba`。
- 静态与接口检查：17个Python文件AST通过；`scripts/*.sh`全部`bash -n`通过；`replay.js`、`ros-live.js`的`node --check`通过；`tests/test_phase28_replay.cjs`、`visualization/ros_hall/test-runtime.cjs`通过；ROS接口`ConfirmTeamRecovery`能从新overlay显示；`git diff --check`退出码0。详细日志/退出码与SHA列表在`static-checks.sha256`。
- 日志最大文件2055字节；本轮没有大体积T10原始日志需要gzip，未修改或删除此前失败/原始证据。
- 本次只做构建、自动化和接口/格式检查，E02/E04/视觉动态等Gazebo实验以各自T04–T08证据为准；本轮T10没有新增Gazebo或实体实验。
