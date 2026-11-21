#!/usr/bin/env bash
# 使用第三步已经验证的项目专属 Android 工具链，不替换系统 JDK/SDK。
set -e
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$project_dir/android/temi_heritage_bridge"
env JAVA_HOME="$project_dir/.toolchain/jdk-17" \
  GRADLE_USER_HOME="$project_dir/.toolchain/gradle" \
  ANDROID_HOME="$project_dir/.toolchain/android-sdk" \
  ANDROID_SDK_ROOT="$project_dir/.toolchain/android-sdk" \
  ANDROID_USER_HOME="$project_dir/.toolchain/android-user" \
  ./gradlew :app:testDebugUnitTest :app:assembleDebug --no-daemon --max-workers=4 "$@"
