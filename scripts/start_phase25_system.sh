#!/usr/bin/env bash
set -Eeuo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
domain_id="${1:-225}"
gazebo_port="${2:-11361}"
web_port="${3:-8089}"
[[ "$domain_id" =~ ^[0-9]+$ ]] && (( domain_id >= 0 && domain_id <= 232 )) || {
  echo 'ROS 域必须为 0–232' >&2; exit 2;
}
[[ "$domain_id" != 211 && "$domain_id" != 219 ]] || {
  echo '域211和219有现存仿真，本脚本拒绝使用这两个域。' >&2; exit 2;
}
for port in "$gazebo_port" "$web_port"; do
  [[ "$port" =~ ^[0-9]+$ ]] && (( port >= 1024 && port <= 65535 )) || {
    echo '端口必须为1024–65535' >&2; exit 2;
  }
done
[[ "$gazebo_port" != "$web_port" ]] || { echo 'Gazebo与网页端口不能相同' >&2; exit 2; }
ros_setup="${PHASE25_ROS_SETUP:-$project_dir/ros2_ws/install/setup.bash}"
[[ -f /opt/ros/humble/setup.bash && -f "$ros_setup" ]] || {
  echo '请先安装 ROS2 Humble 并构建 ros2_ws。' >&2; exit 1;
}
[[ -s "$project_dir/assets/vision/object_detection_yolox_2022nov.onnx" ]] || {
  echo 'YOLOX 模型文件缺失。' >&2; exit 1;
}

set +u
source /opt/ros/humble/setup.bash
source "$ros_setup"
set -u
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID="$domain_id"
export GAZEBO_MASTER_URI="http://127.0.0.1:$gazebo_port"
cd "$project_dir"

python3 - "$gazebo_port" "$web_port" <<'PY'
import socket
import sys

for port in map(int, sys.argv[1:]):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            raise SystemExit(f'本机端口 {port} 已被占用，未启动任何组件。')
PY

exec 9>"/tmp/heritage-phase25-$(id -u)-$domain_id.lock"
flock -n 9 || { echo "阶段2.5系统已在 ROS 域$domain_id 运行。" >&2; exit 1; }
python3 scripts/phase25_preflight.py --check-domain-empty || {
  echo "ROS 域$domain_id 非空，已停止启动。" >&2; exit 1;
}

stamp=$(date +%Y%m%d-%H%M%S)
log_dir="$project_dir/docs/experiments/phase2_5/system_runs/$stamp"
mkdir -p "$log_dir"
pids=()
start_group() {
  local name=$1
  shift
  setsid "$@" 9>&- >"$log_dir/$name.log" 2>&1 < /dev/null &
  pids+=("$!")
  printf '%s\n' "${pids[-1]}" >"$log_dir/$name.pid"
}
alive() {
  local pid
  for pid in "${pids[@]}"; do kill -0 "$pid" 2>/dev/null || return 1; done
}
cleanup() {
  trap - EXIT INT TERM
  local i pid
  for ((i=${#pids[@]}-1; i>=0; i--)); do
    pid=${pids[i]}
    kill -INT -- "-$pid" 2>/dev/null || true
  done
  for ((i=0; i<50; i++)); do
    local any_alive=false
    for pid in "${pids[@]}"; do
      if kill -0 -- "-$pid" 2>/dev/null; then any_alive=true; fi
    done
    [[ "$any_alive" == false ]] && break
    sleep 0.1
  done
  for pid in "${pids[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT
trap 'exit 0' INT TERM

echo "日志目录：$log_dir"
start_group hall ros2 launch "$project_dir/simulation/hall.launch.py" layout:=official gui:=false
deadline=$((SECONDS + 60))
until ros2 service list 2>/dev/null | rg -q '^/spawn_entity$'; do
  alive || { echo 'Gazebo 启动失败，查看 hall.log' >&2; exit 1; }
  (( SECONDS < deadline )) || { echo 'Gazebo 服务等待超时' >&2; exit 1; }
  sleep 1
done
start_group navigation ros2 launch "$project_dir/simulation/navigation.launch.py" layout:=official
sleep 2
start_group gateway python3 scripts/start_nav2_gateway.py --layout official --domain-id "$domain_id"
start_group knowledge ros2 run heritage_knowledge knowledge_node --config config/knowledge.yaml
start_group tour ros2 run heritage_tour_manager tour_manager --config config/submission_system.yaml --exhibits config/submission_exhibits.yaml
start_group speed ros2 launch temi_speed_controller speed_control.launch.py mock_mode:=false allow_simulated_sources:=true
start_group perception ros2 launch visitor_perception sensor_fusion.launch.py simulation_mode:=true model_path:=assets/vision/object_detection_yolox_2022nov.onnx confidence:=0.5
start_group visualization .venv/bin/python scripts/visualization_bridge.py --layout official --port "$web_port" --domain-id "$domain_id"

preflight_timeout="${PHASE25_PREFLIGHT_TIMEOUT_SEC:-240}"
echo "等待阶段2.5 readiness（域$domain_id，网页 http://127.0.0.1:$web_port/）"
if ! python3 scripts/phase25_preflight.py --timeout-sec "$preflight_timeout" >"$log_dir/preflight.json" 2>"$log_dir/preflight.err"; then
  cat "$log_dir/preflight.json" >&2 || true
  cat "$log_dir/preflight.err" >&2 || true
  echo '系统未通过预检，组件正在按本次启动范围关闭。' >&2
  exit 1
fi
cat "$log_dir/preflight.json"
echo '阶段2.5仿真系统已就绪；按 Ctrl+C 只关闭本次启动的进程组。'
wait -n "${pids[@]}" || true
echo '有组件已退出，正在关闭本次启动的进程组。' >&2
