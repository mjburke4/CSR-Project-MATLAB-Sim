from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import shutil
import sys
import zipfile

WORK = Path(__file__).resolve().parent
ROOT = WORK.parent
OLD, NEW = ROOT / 'csr15', ROOT / 'csr16'
sys.path.insert(0, str(NEW / 'scripts'))
from analyze_tranche11_return import candidate_snapshot
import analyze_tranche16_return as gate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


preparation = gate.verify_preparation(NEW)
candidate = json.loads((NEW / gate.CANDIDATE).read_text())
source = candidate_snapshot(NEW)
assert len(source) == 304 and sum(name.endswith('.m') for name in source) == 155
assert len(candidate['ExpectedTestNames']) == 129
counts = {}
for name, expected in [('tests.log', 44), ('t15-tests.log', 28), ('t14-tests.log', 37)]:
    text = (WORK / 'gate' / name).read_text()
    matches = re.findall(r'Ran (\d+) tests', text)
    assert matches and int(matches[-1]) == expected and text.rstrip().endswith('OK'), name
    counts[name] = expected
lint = (WORK / 'gate/lint.log').read_text()
assert '8 file(s) analysed, everything seems fine' in lint
for name, status in [('core', 'no-blocking-findings-static-review'),
                     ('runner', 'no-open-blocking-findings-static-review'),
                     ('gate', 'no_remaining_blocking_findings')]:
    review = json.loads((WORK / 'review' / (name + '.json')).read_text())
    assert review['status'] == status
    if name == 'runner':
        assert not review['open_findings']
    if name == 'gate':
        assert not review['findings'] and review['candidate_sha256'] == sha(NEW / gate.CANDIDATE)

out = NEW / 'evidence/tranche-16-preparation'
out.mkdir(exist_ok=True)
copies = {
    'review/core.json': 'core-review.json', 'review/core.md': 'core-review.md',
    'review/runner.json': 'runner-review.json', 'review/runner.md': 'runner-review.md',
    'review/gate.json': 'gate-review.json', 'review/gate.md': 'gate-review.md',
    'gate/tests.log': 'tests.log', 'gate/t15-tests.log': 't15-tests.log',
    'gate/t14-tests.log': 't14-tests.log', 'gate/lint.log': 'lint.log',
    'gate/preparation.json': 'gate.json', 'native.json': 'native.json',
    'native-live.json': 'native-live.json', 'design.md': 'design.md',
    'interface.json': 'interface.json', 'runner-interface.json': 'runner-interface.json',
    'core.json': 'core.json', 'runner.json': 'runner.json',
    'freeze.py': 'freeze.py', 'package.py': 'package.py',
}
for source_name, target_name in copies.items():
    shutil.copyfile(WORK / source_name, out / target_name)
refs = {name: sha(NEW / name) for name in candidate['ReferenceFiles']}
ready = {
    'Schema': 'csr-tranche-16-readiness-v1', 'Tranche': 16,
    'Status': 'ready_for_owner_matlab_execution',
    'CreatedUTC': datetime.now(timezone.utc).isoformat(),
    'CandidateSHA256': sha(NEW / gate.CANDIDATE),
    'SourceCommit': candidate['SourceCommit'], 'EngineCommit': candidate['EngineCommit'],
    'MATLABExecuted': False, 'NativeRerunForTranche16': False,
    'NativeBoundReferencesReused': True, 'DefaultPolicyChanged': False,
    'AcceptanceEstablished': False, 'NumericalParityEstablished': False,
    'CandidateSourceFiles': len(source), 'CandidateMatlabFiles': 155,
    'BaselineSourceFilesUnchanged': 292, 'BaselineMatlabFilesUnchanged': 147,
    'ChangedExistingSourceFiles': candidate['AllowedModifiedSourceFiles'],
    'PreparedMatlabTests': 129, 'RetainedMatlabTests': 117,
    'PreparedStructuralChecks': 192, 'BaseCases': 6, 'PairedRuns': 12,
    'PlannedSimulatedSeconds': 9360, 'PythonCheckerTestsPassed': sum(counts.values()),
    'NewPythonCheckerTestsPassed': 44, 'RetainedPythonCheckerTestsPassed': 65,
    'MatlabStaticFilesParsed': 8, 'ReferenceFiles': len(refs),
    'SourceBindings': source, 'ReferenceBindings': dict(sorted(refs.items())),
    'Preparation': preparation,
    'ReviewEvidence': [{'path': p.relative_to(NEW).as_posix(), 'sha256': sha(p)}
                       for p in sorted(out.iterdir()) if p.is_file()],
    'Delivery': {'Archive': 't16up.zip', 'Command': 'report = run_tranche16_validation;',
                 'ReturnArchive': 't16.zip', 'SuggestedRoot': 'C:\\csr16'},
    'Scope': candidate['Scope'],
}
write(NEW / 'evidence/tranche-16-readiness.json', ready)
excluded = {'.git', '__pycache__', '.pytest_cache', 'results'}
files = {p.relative_to(NEW).as_posix(): p for p in NEW.rglob('*') if p.is_file()
         and not any(part in excluded for part in p.relative_to(NEW).parts)
         and p.suffix not in {'.pyc', '.pyo'} and p.name != 'PACKAGE.json'}
assert len(files) == len({n.casefold() for n in files})
old_manifest = json.loads((OLD / 'PACKAGE.json').read_text())
old_names = {r['path'] for r in old_manifest['Files']} | {'PACKAGE.json'}
for row in old_manifest['Files']:
    assert sha(OLD / row['path']) == row['sha256'], row['path']
write(NEW / 'PACKAGE.json', {
    'Schema': 'csr-portable-package-v1', 'Tranche': 16,
    'CandidateSHA256': ready['CandidateSHA256'],
    'Scope': 'Optional receiver callback timing candidate; MATLAB execution pending.',
    'UpdateBaseRecipe': candidate['BaseInstallation'],
    'FileCountExcludingManifest': len(files), 'MaximumRelativePathLength': max(map(len, files)),
    'Files': [{'path': n, 'bytes': p.stat().st_size, 'sha256': sha(p)} for n, p in sorted(files.items())],
})
files['PACKAGE.json'] = NEW / 'PACKAGE.json'
assert old_names <= files.keys()
delta = {n: p for n, p in files.items() if n not in old_names or sha(p) != sha(OLD / n)}
modified_matlab = sorted(n for n in delta if n in old_names and n.endswith('.m'))
assert modified_matlab == sorted(gate.MODIFIED), modified_matlab
target = ROOT / 't16up.zip'
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for n, p in sorted(delta.items()):
        archive.write(p, n)
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None and set(archive.namelist()) == set(delta)
    assert set(archive.namelist()) | old_names == files.keys()
    for n, p in files.items():
        data = archive.read(n) if n in delta else (OLD / n).read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha(p), n
assert candidate_snapshot(NEW) == source
result = {
    'archive': target.name, 'bytes': target.stat().st_size, 'sha256': sha(target),
    'members': len(delta), 'maximum_update_path_length': max(map(len, delta)),
    'complete_candidate_files': len(files), 'overlay_reconstructs_complete_candidate': True,
    'crc_verified': True, 'deletions_required': False,
    'candidate_sha256': ready['CandidateSHA256'], 'changed_existing_matlab_files': modified_matlab,
    'unchanged_baseline_source_files': 292, 'unchanged_baseline_matlab_files': 147,
    'matlab_executed': False, 'matlab_tests_prepared': 129,
    'python_checker_tests_passed': 109, 'static_matlab_files_parsed': 8,
}
write(WORK / 'package.json', result)
print(json.dumps(result, indent=2))
