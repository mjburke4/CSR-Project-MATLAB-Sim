from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OLD, NEW, WORK = ROOT / 'csr14r', ROOT / 'csr14s', ROOT / 't14s'
sys.path.insert(0, str(NEW / 'scripts'))
from analyze_tranche11_return import candidate_snapshot, selected_test_names

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')

old_cp = OLD / 'evidence/tranche-14-candidate.json'
old = json.loads(old_cp.read_text())
assert sha(old_cp) == '94bde01e85eac80af05b0e9aa81132b4b7b0fee7907fc3420d28ae8b49eb9609'
owner = ROOT / 'upload/t14(1).zip'
assert sha(owner) == 'b91453bd508bccd5cb10ca12b10e75ff006dd3bbf7f7bfc1386017487d09db2f'
review = json.loads((WORK / 'review.json').read_text())
integrity = json.loads((WORK / 'integrity.json').read_text())
assert review['Disposition'] == 'ready_for_owner_matlab_execution'
assert not review['MATLABExecuted'] and not review['OpenCodeFindings']
assert integrity['status'] == 'failed_run_integrity_verified_not_accepted'
assert integrity['tests']['retained_passed'] == 88
original, repaired = candidate_snapshot(OLD), candidate_snapshot(NEW)
assert set(repaired) - set(original) == {'+csr/+validation/edgeRecordTable.m', 'tests/TestEdgeRecords.m'}
assert not set(original) - set(repaired)
changed = sorted(name for name in repaired if original.get(name) != repaired[name])
assert changed == sorted(row['Path'] for row in review['FileBindings'])
for row in review['FileBindings']:
    assert sha(NEW / row['Path']) == row['SHA256']
baseline = json.loads((NEW / old['BaselineSourceSnapshot']).read_text())
assert len(baseline) == 271 and sum(row['path'].endswith('.m') for row in baseline) == 138
assert all(sha(NEW / row['path']) == row['sha256'] for row in baseline)
prior_ready = json.loads((OLD / 'evidence/tranche-14-readiness.json').read_text())
assert len(prior_ready['ReferenceBindings']) == 299
assert all(sha(NEW / name) == digest for name, digest in prior_ready['ReferenceBindings'].items())
test_files = ['tests/TestEdgeRecords.m'] + old['TestFiles']
names = selected_test_names(NEW, test_files)
assert len(names) == 109 and names[3:] == old['ExpectedTestNames']
folder = NEW / 'evidence/tranche-14-r2'
folder.mkdir()
copies = {
    owner: 'owner.zip', old_cp: 'previous-candidate.json',
    OLD / 'evidence/tranche-14-readiness.json': 'previous-readiness.json',
    OLD / '+csr/+validation/ackEdgeContract.m': 'previous-fixture.txt',
    OLD / '+csr/+validation/TraceScheduler.m': 'previous-scheduler.txt',
    OLD / 'tests/TestAckEdgeContract.m': 'previous-tests.txt',
    OLD / 'run_tranche14_validation.m': 'previous-runner.txt',
    OLD / 'FIX_T14.md': 'previous-fix.md',
    WORK / 'integrity.py': 'integrity.py', WORK / 'integrity.json': 'integrity.json',
    WORK / 'fix.json': 'fix.json', WORK / 'fix.md': 'fix.md',
    WORK / 'review.json': 'review.json', WORK / 'review.md': 'review.md',
}
for source, target in copies.items():
    shutil.copyfile(source, folder / target)
with zipfile.ZipFile(owner) as archive:
    assert archive.testzip() is None
    for name in ('source.json', 'references.json'):
        (folder / ('previous-' + name)).write_bytes(archive.read(name))
record = {
    'Schema': 'csr-tranche-14-r2-provenance-v1', 'Revision': 'r2',
    'Status': 'typed_diagnostic_tables_repaired_matlab_rerun_pending',
    'CreatedUTC': datetime.now(timezone.utc).isoformat(),
    'PreviousCandidateSHA256': sha(old_cp),
    'OriginalCandidateSHA256': old['OriginalCandidateSHA256'],
    'FailedOwnerEvidenceSHA256': sha(owner),
    'PreviousPackageInventorySHA256': sha(OLD / 'PACKAGE.json'),
    'UpdateBaseRecipe': 'Cumulative repair applied to the complete original T14 installation or issued r1. Original T14 is reproducible from verified csr13.zip plus t14up.zip.',
    'UpdateBaseArchiveSHA256': old['RepairUpdateBaseArchiveSHA256'],
    'UpdateBaseOverlaySHA256': old['RepairUpdateBaseOverlaySHA256'],
    'StandaloneOriginalFullArchiveUsed': False,
    'ChangedMatlabFiles': review['FileBindings'],
    'SourceFilesUnchangedFromValidatedT13': 271,
    'MatlabFilesUnchangedFromValidatedT13': 138,
    'PreviousReferenceFilesUnchanged': 299,
    'PreviousTestNamesRetained': True, 'IndependentPreflightTestsAdded': 3,
    'TestCount': 109, 'StructuralChecks': 222, 'NativeRerunForRepair': False,
    'NativeReferenceManifestSHA256': old['EdgeReferenceManifestSHA256'],
    'MATLABExecutedForRepair': False, 'AcceptanceEstablished': False,
    'NumericalParityEstablished': False,
    'Scope': 'Explicit text and exact integer types in all six new T14 diagnostic outputs, independent preflight regressions, per-case partial evidence and honest incomplete-result reporting. Includes r1 DATA-only identity fix. No validated production protocol, timing, PHY/ECC, native or shared-input changes.',
}
write(folder / 'record.json', record)
write(folder / 'manifest.json', {'schema': 'csr-tranche14-r2-files-v1',
    'files': {p.name: sha(p) for p in sorted(folder.iterdir())}})
candidate = dict(old)
candidate.update({
    'Revision': 'r2', 'Status': 'diagnostic_table_types_repaired_matlab_execution_pending',
    'CreatedUTC': datetime.now(timezone.utc).isoformat(),
    'TestFiles': test_files, 'ExpectedTestNames': names,
    'PreviousCandidate': 'evidence/tranche-14-r2/previous-candidate.json',
    'PreviousCandidateSHA256': sha(old_cp),
    'FailedOwnerEvidence': 'evidence/tranche-14-r2/owner.zip',
    'FailedOwnerEvidenceSHA256': sha(owner),
    'RepairManifest': 'evidence/tranche-14-r2/manifest.json',
    'RepairManifestSHA256': sha(folder / 'manifest.json'),
    'RepairUpdateBaseRecipe': record['UpdateBaseRecipe'],
    'ReferenceRoots': old['ReferenceRoots'] + ['evidence/tranche-14-r2'],
    'RepairScope': record['Scope'],
})
write(NEW / 'evidence/tranche-14-candidate.json', candidate)
print(json.dumps({'candidate_sha256': sha(NEW / 'evidence/tranche-14-candidate.json'),
    'repair_manifest_sha256': candidate['RepairManifestSHA256'],
    'matlab_tests_prepared': len(names), 'changed_matlab_files': changed,
    'repair_artifacts': len(list(folder.iterdir()))}, indent=2))
