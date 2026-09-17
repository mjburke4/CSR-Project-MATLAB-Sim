#!/usr/bin/env python3
"""Freeze T18 after source, native references and independent review finish."""
from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_tranche11_return import candidate_snapshot, selected_test_names

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    relative='evidence/tranche-18-candidate.json'
    baseline=json.loads((ROOT/'evidence/tranche-18-baseline.json').read_text())
    assert len(baseline)==313 and sum(row['path'].endswith('.m') for row in baseline)==160
    assert all(sha(ROOT/row['path'])==row['sha256'] for row in baseline)
    native=ROOT/'evidence/tranche-18-ns3-reference/manifest.json'
    assert native.is_file(), 'Native references must be complete before freezing'
    from run_tranche18_ns3_reference import verify_reference_suite
    native_review=verify_reference_suite(ROOT,json.loads((ROOT/'scenarios/t18/plan.json').read_text()))
    assert native_review['status']=='passed' and len(native_review['cases'])==10
    previous=json.loads((ROOT/'evidence/tranche-17-candidate.json').read_text())
    references=set(previous['ReferenceFiles'])
    for directory in ('evidence/t17','evidence/tranche-18-ns3-reference','evidence/tranche-18-source-audit'):
        references.update(p.relative_to(ROOT).as_posix() for p in (ROOT/directory).rglob('*') if p.is_file())
    references.update(('evidence/tranche-18-baseline.json','evidence/tranche-18-main-check.json','scenarios/t18/plan.json'))
    references=sorted(references)
    assert relative not in references
    inventory=[{'path':name,'sha256':sha(ROOT/name),'bytes':(ROOT/name).stat().st_size} for name in references]
    sources=candidate_snapshot(ROOT);sources.pop(relative,None)
    classes=['TestRelayServiceSuite','TestNetworkConfig','TestNwkLayer','TestHopLayer',
        'TestHopControls','TestAckServiceDiagnostics','TestLinkDiagnostics','TestHistoricalApplication',
        'TestBenchmarkAggregates','TestPerformanceSummary','TestNwkScenarios','TestMacHopCustody']
    files=['tests/'+name+'.m' for name in classes]
    methods=selected_test_names(ROOT,files)
    assert len(methods)==186, 'Focused test membership changed'
    candidate={'Schema':'csr-tranche-18-candidate-v1','Tranche':18,
        'Status':'relay_service_diagnostic_matlab_execution_pending',
        'CreatedUTC':datetime.now(timezone.utc).isoformat(),
        'Objective':'Real-PHY local/relayed admission and service at node5, with4-to-5 retry/capacity observations.',
        'SourceCommit':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b',
        'EngineCommit':'6b5cd24ea80713ce16d88575869aedd6f432bdae',
        'SourceMainInspection':'evidence/tranche-18-main-check.json',
        'BaseInstallation':'Copy the exact accepted Tranche17 installation and overlay every t18up.zip file at its root.',
        'BaseCandidateSHA256':sha(ROOT/'evidence/tranche-17-candidate.json'),
        'BaselineSourceSnapshot':'evidence/tranche-18-baseline.json',
        'BaseSourceSnapshotSHA256':sha(ROOT/'evidence/tranche-18-baseline.json'),
        'BaselineOwnerEvidence':'evidence/t17/owner.zip',
        'BaselineOwnerEvidenceSHA256':sha(ROOT/'evidence/t17/owner.zip'),
        'BaselineCandidate':'evidence/t17/candidate.json',
        'BaselineCandidateSHA256':sha(ROOT/'evidence/t17/candidate.json'),
        'BaselineAcceptance':'evidence/t17/acceptance.json',
        'BaselineAcceptanceSHA256':sha(ROOT/'evidence/t17/acceptance.json'),
        'AllowedModifiedSourceFiles':[],'BaselineSourceFiles':313,'BaselineMatlabFiles':160,
        'BaselineSourceFilesUnchanged':313,'BaselineMatlabFilesUnchanged':160,
        'SourceFilesExcludedPaths':[relative],
        'SourceFiles':[{'path':name,'sha256':value} for name,value in sorted(sources.items())],
        'TestFiles':files,'ExpectedTestNames':methods,'PreparedMatlabTestCount':len(methods),
        'PreflightTestFiles':['tests/TestRelayServiceSuite.m'],
        'ExpectedStructuralCheckNames':['research_accounting','performance_accounting',
            'complete_protocol_trace','complete_phy_trace','complete_admission_trace',
            'observer_feedback_contract','observer_service_contract','cancellation_contract',
            'default_continuous_timing','scenario_identity','completed_horizon','trace_horizon'],
        'ExpectedStructuralCheckCount':132,
        'Plan':'scenarios/t18/plan.json','PlanSHA256':sha(ROOT/'scenarios/t18/plan.json'),
        'ReferenceManifest':'evidence/tranche-18-ns3-reference/manifest.json',
        'ReferenceManifestSHA256':sha(native),
        'ReferenceRoots':[],'ReferenceFiles':references,'ReferenceFileInventory':inventory,
        'ExpectedObservedCases':10,'ExpectedExecutedCases':11,'ExpectedStructuralChecks':132,
        'ExpectedSimulatedSeconds':6900,'MATLABExecutedHere':False,'NativeExecutedHere':True,
        'FullAcceptanceEstablished':False,'NumericalParityEstablished':False,
        'DefaultTimingPolicy':'continuous','ProductionBehaviorChanged':False,
        'FullPortableRegressionRequired':False,'SourcePolicy':'Every T17 source binding remains byte-for-byte unchanged.'}
    (ROOT/relative).write_text(json.dumps(candidate,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'candidate_sha256':sha(ROOT/relative),'source_files_including_candidate':len(sources)+1,
        'matlab_files':sum(name.endswith('.m') for name in sources),'test_classes':len(files),
        'prepared_matlab_tests':len(methods),'reference_files':len(references),'baseline_unchanged':313},indent=2))

if __name__=='__main__':
    main()
