#!/usr/bin/env python3
"""Review T23 controlled receiver feedback and custody evidence, never run MATLAB.

A well-formed diagnostic may identify an exact state/feedback mismatch. That is
reported as a behavioral finding, never accepted or hidden behind the descriptive
full-campus +/-10% target. Corrupt or incomplete evidence fails closed.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import json
import re
from pathlib import Path
import zipfile

from analyze_tranche11_return import (
    all_files, candidate_snapshot, csv_rows, integer, inventory, json_object,
    json_value, number, record_map, require, safe_path, selected_test_names,
    sha256, verify_sources, verify_tests,
)
import analyze_tranche17_return as t17
import analyze_tranche22_return as t22

SCHEMA = 'csr-matlab-tranche-23-validation-v1'
REVIEW_SCHEMA = 'csr-matlab-tranche-23-return-review-v1'
PIN = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
ENGINE_PIN = '6b5cd24ea80713ce16d88575869aedd6f432bdae'
CANDIDATE = 'evidence/tranche-23-candidate.json'
BASELINE = 'evidence/tranche-23-baseline.json'
BASELINE_SHA = 'c5ca0672545bb213bd262d3d02f1008fd99d6c64e5355b8248ac102257477fd2'
PARENT = 'evidence/tranche-23-parent-candidate.json'
PARENT_SHA = '333686e6ee7822baf9f53ad06a0aa1d6475fced46947281596704ff147b5ba06'
ACCEPTED = 'evidence/t22/accepted'
ACCEPTANCE_SHA = 'ba3c50e96e150d6d92073edb20c490c595c2121e01dabbd5c0bcaac1ede08633'
OWNER_SHA = '37863a70ef46c2889b3f945bcc2d3cfbe548115f1c349136488cc56357a9f6af'
PARENT_REFERENCE_SHA = '457c88a80ad29243cebeec0033e8109a4021553fb95a1352c4aabd0eef435216'
PLAN = 'scenarios/t23/plan.json'
ACTIONS = 'scenarios/t23/actions.csv'
CASES = 'scenarios/t23/cases.csv'
CONTRACT = 'scenarios/t23/contract.json'
REFERENCE = 'evidence/t23/native'
TIME_TOLERANCE = Decimal('0.000000001')
# Filled from the frozen common contract during tranche construction; no owner
# return can redefine schemas, case membership, or comparison tolerances.
CASE_IDS = ('relay_boundary', 'local_relay_independence', 'ack_duplicate', 'dack_duplicate_pressure', 'dack_reassessment_after_release', 'release_idempotence', 'local_delivery_bypass')
CASE_FIELDS = ('case_id', 'resend_seconds', 'max_resends', 'dack_seconds', 'tic_seconds', 'pending_threshold', 'flow_threshold_max', 'policy', 'scope')
ACTION_FIELDS = ('case_id', 'step', 'time_s', 'observe_s', 'action', 'packet', 'sequence', 'nwk_source', 'destination', 'ack_packets', 'dack_packets', 'note')
STATE_FIELDS = ('case_id', 'step', 'time_s', 'action', 'packet', 'accepted', 'nsdp_relay', 'nsdp_local', 'nwk_waiting', 'nwk_owned', 'hop_pending', 'hop_outstanding', 'hop_resend', 'hop_holds', 'rx_highest', 'rx_ack_hex', 'rx_dack_hex', 'ack_generated', 'dack_generated', 'rx_received', 'rx_delivered', 'rx_duplicates', 'nsdp_releases', 'ack_completed', 'dack_completed', 'dack_expired', 'data_tx')
FEEDBACK_FIELDS = ('case_id', 'step', 'time_s', 'kind', 'sequence', 'ack_hex', 'dack_hex', 'relay_nsdp', 'local_nsdp', 'nwk_owned')
TEST_FILES = ['tests/TestReceiverFeedbackContract.m','tests/TestHopLayer.m','tests/TestNwkLayer.m',
              'tests/TestRelayContract.m','tests/TestMacHopCustody.m']
TEXT_FIELDS = ('case_id','action','packet')
LIMITATIONS = [
    'Owner-returned hashes and rows bind evidence claims; they do not independently prove MATLAB execution.',
    'This is controlled production NWK/HOP replay, not real-PHY or full-campus simulation.',
    'Exact deterministic state and feedback comparisons do not use the descriptive +/-10% campus target.',
    'Production sources, actual-tx retry expiration, continuous timing and PHY/ECC remain unchanged.',
    'Matched or mismatched controlled transitions do not establish the cause of stochastic campus histories.',
    'The accepted T22 native engine libraries are reverified and reused; only the T23 fixture is freshly compiled.',
]


def source_map(value, label):
    return {name: row['sha256'] for name, row in record_map(value,label).items()}


def verify_baseline(source_root, candidate, metadata=None):
    require(candidate.get('BaselineSourceSnapshot') == BASELINE
            and candidate.get('BaseSourceSnapshotSHA256') == sha256(source_root/BASELINE) == BASELINE_SHA,
            'Accepted T22 source snapshot identity mismatch')
    baseline = record_map(json_value(source_root/BASELINE),'T22 source baseline')
    require(len(baseline) == 390 and sum(name.endswith('.m') for name in baseline) == 178,
            'Accepted T22 source membership changed')
    for name,row in baseline.items():
        require(sha256(safe_path(source_root,name)) == row['sha256'],
                'Previously accepted T22 source changed: '+name)
    for field,path,digest in (('BaselineCandidate',PARENT,PARENT_SHA),
                             ('BaselineAcceptance',ACCEPTED+'/acceptance.json',ACCEPTANCE_SHA)):
        require(candidate.get(field) == path and candidate.get(field+'SHA256') == sha256(source_root/path) == digest,
                'T22 accepted provenance mismatch: '+field)
    for name,digest in (('source.json',BASELINE_SHA),('candidate.json',PARENT_SHA),
                        ('references.json',PARENT_REFERENCE_SHA)):
        require(sha256(source_root/ACCEPTED/'returned'/name) == digest,
                'T22 accepted return binding mismatch: '+name)
    accepted = json_object(source_root/ACCEPTED/'acceptance.json')
    require(accepted.get('accepted') is True and accepted.get('source_snapshot_sha256') == BASELINE_SHA
            and accepted.get('candidate_sha256') == PARENT_SHA and accepted.get('tests_passed') == 89
            and accepted.get('source_files_verified') == 390 and accepted.get('reference_files_verified') == 157
            and accepted.get('matched_checkpoints') == 364 and accepted.get('native_source_pin') == PIN
            and accepted.get('native_engine_pin') == ENGINE_PIN,
            'T22 acceptance does not bind the accepted source/test identity')
    require(sha256(source_root/ACCEPTED/'owner.zip') == accepted.get('owner_archive_sha256') == OWNER_SHA
            and candidate.get('BaselineOwnerEvidenceSHA256') == OWNER_SHA,
            'Accepted T22 owner archive binding mismatch')
    require(candidate.get('AllowedModifiedSourceFiles') == [] and candidate.get('AllBaselineSourcesUnchanged') is True
            and candidate.get('BaselineSourceFiles') == 390 and candidate.get('BaselineMatlabFiles') == 178,
            'T23 cannot modify accepted production source')
    if metadata is not None:
        require(metadata.get('AllBaselineSourcesUnchanged') is True
                and integer(metadata.get('BaselineSourceFilesVerified'),'baseline sources') == 390
                and integer(metadata.get('BaselineMatlabFilesVerified'),'baseline MATLAB') == 178,
                'Returned T22 source verification counters disagree')
    return {'source_files':390,'matlab_files':178,'all_unchanged':True,'source_snapshot_sha256':BASELINE_SHA}


def verify_references(source_root, candidate):
    names = candidate.get('ReferenceFiles')
    require(candidate.get('ReferenceRoots') == [] and isinstance(names,list) and names == sorted(set(names)) and names,
            'T23 requires distinct sorted explicit reference membership')
    entries = record_map(candidate.get('ReferenceFileInventory'),'candidate references',sizes=True)
    require(set(names) == set(entries),'Reference paths/inventory membership mismatch')
    inherited = record_map(json_object(source_root/PARENT)['ReferenceFileInventory'],
                           'accepted T22 references',sizes=True)
    verify_inherited_references(source_root,candidate,entries,inherited)
    returned = record_map(json_value(source_root/ACCEPTED/'returned/references.json'),'T22 returned references',sizes=True)
    require(returned == inherited,'T22 accepted references differ from parent candidate')
    required = {BASELINE,PARENT,ACCEPTED+'/acceptance.json',ACCEPTED+'/owner.zip',
                ACCEPTED+'/returned/source.json',ACCEPTED+'/returned/candidate.json',
                ACCEPTED+'/returned/references.json','evidence/tranche-14-native-build.json'}
    required.update(f'{REFERENCE}/{name}' for name in all_files(source_root/REFERENCE))
    require(required <= set(entries),'Required accepted/native reference membership missing')
    for name,row in entries.items():
        path = safe_path(source_root,name)
        require(path.is_file() and path.stat().st_size == row['bytes'] and sha256(path) == row['sha256'],
                'Reference hash or size mismatch: '+name)
    return entries


def verify_inherited_references(source_root,candidate,entries,inherited):
    ledger = 'docs/parity-ledger.csv'
    archived_ledger = 'evidence/t23/baseline/parity-ledger.csv'
    require(candidate.get('AllowedModifiedReferenceFiles') == [ledger],
            'Only the current documentation ledger reference may change')
    require(len(inherited) == 157 and ledger in inherited
            and all(entries.get(name) == row for name,row in inherited.items() if name != ledger),
            'Accepted T22 non-ledger reference inventory changed or was omitted')
    require(ledger in entries and archived_ledger in entries,
            'Current or accepted documentation ledger reference missing')
    old_ledger = inherited[ledger]
    require(entries[archived_ledger] == dict(old_ledger,path=archived_ledger)
            and sha256(source_root/archived_ledger) == old_ledger['sha256']
            and (source_root/archived_ledger).stat().st_size == old_ledger['bytes'],
            'Accepted T22 documentation ledger was not preserved exactly')


def compare_rows(actual, reference, fields):
    """Compare ordered rows without aligning away duplicate, shifted or missing rows."""
    differences = []
    nonzero_time = 0
    maximum_delta = Decimal(0)
    for index in range(max(len(actual),len(reference))):
        left = actual[index] if index < len(actual) else None
        right = reference[index] if index < len(reference) else None
        if left is None or right is None:
            differences.append({'row':index+1,'fields':['row_membership'],
                                'matlab_present':left is not None,'native_present':right is not None})
            continue
        differing = []
        for field in fields:
            if field == 'time_s':
                delta = abs(number(left[field],'comparison time')-number(right[field],'comparison time'))
                maximum_delta = max(maximum_delta,delta)
                nonzero_time += int(delta != 0)
                equal = delta <= TIME_TOLERANCE
            else:
                equal = left[field] == right[field]
            if not equal:
                differing.append(field)
        if differing:
            differences.append({'row':index+1,'case_id':left['case_id'],'step':left['step'],'fields':differing,
                'matlab':{key:str(left[key]) if isinstance(left[key],Decimal) else left[key] for key in differing},
                'native':{key:str(right[key]) if isinstance(right[key],Decimal) else right[key] for key in differing}})
    return {'matches_native':not differences,'actual_rows':len(actual),'reference_rows':len(reference),
        'matched_rows':max(len(actual),len(reference))-len(differences),'unmatched_rows':len(differences),
        'nonzero_time_differences':nonzero_time,'maximum_time_difference_s':str(maximum_delta),
        'time_tolerance_s':str(TIME_TOLERANCE),'differences':differences}


def verify_comparison_receipt(receipt, comparison, label):
    require(isinstance(receipt,dict) and receipt.get('ReferencePresent') is True and receipt.get('SchemaMatches') is True,
            'Missing '+label+' native comparison receipt')
    for field,key in (('ActualRows','actual_rows'),('ReferenceRows','reference_rows'),
                      ('MatchedRows','matched_rows'),('UnmatchedRows','unmatched_rows')):
        require(integer(receipt.get(field),label+' '+field) == comparison[key],
                label+' native comparison receipt count disagrees: '+field)
    failed = receipt.get('FailedRows')
    if not isinstance(failed,list):
        failed = [failed]  # MATLAB encodes a scalar numeric vector as one number.
    failed = [integer(row,'failed row',1) for row in failed]
    require(failed == [row['row'] for row in comparison['differences']],
            label+' native comparison failed-row identity disagrees')


def verify_summary(summary, metadata, state_comparison, feedback_comparison, case_count):
    passed = state_comparison['matches_native'] and feedback_comparison['matches_native']
    expected = {'CaseCount':case_count,'CheckpointCount':state_comparison['actual_rows'],
                'FailedCount':state_comparison['unmatched_rows'],'FeedbackCount':feedback_comparison['actual_rows'],
                'FeedbackFailedCount':feedback_comparison['unmatched_rows']}
    require(summary.get('DiagnosticCompleted') is True and summary.get('Passed') is passed,
            'Contract completion/pass flags disagree with independently compared rows')
    for field,count in expected.items():
        require(integer(summary.get(field),field) == count,'Contract summary count disagrees: '+field)
        require(integer(metadata.get('Contract'+field),'Contract'+field) == count,
                'Metadata contract count disagrees: '+field)
    require(metadata.get('ContractCompleted') is True and metadata.get('ContractPassed') is passed,
            'Metadata contract completion/pass disagreement')
    verify_comparison_receipt(summary.get('NativeComparison'),state_comparison,'checkpoint')
    verify_comparison_receipt(summary.get('NativeFeedbackComparison'),feedback_comparison,'feedback')
    return dict(expected,matches_native=passed)


def verify_identity(root, metadata, source_root, candidate):
    require(metadata.get('Schema') == SCHEMA and metadata.get('Tranche') == 23
            and metadata.get('Status') in ('completed-review-required','completed-differences-review-required'),'Return is not a completed T23 contract')
    require(metadata.get('EvidenceArchive') == 't23.zip'
            and metadata.get('InventoryExcludedPaths') == ['metadata.json','t23.zip'],
            'Return archive/inventory exclusion identity mismatch')
    require(metadata.get('CandidateFile') == CANDIDATE
            and metadata.get('CandidateSHA256') == sha256(source_root/CANDIDATE) == sha256(root/'candidate.json')
            and sha256(root/'plan.json') == candidate['PlanSHA256'],'Candidate/plan return binding mismatch')
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


def bitmap(value, label):
    require(isinstance(value,str) and re.fullmatch(r'[0-9A-F]{16}',value),
            label+': expected uppercase 16-digit bitmap')
    return value


def verify_actions(actions, case_ids):
    require(isinstance(case_ids,list) and case_ids and len(set(case_ids)) == len(case_ids),
            'Missing/duplicate case membership')
    require(actions,'Empty action tape')
    current,previous_observe,steps,aliases = -1,Decimal(-1),0,{}
    counts = {}
    for row in actions:
        require(tuple(row) == ACTION_FIELDS,'Unexpected action CSV schema')
        case = row['case_id']
        require(case in case_ids,'Unknown action case: '+case)
        position = case_ids.index(case)
        if position != current:
            require(position == current+1,'Missing/reordered action case')
            current,previous_observe,steps,aliases = position,Decimal(-1),0,{}
        steps += 1
        require(integer(row['step'],'action step',1) == steps,'Missing/duplicate/reordered action step')
        time = number(row['time_s'],'action time',minimum=0)
        observe = number(row['observe_s'],'observation time',minimum=0)
        require(time > previous_observe and observe-time == Decimal('0.000001'),
                'Action time overlaps observation or settling interval changed')
        previous_observe = observe
        action,packet = row['action'],row['packet']
        require(action in ('RX','LOCAL','TX','FEEDBACK','PROBE'),'Unknown action')
        if action in ('RX','LOCAL'):
            require(packet and ';' not in packet,'Invalid application alias')
            source = integer(row['nwk_source'],'application source',1)
            destination = integer(row['destination'],'application destination',1)
            require(source == (7 if action == 'RX' else 8) and destination in (1,8),
                    'Unexpected application flow')
            identity = (source,destination)
            require(packet not in aliases or aliases[packet] == identity,'Application alias identity changed')
            aliases[packet] = identity
        else:
            require(packet == '' and row['nwk_source'] == '0' and row['destination'] == '1',
                    'Nonapplication action has application identity')
        if action in ('RX','TX'):
            require(integer(row['sequence'],'HOP sequence') <= 65535,'HOP sequence outside uint16')
        else:
            require(row['sequence'] == '0','Unexpected HOP sequence on action')
        for field in ('ack_packets','dack_packets'):
            tokens = row[field].split(';') if row[field] else []
            require(len(tokens) == len(set(tokens)),'Duplicate feedback sequence')
            for token in tokens:
                require(str(integer(token,'feedback sequence')) == token and int(token) <= 65535,
                        'Invalid feedback sequence')
            require(action == 'FEEDBACK' or not tokens,'Feedback sequences on another action')
        if action == 'FEEDBACK':
            require(row['ack_packets'] or row['dack_packets'],'Empty FEEDBACK action')
            require(not set(row['ack_packets'].split(';'))&set(row['dack_packets'].split(';')) - {''},
                    'Overlapping explicit ACK/DACK sequence')
        counts[case] = steps
    require(current == len(case_ids)-1 and set(counts) == set(case_ids),'Missing planned case actions')
    return counts


def validate_checkpoints(rows, actions, label):
    require(len(rows) == len(actions),label+': missing/extra checkpoint rows')
    parsed,previous,rx_count = [],{},{}
    cumulative = ('ack_generated','dack_generated','rx_received','rx_delivered','rx_duplicates',
                  'nsdp_releases','ack_completed','dack_completed','dack_expired','data_tx')
    for row,action in zip(rows,actions):
        require(tuple(row) == STATE_FIELDS,label+': unexpected checkpoint CSV schema')
        for field in TEXT_FIELDS:
            require(row[field] == action[field],label+': checkpoint action/case/packet mismatch')
        values = {field:row[field] for field in TEXT_FIELDS}
        for field in STATE_FIELDS:
            if field in TEXT_FIELDS:
                continue
            if field == 'time_s':
                values[field] = number(row[field],'checkpoint time',minimum=0)
            elif field.endswith('_hex'):
                values[field] = bitmap(row[field],label+' '+field)
            else:
                values[field] = integer(row[field],label+' '+field,-1 if field in ('accepted','rx_highest') else 0)
        require(values['step'] == integer(action['step'],'action step',1),label+': checkpoint step mismatch')
        require(abs(values['time_s']-number(action['observe_s'],'observation time',minimum=0)) <= TIME_TOLERANCE,
                label+': checkpoint observation time mismatch')
        require(values['accepted'] in (0,1) if action['action'] == 'LOCAL' else values['accepted'] == -1,
                label+': invalid accepted sentinel')
        require(values['rx_highest'] <= 65535,label+': receive sequence outside uint16')
        require(values['nwk_owned'] == values['nsdp_relay']+values['nsdp_local'],
                label+': NWK ownership differs from per-flow NSDP counts')
        require(values['nwk_owned'] == values['nwk_waiting']+values['hop_resend'],
                label+': NWK waiting/submitted ownership does not reconcile')
        require(values['hop_pending'] == values['hop_resend']+values['hop_holds']
                and values['hop_outstanding'] == values['hop_pending'],
                label+': HOP resend/hold capacity does not reconcile')
        require(values['hop_holds'] == values['dack_completed']-values['dack_expired'],
                label+': retained DACK ownership differs from completion/expiry counts')
        require(values['nsdp_releases'] == values['ack_completed']+values['dack_completed'],
                label+': NWK custody release did not occur exactly once per completion')
        rx_count[row['case_id']] = rx_count.get(row['case_id'],0)+int(action['action'] == 'RX')
        require(values['rx_received'] == rx_count[row['case_id']]
                and values['rx_delivered']+values['rx_duplicates'] == values['rx_received'],
                label+': receive/delivery/feedback identity counts do not reconcile')
        old = previous.get(row['case_id'])
        if old is not None:
            require(all(values[field] >= old[field] for field in cumulative),label+': cumulative counter decreased')
        previous[row['case_id']] = values
        parsed.append(values)
    return parsed


def validate_feedback(rows, actions, checkpoints, label):
    lookup = {(a['case_id'],int(a['step'])):(index,a,state)
              for index,(a,state) in enumerate(zip(actions,checkpoints))}
    parsed,groups,previous_index = [],{},-1
    for row in rows:
        require(tuple(row) == FEEDBACK_FIELDS,label+': unexpected feedback CSV schema')
        key = (row['case_id'],integer(row['step'],'feedback step',1))
        require(key in lookup and lookup[key][1]['action'] == 'RX',label+': feedback action membership mismatch')
        index,action,state = lookup[key]
        require(index >= previous_index,label+': feedback action order changed')
        previous_index = index
        require(row['kind'] in ('ACK','DACK'),label+': unsupported feedback kind')
        values = {'case_id':row['case_id'],'step':key[1],'kind':row['kind']}
        values['time_s'] = number(row['time_s'],'feedback time',minimum=0)
        require(abs(values['time_s']-number(action['time_s'],'action time',minimum=0)) <= TIME_TOLERANCE,
                label+': generated feedback time differs from receive action')
        for field in FEEDBACK_FIELDS[4:]:
            values[field] = bitmap(row[field],label+' '+field) if field.endswith('_hex') else integer(row[field],field)
        require(values['sequence'] <= 65535,label+': feedback sequence outside uint16')
        require(values['nwk_owned'] == values['relay_nsdp']+values['local_nsdp'],
                label+': feedback NWK ownership differs from per-flow counts')
        groups.setdefault(key,[]).append(values)
        parsed.append(values)
    tally = {}
    for action,state in zip(actions,checkpoints):
        count = tally.setdefault(action['case_id'],{'ACK':0,'DACK':0})
        key = (action['case_id'],int(action['step']))
        for row in groups.get(key,[]):
            count[row['kind']] += 1
        require(count['ACK'] == state['ack_generated'] and count['DACK'] == state['dack_generated'],
                label+': feedback kind/cumulative count differs from checkpoints')
    return parsed


def verify_milestones(rows, contract, label, native=False):
    lookup = {(row['case_id'],row['step']):row for row in rows}
    require(len(lookup) == len(rows),label+': duplicate milestone checkpoint identity')
    milestones = contract.get('milestones')
    require(isinstance(milestones,list) and milestones,'Missing independent milestone constraints')
    if native:
        extra = contract.get('native_milestones',[])
        require(isinstance(extra,list),'Invalid native milestone list')
        milestones = [*milestones,*extra]
    checks,seen = 0,set()
    for item in milestones:
        key = (item.get('case_id'),integer(item.get('step'),'milestone step',1))
        require(key in lookup,'Unknown milestone checkpoint')
        fields = item.get('equals')
        require(isinstance(fields,dict) and fields and set(fields) <= set(STATE_FIELDS[5:]),
                'Unsupported independent milestone fields')
        for field,expected in fields.items():
            require((*key,field) not in seen,'Duplicate milestone field')
            seen.add((*key,field))
            if field.endswith('_hex'):
                expected = bitmap(expected,'milestone '+field)
            else:
                expected = integer(expected,'milestone '+field,-1 if field in ('accepted','rx_highest') else 0)
            require(lookup[key][field] == expected,
                    f'{label}: independent milestone mismatch: {key[0]}/{key[1]} {field}')
            checks += 1
    return {'milestones':len(milestones),'field_assertions':checks}


def verify_plan(source_root, candidate):
    require(candidate.get('Plan') == PLAN and candidate.get('PlanSHA256') == sha256(source_root/PLAN),
            'Replay plan path/hash mismatch')
    plan = json_object(source_root/PLAN)
    require(plan.get('schema') == 'csr-tranche23-receiver-feedback-plan-v1' and plan.get('tranche') == 23
            and plan.get('source_commit') == PIN and plan.get('engine_commit') == ENGINE_PIN
            and plan.get('case_order') == list(CASE_IDS) and plan.get('case_count') == 7
            and plan.get('action_count') == 123 and plan.get('checkpoint_count') == 123
            and plan.get('milestone_count') == 18 and plan.get('native_milestone_count') == 2
            and plan.get('native_reference') == REFERENCE,'Replay plan identity/membership mismatch')
    require(plan.get('timing_policy') == 'continuous' and plan.get('default_policy') == 'actual-tx'
            and plan.get('working_campus_band_percent') == 10
            and all(plan.get(field) is False for field in ('production_source_changed','phy_ecc_changed','full_campus_run')),
            'Replay plan changes production policy/scope')
    for stem,path in (('cases',CASES),('actions',ACTIONS),('contract',CONTRACT)):
        require(plan.get(stem+'_file') == path and plan.get(stem+'_sha256') == sha256(source_root/path),
                'Replay input hash/path mismatch: '+stem)
    contract = json_object(source_root/CONTRACT)
    require(contract.get('schema') == 'csr-tranche23-receiver-feedback-contract-v1'
            and contract.get('case_count') == 7 and contract.get('action_count') == 123,
            'Controlled contract identity/membership mismatch')
    for item in (plan,contract):
        for field,expected in (('action_columns',ACTION_FIELDS),('state_columns',STATE_FIELDS),
                               ('configuration_columns',CASE_FIELDS),('feedback_columns',FEEDBACK_FIELDS)):
            require(item.get(field) == list(expected),'Frozen contract columns changed: '+field)
        compare = item.get('comparison')
        require(isinstance(compare,dict) and compare.get('integer_tolerance') == 0
                and number(compare.get('time_absolute_tolerance_seconds'),'time tolerance') == TIME_TOLERANCE
                and compare.get('campus_percent_target_applies') is False,'Controlled-state tolerance changed')
    require(set(contract.get('input_hashes',{})) == {'cases.csv','actions.csv'},
            'Contract input provenance membership changed')
    for name,digest in contract['input_hashes'].items():
        require(sha256(source_root/'scenarios/t23'/name) == digest,'Contract input hash mismatch: '+name)
    plan_inputs = source_map(plan.get('input_files'),'plan inputs')
    require(set(plan_inputs) == {CASES,ACTIONS,CONTRACT},'Replay plan input membership changed')
    for path,digest in plan_inputs.items():
        require(sha256(safe_path(source_root,path)) == digest,'Replay plan input binding mismatch')
    cases = csv_rows(source_root/CASES,CASE_FIELDS)
    require([row['case_id'] for row in cases] == list(CASE_IDS),'Missing/duplicate/reordered case configuration')
    for case in cases:
        require(case['policy'] == 'actual-tx' and case['scope'],'Controlled case policy/scope mismatch')
        for field,expected in (('resend_seconds',2),('max_resends',2),('dack_seconds',20),
                               ('pending_threshold',16),('flow_threshold_max',16)):
            require(number(case[field],field) == expected,'Controlled default configuration changed: '+field)
        require(abs(number(case['tic_seconds'],'TIC',minimum=0)-Decimal(1)/Decimal(36_000_000)) <= Decimal('1e-23'),
                'Controlled default TIC changed')
    actions = csv_rows(source_root/ACTIONS,ACTION_FIELDS)
    require(len(actions) == 123 and len(contract.get('milestones',[])) == 18
            and len(contract.get('native_milestones',[])) == 2,'Controlled workload/milestones changed')
    verify_actions(actions,list(CASE_IDS))
    return dict(plan,contract=contract),actions,cases


def verify_native_build(source_root, summary):
    directory = source_root/REFERENCE
    require(summary.get('build_manifest') == 'build.json'
            and summary.get('build_manifest_sha256') == sha256(directory/'build.json'),
            'Native execution does not bind the retained build receipt')
    build = json_object(directory/'build.json')
    old_root = source_root/'evidence/t22/native'
    old_summary = json_object(old_root/'summary.json')
    old_build = json_object(old_root/'build.json')
    baseline_build = json_object(source_root/'evidence/tranche-14-native-build.json')
    t22.verify_native_build(old_root,old_summary,baseline_build)
    require(build.get('schema') == 'csr-tranche23-retained-native-build-v1' and build.get('status') == 'passed'
            and build.get('source_pin') == PIN and build.get('engine_pin') == ENGINE_PIN
            and build.get('source_tree') == old_build['source_tree']
            and build.get('engine_tree') == old_build['engine_tree']
            and build.get('engine_rebuilt_for_t23') is False and build.get('reused_accepted_t22_libraries') is True
            and build.get('fresh_fixture_compile') is True and build.get('production_source_unchanged') is True
            and build.get('engine_source_unchanged') is True and build.get('linked_libraries_verified_elf') is True,
            'Native retained-build/source/engine identity mismatch')
    for field,name,original in (('accepted_t22_build','t22-build.json','build.json'),
                                ('accepted_t22_summary','t22-summary.json','summary.json'),
                                ('tracked_source_verification','tracked-source-verification.json','tracked-source-verification.json')):
        path = 'build-provenance/'+name
        require(build.get(field) == path and build.get(field+'_sha256') == sha256(directory/path) == sha256(old_root/original),
                'Retained T22 build receipt identity mismatch: '+field)
    preserved_build_files = {'t22-build.json','t22-summary.json','tracked-source-verification.json',
                             'archive-verification.json','elf-verification.json','verify_archive_trees.py','verify_elf.py',
                             old_build['configure']['log'],*[row['log'] for row in old_build['build_attempts']]}
    require(all_files(directory/'build-provenance') == preserved_build_files,
            'Retained accepted native build provenance inventory is not closed')
    for name in preserved_build_files:
        original = {'t22-build.json':'build.json','t22-summary.json':'summary.json'}.get(name,name)
        require(sha256(safe_path(directory/'build-provenance',name)) == sha256(safe_path(old_root,original)),
                'Copied accepted build provenance changed: '+name)
    require(build.get('libraries') == summary.get('libraries') == old_build['libraries'],
            'T23 executed native libraries differ from accepted T22 build')
    tracked = json_object(directory/build['tracked_source_verification'])
    require(build.get('tracked_files_reverified') == {kind:row['file_count'] for kind,row in tracked.items()},
            'T23 retained tracked-source verification count mismatch')
    compiler = build.get('compiler')
    require(isinstance(compiler,dict) and isinstance(compiler.get('path'),str) and compiler['path'],
            'Native compiler provenance missing')
    record_map([{'path':'compiler','sha256':compiler.get('sha256')}],'compiler hash')
    return {'build_sha256':sha256(directory/'build.json'),'source_tree':build['source_tree'],
            'engine_tree':build['engine_tree'],'linked_libraries':len(build['libraries']),
            'engine_rebuilt_for_t23':False,'reused_accepted_t22_libraries':True,
            'fresh_fixture_compile':True,'tracked_files_reverified':build['tracked_files_reverified']}


def detail_values(event):
    result = {}
    for part in event.get('detail','').split(';'):
        if '=' in part:
            name,value = part.split('=',1)
            require(name not in result,'Duplicate native trace detail key')
            result[name] = value
    return result


def verify_native_raw(directory, checkpoints, feedback, case_ids):
    combined_states,combined_feedback,counts = [],[],{}
    total_events = 0
    for case in case_ids:
        on = directory/'trace_on'/case
        off = directory/'trace_off'/case
        for name in ('states.csv','feedback.csv'):
            require(sha256(on/name) == sha256(off/name),'Observer on/off changes native '+name)
        states = csv_rows(on/'states.csv',STATE_FIELDS)
        frames = csv_rows(on/'feedback.csv',FEEDBACK_FIELDS)
        combined_states.extend(states);combined_feedback.extend(frames)
        expected = [row for row in checkpoints if row['case_id'] == case]
        expected_frames = [row for row in feedback if row['case_id'] == case]
        trace = csv_rows(on/'trace.csv')
        require(trace and len(states) == len(expected),'Incomplete native raw checkpoint/trace population')
        tally = {'ack_completed':0,'dack_completed':0,'nsdp_releases':0,'dack_expired':0,
                 'ack_generated':0,'dack_generated':0,'rx_received':0,'rx_duplicates':0,'rx_delivered':0}
        completed,expired = {},set()
        position,frame_position = 0,0
        previous_time,previous_index = Decimal(0),-1
        for event in trace:
            require(event.get('schema') == 'csr-differential-trace-v1','Unexpected native raw trace schema')
            event_time = number(event.get('time_s'),'native raw time',minimum=0)
            event_index = integer(event.get('event_index'),'native raw event index')
            require(event_time >= previous_time and event_index > previous_index,
                    'Native raw event time/index is not ordered')
            previous_time,previous_index = event_time,event_index
            total_events += 1
            kind,details = event['event'],detail_values(event)
            if kind == 'hop_completion':
                key = (event['peer'],details.get('hop_sequence'))
                require(event['node'] == '8' and event['peer'] == '2' and event['packet_type'] == 'data'
                        and event['dst'] == '1' and key not in completed and event['reason'] in ('ack','dack'),
                        'Duplicate/unsupported native completion')
                require(integer(details.get('nsdp_released'),'native NSDP release') == 1,
                        'Native completion did not release NWK custody')
                completed[key] = (event['reason'],event_time)
                tally[event['reason']+'_completed'] += 1
            elif kind == 'nwk_nsdp_release':
                require(event['node'] == '8' and event['dst'] == '1' and event['reason'] == 'hop_feedback'
                        and integer(details.get('count_before'),'NSDP before',1)
                            == integer(details.get('count_after'),'NSDP after')+1,
                        'Native NSDP release did not decrement exactly once')
                tally['nsdp_releases'] += 1
            elif kind == 'hop_capacity_release':
                key = (event['peer'],details.get('hop_sequence'))
                require(event['node'] == '8' and event['peer'] == '2' and event['reason'] == 'dack_expiry'
                        and key in completed and completed[key][0] == 'dack' and key not in expired
                        and event_time-completed[key][1] >= Decimal(20)
                        and integer(details.get('nsdp_released'),'expiry NSDP release') == 0
                        and integer(details.get('capacity_released'),'expiry capacity release') == 1,
                        'Duplicate/unsupported native delayed capacity release')
                expired.add(key);tally['dack_expired'] += 1
            elif kind == 'hop_feedback':
                require(frame_position < len(expected_frames),'Native trace has unexported feedback frame')
                frame = expected_frames[frame_position]
                require(event['node'] == '8' and event['peer'] == '7' and event['reason'] in ('ack','dack')
                        and frame['kind'] == event['reason'].upper()
                        and abs(event_time-frame['time_s']) <= TIME_TOLERANCE,
                        'Generated feedback kind/time differs from ordered production trace')
                first = integer(details.get('first_reception'),'native first reception')
                require(first in (0,1),'Native first reception sentinel invalid')
                tally['rx_received'] += 1;tally['rx_delivered'] += first;tally['rx_duplicates'] += 1-first
                tally[event['reason']+'_generated'] += 1;frame_position += 1
            elif kind == 't23_checkpoint':
                require(position < len(expected) and event['node'] == '8'
                        and integer(event['sequence'],'native checkpoint step',1) == expected[position]['step'],
                        'Missing/duplicate native checkpoint marker')
                state = expected[position]
                require(abs(event_time-state['time_s']) <= TIME_TOLERANCE,'Native checkpoint marker clock mismatch')
                require(all(state[field] == value for field,value in tally.items()),
                        'Native checkpoint does not reconcile with ordered feedback/completion trace')
                position += 1
            require(kind != 'tx_start','Controlled receiver fixture unexpectedly executed actual PHY/MAC transmission')
        require(position == len(expected) and frame_position == len(expected_frames),
                'Missing final native checkpoint or feedback trace marker')
        counts[case] = {'checkpoints':position,'feedback_frames':frame_position,
            **{field:tally[field] for field in ('ack_completed','dack_completed','nsdp_releases','dack_expired')},
            'actual_mac_transmissions':0}
    require(combined_states == csv_rows(directory/'checkpoints.csv',STATE_FIELDS),
            'Native exported checkpoints differ from raw state rows')
    require(combined_feedback == csv_rows(directory/'feedback.csv',FEEDBACK_FIELDS),
            'Native exported feedback differs from raw captured frames')
    return {'trace_events':total_events,'cases':counts,'all_raw_states_and_events_reconciled':True,
            'observer_on_off_identical':True,'actual_mac_transmissions':0}


def verify_native(source_root, actions, cases, contract):
    directory = source_root/REFERENCE
    manifest = json_object(directory/'manifest.json')
    require(manifest.get('schema') == 'csr-tranche23-native-files-v1' and isinstance(manifest.get('files'),dict),
            'Native manifest schema mismatch')
    entries = record_map([{'path':name,'sha256':digest} for name,digest in manifest['files'].items()],
                         'native manifest')
    require(set(entries) == all_files(directory)-{'manifest.json'},'Native reference inventory is not closed')
    for name,row in entries.items():
        require(sha256(safe_path(directory,name)) == row['sha256'],'Native reference hash mismatch: '+name)
    summary = json_object(directory/'summary.json')
    require(summary.get('schema') == 'csr-tranche23-native-reference-v1' and summary.get('status') == 'passed'
            and summary.get('source_pin') == PIN and summary.get('engine_pin') == ENGINE_PIN
            and summary.get('native_executed') is True and summary.get('matlab_executed') is False
            and summary.get('production_source_unchanged') is True and summary.get('engine_source_unchanged') is True
            and summary.get('observer_on_off_identical') is True and summary.get('actual_mac_transmissions') == 0
            and summary.get('engine_rebuilt_for_t23') is False and summary.get('reused_accepted_t22_libraries') is True
            and summary.get('fresh_fixture_compile') is True,'Native execution/source/scope status mismatch')
    require(summary.get('case_count') == len(cases) and summary.get('checkpoint_count') == len(actions)
            and summary.get('milestone_count') == len(contract['milestones'])+len(contract['native_milestones'])
            and number(summary.get('time_resolution_seconds'),'native time resolution') == TIME_TOLERANCE,
            'Native execution membership/time resolution mismatch')
    expected_inputs = {path.relative_to(source_root).as_posix():sha256(path)
                       for path in (source_root/'scenarios/t23').iterdir() if path.is_file()}
    require(summary.get('input_bindings') == expected_inputs,'Native executed input bindings differ from frozen inputs')
    fixtures = ('scripts/ns3/tranche23_receiver.cc','scripts/run_tranche23_ns3_reference.py')
    require(summary.get('fixture_sources') == {name:sha256(source_root/name) for name in fixtures},
            'Native fixture source binding mismatch')
    expected_model = source_map(json_object(source_root/'evidence/tranche-14-native-build.json')['module_files'],
                                'native source module')
    require(summary.get('model_sources') == expected_model,'Native production module hashes differ from pinned model')
    build = verify_native_build(source_root,summary)
    commands = summary.get('commands')
    require(isinstance(commands,list) and len(commands) == 3,'Missing native compile/on/off run command evidence')
    for command in commands:
        require(isinstance(command,dict) and isinstance(command.get('argv'),list) and command['argv']
                and integer(command.get('exit_code'),'native exit code') == 0
                and command.get('log_sha256') == sha256(safe_path(directory,command.get('log'))),
                'Native command completion/log binding mismatch')
        number(command.get('wall_seconds'),'native command duration',minimum=0)
    require(summary.get('seams_sha256') == sha256(directory/'seams.patch'),'Native fixture seam binding mismatch')
    additions = [line for line in (directory/'seams.patch').read_text().splitlines() if line.startswith('+') and not line.startswith('+++')]
    deletions = [line for line in (directory/'seams.patch').read_text().splitlines() if line.startswith('-') and not line.startswith('---')]
    require(len(additions) == 2 and not deletions and all('friend struct CsrTranche23Access;' in line for line in additions),
            'Native fixture seam changed production behavior')
    rows = validate_checkpoints(csv_rows(directory/'checkpoints.csv',STATE_FIELDS),actions,'native')
    frames = validate_feedback(csv_rows(directory/'feedback.csv',FEEDBACK_FIELDS),actions,rows,'native')
    require(summary.get('feedback_count') == len(frames),'Native feedback count differs from captured frames')
    milestones = verify_milestones(rows,contract,'native',native=True)
    raw = verify_native_raw(directory,rows,frames,[case['case_id'] for case in cases])
    require(summary.get('cases') == raw['cases'],'Native summary completion counts differ from raw trace')
    return {'checkpoints':rows,'feedback':frames,'case_count':len(cases),'checkpoint_count':len(rows),
            'feedback_count':len(frames),'raw':raw,'milestones':milestones,'build':build,
            'checkpoints_sha256':sha256(directory/'checkpoints.csv'),'feedback_sha256':sha256(directory/'feedback.csv'),
            'summary_sha256':sha256(directory/'summary.json')}


def verify_preparation(source_root):
    source_root = Path(source_root).resolve()
    candidate = json_object(source_root/CANDIDATE)
    require(candidate.get('Schema') == 'csr-tranche-23-candidate-v1' and candidate.get('Tranche') == 23
            and candidate.get('SourceCommit') == PIN and candidate.get('EngineCommit') == ENGINE_PIN,
            'T23 candidate identity mismatch')
    require(candidate.get('DataQueuedRetryPolicy') == 'actual-tx' and candidate.get('TimingPolicy') == 'continuous'
            and candidate.get('WorkingCampusBandPercent') == 10 and candidate.get('MATLABExecutionPending') is True
            and all(candidate.get(field) is False for field in ('FullPortableRegression','FullCampusRun','PHYExecuted',
                 'ProductionSourceChanged','MATLABExecuted','AcceptanceEstablished','NumericalParityEstablished')),
            'T23 candidate policy/scope mismatch')
    for field,name in (('NativeReference','checkpoints.csv'),('NativeFeedbackReference','feedback.csv')):
        require(candidate.get(field) == REFERENCE+'/'+name
                and candidate.get(field+'SHA256') == sha256(source_root/REFERENCE/name),
                'Candidate native reference binding mismatch: '+field)
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
    plan,actions,cases = verify_plan(source_root,candidate)
    native = verify_native(source_root,actions,cases,plan['contract'])
    require(candidate.get('ExpectedCaseCount') == len(cases) and candidate.get('ExpectedCheckpointCount') == len(actions)
            and candidate.get('ExpectedFeedbackCount') == len(native['feedback']),
            'Candidate case/checkpoint/feedback count differs from plan/native inputs')
    return {'source':source,'references':references,'baseline':baseline,'plan':plan,'actions':actions,
        'cases':cases,'native':native,'planned_matlab_tests':len(names),'planned_cases':len(cases),
        'planned_checkpoints':len(actions),'native_feedback_frames':len(native['feedback']),'matlab_executed':False}


def verify_contract(root, metadata, source_root, prepared):
    directory = root/'contract'
    for name,expected in (('actions.csv',ACTIONS),('cases.csv',CASES)):
        require(sha256(directory/name) == sha256(source_root/expected),'Returned contract input changed: '+name)
    actual = validate_checkpoints(csv_rows(directory/'checkpoints.csv',STATE_FIELDS),prepared['actions'],'MATLAB')
    actual_frames = validate_feedback(csv_rows(directory/'feedback.csv',FEEDBACK_FIELDS),prepared['actions'],actual,'MATLAB')
    comparison = compare_rows(actual,prepared['native']['checkpoints'],STATE_FIELDS)
    feedback_comparison = compare_rows(actual_frames,prepared['native']['feedback'],FEEDBACK_FIELDS)
    summary = json_object(directory/'summary.json')
    require(summary.get('Schema') == 'csr-tranche23-receiver-feedback-contract-v1'
            and summary.get('ActionsSHA256') == sha256(source_root/ACTIONS)
            and summary.get('CasesSHA256') == sha256(source_root/CASES)
            and summary.get('NativeReferenceSHA256') == sha256(source_root/REFERENCE/'checkpoints.csv')
            and summary.get('NativeFeedbackReferenceSHA256') == sha256(source_root/REFERENCE/'feedback.csv')
            and summary.get('DataQueuedRetryPolicy') == 'actual-tx',
            'Contract summary source/reference/policy binding mismatch')
    result = verify_summary(summary,metadata,comparison,feedback_comparison,len(prepared['cases']))
    expected_status = 'completed-review-required' if result['matches_native'] else 'completed-differences-review-required'
    require(metadata.get('Status') == expected_status,'Returned status hides or invents native differences')
    milestones = verify_milestones(actual,prepared['plan']['contract'],'MATLAB')
    return {'case_count':len(prepared['cases']),'checkpoint_count':len(actual),'feedback_count':len(actual_frames),
            'matches_native':result['matches_native'],'native_comparison':comparison,
            'native_feedback_comparison':feedback_comparison,'common_milestones':milestones,
            'scope':'Controlled production NWK/HOP receiver replay; no PHY, security-ingress or campus run'}


def review(evidence, source_root, output):
    evidence,source_root,output = t17.output_location(evidence,source_root,output)
    prepared = verify_preparation(source_root)
    candidate = json_object(source_root/CANDIDATE)
    with t17.evidence_directory(evidence) as root:
        require(evidence.is_dir() or not (root/'t23.zip').exists(),'Unexpected nested return archive')
        metadata = json_object(root/'metadata.json')
        runtime = verify_identity(root,metadata,source_root,candidate)
        inventory(root,metadata.get('Artifacts'),excluded=('metadata.json','t23.zip'))
        source = verify_sources(root,metadata,source_root)
        references = t17.verify_references(root,metadata,prepared['references'])
        baseline = verify_baseline(source_root,candidate,metadata)
        tests = verify_tests(root,metadata,source_root,candidate)
        contract = verify_contract(root,metadata,source_root,prepared)
        result = {'schema':REVIEW_SCHEMA,'status':'controlled_receiver_review_completed',
            'evidence_integrity_verified':True,'focused_structural_gate_completed':True,
            'cross_engine_contract_passed':contract['matches_native'],
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
        print('T23 output rejected without modifying inputs: '+str(error));return 1
    try:
        if args.verify_candidate:
            prepared = verify_preparation(args.source_root)
            result = {'schema':REVIEW_SCHEMA,'status':'candidate_verified_matlab_execution_pending',
                'matlab_executed_by_reviewer':False,'planned_matlab_tests':prepared['planned_matlab_tests'],
                'planned_cases':prepared['planned_cases'],'planned_checkpoints':prepared['planned_checkpoints'],
                'native_feedback_frames':prepared['native_feedback_frames'],'baseline':prepared['baseline'],
                'reference_files':len(prepared['references']),'native_raw':prepared['native']['raw'],
                'native_build':prepared['native']['build'],
                'acceptance_established':False,'numerical_parity_established':False}
            args.output.mkdir(parents=True,exist_ok=True)
            (args.output/'review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        else:
            result = review(args.evidence,args.source_root,args.output)
    except (ValueError,OSError,csv.Error,zipfile.BadZipFile,KeyError,TypeError,AttributeError,OverflowError,StopIteration) as error:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'review.json').write_text(json.dumps({'schema':REVIEW_SCHEMA,'status':'review_failed',
            'evidence_integrity_verified':False,'focused_structural_gate_completed':False,
            'cross_engine_contract_passed':False,'full_structural_gate_completed':False,'acceptance_established':False,
            'numerical_parity_established':False,'matlab_executed_by_reviewer':False,'error':str(error)},indent=2)+'\n',encoding='utf-8')
        print('T23 evidence rejected: '+str(error));return 1
    print('T23 '+result['status']+'. MATLAB execution was not performed by this checker.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
