from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
OLD, NEW = ROOT / 'csr14s', ROOT / 'csr15'
sys.path.insert(0, str(NEW / 'scripts'))
from analyze_tranche11_return import selected_test_names

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')

old = json.loads((OLD / 'evidence/tranche-14-candidate.json').read_text())
loss = json.loads((NEW / 'evidence/tranche-13-candidate.json').read_text())
test_files = ['tests/TestTransportArrival.m'] + old['TestFiles']
names = selected_test_names(NEW, test_files)
assert len(names) == 117 and names[8:] == old['ExpectedTestNames']
baseline = json.loads((NEW / 'evidence/t14/source.json').read_text())
assert len(baseline) == 285 and sum(p['path'].endswith('.m') for p in baseline) == 144
assert all(sha(NEW / p['path']) == p['sha256'] for p in baseline)
prior = json.loads((OLD / 'evidence/tranche-14-readiness.json').read_text())
assert len(prior['ReferenceBindings']) == 317
assert all(sha(NEW / p) == h for p, h in prior['ReferenceBindings'].items())
plan = json.loads((NEW / 'scenarios/t15/plan.json').read_text())
assert plan['total_checkpoint_count'] == 528 and plan['total_case_count'] == 8
candidate = {
    'Schema': 'csr-tranche-15-candidate-v1', 'Tranche': 15,
    'Status': 'paired_transport_diagnostic_matlab_execution_pending',
    'CreatedUTC': datetime.now(timezone.utc).isoformat(),
    'Objective': 'Measure local transport-time conversion effects on continued-traffic delivery, retries, ACK service, relay custody and admission-capacity release.',
    'SourceCommit': old['SourceCommit'], 'EngineCommit': old['EngineCommit'],
    'SourceMainInspection': 'evidence/tranche-15-main-check.json',
    'BaseInstallation': 'Exact reviewed Tranche 14 r2 installation with t15up.zip applied at its root.',
    'BaseCandidateSHA256': sha(OLD / 'evidence/tranche-14-candidate.json'),
    'BasePackageInventorySHA256': sha(OLD / 'PACKAGE.json'),
    'BaselineCandidate': 'evidence/t14/candidate.json',
    'BaselineCandidateSHA256': sha(NEW / 'evidence/t14/candidate.json'),
    'BaselineOwnerEvidence': 'evidence/t14/owner.zip',
    'BaselineOwnerEvidenceSHA256': sha(NEW / 'evidence/t14/owner.zip'),
    'BaselineSourceSnapshot': 'evidence/t14/source.json',
    'BaseSourceSnapshotSHA256': sha(NEW / 'evidence/t14/source.json'),
    'BaselineSourceFilesUnchanged': 285, 'BaselineMatlabFilesUnchanged': 144,
    'CoreBaselineSourceSnapshot': old['CoreBaselineSourceSnapshot'],
    'CoreBaselineSourceSnapshotSHA256': old['CoreBaselineSourceSnapshotSHA256'],
    'CoreBaselineSourceFilesUnchanged': 225, 'CoreBaselineMatlabFilesUnchanged': 124,
    'TestFiles': test_files, 'ExpectedTestNames': names,
    'RetainedTestCount': 109, 'IndependentPreflightTestCount': 8,
    'ExpectedStructuralCheckCount': 528, 'TimingCaseCount': 8,
    'TimingPlan': 'scenarios/t15/plan.json',
    'TimingPlanSHA256': sha(NEW / 'scenarios/t15/plan.json'),
    'LossPlan': loss['LossPlan'], 'LossPlanSHA256': loss['LossPlanSHA256'],
    'LossReferenceManifest': loss['LossReferenceManifest'],
    'LossReferenceManifestSHA256': loss['LossReferenceManifestSHA256'],
    'RetainedLossCandidate': 'evidence/tranche-13-candidate.json',
    'RetainedLossCandidateSHA256': sha(NEW / 'evidence/tranche-13-candidate.json'),
    'ContinuousBaselineOwnerEvidence': 'evidence/t13/owner.zip',
    'ContinuousBaselineOwnerEvidenceSHA256': sha(NEW / 'evidence/t13/owner.zip'),
    'ReferenceRoots': old['ReferenceRoots'] + ['evidence/t14'],
    'ReferenceFiles': old['ReferenceFiles'] + ['evidence/tranche-15-main-check.json'],
    'CandidateGitCommit': None,
    'GitIdentityNote': 'Portable experimental candidate based on the exact reviewed owner source snapshot; no remote publication identity is asserted.',
    'MATLABExecuted': False, 'NativeRerunForTranche15': False,
    'NativeBoundReferencesReused': True, 'ProductionBehaviorChanged': False,
    'AcceptanceEstablished': False, 'NumericalParityEstablished': False,
    'OwnerCommand': 'report = run_tranche15_validation;', 'ReturnArchive': 't15.zip',
    'Scope': plan['scope'],
}
write(NEW / 'evidence/tranche-15-candidate.json', candidate)
print(json.dumps({'candidate_sha256': sha(NEW / 'evidence/tranche-15-candidate.json'),
                  'tests_prepared': len(names), 'structural_checks_prepared': 528}, indent=2))
