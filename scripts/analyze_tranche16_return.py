#!/usr/bin/env python3
"""Review the T16 real-PHY paired receiver-timing evidence, never run MATLAB.

A seed pairs the two MATLAB policies only. Native RNGs are independent: compare
application totals and the same declared bucket grid, never positional events.
Passing this bounded experiment does not establish full-network/ns-3 parity.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import csv
import json
import math
from pathlib import Path
import statistics
import zipfile

from analyze_tranche11_return import (
    all_files, candidate_snapshot, csv_rows, evidence_directory, integer, inventory,
    json_object, json_value, logical, number as decimal_number, record_map, require, safe_path, sha256,
    verify_references, verify_sources, verify_tests,
)
from analyze_tranche14_return import full_time, hex64, rounded_ns, exact_uint
import analyze_research_sweep as sweep
import analyze_tranche7_return as t7
import analyze_tranche8_return as t8
import tranche8_metrics as metrics
import tranche10_metrics as retained
import compare_benchmark_aggregates as aggregate

SCHEMA = 'csr-matlab-tranche-16-validation-v1'
REVIEW_SCHEMA = 'csr-matlab-tranche-16-return-review-v1'
CANDIDATE = 'evidence/tranche-16-candidate.json'
BASELINE = 'evidence/tranche-16-baseline.json'
BASELINE_SHA = '2cb68e6d1ed35884aeeea1d4db761f75a2a2338283bf5b37cea653da43a369d5'
OWNER_SHA = 'a1c706fc66d2699ffcd4a0d4d811acaa5cfc10fe8bcc3fe459d85a18c94bca73'
PARENT_CANDIDATE_SHA = 'be665c0c733f2e71766cb3b066ca789ea6a2a3de1d8a198ccb0b0a5fe00a16f0'
CONFIG_ARCHIVE = 'evidence/tranche-8-r2025a-accepted/tranche8_evidence.zip'
CONFIG_ARCHIVE_SHA = 'bfc4f7f05f0800316b371df3ec316f309f14e3482ef259c3f9c7bd7eea025d77'
MODIFIED = ('+csr/+phy/SignalEngine.m', '+csr/+sim/NetworkSimulation.m')
CASES = ('a128','c128','a129','c129','a130','c130')
MODES = {'c':'continuous', 'n':'nanoseconds'}
TIME_FIELDS = ('TxSeconds','PropagationSeconds','DurationSeconds','PreambleSeconds',
    'PhysicalStartSeconds','PhysicalPreambleEndSeconds','PhysicalEndSeconds',
    'StartSeconds','PreambleEndSeconds','EndSeconds',
    'StartShiftSeconds','PreambleEndShiftSeconds','EndShiftSeconds')
RECORD_FIELDS = ('Ordinal','SourceId','ReceiverId','FrameId',*TIME_FIELDS[:10],
    'TxNanoseconds','PropagationNanoseconds','DurationNanoseconds','PreambleNanoseconds',
    'StartNanoseconds','PreambleEndNanoseconds','EndNanoseconds',*TIME_FIELDS[10:])
TIMING_FIELDS = (*RECORD_FIELDS, *(suffix for name in TIME_FIELDS for suffix in (name+'Decimal',name+'Hex')))


def number(value,label,*,minimum=None):
    return float(decimal_number(value,label,minimum=minimum))


def verify_identity(root, metadata, source_root, candidate):
    require(candidate.get('Schema') == 'csr-tranche-16-candidate-v1' and candidate.get('Tranche') == 16
            and candidate.get('SourceCommit') == t7.PIN, 'Candidate identity/source pin mismatch')
    require(metadata.get('Schema') == SCHEMA and metadata.get('Tranche') == 16
            and metadata.get('Status') == 'completed', 'Return is not a completed T16 diagnostic')
    require(metadata.get('CandidateFile') == CANDIDATE
            and metadata.get('CandidateSHA256') == sha256(source_root/CANDIDATE), 'Candidate hash mismatch')
    require(metadata.get('MATLABExecuted') is True and metadata.get('NativeExecuted') is False
            and metadata.get('SourceCommit') == t7.PIN, 'Owner/native execution identity mismatch')
    runtime = metadata.get('Runtime')
    require(isinstance(runtime,dict) and runtime.get('Runtime') == 'MATLAB'
            and runtime.get('DefaultBackend') == 'portable'
            and all(isinstance(runtime.get(key),str) and runtime[key] for key in ('Version','Release')),
            'Missing portable MATLAB release/runtime provenance')
    started, ended = (datetime.fromisoformat(metadata.get(key,'').replace('Z','+00:00'))
                      for key in ('StartedUTC','CompletedUTC'))
    require(started.tzinfo and ended.tzinfo and ended >= started, 'Invalid owner execution timestamps')
    require(metadata.get('FocusedGateExecuted') is True and metadata.get('DiagnosticOnly') is True
            and all(metadata.get(key) is False for key in
                    ('FullAcceptanceGateExecuted','AcceptanceEstablished','NumericalParityEstablished')),
            'Unsupported full-acceptance/parity claim or missing focused gate')
    require(metadata.get('EvidenceArchive') == 't16.zip'
            and metadata.get('InventoryExcludedPaths') == ['metadata.json'], 'Archive/exclusion policy changed')
    local = record_map(metadata.get('LocalArtifacts',[]),'local artifacts',sizes=True,empty=True)
    require(all(name.endswith('.mat') and name not in all_files(root) for name in local), 'Invalid local-only artifacts')
    return runtime


def verify_baseline(metadata, source_root, candidate):
    require(candidate.get('BaselineSourceSnapshot') == BASELINE
            and candidate.get('BaseSourceSnapshotSHA256') == sha256(source_root/BASELINE) == BASELINE_SHA,
            'Reviewed T15 source snapshot mismatch')
    baseline = record_map(json_value(source_root/BASELINE),'T15 source')
    require(len(baseline) == 294 and sum(name.endswith('.m') for name in baseline) == 149,
            'T15 baseline membership changed')
    allowed = record_map(candidate.get('AllowedModifiedSourceFiles'),'allowed changes',sizes=True)
    require(set(allowed) == set(MODIFIED), 'Unexpected allowed baseline modifications')
    changed = []
    for name, original in baseline.items():
        path = safe_path(source_root,name)
        actual = sha256(path)
        if name in allowed:
            require(allowed[name]['sha256'] == actual and allowed[name]['bytes'] == path.stat().st_size
                    and actual != original['sha256'], 'Allowed timing integration hash/size mismatch')
            changed.append({'path':name,'baseline_sha256':original['sha256'],'candidate_sha256':actual})
        else:
            require(actual == original['sha256'], 'Previously validated source changed outside exact allowlist: '+name)
    for key,value in (('BaselineSourceFilesVerified',294),('BaselineMatlabFilesVerified',149),
                      ('UnchangedBaselineSourceFilesVerified',292),('UnchangedBaselineMatlabFilesVerified',147),('AllowedModifiedSourceFilesVerified',2)):
        require(integer(metadata.get(key),key) == value, 'Baseline verified/unchanged counts disagree')
    for key,name,digest in (('BaselineOwnerEvidence','evidence/t15/owner.zip',OWNER_SHA),
                            ('BaselineCandidate','evidence/t15/candidate.json',PARENT_CANDIDATE_SHA)):
        require(candidate.get(key) == name and candidate.get(key+'SHA256') == sha256(source_root/name) == digest,
                'T15 owner/candidate provenance mismatch')
    with evidence_directory(source_root/'evidence/t15/owner.zip') as owner:
        parent = json_object(owner/'metadata.json')
        inventory(owner,parent.get('Artifacts'),excluded=('metadata.json',))
        require(parent.get('Status') == 'completed' and parent.get('TestsPassed') is True
                and parent.get('CandidateSHA256') == PARENT_CANDIDATE_SHA
                and parent.get('SourceSnapshotSHA256') == sha256(owner/'source.json') == BASELINE_SHA,
                'Baseline is not bound to completed T15 owner execution')
    return {'source_files':294,'matlab_files':149,'unchanged_source_files':292,
            'unchanged_matlab_files':147,'allowed_changes':changed}


def verify_plan(source_root, candidate):
    require(candidate.get('Plan') == 'scenarios/t16/plan.json'
            and candidate.get('PlanSHA256') == sha256(source_root/candidate['Plan']), 'Plan path/hash mismatch')
    plan = json_object(source_root/candidate['Plan'])
    require(plan.get('schema') == 'csr-tranche16-network-plan-v1' and plan.get('ns3_source_commit') == t7.PIN
            and plan.get('seeds') == [128,129,130] and plan.get('case_order') == list(CASES)
            and plan.get('policies') == list(MODES.values()) and plan.get('policy_keys') == list(MODES)
            and plan.get('case_count') == 6 and plan.get('paired_run_count') == 12
            and plan.get('paired_simulated_seconds') == 9360
            and plan.get('service_window_seconds') == [300,320] and plan.get('service_window_end_exclusive') is True
            and plan.get('timing_max_records') == 100000 and plan.get('service_max_records') == 100000, 'Network timing plan identity/membership changed')
    require(all(plan.get(key) is False for key in ('stimuli_changed','new_native_execution','opnet_available',
            'phy_ecc_changed','global_scheduler_quantized','default_policy_changed')), 'Plan overstates experiment scope')
    old = t8.verify_plan(source_root)
    original = {item['case_id']:item for item in old['cases']}
    cases = plan.get('cases')
    require(isinstance(cases,list) and [item.get('case_id') for item in cases] == list(CASES), 'Planned cases missing/duplicated')
    for item in cases:
        restored = {k:v for k,v in item.items() if k not in ('native_case_id','storage_key','max_events')}
        restored['case_id'] = item['native_case_id']
        require(restored == original.get(item['native_case_id']) and item['storage_key'] == item['case_id']
                and item['max_events'] == 12000000, 'Original native workload/configuration changed')
    for key in ('source_files','reference_files'):
        bindings = record_map(plan.get(key),'plan '+key,sizes=True)
        for name,row in bindings.items():
            path = safe_path(source_root,name)
            require(path.stat().st_size == row['bytes'] and sha256(path) == row['sha256'], 'Plan input/reference binding changed: '+name)
    # Native source traces and their compressed original hash bindings are
    # verified by the retained T8 suite checker, not inferred from candidate names.
    native = t8.verify_reference_suite(source_root,old)
    require(sha256(source_root/CONFIG_ARCHIVE) == CONFIG_ARCHIVE_SHA, 'Accepted workload configuration archive changed')
    return plan, native


def validate_timing(rows, audit, mode, config, protocol, *, label):
    require(mode in MODES, label+': unknown policy')
    require(rows, label+': no receiver timing rows')
    require(audit.get('Mode') == MODES[mode] and integer(audit.get('Count'),'timing count') == len(rows)
            and integer(audit.get('Omitted'),'timing omissions') == 0
            and integer(audit.get('MaxRecords'),'timing capacity') >= len(rows), label+': timing capacity/completion mismatch')
    nodes = {integer(item['Id'],'node'):item for item in sweep.entries(config['Nodes'],'nodes')}
    speed = number(config['Channel']['PropagationSpeedMps'],'propagation speed',minimum=0)
    require(speed > 0, label+': invalid propagation speed')
    transmissions = {}
    for event in protocol:
        if event['Event'] == 'tx_start':
            key = integer(event['PacketId'],'TX frame',1)
            require(key not in transmissions,label+': duplicate actual TX identity')
            transmissions[key] = event
    require(transmissions,label+': no actual network transmissions')
    seen, tx_values, shifts, changed, previous = set(),{},[],0,-1.0
    for ordinal,row in enumerate(rows,1):
        require(tuple(row) == TIMING_FIELDS,label+': receiver timing schema mismatch')
        require(exact_uint(row['Ordinal'],'ordinal') == ordinal,label+': missing/duplicate audit ordinal')
        frame = exact_uint(row['FrameId'],'frame')
        source,receiver = (integer(row[key],key,1) for key in ('SourceId','ReceiverId'))
        require(source in nodes and receiver in nodes and source != receiver and (frame,receiver) not in seen,
                label+': duplicate/invalid receiver identity')
        seen.add((frame,receiver))
        values = {name:full_time(row[name+'Decimal'],row[name+'Hex'],label+' '+name,signed='Shift' in name)
                  for name in TIME_FIELDS}
        # Ordinary CSV numeric columns are presentation exports; their %.17g
        # companions and binary64 hex are the authoritative timing values.
        for name,value in values.items():
            rendered = number(row[name],name)
            require(math.isclose(rendered,value,rel_tol=5e-14,abs_tol=1e-18),label+': displayed/full-precision time disagree')
        tx,prop,duration,preamble = (values[name] for name in TIME_FIELDS[:4])
        require(previous <= tx < config['DurationSeconds'] and 0 < preamble < duration and prop >= 0,
                label+': invalid transmission/component time bounds')
        previous = tx
        expected_prop = math.sqrt(sum((float(a)-float(b))**2 for a,b in zip(
            nodes[source]['PositionMeters'],nodes[receiver]['PositionMeters'])))/speed
        require(math.isclose(prop,expected_prop,rel_tol=2e-15,abs_tol=1e-20),label+': propagation differs from unchanged topology')
        require(frame in transmissions and integer(transmissions[frame]['NodeId'],'TX node') == source
                and math.isclose(float(transmissions[frame]['TimeSeconds']),tx,rel_tol=5e-14,abs_tol=1e-14),
                label+': receiver audit is not bound to actual network TX')
        tx_identity = (source,hex64(tx),hex64(duration),hex64(preamble))
        require(frame not in tx_values or tx_values[frame] == tx_identity,label+': TX components differ between receivers')
        tx_values[frame] = tx_identity
        components = [rounded_ns(value) for value in (tx,prop,duration,preamble)]
        for name,value in zip(('Tx','Propagation','Duration','Preamble'),components):
            require(exact_uint(row[name+'Nanoseconds'],name+' ns') == value and value <= 2**53,
                    label+': independently rounded component mismatch/overflow')
        sums = (components[0]+components[1],components[0]+components[1]+components[3],
                components[0]+components[1]+components[2])
        physical = (tx+prop,(tx+prop)+preamble,(tx+prop)+duration)
        for name,total,original in zip(('Start','PreambleEnd','End'),sums,physical):
            require(total <= 2**53 and exact_uint(row[name+'Nanoseconds'],name+' ns') == total,
                    label+': integer receiver sum mismatch/overflow')
            selected = original if mode == 'c' else total/1_000_000_000
            require(row['Physical'+name+'SecondsHex'] == hex64(original)
                    and row[name+'SecondsHex'] == hex64(selected)
                    and row[name+'ShiftSecondsHex'] == hex64(selected-original),
                    label+': selected receiver policy/arithmetic mismatch')
            shifts.append(abs(selected-original))
            changed += hex64(selected) != hex64(original)
        require(tx <= values['StartSeconds'] <= values['PreambleEndSeconds'] <= values['EndSeconds']
                and values['EndSeconds'] > values['StartSeconds'],label+': acausal/reversed receiver interval')
    expected = {(frame,receiver) for frame,event in transmissions.items() for receiver in nodes
                if receiver != integer(event['NodeId'],'TX node')}
    require(seen == expected,label+': missing/extra actual receiver timing coverage')
    maximum = max(shifts,default=0)
    require(hex64(number(audit.get('MaxAbsShiftSeconds'),'max shift',minimum=0)) == hex64(maximum),
            label+': reported maximum shift disagrees')
    return {'receiver_records':len(rows),'transmissions':len(transmissions),
            'changed_receiver_targets':changed,'max_abs_callback_shift_seconds':maximum,
            'omitted':0,'full_precision_component_policy_verified':True,
            'scope':'Scheduled receiver callback targets bound to actual TX frames; not an end-to-end latency error estimate.'}


def validate_phy_callbacks(timing_rows, phy_rows, stats, horizon):
    """Bind observed receiver callbacks using legacy CSV presentation precision.

