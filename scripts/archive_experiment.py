#!/usr/bin/env python3
"""压缩阶段 2.8 已结束的原始实验目录；保留所有原文件。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile


TERMINAL_STATUSES = {'PASS', 'PASS_WITH_RISK', 'FAIL', 'ABORTED', 'BLOCKED'}


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _files_for_archive(run_dir):
    files = []
    for path in sorted(run_dir.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'实验目录不允许符号链接：{path.relative_to(run_dir)}')
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f'实验目录包含非普通文件：{path.relative_to(run_dir)}')
        files.append(path)
    return files


def archive_run(run_dir, project_root):
    project_root = Path(project_root).resolve(strict=True)
    raw_root = (project_root / 'artifacts/phase2_8/raw').resolve(strict=False)
    run_dir = Path(run_dir).resolve(strict=True)
    try:
        relative_run = run_dir.relative_to(raw_root)
    except ValueError as error:
        raise ValueError('只允许归档 artifacts/phase2_8/raw 下的实验目录') from error
    if not relative_run.parts or len(relative_run.parts) != 1 or not run_dir.is_dir():
        raise ValueError('run_dir 必须是 raw 下的单个实验目录')

    run_id = run_dir.name
    if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', run_id) is None:
        raise ValueError('run_id 只能包含字母、数字、点、下划线和连字符')
    status_path = run_dir / 'status.json'
    try:
        status = json.loads(status_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError('缺少可读的 status.json，拒绝归档') from error
    if (not isinstance(status, dict) or status.get('finished') is not True or
            status.get('status') not in TERMINAL_STATUSES):
        raise ValueError('实验尚未结束或 status.json 不是终态')

    files = _files_for_archive(run_dir)
    if not files:
        raise ValueError('实验目录没有可归档文件')
    archive_dir = project_root / 'artifacts/phase2_8/archive'
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f'{run_id}.tar.gz'
    manifest_path = archive_dir / f'{run_id}.manifest.json'
    if archive_path.exists() or manifest_path.exists():
        raise FileExistsError(f'归档已存在，拒绝覆盖：{run_id}')

    original_files = []
    for path in files:
        relative = path.relative_to(run_dir).as_posix()
        original_files.append({'path': relative, 'size_bytes': path.stat().st_size,
                               'sha256': _sha256(path)})

    descriptor, temporary_name = tempfile.mkstemp(prefix=f'.{run_id}.', suffix='.tmp',
                                                   dir=archive_dir)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            with tarfile.open(fileobj=stream, mode='w:gz') as archive:
                for path in files:
                    relative = path.relative_to(run_dir).as_posix()
                    archive.add(path, arcname=f'{run_id}/{relative}', recursive=False)
            stream.flush()
            os.fsync(stream.fileno())
        # Hard-link publication fails atomically if another run made this name.
        os.link(temporary_path, archive_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    manifest = {
        'run_id': run_id,
        'status': status['status'],
        'source_directory': run_dir.relative_to(project_root).as_posix(),
        'archive_path': archive_path.relative_to(project_root).as_posix(),
        'archive_size_bytes': archive_path.stat().st_size,
        'archive_sha256': _sha256(archive_path),
        'original_files': original_files,
        'originals_retained': True,
        'restore': f'tar -xzf {archive_path.relative_to(project_root).as_posix()} -C <restore-root>',
    }
    try:
        with manifest_path.open('x', encoding='utf-8') as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise
    return {**manifest, 'archive_path': archive_path, 'manifest_path': manifest_path}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', help='artifacts/phase2_8/raw 下已经结束的唯一 run 目录')
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    result = archive_run(args.run_dir, project_root)
    print(json.dumps({key: str(value) if isinstance(value, Path) else value
                      for key, value in result.items()}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
