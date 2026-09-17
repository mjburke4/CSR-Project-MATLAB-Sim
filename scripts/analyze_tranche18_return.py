#!/usr/bin/env python3
"""Verify T18 passive relay/local service evidence without running MATLAB.

All previously accepted simulator sources stay unchanged. This reviewer checks
identities, complete observations, observer nonperturbation and original-campus
prefix preservation, then reports cohort and native numerical differences.
Neither a seed label nor a matching aggregate establishes shared RNG or parity.
"""
from __future__ import annotations

import argparse
import copy
import csv
import io
import itertools
import json
from pathlib import Path
import zipfile

from analyze_tranche11_return import (all_files, candidate_snapshot, csv_rows,
    integer, json_object, json_value, logical, record_map, records, require,
    safe_path, selected_test_names, sha256, verify_sources, verify_tests)
import analyze_tranche7_return as t7
import analyze_tranche16_return as t16
import analyze_tranche17_return as t17
import analyze_research_sweep as sweep
import compare_benchmark_aggregates as aggregate
import tranche8_metrics as metrics
import tranche9_metrics as service
import tranche10_metrics as retained

SCHEMA = 'csr-matlab-tranche-18-validation-v1'
REVIEW_SCHEMA = 'csr-matlab-tranche-18-return-review-v1'
CANDIDATE = 'evidence/tranche-18-candidate.json'
BASELINE = 'evidence/tranche-18-baseline.json'
BASELINE_SHA = '5ba7ff4b26a12192496d98cc36ccbcffe77199255da1cbda1025f83a14618891'
OWNER_SHA = '19921afa83c57db2779e4302e5b39afef5120afb129a87fddb1f6d1bdbec2bd1'
PARENT_SHA = '6210329add45cd50c8173e2e1390f2aa157a154c6977a10bee5917ee01a1052c'
PLAN = 'scenarios/t18/plan.json'
REFERENCE = 'evidence/tranche-18-ns3-reference'
CASE_ORDER = tuple(f'{condition}{seed}' for seed in (128,129,130) for condition in 'rlm')+('p128',)
EXECUTION_ORDER = CASE_ORDER[:3]+('m128_off',)+CASE_ORDER[3:]
CHECKS = ('research_accounting','performance_accounting','complete_protocol_trace','complete_phy_trace',
    'complete_admission_trace','observer_feedback_contract','observer_service_contract','cancellation_contract',
    'default_continuous_timing','scenario_identity','completed_horizon','trace_horizon')
CORE_CSV = ('trace.csv','protocol_trace.csv','phy_trace.csv','nodes.csv','mac_nodes.csv',
    'hop_nodes.csv','nwk_nodes.csv','neighbors.csv','routes.csv',
    'application_admission_statistics.csv','application_admission_trace.csv','scenario.csv')
LIMITATIONS = [
    'Owner-returned hashes and internally reconciled observations are not independent proof of MATLAB execution.',
    'Reduced cases remove original campus nodes/interferers; their results are not full-campus or OPNET acceptance.',
    'MATLAB and ns-3 seeds identify separate random streams; per-event identities are never aligned across simulators.',
    'Service records preserve callback order and supplied snapshots, not continuously observed hidden queue state.',
    'DATA and control identifiers occupy separate namespaces; local/relay labels use original application source.',
    'The accepted queued-DATA retry timeout difference remains unchanged; numerical residuals are descriptive.',
    'Finite-stop dropped and pending work remain outcomes. No forced delivery, queue draining or DACK in every case is required.',
    'The original T17 admission trace stops after 100,000 records; later p128 attempts cannot be compared with missing baseline records.',
    'The p128 proof covers protocol/PHY events strictly before 900 seconds; boundary events are separately reported.',
]


def verify_baseline(source_root, candidate, metadata=None):
    require(candidate.get('BaselineSourceSnapshot') == BASELINE
            and candidate.get('BaseSourceSnapshotSHA256') == sha256(source_root/BASELINE) == BASELINE_SHA,
            'T17 source baseline identity mismatch')
    baseline = record_map(json_value(source_root/BASELINE), 'T17 baseline')
    require(len(baseline) == 313 and sum(name.endswith('.m') for name in baseline) == 160,
            'T17 baseline membership changed')
    for name, row in baseline.items():
        require(sha256(safe_path(source_root,name)) == row['sha256'], 'Previously accepted T17 source changed: '+name)
    for key, name, digest in (('BaselineOwnerEvidence','evidence/t17/owner.zip',OWNER_SHA),
                              ('BaselineCandidate','evidence/t17/candidate.json',PARENT_SHA)):
        require(candidate.get(key) == name and candidate.get(key+'SHA256') == sha256(source_root/name) == digest,
                'T17 owner/candidate provenance mismatch')
    with zipfile.ZipFile(source_root/'evidence/t17/owner.zip') as archive:
        parent = json.loads(archive.read('metadata.json'))
        import hashlib
        require(parent.get('Status') == 'completed-review-required' and parent.get('TestsPassed') is True
                and parent.get('FullAcceptanceGateExecuted') is True and parent.get('CandidateSHA256') == PARENT_SHA
                and parent.get('SourceSnapshotSHA256') == hashlib.sha256(archive.read('source.json')).hexdigest() == BASELINE_SHA,
                'Baseline is not bound to completed T17 owner evidence')
    if metadata is not None:
        require(metadata.get('AllBaselineSourcesUnchanged') is True
                and integer(metadata.get('BaselineSourceFilesVerified'),'baseline sources') == 313
                and integer(metadata.get('BaselineMatlabFilesVerified'),'baseline MATLAB') == 160,
                'T17 baseline verification counters disagree')
    return {'source_files':313,'matlab_files':160,'all_unchanged':True,'source_snapshot_sha256':BASELINE_SHA}


