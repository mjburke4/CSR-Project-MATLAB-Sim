#!/usr/bin/env python3
"""Package the reviewed repair with exact source and return provenance."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
KIT = HERE / 'kit/autocase'
OUT = HERE / 'deliverables'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(path):
    return {p for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts}


def archive(path, paths, base):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(paths):
            z.write(p, p.relative_to(base).as_posix())
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
    return {'filename': path.name, 'bytes': path.stat().st_size,
            'sha256': sha(path), 'members': len(paths)}


def main():
    OUT.mkdir(exist_ok=True)
    manifest = json.loads((KIT / 'FILES.json').read_text())
    for row in manifest['files']:
        assert sha(KIT / row['path']) == row['sha256'], row['path']
    syntax = json.loads((HERE / 'validation/syntax/syntax_summary.json').read_text())
    assert syntax['status'] == 'pass' and syntax['source_unchanged_during_parse']
    assert syntax['file_sha256'] == {
        str(p.relative_to(KIT)): sha(p) for p in sorted(KIT.rglob('*.m'))}
    issued = ROOT / 'autonomous/kit/autocase'
    model = {str(p.relative_to(KIT / 'model')): sha(p) for p in files(KIT / 'model')}
    old_model = {str(p.relative_to(issued / 'model')): sha(p) for p in files(issued / 'model')}
    assert model == old_model and len(model) == 99
    for p in files(KIT / 'ref/native'):
        assert p.read_bytes() == (issued / p.relative_to(KIT)).read_bytes(), p
    report = HERE / 'Autonomous_Return_Review_2026-09-25.md'
    shutil.copy2(report, OUT / report.name)
    owner = archive(OUT / 'autonomous-seed132-repair.zip', files(KIT), KIT.parent)
    with zipfile.ZipFile(OUT / owner['filename']) as z:
        assert 'autocase/run_autonomous_tests.m' in z.namelist()
        assert 'autocase/+ac/Fixture.m' in z.namelist()
        assert 'autocase/ref/accepted/prefix_gate.json' in z.namelist()
    selected = {report, HERE / 'audit_return.py', HERE / 'return_audit.json',
                HERE / 'return_input_manifest.json', Path(__file__).resolve()}
    for sub in ['traffic', 'receiver', 'review', 'repair', 'validation', 'kit']:
        selected |= files(HERE / sub)
    for name in ['report.json', 'provenance.json', 'configuration.json', 'console.log',
                 'A_natural/prefix_gate.json', 'A_natural/case_summary.json',
                 'A_natural/random_summary.json', 'A_natural/observer_status.json',
                 'B_common/case_summary.json', 'B_common/error.json',
                 'B_common/random_summary.json']:
        selected.add(HERE / 'data' / name)
    for name in ['+ac/Streams.m', '+ac/TxSignature.m', 'run_autonomous_tests.m',
                 'FILES.json', 'source_transform.json']:
        selected.add(issued / name)
    readme = HERE / 'EVIDENCE_README.md'
    readme.write_text('''# Autonomous return review evidence

The report is `autonomous_return/Autonomous_Return_Review_2026-09-25.md`.
The owner-run package is `autonomous-seed132-repair.zip`; use its README.

This archive contains the exact repaired kit, static validation, independent
reviews, source comparison, and derived receiver/traffic accounting. The
repaired common-input case has not been executed in MATLAB here.

The original owner return is retained separately as
`out_auto_20260925_124644.zip`, SHA-256
`68050a440c5dbb8c6cbde373e26d806228836aa7d87f6c188adc8ee76dce0b9c`.
Its complete input inventory is included. Selected return receipts and errors
are included here; full ordered logs remain in that original archive.

The earlier `autonomous-seed132-evidence.zip` contains the complete native
capture and original kit used by the offline scripts. To rerun the audits,
extract that archive at the same root, restore the original owner ZIP under
`upload/`, and extract the owner ZIP into `autonomous_return/data/`.
Provenance records may retain the original Windows or analyst workspace paths.
Those are historical evidence, not instructions to load code from those paths.

`autonomous_return/EVIDENCE_CONTENT_SHA256.json` binds every member except itself.
No ns-3 repository, engine build, or compiled simulator is included.
''')
    selected.add(readme)
    inventory = HERE / 'EVIDENCE_CONTENT_SHA256.json'
    inventory.write_text(json.dumps([
        {'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': sha(p)}
        for p in sorted(selected)], indent=2) + '\n')
    selected.add(inventory)
    evidence = archive(OUT / 'autonomous-return-evidence.zip', selected, ROOT)
    receipt = {'owner_kit': owner, 'evidence': evidence,
               'report': str(OUT / report.name), 'unchanged_model_files': len(model),
               'repaired_matlab_execution_performed': False}
    (OUT / 'package_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
