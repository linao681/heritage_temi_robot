import hashlib
import json
import tarfile
from pathlib import Path

import pytest


def make_source_run(tmp_path, monkeypatch, rows=None):
    from scripts import export_phase30_tour_replay as exporter

    run_id = 'visitor-full-test-001'
    source_root = tmp_path / 'docs/phase2_9/experiments/WP04-regroup'
    source = source_root / run_id
    source.mkdir(parents=True)
    monkeypatch.setattr(exporter, 'ROOT', tmp_path.resolve())
    monkeypatch.setattr(exporter, 'SOURCE_ROOT', source_root.resolve())
    manifest = {'schema_version': 1, 'run_id': run_id,
                'layout': 'official', 'team_decision_mode': 'business_script'}
    report = {'status': 'PASS', 'run_id': run_id, 'layout': 'official',
              'team_decision_mode': 'business_script', 'elapsed_sec': 2.0}
    evidence = rows if rows is not None else [
        {'elapsed_sec': 1.0, 'connected': False, 'x': None, 'z': None, 'yaw': None,
         'tour': {'state': 'IDLE', 'reason': 'waiting', 'visited': []},
         'evidence': {}},
        {'elapsed_sec': 1.5, 'connected': True, 'x': 1.0, 'z': 2.0, 'yaw': 0.2,
         'tour': {'state': 'NAVIGATING', 'reason': 'to zone_1', 'visited': ['wait']},
         'team': {'source': 'gazebo_scripted_actors', 'state': 'GATHERED',
                  'count': 1, 'lag_m': 0.0},
         'visitors': [{'id': 'phase25_person_01', 'x': 3.0, 'z': 4.0, 'yaw': 1.0}],
         'speed_control': {'state': 'SLOW', 'reason': 'near visitor',
                           'navigation_session_id': 'nav-1'},
         'evidence': {
             'tracks': {'fresh': True, 'age_sec': 0.0,
                        'value': {'valid': True, 'stamp_ns': 5000000000,
                                  'source': 'vision_tracker',
                                  'tracks': [{'track_id': 'vision-e0-1',
                                              'bbox': [0.1, 0.2, 0.3, 0.6]}]}},
             'cmd_vel': {'fresh': True, 'age_sec': 0.1,
                         'value': {'linear_speed_mps': 0.25,
                                   'angular_speed_rps': 0.0,
                                   'received_monotonic_sec': 100.0}},
             'odom': {'fresh': True, 'age_sec': 0.1,
                      'value': {'linear_speed_mps': 0.2,
                                'angular_speed_rps': 0.0,
                                'received_monotonic_sec': 100.0,
                                'stamp_ns': 5000000000}},
         }},
        {'elapsed_sec': 2.0, 'connected': True, 'x': 1.5, 'z': 2.5, 'yaw': 0.3,
         'tour': {'state': 'COMPLETED', 'reason': 'done',
                  'visited': ['wait', 'zone_1', 'zone_2', 'zone_3', 'zone_4',
                              'zone_5', 'exit']},
         'team': {'source': 'gazebo_scripted_actors', 'state': 'GATHERED',
                  'count': 1, 'lag_m': 0.0},
         'visitors': [],
         'speed_control': {'state': 'IDLE', 'reason': 'no navigation',
                           'navigation_session_id': ''},
         'evidence': {
             'cmd_vel': {'fresh': True, 'age_sec': 0.0,
                         'value': {'linear_speed_mps': 0.0,
                                   'angular_speed_rps': 0.0,
                                   'received_monotonic_sec': 100.5}},
             'odom': {'fresh': True, 'age_sec': 0.0,
                      'value': {'linear_speed_mps': 0.0,
                                'angular_speed_rps': 0.0,
                                'received_monotonic_sec': 100.5,
                                'stamp_ns': 6000000000}},
         }},
    ]
    (source / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    (source / 'report.json').write_text(json.dumps(report), encoding='utf-8')
    (source / 'live_evidence.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in evidence), encoding='utf-8')
    return run_id, source, tmp_path / 'export'


def test_tour_export_uses_real_pose_speed_and_separates_gazebo_truth(tmp_path, monkeypatch):
    from scripts.export_phase30_tour_replay import build_tour_replay

    run_id, source, output = make_source_run(tmp_path, monkeypatch)
    paths = build_tour_replay(source, output)
    replay = json.loads(paths['recording'].read_text(encoding='utf-8'))

    assert replay['mode'] == 'RECORDED_ROS2'
    assert replay['run_id'] == run_id
    assert replay['controls_available'] is False
    assert len(replay['robot_pose_series']) == 2
    assert replay['robot_pose_series'][0]['source'] == 'ROS TF map->base_footprint'
    assert len(replay['visitor_pose_series']) == 1
    assert replay['visitor_pose_series'][0]['source'] == 'Gazebo ModelStates'
    assert replay['visitor_pose_series'][0]['ground_truth'] is True
    assert {item['source'] for item in replay['speed_series']} == {'cmd_vel', 'odom'}
    assert all('interpolated' not in item for item in replay['robot_pose_series'])
    assert replay['rgb_frames'] == [] and replay['depth_frames'] == []
    assert replay['missing_fields']['rgb_frames'] == 'not_collected_in_source_run'
    assert replay['source']['archive_sha256'] == hashlib.sha256(
        paths['archive'].read_bytes()).hexdigest()
    assert replay['source']['manifest_sha256'] == hashlib.sha256(
        paths['source_manifest'].read_bytes()).hexdigest()
    assert paths['checksum'].read_text().startswith(
        hashlib.sha256(paths['recording'].read_bytes()).hexdigest())


def test_tour_export_events_are_monotonic_and_include_state_and_detection(tmp_path, monkeypatch):
    from scripts.export_phase30_tour_replay import build_tour_replay

    _, source, output = make_source_run(tmp_path, monkeypatch)
    replay = json.loads(build_tour_replay(source, output)['recording'].read_text())
    stamps = [event['stamp_ns'] for event in replay['events']]

    assert stamps == sorted(stamps)
    assert any(event['type'] == 'tour_state' for event in replay['events'])
    assert any(event['type'] == 'anonymous_tracks' for event in replay['events'])
    assert replay['duration_ns'] == 1_000_000_000


def test_tour_export_rejects_unordered_sample_times(tmp_path, monkeypatch):
    from scripts.export_phase30_tour_replay import build_tour_replay

    rows = [
        {'elapsed_sec': 2.0, 'connected': False, 'tour': {'state': 'IDLE'}, 'evidence': {}},
        {'elapsed_sec': 1.0, 'connected': False, 'tour': {'state': 'IDLE'}, 'evidence': {}},
    ]
    _, source, output = make_source_run(tmp_path, monkeypatch, rows)

    with pytest.raises(ValueError, match='monotonic'):
        build_tour_replay(source, output)


def test_tour_export_rejects_run_directory_escape(tmp_path, monkeypatch):
    from scripts import export_phase30_tour_replay as exporter

    _, source, output = make_source_run(tmp_path, monkeypatch)
    outside = tmp_path / 'outside'
    outside.mkdir()
    with pytest.raises(ValueError, match='source directory'):
        exporter.build_tour_replay(outside, output)


def test_exported_archive_contains_only_verified_source_files(tmp_path, monkeypatch):
    from scripts.export_phase30_tour_replay import build_tour_replay

    _, source, output = make_source_run(tmp_path, monkeypatch)
    paths = build_tour_replay(source, output)

    with tarfile.open(paths['archive'], 'r:gz') as archive:
        assert sorted(archive.getnames()) == [
            'live_evidence.jsonl', 'manifest.json', 'report.json']
    assert paths['source_manifest'].is_file()


def test_tour_export_resolves_project_relative_output_path(tmp_path, monkeypatch):
    from scripts import export_phase30_tour_replay as exporter

    _, source, _ = make_source_run(tmp_path, monkeypatch)
    paths = exporter.build_tour_replay(source, Path('relative-export'))

    assert paths['recording'].is_relative_to(tmp_path.resolve())


def test_tour_export_rejects_output_outside_project(tmp_path, monkeypatch):
    from scripts import export_phase30_tour_replay as exporter

    _, source, _ = make_source_run(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match='inside the project'):
        exporter.build_tour_replay(source, tmp_path.parent / 'outside-export')


def test_tour_export_maps_legacy_speed_snapshot_age_without_repeating_samples(
        tmp_path, monkeypatch):
    from scripts.export_phase30_tour_replay import build_tour_replay

    def speed_snapshot(age, linear):
        return {'fresh': True, 'age_sec': age,
                'value': {'linear_speed_mps': linear, 'angular_speed_rps': 0.0}}

    rows = [
        {'elapsed_sec': 1.5, 'connected': False, 'tour': {'state': 'NAVIGATING'},
         'evidence': {'cmd_vel': speed_snapshot(0.5, 0.2),
                      'odom': speed_snapshot(0.5, 0.18)}},
        {'elapsed_sec': 1.7, 'connected': False, 'tour': {'state': 'NAVIGATING'},
         'evidence': {'cmd_vel': speed_snapshot(0.5, 0.21),
                      'odom': speed_snapshot(0.5, 0.19)}},
    ]
    _, source, output = make_source_run(tmp_path, monkeypatch, rows)
    replay = json.loads(build_tour_replay(source, output)['recording'].read_text())

    assert len(replay['speed_series']) == 4
    assert {item['sample_time_basis'] for item in replay['speed_series']} == {
        'elapsed_sec_minus_snapshot_age'}
    assert all(item['source_stamp_ns'] is None for item in replay['speed_series'])
    assert sorted(item['stamp_ns'] for item in replay['speed_series']) == [
        1_000_000_000, 1_000_000_000, 1_200_000_000, 1_200_000_000]
