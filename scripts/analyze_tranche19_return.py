#!/usr/bin/env python3
"""Review complete T19 full-campus policy evidence without executing MATLAB.

Structural completeness, preserved default behavior and evidence identities are
gates. Numerical 5% bands remain descriptive, including cases outside the band.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from analyze_tranche11_return import (all_files, candidate_snapshot, csv_rows,
    json_object, json_value, logical, number, record_map, records, require,
    safe_path, selected_test_names, sha256, verify_sources)
import analyze_tranche7_return as t7
import analyze_tranche17_return as t17
import analyze_research_sweep as sweep
import compare_benchmark_aggregates as aggregate
import tranche10_metrics as retained
import tranche19_metrics as metrics

integer = metrics.integer
SCHEMA = 'csr-matlab-tranche-19-validation-v1'
REVIEW_SCHEMA = 'csr-matlab-tranche-19-return-review-v1'
CANDIDATE = 'evidence/tranche-19-candidate.json'
BASELINE = 'evidence/tranche-19-baseline.json'
BASELINE_SHA = '622a511a886219da69ee08678d9b295828feb87e1d708c85f9fd632db4bcff61'
PARENT_OWNER_SHA = '85d63854fff84e8aaf62b5c9814603cbc277cffa6c67c648ba3892d90107965d'
PARENT_CANDIDATE_SHA = 'a74c20d7398c315ca3bbfc02f00be5e4800f228ce1269a6dae66921bd5f975ec'
T17_OWNER_SHA = '19921afa83c57db2779e4302e5b39afef5120afb129a87fddb1f6d1bdbec2bd1'
PLAN = 'scenarios/t19/plan.json'
NATIVE = 'evidence/tranche-7-ns3-reference/campus_multihop_6000'
PHASES = ('tests','a128','p128')
ALLOWED_CHANGES = {'+csr/+hop/Layer.m','+csr/+hop/validateConfig.m'}
CORE_CSV = ('trace.csv','protocol_trace.csv','phy_trace.csv','nodes.csv','mac_nodes.csv','hop_nodes.csv',
    'nwk_nodes.csv','neighbors.csv','routes.csv','application_admission_statistics.csv','application_admission_trace.csv','scenario.csv')
LIMITATIONS = [
    'Hashes bind the frozen candidate and returned claims; they are not independent proof of MATLAB execution.',
    'Two full-horizon cases use one seed. Numerical bands are descriptive practical targets, not pass gates or confidence intervals.',
    'The default case must reproduce accepted T17 statistics and original CSV bytes. The experimental DATA policy may change subsequent events and RNG consumption.',
    'CONTROL, continuous timing and PHY/ECC are unchanged. Native-provisional is a bounded DATA policy intervention, not complete native HOP equivalence.',
    'Complete counters cover all 1,710,000 admission attempts. Only the historical first 100,000 attempt records are retained; omitted blocked-reason timing is unavailable.',
    'Ownership is reconstructed from ordered protocol callbacks and checked against endpoint counters. DACK receipt and HOP capacity release are distinct.',
    'Native application identities are joined within ns-3 only; unmatched sends cannot distinguish drop and pending outcomes.',
    'No post-stop draining, numeric acceptance, default policy promotion or cross-engine common-random-stream claim is made.'
]


def inventory(root, raw, label, *, excluded=(), local=()):
    """Closed inventory with scalar-struct and scientific integer support."""
    root = Path(root)
    found = record_map(raw,label,sizes=True,empty=True)
    raw_rows = {row['path']:row for row in records(raw,label,empty=True)}
    for name,item in found.items():
        path = safe_path(root,name)
        require(path.is_file() and path.stat().st_size == item['bytes'] and sha256(path) == item['sha256'],
                'Artifact hash/size mismatch: '+name)
        count = raw_rows[name].get('row_count')
        if count not in (None,[]):
            require(path.suffix == '.csv' and sum(1 for _ in metrics.rows(path)) == integer(count,'CSV row count'),
                    'Artifact CSV row count mismatch: '+name)
    local_items = record_map(local or [],label+' local',sizes=True,empty=True)
    require(not (set(found) & set(local_items)), 'Artifact present in both carried and local inventories')
    for name,item in local_items.items():
        path = safe_path(root,name)
        require(path.suffix in ('.mat','.zip'), 'Invalid omitted local-only artifact')
        if path.exists():
            require(path.is_file() and path.stat().st_size == item['bytes'] and sha256(path) == item['sha256'],
                    'Local artifact hash/size mismatch: '+name)
    require(all_files(root)-set(excluded)-set(local_items) == set(found), 'Incomplete '+label+' inventory')
    return found


def verify_baseline(source_root,candidate,metadata=None):
    require(candidate.get('BaselineSourceSnapshot') == BASELINE and
            candidate.get('BaseSourceSnapshotSHA256') == sha256(source_root/BASELINE) == BASELINE_SHA,
            'Accepted T18 source snapshot mismatch')
    baseline = record_map(json_value(source_root/BASELINE),'T18 baseline')
    require(len(baseline) == 346 and sum(name.endswith('.m') for name in baseline) == 164,
            'T18 baseline membership mismatch')
    changes = records(candidate.get('AllowedModifiedSourceFiles'),'allowed source changes')
    require(len(changes) == len(ALLOWED_CHANGES) and {r.get('path') for r in changes} == ALLOWED_CHANGES,
            'Unapproved baseline modification membership')
    changes = {r['path']:r for r in changes}
    for name,row in baseline.items():
        digest = sha256(safe_path(source_root,name))
        if name in changes:
            require(changes[name].get('baseline_sha256') == row['sha256'] and
                    changes[name].get('candidate_sha256') == digest and digest != row['sha256'],
                    'Allowed source modification binding mismatch: '+name)
        else:
            require(digest == row['sha256'],'Previously accepted source changed outside policy scope: '+name)
    require(candidate.get('BaselineSourceFiles') == 346 and candidate.get('BaselineMatlabFiles') == 164,
            'Frozen baseline source counts disagree')
    parent_dir = source_root/'evidence/t18'
    require(sha256(parent_dir/'owner.zip') == PARENT_OWNER_SHA and sha256(parent_dir/'candidate.json') == PARENT_CANDIDATE_SHA,
            'Accepted T18 owner/candidate identity mismatch')
    acceptance = json_object(parent_dir/'acceptance.json')
    require(acceptance.get('status') == 'accepted_for_focused_diagnostic' and
            acceptance.get('owner_evidence_sha256') == PARENT_OWNER_SHA and
            acceptance.get('candidate_sha256') == PARENT_CANDIDATE_SHA and
            acceptance.get('source_snapshot_sha256') == BASELINE_SHA, 'Accepted T18 provenance mismatch')
    with zipfile.ZipFile(parent_dir/'owner.zip') as archive:
        parent = json.loads(archive.read('metadata.json'))
        require(parent.get('Status') == 'completed' and parent.get('TestsPassed') is True and
                parent.get('CandidateSHA256') == PARENT_CANDIDATE_SHA and
                parent.get('SourceSnapshotSHA256') == hashlib.sha256(archive.read('source.json')).hexdigest() == BASELINE_SHA,
                'Baseline not bound to completed T18 return')
    if metadata is not None:
        require(metadata.get('AllBaselineSourcesUnchanged') is False and
                metadata.get('UnmodifiedBaselineSourcesUnchanged') is True and
                metadata.get('AllowedBaselineModificationsVerified') is True and
                metadata.get('AllowedModifiedSourceFiles') == candidate['AllowedModifiedSourceFiles'] and
                metadata.get('BaselineSourceFilesVerified') == 346 and metadata.get('BaselineMatlabFilesVerified') == 164,
                'Returned baseline modification claims disagree')
    return {'source_files':346,'matlab_files':164,'source_snapshot_sha256':BASELINE_SHA,
        'modified_files':list(changes),'all_other_baseline_sources_unchanged':True}


def verify_plan(source_root,candidate):
    require(candidate.get('Plan') == PLAN and candidate.get('PlanSHA256') == sha256(source_root/PLAN),'Plan hash/path mismatch')
    plan = json_object(source_root/PLAN)
    expected = {'schema':'csr-tranche19-queued-retry-plan-v1','tranche':19,'ns3_source_commit':t7.PIN,
        'engine_commit':'6b5cd24ea80713ce16d88575869aedd6f432bdae','execution_order':['a128','p128'],
        'planned_simulated_seconds':12000,'comparison_band_percent':5.0,'timeline_bucket_width_s':300,
        'trace_limits':{'protocol':1500000,'phy':1500000,'admission':100000},'max_events':12000000,
        'expected_admission_attempts':1710000,'seed':128,'duration_s':6000,
        'node_ids':[1,2,3,4,5,7,8],'flow_sources':[2,3,4,5,7,8],'timing_policy':'continuous',
        'native_reference_directory':NATIVE,'native_reference_reused':True,'full_portable_regression':True,
        'single_seed_scope':True,'extra_seed_confirmation_deferred':True,
        'baseline_owner_evidence':'evidence/t17/owner.zip','baseline_owner_evidence_sha256':T17_OWNER_SHA,
        'accepted_parent_owner_evidence':'evidence/t18/owner.zip','accepted_parent_owner_evidence_sha256':PARENT_OWNER_SHA}
    expected.update(dict.fromkeys(('default_policy_changed','phy_ecc_changed','observer_enabled','post_horizon_drain',
        'numerical_parity_required','common_random_numbers_claimed','native_execution_required','native_tests_included',
        'finite_stop_pending_is_failure'),False))
    require(all(plan.get(key) == value for key,value in expected.items()), 'T19 plan identity/scope mismatch')
    catalog = json_object(source_root/'scenarios/benchmarks/catalog.json')
    campus = [row for row in records(catalog.get('cases'),'catalog cases') if row.get('case_id') == 'campus_multihop_6000']
    require(len(campus) == 1,'Original campus catalog missing/duplicate')
    campus = campus[0]
    require(plan.get('scenario_file') == campus['scenario_file'] and
            plan.get('scenario_sha256') == campus['scenario_sha256'] == sha256(source_root/campus['scenario_file']),
            'Original campus input changed')
    cases = records(plan.get('cases'),'planned cases')
    require([c.get('case_id') for c in cases] == ['a128','p128'],'Missing/duplicate/reordered policy cases')
    for case,policy in zip(cases,('actual-tx','native-provisional')):
        require(case.get('policy') == policy and all(case.get(key) == campus[key] for key in
                ('seed','duration_s','scenario','scenario_file','scenario_sha256','reference_directory','bucket_width_s')),
                'Policy case changed original campus workload')
    require(sha256(source_root/'evidence/t17/owner.zip') == T17_OWNER_SHA,'Accepted T17 default reference changed')
    return plan,campus


def verify_references(source_root,candidate):
    names = candidate.get('ReferenceFiles')
    require(candidate.get('ReferenceRoots') == [] and isinstance(names,list) and names == sorted(set(names)) and names,
            'Expected sorted explicit reference inventory')
    bindings = record_map(candidate.get('ReferenceFileInventory'),'references',sizes=True)
    require(set(bindings) == set(names),'Reference membership mismatch')
    required = {BASELINE,'evidence/t18/owner.zip','evidence/t18/candidate.json','evidence/t18/acceptance.json',
                'evidence/t17/owner.zip','evidence/t17/acceptance.json'}
    for tree in ('evidence/tranche-7-ns3-reference','evidence/tranche-7-benchmark-inputs'):
        required.update(f'{tree}/{name}' for name in all_files(source_root/tree))
    require(required <= set(bindings),'Required parent/native reference membership missing')
    for name,row in bindings.items():
        path = safe_path(source_root,name)
        require(path.is_file() and path.stat().st_size == row['bytes'] and sha256(path) == row['sha256'],
                'Reference bytes changed: '+name)
    t7.verify_reference_suite(source_root,json_object(source_root/'scenarios/benchmarks/catalog.json'))
    return bindings


def verify_preparation(source_root):
    source_root = Path(source_root).resolve()
    candidate = json_object(source_root/CANDIDATE)
    require(candidate.get('Schema') == 'csr-tranche-19-candidate-v1' and candidate.get('Tranche') == 19
            and candidate.get('SourceCommit') == t7.PIN,'Candidate identity/source pin mismatch')
    source = candidate_snapshot(source_root)
    require(candidate.get('SourceFilesExcludedPaths') == [CANDIDATE] and
            t17.source_map(candidate.get('SourceFiles'),'candidate sources') ==
            {name:digest for name,digest in source.items() if name != CANDIDATE},'Candidate sources changed/missing')
    files = sorted(p.relative_to(source_root).as_posix() for p in (source_root/'tests').glob('Test*.m'))
    names = selected_test_names(source_root,files)
    require(candidate.get('TestFiles') == files and candidate.get('ExpectedTestNames') == names
            and set(names) == t7.portable_test_names(source_root),'Full portable test selection mismatch')
    baseline = verify_baseline(source_root,candidate)
    references = verify_references(source_root,candidate)
    plan,campus = verify_plan(source_root,candidate)
    native = metrics.native_applications(source_root/NATIVE)
    return {'source':source,'references':references,'baseline':baseline,'plan':plan,'campus':campus,
        'planned_matlab_tests':len(names),'planned_cases':2,'native_application_reference':native,
        'matlab_executed':False}


def verify_identity(root,metadata,source_root,candidate):
    require(metadata.get('Schema') == SCHEMA and metadata.get('Tranche') == 19 and
            metadata.get('Status') == 'completed-review-required','Return is not finalized complete T19 evidence')
    require(metadata.get('CandidateFile') == CANDIDATE and metadata.get('CandidateSHA256') == sha256(source_root/CANDIDATE)
            == sha256(root/'candidate.json') and sha256(root/'plan.json') == candidate['PlanSHA256'],
            'Returned candidate/plan binding mismatch')
    runtime = metadata.get('Runtime')
    require(isinstance(runtime,dict) and runtime.get('Runtime') == 'MATLAB' and runtime.get('DefaultBackend') == 'portable'
            and all(isinstance(runtime.get(k),str) and runtime[k] for k in ('Version','Release')),
            'Missing portable MATLAB runtime/release')
    require(metadata.get('SourceCommit') == t7.PIN and metadata.get('MATLABExecuted') is True and
            metadata.get('NativeExecuted') is False and metadata.get('FullAcceptanceGateExecuted') is True and
            metadata.get('AcceptanceEstablished') is False and metadata.get('NumericalParityEstablished') is False and
            metadata.get('CompletedCaseCount') == 2 and metadata.get('CampusStructuralChecksPassed') is True,
            'Runtime/scope/full-gate claims mismatch')
    require(t17.timestamp(metadata.get('StartedUTC'),'start') <= t17.timestamp(metadata.get('CompletedUTC'),'completion'),
            'Completion precedes start')
    require(metadata.get('EvidenceArchive') == 't19.zip','Return archive identity mismatch')
    return runtime


def verify_stage(root,phase,entry,metadata,source,references,runtime):
    require(entry.get('Phase') == phase and entry.get('File') == f'{phase}/receipt.json','Stage receipt path/phase mismatch')
    directory = root/phase; path = directory/'receipt.json'; digest = sha256(path)
    require(entry.get('SHA256') == digest == (directory/'receipt.sha256').read_text().strip(),'Stage receipt hash mismatch')
    receipt = json_object(path)
    require(receipt.get('schema') == 'csr-tranche19-stage-receipt-v1' and receipt.get('phase') == phase
            and receipt.get('status') == 'completed','Stage incomplete or wrong identity')
    identity = receipt.get('identity',{})
    require(isinstance(identity,dict) and identity.get('CandidateSHA256') == metadata['CandidateSHA256']
            and identity.get('SourceCommit') == t7.PIN and identity.get('Runtime') == runtime
            and t17.source_map(identity.get('SourceFiles'),'stage sources') == source
            and record_map(identity.get('ReferenceFiles'),'stage references',sizes=True) == references,
            'Stage source/reference/candidate/runtime mismatch')
    require(receipt.get('SourceFilesStableDuringRun') is True and receipt.get('ReferenceFilesStableDuringRun') is True
            and t17.source_map(receipt.get('SourceFilesFinal'),'stage final sources') == source
            and record_map(receipt.get('ReferenceFilesFinal'),'stage final references',sizes=True) == references,
            'Stage source/reference stability unproven')
    started = json_object(directory/'start.json')
    require(started.get('schema') == 'csr-tranche19-stage-start-v1' and started.get('phase') == phase
            and started.get('status') == 'started' and started.get('identity') == identity,
            'Stage start identity/status mismatch')
    require(t17.timestamp(started.get('started_utc'),'stage start') <= t17.timestamp(receipt.get('completed_utc'),'stage completion')
            <= t17.timestamp(metadata['CompletedUTC'],'finalize'),'Stage timing inconsistent')
    inventory(directory,receipt.get('artifacts'),phase+' artifacts',excluded=('receipt.json','receipt.sha256'),
              local=receipt.get('local_artifacts',[]))
    summary = json_object(directory/'summary.json')
    require(receipt.get('summary') == summary,'Stage receipt summary content mismatch')
    return summary


def verify_tests(root,metadata,source_root,candidate,summary):
    require(summary.get('Schema') == 'csr-tranche19-portable-tests-summary-v1','Unexpected portable test summary schema')
    translated = dict(summary,Schema='csr-tranche17-portable-tests-summary-v1')
    return t17.verify_tests(root,metadata,source_root,candidate,translated)


def verify_configuration(config,baseline,case,source_root):
    actual = copy.deepcopy(config)
    require(actual.get('Hop',{}).pop('DataQueuedRetryPolicy',None) == case['policy'],'Actual DATA retry policy differs from case')
    return retained.same_configuration(baseline,actual,source_root,case)


def verify_default_regression(directory,baseline_archive):
    with zipfile.ZipFile(baseline_archive) as archive:
        old = json.loads(archive.read('campus/c/raw/summary.json'))
        new = json_object(directory/'raw/summary.json')
        require(new['Statistics'] == old['Statistics'],'Default case statistics differ from accepted T17')
        hashes = []
        for name in CORE_CSV:
            digest = hashlib.sha256(archive.read('campus/c/raw/'+name)).hexdigest()
            require(sha256(directory/'raw'/name) == digest,'Default case original CSV differs from accepted T17: '+name)
            hashes.append({'path':'raw/'+name,'sha256':digest})
    return {'statistics_equal':True,'raw_csv_bytes_equal':True,'files':hashes,'baseline_owner_sha256':T17_OWNER_SHA}


def verify_case(root,entry,case,summary,source_root,source,runtime,source_hash,baseline_config):
    key = case['case_id']; directory = root/key
    require(entry.get('CaseId') == key and entry.get('Directory') == key and
            entry.get('ManifestSHA256') == sha256(directory/'case.json') and summary.get('Case') == entry,
            'Case path/manifest/summary binding mismatch')
    manifest = json_object(directory/'case.json')
    require(manifest.get('schema') == 'csr-tranche19-queued-retry-case-v1' and manifest.get('status') == 'completed'
            and manifest.get('case_id') == key and manifest.get('policy') == case['policy']
            and manifest.get('case') == case and manifest.get('original_case_id') == 'campus_multihop_6000',
            'Case manifest identity mismatch')
    for field in ('scenario','scenario_sha256','seed','duration_s','bucket_width_s','reference_directory'):
        require(manifest.get(field) == case[field],'Case plan/manifest mismatch: '+field)
    require(manifest.get('runtime') == runtime and manifest.get('matlab_version') == runtime['Version']
            and manifest.get('matlab_release') == runtime['Release'] and manifest.get('ns3_source_commit') == t7.PIN
            and manifest.get('source_snapshot_sha256') == source_hash
            and t17.source_map(manifest.get('source_files'),'case sources') == source,'Case runtime/source binding mismatch')
    require(manifest.get('scheduler_stop_s') == 6000 and manifest.get('mode') == 'continuous'
            and all(manifest.get(k) is True for k in ('structural_checks_passed','admission_counts_complete','original_admission_trace_prefix'))
            and all(manifest.get(k) is False for k in ('observer_enabled','post_horizon_drain','numerical_parity_established')),
            'Case completion/observation scope mismatch')
    inventory(directory,manifest.get('files'),'case files',excluded=('start.json','case.json','summary.json','receipt.json','receipt.sha256'),
              local=manifest.get('local_files',[]))
    raw_manifest = json_object(directory/'raw/case_manifest.json')
    require(raw_manifest.get('schema') == 'csr-matlab-research-case-v1' and raw_manifest.get('status') == 'completed'
            and all(raw_manifest.get(k) is True for k in ('execution_completed','structural_checks_passed','source_files_stable'))
            and raw_manifest.get('ns3_source_commit') == t7.PIN and raw_manifest.get('matlab_version') == runtime['Version']
            and raw_manifest.get('matlab_release') == runtime['Release']
            and t17.source_map(raw_manifest.get('source_files'),'raw source') == source,'Raw case completion/source mismatch')
    inventory(directory/'raw',raw_manifest.get('files'),'raw files',excluded=('case_manifest.json',),local=raw_manifest.get('local_files',[]))
    require(raw_manifest.get('scenario_sha256') == sha256(directory/'raw/scenario.csv') == case['scenario_sha256'],
            'Raw original scenario mismatch')
    raw = json_object(directory/'raw/summary.json'); config,stats,md = raw['Config'],raw['Statistics'],raw['Metadata']
    configuration = verify_configuration(config,baseline_config,case,source_root)
    require(md.get('Runtime') == 'MATLAB' and md.get('Version') == runtime['Version'] and md.get('Release') == runtime['Release']
            and md.get('SourceCommit') == t7.PIN and md.get('Backend') == 'portable' and md.get('ChannelModel') == 'csr-phy'
            and md.get('ModelStage') == 'tranche-3-autonomous-network-routing' and manifest.get('result_metadata') == md
            and not any(k in raw for k in ('TransportTiming','ServiceDiagnostics','LinkDiagnostics')),
            'Unexpected runtime/controlled or instrumented PHY/configuration')
    require(sha256(directory/'raw/trace.csv') == sha256(directory/'raw/protocol_trace.csv'),'Protocol trace copies disagree')
    require(all(integer(stats.get(k),k) == 0 for k in ('OmittedTraceRecords','OmittedPhyTraceRecords')),
            'Protocol or PHY trace truncated')
    legacy_config = copy.deepcopy(config)
    legacy_config['Hop'].pop('DataQueuedRetryPolicy')
    t7.verify_config(directory,legacy_config)
    counts = t7.count_balance(stats,key)
    performance_rows = list(metrics.rows(directory/'analysis/performance_summary.csv'))
    require(len(performance_rows) == 1,'Missing/duplicate performance summary')
    performance = performance_rows[0]
    parsed = sweep.metrics(performance)
    require(all(parsed[k] == counts[k] for k in t7.COUNTS),'Performance/raw outcome mismatch')
    admission = t7.verify_admission(directory,config,stats)
    require(admission['attempts'] == 1710000 and admission['trace_records'] == 100000
            and admission['omitted_trace_records'] == 1610000
            and integer(manifest.get('admission_trace_omitted_records'),'manifest omissions') == 1610000,
            'Historical admission-prefix exact accounting mismatch')
    expected_summary = {'Schema':'csr-tranche19-queued-retry-summary-v1','CaseId':key,'Policy':case['policy'],
        'OriginalBenchmarkCaseId':'campus_multihop_6000','CompletedCaseCount':1,'DurationSeconds':6000,'SchedulerStopSeconds':6000,
        'Seed':128,'RequestedPolicySameAsDefault':case['policy']=='actual-tx'}
    expected_summary.update(dict.fromkeys(('StructuralChecksPassed','DefaultContinuousTiming','RealPHY','AutonomousRouting','OriginalAdmissionTracePrefix'),True))
    expected_summary.update(dict.fromkeys(('ObserverEnabled','PostHorizonDrain','AcceptanceEstablished','NumericalParityEstablished','FiniteStopPendingIsFailure'),False))
    require(all(summary.get(k) == v for k,v in expected_summary.items()) and summary.get('ProtocolTraceOmissions') == 0
            and summary.get('PhyTraceOmissions') == 0,'Case stage summary completion/scope mismatch')
    number(summary.get('ElapsedWallSeconds'),'elapsed wall seconds',minimum=0)
    t17.verify_campus_summary(summary,performance,admission)
    benchmark = list(metrics.rows(directory/'benchmark_summary.csv',('CaseId','Policy',*t7.COUNTS,'Attempts','AdmissionBlocked')))
    require(len(benchmark) == 1 and benchmark[0]['CaseId'] == key and benchmark[0]['Policy'] == case['policy']
            and t7.count_balance(benchmark[0],key) == counts and integer(benchmark[0]['Attempts'],'attempts') == admission['attempts']
            and integer(benchmark[0]['AdmissionBlocked'],'blocked') == admission['blocked'],'Case benchmark summary mismatch')
    node_counts = t17.verify_node_metrics(directory,config,performance)
    physical = t17.verify_phy(directory,config,stats,performance)
    provenance = json_object(directory/'analysis/aggregate_provenance.json')
    require(provenance.get('source_snapshot_sha256') == source_hash and provenance.get('source_file') == 'raw/protocol_trace.csv'
            and provenance.get('source_file_sha256') == sha256(directory/'raw/protocol_trace.csv'),'Aggregate source/trace binding mismatch')
    observations = metrics.analyze_case(directory,case)
    require(all(observations['totals'][field] == counts[counter] for field,counter in
                (('admitted','Generated'),('delivered','Received'),('dropped','Dropped'),('pending','Pending')))
            and observations['totals']['attempts'] == admission['attempts']
            and observations['totals']['blocked'] == admission['blocked'],
            'Reconstructed metrics disagree with complete raw accounting')
    return {'case_id':key,'policy':case['policy'],'counts':counts,'admission':admission,
        'configuration':configuration,'physical_trace':physical,'node_counts':node_counts,
        'elapsed_wall_seconds':float(summary['ElapsedWallSeconds']),'observations':observations}


def compare_aggregates(directory,reference,campus,output):
    """Use verified T19 identity with the established bound aggregate comparator.

    The T7 adapter requires a historical benchmark_manifest.json; T19 has a
    different case manifest. Build a dedicated input manifest without changing
    owner bytes or synthesizing a historical execution manifest.
    """
    directory,reference,output = Path(directory),Path(reference),Path(output)
    case_manifest = json_object(directory/'case.json')
    require(case_manifest.get('schema') == 'csr-tranche19-queued-retry-case-v1' and
            case_manifest.get('original_case_id') == campus['case_id'],'Aggregate T19 case identity mismatch')
    manifest = {'schema':aggregate.INPUT_SCHEMA,**{key:campus[key] for key in
        ('scenario','scenario_sha256','profile_id','duration_s','bucket_width_s')},'inputs':[]}
    duration,width,count = aggregate._window(campus)
    for source in ('matlab','ns3','opnet'):
        path = directory/'analysis/aggregates.csv' if source == 'matlab' else reference/f'{source}-aggregates.csv'
        side = directory/'analysis/aggregate_provenance.json' if source == 'matlab' else reference/f'{source}-benchmark.provenance.json'
        provenance = json_object(side)
        aggregate._check_provenance(provenance,manifest,source,sha256(path),duration,width,count)
        if source == 'matlab':
            require(provenance.get('source_file_sha256') == sha256(directory/'raw/protocol_trace.csv') and
                    provenance.get('source_snapshot_sha256') == case_manifest.get('source_snapshot_sha256'),
                    'Aggregate MATLAB trace/source binding mismatch')
        else:
            upstream = provenance.get('upstream_provenance',{})
            require(sha256(safe_path(reference,upstream.get('path'))) == upstream.get('sha256'),
                    'Native/OPNET upstream aggregate provenance changed')
        item = {'source':source,'aggregate_file':str(path.resolve()),'aggregate_sha256':sha256(path),
                'provenance_file':str(side.resolve()),'provenance_sha256':sha256(side)}
        if source != 'matlab': item['excluded_statistics'] = provenance.get('excluded_extra_statistics',[])
        manifest['inputs'].append(item)
    manifest['case_binding'] = {'t19_manifest_file':str((directory/'case.json').resolve()),
        't19_manifest_sha256':sha256(directory/'case.json'),'reference_manifest_sha256':sha256(reference/'manifest.json'),
        'original_case_id':campus['case_id'],'case_id':case_manifest['case_id'],'policy':case_manifest['policy'],
        'scope':'The enclosing T19 checker verifies all case/raw/reference inventories, exact policy-only configuration and application accounting.'}
    output.mkdir(parents=True,exist_ok=True)
    path = output/'comparison-input.json'
    require(not path.exists(),'Aggregate review output already exists')
    path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    report = aggregate.compare_manifest(path)
    aggregate.write_report(report,output)
    return report


def review(evidence,source_root,output):
    evidence,source_root,output = t17.output_location(evidence,source_root,output)
    prepared = verify_preparation(source_root); candidate = json_object(source_root/CANDIDATE)
    with t17.evidence_directory(evidence) as root:
        require(evidence.is_dir() or not (root/'t19.zip').exists(),'Unexpected nested return archive')
        metadata = json_object(root/'metadata.json'); runtime = verify_identity(root,metadata,source_root,candidate)
        inventory(root,metadata.get('Artifacts'),'outer artifacts',excluded=('metadata.json','t19.zip'),local=metadata.get('LocalArtifacts',[]))
        source_report = verify_sources(root,metadata,source_root)
        references = t17.verify_references(root,metadata,prepared['references'])
        baseline = verify_baseline(source_root,candidate,metadata)
        stage_entries = records(metadata.get('StageReceipts'),'stage receipts')
        require(len(stage_entries) == 3 and {r.get('Phase') for r in stage_entries} == set(PHASES),'Missing/duplicate stage receipts')
        summaries = {entry['Phase']:verify_stage(root,entry['Phase'],entry,metadata,prepared['source'],prepared['references'],runtime)
                     for entry in stage_entries}
        tests = verify_tests(root,metadata,source_root,candidate,summaries['tests'])
        cases = records(metadata.get('Cases'),'completed cases')
        require(len(cases) == 2 and {r.get('CaseId') for r in cases} == {'a128','p128'},'Missing/duplicate completed policy cases')
        cases = {r['CaseId']:r for r in cases}
        with zipfile.ZipFile(source_root/'evidence/t17/owner.zip') as archive:
            baseline_config = json.loads(archive.read('campus/c/raw/summary.json'))['Config']
        observations = {}
        for case in prepared['plan']['cases']:
            key = case['case_id']
            observations[key] = verify_case(root,cases[key],case,summaries[key],source_root,prepared['source'],runtime,
                                             sha256(root/'source.json'),baseline_config)
        default_regression = verify_default_regression(root/'a128',source_root/'evidence/t17/owner.zip')
        comparisons = metrics.compare_cases(observations['a128']['observations'],observations['p128']['observations'],
                                             prepared['native_application_reference'],prepared['plan']['comparison_band_percent'])
        aggregate_comparisons = {}
        for key in ('a128','p128'):
            aggregate_comparisons[key] = compare_aggregates(root/key,source_root/NATIVE,prepared['campus'],output/key/'aggregates')
            a = aggregate_comparisons[key]
            require(set(a['inputs']) == {'matlab','ns3','opnet'} and a['duration_s'] == 6000 and
                    a['bucket_width_s'] == 60 and a['bucket_count'] == 100,'Historical aggregate comparison scope changed')
        result = {'schema':REVIEW_SCHEMA,'status':'structural_review_completed','evidence_integrity_verified':True,
            'full_structural_gate_completed':True,'acceptance_established':False,'numerical_parity_established':False,
            'matlab_executed_by_reviewer':False,'runtime':runtime,'source':source_report,'baseline':baseline,
            'references':references,'tests':tests,'cases':observations,'default_regression':default_regression,
            'native_application_reference':prepared['native_application_reference'],'comparisons':comparisons,
            'aggregate_comparisons':aggregate_comparisons,'metadata_sha256':sha256(root/'metadata.json'),'limitations':LIMITATIONS}
    output.mkdir(parents=True,exist_ok=True)
    (output/'review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        t17.output_location(args.evidence,args.source_root,args.output)
    except ValueError as exc:
        print('T19 review output rejected without modifying inputs: '+str(exc)); return 1
    try:
        result = review(args.evidence,args.source_root,args.output)
    except (ValueError,OSError,csv.Error,zipfile.BadZipFile,KeyError,TypeError,AttributeError,OverflowError,StopIteration) as exc:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'review.json').write_text(json.dumps({'schema':REVIEW_SCHEMA,'status':'review_failed',
            'evidence_integrity_verified':False,'full_structural_gate_completed':False,'acceptance_established':False,
            'numerical_parity_established':False,'matlab_executed_by_reviewer':False,'error':str(exc)},indent=2)+'\n')
        print('T19 evidence rejected: '+str(exc)); return 1
    print(f"T19 review completed: {result['tests']['count']} portable tests, two full-campus policy cases; numerical residuals descriptive.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
