# 网页展厅 ROS 仿真联动

复用交接包的 Three.js 展厅和模型，在独立副本 `visualization/ros_hall/` 增加只读位置显示。机器人位置取自 ROS 的 `map → base_footprint` 定位变换，映射网页 x=ROS x、z=-ROS y，朝向换算为网页机器人局部 +Z 前向。连接和仿真时钟失效后顶部显示离线并冻结最后位置。

启动：

```bash
cd ~/heritage_workspace/heritage_temi_robot
bash scripts/start_visualization.sh official
```

用浏览器打开 http://127.0.0.1:8088/ 。默认官方布局，另一套可运行 `bash scripts/start_visualization.sh adaptive`。服务仅绑定本机；终端 Ctrl+C 会停止本次启动的进程。

在另一终端可显式启动官方五区模拟导航：

```bash
cd ~/heritage_workspace/heritage_temi_robot
source /opt/ros/humble/setup.bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=211
python3 scripts/check_nav2.py --layout official --full-tour
```

联动页隐藏网页原本的业务控制、演练按钮及模拟仪表；这些按钮没有接入 ROS。游客、展品、场景灯光和镜头仍为原网页可视化，不是 Gazebo 的人流或传感器状态。此页只订阅显示，不控制机器人；它不是完整导览交互联动。

本次使用实际 Gazebo/Nav2 单点导航验证：接口返回位置从 (-12.65, 7.90) 移至 (-11.15, 2.79)，ROS action 成功，仿真停止后接口变为 disconnected。坐标转换自动化测试通过。当前环境浏览器自动化打开超时，页面三维实际显示尚需用户本机检查。

## 路线状态联动

`check_nav2.py` 发布模拟路线的前往、到站、完成或异常状态，网页顶部显示站名与进度；状态超过三秒未更新时显示待命/无新鲜路线状态。本功能是 Nav2 测试路线的状态展示，尚未将原 Mock 导览状态机、讲解播报或游客同意接入 Gazebo。

实际单站联动验证：网页接口在运动中显示 NAVIGATING / 非遗概览，Nav2 到站并确认静止后显示 COMPLETED，定位误差 0.216 米。原有服务运行时需重启启动脚本才能加载新的后台代码；刷新网页加载新版界面。

启动脚本限制同一用户在 Domain 211 只运行一套，并检查展示和 Gazebo 端口；重复执行会提示已经运行，避免多套导航服务互相干扰。2026-11-21 排查发现同时运行两套导航可导致目标 ABORTED；清理重复节点后，实测第一站正常到达，再次从已到站位置发送同一目标亦成功。
