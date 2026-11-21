#!/usr/bin/env bash
# 只启动本机 Mock 系统，不连接实体机器人。
set -e
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
if [[ ! -f /opt/ros/humble/setup.bash || ! -f "$project_dir/ros2_ws/install/setup.bash" ]]; then
    echo '缺少 ROS2 环境或项目构建产物，请先运行 scripts/build_ros2.sh' >&2
    exit 1
fi
source /opt/ros/humble/setup.bash
source "$project_dir/ros2_ws/install/setup.bash"
cd "$project_dir"
exec python3 "$project_dir/scripts/start_mock_system.py" "$@"
