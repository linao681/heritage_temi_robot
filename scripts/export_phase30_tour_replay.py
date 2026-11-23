#!/usr/bin/env python3
"""Export a hash-verified, read-only replay from a recorded full-tour run."""
import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = (ROOT / 'docs/phase2_9/experiments/WP04-regroup').resolve()
ALLOWED_STATUSES = {'PASS', 'PASS_WITH_RISK', 'FAIL'}
RUN_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
SOURCE_FILES = ('manifest.json', 'report.json', 'live_evidence.jsonl')


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _safe_source_file(source_dir, name):
    relative = PurePosixPath(name)
    if relative.is_absolute() or any(part in ('', '.', '..') for part in relative.parts):
        raise ValueError('unsafe source file path')
    path = source_dir / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'source file is missing or unsafe: {name}')
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(source_dir):
        raise ValueError(f'source file escapes run directory: {name}')
    return resolved.read_bytes()


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _snapshot(row, name):
    evidence = row.get('evidence')
    item = evidence.get(name) if isinstance(evidence, dict) else None
    if (not isinstance(item, dict) or item.get('fresh') is not True or
            not _finite(item.get('age_sec')) or item['age_sec'] < 0 or
            not isinstance(item.get('value'), dict)):
        return None
    sample_time = row['elapsed_sec'] - item['age_sec']
    if not _finite(sample_time) or sample_time < 0:
        return None
    return item['value'], sample_time


def _event(run_id, index, event_type, elapsed_sec, data, source):
    return {
        'event_id': f'{run_id}:{event_type}:{index:06d}',
        'type': event_type,
        'stamp_ns': round(elapsed_sec * 1_000_000_000),
        'relative_time_ns': 0,
        'source': source,
        'data': data,
    }


