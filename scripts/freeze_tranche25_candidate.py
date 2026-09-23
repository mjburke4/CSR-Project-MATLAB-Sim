#!/usr/bin/env python3
"""Freeze the new T25 source/reference inventory after native preparation."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import analyze_tranche11_return as base
from tranche25_metrics import METHOD, PIN, ENGINE

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,required=True)
    a=p.parse_args();root=a.source_root.resolve()
    candidate_path='evidence/tranche-25-candidate.json'
    parent=base.json_object(root/'evidence/tranche-25-parent-candidate.json')
    baseline=base.json_value(root/'evidence/tranche-25-baseline.json')
    assert len(baseline)==404 and sum(r['path'].endswith('.m') for r in baseline)==181
    for r in baseline:assert base.sha256(root/r['path'])==r['sha256'],r['path']
    old_refs=base.record_map(parent['ReferenceFileInventory'],'T23 refs',sizes=True)
    for name,row in old_refs.items():
        path=root/('evidence/t25/baseline/parity-ledger.csv' if name=='docs/parity-ledger.csv' else name)
        assert base.sha256(path)==row['sha256'] and path.stat().st_size==row['bytes'],name
    plan=base.json_object(root/'scenarios/t25/plan.json')
    assert plan['numerical_method']==METHOD
    assert plan['reused_campus_sha256']==base.sha256(root/plan['reused_campus_file'])
    for seed in (131,132):
        m=base.json_object(root/f'evidence/tranche-25-ns3-reference/s{seed}/manifest.json')
        assert m['status']=='completed' and m['case']['seed']==seed
    sources=base.candidate_snapshot(root)
    sources.pop(candidate_path,None)
    test_files=sorted(p.relative_to(root).as_posix() for p in (root/'tests').glob('Test*.m'))
    test_names=base.selected_test_names(root,test_files)
    references=set(old_refs)
    references.update({'evidence/tranche-25-baseline.json','evidence/tranche-25-parent-candidate.json',
        'evidence/tranche-25-main-check.json','docs/parity-ledger-t24.csv','T25.md','AGENTS.md'})
    for folder in ('evidence/t19','evidence/t20','evidence/t23','evidence/t24','evidence/t25','evidence/tranche-25-ns3-reference'):
        references.update(p.relative_to(root).as_posix() for p in (root/folder).rglob('*')
                          if p.is_file() and '__pycache__' not in p.parts and not any(s.startswith('.') for s in p.relative_to(root/folder).parts))
    records=[{'path':name,'sha256':base.sha256(root/name),'bytes':(root/name).stat().st_size} for name in sorted(references)]
    c={'Schema':'csr-tranche-25-candidate-v1','Tranche':25,'Status':'native_references_verified_matlab_execution_pending',
       'CreatedUTC':datetime.now(timezone.utc).isoformat(),
       'Objective':'Extend unchanged full-campus comparison to seeds131132, reuse128130, and report all five seeds with descriptive10percent screens and exploratory run-level uncertainty.',
       'SourceCommit':PIN,'EngineCommit':ENGINE,'SourceMainInspection':'evidence/tranche-25-main-check.json',
       'BaseInstallation':'Copy the accepted T23 installation; overlay all t25up.zip files. T24 is an offline review.',
       'BaselineSourceSnapshot':'evidence/tranche-25-baseline.json',
       'BaseSourceSnapshotSHA256':base.sha256(root/'evidence/tranche-25-baseline.json'),
       'BaselineSourceFiles':404,'BaselineMatlabFiles':181,
       'BaselineCandidate':'evidence/tranche-25-parent-candidate.json',
       'BaselineCandidateSHA256':base.sha256(root/'evidence/tranche-25-parent-candidate.json'),
       'BaselineAcceptance':'evidence/t23/acceptance.json',
       'BaselineAcceptanceSHA256':base.sha256(root/'evidence/t23/acceptance.json'),
       'BaselineOwnerEvidence':'evidence/t23/owner.zip',
       'BaselineOwnerEvidenceSHA256':base.sha256(root/'evidence/t23/owner.zip'),
       'AllowedModifiedSourceFiles':[],'AllBaselineSourcesUnchanged':True,
       'AllowedModifiedReferenceFiles':['docs/parity-ledger.csv'],
       'PreservedBaselineLedger':'evidence/t25/baseline/parity-ledger.csv',
       'SourceFilesExcludedPaths':[candidate_path],
       'SourceFiles':[{'path':name,'sha256':digest} for name,digest in sorted(sources.items())],
       'ReferenceRoots':[],'ReferenceFiles':sorted(references),'ReferenceFileInventory':records,
       'Plan':'scenarios/t25/plan.json','PlanSHA256':base.sha256(root/'scenarios/t25/plan.json'),
       'TestFiles':test_files,'ExpectedTestNames':test_names,'ExpectedTestCount':len(test_names),
       'ExpectedCaseCount':2,'ComparisonSeeds':[128,129,130,131,132],'FreshSeeds':[131,132],'ReusedSeeds':[128,129,130],
       'ReusedCampusFile':'evidence/t25/reused-campus.json','ReusedCampusSHA256':base.sha256(root/'evidence/t25/reused-campus.json'),
       'WorkingCampusBandPercent':10,'NumericalMethod':METHOD,
       'FullPortableRegression':True,'FullCampusRun':True,'PlannedSimulatedSeconds':12000,
       'DataQueuedRetryPolicy':'actual-tx','TimingPolicy':'continuous','ProductionSourceChanged':False,
       'PHY_ECCChanged':False,'ObserverEnabled':False,'PostHorizonDrain':False,
       'MATLABExecuted':False,'MATLABExecutionPending':True,'AcceptanceEstablished':False,
       'NumericalParityEstablished':False,'NativeReferencePreparationCompleted':True}
    (root/candidate_path).write_text(json.dumps(c,indent=2)+'\n')
    print(json.dumps({'candidate_sha256':base.sha256(root/candidate_path),'source_bindings':len(sources)+1,
                      'matlab_files':sum(n.endswith('.m') for n in sources),'references':len(references),
                      'portable_test_classes':len(test_files),'portable_tests':len(test_names)}))

if __name__=='__main__':main()
