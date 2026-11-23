import hashlib
import json

import pytest

from scripts.serve_replay import load_resources, make_handler, resolve_resource


def make_verified_pair(tmp_path):
    manifest = {
        'run_id': 'RUN-01',
        'status': 'PASS_WITH_RISK',
        'archive_sha256': 'a' * 64,
    }
    manifest_raw = json.dumps(manifest, separators=(',', ':'))
    manifest_hash = hashlib.sha256(manifest_raw.encode()).hexdigest()
    replay = {
        'schema_version': 1,
        'mode': 'RECORDED_ROS2',
        'run_id': 'RUN-01',
        'source': {
            'status': 'PASS_WITH_RISK',
            'archive_sha256': 'a' * 64,
            'manifest_sha256': manifest_hash,
            'manifest_json_raw': manifest_raw,
        },
        'integrity': {
            'source_archive_sha256': 'a' * 64,
            'source_manifest_sha256': manifest_hash,
        },
        'controls_available': False,
        'events': [],
        'rgb_frames': [],
        'depth_frames': [],
    }
    payload = (json.dumps(replay, separators=(',', ':')) + '\n').encode()
    recording = tmp_path / 'replay.json'
    checksum = tmp_path / 'replay.json.sha256'
    recording.write_bytes(payload)
    checksum.write_text(f'{hashlib.sha256(payload).hexdigest()}  replay.json\n')
    return recording, checksum


def make_assets(tmp_path):
    assets = tmp_path / 'assets'
    assets.mkdir(parents=True)
    (assets / 'replay.html').write_text('<html>replay</html>')
    (assets / 'replay.js').write_text('window.replay = true;')
    return assets


def test_only_fixed_assets_and_verified_recording_are_exposed(tmp_path):
    recording, checksum = make_verified_pair(tmp_path)
    resources = load_resources(make_assets(tmp_path), recording, checksum)

    assert resolve_resource('/', resources).body == b'<html>replay</html>'
    assert resolve_resource('/replay.js', resources).body == b'window.replay = true;'
    assert resolve_resource('/recording/replay.json', resources).body == recording.read_bytes()
    assert resolve_resource('/recording/replay.json.sha256', resources).body == checksum.read_bytes()


def test_unknown_and_traversal_paths_are_not_mapped(tmp_path):
    recording, checksum = make_verified_pair(tmp_path)
    resources = load_resources(make_assets(tmp_path), recording, checksum)

    for path in ('/../etc/passwd', '/%2e%2e/etc/passwd', '/recording/../../etc/passwd', '/api/stop'):
        assert resolve_resource(path, resources) is None


def test_modified_recording_fails_checksum_before_being_served(tmp_path):
    recording, checksum = make_verified_pair(tmp_path)
    recording.write_bytes(recording.read_bytes() + b' ')

    with pytest.raises(ValueError, match='SHA256'):
        load_resources(make_assets(tmp_path), recording, checksum)


def test_control_enabled_or_wrong_mode_recording_is_rejected(tmp_path):
    recording, checksum = make_verified_pair(tmp_path)
    value = json.loads(recording.read_text())
    value['controls_available'] = True
    payload = (json.dumps(value, separators=(',', ':')) + '\n').encode()
    recording.write_bytes(payload)
    checksum.write_text(f'{hashlib.sha256(payload).hexdigest()}  replay.json\n')

    with pytest.raises(ValueError, match='read-only'):
        load_resources(make_assets(tmp_path), recording, checksum)


def test_symlink_recording_or_asset_is_rejected(tmp_path):
    recording, checksum = make_verified_pair(tmp_path)
    linked_recording = tmp_path / 'linked.json'
    linked_recording.symlink_to(recording)

    with pytest.raises(ValueError, match='symlink'):
        load_resources(make_assets(tmp_path), linked_recording, checksum)

    assets = make_assets(tmp_path / 'other')
    (assets / 'replay.js').unlink()
    (assets / 'replay.js').symlink_to(recording)
    with pytest.raises(ValueError, match='symlink'):
        load_resources(assets, recording, checksum)


def test_http_handler_has_no_control_or_post_method():
    handler = make_handler({})

    assert callable(handler.do_GET)
    assert callable(handler.do_HEAD)
    assert not hasattr(handler, 'do_POST')


def test_non_object_source_manifest_fails_closed(tmp_path):
    recording, checksum = make_verified_pair(tmp_path)
    value = json.loads(recording.read_text())
    manifest_raw = '[]'
    manifest_hash = hashlib.sha256(manifest_raw.encode()).hexdigest()
    value['source']['manifest_json_raw'] = manifest_raw
    value['source']['manifest_sha256'] = manifest_hash
    value['integrity']['source_manifest_sha256'] = manifest_hash
    payload = (json.dumps(value, separators=(',', ':')) + '\n').encode()
    recording.write_bytes(payload)
    checksum.write_text(f'{hashlib.sha256(payload).hexdigest()}  replay.json\n')

    with pytest.raises(ValueError, match='manifest'):
        load_resources(make_assets(tmp_path), recording, checksum)