def verify_derived_rows(parent, actual, case):
    expected = []
    for item in parent:
        row = dict(item)
        if row['record'] == 'run':
            row.update(scenario=case['scenario'],duration_s=str(float(case['duration_s'])),seed=str(case['seed']))
        elif row['record'] == 'node':
            if integer(row['node_id'],'node') not in case['node_ids']:
                continue
        elif row['record'] == 'flow':
            if integer(row['flow_src'],'flow source') not in case['flow_sources']:
                continue
        else:
            raise ValueError('Unsupported original campus CSV record')
        expected.append(row)
    require(actual == expected, 'Derived scenario changed retained geometry/traffic/profile beyond its declared rows and run overrides')
    require(sum(row['record'] == 'run' for row in actual) == 1, 'Derived run identity missing/duplicated')


def verify_plan(source_root, candidate):
    require(candidate.get('Plan') == PLAN and candidate.get('PlanSHA256') == sha256(source_root/PLAN), 'Plan path/hash mismatch')
    plan = json_object(source_root/PLAN)
    require(plan.get('schema') == 'csr-tranche18-relay-service-plan-v1' and plan.get('tranche') == 18
            and plan.get('ns3_source_commit') == t7.PIN and plan.get('engine_commit') == '6b5cd24ea80713ce16d88575869aedd6f432bdae'
            and plan.get('seeds') == [128,129,130] and plan.get('case_order') == list(CASE_ORDER)
            and plan.get('execution_order') == list(EXECUTION_ORDER) and plan.get('case_count') == 10
            and plan.get('observed_case_count') == 10 and plan.get('execution_count') == 11
            and plan.get('planned_simulated_seconds') == 6900 and plan.get('timing_policy') == 'continuous',
            'T18 plan identity/membership/budget mismatch')
    require(all(plan.get(key) is False for key in ('phy_ecc_changed','production_source_changed','full_portable_regression',
        'full_campus_acceptance','native_tests_included','post_horizon_drain','native_reference_reused','opnet_available','default_policy_changed',
        'finite_stop_pending_is_failure','dack_required_in_every_case','numerical_parity_required','common_random_numbers_claimed'))
        and plan.get('all_protocol_phy_admission_and_observer_traces_complete_required') is True,
        'T18 diagnostic scope or policy changed')
    require(plan.get('control') == {'case_id':'m128_off','base_case_id':'m128','observer_enabled':False,'duration_s':600,
        'configuration_must_match_exactly':True,'core_statistics_and_raw_csvs_must_match':True}, 'Observer control changed')
    parent_path = source_root/'scenarios/benchmarks/campus_multihop_6000.csv'
    require(plan.get('parent_scenario') == 'scenarios/benchmarks/campus_multihop_6000.csv'
            and plan.get('parent_scenario_sha256') == sha256(parent_path), 'Parent campus identity mismatch')
    parent = list(t7.csv_records(parent_path))
    cases = records(plan.get('cases'),'planned cases')
    require([row.get('case_id') for row in cases] == list(CASE_ORDER), 'Missing/duplicate/reordered T18 case')
    for case in cases:
        key = case['case_id']; prefix = key[0] == 'p'
        nodes = [1,2,3,4,5,7,8] if prefix else [1,4,5]
        flows = [2,3,4,5,7,8] if prefix else {'r':[4],'l':[5],'m':[4,5]}[key[0]]
        horizon = 900 if prefix else 600
        limits = {'protocol':1500000,'phy':1500000,'admission':300000} if prefix else {'protocol':300000,'phy':500000,'admission':50000}
        require(case.get('storage_key') == key and case.get('node_ids') == nodes and case.get('flow_sources') == flows
                and case.get('seed') == int(key[1:]) and case.get('duration_s') == horizon
                and case.get('condition') == {'r':'relay_only','l':'local_only','m':'mixed','p':'campus_prefix'}[key[0]]
                and case.get('bucket_width_s') == 60 and case.get('profile_id') == 'hist-adb97c54-bare'
                and case.get('observer_enabled') is True and case.get('observer_max_records') == (400000 if prefix else 100000)
                and case.get('service_window_seconds') == [0,horizon+1] and case.get('trace_limits') == limits
                and case.get('max_events') == 12000000 and case.get('flow_limit') == 0 and case.get('opnet_available') is False
                and case.get('expected_admission_attempts') == len(flows)*int((horizon-300)/.02), 'Case workload/window/budget mismatch: '+key)
        require(case.get('scenario_file') == f'scenarios/t18/inputs/{key}.csv'
                and case.get('recipe_file') == f'scenarios/t18/inputs/{key}.recipe.json'
                and case.get('reference_directory') == f'{REFERENCE}/{key}', 'Case path identity mismatch')
        require(sha256(source_root/case['scenario_file']) == case.get('scenario_sha256')
                and sha256(source_root/case['recipe_file']) == case.get('recipe_sha256'), 'Derived input/recipe hash mismatch')
        recipe = json_object(source_root/case['recipe_file'])
        require(recipe.get('schema') == 'csr-tranche18-scenario-derivation-v1' and recipe.get('case_id') == key
                and recipe.get('parent_scenario') == plan['parent_scenario']
                and recipe.get('parent_scenario_sha256') == plan['parent_scenario_sha256']
                and recipe.get('scenario_file') == case['scenario_file'] and recipe.get('scenario_sha256') == case['scenario_sha256']
                and recipe.get('run_overrides') == {'scenario':case['scenario'],'duration_s':horizon,'seed':case['seed']}
                and recipe.get('retained_node_ids') == nodes and recipe.get('retained_flow_sources') == flows
                and recipe.get('routes') == 'autonomous' and recipe.get('fixed_routes') is False
                and recipe.get('forced_loss') is False, 'Derivation recipe scope mismatch')
        verify_derived_rows(parent,list(t7.csv_records(source_root/case['scenario_file'])),case)
    return plan


