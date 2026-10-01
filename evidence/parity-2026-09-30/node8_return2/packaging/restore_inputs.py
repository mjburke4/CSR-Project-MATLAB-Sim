#!/usr/bin/env python3
"""Restore the exact paths used by this offline analysis; no simulator is run."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def safe_member(base, name):
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError(f'Archive path escapes destination: {name}')
    return path


def write_checked(source, destination, expected):
    if destination.exists():
        if sha(destination) != expected:
            raise ValueError(f'Refusing to replace different existing file: {destination}')
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.restore-tmp')
    try:
        with temporary.open('wb') as handle:
            shutil.copyfileobj(source, handle, 1 << 20)
        if sha(temporary) != expected:
            raise ValueError(f'Restored SHA-256 mismatch: {destination}')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / 'node8_return2/packaging/archive_manifest.json').read_text())
    for item in manifest['files']:
        path = safe_member(root, item['path'])
        if path.stat().st_size != item['bytes'] or sha(path) != item['sha256']:
            raise ValueError(f'Packaged input hash mismatch: {path}')
    recipe = json.loads((root / 'node8_return2/packaging/restore_manifest.json').read_text())
    count = 0
    for operation in recipe['operations']:
        source = safe_member(root, operation['source'])
        if operation['kind'] == 'zip':
            with zipfile.ZipFile(source) as archive:
                for member in operation['members']:
                    destination = safe_member(root, member['destination'])
                    with archive.open(member['member']) as stream:
                        write_checked(stream, destination, member['sha256'])
                    count += 1
        elif operation['kind'] == 'gzip':
            with gzip.open(source, 'rb') as stream:
                write_checked(stream, safe_member(root, operation['destination']), operation['sha256'])
            count += 1
        else:
            raise ValueError(f"Unknown operation: {operation['kind']}")
    print(json.dumps({'status': 'restored_and_sha256_verified', 'restored_files': count,
                      'simulations_run': 0, 'root': str(root)}, indent=2))


if __name__ == '__main__':
    main()
