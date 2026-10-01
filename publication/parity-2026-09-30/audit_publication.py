#!/usr/bin/env python3
"""Read-only independent audit of the September 30 relay custody publication."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path('/workspace/scratch/db3d3caa011d')
REPO = ROOT / 'publication/repo'
SOURCE = ROOT / 'relay_return/kit/node8case'
DEST = REPO / 'diagnostics/relay-custody/node8case'
ISSUED = ROOT / 'relay-custody-repair-tests.zip'
BASE = '8c976d0eebc914f160ea9fa54972ec68a18fd0fc'
ALLOWED_BASE_EDITS = {'README.md', 'docs/parity-ledger.csv', '.gitattributes'}

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def file_map(folder):
    return {p.relative_to(folder).as_posix(): p for p in folder.rglob('*') if p.is_file()}

def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])

def run():
    errors = []
    baseline = git('ls-tree', '-r', '-z', BASE).split(b'\0')
    base_count = 0
    base_paths = set()
    edited = []
    removed = []
    for item in baseline:
        if not item:
            continue
        meta, path = item.split(b'\t', 1)
        path = path.decode()
        base_paths.add(path)
        base_count += 1
        if not (REPO / path).is_file():
            removed.append(path)
            continue
    edited = [p.decode() for p in git('diff', '--name-only', '-z', BASE, '--').split(b'\0')
              if p and p.decode() in base_paths]
    if removed or set(edited) - ALLOWED_BASE_EDITS:
        errors.append('Unexpected baseline deletion or edit')
    source = file_map(SOURCE)
    destination = file_map(DEST)
    if set(source) != set(destination):
        errors.append('Snapshot file population differs from issued revision 2 staging')
    mismatch = [p for p in sorted(set(source) & set(destination))
                if source[p].read_bytes() != destination[p].read_bytes()]
    if mismatch:
        errors.append('Snapshot byte differences')
    manifest = json.loads((DEST / 'FILES.json').read_text())
    sealed = {f['path']: f for f in manifest['files']}
    if set(sealed) != set(destination) - {'FILES.json'}:
        errors.append('FILES.json population mismatch')
    seal_mismatches = []
    for path, row in sealed.items():
        data = (DEST / path).read_bytes()
        if digest(data) != row['sha256'] or len(data) != row['bytes']:
            seal_mismatches.append(path)
    if seal_mismatches:
        errors.append('FILES.json byte/hash mismatch')
    archive_deltas = []
    with zipfile.ZipFile(ISSUED) as archive:
        crc = archive.testzip()
        members = {p for p in archive.namelist() if not p.endswith('/')}
        if members != {'node8case/' + p for p in destination}:
            errors.append('Issued archive population mismatch')
        for p in destination:
            if archive.read('node8case/' + p) != destination[p].read_bytes():
                archive_deltas.append(p)
    if crc is not None or archive_deltas:
        errors.append('Issued archive CRC or byte difference')
    dependency = DEST / 'TestQueuedRetryPolicy.m'
    dependency_ok = (dependency.is_file() and
                     digest(dependency.read_bytes()) == '603eef79184d92c5b217039b234c98815c1b68409321da8c18441a4e7c74ccee')
    if not dependency_ok:
        errors.append('Required TestQueuedRetryPolicy dependency absent or changed')
    full_destination = REPO / 'diagnostics/terminal-campus6000/csr6000'
    full_files = file_map(full_destination)
    full_archive = ROOT / 'recovered/csr-6000-terminal-parity-tests.zip'
    full_manifest = json.loads((full_destination / 'FILES.json').read_text())
    full_sealed = {f['path']: f for f in full_manifest['files']}
    full_mismatches = []
    if set(full_sealed) != set(full_files) - {'FILES.json'}:
        errors.append('Historical full-run FILES.json population mismatch')
    with zipfile.ZipFile(full_archive) as archive:
        if archive.testzip() is not None:
            errors.append('Historical full-run archive CRC failure')
        if set(archive.namelist()) != {'csr6000/' + p for p in full_files}:
            errors.append('Historical full-run archive population mismatch')
        for p in full_files:
            data = full_files[p].read_bytes()
            if archive.read('csr6000/' + p) != data:
                full_mismatches.append(p)
            if p in full_sealed:
                row = full_sealed[p]
                if digest(data) != row['sha256'] or len(data) != row['bytes']:
                    full_mismatches.append(p + ':manifest')
    if full_mismatches:
        errors.append('Historical full-run snapshot byte/hash mismatch')
    origins = json.loads((REPO / 'publication/parity-2026-09-30/source_origins.json').read_text())['files']
    origin_mismatches = []
    for row in origins:
        destination_data = (REPO / row['path']).read_bytes()
        source_path = row['source_path']
        if '::' in source_path:
            archive_name, member = source_path.split('::', 1)
            with zipfile.ZipFile(ROOT / archive_name) as archive:
                source_data = archive.read(member)
        else:
            source_data = (ROOT / source_path).read_bytes()
        if (source_data != destination_data or digest(destination_data) != row['sha256']
                or len(destination_data) != row['bytes']):
            origin_mismatches.append(row['path'])
    if origin_mismatches:
        errors.append('Published source-origin population has byte differences')
    result = {
        'schema': 'csr-publication-independent-audit-v1',
        'passed': not errors,
        'scope': 'Byte-preserving publication and evidence/provenance audit; not MATLAB execution',
        'baseline': BASE,
        'original_tracked_paths': base_count,
        'removed_original_paths': removed,
        'edited_original_paths': edited,
        'snapshot_files': len(destination),
        'source_snapshot_byte_differences': mismatch,
        'issued_archive_sha256': digest(ISSUED.read_bytes()),
        'issued_archive_byte_differences': archive_deltas,
        'sealed_files': len(sealed),
        'manifest_byte_differences': seal_mismatches,
        'manifest_sha256': digest((DEST / 'FILES.json').read_bytes()),
        'required_root_dependency_verified': dependency_ok,
        'historical_full_run_files': len(full_files),
        'historical_full_run_sealed_files': len(full_sealed),
        'historical_full_run_archive_sha256': digest(full_archive.read_bytes()),
        'historical_full_run_snapshot_mismatches': full_mismatches,
        'historical_full_run_target_retained': full_manifest['target_percent'],
        'source_origins_verified': len(origins),
        'source_origin_mismatches': origin_mismatches,
        'errors': errors,
    }
    output = ROOT / 'publication/review/audit.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(run())
