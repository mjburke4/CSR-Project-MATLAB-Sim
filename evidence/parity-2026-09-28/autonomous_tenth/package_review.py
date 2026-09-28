#!/usr/bin/env python3
"""Validate and package the discovery-membership correction kit and its actual evidence."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
KIT = HERE / 'kit/autocase'
OLD = ROOT / 'autonomous_ninth/kit/autocase'
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
    review = json.loads((HERE / 'review/discovery_membership_preflight_review.json').read_text())
    assert review['blockers'] == [] and review['checks'] == 5 and review['frozen']
    for name, digest in review['files'].items():
        assert sha(KIT / name) == digest, name
    peer = json.loads((HERE / 'receiver/membership_preflight_peer_review.json').read_text())
    assert peer['status'] == 'pass_static_review' and peer['blocking_findings'] == []
    assert (KIT / 'ref/membership/preflight_review.json').read_bytes() == (
        HERE / 'review/discovery_membership_preflight_review.json').read_bytes()
    assert (KIT / 'ref/membership/membership_preflight_peer_review.json').read_bytes() == (
        HERE / 'receiver/membership_preflight_peer_review.json').read_bytes()
    for name, digest in peer['files_sha256'].items():
        assert sha(ROOT / name) == digest, name
    native_review = json.loads((HERE / 'native/candidate_scope_review.json').read_text())
    assert native_review['scope_review'] == 'pass'
    assert (KIT / 'ref/membership/candidate_scope_review.json').read_bytes() == (
        HERE / 'native/candidate_scope_review.json').read_bytes()
    assert sha(KIT / 'run_autonomous_tests.m') == native_review['runner_sha256']
    for item in native_review['verified_transforms']:
        assert sha(KIT / item['target']) == item['sha256'], item['target']
    native_receipt = json.loads((HERE / 'native/evidence_receipt.json').read_text())
    for name, digest in native_receipt['artifact_sha256'].items():
        assert sha(HERE / 'native' / name) == digest, name
    model = {p.relative_to(KIT / 'model').as_posix(): sha(p) for p in files(KIT / 'model')}
    old_model = {p.relative_to(OLD / 'model').as_posix(): sha(p) for p in files(OLD / 'model')}
    assert model == old_model and len(model) == 99
    prior_classes = sorted((OLD / '+ac').glob('*.m'))
    for p in prior_classes:
        assert p.read_bytes() == (KIT / '+ac' / p.name).read_bytes(), p.name
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

    report = HERE / 'Autonomous_Discovery_Membership_Review_2026-09-28.md'
    shutil.copy2(report, OUT / report.name)
    owner_path = OUT / 'autonomous-discovery-membership-tests.zip'
    owner = archive(owner_path, files(KIT), KIT.parent)
    with zipfile.ZipFile(owner_path) as z:
        assert 'autocase/run_autonomous_tests.m' in z.namelist()
        for name in ['DiscoveryMembershipNwk', 'DiscoveryMembershipSimulation',
                     'DiscoveryMembershipProbe', 'discoveryMembershipPreflight']:
            assert 'autocase/+ac/' + name + '.m' in z.namelist()
        for p in files(KIT):
            assert z.read('autocase/' + p.relative_to(KIT).as_posix()) == p.read_bytes()

    readme = HERE / 'EVIDENCE_README.md'
    readme.write_text("""# Discovery membership return evidence

The report is `autonomous_tenth/Autonomous_Discovery_Membership_Review_2026-09-28.md`.
The owner kit is `autonomous-discovery-membership-tests.zip`; its exact content
is also included under `autonomous_tenth/kit/autocase`.

Included: complete owner return and extracted files, the issued L kit,
the new M discovery-membership correction kit, native observations/fixtures, independent audits and reviews,
source transformation proofs, component evidence and static validation.
L and its 61 component checks are actual owner MATLAB executions;
new M and its membership component checks remain pending owner execution.

From the extraction root, Python-only audits include:

    python3 autonomous_tenth/audit_return.py
    python3 autonomous_tenth/review/audit_prefix.py
    python3 autonomous_tenth/receiver/audit_discovery_watchdogs.py

Native source and existing capture audits describe their exact scope.
Rebuilding the native simulator requires the pinned engine/CSR build recorded in
`autonomous/native_env/build.json`; selected relevant source headers are
included, while full repositories, libraries and compiled probes are excluded.
No new native simulation was run for this review. Existing results and
original capture excerpts are inspectable without rebuilding that environment.
Kit-generation scripts may refer to earlier workspace inputs; the final kit
and exact reversible transformations are included.

Historical absolute paths in provenance identify originating environments,
not instructions to load another MATLAB copy. Use the owner ZIP README.
No owner-side ns-3 command is required.

`autonomous_tenth/EVIDENCE_CONTENT_SHA256.json` binds each member except
itself. The separate package receipt records final archive hashes.
""")
    selected = {report, readme, HERE / 'audit_return.py', HERE / 'return_audit.json',
                HERE / 'return_input_manifest.json', Path(__file__).resolve(),
                ROOT / 'upload/out_auto_20260928_090828.zip'}
    for folder in ['data', 'native', 'matlab', 'receiver', 'review', 'validation', 'build', 'kit']:
        selected |= files(HERE / folder)
    selected = {p for p in selected if not p.name.endswith('_probe')}
    selected |= files(OLD)
    selected |= files(ROOT / 'autonomous/native_capture/fixture')
    selected.add(ROOT / 'autonomous/native_capture/normalize.py')
    selected.add(ROOT / 'autonomous/tooling/check_matlab_syntax.py')
    for name in ['run/observations.tsv', 'run/ns3-trace.csv', 'run/run.log', 'receipt.json']:
        selected.add(ROOT / 'autonomous/native_capture' / name)
    for name in ['csr/model/csr-common.h', 'csr/model/csr-phy-model.h', 'csr/model/csr-net-device.h',
                 'csr/model/csr-nwk-layer.h', 'csr/model/csr-hop-layer.h', 'csr/model/csr-mac-core.h',
                 'csr/model/csr-opnet-envelope.h', 'csr/model/csr-hop-security.h', 'csr/model/csr-hop-security.cc',
                 'engine/src/core/model/nstime.h', 'engine/src/core/model/int64x64-128.h',
                 'engine/src/core/model/int64x64-128.cc', 'build.json']:
        selected.add(ROOT / 'autonomous/native_env' / name)
    for p in selected:
        assert p.is_file(), p
    inventory = HERE / 'EVIDENCE_CONTENT_SHA256.json'
    inventory.write_text(json.dumps([
        {'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
        for p in sorted(selected)], indent=2) + '\n')
    selected.add(inventory)
    evidence_path = OUT / 'autonomous-discovery-membership-evidence.zip'
    evidence = archive(evidence_path, selected, ROOT)
    with zipfile.ZipFile(owner_path) as owner_z, zipfile.ZipFile(evidence_path) as evidence_z:
        for name in owner_z.namelist():
            assert owner_z.read(name) == evidence_z.read('autonomous_tenth/kit/' + name)
    receipt = {'owner_kit': owner, 'evidence': evidence, 'report': str(OUT / report.name),
               'bound_kit_files': len(manifest['files']), 'matlab_files_parsed': syntax['matlab_file_count'],
               'unchanged_model_files': len(model), 'candidate_transforms_reverse_exact': True,
               'unchanged_prior_ac_matlab_files': len(prior_classes),
               'new_matlab_cases_executed': False, 'new_network_simulation_executed': False,
               'native_arithmetic_probe_executed': False,
               'owner_kit_identical_to_evidence_copy': True, 'target_percent': 15}
    (OUT / 'package_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
