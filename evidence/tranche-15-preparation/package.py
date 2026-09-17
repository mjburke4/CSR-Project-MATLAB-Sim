from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OLD, NEW, WORK = ROOT / 'csr14s', ROOT / 'csr15', ROOT / 't15w'
sys.path.insert(0, str(NEW / 'scripts'))
import analyze_tranche15_return as gate
from analyze_tranche11_return import candidate_snapshot, selected_test_names

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')

candidate = json.loads((NEW / gate.CANDIDATE).read_text())
plan, old_loss = gate.verify_plan(NEW, candidate)
loss_plan, tape, offers = gate.loss.verify_plan(NEW, old_loss)
native, native_proof = gate.loss.verify_native(NEW, old_loss, loss_plan, tape, offers)
baseline_proof = gate.verify_baseline({'BaselineSourceFilesVerified': 285,
    'BaselineMatlabFilesVerified': 144, 'CoreBaselineSourceFilesVerified': 225,
    'CoreBaselineMatlabFilesVerified': 124}, NEW, candidate)
source = candidate_snapshot(NEW)
old_source = candidate_snapshot(OLD)
assert all(source[name] == digest for name, digest in old_source.items())
assert len(source) == 294 and sum(name.endswith('.m') for name in source) == 149
names = selected_test_names(NEW, candidate['TestFiles'])
assert names == candidate['ExpectedTestNames'] and len(names) == 117
prior = json.loads((OLD / 'evidence/tranche-14-readiness.json').read_text())
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
assert len(refs) == 339 and all(refs[n] == h for n,h in prior['ReferenceBindings'].items())
review = json.loads((WORK / 'review/review.json').read_text())
assert review['Disposition'] == 'ready_for_owner_matlab_execution'
assert not review['MATLABExecuted'] and not review['OpenFindings']
for row in review['FileBindings']:
    assert sha(NEW / row['Path']) == row['SHA256'], row['Path']
tests_text = (WORK / 'tests.log').read_text()
match = re.search(r'Ran (\d+) tests', tests_text)
assert match and tests_text.rstrip().endswith('OK')
python_count = int(match[1])
assert 'Ran 37 tests' in (WORK / 'retained-tests.log').read_text()
assert (WORK / 'retained-tests.log').read_text().rstrip().endswith('OK')
assert '5 file(s) analysed, everything seems fine' in (WORK / 'lint.log').read_text()
# Update ledger only after preparation is actually verified. It is not a runtime pass.
ledger = NEW / 'docs/parity-ledger.csv'
with ledger.open(newline='') as handle:
    rows = list(csv.reader(handle))
rows = [row for row in rows if not row or row[0] != 'T15_paired_transport_preparation']
rows.append(['T15_paired_transport_preparation', 'No_OPNET_execution', 'Pinned_T13_native_reference_reverified_currentmain_486d9e0',
    'Experiment ready; MATLAB execution pending', '117tests_prepared_8paired64secondcases528checks_exactbaseline_and_fullprecision_gate',
    'All285T14sources144MATLAB_unchanged_no_productionclock_PHYchange_evaluate_actual_delivery_retry_release_gains', 15])
with ledger.open('w', newline='') as handle:
    csv.writer(handle).writerows(rows)
out = NEW / 'evidence/tranche-15-preparation'
out.mkdir(exist_ok=True)
for source_path, name in [
    (WORK / 'review/review.json', 'review.json'), (WORK / 'review/review.md', 'review.md'),
    (WORK / 'matlab.json', 'matlab.json'), (WORK / 'matlab.md', 'matlab.md'),
    (WORK / 'tests.log', 'tests.log'), (WORK / 'retained-tests.log', 'retained-tests.log'),
    (WORK / 'lint.log', 'lint.log'), (WORK / 'freeze.py', 'freeze.py'),
    (WORK / 'package.py', 'package.py'),
    (WORK / 'gate/preflight.json', 'gate.json'),
    (ROOT / 't15pub/readiness.json', 'publication.json'),
    (ROOT / 't15pub/PR.md', 'publication-pr.md'),
]:
    shutil.copyfile(source_path, out / name)
