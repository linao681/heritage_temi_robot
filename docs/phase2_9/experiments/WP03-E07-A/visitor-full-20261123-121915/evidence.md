# E07-A business-script partial run

## Result

**FAIL — operator-interrupted partial run.** The user asked to stop this session's test. It had completed the entrance reception and consent, the waiting point, and zones 1–4; it was navigating to zone 5 when interrupted. The exit and full-route completion were not reached. The report's `FAIL` is retained and is not counted as a completed-tour pass.

## Run identity and sources

- Run ID: `visitor-full-20261123-121915`
- Branch / source revision: `phase2_9-work` / `24c14231de61840a11c5462805df0cd6160af84d`; dirty source hash in the manifest: `0428c9b1f461e6a785cd4b91e1a19b054f1e9d79dbc63225c03b2b84d651391e`.
- Start: `2026-11-23T04:19:15.760934Z` (12:19:15 CST); elapsed: 447.396 s.
- Layout: `official`; ROS Domain: 226; Gazebo port: 11379; web port: 8102.
- Mode: `business_script`; three Gazebo scripted actors supplied team truth and drove the business-team decision. Consent and operator resume were scripted. Speech was timed subtitles; there was no physical temi audio.
- Startup preflight: ready; 7.779 GiB available memory, 44.716 GiB free disk, load 0.0206 / 16 CPU cores, no Gazebo before this run, requested ports available.
- Map hashes: `official.yaml` `039fdaf1dd600daece245f0d558c1221a5fa7b407afd8f73319e32170cb89f0c`; `official.pgm` `69793ba58c6a8f69ca28c75b2b524cfed006c664019a3e02cbcbb6ea1a5ec615`; goals `4bac876b5c3287a62eded8ec38546b66f5e2ed8ab204924396064e6816332e6f`.

## Observed partial E07-A behavior

- The run recorded six scripted gather requests and six accepted scripted resume actions. Nav2 logs contain five successful goals and seven canceled goals; cancellation is direct evidence of action cancellation, not by itself evidence of a stationary robot.
- Six tour pause windows have fresh odometry samples matching the paused session. During samples with `stop_confirmed=true`, the maximum absolute odometry linear speed per window was 0.0071 m/s; all these samples were at or below 0.02 m/s. This supports the simulator's stationary-stop check for the six observed pauses.
- The last dropout occurred while traveling toward zone 3. Three visitors were expected; the simulated team reported `LOST`, with 4.735 m trail lag and `gathered=false`. The robot held the same target and stayed stop-confirmed while the scripted trailing visitor took a long route around mapped geometry. `GATHERED` returned around elapsed 351.6 s; scripted operator resume was accepted at 353.79 s; navigation resumed around 354.1 s.
- This final pause lasted about 201.7 s. The initial joining path contained 68 grid waypoints at a 0.2 m grid resolution. From 654 live Gazebo actor-position samples between elapsed 152.4–351.6 s, the sampled polyline lower bound was 12.971 m, net displacement 6.762 m, and average sampled path speed 0.0651 m/s. This is a real business-script/Gazebo truth measurement, not visual tracking or a controlled before/after comparison.
- The high-rate raw actor trace contains 86,459 updates over 440.617 s (196.2 Hz average; 3.30 ms median interval). The Gazebo model-state plugin publishes at 20 Hz. The movement loop's median interval therefore creates ~2.8 mm steps at its configured 0.85 m/s pace, below the 20 mm `move()` readback tolerance. Before the fix, `wait_for_model_pose()` could accept a cached pose up to 0.5 s old if it remained within tolerance; the next step could then be computed from the same old pose. This code/data path explains the measured low actor speed. The fix now requires a `/gazebo/model_states` sample newer than the `SetEntityState` service acknowledgment before accepting the move readback; direct Gazebo entity-state readback remains the timeout fallback.
- The fix's unit-level freshness and movement-contract tests pass. A new Gazebo run is still required to measure actor pace and collection wait after the fix; until then WP04 remains unverified.
- The last captured live row was `NAVIGATING` to zone 5 with speed control active and `stop_confirmed=false`. The process was intentionally stopped during motion, so there is no terminal-stop confirmation or complete-tour claim for this run.

## Shutdown and reproducibility

After the user authorized stopping the test they had identified as ours, the run received SIGINT. Some launcher-owned child processes remained; only process groups created by this run were then sent SIGTERM. The project preflight subsequently reported Domain 226 `empty: true`; PIDs from this run were absent; ports 11379 and 8102 were no longer listening. No other ROS/Gazebo process was targeted.

Reproduction command (the run itself used this command):

```bash
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
export ROS_LOCALHOST_ONLY=1
timeout 1000s .venv/bin/python -u scripts/run_visitor_full_demo.py \
  --layout official --team-decision-mode business_script --domain-id 226 \
  --gazebo-port 11379 --web-port 8102 --timeout-sec 900 \
  --output-dir docs/phase2_9/experiments/WP03-E07-A
```

The command above describes the original launch; normal use should select a newly verified empty domain and free ports.

## Preserved evidence hashes

- `report.json`: `77ea1df5bdd7ba66bd1c3908db35c50b588bcd65b3d2b4e398ee54d1206d794f`
- `manifest.json`: `e48668a0c440e978b78b60bf42fa3ac0c1a85ec37e0467f4141715599df18d45`
- `live_evidence.jsonl`: `60ba0d57d9f2549d414b3636a3d6f780ee5871f39f2f5d501979cb64f71b1aa9`
- `system.log`: `6be6c336b7c7f6a381ad3d2fe5eb2a3c0a23a3cacfb23ec778f745607476789f`
- `system/navigation.log`: `2c999a9ecd4c3323c388b0d94bbd3a1f51374e7b5a3f008c757a8e11b6bc401f`
- `system/visitor_team.jsonl`: `339794eb7c6a262cbe352e11f3ed9fd2b6988134f8399d836ba4893bb43deb27` (large raw actor trace).
