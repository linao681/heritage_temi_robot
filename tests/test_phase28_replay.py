import hashlib
import json
import tarfile
from pathlib import Path

import pytest


def make_recording(tmp_path):
    from scripts.export_phase28_replay import build_replay_recording

    run_id = 'REPLAY-FIXTURE-01'
    recording_dir = tmp_path / 'artifacts' / 'phase2_8' / 'raw' / run_id
    archive_dir = tmp_path / 'artifacts' / 'phase2_8' / 'archive'
    recording_dir.mkdir(parents=True)
    archive_dir.mkdir(parents=True)
    rgb_bytes = b'png-fixture-data'
    capture = {
        'duration_sec': 1.0,
        'camera_info': {'rgb': {'width': 2, 'height': 1, 'fx': 1.0}},
        'frames': {'rgb': [{'path': 'rgb_00.png', 'stamp_ns': 100,
                            'frame_id': 'camera_optical', 'width': 2,
                            'height': 1, 'encoding': 'rgb8',
                            'saved_monotonic_sec': 10.0}], 'depth': []},
        'detections': [{'kind': 'raw', 'stamp_ns': 100, 'source': 'yolox_rgb',
                        'people_count': 1, 'detections': [{'bbox': [0.1, 0.1, 0.4, 0.9]}]}],
        'tracks': [{'stamp_ns': 100, 'source': 'vision_tracker',
                    'tracks': [{'track_id': 'vision-e0-1', 'bbox': [0.1, 0.1, 0.4, 0.9]}],
                    '_received_monotonic_sec': 10.1}],
        'team_observations': [{'stamp_ns': 100, 'source': 'vision_tracker',
                               'observation_state': 'UNKNOWN', 'observed_count': 1,
                               '_received_monotonic_sec': 10.2}],
    }
    capture_bytes = json.dumps(capture).encode()
    (recording_dir / 'capture.json').write_bytes(capture_bytes)
    (recording_dir / 'rgb_00.png').write_bytes(rgb_bytes)
    original_files = []
    for name in ('capture.json', 'rgb_00.png'):
        data = (recording_dir / name).read_bytes()
        original_files.append({'path': name, 'size_bytes': len(data),
                               'sha256': hashlib.sha256(data).hexdigest()})
    archive_path = archive_dir / f'{run_id}.tar.gz'
    with tarfile.open(archive_path, 'w:gz') as archive:
        archive.add(recording_dir / 'capture.json', arcname=f'{run_id}/capture.json')
        archive.add(recording_dir / 'rgb_00.png', arcname=f'{run_id}/rgb_00.png')
    archive_manifest = {
        'run_id': run_id, 'status': 'PASS_WITH_RISK',
        'source_directory': f'artifacts/phase2_8/raw/{run_id}',
        'archive_path': f'artifacts/phase2_8/archive/{run_id}.tar.gz',
        'archive_size_bytes': archive_path.stat().st_size,
        'archive_sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        'original_files': original_files,
    }
    manifest_path = archive_dir / f'{run_id}.manifest.json'
    manifest_path.write_text(json.dumps(archive_manifest))
    return build_replay_recording(manifest_path, recording_dir, archive_path)


def test_replay_export_preserves_provenance_and_real_sample_fields(tmp_path):
    replay = make_recording(tmp_path)

    assert replay['mode'] == 'RECORDED_ROS2'
    assert replay['run_id'] == 'REPLAY-FIXTURE-01'
    assert replay['source']['status'] == 'PASS_WITH_RISK'
    assert replay['clock_mapping'][0] == {
        'ros_stamp_ns': 100, 'recorded_monotonic_sec': 10.0, 'frame': 'rgb'}
    assert [event['type'] for event in replay['events']] == [
        'raw_detection', 'anonymous_tracks', 'team_observation']
    assert replay['rgb_frames'][0]['data_url'].startswith('data:image/png;base64,')
    assert replay['robot_pose_series'] == []
    assert replay['visitor_pose_series'] == []
    assert replay['speed_series'] == []
    assert replay['missing_fields']['robot_pose_series'] == 'not_collected_in_source_run'


def test_replay_export_rejects_modified_source_file(tmp_path):
    with pytest.raises(ValueError, match='source hash mismatch'):
        # Build the fixture metadata first, then corrupt a source file.
        from scripts.export_phase28_replay import build_replay_recording
        run_id = 'REPLAY-FIXTURE-01'
        recording_dir = tmp_path / 'artifacts' / 'phase2_8' / 'raw' / run_id
        archive_dir = tmp_path / 'artifacts' / 'phase2_8' / 'archive'
        archive_dir.mkdir(parents=True)
        recording_dir.mkdir(parents=True)
        (recording_dir / 'capture.json').write_text(json.dumps({'frames': {'rgb': [], 'depth': []}, 'detections': [], 'tracks': [], 'team_observations': []}))
        (recording_dir / 'rgb_00.png').write_bytes(b'original')
        entries = []
        for name in ('capture.json', 'rgb_00.png'):
            data = (recording_dir / name).read_bytes()
            entries.append({'path': name, 'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        archive_path = archive_dir / f'{run_id}.tar.gz'
        with tarfile.open(archive_path, 'w:gz') as archive:
            archive.add(recording_dir / 'capture.json', arcname=f'{run_id}/capture.json')
            archive.add(recording_dir / 'rgb_00.png', arcname=f'{run_id}/rgb_00.png')
        manifest_path = archive_dir / f'{run_id}.manifest.json'
        manifest_path.write_text(json.dumps({'run_id': run_id, 'status': 'PASS',
            'source_directory': f'artifacts/phase2_8/raw/{run_id}',
            'archive_path': f'artifacts/phase2_8/archive/{run_id}.tar.gz',
            'archive_size_bytes': archive_path.stat().st_size,
            'archive_sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            'original_files': entries}))
        (recording_dir / 'rgb_00.png').write_bytes(b'tampered')
        build_replay_recording(manifest_path, recording_dir, archive_path)


def test_replay_export_rejects_archive_hash_mismatch(tmp_path):
    replay = make_recording(tmp_path)
    assert replay['integrity']['source_manifest_sha256'] == replay['source']['manifest_sha256']
    manifest_path = tmp_path / 'artifacts' / 'phase2_8' / 'archive' / 'REPLAY-FIXTURE-01.manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['archive_sha256'] = '0' * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='archive hash mismatch'):
        from scripts.export_phase28_replay import build_replay_recording
        build_replay_recording(manifest_path,
            tmp_path / 'artifacts' / 'phase2_8' / 'raw' / 'REPLAY-FIXTURE-01',
            tmp_path / 'artifacts' / 'phase2_8' / 'archive' / 'REPLAY-FIXTURE-01.tar.gz')


def test_replay_export_rejects_path_traversal_in_manifest(tmp_path):
    replay = make_recording(tmp_path)
    manifest_path = tmp_path / 'artifacts' / 'phase2_8' / 'archive' / 'REPLAY-FIXTURE-01.manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['original_files'][0]['path'] = '../capture.json'
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match='unsafe source member path'):
        from scripts.export_phase28_replay import build_replay_recording
        build_replay_recording(manifest_path,
            tmp_path / 'artifacts' / 'phase2_8' / 'raw' / 'REPLAY-FIXTURE-01',
            tmp_path / 'artifacts' / 'phase2_8' / 'archive' / 'REPLAY-FIXTURE-01.tar.gz')
