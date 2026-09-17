#!/usr/bin/env python3
"""Review complete T20 full-campus multi-seed evidence without executing MATLAB.

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
import tranche20_metrics as multi

integer = metrics.integer
SCHEMA = 'csr-matlab-tranche-20-validation-v1'
REVIEW_SCHEMA = 'csr-matlab-tranche-20-return-review-v1'
CANDIDATE = 'evidence/tranche-20-candidate.json'
BASELINE = 'evidence/tranche-20-baseline.json'
BASELINE_SHA = '2c8565557d765dd580deccbc92f1b164f607f62fd75a4d703f39661c60578e74'
PARENT_OWNER_SHA = '525758669b8f84fa5dada46e293b8482980ef389efc5408ff056aac0e804ee30'
PARENT_CANDIDATE_SHA = '37b87a253a217824b0160f14b23f2b498e9df7a99cdc46648f3d9785a2fda777'
PARENT_ACCEPTANCE_SHA = 'a0f2bcce6c8cc3d05b05bedbd80fc4426bcfbf2c505f0d0ac07d751573aba2f8'
PLAN = 'scenarios/t20/plan.json'
NATIVE = 'evidence/tranche-7-ns3-reference/campus_multihop_6000'
PHASES = ('tests','s129','s130')
CORE_CSV = ('trace.csv','protocol_trace.csv','phy_trace.csv','nodes.csv','mac_nodes.csv','hop_nodes.csv',
    'nwk_nodes.csv','neighbors.csv','routes.csv','application_admission_statistics.csv','application_admission_trace.csv','scenario.csv')
LIMITATIONS = [
    'Hashes bind evidence claims; they do not independently prove MATLAB execution.',
    'Three full-campus seeds provide a descriptive sample, not statistical equivalence or confidence intervals.',
    'Seed128 retains its accepted T19 source identity; only seeds129 and130 execute under T20.',
    'Engine random streams are not common random numbers. A seed label is not packet-level pairing.',
    'The first100000 attempt records are retained; complete counters cover1710000 attempts.',
    'Native unmatched sends do not separate dropped and pending applications.',
    'The5% band is descriptive, never a structural acceptance gate. OPNET has no matched additional seeds.'
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
            'Accepted T19 source snapshot mismatch')
    baseline = record_map(json_value(source_root/BASELINE),'T19 baseline')
    require(len(baseline) == 358 and sum(n.endswith('.m') for n in baseline) == 170,
            'T19 baseline membership mismatch')
    require(candidate.get('AllowedModifiedSourceFiles') == [], 'T20 permits no baseline changes')
    for name,row in baseline.items():
        require(sha256(safe_path(source_root,name)) == row['sha256'],'Accepted source changed: '+name)
    require(candidate.get('BaselineSourceFiles') == 358 and candidate.get('BaselineMatlabFiles') == 170,
            'Baseline counts disagree')
    parent_dir = source_root/'evidence/t19'
    require(sha256(parent_dir/'owner.zip') == PARENT_OWNER_SHA and
            sha256(parent_dir/'candidate.json') == PARENT_CANDIDATE_SHA and
            sha256(parent_dir/'acceptance.json') == PARENT_ACCEPTANCE_SHA, 'Parent identities changed')
    acceptance = json_object(parent_dir/'acceptance.json')
    require(acceptance.get('status') == 'accepted_for_portable_regression_and_policy_experiment' and
            acceptance.get('owner_evidence_sha256') == PARENT_OWNER_SHA and
            acceptance.get('candidate_sha256') == PARENT_CANDIDATE_SHA and
            acceptance.get('source_snapshot_sha256') == BASELINE_SHA and
            acceptance.get('default_policy') == 'actual-tx' and acceptance.get('experimental_policy_promoted') is False,
            'Accepted parent provenance mismatch')
    with zipfile.ZipFile(parent_dir/'owner.zip') as archive:
        parent = json.loads(archive.read('metadata.json'))
        require(parent.get('Status') == 'completed-review-required' and parent.get('TestsPassed') is True and
                parent.get('Runtime') == acceptance['runtime'] and parent.get('CandidateSHA256') == PARENT_CANDIDATE_SHA and
                hashlib.sha256(archive.read('source.json')).hexdigest() == BASELINE_SHA,
                'Parent not bound to completed T19 return')
    if metadata is not None:
        require(metadata.get('AllBaselineSourcesUnchanged') is True and
                metadata.get('BaselineSourceFilesVerified') == 358 and metadata.get('BaselineMatlabFilesVerified') == 170,
                'Returned baseline preservation claims disagree')
    return {'source_files':358,'matlab_files':170,'source_snapshot_sha256':BASELINE_SHA,
            'all_baseline_sources_unchanged':True,'runtime':acceptance['runtime']}


def verify_plan(source_root,candidate):
    require(candidate.get('Plan') == PLAN and candidate.get('PlanSHA256') == sha256(source_root/PLAN),'Plan binding mismatch')
    plan=json_object(source_root/PLAN)
    required={'tranche':20,'execution_order':['s129','s130'],'comparison_seeds':[128,129,130],
        'planned_simulated_seconds':12000,'comparison_band_percent':5,'timeline_bucket_width_s':300,
        'duration_s':6000,'expected_admission_attempts':1710000,'timing_policy':'continuous',
        'full_portable_regression':True,'seed_override_after_import':True}
    require(all(plan.get(k)==v for k,v in required.items()),'T20 plan scope mismatch')
    for flag in ('default_policy_changed','phy_ecc_changed','observer_enabled','post_horizon_drain','numerical_parity_required','common_random_numbers_claimed'):
        require(plan.get(flag) is False,'Unsupported plan behavior: '+flag)
    require(plan.get('ns3_source_commit')==t7.PIN and plan.get('engine_commit')==multi.ENGINE and
        plan.get('runtime_must_equal_parent') is True and plan.get('fresh_seeds')==[129,130], 'Plan pin/runtime/seeds mismatch')
    catalog=json_object(source_root/'scenarios/benchmarks/catalog.json')
    campus=[c for c in records(catalog['cases'],'catalog') if c['case_id']=='campus_multihop_6000'][0]
    require(plan['scenario_file']==campus['scenario_file'] and plan['scenario_sha256']==campus['scenario_sha256']==sha256(source_root/campus['scenario_file']), 'Original campus changed')
    cases=records(plan['cases'],'cases')
    require([c['case_id'] for c in cases]==['s129','s130'],'Wrong fresh cases')
    for case,seed in zip(cases,(129,130)):
        require(case['seed']==seed and case['policy']=='actual-tx' and case['reference_directory']==f'evidence/tranche-20-ns3-reference/s{seed}' and
            all(case[k]==campus[k] for k in ('scenario','scenario_file','scenario_sha256','duration_s','bucket_width_s')),'Case changed beyond seed')
    return plan,campus


def verify_references(source_root,candidate):
    names = candidate.get('ReferenceFiles')
    require(candidate.get('ReferenceRoots') == [] and isinstance(names,list) and names == sorted(set(names)) and names,
            'Expected sorted explicit reference inventory')
    bindings = record_map(candidate.get('ReferenceFileInventory'),'references',sizes=True)
    require(set(bindings) == set(names),'Reference membership mismatch')
    required = {BASELINE,'evidence/t19/owner.zip','evidence/t19/candidate.json','evidence/t19/acceptance.json'}
    for tree in ('evidence/tranche-7-ns3-reference','evidence/tranche-7-benchmark-inputs','evidence/tranche-20-ns3-reference'):
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
    require(candidate.get('Schema') == 'csr-tranche-20-candidate-v1' and candidate.get('Tranche') == 20
            and candidate.get('SourceCommit') == t7.PIN and candidate.get('EngineCommit') == multi.ENGINE,'Candidate identity/source pin mismatch')
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
    native = {128:metrics.native_applications(source_root/NATIVE)}
    for row in [native[128]['totals'],*native[128]['flows']]:
        row.update(unique_delivered=row['delivered'],delivery_events=row['delivered'],duplicate_delivery_events=0)
    native[128]['scope'] += ' The strict retained parser rejects any duplicate delivery, so event and unique counts agree for seed128.'
    for seed in (129,130):
        native[seed] = multi.verify_native(source_root,seed)
    return {'source':source,'references':references,'baseline':baseline,'plan':plan,'campus':campus,
        'planned_matlab_tests':len(names),'planned_cases':2,'native_application_reference':native,
        'matlab_executed':False}


def verify_identity(root,metadata,source_root,candidate):
    require(metadata.get('Schema') == SCHEMA and metadata.get('Tranche') == 20 and
            metadata.get('Status') == 'completed-review-required','Return is not finalized complete T20 evidence')
    require(metadata.get('CandidateFile') == CANDIDATE and metadata.get('CandidateSHA256') == sha256(source_root/CANDIDATE)
            == sha256(root/'candidate.json') and sha256(root/'plan.json') == candidate['PlanSHA256'],
            'Returned candidate/plan binding mismatch')
    runtime = metadata.get('Runtime')
    require(runtime == json_object(source_root/'evidence/t19/acceptance.json')['runtime'], 'Runtime differs from reused seed128')
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
    expected_reused={'CaseId':'a128','Seed':128,'Policy':'actual-tx','OwnerFile':'evidence/t19/owner.zip',
        'OwnerSHA256':PARENT_OWNER_SHA,'CandidateFile':'evidence/t19/candidate.json','CandidateSHA256':PARENT_CANDIDATE_SHA,
        'AcceptanceFile':'evidence/t19/acceptance.json','AcceptanceSHA256':PARENT_ACCEPTANCE_SHA,
        'SourceSnapshotSHA256':BASELINE_SHA,'Runtime':runtime,'FreshlyExecuted':False}
    require(metadata.get('ReusedBaseline')==expected_reused and metadata.get('ReusedCaseCount')==1 and
        metadata.get('ReusedSeeds')==128 and metadata.get('ComparisonSeeds')==[128,129,130] and
        metadata.get('SingleSeedScope') is False,'Reused seed identity/scope mismatch')
    require(metadata.get('EvidenceArchive') == 't20.zip','Return archive identity mismatch')
    return runtime


def verify_stage(root,phase,entry,metadata,source,references,runtime):
    require(entry.get('Phase') == phase and entry.get('File') == f'{phase}/receipt.json','Stage receipt path/phase mismatch')
    directory = root/phase; path = directory/'receipt.json'; digest = sha256(path)
    require(entry.get('SHA256') == digest == (directory/'receipt.sha256').read_text().strip(),'Stage receipt hash mismatch')
    receipt = json_object(path)
    require(receipt.get('schema') == 'csr-tranche20-stage-receipt-v1' and receipt.get('phase') == phase
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
    require(started.get('schema') == 'csr-tranche20-stage-start-v1' and started.get('phase') == phase
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
    require(summary.get('Schema') == 'csr-tranche20-portable-tests-summary-v1','Unexpected portable test summary schema')
    translated = dict(summary,Schema='csr-tranche17-portable-tests-summary-v1')
    return t17.verify_tests(root,metadata,source_root,candidate,translated)


def verify_configuration(config,baseline,case,source_root):
    actual=copy.deepcopy(config)
    require(actual.get('Hop',{}).get('DataQueuedRetryPolicy') == case['policy'] == 'actual-tx','Default DATA policy changed')
    require(actual.get('Seed') == case['seed'] and baseline.get('Seed') == 128,'Case seed override mismatch')
    actual['Seed']=128
    result=retained.same_configuration(baseline,actual,source_root,case)
    result['seed_override']={'before':128,'after':case['seed']}
    return result


def verify_case(root,entry,case,summary,source_root,source,runtime,source_hash,baseline_config):
    key = case['case_id']; directory = root/key
    require(entry.get('CaseId') == key and entry.get('Directory') == key and
            entry.get('ManifestSHA256') == sha256(directory/'case.json') and summary.get('Case') == entry,
            'Case path/manifest/summary binding mismatch')
    manifest = json_object(directory/'case.json')
    require(manifest.get('schema') == 'csr-tranche20-multi-seed-case-v1' and manifest.get('status') == 'completed'
            and manifest.get('case_id') == key and manifest.get('policy') == case['policy']
            and manifest.get('case') == case and manifest.get('original_case_id') == 'campus_multihop_6000',
            'Case manifest identity mismatch')
    require(manifest.get('opnet_same_seed_reference_available') is False and
        manifest.get('opnet_scope')=='archived-seed128-aggregate-context-only', 'Unsupported OPNET seed comparison')
    for field in ('scenario','scenario_sha256','seed','duration_s','bucket_width_s','reference_directory'):
        require(manifest.get(field) == case[field],'Case plan/manifest mismatch: '+field)
    require(manifest.get('runtime') == runtime and manifest.get('matlab_version') == runtime['Version']
            and manifest.get('matlab_release') == runtime['Release'] and manifest.get('ns3_source_commit') == t7.PIN
            and manifest.get('source_snapshot_sha256') == source_hash
            and t17.source_map(manifest.get('source_files'),'case sources') == source,'Case runtime/source binding mismatch')
    require(manifest.get('seed_override_after_import') is True and manifest.get('imported_seed') == 128, 'Seed override provenance missing')
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
    require(raw_manifest.get('imported_seed')==128 and raw_manifest.get('seed_override_after_import') is True,
        'Raw seed override provenance missing')
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
    expected_summary = {'Schema':'csr-tranche20-multi-seed-summary-v1','CaseId':key,'Policy':case['policy'],
        'OriginalBenchmarkCaseId':'campus_multihop_6000','CompletedCaseCount':1,'DurationSeconds':6000,'SchedulerStopSeconds':6000,
        'Seed':case['seed'],'ImportedSeed':128,'SeedOverrideAfterImport':True,'RequestedPolicySameAsDefault':case['policy']=='actual-tx'}
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
    observations = multi.analyze_case(directory,case)
    require(all(observations['totals'][field] == counts[counter] for field,counter in
                (('admitted','Generated'),('delivered','Received'),('dropped','Dropped'),('pending','Pending')))
            and observations['totals']['attempts'] == admission['attempts']
            and observations['totals']['blocked'] == admission['blocked'],
            'Reconstructed metrics disagree with complete raw accounting')
    return {'case_id':key,'policy':case['policy'],'counts':counts,'admission':admission,
        'configuration':configuration,'physical_trace':physical,'node_counts':node_counts,
        'elapsed_wall_seconds':float(summary['ElapsedWallSeconds']),'observations':observations}



def compare_seed_aggregates(directory,reference,campus,seed):
    """Validate each engine's real input hash, then align event-rate buckets."""
    observations={}; inputs={}
    for engine in ('matlab','ns3'):
        path=directory/'analysis/aggregates.csv' if engine=='matlab' else reference/'ns3-aggregates.csv'
        side=directory/'analysis/aggregate_provenance.json' if engine=='matlab' else reference/'ns3-benchmark.provenance.json'
        provenance=json_object(side)
        descriptor={k:campus[k] for k in ('scenario','scenario_sha256','profile_id','duration_s','bucket_width_s')}
        if engine=='ns3' and seed!=128:
            descriptor['scenario_sha256']=sha256(reference/'scenario.csv')
        trace_hash=aggregate._check_provenance(provenance,descriptor,engine,sha256(path),6000,60,100)
        observations[engine],excluded=aggregate.read_series(path,engine,campus['scenario'],trace_hash,60,100,provenance.get('excluded_extra_statistics',[]))
        inputs[engine]={'scenario_sha256':descriptor['scenario_sha256'],'aggregate_sha256':sha256(path),'provenance_sha256':sha256(side),'excluded':excluded}
        if engine=='matlab':
            require(trace_hash==sha256(directory/'raw/protocol_trace.csv'),'MATLAB aggregate trace hash mismatch')
        else:
            upstream=provenance.get('upstream_provenance',{})
            require(sha256(safe_path(reference,upstream.get('path')))==upstream.get('sha256'),'Native aggregate upstream mismatch')
    comparison,points=aggregate._compare_pair('matlab','ns3',observations,60,100)
    return {'seed':seed,'inputs':inputs,'comparison':comparison,'points':points,
        'scope':'Event-based aggregate rates and bucket means, separate from unique delivered application counts. Native seed-only input mapping verified independently.',
        'numeric_tolerance_gate_applied':False}


