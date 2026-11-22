import hashlib
import json
from pathlib import Path
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from archive_experiment import archive_run


def make_run(project_root, *, finished=True):
    run = project_root / 'artifacts/phase2_8/raw/RUN-001'
    (run / 'nested').mkdir(parents=True)
    (run / 'status.json').write_text(json.dumps({'finished': finished, 'status': 'PASS'}))
    (run / 'nested/odom.jsonl').write_bytes(b'{"x":1}\n\x00')
    return run


def test_archive_preserves_original_bytes_and_manifest_hashes(tmp_path):
    project = tmp_path / 'project'
    run = make_run(project)
    original = {path.relative_to(run).as_posix(): path.read_bytes()
                for path in run.rglob('*') if path.is_file()}

    result = archive_run(run, project)

    assert result['archive_path'].is_file()
    assert result['manifest_path'].is_file()
    manifest = json.loads(result['manifest_path'].read_text())
    assert manifest['run_id'] == 'RUN-001'
    assert manifest['original_files'] == [
        {'path': name, 'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        for name, data in sorted(original.items())]
    assert manifest['archive_sha256'] == hashlib.sha256(result['archive_path'].read_bytes()).hexdigest()
    assert {path.relative_to(run).as_posix(): path.read_bytes()
            for path in run.rglob('*') if path.is_file()} == original

    extracted = tmp_path / 'restore'
    extracted.mkdir()
    with tarfile.open(result['archive_path'], 'r:gz') as archive:
        for member in archive.getmembers():
            destination = extracted / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.extractfile(member).read())
    restored = extracted / 'RUN-001'
    assert {path.relative_to(restored).as_posix(): path.read_bytes()
            for path in restored.rglob('*') if path.is_file()} == original


def test_archive_refuses_in_progress_run(tmp_path):
    project = tmp_path / 'project'
    run = make_run(project, finished=False)

    with pytest.raises(ValueError, match='尚未结束'):
        archive_run(run, project)

    assert not (project / 'artifacts/phase2_8/archive/RUN-001.tar.gz').exists()


def test_repeated_archive_refuses_to_overwrite_existing_artifact(tmp_path):
    project = tmp_path / 'project'
    run = make_run(project)
    first = archive_run(run, project)
    archive_before = first['archive_path'].read_bytes()

    with pytest.raises(FileExistsError):
        archive_run(run, project)

    assert first['archive_path'].read_bytes() == archive_before


def test_archive_rejects_run_outside_raw_root_and_symlink_escape(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'status.json').write_text('{"finished": true}')
    with pytest.raises(ValueError, match='raw'):
        archive_run(outside, project)

    run = make_run(project)
    secret = tmp_path / 'secret.txt'
    secret.write_text('do not archive')
    (run / 'escape.txt').symlink_to(secret)
    with pytest.raises(ValueError, match='符号链接'):
        archive_run(run, project)