The audit records exact scheduled targets. The PHY CSV does not export exact
binary64 callback times, nor a preamble-end event, so this check claims neither.
Closure receivers deliberately emit completion without a receive-start event.
"""
    targets = {(exact_uint(row['FrameId'],'frame'),integer(row['ReceiverId'],'receiver')):row for row in timing_rows}
    starts,ends,previous = {},{},-1.0
    for row in phy_rows:
        key = integer(row['PacketId'],'PHY frame'),integer(row['NodeId'],'PHY receiver')
        require(key in targets,'PHY observation references unknown receiver target')
        target = targets[key]
        require(integer(row['SourceId'],'PHY source') == integer(target['SourceId'],'source'),'PHY source differs from actual TX')
        when = number(row['TimeSeconds'],'PHY time',minimum=0)
        require(previous <= when <= horizon,'PHY callback order/horizon mismatch')
        previous = when
        start,end = float(target['StartSecondsDecimal']),float(target['EndSecondsDecimal'])
        tolerance = max(1e-14,abs(when)*5e-14)
        require(start-tolerance <= when <= end+tolerance,'PHY callback outside scheduled receiver interval')
        if row['Event'] in ('phy_signal_start','phy_signal_end'):
            observed = starts if row['Event'] == 'phy_signal_start' else ends
            expected = start if row['Event'] == 'phy_signal_start' else end
            require(key not in observed and abs(when-expected) <= tolerance,'Missing/duplicate or mistimed actual PHY callback')
            observed[key] = row
    expected_ends = {key for key,row in targets.items() if float(row['EndSecondsDecimal']) <= horizon}
    require(set(ends) == expected_ends,'Actual PHY end callback coverage differs from due targets')
    for key,row in ends.items():
        require((key in starts) == (row['Reason'] != 'closure'),'Actual PHY start coverage contradicts closure/completion')
    require(integer(stats['PhysicalReceived'],'physical received') == sum(logical(row['Success'],'PHY success') for row in ends.values())
            and integer(stats['PhysicalDropped'],'physical dropped') == sum(not logical(row['Success'],'PHY success') for row in ends.values())
            and integer(stats['PhysicalPending'],'physical pending') == len(targets)-len(ends),
            'Actual PHY completion outcomes disagree with physical counters')
    return {'actual_starts_joined':len(starts),'actual_ends_joined':len(ends),'future_end_targets':len(targets)-len(ends),
            'precision_scope':'Actual start/end callbacks joined at legacy CSV decimal precision; full binary64 applies to scheduled targets only. Preamble callback execution is not exported.'}


def validate_applications(applications, protocol, counts, case):
    generated, outcomes = {},{}
    for row in protocol:
        event = row['Event']
        if event not in ('app_generate','app_receive','app_drop','relay_accept'):
            continue
        identity = integer(row['PacketId'],'application ID',1)
        if event == 'app_generate':
            require(identity not in generated,'Duplicate generated application identity')
            generated[identity] = row
            outcomes[identity] = ('pending',None)
        elif outcomes.get(identity,('missing',))[0] != 'delivered':
            require(identity in generated,'Unknown application outcome identity')
            outcomes[identity] = ('delivered' if event == 'app_receive' else 'dropped' if event == 'app_drop' else 'pending',row)
    require(len(applications) == len(generated) == counts['Generated'],'Application export coverage mismatch')
    sent,received,seen = {},[],set()
    for row in applications:
        key = integer(row['PacketId'],'application identity',1)
        require(key in generated and key not in seen,'Missing/duplicate exported application identity')
        seen.add(key)
        original = generated[key]
        for field,source in (('SourceId','NodeId'),('DestinationId','PeerId'),('ApplicationBytes','ApplicationBytes')):
            require(integer(row[field],field) == integer(original[source],source),'Application identity/payload differs from trace')
        when = number(row['GeneratedSeconds'],'generation',minimum=0)
        require(when == float(original['TimeSeconds']),'Application generation differs from trace')
        outcome,last = outcomes[key]
        require(row['Outcome'] == outcome,'Application outcome differs from trace')
        sent[key] = (when,int(row['SourceId']),int(row['DestinationId']),int(row['ApplicationBytes'])+7)
        if outcome == 'delivered':
            arrival = number(row['ReceivedSeconds'],'delivery',minimum=0)
            require(arrival == float(last['TimeSeconds']) and arrival >= when
                    and math.isclose(float(row['LatencySeconds']),arrival-when,rel_tol=2e-12,abs_tol=1e-9),
                    'Application delivery/latency differs from actual identity trace')
            received.append((key,arrival,sent[key][3]))
        elif outcome == 'dropped':
            require(row['DropReason'] == last['Reason'] and row['DropReason'],'Application drop reason differs from trace')
    require(Counter(row['Outcome'] for row in applications) == Counter(
        {'delivered':counts['Received'],'dropped':counts['Dropped'],'pending':counts['Pending']}),
        'Application terminal count partition mismatch')
    return sent,received


def verify_feedback(directory, summary, case, protocol):
    raw = directory/'raw'
    audit = summary.get('LinkDiagnostics',{})
    require(audit.get('SchemaVersion') == 'csr-matlab-link-diagnostics-v1' and all(audit.get(key) is True
            for key in ('Enabled','Complete','Passive')) and audit.get('MaxRecords') == case['trace_limits']['link_decisions'],
            'Missing/incomplete real-network feedback observation')
    for key in ('OmittedDecisionRecords','OmittedActualFeedbackRecords','UnmatchedActualFeedbackRecords',
                'CorrelationErrors','ScheduledEvents','RandomDraws'):
        require(integer(audit.get(key),key) == 0,'Feedback observation is truncated/perturbing')
    require(all(audit.get(key) is False for key in ('LinkControlApplied','PeerS0Available','HopFailureCountAvailable')),
            'Unavailable feedback link-control inputs invented')
    rows = list(metrics.csv_rows(raw/'link_decisions.csv',('DecisionId','NodeId','PeerId','FrameKind','QueueDisposition')))
    actual = list(metrics.csv_rows(raw/'actual_feedback.csv',('ObservationId','DecisionId','AggregateId','SegmentIndex')))
    require(len(rows) == integer(audit.get('DecisionCount'),'decisions') and len(actual) == integer(audit.get('ActualFeedbackCount'),'feedback'),
            'Feedback observations differ from complete counters')
    nodes = {integer(item['Id'],'node'):item for item in sweep.entries(summary['Config']['Nodes'],'configured nodes')}
    decisions,previous = {},-1.0
    for ordinal,row in enumerate(rows,1):
        key = integer(row['DecisionId'],'decision',1)
        when = number(row['TimeSeconds'],'decision time',minimum=0)
        require(key == ordinal and previous <= when <= case['duration_s'] and row['FrameKind'] in ('ACK','DACK')
                and row['Stage'] == 'feedback_mac_admission','Invalid feedback decision identity/order/type')
        previous = when
        t8.check_rate(row,'SelectedRateKeyKbps','SelectedRateBps')
        node,peer = integer(row['NodeId'],'feedback node'),integer(row['PeerId'],'feedback peer')
        require(node in nodes and peer in nodes,'Feedback endpoint outside configured topology')
        configured = number(nodes[node]['RadioProfile']['TxPowerDbm'],'configured node power')
        require(number(row.get('ConfiguredNodePowerDbm'),'observed configured power') == configured,
                'Feedback configured power differs from original topology')
        if logical(row['PowerDefaulted'],'defaulted power'):
            require(number(row['SelectedPowerDbm'],'selected power') == configured,'Defaulted feedback power differs from configuration')
        require(not logical(row['LinkControlApplied'],'link control'),'Unavailable feedback link control was fabricated')
        if logical(row['InputContextAvailable'],'input context'):
            require(row.get('InputFrameKind') in ('DATA','CONTROL'),'Invalid incoming feedback context kind')
            t8.check_rate(row,'InputRateKeyKbps','InputRateBps')
            require(integer(row['InputRateKeyKbps'],'input rate') == integer(row['SelectedRateKeyKbps'],'selected rate'),
                    'Feedback selection differs from original incoming rate')
        else:
            require(all(metrics.optional_number(row.get(field),field) is None for field in
                    ('InputRateKeyKbps','InputRateBps','InputPowerDbm','InputReceivedPowerDbm','PathlossDb')),
                    'Unavailable incoming feedback context was fabricated')
        for field in ('AckBitmap','DackBitmap'): exact_uint(row[field],field)
        require(metrics.optional_number(row.get('PeerS0Dbm'),'peer S0') is None
                and metrics.optional_number(row.get('HopFailureCount'),'hop failure input') is None,
                'Feedback input was fabricated')
        disposition,accepted,retained_id = row['QueueDisposition'],logical(row['QueueAccepted'],'accepted'),integer(row['RetainedDecisionId'],'retained')
        if disposition in ('enqueued','replaced'):
            require(accepted and retained_id == key,'Feedback decision retained identity mismatch')
        elif disposition == 'duplicate_retained':
            require(accepted and retained_id in decisions and not logical(row['HasAckWindow'],'ACK window'),
                    'Duplicate feedback has no retained original decision')
            require(all(row[field] == decisions[retained_id][field] for field in ('NodeId','PeerId','Sequence')),
                    'Duplicate retained feedback identity differs from original peer/sequence')
        else:
            require(disposition == 'rejected' and not accepted and retained_id == 0,'Invalid feedback rejection disposition')
        decisions[key] = row
    tx = {(int(row['PacketId']),int(row['NodeId'])):float(row['TimeSeconds'])
          for row in protocol if row['Event'] == 'tx_start'}
    positions,repeats,previous = set(),Counter(),-1.0
    fields = ('NodeId','PeerId','FrameKind','Sequence','HasAckWindow','AckBitmap','DackBitmap','SelectedRateKeyKbps','SelectedPowerDbm')
    for ordinal,row in enumerate(actual,1):
        key = integer(row['DecisionId'],'decision',1)
        when = number(row['TimeSeconds'],'feedback time',minimum=0)
        require(integer(row['ObservationId'],'feedback observation',1) == ordinal and key in decisions
                and previous <= when <= case['duration_s'] and logical(row['DecisionMatched'],'matched')
                and row['Stage'] == 'ota_feedback','Actual feedback decision identity/order mismatch')
        previous = when
        decision = decisions[key]
        require(decision['QueueDisposition'] in ('enqueued','replaced') and all(row[k] == decision[k] for k in fields)
                and when >= float(decision['TimeSeconds']),'Actual feedback differs from original retained selection')
        aggregate_id,segment,count = (integer(row[k],k,1) for k in ('AggregateId','SegmentIndex','SegmentCount'))
        require(segment <= count <= 16 and (aggregate_id,segment) not in positions,'Duplicate/invalid actual feedback member')
        positions.add((aggregate_id,segment)); repeats[key] += 1
        require(tx.get((aggregate_id,int(row['NodeId']))) == when,'Feedback member has no original actual TX event')
        require(repeats[key] <= summary['Config']['Mac']['AckTransmissions'],'Feedback repeats exceed configured limit')
        t8.check_rate(row,'RateKeyKbps','RateBps')
        number(row['TxPowerDbm'],'actual power')
    hop = list(metrics.csv_rows(raw/'hop_nodes.csv',('NodeId','AckGenerated','DackGenerated')))
    mac = list(metrics.csv_rows(raw/'mac_nodes.csv',('NodeId','AckTransmissions','AckEnqueued','AckQueueDrops','AckReplacements')))
    for h in hop:
        node = int(h['NodeId']); m = next(row for row in mac if int(row['NodeId']) == node)
        selected = [row for row in rows if int(row['NodeId']) == node]
        sent = [row for row in actual if int(row['NodeId']) == node]
        require(len(selected) == int(h['AckGenerated'])+int(h['DackGenerated']) and len(sent) == int(m['AckTransmissions']),
                'Feedback traces disagree with original HOP/MAC counters')
        require(sum(row['FrameKind'] == 'DACK' for row in selected) == int(h['DackGenerated'])
                and sum(row['QueueDisposition'] == 'rejected' for row in selected) == int(h['FeedbackQueueDrops']),
                'DACK/rejection observations disagree with original HOP counters')
        for disposition,field in (('enqueued','AckEnqueued'),('replaced','AckReplacements'),('rejected','AckQueueDrops')):
            require(sum(row['QueueDisposition'] == disposition for row in selected) == int(m[field]),'Feedback queue counter mismatch')
    return {'decision_count':len(rows),'actual_feedback_member_count':len(actual),
            'queue_dispositions':dict(Counter(row['QueueDisposition'] for row in rows)),
            'selection_distribution':t8.distribution(rows,'FrameKind','SelectedRateKeyKbps','SelectedPowerDbm'),
            'ota_member_distribution':t8.distribution(actual,'FrameKind','RateKeyKbps','TxPowerDbm'),
            'actual_vs_selected_rate_change_count':sum(row['RateKeyKbps'] != row['SelectedRateKeyKbps'] for row in actual),
            'actual_vs_selected_power_change_count':sum(float(row['TxPowerDbm']) != float(row['SelectedPowerDbm']) for row in actual),
            'feedback_forms':t8.feedback_forms(rows,actual),
            'peer_s0_dbm':None,'hop_failure_input':None,
            'scope':'Feedback member counts include retained repeats; PHY aggregate envelopes remain distinct.'}


def verify_buckets(directory, case, source_hash, sent, received):
    path = directory/'analysis/aggregates.csv'
    provenance = json_object(directory/'analysis/aggregate_provenance.json')
    require(provenance.get('source_file') == 'raw/protocol_trace.csv'
            and provenance.get('source_file_sha256') == sha256(directory/'raw/protocol_trace.csv')
            and provenance.get('source_snapshot_sha256') == source_hash,'Aggregate source trace/snapshot binding mismatch')
    aggregate._check_provenance(provenance,case,'matlab',sha256(path),case['duration_s'],case['bucket_width_s'],100)
    metrics.verify_aggregates(path,sent,received,case)
    # This enforces schemas, units, aggregation semantics, source identities,
    # null samples, and every bucket independently of the reconstructed values.
    aggregate.read_series(path,'matlab',case['scenario'],provenance['source_file_sha256'],
                          case['bucket_width_s'],100,[])
    return list(metrics.csv_rows(path))


def bucket_differences(left,right):
    def mapping(rows):
        out = {}
        for row in rows:
            if row['statistic'] not in aggregate.CORE_SERIES: continue
            key = row['statistic'],float(row['time_s'])
            require(key not in out,'Duplicate aggregate identity')
            out[key] = metrics.optional_number(row['value'],'bucket value')
        require(out,'No aggregate observations')
        return out
    a,b = mapping(left),mapping(right)
    require(a.keys() == b.keys(),'Aggregate bucket grids differ')
    result = []
    for statistic in aggregate.CORE_SERIES:
        keys = [key for key in a if key[0] == statistic]
        deltas = [b[key]-a[key] for key in keys if a[key] is not None and b[key] is not None]
        result.append({'statistic':statistic,'bucket_count':len(keys),'both_populated':len(deltas),
            'missing_sample_difference_count':sum((a[k] is None) != (b[k] is None) for k in keys),
            'max_abs_bucket_difference':max(map(abs,deltas),default=None),
            'mean_signed_bucket_difference':statistics.fmean(deltas) if deltas else None})
    return result


def scalar_differences(left,right):
    keys = ('attempts','admitted','admission_blocked','delivered','delivered_unique','unmatched_sends',
            'mean_packet_latency_s','mean_populated_bucket_latency_s','network_bytes_received')
    return {key:None if left.get(key) is None or right.get(key) is None else right[key]-left[key] for key in keys}


CHECKS = ('research_accounting','performance_accounting','complete_protocol_trace','complete_phy_trace',
    'complete_admission_trace','complete_feedback_trace','complete_service_trace','timing_mode',
    'timing_coverage','timing_schema','finite_timing','causal_callbacks','physical_operands',
    'timing_policy','timing_shift_bound','scenario_identity')


def verify_case(directory, source_root, case, mode, entry, source_hash, runtime, expected_source, accepted_config):
    manifest_path = directory/'case.json'
    manifest = json_object(manifest_path)
    require(entry.get('ManifestSHA256') == sha256(manifest_path)
            and manifest.get('schema') == 'csr-tranche16-network-case-v1' and manifest.get('status') == 'completed',
            'Case manifest identity/hash mismatch')
    for field in ('case_id','native_case_id','storage_key','base_case_id','scenario','scenario_sha256',
                  'profile_id','seed','duration_s','bucket_width_s','reference_directory'):
        require(manifest.get(field) == case[field], 'Case stimulus identity mismatch: '+field)
    require(manifest.get('policy_key') == mode and manifest.get('mode') == MODES[mode]
            and manifest.get('source_snapshot_sha256') == source_hash and manifest.get('ns3_source_commit') == t7.PIN
            and manifest.get('structural_checks_passed') is True and manifest.get('structural_check_count') == 16
            and manifest.get('numerical_parity_established') is False,'Case policy/source/scope mismatch')
    t7.inventory(directory,manifest.get('files'),'case files',excluded=('case.json',),local=manifest.get('local_files',[]))
    raw = directory/'raw'
    raw_manifest = json_object(raw/'case_manifest.json')
    require(raw_manifest.get('schema') == 'csr-matlab-research-case-v1' and raw_manifest.get('status') == 'completed'
            and all(raw_manifest.get(k) is True for k in ('execution_completed','structural_checks_passed','source_files_stable'))
            and raw_manifest.get('ns3_source_commit') == t7.PIN
            and sweep.snapshot(raw_manifest.get('source_files'),'raw source') == expected_source,
            'Actual network execution/source identity mismatch')
    t7.inventory(raw,raw_manifest.get('files'),'raw case files',excluded=('case_manifest.json',),local=raw_manifest.get('local_files',[]))
    require(sha256(raw/'scenario.csv') == case['scenario_sha256'],'Actual scenario file hash differs from unchanged input')
    summary = json_object(raw/'summary.json')
    config,stats,md = summary['Config'],summary['Statistics'],summary['Metadata']
    require(manifest.get('runtime') == md and md.get('Version') == runtime['Version'] and md.get('Release') == runtime['Release']
            and md.get('Backend') == 'portable' and md.get('SourceCommit') == t7.PIN,'Case MATLAB backend/runtime/source differs')
    original_case = dict(case,case_id=case['native_case_id'])
    configuration = retained.same_configuration(accepted_config,config,source_root,original_case)
    require(config.get('Channel',{}).get('Model') == 'csr-phy' and config.get('Stack') == 'network'
            and config.get('ApplicationGenerator') == 'historical-opnet-gated', 'Controlled/replaced workload supplied as real network')
    accounting = retained.verify_raw_accounting(raw,summary)
    require(accounting['counts']['Generated'] > 0,'Zero generated applications cannot complete this network milestone')
    protocol = list(metrics.csv_rows(raw/'protocol_trace.csv'))
    performance = csv_rows(directory/'analysis/performance_summary.csv')
    require(len(performance) == 1,'Missing/duplicate per-case performance summary')
    measured = sweep.metrics(performance[0])
    require(all(measured[k] == accounting['counts'][k] for k in t7.COUNTS),'Performance/raw application count mismatch')
    require(manifest.get('data_drained') is bool(measured['DataDrained']), 'Manifest drain flag mismatch')
    maps = {
        'hop_nodes.csv': {'PendingData':'HopPendingData','ResendQueueDepth':'ResendQueueDepth','DackHoldCount':'DackHoldCount',
                         'ControlPending':'ControlPending','ControlPendingTargets':'ControlPendingTargets',
                         'Retransmissions':'HopDataRetransmissions','ControlRetransmissions':'HopControlRetransmissions'},
        'nwk_nodes.csv': {'PendingCustody':'NwkPendingCustody','PendingControlMessages':'NwkPendingControlMessages'},
        'mac_nodes.csv': {'Transmissions':'PhysicalTransmissions','SegmentsTransmitted':'MacMemberTransmissions',
                         'AckTransmissions':'AckFeedbackMemberTransmissions'}}
    counters = {}
    for filename,mapping in maps.items():
        node_rows = list(metrics.csv_rows(raw/filename,tuple(mapping)))
        for field,metric in mapping.items():
            count = sum(integer(row[field],field) for row in node_rows)
            require(integer(performance[0][metric],metric) == count,'Performance/node ownership or transmission count mismatch')
        counters[filename] = {field:sum(integer(row[field],field) for row in node_rows)
                              for field in node_rows[0] if field != 'NodeId' and all(row[field].isdigit() for row in node_rows)}
    timing_rows = csv_rows(directory/'timing.csv',TIMING_FIELDS)
    audit = json_object(directory/'timing.json')
    require(audit.get('Schema') == 'csr-tranche16-transport-audit-v1' and audit.get('MaxRecords') == 100000
            and {k:v for k,v in audit.items() if k != 'Schema'} == manifest.get('timing_diagnostics')
            and integer(stats.get('PhysicalAttempts'),'physical attempts') == len(timing_rows), 'Timing audit/schema/counter binding mismatch')
    timing = validate_timing(timing_rows,audit,mode,config,protocol,label=mode+'/'+case['case_id'])
    timing['actual_callbacks'] = validate_phy_callbacks(timing_rows,list(metrics.csv_rows(raw/'phy_trace.csv')),stats,case['duration_s'])
    require(manifest.get('observer_diagnostics') == summary.get('LinkDiagnostics')
            and manifest.get('service_diagnostics') == summary.get('ServiceDiagnostics'),'Observer manifests differ from raw summary')
    feedback = verify_feedback(directory,summary,case,protocol)
    import tranche9_metrics as service
    service_rows = list(metrics.csv_rows(raw/'service_trace.csv'))
    service_report = service.verify_matlab_rows(service_rows,protocol,
        list(metrics.csv_rows(raw/'application_admission_trace.csv')),
        list(metrics.csv_rows(raw/'link_decisions.csv')),summary['ServiceDiagnostics'],
        {'service_window_s':[300,320],'service_max_records':100000})
    service_report['capacity_release_observations'] = sum(metrics.optional_number(row.get('CapacityReleased'),'release') == 1
                                                         for row in service_rows)
    service_report['capacity_scope'] = 'Recorded callback capacity-release flags in [300,320); no inferred release time between snapshots.'
    app_rows = list(metrics.csv_rows(directory/'analysis/applications.csv'))
    sent,received = validate_applications(app_rows,protocol,accounting['counts'],case)
    applications = metrics.matlab_applications(directory,case)
    buckets = verify_buckets(directory,case,source_hash,sent,received)
    result = {'case_id':case['case_id'],'mode':MODES[mode],'seed':case['seed'],'duration_seconds':case['duration_s'],
        'configuration':configuration,'accounting':accounting,'applications':applications,'feedback':feedback,
        'service':service_report,'timing':timing,'node_counter_totals':counters,
        'data_drained':bool(measured['DataDrained']),'controls_drained':bool(measured['ControlsDrained'])}
    return result,performance[0],buckets


def verify_network(root,metadata,source_root,candidate,plan):
    require(metadata.get('TimingDirectory') == 'network' and metadata.get('TimingCompleted') is True
            and metadata.get('TimingPassed') is True,'Paired network completion is missing')
    combined = json_object(root/'network/summary.json')
    require(combined.get('Schema') == 'csr-tranche16-network-timing-contract-v1'
            and combined.get('DiagnosticCompleted') is True and combined.get('Passed') is True
            and combined.get('NumericalParityEstablished') is False and combined.get('FullAcceptanceEstablished') is False,
            'Network summary schema/completion/scope mismatch')
    for key,value in (('ModeCount',2),('CaseCount',12),('PlannedCaseCount',12),('CheckpointCount',192),
        ('FailedCount',0),('SimulatedSecondsCompleted',9360),('PlannedSimulatedSeconds',9360),
        ('TimingMaxRecords',100000),('ObserverMaxRecords',100000)):
        require(integer(combined.get(key),key) == value,'Network summary count/budget mismatch')
    for key,value in (('TimingModeCount',2),('TimingCaseCount',12),('TimingCheckpointCount',192),('TimingFailedCount',0)):
        require(integer(metadata.get(key),key) == value,'Network metadata counters disagree')
    require(candidate.get('ExpectedStructuralCheckCount') == 192 and combined.get('PlanSHA256') == candidate.get('PlanSHA256')
            and combined.get('Runtime') == metadata['Runtime']['Version'] and combined.get('ServiceWindowSeconds') == [300,320]
            and combined.get('SourceSnapshotSHA256') == metadata.get('SourceSnapshotSHA256')
            == sha256(root/'network/source.json'),'Network source/plan/runtime/service window binding mismatch')
    expected_order = [(mode,case) for case in CASES for mode in MODES]
    entries = combined.get('Cases')
    require(isinstance(entries,list) and [(item.get('PolicyKey'),item.get('CaseId')) for item in entries] == expected_order,
            'Network cases missing, duplicated, extra or reordered')
    source = candidate_snapshot(source_root)
    require(sweep.snapshot(json_value(root/'network/source.json'),'network source') == source,'Network source snapshot differs')
    summary_rows = csv_rows(root/'network/summary.csv')
    require([(row.get('PolicyKey'),row.get('CaseId')) for row in summary_rows] == expected_order,'Network aggregate case membership differs')
    checks = csv_rows(root/'network/checks.csv',('PolicyKey','CaseId','Check','Passed'))
    require([(row['PolicyKey'],row['CaseId'],row['Check']) for row in checks] ==
            [(mode,case,check) for mode,case in expected_order for check in CHECKS]
            and all(logical(row['Passed'],'structural pass') for row in checks),'Missing/failed/duplicate structural check identity')
    results,bucket_sets,native = {},{},{}
    cases = {case['case_id']:case for case in plan['cases']}
    with zipfile.ZipFile(source_root/CONFIG_ARCHIVE) as archive:
        for entry,row in zip(entries,summary_rows):
            mode,key = entry['PolicyKey'],entry['CaseId']; case = cases[key]
            require(entry.get('Directory') == mode+'/'+key and entry.get('NativeCaseId') == case['native_case_id']
                    and entry.get('Mode') == MODES[mode] and entry.get('Passed') is True
                    and entry.get('DurationSeconds') == case['duration_s'], 'Paired case entry policy/path/horizon changed')
            accepted_config = json.loads(archive.read(f'b/{key}/raw/summary.json'))['Config']
            observed,performance,buckets = verify_case(root/'network'/mode/key,source_root,case,mode,entry,
                metadata['SourceSnapshotSHA256'],metadata['Runtime'],source,accepted_config)
            require(all(row.get(field) == value for field,value in performance.items()),'Aggregate/per-case performance rows differ')
            require(row.get('Mode') == MODES[mode] and row.get('NativeCaseId') == case['native_case_id'] and row.get('StorageKey') == key
                    and integer(row.get('Attempts'),'attempts') == observed['applications']['attempts']
                    and integer(row.get('AdmissionBlocked'),'blocked') == observed['applications']['admission_blocked']
                    and integer(row.get('OmittedApplicationAdmissionRecords'),'omissions') == 0,'Network aggregate diagnostics differ')
            results[mode,key],bucket_sets[mode,key] = observed,buckets
            if key not in native:
                reference = source_root/case['reference_directory']
                native[key] = {'applications':metrics.ns3_applications(reference,case),
                               'feedback':t8.verify_ns3_feedback(reference,case)}
                bucket_sets['native',key] = list(metrics.csv_rows(reference/'ns3-aggregates.csv'))
    paired = []
    for key in CASES:
        a,b = results['c',key],results['n',key]
        paired.append({'case_id':key,'nanoseconds_minus_continuous':scalar_differences(a['applications'],b['applications']),
            'continuous_minus_native':scalar_differences(native[key]['applications'],a['applications']),
            'nanoseconds_minus_native':scalar_differences(native[key]['applications'],b['applications']),
            'nanoseconds_minus_continuous_buckets':bucket_differences(bucket_sets['c',key],bucket_sets['n',key]),
            'continuous_minus_native_buckets':bucket_differences(bucket_sets['native',key],bucket_sets['c',key]),
            'nanoseconds_minus_native_buckets':bucket_differences(bucket_sets['native',key],bucket_sets['n',key]),
            'ack_feedback_members_change':b['feedback']['actual_feedback_member_count']-a['feedback']['actual_feedback_member_count'],
            'physical_transmissions_change':b['timing']['transmissions']-a['timing']['transmissions']})
    return {'case_count':12,'checkpoint_count':192,'simulated_seconds':9360,
            'cases':[results[key] for key in expected_order],'native':native,'paired_comparisons':paired,
            'interpretation':'Same MATLAB seed pairs policies, not cross-simulator packet identities. Native unmatched sends are not classified as drops or pending. Bucket differences retain missing samples; timing audits describe receiver targets, not physical timing measurements or positional end-to-end errors.'}


def verify_preparation(source_root):
    """Read-only preflight of issued code/inputs, making no owner-run claim."""
    source_root = Path(source_root).resolve()
    candidate = json_object(source_root/CANDIDATE)
    require(candidate.get('Schema') == 'csr-tranche-16-candidate-v1' and candidate.get('SourceCommit') == t7.PIN,
            'Candidate identity/source pin mismatch')
    expected = candidate_snapshot(source_root)
    require(candidate.get('SourceFilesExcludedPaths') == [CANDIDATE]
            and {name:row['sha256'] for name,row in record_map(candidate.get('SourceFiles'),'candidate source').items()}
            == {name:digest for name,digest in expected.items() if name != CANDIDATE},
            'Frozen candidate source file set/hash differs')
    baseline = verify_baseline({'BaselineSourceFilesVerified':294,'BaselineMatlabFilesVerified':149,
        'UnchangedBaselineSourceFilesVerified':292,'UnchangedBaselineMatlabFilesVerified':147,'AllowedModifiedSourceFilesVerified':2},source_root,candidate)
    plan,native = verify_plan(source_root,candidate)
    from analyze_tranche11_return import selected_test_names
    names = selected_test_names(source_root,candidate.get('TestFiles'))
    require(candidate.get('ExpectedTestNames') == names and len(names) == 129,
            'Prepared MATLAB test membership differs')
    return {'status':'prepared_for_owner_matlab_execution','source_files':len(expected),'baseline':baseline,
            'planned_matlab_tests':len(names),'planned_cases':12,'native_reference_reused':True,
            'matlab_executed':False,'native_executed':False}


def review(evidence,source_root,output):
    evidence,source_root,output = map(lambda p:Path(p).resolve(),(evidence,source_root,output))
    preparation = verify_preparation(source_root)
    candidate = json_object(source_root/CANDIDATE)
    plan,_ = verify_plan(source_root,candidate)
    with evidence_directory(evidence) as root:
        metadata = json_object(root/'metadata.json')
        runtime = verify_identity(root,metadata,source_root,candidate)
        artifacts = inventory(root,metadata.get('Artifacts'),excluded=('metadata.json',))
        require({'source.json','references.json','tests.csv','run.log','network/summary.json','network/source.json',
                 'network/checks.csv','network/summary.csv'} <= set(artifacts),'Required paired network evidence missing')
        source = verify_sources(root,metadata,source_root)
        baseline = verify_baseline(metadata,source_root,candidate)
        references = verify_references(root,metadata,source_root,candidate)
        tests = verify_tests(root,metadata,source_root,candidate)
        network = verify_network(root,metadata,source_root,candidate,plan)
    result = {'schema':REVIEW_SCHEMA,'status':'focused_diagnostic_review_completed','evidence_integrity_verified':True,
        'focused_structural_gate_completed':True,'acceptance_established':False,'numerical_parity_established':False,
        'matlab_executed_by_reviewer':False,'runtime':runtime,'source':source,'baseline':baseline,
        'references':references,'tests':tests,'network':network,
        'evidence':{'path':evidence.name,'bytes':evidence.stat().st_size,'sha256':sha256(evidence)}}
    output.mkdir(parents=True,exist_ok=True)
    (output/'review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        result = review(args.evidence,args.source_root,args.output)
    except (ValueError,OSError,csv.Error,zipfile.BadZipFile,KeyError,TypeError,OverflowError,StopIteration) as error:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'review.json').write_text(json.dumps({'schema':REVIEW_SCHEMA,'status':'review_failed',
            'evidence_integrity_verified':False,'focused_structural_gate_completed':False,'acceptance_established':False,
            'numerical_parity_established':False,'matlab_executed_by_reviewer':False,'error':str(error)},indent=2)+'\n',encoding='utf-8')
        print('T16 evidence rejected: '+str(error)); return 1
    print(f"T16 focused review complete: {result['tests']['count']} MATLAB tests and 12 real-network cases; numerical differences remain explicit.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
