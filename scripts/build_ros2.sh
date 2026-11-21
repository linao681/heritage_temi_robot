#!/usr/bin/env bash
# ROS2 Humble rosidl 对中文构建路径的解析兼容性问题：使用纯 ASCII 构建目录。
set -e

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
workspace="$project_dir/ros2_ws"
source /opt/ros/humble/setup.bash

# 每次使用 mktemp 创建当前用户独享的目录，避免复用不可信的共享 CMake 缓存。
build_base=$(mktemp -d /tmp/heritage-temi-ros2-build.XXXXXX)
printf 'ROS2 build cache: %s\n' "$build_base"

cd "$workspace"
colcon build --base-paths src --build-base "$build_base" --install-base "$workspace/install" "$@"
