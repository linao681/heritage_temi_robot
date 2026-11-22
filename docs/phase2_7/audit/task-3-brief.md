# Task 3 brief: E06 recovery qualification and Nav2 safety review

Read the user specification at `/home/linao/.codex/attachments/13af0822-ba81-451c-93ed-99669e188d8d/已粘贴的文本.txt`, sections “P0任务3：修复E06恢复状态时序” and “P1任务8：导航与安全控制代码专项审查”, plus project `docs/phase2_7/implementation_plan.md` section 4.

## Scope

Audit and, where a failing test proves a defect, make the smallest fix across:
- `ros2_ws/src/temi_speed_controller/temi_speed_controller/{speed_policy.py,speed_controller_node.py}`
- `ros2_ws/src/visitor_perception/visitor_perception/{perception_fusion.py,ros_perception_fusion.py}`
- `ros2_ws/src/temi_bridge/temi_bridge/{nav2_transport.py,nav2_backend.py}`
- `ros2_ws/src/heritage_tour_manager/heritage_tour_manager/{tour_manager.py,ros_tour_node.py}`
- relevant `tests/`, preferably adding `tests/test_phase27_recovery.py`.
- write `docs/phase2_7/safety/nav2_review.md` with 20 checklist rows and evidence/repro/conclusion/fix.

Key requirements: use monotonic safety windows; stale, out-of-order, interrupted, or time-regressing input resets the window; require fresh perception, valid laser, localization/communication, and a matching STOP_CONFIRMED UUID; re-check active task and pause source before sending; manual stop/team wait/fault latch cannot auto-resume; one in-flight resume future; stale futures and old stop confirmations cannot unlock a new session; no timing sleeps to hide races. Preserve existing service/message compatibility unless a failing test demonstrates a necessary schema change. Do not treat NO_PERSON_OBSERVED as confirmed person-clear without valid safe laser evidence.

Audit all 20 issues from original spec: action cancel race; duplicate stop requests; stop confirmation/new UUID conflict; stale odom; stale TF; reversed sensor timestamps; angular velocity during turning; duplicate navigation recovery; failed Nav2 dynamic parameter updates; partial parameter rollback; transient fusion invalidity; jumping person range; consecutive YOLOX misses; positive-infinity LaserScan returns; concurrent ROS callbacks; replayed old task after communications loss; manual cancel vs automatic recovery; stale navigation complete while paused; motion after stop confirmation; cold-start after sensor recovery.

## Evidence and workflow

- Start with failing regression tests or a small replay of the existing E06 event timing; keep original phase2.6 evidence immutable.
- Run only targeted test files for this task and any required source/build checks. Report exact commands, exits, counts and log paths.
- Do not run Gazebo, touch other ROS domains, alter historical evidence, commit or push.
- Do not modify the phase 2.7 plan checkboxes; report conclusions to the coordinator for review.
- Keep all changes within the named ROS packages, tests, and `docs/phase2_7/safety/`.
- Save the full implementation/review report to `docs/phase2_7/audit/task-3-report.md`.
- Do not commit. The user explicitly prohibited automatic Git commit/push.