def verify_references(source_root, candidate):
    names = candidate.get('ReferenceFiles')
    require(candidate.get('ReferenceRoots') == [] and isinstance(names,list) and names == sorted(set(names)) and names,
            'T18 requires distinct sorted explicit reference membership')
    expected = record_map(candidate.get('ReferenceFileInventory'),'candidate references',sizes=True)
    require(set(names) == set(expected), 'Reference path/inventory membership mismatch')
    required = {BASELINE,'evidence/t17/owner.zip','evidence/t17/candidate.json','evidence/t17/acceptance.json'}
    required.update(f'{REFERENCE}/{name}' for name in all_files(source_root/REFERENCE))
    require(required <= set(expected), 'Required T17/native reference membership missing')
    for name,row in expected.items():
        path = safe_path(source_root,name)
        require(path.is_file() and path.stat().st_size == row['bytes'] and sha256(path) == row['sha256'],
                'Reference hash or size mismatch: '+name)
    return expected


def verify_preparation(source_root):
    source_root = Path(source_root).resolve()
    candidate = json_object(source_root/CANDIDATE)
    require(candidate.get('Schema') == 'csr-tranche-18-candidate-v1' and candidate.get('Tranche') == 18
            and candidate.get('SourceCommit') == t7.PIN, 'T18 candidate identity mismatch')
    source = candidate_snapshot(source_root)
    require(candidate.get('SourceFilesExcludedPaths') == [CANDIDATE]
            and t17.source_map(candidate.get('SourceFiles'),'candidate source') ==
            {name:digest for name,digest in source.items() if name != CANDIDATE}, 'Frozen source membership/hash mismatch')
    names = selected_test_names(source_root,candidate.get('TestFiles'))
    require(candidate.get('ExpectedTestNames') == names and candidate.get('PreflightTestFiles') == ['tests/TestRelayServiceSuite.m']
            and candidate['TestFiles'][0] == 'tests/TestRelayServiceSuite.m', 'Frozen focused/preflight test membership mismatch')
    baseline = verify_baseline(source_root,candidate)
    references = verify_references(source_root,candidate)
    plan = verify_plan(source_root,candidate)
    require(candidate.get('ExpectedStructuralCheckNames') == list(CHECKS)
            and candidate.get('ExpectedStructuralCheckCount') == 132, 'Frozen structural check membership mismatch')
    from run_tranche18_ns3_reference import verify_reference_suite
    native = verify_reference_suite(source_root,plan)
    for case in plan['cases']:
        verify_native_buckets(source_root/case['reference_directory'],case)
    return {'source':source,'references':references,'baseline':baseline,'plan':plan,'native':native,
            'planned_matlab_tests':len(names),'planned_cases':11,'matlab_executed':False}


def verify_identity(root,metadata,source_root,candidate):
    require(metadata.get('Schema') == SCHEMA and metadata.get('Tranche') == 18 and metadata.get('Status') == 'completed',
            'Return is not a completed T18 diagnostic')
    require(metadata.get('CandidateFile') == CANDIDATE and metadata.get('CandidateSHA256') == sha256(source_root/CANDIDATE)
            and sha256(root/'candidate.json') == sha256(source_root/CANDIDATE)
            and sha256(root/'plan.json') == candidate['PlanSHA256'], 'Candidate/plan return binding mismatch')
    runtime = metadata.get('Runtime')
    require(isinstance(runtime,dict) and runtime.get('Runtime') == 'MATLAB' and runtime.get('DefaultBackend') == 'portable'
            and all(isinstance(runtime.get(key),str) and runtime[key] for key in ('Version','Release')),
            'Missing portable MATLAB runtime/release')
    require(metadata.get('MATLABExecuted') is True and metadata.get('NativeExecuted') is False
            and metadata.get('SourceCommit') == t7.PIN and metadata.get('DiagnosticOnly') is True
            and metadata.get('FocusedGateExecuted') is True and all(metadata.get(key) is False for key in
            ('FullAcceptanceGateExecuted','AcceptanceEstablished','NumericalParityEstablished')),
            'Execution/source/scope claims mismatch')
    require(t17.timestamp(metadata.get('StartedUTC'),'start') <= t17.timestamp(metadata.get('CompletedUTC'),'completion'),
            'Invalid owner execution timestamps')
    require(metadata.get('EvidenceArchive') == 't18.zip', 'Archive identity mismatch')
    return runtime


