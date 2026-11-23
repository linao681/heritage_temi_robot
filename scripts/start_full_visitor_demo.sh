#!/usr/bin/env bash
set -Eeuo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$project_dir"
set +u
source /opt/ros/humble/setup.bash
set -u
bash scripts/build_ros2.sh
set +u
source ros2_ws/install/setup.bash
set -u
exec .venv/bin/python scripts/run_visitor_full_demo.py "$@"
