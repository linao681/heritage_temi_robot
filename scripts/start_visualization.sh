#!/usr/bin/env bash
set -e
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
layout="${1:-official}"
if [[ "$layout" != official && "$layout" != adaptive ]]; then
  echo '用法: bash scripts/start_visualization.sh [official|adaptive]' >&2
  exit 2
fi
source /opt/ros/humble/setup.bash
export ROS_LOCALHOST_ONLY=1 ROS_DOMAIN_ID=211
export GAZEBO_MASTER_URI=http://127.0.0.1:11359
cd "$project_dir"
# 同一用户同一 Domain 只允许运行一套，锁随进程退出自动释放。
lock_path="/tmp/heritage-visualization-$(id -u)-211.lock"
exec 9>"$lock_path"
if ! flock -n 9; then
  echo '展厅仿真已经运行，请直接打开 http://127.0.0.1:8088/；不要重复启动。' >&2
  exit 1
fi
if ! python3 - <<'PY'
import socket
import sys
for port in (8088, 11359):
    sock = socket.socket()
    sock.settimeout(0.5)
    used = sock.connect_ex(('127.0.0.1', port)) == 0
    sock.close()
    if used:
        print(f'本机端口 {port} 已被占用，请关闭已有仿真后再启动。', file=sys.stderr)
        sys.exit(1)
PY
then
  exit 1
fi
setsid ros2 launch ./simulation/hall.launch.py "layout:=$layout" gui:=false 9>&- &
hall_pid=$!
setsid ros2 launch ./simulation/navigation.launch.py "layout:=$layout" 9>&- &
nav_pid=$!
cleanup() {
  trap - EXIT INT TERM
  kill -INT -- "-$nav_pid" "-$hall_pid" 2>/dev/null || true
  if [[ -n "${bridge_pid:-}" ]]; then kill -TERM "$bridge_pid" 2>/dev/null || true; fi
  wait "$nav_pid" "$hall_pid" 2>/dev/null || true
  if [[ -n "${bridge_pid:-}" ]]; then wait "$bridge_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 0' INT TERM
python3 scripts/visualization_bridge.py --layout "$layout" 9>&- &
bridge_pid=$!
wait -n "$hall_pid" "$nav_pid" "$bridge_pid" || true
echo '展厅服务已退出，正在关闭本次启动的组件。' >&2
kill -TERM "$bridge_pid" 2>/dev/null || true
wait "$bridge_pid" 2>/dev/null || true