def verify_configuration(config,parent,case,source_root,plan_hash):
    """Exact inherited configuration, with only named diagnostic derivations."""
    expected = copy.deepcopy(parent)
    expected['Name'],expected['DurationSeconds'],expected['Seed'] = case['scenario'],case['duration_s'],case['seed']
    expected['Nodes'] = [row for row in records(parent['Nodes'],'nodes') if row['Id'] in case['node_ids']]
    expected['Traffic'] = [row for row in records(copy.deepcopy(parent['Traffic']),'traffic') if row['SourceId'] in case['flow_sources']]
    for row in expected['Traffic']:
        row['PacketCount'] = t7.possible_attempts(case['duration_s'],row['StartSeconds'],row['IntervalSeconds'],2**53)
    expected['Trace'].update(MaxRecords=case['trace_limits']['protocol'],MaxPhyRecords=case['trace_limits']['phy'],
                              MaxApplicationAdmissionRecords=case['trace_limits']['admission'])
    expected['MaxEvents'] = case['max_events']
    expected['Benchmark'] = {'Schema':'csr-matlab-benchmark-v1','CaseId':case['case_id'],'SourceKind':case['source_kind'],
        'ProfileId':case['profile_id'],'OpnetAvailable':False,'BucketWidthSeconds':case['bucket_width_s'],
        'ReferenceDirectory':case['reference_directory'],'CatalogSHA256':plan_hash,'HistoricalOutcomeEquivalenceEstablished':False}
    actual = copy.deepcopy(config)
    actual['Nodes'] = records(actual.get('Nodes'),'nodes')
    actual['Traffic'] = records(actual.get('Traffic'),'traffic')
    # The importer records canonical run-row provenance; compare every field
    # except relocation and the deliberately changed run identity/hash below.
    shared = actual.get('SharedScenario')
    require(isinstance(shared,dict) and shared.get('SourceSHA256') == case['scenario_sha256'], 'Derived imported source hash mismatch')
    original_shared = expected['SharedScenario']
    original_shared['SourcePath'] = shared.get('SourcePath')
    original_shared['SourceSHA256'] = case['scenario_sha256']
    original_shared['NodeNames'] = [name for node,name in zip(records(parent['Nodes'],'parent nodes'),parent['SharedScenario']['NodeNames'])
                                    if node['Id'] in case['node_ids']]
    original_shared['OriginalNodeApplicationSettings'] = [row for row in records(original_shared['OriginalNodeApplicationSettings'],'original node applications')
                                                        if row['NodeId'] in case['node_ids']]
    original_shared['ConfiguredFlowPacketBytes'] = [row['ApplicationPayloadBytes']+15 for row in expected['Traffic']]
    if not isinstance(shared.get('ConfiguredFlowPacketBytes'),list):
        shared['ConfiguredFlowPacketBytes'] = [shared.get('ConfiguredFlowPacketBytes')]
    require(shared == original_shared, 'Derived import profile/options differ from exact original campus subset')
    require(str(shared.get('SourcePath','')).replace('\\','/').endswith('/'+case['scenario_file'])
            and sha256(source_root/case['scenario_file']) == shared['SourceSHA256'], 'Imported scenario path is not the frozen derived input')
    require(actual == expected, 'Actual protocol/PHY/traffic configuration differs from exact campus derivation')
    return {'original_campus_inheritance_verified':True,'derived_node_ids':case['node_ids'],'derived_flow_sources':case['flow_sources']}


def verify_buckets(directory,case,source_hash,sent,received):
    path = directory/'analysis/aggregates.csv'
    provenance = json_object(directory/'analysis/aggregate_provenance.json')
    count = int(case['duration_s']/case['bucket_width_s'])
    require(provenance.get('source_file') == 'raw/protocol_trace.csv'
            and provenance.get('source_file_sha256') == sha256(directory/'raw/protocol_trace.csv')
            and provenance.get('source_snapshot_sha256') == source_hash, 'Aggregate trace/source binding mismatch')
    aggregate._check_provenance(provenance,case,'matlab',sha256(path),case['duration_s'],case['bucket_width_s'],count)
    # Simulation processes callbacks at the stop; aggregates deliberately use
    # [0, stop). Keep an exactly-at-stop delivery in terminal accounting while
    # excluding it from the bucket reconstruction, just as the exporter does.
    def in_window(when):
        quotient = when/case['bucket_width_s']
        if abs(quotient-round(quotient)) <= 1e-12:
            quotient = round(quotient)
        return 0 <= quotient < count
    metrics.verify_aggregates(path,sent,[row for row in received if in_window(row[1])],case)
    aggregate.read_series(path,'matlab',case['scenario'],provenance['source_file_sha256'],case['bucket_width_s'],count,[])
    return list(metrics.csv_rows(path))


