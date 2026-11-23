# Vision-conservative partial run

## Result

**FAIL — partial run intentionally stopped; full tour and operator-resume path not reached.** This run provides new real-camera/YOLOX/RGB-D evidence that the front-facing observer correctly retained `UNKNOWN` when it could not establish team-wide coverage, and the simulator confirmed a stationary safety stop. A runner bookkeeping gap prevented the external-operator pause handler from recognizing the generic “导航安全停车” reason; the current run was stopped after preserving the finding. The runner fix and regression test are recorded separately. The run is not a dynamic eight-stage vision pass.

## Run identity and setup

- Run ID `visitor-full-20261123-133255`; branch `phase2_9-work`; HEAD `24c14231de61840a11c5462805df0cd6160af84d`.
- Start `2026-11-23T05:32:55.927437Z` (13:32:55 CST); the runner report elapsed time is `266.597 s`; live telemetry covers `259.948 s`.
- Official layout, ROS Domain 226, Gazebo port 11379, web port 8102; three Gazebo scripted actors. Mode `vision_conservative`; manifest records `team_truth_used_for_decision=false`.
- Preflight passed: 7.727 GiB available memory, 44.541 GiB disk, load 0.015 per CPU, no Gazebo process, both ports available.
- Tour started and consent was accepted, then remained `PAUSED` at `zone_1`; no external resume was sent. Full route, QA, and exit were not reached. Report status remains `FAIL`, error `演示被操作员中断`.

## Actual perception and stop evidence

- 850 live samples, median sample interval `0.303 s`; the observer is present in 845 samples.
- All 845 team observations are `UNKNOWN` under `forward_only` coverage: 818 show 1/3 tracks, 21 show 2/3, 5 momentarily show 3/3, and 1 shows 0/3. Even the five 3/3 samples remain `UNKNOWN` because the forward-only camera does not establish team-wide coverage. This is the intended conservative result; no rear-view capability is inferred.
- Anonymous tracker IDs sampled: `vision-e0-3` 844, `vision-e0-1` 27, `vision-e0-2` 7. These counts do not establish identity accuracy or ground-truth ID switches.
- Fresh depth samples: 848/850. Reported valid person-distance values ranged from `2.224 m` to `3.345 m` in this partial run; no independent reference-distance accuracy measurement was made.
- Among 801 telemetry samples while the Tour was paused, 800 had `stop_confirmed=true`, fresh odometry, and absolute linear velocity at or below `0.02 m/s`; the maximum observed absolute paused odometry speed was `0.0000416 m/s`. The runner’s `pause_stop_evidence` array is null because its generic-reason handler did not collect these samples; the underlying live evidence remains intact.
- The separate Gazebo-script team feed reported count 3 in 840 samples and `gathered=true` in 815; this is scripted actor/status data, not visual evidence and was not used by the conservative team decision. Its status file does not contain actor XYZ positions.

## Root cause and correction

The runner only recognized vision pauses when the Tour reason string contained “视觉” or “观察”. The actual paused reason was the generic “导航安全停车”, even though the camera observation was fresh `UNKNOWN` and required manual confirmation. Consequently the runner did not save its stop record or mark the vision pause for external resume tracking. A test was added first and failed on this exact generic-reason case; after the fix, `tests/test_phase29_full_demo.py` passes 20/20. The runner now bases this handling on the visual observer’s `requires_manual_confirmation` field and passes that observer payload, not the Gazebo scripted-team payload, in vision mode.

## Evidence files and SHA-256

- `report.json`: `aa5de4b0583e2d969c5bc887700bbed97615cf1aec65777a15b8f2e6b9ea7155`
- `manifest.json`: `43b3391e6740f3ea9dbd57abe30d31288ad8576e54ef19a154b29880a4f00770`
- `live_evidence.jsonl`: `3983c14f05e7bae667444776aece3625c13571704a556cd6aff651bfdbc39e63`
- `system.log`: `9e3e49cc8dc2d78c9527a314bac8faefec317713410f7cc1126ff093c5baba26`
- `system/navigation.log`: `61c6ab7e59935b71a941a3f57c2f3b5edcb07fad80d6328c8237997afc5ccb27`
- `system/visitor_team.jsonl`: `76a9dc4dd729f27acd2c9ea70d178d3a1467ea1da8ad90b689e0db3780a5b34f`

## Cleanup and limits

After the runner stopped, only its Domain 226 ROS CLI daemon remained. That daemon was stopped, the project preflight confirmed Domain 226 empty, ports 11379/8102 were released, and no run-created Gazebo or demo process remained. No other user ROS/Gazebo process was stopped.

No RGB/depth image frames were archived in this run; it retains live inference, track, distance, and odometry telemetry only. Short occlusion, deliberate entry/leave/re-entry, invalid-depth injection, stale-detection handling, and operation-confirmed recovery remain unverified.
