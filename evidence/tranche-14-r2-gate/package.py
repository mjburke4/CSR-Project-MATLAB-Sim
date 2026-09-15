from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL, OLD, NEW, WORK = ROOT / 'csr14', ROOT / 'csr14r', ROOT / 'csr14s', ROOT / 't14s'
sys.path.insert(0, str(NEW / 'scripts'))
import analyze_tranche14_return as gate

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')

candidate = json.loads((NEW / gate.CANDIDATE).read_text())
prior = json.loads((OLD / 'evidence/tranche-14-readiness.json').read_text())
assert candidate['Revision'] == 'r2'
plan = gate.verify_plan(NEW, candidate)
native, native_proof = gate.verify_native(NEW, candidate, plan)
gate.verify_manifest(NEW, candidate['RepairManifest'], candidate['RepairManifestSHA256'],
                     'csr-tranche14-r2-files-v1')
source = gate.candidate_snapshot(NEW)
names = gate.selected_test_names(NEW, candidate['TestFiles'])
assert names == candidate['ExpectedTestNames'] and len(names) == 109
assert candidate['TestFiles'][0] == 'tests/TestEdgeRecords.m'
assert len(source) == 285 and sum(p.endswith('.m') for p in source) == 144
assert prior['SourceBindings'].keys() <= source.keys()
changed = sorted(p for p in source if source[p] != prior['SourceBindings'].get(p))
review = json.loads((WORK / 'review.json').read_text())
matlab_changes = sorted(row['Path'] for row in review['FileBindings'])
assert changed == sorted(matlab_changes + [gate.CANDIDATE])
assert review['Disposition'] == 'ready_for_owner_matlab_execution'
assert not review['MATLABExecuted'] and not review['OpenCodeFindings']
assert all(source[row['Path']] == row['SHA256'] for row in review['FileBindings'])
refs = {}
for name in candidate['ReferenceRoots']:
    for p in (NEW / name).rglob('*'):
        if p.is_file():
            relative = p.relative_to(NEW).as_posix()
            assert relative not in refs
            refs[relative] = sha(p)
for name in candidate['ReferenceFiles']:
    assert name not in refs
    refs[name] = sha(NEW / name)
assert len(refs) == 317 and len(prior['ReferenceBindings']) == 299
assert all(refs[name] == digest for name, digest in prior['ReferenceBindings'].items())
baseline = json.loads((NEW / candidate['BaselineSourceSnapshot']).read_text())
assert len(baseline) == 271 and sum(row['path'].endswith('.m') for row in baseline) == 138
assert all(source[row['path']] == row['sha256'] for row in baseline)
assert 'Ran 37 tests' in (WORK / 'tests.log').read_text() and (WORK / 'tests.log').read_text().rstrip().endswith('OK')
assert '6 file(s) analysed, everything seems fine' in (WORK / 'lint.log').read_text()
proof = {
    'Schema': 'csr-tranche14-r2-preflight-v1', 'Status': 'passed',
    'CreatedUTC': datetime.now(timezone.utc).isoformat(), 'MATLABExecuted': False,
    'CandidateSHA256': sha(NEW / gate.CANDIDATE), 'SourceFiles': len(source),
    'MatlabSourceFiles': sum(p.endswith('.m') for p in source), 'ReferenceFiles': len(refs),
    'MatlabTestCount': len(names), 'Previous106TestNamesRetained': True,
    'IndependentMatlabPreflightTestsAdded': 3,
    'PythonEvidenceTestsPassed': 37, 'MatlabStaticFilesPassed': 6,
    'BaselineSourceFilesUnchanged': 271, 'BaselineMatlabFilesUnchanged': 138,
    'ChangedSourceBindings': {p: source[p] for p in changed},
    'PreviousReferenceFilesUnchanged': 299, 'NativeReferenceProof': native_proof,
    'NativeRerunForRepair': False, 'FailedOwnerReturnAccepted': False,
    'ReviewSHA256': sha(WORK / 'review.json'), 'TestLogSHA256': sha(WORK / 'tests.log'),
    'LintLogSHA256': sha(WORK / 'lint.log'),
}
out = NEW / 'evidence/tranche-14-r2-gate'
out.mkdir(exist_ok=True)
write(out / 'preflight.json', proof)
for name in ('tests.log', 'lint.log', 'freeze.py', 'package.py'):
    shutil.copyfile(WORK / name, out / name)