def review(evidence,source_root,output):
    evidence,source_root,output = t17.output_location(evidence,source_root,output)
    prepared = verify_preparation(source_root); candidate = json_object(source_root/CANDIDATE)
    with t17.evidence_directory(evidence) as root:
        require(evidence.is_dir() or not (root/'t20.zip').exists(),'Unexpected nested return archive')
        metadata = json_object(root/'metadata.json'); runtime = verify_identity(root,metadata,source_root,candidate)
        inventory(root,metadata.get('Artifacts'),'outer artifacts',excluded=('metadata.json','t20.zip'),local=metadata.get('LocalArtifacts',[]))
        source_report = verify_sources(root,metadata,source_root)
        references = t17.verify_references(root,metadata,prepared['references'])
        baseline = verify_baseline(source_root,candidate,metadata)
        stage_entries = records(metadata.get('StageReceipts'),'stage receipts')
        require(len(stage_entries) == 3 and {r.get('Phase') for r in stage_entries} == set(PHASES),'Missing/duplicate stage receipts')
        summaries = {entry['Phase']:verify_stage(root,entry['Phase'],entry,metadata,prepared['source'],prepared['references'],runtime)
                     for entry in stage_entries}
        tests = verify_tests(root,metadata,source_root,candidate,summaries['tests'])
        cases = records(metadata.get('Cases'),'completed cases')
        require(len(cases) == 2 and {r.get('CaseId') for r in cases} == {'s129','s130'},'Missing/duplicate fresh seed cases')
        cases = {r['CaseId']:r for r in cases}
        with zipfile.ZipFile(source_root/'evidence/t19/owner.zip') as archive:
            baseline_config = json.loads(archive.read('a128/raw/summary.json'))['Config']
        observations = {}; aggregate_comparisons={}
        for case in prepared['plan']['cases']:
            key = case['case_id']
            observations[key] = verify_case(root,cases[key],case,summaries[key],source_root,prepared['source'],runtime,
                                             sha256(root/'source.json'),baseline_config)
        for case in prepared['plan']['cases']:
            aggregate_comparisons[case['seed']]=compare_seed_aggregates(root/case['case_id'],source_root/case['reference_directory'],prepared['campus'],case['seed'])
        with t17.evidence_directory(source_root/'evidence/t19/owner.zip') as parent:
            inherited=json_object(parent/'a128/case.json')['case']
            inherited['policy']='actual-tx'
            old=multi.analyze_case(parent/'a128',inherited)
            aggregate_comparisons[128]=compare_seed_aggregates(parent/'a128',source_root/NATIVE,prepared['campus'],128)
        compared={128:old,129:observations['s129']['observations'],130:observations['s130']['observations']}
        comparisons=multi.compare_seeds(compared,prepared['native_application_reference'],5)
        result = {'schema':REVIEW_SCHEMA,'status':'structural_review_completed','evidence_integrity_verified':True,
            'full_structural_gate_completed':True,'acceptance_established':False,'numerical_parity_established':False,
            'matlab_executed_by_reviewer':False,'runtime':runtime,'source':source_report,'baseline':baseline,
            'references':references,'tests':tests,'cases':observations,'reused_seed128':{'owner_sha256':PARENT_OWNER_SHA,'source_snapshot_sha256':BASELINE_SHA,'case_id':'a128','observations':old},
            'native_application_reference':prepared['native_application_reference'],'comparisons':comparisons,'aggregate_comparisons':aggregate_comparisons,
            'metadata_sha256':sha256(root/'metadata.json'),'limitations':LIMITATIONS}
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
        print('T20 review output rejected without modifying inputs: '+str(exc)); return 1
    try:
        result = review(args.evidence,args.source_root,args.output)
    except (ValueError,OSError,csv.Error,zipfile.BadZipFile,KeyError,TypeError,AttributeError,OverflowError,StopIteration) as exc:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'review.json').write_text(json.dumps({'schema':REVIEW_SCHEMA,'status':'review_failed',
            'evidence_integrity_verified':False,'full_structural_gate_completed':False,'acceptance_established':False,
            'numerical_parity_established':False,'matlab_executed_by_reviewer':False,'error':str(exc)},indent=2)+'\n')
        print('T20 evidence rejected: '+str(exc)); return 1
    print(f"T20 review completed: {result['tests']['count']} portable tests, two fresh full-campus seeds and one archived seed; numerical residuals descriptive.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
