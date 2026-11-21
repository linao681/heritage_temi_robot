#!/usr/bin/env bash
set -e
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
layout="${1:-official}"
[[ "$layout" == official || "$layout" == adaptive ]] || { echo '用法: bash scripts/start_submission_tour.sh [official|adaptive]' >&2; exit 2; }
source /opt/ros/humble/setup.bash
source "$project_dir/ros2_ws/install/setup.bash"
ros_domain_id="${ROS_DOMAIN_ID:-211}"
[[ "$ros_domain_id" =~ ^[0-9]+$ ]] && (( ros_domain_id >= 0 && ros_domain_id <= 232 )) || { echo 'ROS_DOMAIN_ID 必须在 0–232 之间' >&2; exit 2; }
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID="$ros_domain_id"
cd "$project_dir"
exec 9>"/tmp/heritage-submission-tour-$(id -u)-$ROS_DOMAIN_ID.lock"
flock -n 9 || { echo '五区导览组件已运行' >&2; exit 1; }
python3 scripts/start_nav2_gateway.py --layout "$layout" --domain-id "$ROS_DOMAIN_ID" 9>&- &
gateway_pid=$!
ros2 run heritage_knowledge knowledge_node --config config/knowledge.yaml 9>&- &
knowledge_pid=$!
ros2 run heritage_tour_manager tour_manager --config config/submission_system.yaml --exhibits config/submission_exhibits.yaml 9>&- &
tour_pid=$!
ros2 launch temi_speed_controller speed_control.launch.py mock_mode:=false allow_simulated_sources:=true 9>&- &
speed_pid=$!
cleanup() {
  kill -TERM "$speed_pid" "$tour_pid" 2>/dev/null || true
  wait "$speed_pid" "$tour_pid" 2>/dev/null || true
  kill -TERM "$gateway_pid" "$knowledge_pid" 2>/dev/null || true
  wait "$gateway_pid" "$knowledge_pid" 2>/dev/null || true
}
trap cleanup EXIT
echo '导览组件启动中：服务就绪后需显式调用 start 和 accept；语音为无音频模拟。'
wait -n "$gateway_pid" "$knowledge_pid" "$tour_pid" "$speed_pid" || true
echo '导览组件已退出，正在关闭本次进程。' >&2