def _load_live_rows(raw):
    rows = []
    previous = -1.0
    for line_number, line in enumerate(raw.decode('utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f'invalid live evidence JSON on line {line_number}') from error
        elapsed = row.get('elapsed_sec') if isinstance(row, dict) else None
        if not _finite(elapsed) or elapsed < 0 or elapsed < previous:
            raise ValueError(f'live evidence times are not monotonic on line {line_number}')
        previous = elapsed
        rows.append(row)
    if not rows:
        raise ValueError('source run has no live evidence records')
    return rows


def _build_samples(run_id, rows):
    events = []
    robot_pose_series = []
    visitor_pose_series = []
    speed_series = []
    seen_sources = {'tracks': set(), 'team_observation': set(),
                    'cmd_vel': set(), 'odom': set()}
    last_tour = last_safety = last_team = None
    counts = {}

    for row_index, row in enumerate(rows):
        elapsed = row['elapsed_sec']
        if row.get('connected') is True and all(_finite(row.get(key)) for key in ('x', 'z', 'yaw')):
            robot_pose_series.append({
                'stamp_ns': round(elapsed * 1_000_000_000),
                'x': float(row['x']), 'z': float(row['z']), 'yaw': float(row['yaw']),
                'source': 'ROS TF map->base_footprint',
            })

        visitors = row.get('visitors')
        if isinstance(visitors, list):
            for visitor in visitors:
                if (not isinstance(visitor, dict) or not isinstance(visitor.get('id'), str) or
                        not all(_finite(visitor.get(key)) for key in ('x', 'z', 'yaw'))):
                    continue
                visitor_pose_series.append({
                    'stamp_ns': round(elapsed * 1_000_000_000),
                    'id': visitor['id'], 'x': float(visitor['x']),
                    'z': float(visitor['z']), 'yaw': float(visitor['yaw']),
                    'source': 'Gazebo ModelStates', 'ground_truth': True,
                })

        tour = row.get('tour')
        if isinstance(tour, dict):
            signature = tuple(tour.get(key) for key in
                              ('state', 'reason', 'target', 'outcome', 'route_index',
                               'pause_source', 'paused_session_id', 'team_pause_event_id',
                               'team_resume_confirmed')) + (json.dumps(
                                   tour.get('visited', []), sort_keys=True),
                                   json.dumps(tour.get('qa_result'), sort_keys=True))
            if signature != last_tour:
                events.append(_event(run_id, counts.get('tour_state', 0), 'tour_state', elapsed,
                                     {key: tour.get(key) for key in (
                                         'state', 'reason', 'target', 'visited', 'outcome',
                                         'route_index', 'qa_waiting', 'qa_result', 'pause_source',
                                         'paused_session_id', 'team_pause_event_id',
                                         'team_resume_confirmed')}, 'ROS heritage/tour/status snapshot'))
                counts['tour_state'] = counts.get('tour_state', 0) + 1
                last_tour = signature

        speed_control = row.get('speed_control')
        if isinstance(speed_control, dict):
            safety = {key: speed_control.get(key) for key in (
                'state', 'reason', 'stop_requested', 'stop_confirmed',
                'navigation_session_id', 'target_speed_mps', 'dynamic_stop_distance_m')}
            signature = tuple(safety.values())
            if signature != last_safety:
                events.append(_event(run_id, counts.get('safety_state', 0), 'safety_state', elapsed,
                                     safety, 'ROS heritage/speed_control/status snapshot'))
                counts['safety_state'] = counts.get('safety_state', 0) + 1
                last_safety = signature

        team = row.get('team')
        if isinstance(team, dict):
            truth = {key: team.get(key) for key in (
                'source', 'team_decision_mode', 'state', 'count', 'lag_m',
                'gathered', 'safe_hold', 'blocked')}
            signature = tuple(truth.values())
            if signature != last_team:
                events.append(_event(run_id, counts.get('gazebo_team_truth', 0),
                                     'gazebo_team_truth', elapsed, truth,
                                     'Gazebo scripted actor truth; not a vision estimate'))
                counts['gazebo_team_truth'] = counts.get('gazebo_team_truth', 0) + 1
                last_team = signature

        tracks = _snapshot(row, 'tracks')
        if tracks:
            value, sample_time = tracks
            stamp = value.get('stamp_ns')
            key = stamp if isinstance(stamp, int) else None
            if value.get('valid') is True and key is not None and key not in seen_sources['tracks']:
                events.append(_event(run_id, counts.get('anonymous_tracks', 0),
                                     'anonymous_tracks', sample_time, value,
                                     value.get('source', 'ROS visitor/tracks')))
                counts['anonymous_tracks'] = counts.get('anonymous_tracks', 0) + 1
                seen_sources['tracks'].add(key)

        team_observation = _snapshot(row, 'team_observation')
        if team_observation:
            value, sample_time = team_observation
            stamp = value.get('stamp_ns')
            key = stamp if isinstance(stamp, int) else None
            if key is not None and key not in seen_sources['team_observation']:
                events.append(_event(run_id, counts.get('team_observation', 0),
                                     'team_observation', sample_time, value,
                                     value.get('source', 'ROS visitor/team_observation')))
                counts['team_observation'] = counts.get('team_observation', 0) + 1
                seen_sources['team_observation'].add(key)

        for source_name in ('cmd_vel', 'odom'):
            snapshot = _snapshot(row, source_name)
            if not snapshot:
                continue
            value, sample_time = snapshot
            linear = value.get('linear_speed_mps')
            angular = value.get('angular_speed_rps')
            source_stamp = value.get('stamp_ns')
            received_time = value.get('received_monotonic_sec')
            if source_name == 'odom' and isinstance(source_stamp, int):
                sample_id = ('ros_stamp', source_stamp)
            elif _finite(received_time):
                sample_id = ('received_monotonic', round(received_time * 1_000_000_000))
            else:
                # Earlier recordings kept freshness age but not the ROS receive timestamp.
                # elapsed_sec - age_sec is the recorded sample time for that snapshot.
                sample_id = ('recorded_age', round(sample_time * 1_000_000_000))
            if (not _finite(linear) or not _finite(angular) or
                    sample_id in seen_sources[source_name]):
                continue
            seen_sources[source_name].add(sample_id)
            series_item = {
                'stamp_ns': round(sample_time * 1_000_000_000),
                'source_stamp_ns': source_stamp if isinstance(source_stamp, int) else None,
                'sample_time_basis': ('ros_stamp_and_recorded_age' if isinstance(source_stamp, int)
                                      else 'elapsed_sec_minus_snapshot_age'),
                'linear_speed_mps': float(linear), 'angular_speed_rps': float(angular),
                'source': source_name,
            }
            speed_series.append(series_item)
            event_type = 'cmd_vel' if source_name == 'cmd_vel' else 'odom'
            events.append(_event(run_id, counts.get(event_type, 0), event_type, sample_time,
                                 series_item, f'ROS {source_name} sample'))
            counts[event_type] = counts.get(event_type, 0) + 1

    events.sort(key=lambda item: (item['stamp_ns'], item['event_id']))
    first_stamp = min(event['stamp_ns'] for event in events) if events else 0
    last_stamp = max(event['stamp_ns'] for event in events) if events else first_stamp
    for event in events:
        event['relative_time_ns'] = event['stamp_ns'] - first_stamp
    for series in (robot_pose_series, visitor_pose_series, speed_series):
        series.sort(key=lambda item: item['stamp_ns'])
    return events, robot_pose_series, visitor_pose_series, speed_series, first_stamp, last_stamp


def build_tour_replay(run_dir, output_dir):
    run_dir = Path(run_dir)
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ValueError('source directory is missing or unsafe')
    source_dir = run_dir.resolve(strict=True)
    if source_dir.parent != Path(SOURCE_ROOT).resolve(strict=True):
        raise ValueError('source directory must be a direct child of the approved WP04 source root')
    run_id = source_dir.name
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError('source run id is invalid')

    source_bytes = {name: _safe_source_file(source_dir, name) for name in SOURCE_FILES}
    manifest = json.loads(source_bytes['manifest.json'])
    report = json.loads(source_bytes['report.json'])
    if (not isinstance(manifest, dict) or manifest.get('run_id') != run_id or
            not isinstance(report, dict) or report.get('run_id') != run_id or
            report.get('status') not in ALLOWED_STATUSES):
        raise ValueError('source run manifest/report identity or status is invalid')
    if (report.get('layout') != manifest.get('layout') or
            report.get('team_decision_mode') != manifest.get('team_decision_mode')):
        raise ValueError('source run metadata does not match')
    rows = _load_live_rows(source_bytes['live_evidence.jsonl'])
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    project_root = Path(ROOT).resolve(strict=True)
    output_dir = output_dir.resolve(strict=False)
    if not output_dir.is_relative_to(project_root):
        raise ValueError('output directory must remain inside the project')
    if output_dir.exists():
        raise FileExistsError(f'output directory already exists: {output_dir}')
    output_dir.mkdir(parents=True)

    archive_path = output_dir / 'source-evidence.tar.gz'
    with tarfile.open(archive_path, 'w:gz') as archive:
        for name in SOURCE_FILES:
            info = tarfile.TarInfo(name)
            info.size = len(source_bytes[name])
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            import io
            archive.addfile(info, io.BytesIO(source_bytes[name]))
    archive_bytes = archive_path.read_bytes()
    verified = [{'path': name, 'size_bytes': len(source_bytes[name]),
                 'sha256': _sha256(source_bytes[name])} for name in SOURCE_FILES]
    archive_path_relative = archive_path.relative_to(ROOT).as_posix()
    source_manifest = {
        'schema_version': 1, 'run_id': run_id, 'status': report['status'],
        'archive_path': archive_path_relative, 'archive_sha256': _sha256(archive_bytes),
        'source_layout': report['layout'],
        'source_team_decision_mode': report['team_decision_mode'],
        'original_manifest_sha256': _sha256(source_bytes['manifest.json']),
        'source_files': verified,
    }
    manifest_raw = (json.dumps(source_manifest, ensure_ascii=False, sort_keys=True,
                               separators=(',', ':')) + '\n').encode('utf-8')
    source_manifest_path = output_dir / 'source-manifest.json'
    source_manifest_path.write_bytes(manifest_raw)

    events, robot_pose, visitor_pose, speeds, first_stamp, last_stamp = _build_samples(run_id, rows)
    payload = {
        'schema_version': 1, 'mode': 'RECORDED_ROS2', 'run_id': run_id,
        'source': {
            'status': report['status'], 'archive_sha256': _sha256(archive_bytes),
            'archive_path': archive_path_relative,
            'manifest_sha256': _sha256(manifest_raw),
            'manifest_json_raw': manifest_raw.decode('utf-8'),
            'verified_source_files': verified,
        },
        'time_base': 'source live_evidence elapsed_sec and fresh ROS snapshot age; no interpolation',
        'wall_clock_mapping': None, 'clock_mapping': [],
        'duration_ns': max(0, last_stamp - first_stamp),
        'events': events, 'rgb_frames': [], 'depth_frames': [],
        'robot_pose_series': robot_pose, 'visitor_pose_series': visitor_pose,
        'speed_series': speeds,
        'missing_fields': {
            'wall_clock_mapping': 'not_collected_in_source_run',
            'rgb_frames': 'not_collected_in_source_run',
            'depth_frames': 'not_collected_in_source_run',
            'camera_video_overlay': 'no recorded RGB frame is available for timestamp alignment',
        },
        'controls_available': False,
    }
    payload['integrity'] = {
        'source_manifest_sha256': payload['source']['manifest_sha256'],
        'source_archive_sha256': _sha256(archive_bytes),
    }
    recording_path = output_dir / 'replay.json'
    recording_bytes = (json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    recording_path.write_bytes(recording_bytes)
    checksum_path = output_dir / 'replay.json.sha256'
    checksum_path.write_text(f'{_sha256(recording_bytes)}  replay.json\n', encoding='utf-8')
    return {'recording': recording_path, 'checksum': checksum_path,
            'archive': archive_path, 'source_manifest': source_manifest_path,
            'run_id': run_id, 'events': len(events), 'robot_pose_samples': len(robot_pose),
            'visitor_pose_samples': len(visitor_pose), 'speed_samples': len(speeds)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_tour_replay(args.run_dir, args.output_dir)
    except (OSError, ValueError, json.JSONDecodeError, tarfile.TarError) as error:
        parser.error(str(error))
    print(json.dumps({key: str(value) if isinstance(value, Path) else value
                      for key, value in result.items()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