def verify_physical_trace(directory,config,stats,performance):
    """T17 receiver accounting with T18's explicitly closed callback horizon."""
    horizon = config['DurationSeconds']
    nodes = {integer(row['Id'],'node') for row in records(config['Nodes'],'nodes')}
    tx,protocol_count = {},0
    for row in t7.csv_records(directory/'raw/protocol_trace.csv',('TimeSeconds','Event','NodeId','PacketId')):
        protocol_count += 1
        when = sweep.finite(row['TimeSeconds'],'protocol time')
        require(0 <= when <= horizon,'Protocol observation outside closed simulation horizon')
        if row['Event'] != 'tx_start':
            continue
        frame = integer(row['PacketId'],'TX frame',1)
        source = integer(row['NodeId'],'TX source')
        require(frame not in tx and source in nodes,'Duplicate/unknown actual TX identity')
        tx[frame] = source,when
    require(len(tx) == integer(stats['PhysicalTransmissions'],'transmissions') > 0
            and integer(stats['PhysicalAttempts'],'receiver attempts') == len(tx)*(len(nodes)-1),
            'Physical TX/receiver target accounting mismatch')
    starts,ends,previous,count = set(),{},-1.0,0
    for row in t7.csv_records(directory/'raw/phy_trace.csv',('TimeSeconds','Event','PacketId','NodeId','SourceId','Success','Reason')):
        count += 1
        frame,receiver = integer(row['PacketId'],'PHY frame'),integer(row['NodeId'],'receiver')
        require(frame in tx and receiver in nodes and receiver != tx[frame][0]
                and integer(row['SourceId'],'PHY source') == tx[frame][0], 'PHY receiver/frame identity mismatch')
        when = sweep.finite(row['TimeSeconds'],'PHY time')
        require(previous <= when <= horizon and when >= 0 and when+1e-9 >= tx[frame][1], 'PHY callback order/horizon mismatch')
        previous = when; key = frame,receiver
        require(row['Event'] != 'post_phy_drop','Unexpected post-PHY fault injection')
        if row['Event'] == 'phy_signal_start':
            require(key not in starts and key not in ends,'Duplicate/out-of-order PHY start')
            starts.add(key)
        elif row['Event'] == 'phy_signal_end':
            require(key not in ends and (key in starts) == (row['Reason'] != 'closure'),'PHY completion/start coverage mismatch')
            ends[key] = logical(row['Success'],'PHY success')
    received = sum(ends.values())
    require(received == integer(stats['PhysicalReceived'],'physical received')
            and len(ends)-received == integer(stats['PhysicalDropped'],'physical dropped')
            and integer(stats['PhysicalAttempts'],'attempts')-len(ends) == integer(stats['PhysicalPending'],'physical pending'),
            'PHY completion outcomes disagree with counters')
    require(integer(performance['ProtocolTraceRecords'],'protocol records') == protocol_count
            and integer(performance['PhyTraceRecords'],'PHY records') == count,'Trace record totals disagree')
    return {'ota_transmissions':len(tx),'receiver_completions':len(ends),'protocol_records':protocol_count,
        'phy_records':count,'pending_receivers':integer(stats['PhysicalPending'],'physical pending'),
        'transmissions_exactly_at_stop':sum(when == horizon for _,when in tx.values()),'callback_horizon_end_inclusive':True}


def verify_native_buckets(directory,case):
    """Bind native aggregate semantics to its preserved original trace bytes."""
    path = directory/'ns3-aggregates.csv'
    provenance = json_object(directory/'ns3-benchmark.provenance.json')
    count = int(case['duration_s']/case['bucket_width_s'])
    aggregate._check_provenance(provenance,case,'ns3',sha256(path),case['duration_s'],case['bucket_width_s'],count)
    require(provenance.get('source_commit') == t7.PIN, 'Native aggregate source commit mismatch')
    record = json_object(directory/'manifest.json')
    traces = [row for row in records(record.get('compressed_artifacts'),'compressed native artifacts')
              if row.get('original_name') == 'ns3-trace.csv']
    require(len(traces) == 1 and traces[0].get('original_sha256') == provenance['source_file_sha256'],
            'Native aggregate source trace binding mismatch')
    upstream = provenance.get('upstream_provenance')
    require(isinstance(upstream,dict) and upstream.get('path') == 'ns3-aggregates.provenance.json'
            and upstream.get('sha256') == sha256(directory/'ns3-aggregates.provenance.json'),
            'Native aggregate upstream hash mismatch')
    require(json_object(directory/'ns3-aggregates.provenance.json').get('input',{}).get('sha256') == provenance['source_file_sha256'],
            'Native aggregate upstream trace hash mismatch')
    aggregate.read_series(path,'ns3',case['scenario'],provenance['source_file_sha256'],case['bucket_width_s'],count,
                          provenance.get('excluded_extra_statistics',[]))
    return list(metrics.csv_rows(path))


