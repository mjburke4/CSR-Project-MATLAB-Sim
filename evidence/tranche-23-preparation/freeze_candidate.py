"""Freeze the T23 diagnostic overlay over the accepted T22 installation."""
import hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
WORK=Path(__file__).resolve().parents[1]
ROOT=WORK/'csr23'
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_tranche11_return import candidate_snapshot,selected_test_names

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,data): p.write_text(json.dumps(data,indent=2)+'\n')
baseline_path=ROOT/'evidence/tranche-23-baseline.json'
baseline=json.loads(baseline_path.read_text())
assert len(baseline)==390 and sum(x['path'].endswith('.m') for x in baseline)==178
for row in baseline: assert digest(ROOT/row['path'])==row['sha256'],row['path']
parent_path=ROOT/'evidence/tranche-23-parent-candidate.json'
parent=json.loads(parent_path.read_text())
for row in parent['ReferenceFileInventory']:
 p=ROOT/row['path']
 if row['path']=='docs/parity-ledger.csv': p=ROOT/'evidence/t23/baseline/parity-ledger.csv'
 assert digest(p)==row['sha256'] and p.stat().st_size==row['bytes'],row['path']
tests=['tests/TestReceiverFeedbackContract.m','tests/TestHopLayer.m','tests/TestNwkLayer.m','tests/TestRelayContract.m','tests/TestMacHopCustody.m']
reference_names={x['path'] for x in parent['ReferenceFileInventory']}
reference_names.update({'evidence/tranche-23-baseline.json','evidence/tranche-23-parent-candidate.json',
 'evidence/tranche-23-main-check.json','T23.md','docs/tranche-23-receiver-feedback.md','docs/parity-ledger.csv'})
for folder in ['evidence/t22/accepted','evidence/t23/native','evidence/t23/baseline','evidence/tranche-23-preparation']:
 reference_names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/folder).rglob('*')
   if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
reference_names=sorted(reference_names)
references=[{'path':n,'sha256':digest(ROOT/n),'bytes':(ROOT/n).stat().st_size} for n in reference_names]
candidate_file='evidence/tranche-23-candidate.json'
source=candidate_snapshot(ROOT);source.pop(candidate_file,None)
candidate={
 'Schema':'csr-tranche-23-candidate-v1','Tranche':23,
 'Status':'native_diagnostic_executed_matlab_execution_pending',
 'CreatedUTC':datetime.now(timezone.utc).isoformat(),
 'Objective':'Compare real receiver NWK/HOP custody and emitted ACK/DACK feedback under controlled relay and local pressure.',
 'SourceCommit':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b',
 'EngineCommit':'6b5cd24ea80713ce16d88575869aedd6f432bdae',
 'SourceMainInspection':'evidence/tranche-23-main-check.json',
 'BaseInstallation':'Copy the accepted T22 installation and overlay every t23up.zip file.',
 'BaselineSourceSnapshot':'evidence/tranche-23-baseline.json','BaseSourceSnapshotSHA256':digest(baseline_path),
 'BaselineSourceFiles':390,'BaselineMatlabFiles':178,
 'BaselineCandidate':'evidence/tranche-23-parent-candidate.json','BaselineCandidateSHA256':digest(parent_path),
 'BaselineAcceptance':'evidence/t22/accepted/acceptance.json',
 'BaselineAcceptanceSHA256':digest(ROOT/'evidence/t22/accepted/acceptance.json'),
 'BaselineOwnerEvidenceSHA256':'37863a70ef46c2889b3f945bcc2d3cfbe548115f1c349136488cc56357a9f6af',
 'AllowedModifiedSourceFiles':[],'AllBaselineSourcesUnchanged':True,
 'AllowedModifiedReferenceFiles':['docs/parity-ledger.csv'],
 'PreservedBaselineLedger':'evidence/t23/baseline/parity-ledger.csv',
 'SourceFilesExcludedPaths':[candidate_file],
 'SourceFiles':[{'path':k,'sha256':v} for k,v in sorted(source.items())],
 'ReferenceRoots':[],'ReferenceFiles':reference_names,'ReferenceFileInventory':references,
 'Plan':'scenarios/t23/plan.json','PlanSHA256':digest(ROOT/'scenarios/t23/plan.json'),
 'TestFiles':tests,'ExpectedTestNames':selected_test_names(ROOT,tests),
 'ExpectedCaseCount':7,'ExpectedCheckpointCount':123,'ExpectedFeedbackCount':91,
 'NativeReference':'evidence/t23/native/checkpoints.csv',
 'NativeReferenceSHA256':digest(ROOT/'evidence/t23/native/checkpoints.csv'),
 'NativeFeedbackReference':'evidence/t23/native/feedback.csv',
 'NativeFeedbackReferenceSHA256':digest(ROOT/'evidence/t23/native/feedback.csv'),
 'WorkingCampusBandPercent':10,'DiagnosticOnly':True,
 'FullPortableRegression':False,'FullCampusRun':False,'PHYExecuted':False,
 'ProductionSourceChanged':False,'MATLABExecuted':False,'MATLABExecutionPending':True,
 'AcceptanceEstablished':False,'NumericalParityEstablished':False,
 'DataQueuedRetryPolicy':'actual-tx','TimingPolicy':'continuous',
 'NativeEngineRebuilt':False,'NativeFixtureFreshlyCompiled':True,
}
write(ROOT/candidate_file,candidate)
print(json.dumps({'candidate_sha256':digest(ROOT/candidate_file),'source_count_including_candidate':len(source)+1,
 'reference_count':len(references),'focused_tests':len(candidate['ExpectedTestNames']),
 'cases':7,'checkpoints':123,'native_feedback_frames':91}))
