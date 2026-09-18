#!/usr/bin/env python3
"""Assemble the completed T24 diagnostic after the independent gate passes."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

HERE=Path(__file__).resolve().parent
WORK=HERE.parent
PACKAGE=HERE/'package'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def js(path):
    return json.loads(path.read_text())

def write_json(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')

def copy(source, rel):
    dest=PACKAGE/rel
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,dest)

def tree(source,rel):
    for path in sorted(source.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            copy(path,Path(rel)/path.relative_to(source))

def main():
    gate=js(HERE/'review/independent-review.json')
    assert gate['status']=='pass', 'Independent gate must pass before packaging'
    for rel,binding in gate['reviewed_files'].items():
        path=HERE/rel
        assert sha(path)==binding['sha256'] and path.stat().st_size==binding['bytes'], ('Changed since review',rel)
    proof=js(HERE/'input-verification.json')
    assert proof['status']=='pass'
    PACKAGE.mkdir(exist_ok=True)
    assert not any(PACKAGE.iterdir()), 'Use an empty package directory'
    for name in ('T24_Review.md','README.md','analyze_matlab.py','verify_inputs.py','input-verification.json','package_review.py','AGENTS.md'):
        copy(HERE/name,name)
    tree(HERE/'analysis','analysis')
    tree(HERE/'matlab','matlab')
    tree(HERE/'review','review')
    copy(HERE/'inputs/source-pin.json','context/source-pin.json')
    copy(HERE/'inputs/t21review/diagnostic.json','context/t21-diagnostic.json')
    copy(HERE/'inputs/t21review/T21_Review.md','context/T21_Review.md')
    copy(WORK/'t23-return-review/package/acceptance.json','context/t23-acceptance.json')
    copy(WORK/'t23-return-review/package/T23_Review.md','context/T23_Review.md')
    source=WORK/'t23-return-review/issued-overlay'
    copy(source/'evidence/tranche-23-candidate.json','context/tranche-23-candidate.json')
    for filename in ('csr-nwk-layer.h','csr-hop-layer.h'):
        copy(WORK/'t23-return-review/findings/source'/filename,'context/source/'+filename)
    copy(source/'+csr/+nwk/Layer.m','context/source/matlab-nwk-Layer.m')
    copy(source/'+csr/+hop/Layer.m','context/source/matlab-hop-Layer.m')
    for seed in (129,130):
        for name in ('scenario.csv','ns3-aggregates.provenance.json'):
            copy(source/f'evidence/tranche-20-ns3-reference/s{seed}'/name,f'context/native/s{seed}/'+name)
        for name in ('receipt.json','receipt.sha256'):
            copy(HERE/f'inputs/t20/s{seed}'/name,f'context/matlab/s{seed}/'+name)
    base_ledger=WORK/'t23-return-review/package/parity-ledger.csv'
    with base_ledger.open(newline='') as stream:
        rows=list(csv.reader(stream))
    rows.extend([
        ['T24_campus_duplicate_custody','No_new_OPNET_run','Native129_130_exact_lifecycle_census','Accepted_offline_diagnostic','Node8_source7_849_and1361_unique_entries_zero_repeats_318distinct_waiting_at130_stop','No_MATLAB_rerun_or_production_change_404source_bindings_unchanged','24'],
        ['T24_rare_native_repeat_service','OPNET_custody_behavior_unresolved','10_and9_repeat_entries_elsewhere_all_submitted_and_released','Documented_ownership_difference','Repeat_HOP_capacity_owner_seconds_share_0p0619pct_and0p0456pct','Retain_discrepancy_backlog_no_counterfactual_performance_claim','24'],
        ['T24_next_decision','Archived_OPNET_context_retained','Controlled_sender_and_feedback_contracts_already_reviewed','Unchanged_default_retained','Working10pct_single_seed_flags_preserved_no_new_performance_acceptance','Recommend_fixed6000s_seeds131_132_reuse128_130_no_T25_runs_started','24']
    ])
    with (PACKAGE/'parity-ledger.csv').open('w',newline='') as stream:
        csv.writer(stream).writerows(rows)
    results=[js(HERE/f'analysis/results/s{s}-census.json') for s in (129,130)]
    summary=[]
    for r in results:
        focus=next(f for f in r['flows'] if f['node']==8 and f['source']==7)
        totals={group:{key:sum(f[group][key] for f in r['flows']) for key in ('enqueues','forwards','nsdp_owner_seconds','hop_capacity_owner_seconds')} for group in ('all_instances','repeated_instances')}
        summary.append({'seed':r['seed'],'trace_rows':r['input']['rows'],
                        'node8_source7':{'entries':focus['all_instances']['enqueues'],
                         'distinct_applications':focus['distinct_application_identities'],
                         'repeated_entries':focus['repeat_enqueue_count'],
                         'waiting_at_stop':focus['all_instances']['waiting_at_stop']},
                        'totals':totals,
                        'repeat_capacity_share_percent':100*totals['repeated_instances']['hop_capacity_owner_seconds']/totals['all_instances']['hop_capacity_owner_seconds']})
    assert [x['node8_source7']['repeated_entries'] for x in summary]==[0,0]
    assert [x['totals']['repeated_instances']['enqueues'] for x in summary]==[10,9]
    acceptance={'schema':'csr-tranche24-offline-diagnostic-acceptance-v1',
                'created_utc':datetime.now(timezone.utc).isoformat(),
                'status':'accepted_offline_custody_diagnostic',
                'diagnostic_accepted':True,'numerical_parity_established':False,
                'working_campus_band_percent':10,
                'matlab_simulations_executed':0,'native_simulations_executed':0,
                'opnet_simulations_executed':0,'new_matlab_tests_executed':0,
                'matlab_rerun_required':False,'production_files_modified':[],
                'source_bindings_verified':proof['t23_source_bindings_verified_including_candidate'],
                'default_retry_policy':'actual-tx','timing':'continuous','PHY_ECC_changed':False,
                'independent_review_sha256':sha(HERE/'review/independent-review.json'),
                'input_verification_sha256':sha(HERE/'input-verification.json'),
                'results':summary,
                'decision':'Keep the current default. Repeats contribute no direct node8/source7 custody and do not account for its observed backlog. Rare downstream repeats remain a documented difference; no causal performance bound is claimed.',
                'recommended_next_tranche':'Two predefined unchanged campus seeds131 and132, preserving all accepted128-130 results and existing per-seed10percent flags, with pooled comparisons and uncertainty.',
                'next_tranche_prepared_or_executed':False}
    write_json(PACKAGE/'acceptance.json',acceptance)
    files={p.relative_to(PACKAGE).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(PACKAGE.rglob('*')) if p.is_file()}
    write_json(PACKAGE/'SHA256SUMS.json',{'schema':'csr-tranche24-package-sha256-v1','files':files})
    target=WORK/'deliverables/t24review.zip'
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(PACKAGE.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(PACKAGE).as_posix())
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert set(z.namelist())==set(files)|{'SHA256SUMS.json'}
        for name,binding in files.items():
            data=z.read(name)
            assert len(data)==binding['bytes'] and hashlib.sha256(data).hexdigest()==binding['sha256']
    receipt={'path':str(target),'bytes':target.stat().st_size,'sha256':sha(target),'members':len(files)+1,'closed_manifest_verified':True}
    write_json(HERE/'package-receipt.json',receipt)
    print(json.dumps(receipt))

if __name__=='__main__':main()