def verify_case(directory,entry,case,key,source_root,source,source_hash,runtime,parent_config,plan_hash):
    observed = key != 'm128_off'
    require(entry.get('CaseId') == key and entry.get('Directory') == key
            and entry.get('NativeCaseId') == case['case_id'] and entry.get('ObserverEnabled') is observed
            and entry.get('DurationSeconds') == case['duration_s'] and entry.get('Passed') is True
            and entry.get('ManifestSHA256') == sha256(directory/'case.json'), 'Case entry identity/hash mismatch')
    manifest = json_object(directory/'case.json')
    require(manifest.get('schema') == 'csr-tranche18-relay-service-case-v1' and manifest.get('status') == 'completed'
            and manifest.get('case_id') == key and manifest.get('native_case_id') == case['case_id']
            and manifest.get('mode') == 'continuous' and manifest.get('receiver_timing_injected') is False
            and manifest.get('observer_enabled') is observed and manifest.get('case') == case
            and manifest.get('source_snapshot_sha256') == source_hash and manifest.get('ns3_source_commit') == t7.PIN
            and manifest.get('structural_checks_passed') is True and manifest.get('structural_check_count') == 12
            and manifest.get('numerical_parity_established') is False, 'Case workload/observer/source identity mismatch')
    require(manifest.get('base_case_id') == case['case_id'] and manifest.get('storage_key') == key
            and manifest.get('scheduler_stop_s') == case['duration_s']
            and t17.source_map(manifest.get('source_files'),'case source') == source, 'Case stop/source identity mismatch')
    for field in ('condition','scenario','scenario_sha256','profile_id','seed','duration_s','bucket_width_s','reference_directory'):
        require(manifest.get(field) == case[field], 'Case duplicate identity differs: '+field)
    t7.inventory(directory,manifest.get('files'),'T18 case artifacts',excluded=('case.json',),local=manifest.get('local_files',[]))
    raw = directory/'raw'
    raw_manifest = json_object(raw/'case_manifest.json')
    require(raw_manifest.get('schema') == 'csr-matlab-research-case-v1' and raw_manifest.get('status') == 'completed'
            and all(raw_manifest.get(key) is True for key in ('execution_completed','source_files_stable','structural_checks_passed'))
            and raw_manifest.get('ns3_source_commit') == t7.PIN
            and t17.source_map(raw_manifest.get('source_files'),'raw source') == source, 'Raw source/execution incomplete')
    for field in ('scenario','scenario_sha256','seed','duration_s','flow_limit'):
        require(raw_manifest.get(field) == case[field], 'Raw case duplicate identity differs: '+field)
    t7.inventory(raw,raw_manifest.get('files'),'T18 raw artifacts',excluded=('case_manifest.json',),local=raw_manifest.get('local_files',[]))
    require(set(CORE_CSV) <= all_files(raw) and sha256(raw/'scenario.csv') == case['scenario_sha256']
            and sha256(raw/'trace.csv') == sha256(raw/'protocol_trace.csv'), 'Raw export/scenario/protocol copies mismatch')
    summary = json_object(raw/'summary.json')
    config,stats,md = summary['Config'],summary['Statistics'],summary['Metadata']
    require(manifest.get('runtime') == md and md.get('Runtime') == 'MATLAB'
            and md.get('Version') == runtime['Version'] and md.get('Release') == runtime['Release']
            and md.get('SourceCommit') == t7.PIN and md.get('Backend') == 'portable' and md.get('ChannelModel') == 'csr-phy'
            and md.get('ModelStage') == 'tranche-3-autonomous-network-routing' and 'TransportTiming' not in summary,
            'Case is not unchanged portable/default-continuous real-PHY autonomous network')
    configuration = verify_configuration(config,parent_config,case,source_root,plan_hash)
    t7.verify_config(directory,config)
    accounting = retained.verify_raw_accounting(raw,summary)
    admissions = t7.verify_admission(directory,config,stats)
    require(admissions['omitted_trace_records'] == 0 and admissions['attempts'] == case['expected_admission_attempts'],
            'Incomplete short-run admission observations or changed offered attempts')
    performance = csv_rows(directory/'analysis/performance_summary.csv')
    require(len(performance) == 1, 'Missing/duplicate performance summary')
    measured = sweep.metrics(performance[0])
    require(manifest.get('data_drained') is bool(measured['DataDrained']), 'Case drain flag differs from ownership')
    require(all(measured[name] == accounting['counts'][name] for name in t7.COUNTS), 'Performance application counters disagree')
    nodes = t17.verify_node_metrics(directory,config,performance[0])
    physical = verify_physical_trace(directory,config,stats,performance[0])
    protocol = list(metrics.csv_rows(raw/'protocol_trace.csv'))
    app_rows = csv_rows(directory/'analysis/applications.csv')
    sent,received = t16.validate_applications(app_rows,protocol,accounting['counts'],case)
    buckets = verify_buckets(directory,case,source_hash,sent,received)
    feedback = service_report = cohort = None
    if observed:
        adapted_case = copy.deepcopy(case)
        adapted_case['trace_limits']['link_decisions'] = case['observer_max_records']
        feedback = t16.verify_feedback(directory,summary,adapted_case,protocol)
        require(manifest.get('observer_diagnostics') == summary.get('LinkDiagnostics')
                and manifest.get('service_diagnostics') == summary.get('ServiceDiagnostics'), 'Observer manifests disagree')
        service_report = service.verify_matlab_rows(list(metrics.csv_rows(raw/'service_trace.csv')),protocol,
            list(metrics.csv_rows(raw/'application_admission_trace.csv')),list(metrics.csv_rows(raw/'link_decisions.csv')),
            summary['ServiceDiagnostics'],{'service_window_s':case['service_window_seconds'],'service_max_records':case['observer_max_records']})
        require(service_report['out_of_window_events_verified'] == 0, 'Full-run observer omitted in-horizon callback')
        import tranche18_metrics
        cohort = tranche18_metrics.analyze_case(directory,dict(case,service_window_s=case['service_window_seconds']))
    else:
        require(not any(name in summary for name in ('ServiceDiagnostics','LinkDiagnostics'))
                and not ({'service_trace.csv','link_decisions.csv','actual_feedback.csv'} & all_files(raw)),
                'Observer-off control contains observer observations')
    application_case = dict(case,base_case_id=case['case_id'])
    import tranche18_metrics
    return {'case_id':key,'configuration':configuration,'accounting':accounting,'admission':admissions,
        'physical_trace':physical,'node_counter_totals':nodes,'applications':tranche18_metrics.summarize_matlab_applications(directory,application_case),
        'feedback':feedback,'service':service_report,'cohorts':cohort,'data_drained':bool(measured['DataDrained']),
        'controls_drained':bool(measured['ControlsDrained'])},performance[0],buckets


def verify_nonperturbation(on,off):
    before,after = (json_object(path/'raw/summary.json') for path in (on,off))
    require(before['Config'] == after['Config'] and before['Statistics'] == after['Statistics'],
            'Observer changes configuration or core Statistics')
    require({k:v for k,v in before['Metadata'].items() if k != 'RuntimeSeconds'} ==
            {k:v for k,v in after['Metadata'].items() if k != 'RuntimeSeconds'}, 'Observer changes core Metadata')
    differences = []
    for filename in CORE_CSV:
        a,b = on/'raw'/filename,off/'raw'/filename
        require(a.read_bytes() == b.read_bytes(), 'Observer changes core CSV bytes: '+filename)
        differences.append({'path':filename,'sha256':sha256(a),'bytes':a.stat().st_size})
    for filename in ('applications.csv','aggregates.csv'):
        a,b = on/'analysis'/filename,off/'analysis'/filename
        require(a.read_bytes() == b.read_bytes(), 'Observer changes analysis CSV bytes: '+filename)
    return {'passed':True,'observed_case':'m128','control_case':'m128_off','statistics_exact_equal':True,
        'configuration_exact_equal':True,'core_csvs':differences,'scope':'Existing passive observer; runtime and observer-only exports excluded.'}


