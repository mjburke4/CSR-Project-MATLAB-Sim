#!/usr/bin/env python3
"""Independently review T22 controlled HOP window contracts, never run MATLAB.

This short production-layer replay is a deterministic contract gate. Its exact
integer state comparisons do not replace the descriptive full-campus +/-10%
target or establish network/PHY numerical equivalence.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import gzip
import json
from pathlib import Path
import zipfile

from analyze_tranche11_return import (
    all_files, candidate_snapshot, csv_rows, integer, inventory, json_object,
    json_value, number, record_map, require, safe_path, selected_test_names,
    sha256, verify_sources, verify_tests,
)
import analyze_tranche17_return as t17

SCHEMA = 'csr-matlab-tranche-22-validation-v1'
REVIEW_SCHEMA = 'csr-matlab-tranche-22-return-review-v1'
PIN = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
ENGINE_PIN = '6b5cd24ea80713ce16d88575869aedd6f432bdae'
CANDIDATE = 'evidence/tranche-22-candidate.json'
BASELINE = 'evidence/tranche-22-baseline.json'
BASELINE_SHA = '3b0fd01057f1d498759331d9db024a1fce8df5d51e1b1ba9d8d0531e96c9a428'
PARENT_SHA = 'ba4cedf3551a0bc1fe31385108e1f33011d1c97211bba993b6061a2de31389c1'
ACCEPTANCE_SHA = '69d9bafef93c64a674e8226a434c7c1a5d3b7ebb6f6f2fb76e64461fc497bc28'
PLAN = 'scenarios/t22/plan.json'
ACTIONS = 'scenarios/t22/actions.csv'
CASES = 'scenarios/t22/cases.csv'
CONTRACT = 'scenarios/t22/contract.json'
REFERENCE = 'evidence/t22/native'
CASE_IDS = ('clean_growth_boundary','retried_third_ack','retried_second_ack','dack_hold_20','dack_hold_40',
    'final_failure_floor','ceiling_global_capacity','grouped_feedback_order','seed130_feedback_motif')
CASE_FIELDS = ('case_id','resend_seconds','max_resends','dack_seconds','tic_seconds','pending_threshold',
    'flow_threshold_max','policy','scope')
TEST_FILES = ['tests/TestAdaptiveWindowContract.m','tests/TestEventScheduler.m','tests/TestHopLayer.m',
    'tests/TestHopControls.m','tests/TestQueuedRetryPolicy.m','tests/TestMacHopCustody.m']
ACTION_FIELDS = ('case_id','step','time_s','action','packet','peer','ack_packets','dack_packets','note')
STATE_FIELDS = ('case_id','step','time_s','action','packet','peer','accepted','threshold','ack_count',
    'outstanding','global_pending','dack_holds','resend','can_send','ack_total','dack_total','fail_total',
    'nsdp_release_total','retry_total','tx_total','dack_expired_total')
TEXT_FIELDS = ('case_id','action','packet')
TIME_TOLERANCE = Decimal('0.000000001')
LIMITATIONS = [
    'Owner-returned hashes and rows bind evidence claims; they do not independently prove MATLAB execution.',
    'This is a controlled HOP-layer event replay, not a real-PHY or full-campus simulation.',
    'The exact deterministic state contract is distinct from the descriptive +/-10% campus target.',
    'Production sources, actual-tx retry expiration, continuous timing and PHY/ECC remain unchanged.',
    'Known queued-retry expiration differences are not erased by selecting this bounded event tape.',
    'Matching callbacks does not establish the cause of different stochastic full-campus histories.',
]


def source_map(value, label):
    return {name: row['sha256'] for name, row in record_map(value, label).items()}


def verify_baseline(source_root, candidate, metadata=None):
    require(candidate.get('BaselineSourceSnapshot') == BASELINE
            and candidate.get('BaseSourceSnapshotSHA256') == sha256(source_root/BASELINE) == BASELINE_SHA,
            'Accepted T20 source snapshot identity mismatch')
    baseline = record_map(json_value(source_root/BASELINE), 'T20 source baseline')
    require(len(baseline) == 376 and sum(path.endswith('.m') for path in baseline) == 175,
            'Accepted T20 source membership changed')
    for name, row in baseline.items():
        require(sha256(safe_path(source_root,name)) == row['sha256'],
                'Previously accepted T20 source changed: '+name)
    expected = (('BaselineCandidate','evidence/t20/candidate.json',PARENT_SHA),
                ('BaselineAcceptance','evidence/t20/acceptance.json',ACCEPTANCE_SHA))
    for field, path, digest in expected:
        require(candidate.get(field) == path and candidate.get(field+'SHA256') == sha256(source_root/path) == digest,
                'T20 accepted provenance mismatch: '+field)
    require(sha256(source_root/'evidence/t20/source.json') == BASELINE_SHA,
            'T20 copied source snapshot mismatch')
    accepted = json_object(source_root/'evidence/t20/acceptance.json')
    require(accepted.get('accepted') is True and accepted.get('source_snapshot_sha256') == BASELINE_SHA
            and accepted.get('candidate_sha256') == PARENT_SHA and accepted.get('tests_passed') == 716,
            'T20 acceptance does not bind the accepted source/test identity')
    require(candidate.get('AllowedModifiedSourceFiles') == [], 'T22 cannot modify accepted production source')
    if metadata is not None:
        require(metadata.get('AllBaselineSourcesUnchanged') is True
                and integer(metadata.get('BaselineSourceFilesVerified'),'baseline sources') == 376
                and integer(metadata.get('BaselineMatlabFilesVerified'),'baseline MATLAB') == 175,
                'Returned T20 source verification counters disagree')
    return {'source_files':376,'matlab_files':175,'all_unchanged':True,'source_snapshot_sha256':BASELINE_SHA}


def verify_references(source_root, candidate):
    names = candidate.get('ReferenceFiles')
    require(candidate.get('ReferenceRoots') == [] and isinstance(names,list) and names == sorted(set(names)) and names,
            'T22 requires distinct sorted explicit reference membership')
    entries = record_map(candidate.get('ReferenceFileInventory'),'candidate references',sizes=True)
    require(set(names) == set(entries), 'Reference paths/inventory membership mismatch')
    required = {BASELINE,'evidence/t20/source.json','evidence/t20/candidate.json','evidence/t20/acceptance.json',
                'evidence/tranche-14-native-build.json'}
    inherited = record_map(json_object(source_root/'evidence/t20/candidate.json')['ReferenceFileInventory'],
                           'accepted T20 references',sizes=True)
    require(len(inherited) == 98 and all(entries.get(name) == row for name,row in inherited.items()),
            'Accepted T20 reference inventory changed or was omitted')
    required.update(f'{REFERENCE}/{name}' for name in all_files(source_root/REFERENCE))
    require(required <= set(entries), 'Required accepted/native reference membership missing')
    for name, row in entries.items():
        path = safe_path(source_root,name)
        require(path.is_file() and path.stat().st_size == row['bytes'] and sha256(path) == row['sha256'],
                'Reference hash or size mismatch: '+name)
    return entries


def verify_actions(actions, case_ids):
    require(isinstance(case_ids,list) and case_ids and len(set(case_ids)) == len(case_ids),
            'Missing/duplicate case membership')
    require(actions, 'Empty action tape')
    current, previous_time, steps, aliases = -1, Decimal(0), 0, set()
    counts = {}
    for row in actions:
        require(tuple(row) == ACTION_FIELDS, 'Unexpected action CSV schema')
        case = row['case_id']
        require(case in case_ids, 'Unknown action case: '+case)
        position = case_ids.index(case)
        if position != current:
            require(position == current+1, 'Missing/reordered action case')
            current, previous_time, steps, aliases = position, Decimal(0), 0, set()
        steps += 1
        require(integer(row['step'],'action step',1) == steps, 'Missing/duplicate/reordered action step')
        time = number(row['time_s'],'action time',minimum=0)
        require(time >= previous_time, 'Action time moves backwards')
        previous_time = time
        action, packet = row['action'], row['packet']
        require(action in ('SEND','TX','FEEDBACK','PROBE'), 'Unknown action')
        require(integer(row['peer'],'action peer',1) in (8,9), 'Unexpected contract peer')
        if action == 'SEND':
            require(packet and packet not in aliases and ';' not in packet, 'Duplicate/invalid SEND alias')
            aliases.add(packet)
        elif action == 'TX':
            require(packet in aliases, 'TX alias was not offered')
        else:
            require(packet == '', 'Nonpacket action has packet alias')
        for field in ('ack_packets','dack_packets'):
            tokens = row[field].split(';') if row[field] else []
            require(len(tokens) == len(set(tokens)) and all(token in aliases for token in tokens),
                    'Unknown/duplicate feedback alias')
            require(action == 'FEEDBACK' or not tokens, 'Feedback aliases on another action')
        counts[case] = steps
    require(current == len(case_ids)-1 and set(counts) == set(case_ids), 'Missing planned case actions')
    return counts


def validate_checkpoints(rows, actions, label):
    """Require every action in exact order; never align away missing/shifted rows."""
    require(len(rows) == len(actions), label+': missing/extra checkpoint rows')
    parsed, previous, accepted = [], {}, {}
    for row, action in zip(rows, actions):
        require(tuple(row) == STATE_FIELDS, label+': unexpected checkpoint CSV schema')
        for field in TEXT_FIELDS:
            require(row[field] == action[field], label+': checkpoint action/case/packet mismatch')
        require(integer(row['step'],'checkpoint step',1) == integer(action['step'],'action step',1)
                and integer(row['peer'],'checkpoint peer',1) == integer(action['peer'],'action peer',1),
                label+': checkpoint step/peer mismatch')
        values = {field: row[field] for field in TEXT_FIELDS}
        values['time_s'] = number(row['time_s'],'checkpoint time',minimum=0)
        require(abs(values['time_s']-number(action['time_s'],'action time',minimum=0)) <= TIME_TOLERANCE,
                label+': checkpoint action time mismatch')
        for field in STATE_FIELDS:
            if field in (*TEXT_FIELDS,'time_s'):
                continue
            values[field] = integer(row[field],label+' '+field,-1 if field == 'accepted' else 0)
        require(values['accepted'] in (0,1) if action['action'] == 'SEND' else values['accepted'] == -1,
                label+': invalid accepted sentinel')
        require(values['can_send'] in (0,1) and values['threshold'] <= 16 and values['ack_count'] <= 2,
                label+': invalid admission/threshold state')
        require(values['outstanding'] <= values['global_pending']
                and values['global_pending'] == values['resend']+values['dack_holds'],
                label+': inconsistent retained ownership bounds')
        require(values['can_send'] == int(values['outstanding'] <= values['threshold'] and values['global_pending'] <= 16),
                label+': admission does not obey neighbor/global capacity')
        accepted[row['case_id']] = accepted.get(row['case_id'],0)+int(values['accepted'] == 1)
        require(accepted[row['case_id']] == values['ack_total']+values['dack_total']+values['fail_total']+values['resend'],
                label+': accepted DATA identity conservation failed')
        cumulative = ('ack_total','dack_total','fail_total','nsdp_release_total','retry_total','tx_total','dack_expired_total')
        old = previous.get(row['case_id'])
        if old is not None:
            require(all(values[field] >= old[field] for field in cumulative), label+': cumulative counter decreased')
        require(values['nsdp_release_total'] == values['ack_total']+values['dack_total']+values['fail_total'],
                label+': NWK custody release counter does not reconcile')
        require(values['dack_expired_total'] <= values['dack_total'], label+': more DACK expirations than DACKs')
        previous[row['case_id']] = values
        parsed.append(values)
    return parsed


def compare_checkpoints(actual, reference):
    require(len(actual) == len(reference), 'MATLAB/native checkpoint membership mismatch')
    differences = []
    nonzero_time = 0
    maximum_delta = Decimal(0)
    for index, (left,right) in enumerate(zip(actual,reference),1):
        fields = []
        for field in STATE_FIELDS:
            if field == 'time_s':
                delta = abs(left[field]-right[field])
                maximum_delta = max(maximum_delta,delta)
                nonzero_time += int(delta != 0)
                equal = delta <= TIME_TOLERANCE
            else:
                equal = left[field] == right[field]
            if not equal:
                fields.append(field)
        if fields:
            differences.append({'row':index,'case_id':left['case_id'],'step':left['step'],'fields':fields,
                'matlab':{key:str(left[key]) if isinstance(left[key],Decimal) else left[key] for key in fields},
                'native':{key:str(right[key]) if isinstance(right[key],Decimal) else right[key] for key in fields}})
    return {'matches_native':not differences,'actual_rows':len(actual),'reference_rows':len(reference),
        'matched_rows':len(actual)-len(differences),'unmatched_rows':len(differences),
        'nonzero_time_differences':nonzero_time,'maximum_time_difference_s':str(maximum_delta),
        'time_tolerance_s':str(TIME_TOLERANCE),'differences':differences}


def verify_milestones(rows, contract, label):
    lookup = {(row['case_id'],row['step']):row for row in rows}
    require(len(lookup) == len(rows), label+': duplicate milestone checkpoint identity')
    milestones = contract.get('milestones')
    require(isinstance(milestones,list) and milestones, 'Missing independent milestone constraints')
    seen, checks = set(), 0
    for item in milestones:
        key = (item.get('case_id'),integer(item.get('step'),'milestone step',1))
        require(key in lookup and key not in seen, 'Unknown/duplicate milestone checkpoint')
        seen.add(key)
        fields = item.get('equals')
        require(isinstance(fields,dict) and fields and set(fields) <= set(STATE_FIELDS[6:]),
                'Unsupported independent milestone fields')
        for field, expected in fields.items():
            expected = integer(expected,'milestone '+field,-1 if field == 'accepted' else 0)
            require(lookup[key][field] == expected,
                    f'{label}: independent milestone mismatch: {key[0]}/{key[1]} {field}')
            checks += 1
    return {'milestones':len(milestones),'integer_assertions':checks}


def verify_native_raw(directory, checkpoints, case_ids):
    """Reconstruct exported completion counters from ordered production records."""
    raw_fields = STATE_FIELDS[:14]+('nsdp_release_total','live_retry_sum','tx_total')
    derived_fields = ('ack_total','dack_total','fail_total','retry_total','dack_expired_total')
    total_events = 0
    counts = {}
    for case in case_ids:
        expected = [row for row in checkpoints if row['case_id'] == case]
        states = csv_rows(directory/'raw'/case/'states.csv',raw_fields)
        trace = csv_rows(directory/'raw'/case/'trace.csv')
        require(len(states) == len(expected) and trace, 'Incomplete native raw checkpoint/trace population')
        tally = {'ack':0,'dack':0,'no_ack':0}
        completed, releases = set(), set()
        retired_retries, expired, position = 0, 0, 0
        previous_time, previous_index = Decimal(0), -1
        for event in trace:
            require(event.get('schema') == 'csr-differential-trace-v1', 'Unexpected native raw trace schema')
            event_time = number(event.get('time_s'),'native raw time',minimum=0)
            event_index = integer(event.get('event_index'),'native raw event index')
            require(event_time >= previous_time and event_index > previous_index,
                    'Native raw event time/index is not ordered')
            previous_time,previous_index = event_time,event_index
            total_events += 1
            kind = event['event']
            if kind == 'hop_completion':
                require(event['node'] == '7' and event['packet_type'] == 'data' and event['src'] == '7'
                        and event['dst'] == '1', 'Unexpected native completion population')
                key = (event['peer'],event['sequence'])
                reason = event['reason']
                require(key not in completed and reason in tally, 'Duplicate/unsupported native completion')
                completed.add(key)
                tally[reason] += 1
                details = {}
                for value in event['detail'].split(';'):
                    if '=' not in value:
                        continue
                    name,detail = value.split('=',1)
                    require(name not in details, 'Duplicate native completion detail key')
                    details[name] = detail
                retired_retries += integer(details.get('resend_count'),'completed native retry count')
            elif kind == 'hop_capacity_release':
                key = (event['peer'],event['sequence'])
                require(event['node'] == '7' and event['reason'] == 'dack_expiry' and key not in releases,
                        'Duplicate/unsupported native capacity release')
                releases.add(key)
                expired += 1
            elif kind == 't22_checkpoint':
                require(position < len(states) and event['node'] == '7'
                        and integer(event['sequence'],'native marker step',1) == position+1,
                        'Missing/duplicate native checkpoint marker')
                raw, row = states[position], expected[position]
                require(abs(event_time-row['time_s']) <= TIME_TOLERANCE, 'Native checkpoint marker clock mismatch')
                for field in raw_fields:
                    if field == 'live_retry_sum':
                        continue
                    value = raw[field] if field in TEXT_FIELDS else (
                        number(raw[field],field,minimum=0) if field == 'time_s'
                        else integer(raw[field],field,-1 if field == 'accepted' else 0))
                    require(abs(value-row[field]) <= TIME_TOLERANCE if field == 'time_s' else value == row[field],
                            'Native checkpoint differs from raw state: '+field)
                computed = (tally['ack'],tally['dack'],tally['no_ack'],
                            retired_retries+integer(raw['live_retry_sum'],'native live retry sum'),expired)
                require(all(row[field] == value for field,value in zip(derived_fields,computed)),
                        'Native checkpoint does not reconcile with ordered completion trace')
                require(row['dack_holds'] == tally['dack']-expired,
                        'Native retained DACK capacity does not reconcile with expiry trace')
                position += 1
        require(position == len(states), 'Missing final native checkpoint marker')
        counts[case] = {'checkpoints':position,'ack':tally['ack'],'dack':tally['dack'],
                       'failed':tally['no_ack'],'dack_expired':expired}
    return {'trace_events':total_events,'cases':counts,'all_raw_states_and_completions_reconciled':True}


def verify_native(source_root, actions, cases, contract):
    directory = source_root/REFERENCE
    manifest = json_object(directory/'manifest.json')
    require(manifest.get('schema') == 'csr-tranche22-native-files-v1' and isinstance(manifest.get('files'),dict),
            'Native manifest schema mismatch')
    entries = record_map([{'path':name,'sha256':digest} for name,digest in manifest['files'].items()],
                         'native manifest')
    require(set(entries) == all_files(directory)-{'manifest.json'}, 'Native reference inventory is not closed')
    for name,row in entries.items():
        require(sha256(safe_path(directory,name)) == row['sha256'], 'Native reference hash mismatch: '+name)
    summary = json_object(directory/'summary.json')
    require(summary.get('schema') == 'csr-tranche22-native-reference-v1' and summary.get('status') == 'passed'
            and summary.get('source_pin') == PIN and summary.get('engine_pin') == ENGINE_PIN
            and summary.get('native_executed') is True and summary.get('matlab_executed') is False
            and summary.get('production_source_unchanged') is True and summary.get('engine_source_unchanged') is True,
            'Native execution/source status mismatch')
    require(summary.get('case_count') == len(cases) and summary.get('checkpoint_count') == len(actions)
            and summary.get('milestone_count') == len(contract['milestones'])
            and number(summary.get('time_resolution_seconds'),'native time resolution') == TIME_TOLERANCE,
            'Native execution membership/time resolution mismatch')
    bindings = summary.get('input_bindings')
    expected_inputs = {path.relative_to(source_root).as_posix():sha256(path)
                       for path in (source_root/'scenarios/t22').iterdir() if path.is_file()}
    require(bindings == expected_inputs, 'Native executed input bindings differ from frozen inputs')
    fixtures = summary.get('fixture_sources')
    fixture_files = ('scripts/ns3/tranche22_window.cc','scripts/run_tranche22_ns3_reference.py')
    require(fixtures == {name:sha256(source_root/name) for name in fixture_files}, 'Native fixture source binding mismatch')
    baseline_build = json_object(source_root/'evidence/tranche-14-native-build.json')
    expected_model = source_map(baseline_build.get('module_files'),'native source module')
    require(summary.get('model_sources') == expected_model, 'Native production module hashes differ from pinned model')
    build = verify_native_build(directory,summary,baseline_build)
    commands = summary.get('commands')
    require(isinstance(commands,list) and len(commands) == 2, 'Missing native compile/run command evidence')
    for command in commands:
        require(isinstance(command,dict) and isinstance(command.get('argv'),list) and command['argv']
                and integer(command.get('exit_code'),'native exit code') == 0
                and command.get('log_sha256') == sha256(safe_path(directory,command.get('log'))),
                'Native command completion/log binding mismatch')
        number(command.get('wall_seconds'),'native command duration',minimum=0)
    require(summary.get('seams_sha256') == sha256(directory/'seams.patch'), 'Native fixture seam binding mismatch')
    rows = validate_checkpoints(csv_rows(directory/'checkpoints.csv',STATE_FIELDS),actions,'native')
    milestones = verify_milestones(rows,contract,'native')
    raw = verify_native_raw(directory,rows,[case['case_id'] for case in cases])
    require(summary.get('cases') == raw['cases'], 'Native summary completion counts differ from raw trace')
    return {'checkpoints':rows,'case_count':len(cases),'checkpoint_count':len(rows),'raw':raw,
            'milestones':milestones,'build':build,'checkpoints_sha256':sha256(directory/'checkpoints.csv'),
            'summary_sha256':sha256(directory/'summary.json')}


def verify_native_build(directory, summary, baseline_build):
    require(summary.get('build_manifest') == 'build.json'
            and summary.get('build_manifest_sha256') == sha256(directory/'build.json'),
            'Native execution does not bind the final build receipt')
    build = json_object(directory/'build.json')
    require(build.get('schema') == 'csr-tranche22-native-build-v1' and build.get('status') == 'passed'
            and build.get('source_pin') == PIN and build.get('engine_pin') == ENGINE_PIN
            and build.get('source_tree') == baseline_build.get('source_tree')
            and build.get('engine_tree') == baseline_build.get('engine_tree')
            and build.get('engine_rebuilt') is True and build.get('reused_historical_libraries') is False
            and build.get('production_source_unchanged') is True and build.get('engine_source_unchanged') is True,
            'Native build/source/engine identity mismatch')
    require(build.get('assertions') is True and build.get('logging') is True and build.get('build_profile') == 'Debug'
            and build.get('cxx_standard') == 23 and build.get('linked_libraries_verified_elf') is True,
            'Native build configuration or linked ELF verification mismatch')
    archives = json_object(directory/'archive-verification.json')
    require(archives == build.get('archives') and set(archives) == {'source','engine'},
            'Native archive tree receipts disagree')
    for kind,row in archives.items():
        require(row.get('git_tree_verified') is True and row.get('git_tree_sha') == build.get(kind+'_tree')
                and integer(row.get('bytes'),'native source archive bytes',1) > 0,
                'Native source archive tree identity missing')
        record_map([{'path':kind,'sha256':row.get('sha256')}],'native archive digest')
    for key,name in (('tracked_source_verification','tracked-source-verification.json'),
                     ('elf_verification','elf-verification.json'),('archive_tree_verifier','verify_archive_trees.py')):
        require(build.get(key) == name and build.get(key+'_sha256') == sha256(directory/name),
                'Native build verification receipt binding mismatch: '+key)
    tracked = json_object(directory/'tracked-source-verification.json')
    require(set(tracked) == {'source','engine'}, 'Missing tracked source/engine inventory')
    for kind,row in tracked.items():
        require(row.get('archive_tracked_files_unchanged') is True and isinstance(row.get('file_sha256'),dict)
                and len(row['file_sha256']) == integer(row.get('file_count'),'tracked source files',1),
                'Native tracked source stability inventory mismatch')
        record_map([{'path':name,'sha256':digest} for name,digest in row['file_sha256'].items()],
                   'tracked '+kind)
    require(all(tracked['source']['file_sha256'].get(name) == digest for name,digest in summary['model_sources'].items()),
            'Tracked native module identity differs from executed module')
    libraries = build.get('libraries')
    require(isinstance(summary.get('libraries'),dict) and set(summary['libraries']) ==
            {'csr','spectrum','buildings','propagation','mobility','antenna','network','stats','core'},
            'Native linked module membership differs')
    expected = {f'libns3-dev-{name}-debug.so':digest for name,digest in summary['libraries'].items()}
    require(libraries == expected, 'Native execution library hashes differ from final build')
    record_map([{'path':name,'sha256':digest} for name,digest in expected.items()],'native libraries')
    elf = json_object(directory/'elf-verification.json')
    require(elf.get('passed') is True and elf.get('zero_object_files') == [] and isinstance(elf.get('libraries'),dict)
            and set(elf['libraries']) == set(expected), 'Linked native ELF verification incomplete')
    for name,row in elf['libraries'].items():
        require(row.get('sha256') == expected[name] and row.get('elf_shared_object') is True
                and integer(row.get('bytes'),'ELF library bytes',1) > 0
                and integer(row.get('defined_dynamic_symbols'),'ELF dynamic symbols',1) > 0,
                'Native ELF identity or symbols invalid')
    attempts = build.get('build_attempts')
    require(isinstance(attempts,list) and attempts and isinstance(build.get('configure'),dict)
            and integer(attempts[-1].get('exit_code'),'final native build status') == 0
            and integer(build['configure'].get('exit_code'),'native configure status') == 0,
            'Native final build/configure did not complete successfully')
    for command in [build['configure'],*attempts]:
        require(isinstance(command.get('argv'),list) and command['argv']
                and command.get('log_sha256') == sha256(safe_path(directory,command.get('log'))),
                'Native build command/log binding mismatch')
        integer(command.get('exit_code'),'native build attempt status')
    return {'build_sha256':sha256(directory/'build.json'),'source_tree':build['source_tree'],
            'engine_tree':build['engine_tree'],'linked_libraries':len(expected),'engine_rebuilt':True,
            'recorded_incomplete_build_attempts':sum(row['exit_code'] != 0 for row in attempts)}


def verify_plan_and_native(source_root, candidate):
    require(candidate.get('Plan') == PLAN and candidate.get('PlanSHA256') == sha256(source_root/PLAN),
            'Replay plan path/hash mismatch')
    plan = json_object(source_root/PLAN)
    require(plan.get('schema') == 'csr-tranche22-adaptive-window-plan-v1' and plan.get('tranche') == 22
            and plan.get('source_commit') == PIN and plan.get('engine_commit') == ENGINE_PIN
            and plan.get('case_order') == list(CASE_IDS) and plan.get('case_count') == 9
            and plan.get('action_count') == 364 and plan.get('checkpoint_count') == 364
            and plan.get('milestone_count') == 38 and plan.get('native_reference') == REFERENCE,
            'Replay plan identity/membership mismatch')
    require(plan.get('timing_policy') == 'continuous' and plan.get('default_policy') == 'actual-tx'
            and plan.get('working_campus_band_percent') == 10
            and all(plan.get(field) is False for field in ('production_source_changed','phy_ecc_changed','full_campus_run')),
            'Replay plan changes production policy/scope')
    for stem,path in (('cases',CASES),('actions',ACTIONS),('contract',CONTRACT)):
        require(plan.get(stem+'_file') == path and plan.get(stem+'_sha256') == sha256(source_root/path),
                'Replay input hash/path mismatch: '+stem)
    contract = json_object(source_root/CONTRACT)
    require(contract.get('schema') == 'csr-tranche22-controlled-hop-contract-v1'
            and contract.get('case_count') == 9 and contract.get('action_count') == 364,
            'Controlled contract identity/membership mismatch')
    for item in (plan,contract):
        require(item.get('action_columns') == list(ACTION_FIELDS) and item.get('state_columns') == list(STATE_FIELDS)
                and item.get('configuration_columns') == list(CASE_FIELDS), 'Frozen contract columns changed')
        compare = item.get('comparison')
        require(isinstance(compare,dict) and compare.get('integer_tolerance') == 0
                and number(compare.get('time_absolute_tolerance_seconds'),'time tolerance') == TIME_TOLERANCE
                and compare.get('campus_percent_target_applies') is False, 'Controlled-state tolerance changed')
    input_names = {'cases.csv','actions.csv','seed130-provenance.json'}
    require(set(contract.get('input_hashes',{})) == input_names, 'Contract input provenance membership changed')
    for name,digest in contract['input_hashes'].items():
        require(sha256(source_root/'scenarios/t22'/name) == digest, 'Contract input hash mismatch: '+name)
    plan_inputs = source_map(plan.get('input_files'),'plan inputs')
    require(set(plan_inputs) == {CASES,ACTIONS,CONTRACT,'scenarios/t22/seed130-provenance.json'},
            'Replay plan input membership changed')
    for path,digest in plan_inputs.items():
        require(sha256(safe_path(source_root,path)) == digest, 'Replay plan input binding mismatch')
    provenance = json_object(source_root/'scenarios/t22/seed130-provenance.json')
    verify_seed130_provenance(source_root,provenance)
    cases = csv_rows(source_root/CASES,CASE_FIELDS)
    require([row['case_id'] for row in cases] == list(CASE_IDS), 'Missing/duplicate/reordered case configuration')
    for case in cases:
        require(case['policy'] == 'actual-tx' and case['scope'], 'Controlled case policy/scope mismatch')
        for field,expected in (('resend_seconds',2),('max_resends',2),('dack_seconds',20),
                               ('pending_threshold',16),('flow_threshold_max',16)):
            require(number(case[field],field) == expected, 'Controlled default configuration changed: '+field)
        require(abs(number(case['tic_seconds'],'TIC',minimum=0)-Decimal(1)/Decimal(36_000_000)) <= Decimal('1e-23'),
                'Controlled default TIC changed')
    actions = csv_rows(source_root/ACTIONS,ACTION_FIELDS)
    require(len(actions) == 364 and len(contract.get('milestones',[])) == 38, 'Controlled workload/milestones changed')
    verify_actions(actions,list(CASE_IDS))
    native = verify_native(source_root,actions,cases,contract)
    plan = dict(plan,contract=contract)
    return plan,actions,cases,native


def verify_seed130_provenance(source_root, provenance):
    source = 'evidence/tranche-20-ns3-reference/s130/ns3-trace.csv.gz'
    require(provenance.get('schema') == 'csr-tranche22-seed130-motif-provenance-v1'
            and provenance.get('source_pin') == PIN and provenance.get('accepted_candidate_sha256') == PARENT_SHA
            and provenance.get('input_path') == source and provenance.get('input_gzip_sha256') == sha256(source_root/source),
            'Historical feedback motif provenance mismatch')
    events = provenance.get('events')
    require(isinstance(events,list) and events, 'Missing historical feedback motif events')
    event_fields = ('schema','event_index','time_s','event','node','peer','packet_type','src','dst','sequence',
                    'success','reason','next_hop','detail')
    require(all(isinstance(row,dict) and set(row) == set(event_fields) for row in events),
            'Historical motif event projection schema changed')
    indices = [integer(row.get('event_index'),'historical event index') for row in events]
    require(indices == sorted(set(indices)), 'Historical motif events are missing/duplicated/reordered')
    found = []
    wanted = set(indices)
    with gzip.open(source_root/source,'rt',newline='') as stream:
        for row in csv.DictReader(stream):
            index = integer(row['event_index'],'historical input event index')
            if index in wanted:
                found.append({field:row[field] for field in event_fields})
            if index >= indices[-1]:
                break
    require(found == events, 'Historical motif events differ from pinned campus trace')
    motif = provenance.get('motif')
    require(isinstance(motif,dict), 'Missing historical motif identity')
    paired = [row for row in events if integer(row['event_index'],'historical event index') in motif.get('ordered_group_event_indices',[])]
    require(len(paired) == 2 and [integer(row['event_index'],'index') for row in paired] == motif['ordered_group_event_indices']
            and all(row['event'] == 'hop_completion' and row['reason'] == 'ack' and row['node'] == '7'
                    and row['peer'] == '8' and row['src'] == '7' and row['dst'] == '1' for row in paired),
            'Historical newer-clean/older-retry completion order is unbound')
    details = [dict(piece.split('=',1) for piece in row['detail'].split(';') if '=' in piece) for row in paired]
    require(integer(details[0].get('resend_count'),'clean retry') == 0
            and integer(details[1].get('resend_count'),'retried retry',1) > 0
            and integer(paired[1]['sequence'],'historical old packet') == motif.get('old_retried_application_sequence')
            and integer(details[0].get('threshold_after'),'clean threshold') == motif.get('clean_completion_threshold_after') == 3
            and integer(details[1].get('threshold_after'),'retry threshold') == motif.get('retried_completion_threshold_after') == 3,
            'Historical feedback motif does not exhibit the declared clean/retried threshold sequence')
    return {'events':len(events),'pinned_raw_events_match':True}


def verify_summary(summary, metadata, comparison, case_count):
    expected = {'CaseCount':case_count,'CheckpointCount':comparison['actual_rows'],
                'FailedCount':comparison['unmatched_rows']}
    passed = comparison['matches_native']
    require(summary.get('DiagnosticCompleted') is True and summary.get('Passed') is passed,
            'Contract completion/pass flags disagree with independently compared rows')
    for field,count in expected.items():
        require(integer(summary.get(field),field) == count, 'Contract summary count disagrees: '+field)
        require(integer(metadata.get('Contract'+field),'Contract'+field) == count,
                'Metadata contract count disagrees: '+field)
    require(metadata.get('ContractCompleted') is True and metadata.get('ContractPassed') is passed,
            'Metadata contract completion/pass disagreement')
    native = summary.get('NativeComparison')
    require(isinstance(native,dict) and native.get('ReferencePresent') is True and native.get('SchemaMatches') is True,
            'Missing native comparison receipt')
    for field,key in (('ActualRows','actual_rows'),('ReferenceRows','reference_rows'),('MatchedRows','matched_rows'),
                      ('UnmatchedRows','unmatched_rows')):
        require(integer(native.get(field),field) == comparison[key],
                'Native comparison receipt count disagrees: '+field)
    failed = native.get('FailedRows')
    if not isinstance(failed,list):
        failed = [failed]  # MATLAB may encode a scalar numeric vector as one number.
    failed = [integer(row,'failed checkpoint row',1) for row in failed]
    require(failed == [row['row'] for row in comparison['differences']],
            'Native comparison failed-row identity disagrees')
    require(passed, 'Controlled contract differs from pinned native state; review required')
    return expected


def verify_identity(root, metadata, source_root, candidate):
    require(metadata.get('Schema') == SCHEMA and metadata.get('Tranche') == 22
            and metadata.get('Status') == 'completed-review-required', 'Return is not a completed T22 contract')
    require(metadata.get('CandidateFile') == CANDIDATE
            and metadata.get('CandidateSHA256') == sha256(source_root/CANDIDATE) == sha256(root/'candidate.json')
            and sha256(root/'plan.json') == candidate['PlanSHA256'], 'Candidate/plan return binding mismatch')
    runtime = metadata.get('Runtime')
    require(isinstance(runtime,dict) and runtime.get('Runtime') == 'MATLAB'
            and runtime.get('DefaultBackend') == 'portable'
            and all(isinstance(runtime.get(key),str) and runtime[key] for key in ('Version','Release')),
            'Missing portable MATLAB runtime/release')
    require(metadata.get('MATLABExecuted') is True and metadata.get('NativeExecuted') is False
            and metadata.get('SourceCommit') == PIN and metadata.get('FocusedGateExecuted') is True
            and all(metadata.get(key) is False for key in
                    ('FullAcceptanceGateExecuted','AcceptanceEstablished','NumericalParityEstablished'))
            and integer(metadata.get('WorkingCampusBandPercent'),'working band') == 10,
            'Execution/source/scope claims mismatch')
    require(t17.timestamp(metadata.get('StartedUTC'),'start') <= t17.timestamp(metadata.get('CompletedUTC'),'completion'),
            'Owner completion precedes start')
    return runtime


def verify_preparation(source_root):
    source_root = Path(source_root).resolve()
    candidate = json_object(source_root/CANDIDATE)
    require(candidate.get('Schema') == 'csr-tranche-22-candidate-v1' and candidate.get('Tranche') == 22
            and candidate.get('SourceCommit') == PIN and candidate.get('EngineCommit') == ENGINE_PIN,
            'T22 candidate identity mismatch')
    require(candidate.get('DataQueuedRetryPolicy') == 'actual-tx' and candidate.get('TimingPolicy') == 'continuous'
            and candidate.get('WorkingCampusBandPercent') == 10 and candidate.get('MATLABExecutionPending') is True
            and all(candidate.get(field) is False for field in ('FullPortableRegression','FullCampusRun','PHYExecuted',
                 'ProductionSourceChanged','MATLABExecuted','AcceptanceEstablished','NumericalParityEstablished')),
            'T22 candidate policy/scope mismatch')
    require(candidate.get('NativeReference') == REFERENCE+'/checkpoints.csv'
            and candidate.get('NativeReferenceSHA256') == sha256(source_root/REFERENCE/'checkpoints.csv'),
            'Candidate native state reference binding mismatch')
    source = candidate_snapshot(source_root)
    require(candidate.get('SourceFilesExcludedPaths') == [CANDIDATE]
            and source_map(candidate.get('SourceFiles'),'candidate source') ==
                {name:digest for name,digest in source.items() if name != CANDIDATE},
            'Frozen source membership/hash mismatch')
    names = selected_test_names(source_root,candidate.get('TestFiles'))
    require(candidate.get('ExpectedTestNames') == names and candidate.get('TestFiles') == TEST_FILES,
            'Frozen focused test membership mismatch')
    baseline = verify_baseline(source_root,candidate)
    references = verify_references(source_root,candidate)
    plan, actions, cases, native = verify_plan_and_native(source_root,candidate)
    require(candidate.get('ExpectedCaseCount') == len(cases) and candidate.get('ExpectedCheckpointCount') == len(actions),
            'Candidate case/checkpoint count differs from plan')
    return {'source':source,'references':references,'baseline':baseline,'plan':plan,'actions':actions,
        'cases':cases,'native':native,'planned_matlab_tests':len(names),'planned_cases':len(cases),
        'planned_checkpoints':len(actions),'matlab_executed':False}


def verify_contract(root, metadata, source_root, prepared):
    directory = root/'contract'
    for name, expected in (('actions.csv',ACTIONS),('cases.csv',CASES)):
        require(sha256(directory/name) == sha256(source_root/expected), 'Returned contract input changed: '+name)
    rows = csv_rows(directory/'checkpoints.csv',STATE_FIELDS)
    actual = validate_checkpoints(rows,prepared['actions'],'MATLAB')
    comparison = compare_checkpoints(actual,prepared['native']['checkpoints'])
    summary = json_object(directory/'summary.json')
    require(summary.get('Schema') == 'csr-tranche22-adaptive-window-contract-v1'
            and summary.get('ActionsSHA256') == sha256(source_root/ACTIONS)
            and summary.get('CasesSHA256') == sha256(source_root/CASES)
            and summary.get('NativeReferenceSHA256') == sha256(source_root/REFERENCE/'checkpoints.csv')
            and summary.get('DataQueuedRetryPolicy') == 'actual-tx',
            'Contract summary source/reference/policy binding mismatch')
    verify_summary(summary,metadata,comparison,len(prepared['cases']))
    verify_milestones(actual,prepared['plan']['contract'],'MATLAB')
    return {'case_count':len(prepared['cases']),'checkpoint_count':len(actual),
            'native_comparison':comparison,'scope':'Controlled production HOP callback replay; no real PHY/campus run'}


def review(evidence, source_root, output):
    evidence,source_root,output = t17.output_location(evidence,source_root,output)
    prepared = verify_preparation(source_root)
    candidate = json_object(source_root/CANDIDATE)
    with t17.evidence_directory(evidence) as root:
        require(evidence.is_dir() or not (root/'t22.zip').exists(), 'Unexpected nested return archive')
        metadata = json_object(root/'metadata.json')
        runtime = verify_identity(root,metadata,source_root,candidate)
        inventory(root,metadata.get('Artifacts'),excluded=('metadata.json','t22.zip'))
        source = verify_sources(root,metadata,source_root)
        references = t17.verify_references(root,metadata,prepared['references'])
        baseline = verify_baseline(source_root,candidate,metadata)
        tests = verify_tests(root,metadata,source_root,candidate)
        contract = verify_contract(root,metadata,source_root,prepared)
        result = {'schema':REVIEW_SCHEMA,'status':'controlled_contract_review_completed',
            'evidence_integrity_verified':True,'focused_structural_gate_completed':True,
            'full_structural_gate_completed':False,'acceptance_established':False,
            'numerical_parity_established':False,'working_campus_band_percent':10,
            'matlab_executed_by_reviewer':False,'runtime':runtime,'source':source,'references':references,
            'baseline':baseline,'tests':tests,'contract':contract,
            'metadata_sha256':sha256(root/'metadata.json'),'limitations':LIMITATIONS}
    output.mkdir(parents=True,exist_ok=True)
    (output/'review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--evidence',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verify-candidate',action='store_true',help='Verify issued inputs/references without a MATLAB return')
    args = parser.parse_args(argv)
    if not args.verify_candidate and args.evidence is None:
        parser.error('--evidence is required unless --verify-candidate is selected')
    try:
        t17.output_location(args.evidence or args.source_root,args.source_root,args.output)
    except ValueError as error:
        print('T22 output rejected without modifying inputs: '+str(error)); return 1
    try:
        if args.verify_candidate:
            prepared = verify_preparation(args.source_root)
            result = {'schema':REVIEW_SCHEMA,'status':'candidate_verified_matlab_execution_pending',
                'matlab_executed_by_reviewer':False,'planned_matlab_tests':prepared['planned_matlab_tests'],
                'planned_cases':prepared['planned_cases'],'planned_checkpoints':prepared['planned_checkpoints'],
                'baseline':prepared['baseline'],'reference_files':len(prepared['references']),
                'acceptance_established':False,'numerical_parity_established':False}
            args.output.mkdir(parents=True,exist_ok=True)
            (args.output/'review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        else:
            result = review(args.evidence,args.source_root,args.output)
    except (ValueError,OSError,csv.Error,zipfile.BadZipFile,KeyError,TypeError,AttributeError,OverflowError,StopIteration) as error:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'review.json').write_text(json.dumps({'schema':REVIEW_SCHEMA,'status':'review_failed',
            'evidence_integrity_verified':False,'focused_structural_gate_completed':False,
            'full_structural_gate_completed':False,'acceptance_established':False,
            'numerical_parity_established':False,'matlab_executed_by_reviewer':False,'error':str(error)},indent=2)+'\n',encoding='utf-8')
        print('T22 evidence rejected: '+str(error)); return 1
    print('T22 '+result['status']+'. MATLAB execution was not performed by this checker.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
