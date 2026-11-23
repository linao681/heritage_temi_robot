# WP04 post-fix business-script full-tour run

## Result

**Full scripted business tour: PASS. WP04 regroup-efficiency result: PASS_WITH_RISK.** The run completed the entrance wait, all five zones, and exit, with a knowledge-base answer and fresh odometry at the final stop. One scripted zone-3 dropout reached `GATHERED` 21.42 s after the team status entered `LOST`; the earlier interrupted run measured about 201.7 s for its zone-3 collection. This is encouraging post-fix evidence, but it is not a controlled same-seed comparison: this run does not contain sampled actor XYZ positions, and no repeated fixed-seed trial was made.

## Run identity and setup

- Run ID: `visitor-full-20261123-125818`
- Branch / HEAD: `phase2_9-work` / `24c14231de61840a11c5462805df0cd6160af84d`; worktree was dirty and the run manifest records its source hashes.
- Start: `2026-11-23T04:58:18.056180Z` (12:58:18 CST); runner elapsed `396.386 s`; Tour Manager elapsed `381.869 s`.
- Layout/map: `official`, `simulation/generated/official.yaml`; map SHA-256 `039fdaf1dd600daece245f0d558c1221a5fa7b407afd8f73319e32170cb89f0c`.
- Team mode: `business_script`; three Gazebo scripted visitor actors supplied the team truth and business decision state. Consent, gather, and resume were simulated operator actions. Speech used timed subtitles; no physical temi audio was produced.
- ROS Domain `226`; Gazebo port `11379`; web port `8102`; configured run timeout `900 s`.
- Startup resource check: ready, 7.776 GiB available memory, 44.563 GiB free disk, load 0.02875 over 16 CPU cores; no Gazebo process before launch and requested ports available.

## Full-tour evidence

- The recorded visit sequence is `wait`, `zone_1` through `zone_5`, `exit`; final Tour state is `COMPLETED` and the QA state is finished.
- Navigation motion evidence is complete for the six reported motion targets (`zone_1`–`zone_5`, `exit`): respectively 58/58, 117/116, 149/149, 130/129, 169/167, and 211/211 paired cmd_vel/odom motion samples. These are the report’s target-scoped samples; they do not claim a separate paired-motion count for the entrance wait point.
- The question matched knowledge entry `music_types`; answer source was China Intangible Cultural Heritage Network, “潮州音乐”; the run reports `spoken: true` for the timed/mock speech action.
- The final stop is confirmed by a fresh odometry sample: absolute linear speed `0.001129 m/s`, sample age `0.0332 s`, `tour.is_moving=false`. The terminal cmd_vel sample is stale (age `3.590 s`) and is not presented as final-stop evidence.
- Tour history contains seven `PAUSED` transitions. The runner report contains five distinct pause-stop records, all confirmed with fresh odometry; the highest recorded absolute linear speed was `0.00654 m/s`. Thus not every pause in Tour history has a corresponding stop record in the report.

## E07-A / regroup observation

- The runner issued six scripted `gather` actions and six scripted `resume` actions; all recorded actions were accepted. The navigation log contains nine “goal succeeded” and seven “goal canceled” messages.
- During the zone-3 dropout, the team status entered `LOST` with maximum recorded lag `4.7428 m`; it returned to `GATHERED` after `21.42 s`. The simulated operator resume was accepted after the gathered state, and the same zone-3 target resumed under a new navigation session UUID (`45d9c7474ce04eef8f9601b469649c12` stopped; `1bc8f3f47a47472789b875a637e10cd4` resumed).
- The prior partial run `visitor-full-20261123-121915` reported about `201.7 s` from its last dropout pause through collection/operator resume. The two observations share official layout, three scripted visitors, and business-script mode, but were not run with a fixed seed and actor XYZ is absent from this run’s status log. Treat the difference as indicative, not a controlled causal estimate.
- `system/visitor_team.jsonl` contains 2,931 team-status samples over `389.478 s` (median interval `0.1484 s`). It records team state/progress, not a new per-frame actor XYZ trajectory. No post-fix actor path speed is claimed.

## Data provenance and cleanup

- Report: `report.json`, SHA-256 `5d745cb17badc728bda90cfd3f45afddd446e08c905a3681760349f914958ddd`
- Manifest: `manifest.json`, SHA-256 `062ed7853c21fa30e141498ecc950e29e2766ee75090421a9a11cac14ff51bf3`
- Live evidence: `live_evidence.jsonl`, SHA-256 `047ba41027a4dd84641855181170bf2ec27d144e98e9f4ab52f0861472f5d601`
- Supervisor log: `system.log`, SHA-256 `aa217eab2639b66e7cb86082f51f8bd4053bbc019d86822be1d0d7e0990d5057`
- Navigation log: `system/navigation.log`, SHA-256 `4e7cf5849995dcf0066491308b581ba80a532a058457c4ad5289f63a806aa659`
- Team status log: `system/visitor_team.jsonl`, SHA-256 `368185adbbaeac5174eaf6ba4448e339a25a2eafd485f2dca9b91261aa29d06e`
- After the run, only its ROS CLI daemon (Domain 226, started at 12:58:19) remained; it was stopped. The project preflight then reported Domain 226 empty. Ports `11379` and `8102` were released, and no run-created Gazebo or demo process remained. No other ROS/Gazebo process was stopped.

## Reproduction command

```bash
cd /home/linao/heritage_workspace/heritage_temi_robot-phase28
source /opt/ros/humble/setup.bash
source ros2_ws/install/setup.bash
export ROS_LOCALHOST_ONLY=1
timeout 1000s .venv/bin/python -u scripts/run_visitor_full_demo.py \
  --layout official --team-decision-mode business_script --domain-id 226 \
  --gazebo-port 11379 --web-port 8102 --timeout-sec 900 \
  --output-dir docs/phase2_9/experiments/WP04-regroup
```

Before reproducing, re-check ROS domain, Gazebo/web ports, memory, disk, and existing Gazebo processes. The recorded command is evidence of this run, not a recommendation to reuse those IDs without a fresh check.

## Scope limits

This run does not validate YOLOX team decisions, dynamic visual tracking, vision-based recovery, E02 crowd speed control, E04 crossing avoidance, the 0.3/0.5/0.7 m/s calibration windows, adaptive-layout navigation, or physical temi behavior. It used scripted Gazebo visitors and simulated interaction.