def verify_nonperturbation_claim(declared,on,off):
    require(declared.get('Schema') == 'csr-tranche18-observer-nonperturbation-v1'
            and declared.get('ObserverOnCase') == 'm128' and declared.get('ObserverOffCase') == 'm128_off'
            and declared.get('MetadataExcludedFields') == ['RuntimeSeconds']
            and all(declared.get(key) is True for key in ('Passed','StatisticsEqual','ConfigurationEqual','MetadataEqualExcludingRuntimeSeconds')),
            'Owner nonperturbation identity/claims incomplete')
    require(declared.get('ObservedSummarySHA256') == sha256(on/'raw/summary.json')
            and declared.get('ControlSummarySHA256') == sha256(off/'raw/summary.json'), 'Nonperturbation summary hash mismatch')
    bindings = records(declared.get('Files'),'nonperturbation files')
    require(len(bindings) == len(CORE_CSV) and {row.get('Path') for row in bindings} == set(CORE_CSV),
            'Nonperturbation file membership mismatch')
    for row in bindings:
        require(row.get('Equal') is True and row.get('ObservedSHA256') == sha256(on/'raw'/row['Path'])
                and row.get('ControlSHA256') == sha256(off/'raw'/row['Path']), 'Nonperturbation file hash mismatch')


def compare_prefix_rows(baseline,current,*,horizon,partial_baseline=False):
    """Exact retained CSV values; the finite-stop boundary is never guessed."""
    sentinel = object(); matched = 0; baseline_boundary = current_boundary = 0
    baseline = iter(baseline); current = iter(current)
    a = next(baseline,sentinel); b = next(current,sentinel)
    while a is not sentinel and float(a['TimeSeconds']) < horizon:
        require(b is not sentinel and float(b['TimeSeconds']) < horizon and a == b,
                'Original campus pre-stop prefix changed or omitted an observation')
        matched += 1
        a,b = next(baseline,sentinel),next(current,sentinel)
    if not partial_baseline:
        require(b is sentinel or float(b['TimeSeconds']) >= horizon, 'Extra pre-stop observation absent from original campus')
    else:
        require(a is sentinel, 'Partial-baseline mode requires the actually exhausted retained prefix')
    unmatched_current = 0
    if b is not sentinel:
        for row in itertools.chain([b],current):
            when = float(row['TimeSeconds'])
            require(0 <= when <= horizon, 'Current prefix observation exceeds its horizon')
            if when == horizon:
                current_boundary += 1
            else:
                unmatched_current += 1
    if a is not sentinel:
        for row in itertools.chain([a],baseline):
            when = float(row['TimeSeconds'])
            if when > horizon:
                break
            if when == horizon:
                baseline_boundary += 1
    return {'matched_pre_stop_rows':matched,'baseline_boundary_rows':baseline_boundary,
        'current_boundary_rows':current_boundary,'new_rows_beyond_retained_baseline':unmatched_current,
        'baseline_capture_censored':partial_baseline,'strict_prefix_end_seconds':horizon}


def verify_campus_prefix(directory,source_root):
    report = {}
    with zipfile.ZipFile(source_root/'evidence/t17/owner.zip') as archive:
        for filename in ('protocol_trace.csv','phy_trace.csv','application_admission_trace.csv'):
            with archive.open('campus/c/raw/'+filename) as source:
                reader = csv.DictReader(io.TextIOWrapper(source,encoding='utf-8-sig',newline=''))
                report[filename] = compare_prefix_rows(reader,t7.csv_records(directory/'raw'/filename),horizon=900,
                    partial_baseline=filename == 'application_admission_trace.csv')
    require(report['application_admission_trace.csv']['matched_pre_stop_rows'] == 100000,
            'Original T17 admission retained prefix membership changed')
    return {'passed':True,'files':report,'scope':LIMITATIONS[-2:]}