ready = dict(prior)
ready.update({
    'Revision': 'r2', 'CreatedUTC': datetime.now(timezone.utc).isoformat(),
    'Status': 'ready_for_owner_matlab_execution', 'CandidateSHA256': sha(NEW / gate.CANDIDATE),
    'MATLABExecuted': False, 'AcceptanceEstablished': False, 'NumericalParityEstablished': False,
    'NativeRerunForRepair': False, 'NativeBoundReferencesReused': True,
    'PythonEvidenceTestsPassed': 37, 'MatlabStaticFilesParsed': 6,
    'MatlabTestMethodsReady': 109, 'NewMatlabTestMethods': 21,
    'IndependentPreflightMatlabTestMethods': 3,
    'CandidateSourceFiles': len(source), 'CandidateMatlabFiles': sum(p.endswith('.m') for p in source),
    'ReferenceFiles': len(refs), 'SourceBindings': source, 'ReferenceBindings': dict(sorted(refs.items())),
    'PreparationEvidence': [{'path': p.relative_to(NEW).as_posix(), 'sha256': sha(p)} for p in sorted(out.iterdir())],
    'OriginalCandidateSHA256': candidate['OriginalCandidateSHA256'],
    'PreviousCandidateSHA256': candidate['PreviousCandidateSHA256'],
    'FailedOwnerEvidenceSHA256': candidate['FailedOwnerEvidenceSHA256'],
    'RepairManifestSHA256': candidate['RepairManifestSHA256'],
    'ChangedMatlabFiles': matlab_changes,
    'Delivery': {'RepairArchive': 't14fix2.zip', 'Command': 'report = run_tranche14_validation;',
                 'ReturnArchive': 't14.zip', 'Cumulative': True},
    'NextDecision': 'Run three independent preflight tests, six diagnostic cases and remaining 106 MATLAB tests; review the completed owner evidence before any ACK timing/parity conclusion.',
})
write(NEW / 'evidence/tranche-14-readiness.json', ready)
excluded = {'.git', '__pycache__', '.pytest_cache', 'results'}
files = {p.relative_to(NEW).as_posix(): p for p in NEW.rglob('*') if p.is_file()
         and not any(part in excluded for part in p.relative_to(NEW).parts)
         and p.suffix not in {'.pyc', '.pyo'} and p.name != 'PACKAGE.json'}
assert len(files) == len({p.casefold() for p in files})
write(NEW / 'PACKAGE.json', {
    'Schema': 'csr-portable-package-v1', 'Tranche': 14, 'Revision': 'r2',
    'CandidateSHA256': sha(NEW / gate.CANDIDATE),
    'Scope': 'Cumulative T14 observer and typed-record repair; owner MATLAB rerun pending.',
    'UpdateBaseRecipe': candidate['RepairUpdateBaseRecipe'],
    'FileCountExcludingManifest': len(files),
    'MaximumRelativePathLength': max(map(len, files)),
    'Files': [{'path': n, 'bytes': p.stat().st_size, 'sha256': sha(p)} for n, p in sorted(files.items())],
})
files['PACKAGE.json'] = NEW / 'PACKAGE.json'
base_names = {}
for base in (ORIGINAL, OLD):
    inventory = json.loads((base / 'PACKAGE.json').read_text())
    base_names[base] = {row['path'] for row in inventory['Files']} | {'PACKAGE.json'}
    assert base_names[base] <= files.keys()
    for row in inventory['Files']:
        assert sha(base / row['path']) == row['sha256']
delta = {n: p for n, p in files.items()
         if n not in base_names[ORIGINAL] or sha(p) != sha(ORIGINAL / n)}
assert sorted(n for n in delta if n.endswith('.m')) == matlab_changes
target = ROOT / 't14fix2.zip'
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for n, p in sorted(delta.items()):
        archive.write(p, n)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None and set(archive.namelist()) == set(delta)
    for base in (ORIGINAL, OLD):
        assert set(archive.namelist()) | base_names[base] == files.keys()
        for n, p in files.items():
            data = archive.read(n) if n in delta else (base / n).read_bytes()
            assert hashlib.sha256(data).hexdigest() == sha(p), (base.name, n)
assert gate.candidate_snapshot(NEW) == source
result = {'archive': target.name, 'sha256': sha(target), 'bytes': target.stat().st_size,
          'members': len(delta), 'maximum_relative_path_length': max(map(len, delta)),
          'crc_verified': True, 'cumulative_overlay_verified_against': ['original_t14', 't14_r1'],
          'overlay_reconstructs_complete_repaired_tree': True, 'deletions_required': False,
          'candidate_sha256': sha(NEW / gate.CANDIDATE), 'source_count': len(source),
          'reference_count': len(refs), 'matlab_tests_prepared': 109,
          'matlab_executed_for_repair': False}
write(WORK / 'package.json', result)
print(json.dumps(result, indent=2))
