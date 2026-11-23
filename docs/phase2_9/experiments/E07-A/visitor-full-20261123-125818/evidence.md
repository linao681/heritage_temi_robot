# E07-A business-script closure evidence

**Result: PASS_WITH_RISK (scripted Gazebo business path only).** This run completes the same-target dropout/regroup/operator-resume cycle and the full official-layout tour. The canonical raw evidence is stored under [`WP04-regroup/visitor-full-20261123-125818`](../../WP04-regroup/visitor-full-20261123-125818/); no raw files are duplicated here.

- Run ID `visitor-full-20261123-125818`, branch `phase2_9-work`, HEAD `24c14231de61840a11c5462805df0cd6160af84d`.
- Three scripted Gazebo visitors; `business_script` team decision; simulated operator consent, gather, and resume; timed subtitle/mock speech. No vision team state was used to make the business decision.
- At zone 3, team status entered `LOST` with peak lag `4.7428 m`, then returned to `GATHERED` in `21.42 s`. A simulated operator resume followed; the same `zone_3` goal resumed under a new UUID after stopped session `45d9c7474a47472789b875a637e10cd4`.
- The report contains five fresh-odom confirmed pause-stop records; Tour history has seven pause transitions, so not every pause has its own recorded stop sample. Final exit stop is confirmed by fresh odom at `0.001129 m/s` (age `0.0332 s`).
- Tour completed `wait` → zones 1–5 → `exit`, and knowledge QA finished. Full details, raw-file hashes, logs, and reproduction command are in the canonical run’s [`evidence.md`](../../WP04-regroup/visitor-full-20261123-125818/evidence.md).
- Vision-driven E07-B remains unverified. The prior ~201.7 s collection run and this ~21.42 s LOST interval are not a fixed-seed controlled comparison; no new actor XYZ speed is claimed.