def verify_network(root,metadata,source_root,candidate,prepared,runtime):
    require(metadata.get('RelayDirectory') == 'network' and metadata.get('RelayCompleted') is True
            and metadata.get('RelayPassed') is True and metadata.get('NonperturbationPassed') is True
            and all(integer(metadata.get(name),name) == value for name,value in (
                ('RelayCaseCount',11),('RelayObservedCaseCount',10),('RelayControlCaseCount',1),
                ('RelayCheckpointCount',132),('RelayFailedCount',0))), 'Top-level diagnostic completion counts disagree')
    combined = json_object(root/'network/summary.json')
    require(combined.get('Schema') == 'csr-tranche18-relay-service-contract-v1'
            and combined.get('DiagnosticCompleted') is True and combined.get('Completed') is True
            and combined.get('Passed') is True and combined.get('NumericalParityEstablished') is False
            and combined.get('FullAcceptanceEstablished') is False, 'T18 network completion/scope mismatch')
    require(combined.get('CaseCount') == 11 and combined.get('PlannedCaseCount') == 11
            and combined.get('ObservedCaseCount') == 10 and combined.get('ControlCaseCount') == 1
            and combined.get('NonperturbationPassed') is True and combined.get('Runtime') == runtime
            and combined.get('CheckpointCount') == 132 and combined.get('FailedCount') == 0
            and combined.get('SimulatedSecondsCompleted') == 6900 and combined.get('PlannedSimulatedSeconds') == 6900
            and combined.get('SourceSnapshotSHA256') == metadata['SourceSnapshotSHA256']
            and combined.get('PlanSHA256') == candidate['PlanSHA256'], 'Network source/plan/count budget mismatch')
    entries = records(combined.get('Cases'),'network cases')
    require([entry.get('CaseId') for entry in entries] == list(EXECUTION_ORDER), 'Missing/duplicate/reordered actual cases')
    checks = csv_rows(root/'network/checks.csv',('CaseId','Check','Passed'))
    require([(row['CaseId'],row['Check']) for row in checks] == [(key,name) for key in EXECUTION_ORDER for name in CHECKS]
            and all(logical(row['Passed'],'check') for row in checks), 'Missing/duplicate/failed structural check identity')
    summaries = csv_rows(root/'network/summary.csv')
    require([row.get('CaseId') for row in summaries] == list(EXECUTION_ORDER), 'Network performance case membership mismatch')
    with zipfile.ZipFile(source_root/'evidence/t17/owner.zip') as archive:
        parent = json.loads(archive.read('campus/c/raw/summary.json'))['Config']
    planned = {case['case_id']:case for case in prepared['plan']['cases']}
    results,buckets,native = {},{},{}
    for entry,row in zip(entries,summaries):
        key = entry['CaseId']; base = 'm128' if key == 'm128_off' else key; case = planned[base]
        observed,performance,series = verify_case(root/'network'/key,entry,case,key,source_root,prepared['source'],
            metadata['SourceSnapshotSHA256'],runtime,parent,candidate['PlanSHA256'])
        require(all(row.get(name) == value for name,value in performance.items()), 'Combined performance differs from original case')
        require(integer(row.get('Attempts'),'attempts') == observed['admission']['attempts']
                and integer(row.get('AdmissionBlocked'),'blocked') == observed['admission']['blocked']
                and integer(row.get('OmittedApplicationAdmissionRecords'),'omissions') == 0,
                'Combined admission counters differ')
        require(row.get('NativeCaseId') == base and row.get('Condition') == case['condition']
                and logical(row.get('ObserverEnabled'),'observer enabled') is (key != 'm128_off'),
                'Combined case condition/control identity differs')
        results[key],buckets[key] = observed,series
        if key != 'm128_off':
            native_case = dict(case,base_case_id=case['case_id'])
            reference = source_root/case['reference_directory']
            native[key] = {'applications':metrics.ns3_applications(reference,native_case)}
            native_series = verify_native_buckets(reference,case)
            native[key]['matlab_minus_native_buckets'] = t16.bucket_differences(native_series,series)
            native[key]['matlab_minus_native_applications'] = t16.scalar_differences(native[key]['applications'],observed['applications'])
    nonperturbation = verify_nonperturbation(root/'network/m128',root/'network/m128_off')
    declared = json_object(root/'network/nonperturbation.json')
    verify_nonperturbation_claim(declared,root/'network/m128',root/'network/m128_off')
    prefix = verify_campus_prefix(root/'network/p128',source_root)
    return {'case_count':11,'simulated_seconds':6900,'cases':[results[key] for key in EXECUTION_ORDER],
        'native':native,'nonperturbation':nonperturbation,'campus_prefix':prefix,'limitations':LIMITATIONS}


def review(evidence,source_root,output):
    evidence,source_root,output = t17.output_location(evidence,source_root,output)
    prepared = verify_preparation(source_root)
    candidate = json_object(source_root/CANDIDATE)
    with t17.evidence_directory(evidence) as root:
        require(evidence.is_dir() or not (root/'t18.zip').exists(), 'Unexpected nested return archive')
        metadata = json_object(root/'metadata.json')
        runtime = verify_identity(root,metadata,source_root,candidate)
        t7.inventory(root,metadata.get('Artifacts'),'T18 outer artifacts',excluded=('metadata.json','t18.zip'),
                     local=metadata.get('LocalArtifacts',[]))
        source = verify_sources(root,metadata,source_root)
        references = t17.verify_references(root,metadata,prepared['references'])
        baseline = verify_baseline(source_root,candidate,metadata)
        tests = verify_tests(root,metadata,source_root,candidate)
        network = verify_network(root,metadata,source_root,candidate,prepared,runtime)
        result = {'schema':REVIEW_SCHEMA,'status':'focused_diagnostic_review_completed','evidence_integrity_verified':True,
            'focused_structural_gate_completed':True,'full_structural_gate_completed':False,'acceptance_established':False,
            'numerical_parity_established':False,'matlab_executed_by_reviewer':False,'runtime':runtime,'source':source,
            'baseline':baseline,'references':references,'tests':tests,'network':network,'native_reference':prepared['native'],
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
    except ValueError as error:
        print('T18 output rejected without modifying inputs: '+str(error)); return 1
    try:
        result = review(args.evidence,args.source_root,args.output)
    except (ValueError,OSError,csv.Error,zipfile.BadZipFile,KeyError,TypeError,AttributeError,OverflowError,StopIteration,ImportError) as error:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'review.json').write_text(json.dumps({'schema':REVIEW_SCHEMA,'status':'review_failed',
            'evidence_integrity_verified':False,'focused_structural_gate_completed':False,'full_structural_gate_completed':False,
            'acceptance_established':False,'numerical_parity_established':False,'matlab_executed_by_reviewer':False,
            'error':str(error)},indent=2)+'\n',encoding='utf-8')
        print('T18 evidence rejected: '+str(error)); return 1
    print(f"T18 focused review complete: {result['tests']['count']} MATLAB tests and 11 finite-stop runs; numerical residuals remain descriptive.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
