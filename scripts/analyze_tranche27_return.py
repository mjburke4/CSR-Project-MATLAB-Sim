#!/usr/bin/env python3
"""Verify T27 deterministic discovery evidence without executing MATLAB.

Completed controller differences are findings, not malformed evidence and not
numerical-parity acceptance. Reuses the established strict inventory readers.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import json
import math
from pathlib import Path
import zipfile

from analyze_tranche11_return import (
    all_files, candidate_snapshot, csv_rows, evidence_directory, integer,
    inventory, json_object as _json_object, json_value as _json_value, logical,
    number, record_map, records, require, safe_path, selected_test_names, sha256,
    verify_sources, verify_tests,
)
import analyze_tranche17_return as t17

SCHEMA = 'csr-matlab-tranche-27-validation-v1'
REVIEW_SCHEMA = 'csr-tranche27-return-review-v1'
PIN = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
ENGINE_PIN = '6b5cd24ea80713ce16d88575869aedd6f432bdae'
CANDIDATE = 'evidence/tranche-27-candidate.json'
PLAN = 'evidence/tranche-27-plan.json'
BASELINE = 'evidence/tranche-27-baseline.json'
BASELINE_SHA = 'a18437d84b4557a9b52c96ef6fb065b7904ec7a011c55debf2cc637541aa7376'
PARENT = 'evidence/tranche-27-parent-candidate.json'
PARENT_SHA = '3859ff6eaecd504b9c84f0030a97069a364a054063022c903cfdeabd47b02741'
ACCEPTANCE = 'evidence/t27/baseline/t25-acceptance.json'
ACCEPTANCE_SHA = '4c0937d5a6387e5bed3e23920ca9889e32c6eca04f44c61a6cd96e59b068c80d'
PARENT_REFERENCES = 'evidence/t27/baseline/t25-references.json'
PARENT_REFERENCES_SHA = '75c1c71f38c1ee5df41496e78e869a03510b713abd10efae1a275ff17e9fedf1'
REFERENCE = 'evidence/tranche-27-native-reference'
CASE_IDS = ('C0', 'C1', 'C2', 'C3_match', 'C3_timeout')
CONTROL_FIELDS = ('case_id','order','time_s','command','source','final_destination',
                  'next_hop','ackable','send_result','advertised_nodes')
TIME_TOLERANCE = Decimal('0.000000001')
LIMITATIONS = [
    'Hashes bind returned claims; they do not independently prove MATLAB execution.',
    'This is deterministic discovery-controller boundary replay, without stochastic PHY or campus traffic.',
    'MATLAB private controller fields remain unavailable; no values are invented for cross-engine comparison.',
    'Control-stream differences are reported independently of the evidence-integrity and focused-test gate.',
    'These fixtures alone do not establish the cause of native seed 131 topology or population numerical parity.',
]


def finite_json(value):
    """Also reject exponent overflow (JSON 1e999), beyond literal NaN rejection."""
    if isinstance(value, float):
        require(math.isfinite(value), 'Nonfinite JSON number')
    elif isinstance(value, dict):
        for item in value.values():
            finite_json(item)
    elif isinstance(value, list):
        for item in value:
            finite_json(item)
    return value


def json_value(path):
    return finite_json(_json_value(path))


def json_object(path):
    return finite_json(_json_object(path))


def source_map(value, label):
    return {name: row['sha256'] for name,row in record_map(value,label).items()}


def verify_baseline(root, candidate, metadata=None):
    for field,path,digest in (
        ('BaselineSourceSnapshot',BASELINE,BASELINE_SHA),
        ('BaselineCandidate',PARENT,PARENT_SHA),
        ('BaselineAcceptance',ACCEPTANCE,ACCEPTANCE_SHA),
    ):
        hash_field = 'BaseSourceSnapshotSHA256' if field == 'BaselineSourceSnapshot' else field+'SHA256'
        require(candidate.get(field) == path and candidate.get(hash_field) == sha256(root/path) == digest,
                'Accepted T25 provenance identity mismatch: '+field)
    baseline = record_map(json_value(root/BASELINE),'T25 baseline')
    require(len(baseline) == 420 and sum(name.endswith('.m') for name in baseline) == 186,
            'Accepted T25 source membership changed')
    for name,row in baseline.items():
        require(sha256(safe_path(root,name)) == row['sha256'], 'Accepted T25 source changed: '+name)
    parent = json_object(root/PARENT)
    require(source_map(parent.get('SourceFiles'),'parent source') ==
            {name: row['sha256'] for name,row in baseline.items() if name != 'evidence/tranche-25-candidate.json'},
            'T25 accepted source and parent candidate disagree')
    acceptance = json_object(root/ACCEPTANCE)
    require(acceptance.get('portable_regression_accepted') is True
            and acceptance.get('campus_structural_gate_accepted') is True
            and acceptance.get('source_snapshot_sha256') == BASELINE_SHA
            and acceptance.get('candidate_sha256') == PARENT_SHA
            and acceptance.get('source_files_verified') == 420
            and acceptance.get('matlab_source_files_verified') == 186
            and acceptance.get('tests_passed') == 760,
            'T25 accepted evidence claims do not bind this source')
    require(candidate.get('AllowedModifiedSourceFiles') == []
            and candidate.get('AllBaselineSourcesUnchanged') is True
            and candidate.get('BaselineSourceFiles') == 420 and candidate.get('BaselineMatlabFiles') == 186,
            'T27 cannot modify accepted T25 source')
    if metadata is not None:
        require(metadata.get('AllBaselineSourcesUnchanged') is True
                and integer(metadata.get('BaselineSourceFilesVerified'),'baseline count') == 420
                and integer(metadata.get('BaselineMatlabFilesVerified'),'baseline MATLAB count') == 186,
                'Returned T25 baseline counters disagree')
    return {'source_files':420,'matlab_files':186,'all_unchanged':True,'source_snapshot_sha256':BASELINE_SHA}


def verify_references(root, candidate):
    names = candidate.get('ReferenceFiles')
    entries = record_map(candidate.get('ReferenceFileInventory'),'candidate references',sizes=True)
    require(candidate.get('ReferenceRoots') == [] and isinstance(names,list)
            and names == sorted(set(names)) and set(names) == set(entries),
            'Explicit reference membership is not closed')
    inherited = record_map(json_object(root/PARENT)['ReferenceFileInventory'],'parent references',sizes=True)
    require(sha256(root/PARENT_REFERENCES) == PARENT_REFERENCES_SHA
            and record_map(json_value(root/PARENT_REFERENCES),'accepted references',sizes=True) == inherited,
            'Accepted T25 reference binding changed')
    ledger,archive = 'docs/parity-ledger.csv','evidence/t27/baseline/parity-ledger.csv'
    require(len(inherited) == 365 and candidate.get('AllowedModifiedReferenceFiles') == [ledger]
            and all(entries.get(name) == row for name,row in inherited.items() if name != ledger)
            and entries.get(archive) == dict(inherited[ledger],path=archive),
            'Inherited references or preserved ledger changed')
    required = {BASELINE,PARENT,ACCEPTANCE,PARENT_REFERENCES,PLAN,ledger,archive}
    required.update(REFERENCE+'/'+name for name in all_files(root/REFERENCE))
    require(required <= set(entries), 'Required native/baseline/plan reference omitted')
    for name,row in entries.items():
        path = safe_path(root,name)
        require(path.is_file() and path.stat().st_size == row['bytes'] and sha256(path) == row['sha256'],
                'Reference hash or size mismatch: '+name)
    return entries


def verify_plan(root, candidate):
    require(candidate.get('Plan') == PLAN and candidate.get('PlanSHA256') == sha256(root/PLAN),
            'Frozen controller plan path/hash mismatch')
    plan = json_object(root/PLAN)
    require(plan.get('schema') == 'csr-tranche27-controller-plan-v1'
            and plan.get('fixture_count') == 4 and plan.get('execution_count') == 5
            and plan.get('local_node') == 1 and plan.get('local_role') == 'gateway'
            and plan.get('peer_capability') == 1,
            'Controller plan identity/scope mismatch')
    cases = plan.get('cases')
    require(isinstance(cases,list) and [c.get('id') for c in cases] == list(CASE_IDS),
            'Missing, duplicate or reordered controller executions')
    expected = (
        ([3,5],None,None,None,None,'60.2'),
        ([3],1,3,20,4,'20.1'),
        ([3,5,4],1,3,None,None,'60.2'),
        ([3,5,4],1,4,None,None,'61.2'),
        ([3,5,4],None,None,None,None,'61.2'),
    )
    common = ['0.0000001','0.0999999','0.1000001','0.9999999','1.0000001']
    endings = [
        ['60.0999999','60.1000001','60.2'],
        ['19.9999999','20.0000001','20.1'],
        ['60.0999999','60.1000001','60.2'],
        ['60.0999999','60.1000001','60.9999999','61.0000001','61.2'],
        ['60.0999999','60.1000001','60.9999999','61.0000001','61.2'],
    ]
    for case,values,ending in zip(cases,expected,endings):
        peers,done_time,done_source,late_time,late_peer,stop = values
        require(case.get('fixture_id') == case['id'].split('_')[0]
                and case.get('initial_peers') == peers and case.get('done_time_s') == done_time
                and case.get('done_source') == done_source and case.get('late_peer_time_s') == late_time
                and case.get('late_peer') == late_peer and number(case.get('local_duration_s'),'local duration') == Decimal('.1')
                and number(case.get('stop_s'),'case stop') == Decimal(stop),
                'Prespecified controller input changed: '+case['id'])
        require([number(v,'checkpoint time') for v in case.get('checkpoints_s',[])] ==
                [Decimal(v) for v in common+ending], 'Prespecified checkpoint tape changed: '+case['id'])
    return plan


def validate_controls(rows, case, label, native=False):
    require(isinstance(rows,list) and rows, label+': missing controller controls')
    parsed,previous,targets = [],Decimal(-1),set()
    peers = set(case['initial_peers']) | ({case['late_peer']} if case['late_peer'] is not None else set())
    for index,row in enumerate(rows,1):
        require(isinstance(row,dict), label+': invalid control record')
        if not native:
            require(tuple(row) == CONTROL_FIELDS and row['case_id'] == case['id']
                    and integer(row['order'],'control order',1) == index,
                    label+': control schema/case/order mismatch')
        when = number(row.get('time_s'),'control time',minimum=0)
        require(previous <= when <= number(case['stop_s'],'stop'), label+': unordered/out-of-window control')
        previous = when
        target = integer(row.get('final_destination'),'control target',1)
        require(row.get('command') == 'START' and integer(row.get('source'),'control source',1) == 1
                and target in peers and target not in targets
                and integer(row.get('next_hop'),'control next hop',1) == target,
                label+': unexpected or duplicated controller destination')
        targets.add(target)
        ackable = row.get('ackable')
        sent = row.get('send_result')
        ackable = ackable if isinstance(ackable,bool) else logical(str(ackable),'ackable')
        sent = sent if isinstance(sent,bool) else logical(str(sent),'send result')
        require(not ackable and sent, label+': fixture control must be best effort and successfully enqueued')
        advertised = row.get('advertised_nodes')
        if not native:
            require(advertised == '[]', label+': unexpected advertised nodes serialization')
        else:
            require(advertised == [], label+': unexpected advertised nodes')
        parsed.append({'case_id':case['id'],'order':index,'time_s':str(when),'command':'START',
                       'source':1,'final_destination':target,'next_hop':target,
                       'ackable':False,'send_result':True,'advertised_nodes':[]})
    require(abs(number(parsed[0]['time_s'],'first control')-Decimal('.1')) <= TIME_TOLERANCE
            and parsed[0]['final_destination'] == case['initial_peers'][-1],
            label+': missing local completion/newest-first control')
    return parsed


def compare_controls(actual, reference):
    differences = []
    for index in range(max(len(actual),len(reference))):
        left = actual[index] if index < len(actual) else None
        right = reference[index] if index < len(reference) else None
        fields = ['row_membership'] if left is None or right is None else [
            field for field in CONTROL_FIELDS if
            (abs(number(left[field],'MATLAB time')-number(right[field],'native time')) > TIME_TOLERANCE
             if field == 'time_s' else left[field] != right[field])]
        if fields:
            differences.append({'row':index+1,'fields':fields,'matlab':left,'native':right})
    return {'matches_native':not differences,'matlab_control_count':len(actual),
            'native_control_count':len(reference),'differing_rows':len(differences),
            'time_tolerance_s':str(TIME_TOLERANCE),'differences':differences}


def validate_states(document, case, label):
    require(document.get('Schema') == 'csr-tranche27-matlab-controller-states-v1'
            and document.get('CaseId') == case['id'] and document.get('PrivateControllerStateAvailable') is False,
            label+': state identity or private-access claim mismatch')
    unavailable = document.get('UnavailableControllerFields')
    require(unavailable == ['ScanKnown','ScanRequested','ScanWaiting','ScanGeneration',
                            'NeighborDiscoveryState','WatchdogDeadline']
            and isinstance(document.get('ObservationMethod'),str) and document['ObservationMethod'],
            label+': missing honest private-state observation scope')
    snapshots = records(document.get('Snapshots'),'controller snapshots')
    require(len(snapshots) == len(case['checkpoints_s']), label+': missing/extra state checkpoints')
    for index,(row,expected_time) in enumerate(zip(snapshots,case['checkpoints_s']),1):
        require(integer(row.get('event_order'),'checkpoint order',1) == index
                and row.get('event') == 'checkpoint'
                and abs(number(row.get('time_s'),'checkpoint time')-number(expected_time,'plan time')) <= TIME_TOLERANCE,
                label+': checkpoint time/order mismatch')
        for field in ('local_discovery_active','topology_known','gateway_available','local_is_gateway'):
            require(isinstance(row.get(field),bool), label+': missing Boolean '+field)
        require(row['local_is_gateway'] is True and row['topology_known'] is True,
                label+': fixture topology/gateway setup missing')
        require(row['local_discovery_active'] == (number(expected_time,'plan time') < Decimal('.1')),
                label+': local discovery interval differs from prescribed fixture')
        for field in ('active_peers','route_storage_order','logical_destination_birth_order_fixture'):
            value = row.get(field)
            if not isinstance(value,list):
                value = [value]  # MATLAB encodes one numeric item as a scalar.
            ids = [integer(item,field,1) for item in value]
            require(ids and len(ids) == len(set(ids)), label+': invalid '+field)
            peers = list(case['initial_peers'])
            if case['late_peer_time_s'] is not None and number(expected_time,'time') > number(case['late_peer_time_s'],'late time'):
                peers.append(case['late_peer'])
            require(set(ids) == set(peers), label+': prescribed usable peer membership missing: '+field)
            if field == 'logical_destination_birth_order_fixture':
                require(ids == list(reversed(peers)), label+': supplied logical birth order changed')
        for field in ('application_state','stats'):
            require(isinstance(row.get(field),dict) and row[field], label+': missing public '+field)
        require('routes' in row and 'neighbors' in row, label+': missing raw public snapshots')
        state = row['application_state']
        require(row['local_discovery_active'] == state.get('DiscoveryActive')
                and row['topology_known'] == state.get('TopologyKnown')
                and row['gateway_available'] == (state.get('GatewayId') not in ([],None))
                and row['gateway_available'] is False,
                label+': flags disagree with raw application state')
        require(integer(row['stats'].get('DiscoveryStarts'),'discovery starts') == 1
                and integer(row['stats'].get('DiscoveryCompletions'),'discovery completions') ==
                    int(number(expected_time,'plan time') > Decimal('.1')),
                label+': public discovery counters disagree with prescribed local scan')
        routes = records(row['routes'],'public routes')
        neighbors = records(row['neighbors'],'public neighbors')
        require(len(routes) == len(peers) and {r.get('DestinationId') for r in routes} == set(peers)
                and all(r.get('NextHop') == r.get('DestinationId') and r.get('Capability') == 1
                        and r.get('Selected') is True for r in routes),
                label+': prescribed capable direct routes missing')
        require(len(neighbors) == len(peers) and {r.get('Id') for r in neighbors} == set(peers)
                and all(r.get('Active') is True and r.get('Stale') is False for r in neighbors),
                label+': prescribed active peers missing')
    return {'checkpoint_count':len(snapshots),'private_controller_state_available':False,
            'unavailable_controller_fields':unavailable}


def verify_native(root, plan):
    directory = root/REFERENCE
    manifest = json_object(directory/'manifest.json')
    require(manifest.get('schema') == 'csr-tranche27-native-files-v1'
            and isinstance(manifest.get('files'),dict), 'Native manifest schema mismatch')
    entries = record_map([{'path':name,'sha256':digest} for name,digest in manifest['files'].items()],
                         'native manifest')
    require(set(entries) == all_files(directory)-{'manifest.json'}, 'Native reference inventory is not closed')
    for name,row in entries.items():
        require(sha256(safe_path(directory,name)) == row['sha256'], 'Native reference hash mismatch: '+name)
    summary = json_object(directory/'summary.json')
    require(summary.get('schema') == 'csr-tranche27-native-reference-v1' and summary.get('status') == 'passed'
            and summary.get('source_pin') == PIN and summary.get('engine_pin') == ENGINE_PIN
            and summary.get('native_executed') is True and summary.get('matlab_executed') is False
            and summary.get('production_source_unchanged') is True and summary.get('engine_source_unchanged') is True
            and summary.get('observer_on_off_identical') is True and summary.get('case_ids') == list(CASE_IDS)
            and summary.get('plan_sha256') == sha256(root/PLAN),
            'Native execution/source/scope/plan identity mismatch')
    require(summary.get('build_manifest') == 'build.json'
            and summary.get('build_manifest_sha256') == sha256(directory/'build.json'),
            'Native build receipt binding mismatch')
    build = json_object(directory/'build.json')
    require(build.get('status') == 'passed' and build.get('source_pin') == PIN
            and build.get('engine_pin') == ENGINE_PIN and build.get('native_executed') is True
            and build.get('production_source_unchanged') is True and build.get('engine_source_unchanged') is True
            and build.get('new_compilation') is True, 'Native build status/pins mismatch')
    seam = build.get('test_seam')
    require(isinstance(seam,dict) and seam.get('compiler_flag') == '-fno-access-control'
            and seam.get('source_edits') is False and seam.get('no_phy') is True
            and seam.get('no_campus') is True and seam.get('observations_do_not_schedule_events') is True,
            'Native test-only boundary declaration missing')
    runs = build.get('runs')
    require(isinstance(runs,dict) and set(runs) == {'observed','unobserved'}, 'Native run membership mismatch')
    commands = [build.get('compile'),build.get('ldd'),runs['observed'],runs['unobserved']]
    for command in commands:
        require(isinstance(command,dict) and isinstance(command.get('argv'),list) and command['argv']
                and integer(command.get('exit_code'),'native command exit code') == 0
                and command.get('log_sha256') == sha256(safe_path(directory,command.get('log'))),
                'Native compile/run completion or log identity mismatch')
        number(command.get('wall_seconds'),'native command wall time',minimum=0)
    require(build.get('tracked_verification') == 'tracked-verification.json'
            and build.get('tracked_verification_sha256') == sha256(directory/'tracked-verification.json')
            and build.get('plan_sha256') == sha256(root/PLAN)
            and build.get('harness_sha256') == sha256(root/'scripts/ns3/tranche27_discovery_controller.cc')
            and build.get('runner_sha256') == sha256(root/'scripts/run_tranche27_ns3_reference.py'),
            'Native source/plan/tracked verification receipt binding mismatch')
    tracked = json_object(directory/'tracked-verification.json')
    require(tracked.get('source_unchanged') is True and tracked.get('engine_unchanged') is True
            and tracked.get('before') == tracked.get('after'), 'Native tracked source changed during execution')
    for kind,count in (('source',110),('engine',4012)):
        require(tracked.get('before',{}).get(kind) == {'file_count':count,'all_tracked_files_verified':True},
                'Native tracked '+kind+' membership mismatch')
    expected_model = source_map(json_object(root/'evidence/tranche-14-native-build.json')['module_files'],'pinned native model')
    require(tracked.get('source_used_model_files_sha256') == expected_model,
            'Native model inputs differ from pinned production module')
    cases = summary.get('cases')
    require(isinstance(cases,dict) and set(cases) == set(CASE_IDS), 'Native case membership mismatch')
    expected = {'C0':[(5,'.1'),(3,'60.1')], 'C1':[(3,'.1')], 'C2':[(4,'.1'),(5,'1')],
                'C3_match':[(4,'.1'),(5,'1'),(3,'61')], 'C3_timeout':[(4,'.1'),(5,'60.1')]}
    checked,checkpoint_total,pre_send_total = {},0,0
    for case in plan['cases']:
        name = case['id']; item = cases[name]
        document_path = safe_path(directory,item.get('file'))
        require(item.get('sha256') == sha256(document_path), 'Native case content hash mismatch: '+name)
        document = json_object(document_path)
        require(document.get('schema') == 'csr-tranche27-native-controller-case-v1'
                and document.get('case_id') == name and document.get('engine') == 'ns3'
                and document.get('observer_enabled') is True and document.get('phy_executed') is False
                and document.get('production_source_modified') is False
                and integer(document.get('mac_data_queue_drops'),'native MAC queue drops') == 0,
                'Native case identity/scope/queue mismatch: '+name)
        controls = validate_controls(document.get('controls'),case,'native '+name,native=True)
        require(len(controls) == len(expected[name]) and all(
            row['final_destination'] == target and abs(number(row['time_s'],'native time')-Decimal(time)) <= TIME_TOLERANCE
            for row,(target,time) in zip(controls,expected[name])), 'Native source-contract milestones failed: '+name)
        for raw in document['controls']:
            require(raw.get('requested_at_capture') is True and integer(raw.get('sequence'),'sequence') == 0
                    and integer(raw.get('command_code'),'command code') == 1,
                    'Native mark-before-enqueue or wire identity changed: '+name)
        marks = document.get('pre_send')
        require(isinstance(marks,list) and len(marks) == len(controls), 'Native pre-send observation missing')
        for row,mark in zip(controls,marks):
            require(mark.get('requested_before_send') is True and mark.get('target') == row['final_destination']
                    and abs(number(mark.get('time_s'),'mark time')-number(row['time_s'],'control time')) <= TIME_TOLERANCE,
                    'Native requested bit not marked before send')
        states = document.get('states')
        require(isinstance(states,list) and states, 'Missing native controller state stream')
        previous = Decimal(-1)
        for state in states:
            when = number(state.get('time_s'),'native state time',minimum=0)
            require(previous <= when <= number(case['stop_s'],'stop'), 'Native states unordered/outside fixture')
            previous = when
        checkpoints = [row for row in states if row.get('event') == 'checkpoint']
        require(len(checkpoints) == len(case['checkpoints_s']) and all(
            abs(number(row['time_s'],'native checkpoint')-number(time,'planned checkpoint')) <= TIME_TOLERANCE
            for row,time in zip(checkpoints,case['checkpoints_s'])), 'Native checkpoint membership changed')
        off = json_object(directory/'observer-off'/f'{name}.json')
        require(off.get('case_id') == name and off.get('observer_enabled') is False
                and off.get('controls') == document['controls']
                and [row for row in off.get('states',[]) if row.get('event') == 'checkpoint'] == checkpoints,
                'Native observer changes controls or common checkpoints')
        exported_path = directory/'cases'/name/'controls.csv'
        require(item.get('controls_csv') == f'cases/{name}/controls.csv'
                and item.get('controls_csv_sha256') == sha256(exported_path)
                and item.get('controls') == len(controls) and item.get('checkpoint_count') == len(checkpoints),
                'Native summary exported control/checkpoint binding mismatch')
        exported = csv_rows(exported_path,CONTROL_FIELDS)
        require(validate_controls(exported,case,'native exported '+name) == controls,
                'Native logical CSV differs from captured real controller controls')
        checked[name] = {'controls':controls,'checkpoints':checkpoints,'source_milestones_verified':True}
        checkpoint_total += len(checkpoints); pre_send_total += len(marks)
    require(checkpoint_total == 44 and pre_send_total == 10, 'Native observation population mismatch')
    return {'cases':checked,'case_count':5,'checkpoint_count':44,'control_count':10,
            'native_executed':True,'matlab_executed':False,'observer_on_off_identical':True,
            'mark_before_send_checks':pre_send_total,'build_sha256':sha256(directory/'build.json'),
            'summary_sha256':sha256(directory/'summary.json')}


def verify_preparation(source_root):
    root = Path(source_root).resolve()
    candidate = json_object(root/CANDIDATE)
    require(candidate.get('Schema') == 'csr-tranche-27-candidate-v1' and candidate.get('Tranche') == 27
            and candidate.get('SourceCommit') == PIN and candidate.get('EngineCommit') == ENGINE_PIN,
            'T27 candidate identity mismatch')
    require(candidate.get('TimingPolicy') == 'continuous' and candidate.get('DataQueuedRetryPolicy') == 'actual-tx'
            and candidate.get('WorkingCampusBandPercent') == 10 and candidate.get('MATLABExecutionPending') is True
            and candidate.get('NativeExecuted') is True and candidate.get('NativeReferenceRoot') == REFERENCE
            and all(candidate.get(field) is False for field in ('MATLABExecuted','ProductionSourceChanged',
                'PHYExecuted','PHY_ECC_Changed','FullPortableRegression','FullCampusRun',
                'AcceptanceEstablished','NumericalParityEstablished')),
            'T27 candidate execution/scope claims mismatch')
    source = candidate_snapshot(root)
    require(candidate.get('SourceFilesExcludedPaths') == [CANDIDATE]
            and source_map(candidate.get('SourceFiles'),'T27 frozen source') ==
                {name:digest for name,digest in source.items() if name != CANDIDATE},
            'Frozen source hash/membership changed')
    test_files = ['tests/TestTranche27DiscoveryController.m','tests/TestNwkLayer.m',
                  'tests/TestNeighbors.m','tests/TestRoutes.m']
    names = selected_test_names(root,candidate.get('TestFiles'))
    require(candidate.get('TestFiles') == test_files and candidate.get('ExpectedTestNames') == names
            and candidate.get('ExpectedTestCount') == len(names), 'Focused MATLAB test membership mismatch')
    require(candidate.get('ExactExecutableCaseIDs') == list(CASE_IDS) and candidate.get('ExpectedCaseCount') == 5
            and candidate.get('ConceptualCaseCount') == 4 and candidate.get('ExpectedCheckpointCount') == 44,
            'Frozen execution/fixture/checkpoint counts mismatch')
    baseline = verify_baseline(root,candidate)
    references = verify_references(root,candidate)
    plan = verify_plan(root,candidate)
    native = verify_native(root,plan)
    return {'candidate':candidate,'source':source,'references':references,'plan':plan,
            'baseline':baseline,'native':native,'planned_matlab_tests':len(names)}


def verify_identity(root, metadata, source_root, candidate):
    require(metadata.get('Schema') == SCHEMA and metadata.get('Tranche') == 27
            and metadata.get('Status') in ('completed-review-required','completed-differences-review-required'),
            'Return is not a completed T27 diagnostic')
    require(metadata.get('EvidenceArchive') == 't27.zip'
            and metadata.get('InventoryExcludedPaths') == ['metadata.json','t27.zip']
            and metadata.get('CandidateFile') == CANDIDATE
            and metadata.get('CandidateSHA256') == sha256(source_root/CANDIDATE) == sha256(root/'candidate.json')
            and sha256(root/'plan.json') == candidate['PlanSHA256'], 'Returned candidate/plan/archive identity mismatch')
    runtime = metadata.get('Runtime')
    require(isinstance(runtime,dict) and runtime.get('Runtime') == 'MATLAB'
            and runtime.get('DefaultBackend') == 'portable'
            and all(isinstance(runtime.get(key),str) and runtime[key] for key in ('Version','Release')),
            'Missing actual portable MATLAB runtime/release identity')
    require(metadata.get('MATLABExecuted') is True and metadata.get('NativeExecuted') is False
            and metadata.get('SourceCommit') == PIN and metadata.get('FocusedGateExecuted') is True
            and all(metadata.get(field) is False for field in ('FullAcceptanceGateExecuted','AcceptanceEstablished',
                'NumericalParityEstablished','ProductionChanges','CampusExecuted'))
            and metadata.get('CrossEngineComparisonScope') == 'ordered_logical_SNMP_controls',
            'Owner execution/scope claims mismatch')
    require(t17.timestamp(metadata.get('StartedUTC'),'start') <= t17.timestamp(metadata.get('CompletedUTC'),'completion'),
            'Owner completion precedes start')
    number(metadata.get('ElapsedSeconds'),'owner duration',minimum=0)
    return runtime


def verify_case(root, case, native):
    name = case['id']; directory = root/'cases'/name
    require(all_files(directory) == {'controls.csv','states.json','summary.json','lower-layer-controls.json'},
            'Unexpected or missing case evidence: '+name)
    controls = validate_controls(csv_rows(directory/'controls.csv',CONTROL_FIELDS),case,'MATLAB '+name)
    document = json_object(directory/'states.json')
    state_result = validate_states(document,case,'MATLAB '+name)
    summary = json_object(directory/'summary.json')
    require(summary.get('Schema') == 'csr-tranche27-matlab-controller-case-v1' and summary.get('CaseId') == name
            and summary.get('DiagnosticCompleted') is True and summary.get('StructuralPassed') is True
            and summary.get('PrivateControllerStateAvailable') is False
            and all(summary.get(field) is False for field in ('ProductionChanges','RandomnessUsed','CampusExecuted')),
            'MATLAB case completion or scope claim mismatch: '+name)
    require(integer(summary.get('ControlCount'),'case controls') == len(controls)
            and integer(summary.get('CheckpointCount'),'case checkpoints') == state_result['checkpoint_count']
            and number(summary.get('StopSeconds'),'case stop') == number(case['stop_s'],'planned stop'),
            'MATLAB case completion count/time mismatch: '+name)
    number(summary.get('ElapsedSeconds'),'case elapsed',minimum=0)
    final_stats = document['Snapshots'][-1]['stats']
    require(summary.get('FinalStatistics') == final_stats, 'Case summary differs from final raw statistics')
    for field in ('MalformedControl','ControlQueueRejections','ControlFailures'):
        require(integer(final_stats.get(field),field) == 0, 'Controlled fixture has '+field)
    lower = records(json_value(directory/'lower-layer-controls.json'),'lower-layer controls')
    require(integer(summary.get('AcceptedLowerLayerControlCount'),'lower-layer controls') == len(lower),
            'Accepted lower-layer control count mismatch')
    previous = Decimal(-1)
    snmp = []
    for item in lower:
        when = number(item.get('time_s'),'lower-layer control time',minimum=0)
        require(previous <= when <= number(case['stop_s'],'stop') and isinstance(item.get('kind'),str)
                and isinstance(item.get('ackable'),bool), 'Invalid lower-layer control time/type')
        previous = when
        if item['kind'].startswith('SNMP_'):
            snmp.append(item)
    require(len(snmp) == len(controls), 'Lower-layer log omits/adds discovery commands')
    for raw,row in zip(snmp,controls):
        peers = raw.get('peers'); peers = peers if isinstance(peers,list) else [peers]
        require(raw['kind'] == 'SNMP_'+row['command'] and peers == [row['next_hop']]
                and raw['ackable'] == row['ackable']
                and abs(number(raw['time_s'],'lower-layer time')-number(row['time_s'],'control time')) <= TIME_TOLERANCE,
                'Logical controls differ from lower-layer captured handoffs')
    comparison = compare_controls(controls,native['controls'])
    public_differences = []
    fields = ('local_discovery_active','topology_known','gateway_available','local_is_gateway')
    for index,(left,right) in enumerate(zip(document['Snapshots'],native['checkpoints']),1):
        differing = [field for field in fields if left[field] != right[field]]
        if differing:
            public_differences.append({'checkpoint':index,'fields':differing,
                'matlab':{field:left[field] for field in differing},'native':{field:right[field] for field in differing}})
    return {'controls':comparison,'states':state_result,'public_admission_state_comparison':{
        'fields':list(fields),'matches_native':not public_differences,'differences':public_differences}}


def verify_difference_counters(summary, metadata, results):
    differing_cases = sum(not result['controls']['matches_native'] for result in results.values())
    differing_rows = sum(result['controls']['differing_rows'] for result in results.values())
    require(integer(summary.get('DifferingCaseCount'),'summary differing cases') == differing_cases
            and integer(summary.get('DifferingControlRows'),'summary differing rows') == differing_rows
            and integer(metadata.get('ContractDifferingCaseCount'),'metadata differing cases') == differing_cases
            and integer(metadata.get('ContractDifferingControlRows'),'metadata differing rows') == differing_rows,
            'Reported difference counters hide or invent native differences')


def verify_contract(root, metadata, prepared):
    require({p.name for p in (root/'cases').iterdir() if p.is_dir()} == set(CASE_IDS)
            and all(p.is_dir() for p in (root/'cases').iterdir()), 'Returned case membership changed')
    results = {case['id']:verify_case(root,case,prepared['native']['cases'][case['id']])
               for case in prepared['plan']['cases']}
    summary = json_object(root/'contract-summary.json')
    matches = all(result['controls']['matches_native'] for result in results.values())
    controls = sum(result['controls']['matlab_control_count'] for result in results.values())
    require(summary.get('Schema') == 'csr-tranche27-matlab-controller-contract-v1'
            and summary.get('DiagnosticCompleted') is True and summary.get('StructuralPassed') is True
            and summary.get('CrossEngineMatchesNative') is matches
            and summary.get('CrossEngineComparisonScope') == 'ordered_logical_SNMP_controls'
            and summary.get('PlanSHA256') == prepared['candidate']['PlanSHA256'],
            'Controller summary hides or invents logical control differences')
    for field,expected in (('CaseCount',5),('FixtureCount',4),('ControlCount',controls),('CheckpointCount',44)):
        require(integer(summary.get(field),field) == expected, 'Controller summary count mismatch: '+field)
    rows = records(summary.get('Comparison'),'controller comparison')
    require([row.get('CaseId') for row in rows] == list(CASE_IDS), 'Controller comparison membership changed')
    for row in rows:
        comparison = results[row['CaseId']]['controls']
        require(row.get('MatchesNative') is comparison['matches_native'], 'Comparison hides or invents differences')
        for field,key in (('MatlabControlCount','matlab_control_count'),('NativeControlCount','native_control_count'),
                          ('DifferingRows','differing_rows')):
            require(integer(row.get(field),field) == comparison[key], 'Comparison count differs from independent review')
    case_receipts = records(summary.get('Cases'),'completed case receipts')
    require([row.get('CaseId') for row in case_receipts] == list(CASE_IDS), 'Case receipt membership changed')
    for row in case_receipts:
        observed = results[row['CaseId']]
        require(row.get('DiagnosticCompleted') is True and row.get('StructuralPassed') is True
                and integer(row.get('ControlCount'),'receipt controls') == observed['controls']['matlab_control_count']
                and integer(row.get('CheckpointCount'),'receipt checkpoints') == observed['states']['checkpoint_count'],
                'Case receipt differs from independently verified outputs')
    verify_difference_counters(summary,metadata,results)
    require(metadata.get('ContractCompleted') is True and metadata.get('ContractStructuralPassed') is True
            and metadata.get('ContractMatchesNative') is matches and metadata.get('PrivateControllerStateAvailable') is False,
            'Returned contract completion/match flags disagree')
    for field,value in (('ContractCaseCount',5),('ContractCheckpointCount',44),('ContractControlCount',controls)):
        require(integer(metadata.get(field),field) == value, 'Metadata contract count mismatch')
    require(metadata.get('Status') == ('completed-review-required' if matches else 'completed-differences-review-required'),
            'Return status hides or invents native differences')
    return {'case_count':5,'fixture_count':4,'checkpoint_count':44,'control_count':controls,
            'logical_controls_match_native':matches,'comparison_scope':'ordered_logical_SNMP_controls',
            'private_controller_state_comparison_available':False,'cases':results}


def review(evidence, source_root, output):
    evidence,source_root,output = t17.output_location(evidence,source_root,output)
    prepared = verify_preparation(source_root)
    with evidence_directory(evidence) as root:
        require(not (root/'t27.zip').exists(), 'Unexpected nested return archive')
        metadata = json_object(root/'metadata.json')
        runtime = verify_identity(root,metadata,source_root,prepared['candidate'])
        inventory(root,metadata.get('Artifacts'),excluded=('metadata.json','t27.zip'))
        sources = verify_sources(root,metadata,source_root)
        references = t17.verify_references(root,metadata,prepared['references'])
        verify_baseline(source_root,prepared['candidate'],metadata)
        tests = verify_tests(root,metadata,source_root,prepared['candidate'])
        contract = verify_contract(root,metadata,prepared)
        result = {'schema':REVIEW_SCHEMA,'status':'controller_review_completed',
            'evidence_integrity_verified':True,'focused_structural_gate_completed':True,
            'logical_controls_match_native':contract['logical_controls_match_native'],
            'full_acceptance_gate_completed':False,'acceptance_established':False,
            'numerical_parity_established':False,'matlab_executed_by_reviewer':False,
            'runtime':runtime,'baseline':prepared['baseline'],'source':sources,'references':references,
            'tests':tests,'contract':contract,'metadata_sha256':sha256(root/'metadata.json'),'limitations':LIMITATIONS}
    output.mkdir(parents=True,exist_ok=True)
    (output/'review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-root','--source-root',dest='source_root',type=Path,required=True)
    parser.add_argument('--return-zip','--evidence',dest='evidence',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        t17.output_location(args.evidence or args.source_root,args.source_root,args.output)
    except (ValueError,OSError) as error:
        print('T27 output rejected without modifying inputs: '+str(error)); return 1
    try:
        if args.evidence is None:
            prepared = verify_preparation(args.source_root)
            result = {'schema':REVIEW_SCHEMA,'status':'native_preparation_verified_matlab_execution_pending',
                'native_reference_preparation_completed':True,'matlab_execution_pending':True,
                'matlab_executed_by_reviewer':False,'planned_matlab_tests':prepared['planned_matlab_tests'],
                'planned_fixtures':4,'planned_executions':5,'planned_checkpoints':44,
                'baseline':prepared['baseline'],'reference_files':len(prepared['references']),
                'native_controls':prepared['native']['control_count'],
                'acceptance_established':False,'numerical_parity_established':False,'limitations':LIMITATIONS}
            args.output.mkdir(parents=True,exist_ok=True)
            (args.output/'review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        else:
            result = review(args.evidence,args.source_root,args.output)
    except (ValueError,OSError,csv.Error,zipfile.BadZipFile,KeyError,TypeError,AttributeError,OverflowError) as error:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'review.json').write_text(json.dumps({'schema':REVIEW_SCHEMA,'status':'review_failed',
            'evidence_integrity_verified':False,'focused_structural_gate_completed':False,
            'acceptance_established':False,'numerical_parity_established':False,
            'matlab_executed_by_reviewer':False,'error':str(error)},indent=2)+'\n',encoding='utf-8')
        print('T27 evidence rejected: '+str(error)); return 1
    print('T27 '+result['status']+'. This checker did not execute MATLAB.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
