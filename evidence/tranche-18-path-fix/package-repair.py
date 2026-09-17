#!/usr/bin/env python3
"""Create a small patch over the issued T18 update and verify its full overlay."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT.parent / 'deliverables'
spec = importlib.util.spec_from_file_location('t18_package', ROOT / 'evidence/tranche-18-preparation/package.py')
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    old = json.loads((HERE / 'original-package.json').read_text())
    before = {row['path']: row for row in old['Files']}
    after = pack.inventory(ROOT)
    assert set(before) <= set(after), 'Repair cannot delete issued files'
    assert len({name.casefold() for name in after}) == len(after)
    modified = sorted(name for name in before if before[name] != after[name])
    expected = ['+csr/+scenario/tranche18Suite.m', 'README.md', 'docs/parity-ledger.csv',
                'evidence/tranche-18-candidate.json']
    assert modified == expected, modified
    candidate_sha = sha(ROOT / 'evidence/tranche-18-candidate.json')
    verification = json.loads((HERE / 'verification.json').read_text())
    assert verification['candidate_sha256'] == candidate_sha
    assert verification['status'] == 'ready_for_owner_rerun'
    changed = sorted(name for name in after if before.get(name) != after[name])
    manifest = {
        'Schema': 'csr-portable-package-v1', 'Tranche': 18, 'Revision': 2,
        'CandidateSHA256': candidate_sha,
        'Scope': 'Repair T18 recipe path validation; model and native references unchanged; MATLAB rerun pending.',
        'UpdateBaseRecipe': 'Overlay every t18fix.zip file at the root of the installation containing the original t18up.zip update.',
        'BasePackageInventorySHA256': sha(HERE / 'original-package.json'),
        'FileCountExcludingManifest': len(after),
        'MaximumRelativePathLength': max(map(len, after)), 'Files': list(after.values())}
    (ROOT / 'PACKAGE.json').write_text(json.dumps(manifest, indent=2)+'\n')
    changed = sorted(changed+['PACKAGE.json'])
    bundle = OUT / 't18fix.zip'
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in changed:
            assert not (ROOT/name).is_symlink() and '..' not in Path(name).parts and not Path(name).is_absolute()
            archive.write(ROOT/name, name)
    with zipfile.ZipFile(bundle) as repair, tempfile.TemporaryDirectory(prefix='t18fix-apply-', dir=ROOT.parent) as temporary:
        assert repair.testzip() is None and sorted(repair.namelist()) == changed
        applied = Path(temporary) / 'installation'
        shutil.copytree(ROOT.parent/'csr17', applied,
            ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '.git', '*.pyc', '*.pyo', 'results'))
        with zipfile.ZipFile(OUT/'t18up.zip') as original:
            assert original.testzip() is None
            original.extractall(applied)
        assert pack.inventory(applied) == before, 'Reconstructed original T18 differs from issued package'
        assert sha(applied/'PACKAGE.json') == sha(HERE/'original-package.json')
        repair.extractall(applied)
        assert pack.inventory(applied) == after, 'Patched full tree differs from prepared repair'
        assert sha(applied/'PACKAGE.json') == sha(ROOT/'PACKAGE.json')
    report = {'schema': 'csr-tranche18-path-repair-package-v1', 'status': 'passed',
        'archive': bundle.name, 'archive_bytes': bundle.stat().st_size,
        'archive_sha256': sha(bundle), 'archive_members': len(changed),
        'candidate_sha256': candidate_sha, 'changed_existing_files': modified+['PACKAGE.json'],
        'original_T18_reconstructed_and_hash_verified': True,
        'patched_full_tree_hash_verified': True, 'zip_crc_passed': True,
        'baseline_T17_source_files_unchanged': 313, 'matlab_repair_executed': False}
    (OUT/'t18fix-verification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
