#!/usr/bin/env python3
"""Validate and package the neighbor-check diagnostic kit and its actual evidence."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
KIT = HERE / 'kit/autocase'
OLD = ROOT / 'autonomous_third/kit/autocase'
OUT = HERE / 'deliverables'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def files(p):
    return {q for q in p.rglob('*') if q.is_file() and '__pycache__' not in q.parts}


def verify_rows(base, rows):
    for row in rows:
        assert sha(base / row['path']) == row['sha256'], row['path']


def archive(p, selected, base):
    with zipfile.ZipFile(p, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for source in sorted(selected):
            z.write(source, source.relative_to(base).as_posix())
    with zipfile.ZipFile(p) as z:
        assert z.testzip() is None
    return {'filename': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p),
            'members': len(selected)}


def main():
    OUT.mkdir(exist_ok=True)
    manifest = json.loads((KIT / 'FILES.json').read_text())
    verify_rows(KIT, manifest['files'])
    expected = {r['path'] for r in manifest['files']} | {'FILES.json'}
    assert expected == {p.relative_to(KIT).as_posix() for p in files(KIT)}
    syntax = json.loads((HERE / 'validation/syntax/syntax_summary.json').read_text())
    assert syntax['status'] == 'pass' and syntax['source_unchanged_during_parse']
    assert syntax['file_sha256'] == {
        p.relative_to(KIT).as_posix(): sha(p) for p in sorted(KIT.rglob('*.m'))}
    model = {p.relative_to(KIT / 'model').as_posix(): sha(p) for p in files(KIT / 'model')}
    old_model = {p.relative_to(OLD / 'model').as_posix(): sha(p) for p in files(OLD / 'model')}
    assert model == old_model and len(model) == 99
    for p in files(KIT / 'ref/native'):
        assert p.read_bytes() == (OLD / p.relative_to(KIT)).read_bytes()
    reuse = json.loads((KIT / 'ref/accepted/reuse_proof.json').read_text())
    verify_rows(KIT, reuse['unchanged_natural_source_files'])
    verify_rows(KIT / 'ref/accepted', reuse['accepted_files'])
    transform = json.loads((KIT / 'candidate_transform.json').read_text())
    for entry in transform['transforms']:
        source, target = KIT / entry['source'], KIT / entry['target']
        assert sha(source) == entry['source_sha256'] and sha(target) == entry['target_sha256']
        restored = target.read_text()
        for edit in reversed(entry['edits']):
            assert restored.count(edit['new']) == 1
            restored = restored.replace(edit['new'], edit['old'], 1)
        assert restored.encode() == source.read_bytes()

    report = HERE / 'Autonomous_Neighbor_Control_Review_2026-09-25.md'
    shutil.copy2(report, OUT / report.name)
    owner_path = OUT / 'autonomous-neighbor-check-tests.zip'
    owner = archive(owner_path, files(KIT), KIT.parent)
    with zipfile.ZipFile(owner_path) as z:
        assert 'autocase/run_autonomous_tests.m' in z.namelist()
        assert 'autocase/+ac/checkGatePreflight.m' in z.namelist()
        assert 'autocase/+ac/MessageFlagNeighbors.m' in z.namelist()
        for p in files(KIT):
            assert z.read('autocase/' + p.relative_to(KIT).as_posix()) == p.read_bytes()

    readme = HERE / 'EVIDENCE_README.md'
    readme.write_text("""# Neighbor-control return review evidence

The report is `autonomous_fourth/Autonomous_Neighbor_Control_Review_2026-09-25.md`.
The separately issued owner kit is `autonomous-neighbor-check-tests.zip`;
its exact content is also included under `autonomous_fourth/kit/autocase`.

Included: the complete owner ZIP and extracted return, the previously issued
C/D kit, the new E/F kit, native observations and fixtures, independent audits,
source reviews, static validation and the native component-probe evidence.
E/F and their new MATLAB preflight are pending owner execution. C/D and the
seven KEY_REQUEST checks are actual owner-executed results.

From the extraction root, Python-only audit commands are:

    python3 autonomous_fourth/audit_return.py
    python3 autonomous_fourth/review/audit_cases.py
    python3 autonomous_fourth/matlab/audit_missing_child.py

The native public-API probe source, log and build receipt are included. It
uses actual HOP key exchange/ACK and NWK callbacks with an unattached MAC;
it does not run a network or call Simulator::Run. Recompiling requires the
pinned engine/CSR build identified in autonomous/native_env/build.json.
Selected native source headers are included for inspection. Full repositories,
libraries and compiled probes are excluded. Recorded outputs are inspectable
without a native build. Kit-generation scripts retain prior workspace inputs;
the final kit and exact reversible candidate transformations are included.

Historical absolute paths in provenance identify the originating environment;
they are not instructions to load another MATLAB code copy. Use the owner
ZIP README to run. No ns-3 command is required from the owner.

`autonomous_fourth/EVIDENCE_CONTENT_SHA256.json` binds every member except
itself. The separate package receipt identifies the final archive hashes.
""")
    selected = {report, readme, HERE / 'audit_return.py', HERE / 'return_audit.json',
                HERE / 'return_input_manifest.json', Path(__file__).resolve(),
                ROOT / 'upload/out_auto_20260925_133710.zip'}
    for folder in ['data', 'native', 'matlab', 'review', 'validation', 'build', 'kit']:
        selected |= files(HERE / folder)
    selected = {p for p in selected if not p.name.endswith('_probe')}
    selected |= files(OLD)
    selected |= files(ROOT / 'autonomous/native_capture/fixture')
    for name in ['run/observations.tsv', 'run/ns3-trace.csv', 'run/run.log', 'receipt.json']:
        selected.add(ROOT / 'autonomous/native_capture' / name)
    for name in ['csr/model/csr-phy-model.h', 'csr/model/csr-net-device.h',
                 'csr/model/csr-nwk-layer.h', 'csr/model/csr-hop-layer.h',
                 'engine/src/core/model/nstime.h', 'engine/src/core/model/int64x64-128.h', 'build.json']:
        selected.add(ROOT / 'autonomous/native_env' / name)
    for p in selected:
        assert p.is_file(), p
    inventory = HERE / 'EVIDENCE_CONTENT_SHA256.json'
    inventory.write_text(json.dumps([
        {'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
        for p in sorted(selected)], indent=2) + '\n')
    selected.add(inventory)
    evidence_path = OUT / 'autonomous-neighbor-check-evidence.zip'
    evidence = archive(evidence_path, selected, ROOT)
    with zipfile.ZipFile(owner_path) as owner_z, zipfile.ZipFile(evidence_path) as evidence_z:
        for name in owner_z.namelist():
            assert owner_z.read(name) == evidence_z.read('autonomous_fourth/kit/' + name)
    receipt = {'owner_kit': owner, 'evidence': evidence, 'report': str(OUT / report.name),
               'bound_kit_files': len(manifest['files']), 'matlab_files_parsed': syntax['matlab_file_count'],
               'unchanged_model_files': len(model), 'candidate_transforms_reverse_exact': True,
               'new_matlab_cases_executed': False, 'new_network_simulation_executed': False,
               'owner_kit_identical_to_evidence_copy': True, 'target_percent': 15}
    (OUT / 'package_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
