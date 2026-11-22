#!/usr/bin/env python3
"""Export a hash-verified Phase 2.8 ROS capture for offline, read-only replay."""
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

ALLOWED_STATUSES = {'PASS', 'PASS_WITH_RISK', 'FAIL'}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def safe_member_path(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(part in ('', '.', '..') for part in path.parts):
        raise ValueError('unsafe source member path')
    return path.as_posix()


def relative_sources(capture, run_id):
    events = []
    source_lists = (
        ('detections', 'detection', 0),
        ('tracks', 'anonymous_tracks', 2),
        ('team_observations', 'team_observation', 3),
    )
    for key, event_type, order in source_lists:
        for index, source_event in enumerate(capture.get(key, [])):
            stamp_ns = source_event.get('stamp_ns')
            if not isinstance(stamp_ns, int) or stamp_ns < 0:
                continue
            event_data = {k: v for k, v in source_event.items()
                          if not k.startswith('_received_')}
            if key == 'detections':
                event_type_for_item = f"{source_event.get('kind', 'unknown')}_detection"
                item_order = 0 if source_event.get('kind') == 'raw' else 1
            else:
                event_type_for_item = event_type
                item_order = order
            received = source_event.get('_received_monotonic_sec')
            received_ns = int(received * 1_000_000_000) if isinstance(received, (int, float)) else None
            events.append({
                '_sort': (stamp_ns, item_order, index),
                'event_id': f'{run_id}:{key}:{index:04d}',
                'type': event_type_for_item,
                'stamp_ns': stamp_ns,
                'received_monotonic_ns': received_ns,
                'source': source_event.get('source'),
                'data': event_data,
            })
    events.sort(key=lambda event: event['_sort'])
    first_stamp = events[0]['stamp_ns'] if events else 0
    for event in events:
        event['relative_time_ns'] = event['stamp_ns'] - first_stamp
        del event['_sort']
    return events


def build_replay_recording(manifest_path, recording_dir, archive_path):
    manifest_path = Path(manifest_path)
    recording_dir = Path(recording_dir).resolve()
    archive_path = Path(archive_path)
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    run_id = manifest.get('run_id')
    if not isinstance(run_id, str) or not run_id or recording_dir.name != run_id:
        raise ValueError('run id does not match source directory')
    if manifest.get('status') not in ALLOWED_STATUSES:
        raise ValueError('source run status is not replayable')
    expected_raw_path = f'artifacts/phase2_8/raw/{run_id}'
    expected_archive_path = f'artifacts/phase2_8/archive/{run_id}.tar.gz'
    if tuple(recording_dir.parts[-4:]) != ('artifacts', 'phase2_8', 'raw', run_id):
        raise ValueError('recording directory is outside Phase 2.8 raw evidence')
    if tuple(archive_path.resolve().parts[-4:]) != ('artifacts', 'phase2_8', 'archive', f'{run_id}.tar.gz'):
        raise ValueError('archive is outside Phase 2.8 archive directory')
    if manifest.get('source_directory') != expected_raw_path:
        raise ValueError('manifest source path mismatch')
    if manifest.get('archive_path') != expected_archive_path or archive_path.name != f'{run_id}.tar.gz':
        raise ValueError('manifest archive path mismatch')
    archive_bytes = archive_path.read_bytes()
    archive_hash = sha256_bytes(archive_bytes)
    if archive_hash != manifest.get('archive_sha256'):
        raise ValueError('archive hash mismatch')
    if len(archive_bytes) != manifest.get('archive_size_bytes'):
        raise ValueError('archive size mismatch')

    entries = {}
    for entry in manifest.get('original_files', []):
        name = safe_member_path(entry.get('path', ''))
        if name in entries:
            raise ValueError('duplicate source member')
        entries[name] = entry
    if not entries or 'capture.json' not in entries:
        raise ValueError('manifest has no capture.json')
    try:
        with tarfile.open(archive_path, 'r:gz') as archive:
            members = {}
            for member in archive.getmembers():
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError('archive contains a non-regular file')
                prefix = f'{run_id}/'
                if not member.name.startswith(prefix):
                    raise ValueError('archive member path mismatch')
                name = safe_member_path(member.name[len(prefix):])
                if name in members:
                    raise ValueError('duplicate archive member')
                members[name] = member
            if set(members) != set(entries):
                raise ValueError('archive members do not match manifest')
            verified = {}
            for name, entry in entries.items():
                source = (recording_dir / name).resolve()
                if not source.is_relative_to(recording_dir):
                    raise ValueError('source member escapes recording directory')
                source_bytes = source.read_bytes()
                archived_bytes = archive.extractfile(members[name]).read()
                expected_hash = entry.get('sha256')
                if (len(source_bytes) != entry.get('size_bytes') or
                        sha256_bytes(source_bytes) != expected_hash):
                    raise ValueError(f'source hash mismatch: {name}')
                if (len(archived_bytes) != entry.get('size_bytes') or
                        sha256_bytes(archived_bytes) != expected_hash):
                    raise ValueError(f'archive member hash mismatch: {name}')
                verified[name] = source_bytes
    except (tarfile.TarError, OSError, KeyError) as exc:
        raise ValueError(f'invalid source archive: {exc}') from exc

    capture = json.loads(verified['capture.json'])
    required_lists = ('detections', 'tracks', 'team_observations')
    if any(not isinstance(capture.get(key), list) for key in required_lists):
        raise ValueError('capture is missing required observation lists')
    events = relative_sources(capture, run_id)
    first_stamp = events[0]['stamp_ns'] if events else 0
    last_stamp = events[-1]['stamp_ns'] if events else first_stamp
    rgb_frames = []
    depth_frames = []
    for kind, destination in (('rgb', rgb_frames), ('depth', depth_frames)):
        for frame in capture.get('frames', {}).get(kind, []):
            name = safe_member_path(frame.get('path', ''))
            if name not in verified:
                raise ValueError(f'frame is not hash-verified: {name}')
            item = {key: frame.get(key) for key in
                    ('stamp_ns', 'frame_id', 'width', 'height', 'encoding', 'saved_monotonic_sec')}
            item.update(path=name, sha256=entries[name]['sha256'])
            if kind == 'rgb':
                suffix = Path(name).suffix.lower()
                mime = 'image/png' if suffix == '.png' else 'image/jpeg' if suffix in ('.jpg', '.jpeg') else None
                if mime is None:
                    raise ValueError(f'unsupported RGB frame format: {suffix}')
                item['data_url'] = f'data:{mime};base64,' + base64.b64encode(verified[name]).decode('ascii')
            destination.append(item)

    mappings = []
    for kind, frames in (('rgb', capture.get('frames', {}).get('rgb', [])),
                         ('depth', capture.get('frames', {}).get('depth', []))):
        for frame in frames:
            if isinstance(frame.get('stamp_ns'), int) and isinstance(frame.get('saved_monotonic_sec'), (int, float)):
                mappings.append({'ros_stamp_ns': frame['stamp_ns'],
                                 'recorded_monotonic_sec': frame['saved_monotonic_sec'],
                                 'frame': kind})

    payload = {
        'schema_version': 1,
        'mode': 'RECORDED_ROS2',
        'run_id': run_id,
        'source': {
            'status': manifest['status'],
            'archive_sha256': archive_hash,
            'archive_path': manifest['archive_path'],
            'manifest_sha256': sha256_bytes(manifest_raw),
            'manifest_json_raw': manifest_raw.decode('utf-8'),
            'verified_source_files': [{'path': name, 'size_bytes': entries[name]['size_bytes'],
                                       'sha256': entries[name]['sha256']} for name in sorted(entries)],
        },
        'time_base': 'ROS simulation stamp_ns; received monotonic timestamps only where recorded',
        'wall_clock_mapping': None,
        'clock_mapping': mappings,
        'capture_duration_wall_sec': capture.get('duration_sec'),
        'duration_ns': max(0, last_stamp - first_stamp),
        'camera_info': capture.get('camera_info', {}),
        'events': events,
        'rgb_frames': rgb_frames,
        'depth_frames': depth_frames,
        'robot_pose_series': [],
        'visitor_pose_series': [],
        'speed_series': [],
        'missing_fields': {
            'wall_clock_mapping': 'not_collected_in_source_run',
            'robot_pose_series': 'not_collected_in_source_run',
            'visitor_pose_series': 'not_collected_in_source_run',
            'speed_series': 'not_collected_in_source_run',
        },
        'controls_available': False,
    }
    payload['integrity'] = {'source_manifest_sha256': payload['source']['manifest_sha256'],
                            'source_archive_sha256': archive_hash}
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--recording-dir', required=True, type=Path)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        replay = build_replay_recording(args.manifest, args.recording_dir, args.archive)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output_bytes = (json.dumps(replay, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        args.output.write_bytes(output_bytes)
        digest = sha256_bytes(output_bytes)
        args.output.with_suffix(args.output.suffix + '.sha256').write_text(
            f'{digest}  {args.output.name}\n', encoding='utf-8')
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({'run_id': replay['run_id'], 'mode': replay['mode'],
                      'events': len(replay['events']), 'rgb_frames': len(replay['rgb_frames']),
                      'output': str(args.output),
                      'sha256': sha256_bytes(args.output.read_bytes()), 'status': 'PASS'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
