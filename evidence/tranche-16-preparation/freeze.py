from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sys

WORK = Path(__file__).resolve().parent
ROOT = WORK.parent
OLD, NEW = ROOT / 'csr15', ROOT / 'csr16'
sys.path.insert(0, str(NEW / 'scripts'))
from analyze_tranche11_return import candidate_snapshot, selected_test_names


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


candidate_path = 'evidence/tranche-16-candidate.json'
old = json.loads((OLD / 'evidence/tranche-15-candidate.json').read_text())
baseline = json.loads((NEW / 'evidence/tranche-16-baseline.json').read_text())
assert len(baseline) == 294 and sum(x['path'].endswith('.m') for x in baseline) == 149
allowed = ['+csr/+phy/SignalEngine.m', '+csr/+sim/NetworkSimulation.m']
for row in baseline:
    assert sha(OLD / row['path']) == row['sha256'], row['path']
    if row['path'] not in allowed:
        assert sha(NEW / row['path']) == row['sha256'], row['path']
    else:
        assert sha(NEW / row['path']) != row['sha256'], row['path']
test_files = ['tests/TestNetworkTransportTiming.m', 'tests/TestNetworkTimingSuite.m'] + old['TestFiles']
names = selected_test_names(NEW, test_files)
assert len(names) == 129 and names[12:] == old['ExpectedTestNames']
plan_path = 'scenarios/t16/plan.json'
plan = json.loads((NEW / plan_path).read_text())
assert [row['case_id'] for row in plan['cases']] == ['a128', 'c128', 'a129', 'c129', 'a130', 'c130']
refs = set(old['ReferenceFiles'])
for name in old['ReferenceRoots']:
    refs.update(p.relative_to(NEW).as_posix() for p in (NEW / name).rglob('*') if p.is_file())
for key in ['input_bindings', 'reference_bindings']:
    if key in plan:
        refs.update(row['path'] for row in plan[key])
for key in ['input_files', 'source_files', 'reference_files']:
    if key in plan:
        refs.update(row['path'] for row in plan[key])
refs.update([
    plan_path, 'evidence/tranche-16-baseline.json', 'evidence/tranche-16-main-check.json',
    'evidence/tranche-8-r2025a-accepted/tranche8_evidence.zip',
])
refs.update(p.relative_to(NEW).as_posix() for p in (NEW / 'evidence/t15').rglob('*') if p.is_file())
assert all((NEW / name).is_file() for name in refs)
sources = candidate_snapshot(NEW)
sources.pop(candidate_path, None)
candidate = {
    'Schema': 'csr-tranche-16-candidate-v1', 'Tranche': 16,
    'Status': 'network_receiver_timing_matlab_execution_pending',
    'CreatedUTC': datetime.now(timezone.utc).isoformat(),
    'Objective': 'Measure optional receiver callback timing across three seeds in unchanged real-PHY admission and contention workloads.',
    'SourceCommit': old['SourceCommit'], 'EngineCommit': old['EngineCommit'],
    'SourceMainInspection': 'evidence/tranche-16-main-check.json',
    'BaseInstallation': 'A copy of the exact reviewed Tranche 15 installation, with the complete t16up.zip overlaid at its root.',
    'BaseCandidateSHA256': sha(OLD / 'evidence/tranche-15-candidate.json'),
    'BasePackageInventorySHA256': sha(OLD / 'PACKAGE.json'),
    'BaselineSourceSnapshot': 'evidence/tranche-16-baseline.json',
    'BaseSourceSnapshotSHA256': sha(NEW / 'evidence/tranche-16-baseline.json'),
    'BaselineOwnerEvidence': 'evidence/t15/owner.zip',
    'BaselineOwnerEvidenceSHA256': sha(NEW / 'evidence/t15/owner.zip'),
    'BaselineCandidate': 'evidence/t15/candidate.json',
    'BaselineCandidateSHA256': sha(NEW / 'evidence/t15/candidate.json'),
    'AllowedModifiedSourceFiles': [
        {'path': name, 'sha256': sha(NEW / name), 'bytes': (NEW / name).stat().st_size}
        for name in allowed
    ],
    'BaselineSourceFiles': 294, 'BaselineMatlabFiles': 149,
    'BaselineSourceFilesUnchanged': 292, 'BaselineMatlabFilesUnchanged': 147,
    'SourceFilesExcludedPaths': [candidate_path],
    'SourceFiles': [{'path': name, 'sha256': digest} for name, digest in sorted(sources.items())],
    'TestFiles': test_files, 'ExpectedTestNames': names,
    'RetainedTestCount': 117, 'IndependentPreflightTestCount': 9,
    'NewSuiteTestCount': 3, 'PreparedMatlabTestCount': len(names),
    'ExpectedStructuralCheckCount': 192,
    'BaseCaseCount': 6, 'PairedCaseCount': 12, 'PlannedSimulatedSeconds': 9360,
    'Plan': plan_path, 'PlanSHA256': sha(NEW / plan_path),
    'TimingModes': ['continuous', 'nanoseconds'],
    'ServiceWindowSeconds': [300, 320], 'ServiceWindowEndExclusive': True,
    'TimingMaxRecords': 100000, 'ServiceMaxRecords': 100000,
    'ReferenceRoots': [], 'ReferenceFiles': sorted(refs),
    'MATLABExecuted': False, 'NativeRerunForTranche16': False,
    'NativeBoundReferencesReused': True, 'DefaultPolicyChanged': False,
    'OptionalReceiverCallbackPolicyAdded': True,
    'AcceptanceEstablished': False, 'NumericalParityEstablished': False,
    'CandidateGitCommit': None,
    'GitIdentityNote': 'Isolated experimental candidate. Previously authorized Tranches 6–14 publication excludes Tranche 16.',
    'OwnerCommand': 'report = run_tranche16_validation;', 'ReturnArchive': 't16.zip',
    'Scope': 'Optional receiver callback timing in unchanged full-PHY admission/contention workloads. Physical signal fields, PHY/ECC formulas, TX/MAC/global timers and default behavior retained. Continued traffic is censored at the original horizon; no forced drain, campus parity or production-policy promotion.',
}
write(NEW / candidate_path, candidate)
full_source = candidate_snapshot(NEW)
assert {n: h for n, h in full_source.items() if n != candidate_path} == sources
write(WORK / 'freeze.json', {
    'candidate_sha256': sha(NEW / candidate_path),
    'source_count': len(full_source),
    'matlab_count': sum(n.endswith('.m') for n in full_source),
    'reference_count': len(refs), 'prepared_tests': len(names),
    'prepared_structural_checks': 192,
    'matlab_executed': False, 'native_rerun': False,
})
print((WORK / 'freeze.json').read_text())