proof = {
    'Schema': 'csr-tranche15-preparation-v1', 'Status': 'passed',
    'MATLABExecuted': False, 'NativeRerunForTranche15': False,
    'CandidateSHA256': sha(NEW / gate.CANDIDATE),
    'SourceFiles': len(source), 'MatlabFiles': 149, 'ReferenceFiles': len(refs),
    'ValidatedT14Baseline': baseline_proof, 'NativeReferenceProof': native_proof,
    'PreparedMatlabTests': 117, 'PreparedStructuralChecks': 528,
    'PythonGateTestsPassed': python_count, 'RetainedT14PythonGateTestsPassed': 37,
    'MatlabStaticFilesParsed': 5,
    'ChangedExistingSourceBindings': [],
    'NewSourceBindings': {n:h for n,h in source.items() if n not in old_source},
    'AcceptanceEstablished': False, 'NumericalParityEstablished': False,
}
write(out / 'preflight.json', proof)
ready = {
    'Schema': 'csr-tranche-15-readiness-v1', 'Tranche': 15,
    'Status': 'ready_for_owner_matlab_execution',
    'CreatedUTC': datetime.now(timezone.utc).isoformat(),
    'CandidateSHA256': sha(NEW / gate.CANDIDATE),
    'SourceCommit': candidate['SourceCommit'], 'EngineCommit': candidate['EngineCommit'],
    'MATLABExecuted': False, 'NativeRerunForTranche15': False, 'NativeBoundReferencesReused': True,
    'AcceptanceEstablished': False, 'NumericalParityEstablished': False,
    'CandidateSourceFiles': len(source), 'CandidateMatlabFiles': 149,
    'BaselineSourceFilesUnchanged': 285, 'BaselineMatlabFilesUnchanged': 144,
    'ReferenceFiles': len(refs), 'MatlabTestMethodsPrepared': 117,
    'IndependentPreflightMethods': 8, 'StructuralChecksPrepared': 528,
    'DiagnosticModes': 2, 'DiagnosticCases': 8, 'CaseDurationSeconds': 64,
    'PythonGateTestsPassed': python_count, 'RetainedPythonGateTestsPassed': 37,
    'MatlabStaticFilesParsed': 5, 'SourceBindings': source, 'ReferenceBindings': dict(sorted(refs.items())),
    'PreparationEvidence': [{'path': p.relative_to(NEW).as_posix(), 'sha256': sha(p)} for p in sorted(out.iterdir())],
    'Delivery': {'Archive': 't15up.zip', 'Command': 'report = run_tranche15_validation;', 'ReturnArchive': 't15.zip'},
    'Scope': plan['scope'],
    'NextDecision': 'Review owner-returned paired outcomes and exact continuous baseline reproduction before considering any production timing adoption.',
}
write(NEW / 'evidence/tranche-15-readiness.json', ready)
excluded = {'.git','__pycache__','.pytest_cache','results'}
files = {p.relative_to(NEW).as_posix(): p for p in NEW.rglob('*') if p.is_file()
         and not any(part in excluded for part in p.relative_to(NEW).parts)
         and p.suffix not in {'.pyc','.pyo'} and p.name != 'PACKAGE.json'}
assert len(files) == len({n.casefold() for n in files})
write(NEW / 'PACKAGE.json', {'Schema': 'csr-portable-package-v1', 'Tranche': 15,
    'CandidateSHA256': sha(NEW / gate.CANDIDATE),
    'Scope': 'Paired transport timing experiment; new MATLAB execution pending.',
    'UpdateBaseRecipe': candidate['BaseInstallation'],
    'FileCountExcludingManifest': len(files), 'MaximumRelativePathLength': max(map(len, files)),
    'Files': [{'path': n, 'bytes': p.stat().st_size, 'sha256': sha(p)} for n,p in sorted(files.items())]})
files['PACKAGE.json'] = NEW / 'PACKAGE.json'
old_manifest = json.loads((OLD / 'PACKAGE.json').read_text())
old_names = {r['path'] for r in old_manifest['Files']} | {'PACKAGE.json'}
assert old_names <= files.keys()
for row in old_manifest['Files']:
    assert sha(OLD / row['path']) == row['sha256']
delta = {n:p for n,p in files.items() if n not in old_names or sha(p) != sha(OLD / n)}
assert all(n not in old_names for n in delta if n.endswith('.m'))
target = ROOT / 't15up.zip'
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for n,p in sorted(delta.items()):
        archive.write(p,n)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None and set(archive.namelist()) == set(delta)
    assert set(archive.namelist()) | old_names == files.keys()
    for n,p in files.items():
        data = archive.read(n) if n in delta else (OLD / n).read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha(p), n
assert candidate_snapshot(NEW) == source
result = {'archive': target.name, 'bytes': target.stat().st_size, 'sha256': sha(target),
    'members': len(delta), 'maximum_relative_path_length': max(map(len, delta)),
    'overlay_reconstructs_complete_candidate': True, 'crc_verified': True,
    'deletions_required': False, 'validated_source_files_unchanged': 285,
    'candidate_sha256': sha(NEW / gate.CANDIDATE), 'matlab_executed': False,
    'matlab_tests_prepared': 117, 'python_gate_tests_passed': python_count}
write(WORK / 'package.json', result)
print(json.dumps(result, indent=2))
