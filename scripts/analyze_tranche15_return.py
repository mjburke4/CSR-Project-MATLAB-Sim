#!/usr/bin/env python3
"""Audit the paired T15 transport-time experiment; never execute MATLAB.

T13's immutable structural checker is reused after T15 archive/source/reference
and exact test identity verification. A successful focused result need not match
ns-3. Exact semantic/outcome deltas remain separate from positional comparisons.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
import csv
import json
import math
from pathlib import Path
import shutil
import tempfile
import zipfile

import analyze_tranche13_return as loss
from analyze_tranche11_return import (
    all_files, candidate_snapshot, csv_rows, evidence_directory, integer,
    inventory, json_object, json_value, record_map, records, require, safe_path,
    selected_test_names, sha256, verify_references, verify_sources, verify_tests,
)
from analyze_tranche14_return import full_time, hex64, rounded_ns, exact_uint

SCHEMA = 'csr-matlab-tranche-15-validation-v1'
REVIEW_SCHEMA = 'csr-matlab-tranche-15-return-review-v1'
CANDIDATE = 'evidence/tranche-15-candidate.json'
BASELINE = 'evidence/t14/source.json'
BASELINE_SHA = '3073c350f5fb999017a0a3a4f8ea168e1340a5ea183638eb14ea9fb4ba30030e'
OWNER_SHA = '1b351bc8cf356ace8fe5e60413cba30812b5c3fcb4d71cede29d356102fe4241'
PARENT_CANDIDATE_SHA = '4bb51710031ead9d8d7c6b718fb41fd9224156b46076111e4e9c161aebbcc69f'
MODES = ('c', 'n')
TIMING_FIELDS = ('case','tx_id','sender','tx_seconds','tx_hex','duration_seconds','duration_hex',
    'propagation_seconds','propagation_hex','continuous_seconds','continuous_hex',
    'nanoseconds_seconds','nanoseconds_hex','arrival_seconds','arrival_hex','delta_seconds','delta_hex',
    'tx_ns','duration_ns','propagation_ns','sum_ns','wire_payload_bytes','segment_count','preamble','rate_kbps','power_dbm')
PRECISION_FIELDS = ('case','order','time_ns','event','node','peer','app_source','app_id','hop_seq',
                    'ack_bits','dack_bits','time_seconds','time_hex')
FAMILIES = (*loss.FAMILIES, ('check', loss.CHECK_FIELDS))
EXTRA_FAMILIES = (('timing', TIMING_FIELDS), ('precision', PRECISION_FIELDS))


def verify_run_identity(root, metadata, source_root, candidate):
    require(candidate.get('Schema') == 'csr-tranche-15-candidate-v1' and candidate.get('Tranche') == 15
            and candidate.get('SourceCommit') == loss.PIN and candidate.get('EngineCommit') == loss.ENGINE_PIN,
            'Candidate identity/native source pin mismatch')
    require(metadata.get('Schema') == SCHEMA and metadata.get('Tranche') == 15
            and metadata.get('Status') == 'completed', 'Return is not a completed T15 diagnostic')
    require(metadata.get('MATLABExecuted') is True and metadata.get('NativeExecuted') is False
            and metadata.get('SourceCommit') == loss.PIN, 'Missing owner execution/source identity')
    runtime = metadata.get('Runtime')
    require(isinstance(runtime, dict) and runtime.get('Runtime') == 'MATLAB'
            and runtime.get('DefaultBackend') == 'portable' and isinstance(runtime.get('Version'), str)
            and runtime['Version'], 'Missing/unsupported MATLAB runtime provenance')
    require(metadata.get('CandidateFile') == CANDIDATE
            and metadata.get('CandidateSHA256') == sha256(source_root / CANDIDATE), 'Candidate hash mismatch')
    started, completed = (datetime.fromisoformat(metadata.get(field, '').replace('Z', '+00:00'))
                          for field in ('StartedUTC', 'CompletedUTC'))
    require(started.tzinfo is not None and completed.tzinfo is not None and completed >= started,
            'Invalid owner execution timestamps')
    require(metadata.get('InventoryExcludedPaths') == ['metadata.json']
            and metadata.get('EvidenceArchive') == 't15.zip', 'Evidence archive/exclusion changed')
    local = record_map(metadata.get('LocalArtifacts', []), 'local artifacts', sizes=True, empty=True)
    require(all(name.endswith('.mat') and name not in all_files(root) for name in local), 'Invalid local-only artifacts')
    require(metadata.get('FocusedGateExecuted') is True and metadata.get('DiagnosticOnly') is True
            and all(metadata.get(field) is False for field in
                ('FullAcceptanceGateExecuted', 'AcceptanceEstablished', 'NumericalParityEstablished')),
            'Unsupported acceptance/parity claim or missing focused scope')
    return runtime


def verify_baseline(metadata, source_root, candidate):
    require(candidate.get('BaselineSourceSnapshot') == BASELINE
            and candidate.get('BaseSourceSnapshotSHA256') == sha256(source_root / BASELINE) == BASELINE_SHA,
            'T14 source snapshot binding mismatch')
    source = record_map(json_value(source_root / BASELINE), 'T14 source')
    require(len(source) == 285 and sum(name.endswith('.m') for name in source) == 144,
            'T14 source membership changed')
    for name, row in source.items():
        require(sha256(safe_path(source_root, name)) == row['sha256'], f'Validated T14 source changed: {name}')
    for field, value in (('SourceFiles', 285), ('MatlabFiles', 144)):
        require(integer(candidate.get('Baseline' + field + 'Unchanged'), field) == value
                and integer(metadata.get('Baseline' + field + 'Verified'), field) == value,
                'T14 baseline counts disagree')
    for field, name, digest in (
        ('BaselineOwnerEvidence','evidence/t14/owner.zip',OWNER_SHA),
        ('BaselineCandidate','evidence/t14/candidate.json',PARENT_CANDIDATE_SHA)):
        require(candidate.get(field) == name and candidate.get(field + 'SHA256') == sha256(source_root / name) == digest,
                'T14 owner/candidate provenance mismatch')
    with evidence_directory(source_root / 'evidence/t14/owner.zip') as owner:
        parent = json_object(owner / 'metadata.json')
        inventory(owner, parent.get('Artifacts'), excluded=('metadata.json',))
        require(parent.get('Status') == 'completed' and parent.get('TestsPassed') is True
                and parent.get('CandidateSHA256') == PARENT_CANDIDATE_SHA
                and parent.get('SourceSnapshotSHA256') == sha256(owner / 'source.json') == BASELINE_SHA,
                'Reviewed T14 source not bound to completed owner run')
    core = record_map(json_value(source_root / loss.CORE_BASELINE), 'accepted core')
    require(candidate.get('CoreBaselineSourceSnapshot') == loss.CORE_BASELINE
            and candidate.get('CoreBaselineSourceSnapshotSHA256') == sha256(source_root / loss.CORE_BASELINE) == loss.CORE_BASELINE_SHA,
            'Accepted core source binding changed')
    require(len(core) == 225 and sum(name.endswith('.m') for name in core) == 124, 'Accepted core membership changed')
    for name, row in core.items():
        require(sha256(safe_path(source_root, name)) == row['sha256'], 'Accepted core source changed')
    for field, value in (('SourceFiles',225), ('MatlabFiles',124)):
        require(integer(candidate.get('CoreBaseline' + field + 'Unchanged'),field) == value
                and integer(metadata.get('CoreBaseline' + field + 'Verified'),field) == value, 'Core baseline counts disagree')
    return {'source_files': 285, 'matlab_files': 144, 'unchanged': True, 'snapshot_sha256': BASELINE_SHA,
            'accepted_core': {'source_files': 225, 'matlab_files': 124, 'unchanged': True}}


def verify_plan(source_root, candidate):
    require(candidate.get('TimingPlan') == 'scenarios/t15/plan.json', 'Unexpected timing plan path')
    path = source_root / candidate['TimingPlan']
    require(candidate.get('TimingPlanSHA256') == sha256(path), 'Timing plan hash mismatch')
    plan = json_object(path)
    require(plan.get('schema') == 'csr-tranche15-loss-timing-input-v1'
            and plan.get('source_pin') == loss.PIN and plan.get('engine_pin') == loss.ENGINE_PIN
            and plan.get('modes') == ['continuous','nanoseconds'] and plan.get('mode_directories') == list(MODES)
            and plan.get('cases') == list(loss.CASES),
            'Timing plan identity/modes/cases changed')
    require(plan.get('timing_schema') == list(TIMING_FIELDS)
            and plan.get('precision_schema') == list(PRECISION_FIELDS), 'Timing evidence schema changed')
    for field, value in (('case_count_per_mode',4), ('total_case_count',8), ('duration_seconds',64),
                         ('checkpoint_count_per_mode',264), ('total_checkpoint_count',528)):
        require(integer(plan.get(field), field) == value, 'Timing fixed plan counts/horizon changed')
    require(plan.get('case_directories') == ['c1','c2','c3','c4'], 'Per-case path membership changed')
    loss.verify_bindings(plan.get('input_bindings'), source_root,
        ['scenarios/loss/' + name for name in ('plan.json','cases.csv','offers.csv','draws.csv')], 'T15 retained loss inputs')
    require(plan.get('native_reference_directory') == loss.REFERENCE
            and plan.get('native_reference_manifest_sha256') == sha256(source_root / loss.REFERENCE / 'manifest.json'),
            'T15 native reference binding changed')
    old = json_object(source_root / loss.CANDIDATE)
    loss.verify_plan(source_root, old)
    return plan, old


def validate_precision(rows, events, *, label):
    require(len(rows) == len(events) and rows, f'{label}: missing/extra precision observations')
    times = {}
    last = defaultdict(float)
    for row, event in zip(rows, events):
        require(tuple(row) == PRECISION_FIELDS, f'{label}: invalid precision schema')
        require(all(row[field] == event[field] for field in PRECISION_FIELDS[:-2]),
                f'{label}: precision identity differs from actual event')
        key = row['case'], integer(row['order'], 'precision order', 1)
        require(key not in times, f'{label}: duplicate precision identity')
        value = full_time(row['time_seconds'], row['time_hex'], label + ' time')
        require(value <= 64 and value >= last[row['case']], f'{label}: precision time reversed/outside horizon')
        require(rounded_ns(value) == integer(row['time_ns'], 'precision nanoseconds'),
                f'{label}: precision nanoseconds contradict binary64 value')
        last[row['case']] = value
        times[key] = value
    return times


def _segment_identity(row, *, transport=False, transmit=False):
    fields = ('app_source', 'app_id', 'hop_seq', 'ack_bits', 'dack_bits')
    nodes = (('sender','receiver') if transmit else ('receiver','sender')) if transport else ('node','peer')
    return tuple(integer(row[field], field) for field in (*nodes, *fields))


def validate_timing(rows, transport, events, precision, mode, *, label):
    require(mode in MODES, f'{label}: unknown timing mode')
    require(rows, f'{label}: no timing records')
    times = validate_precision(precision, events, label=label)
    by_tx = defaultdict(list)
    for segment in transport:
        by_tx[segment['case'], integer(segment['tx_id'], 'transport TX ID', 1)].append(segment)
    require([(row['case'], integer(row['tx_id'], 'timing TX ID', 1)) for row in rows] == list(by_tx),
            f'{label}: timing TX identities missing/duplicate/reordered')
    expected = {name: Counter() for name in ('tx_start', 'ingress_before', 'ingress_after', 'loss')}
    changed = 0
    maximum_delta = 0.0
    for row in rows:
        require(tuple(row) == TIMING_FIELDS, f'{label}: timing schema changed')
        case, tx_id = row['case'], integer(row['tx_id'], 'timing TX ID', 1)
        segments = by_tx[case, tx_id]
        require(all(integer(segment['sender'], 'sender') == integer(row['sender'], 'sender') for segment in segments),
                f'{label}: timing sender differs from actual TX')
        values = {name: full_time(row[name + '_seconds'], row[name + '_hex'], label + ' ' + name,
                                 signed=name == 'delta') for name in
                  ('tx','duration','propagation','continuous','nanoseconds','arrival','delta')}
        tx, duration, propagation = (values[name] for name in ('tx','duration','propagation'))
        require(0 <= tx < 64 and duration > 0 and propagation == 1e-6,
                f'{label}: invalid callback duration/propagation/horizon')
        require(integer(row['segment_count'], 'segments', 1) == len(segments)
                and row['preamble'] in ('long','short') and integer(row['rate_kbps'], 'rate') == 128
                and integer(row['power_dbm'], 'power') == 33, f'{label}: emitted envelope selection/count changed')
        payload_bytes = integer(row['wire_payload_bytes'], 'wire payload')
        # Bare DATA is 16 app bytes + 32 modeled envelope bytes. Every
        # feedback frame in this fixed DATA fixture carries its ACK window:
        # 25 + 16 bytes. No reliable control transport is enabled.
        require(payload_bytes == sum(48 if segment['kind'] == 'DATA' else 41 for segment in segments),
                f'{label}: emitted payload bytes disagree with actual segment accounting')
        preamble_bits = 7888 if row['preamble'] == 'long' else 104
        # Preserve source operation order and its exact operational rate; the
        # legacy key 128 denotes 4/30us, not 128000 bits per second.
        expected_duration = ((preamble_bits + 48) / 4 * .000510) + ((payload_bytes * 8 + 32) / (4 / .000030))
        require(hex64(duration) == hex64(expected_duration), f'{label}: callback duration contradicts source airtime')
        component_ns = [rounded_ns(values[name]) for name in ('tx','duration','propagation')]
        require(all(exact_uint(row[name + '_ns'], name + ' ns') == value
                    for name, value in zip(('tx','duration','propagation'), component_ns)),
                f'{label}: component conversion differs from independent rounding')
        total = sum(component_ns)
        require(total <= 64_000_000_000 and total <= 2**53
                and exact_uint(row['sum_ns'], 'sum ns') == total,
                f'{label}: integer sum exceeds horizon/exact range or is inconsistent')
        continuous = (tx + duration) + propagation
        quantized = total / 1_000_000_000
        selected = continuous if mode == 'c' else quantized
        for name, value in (('continuous', continuous), ('nanoseconds', quantized),
                            ('arrival', selected), ('delta', selected - continuous)):
            require(row[name + '_hex'] == hex64(value), f'{label}: {name} arithmetic/policy mismatch')
        require(selected > tx and selected <= 64, f'{label}: invalid actual arrival interval')
        changed += hex64(continuous) != hex64(quantized)
        maximum_delta = max(maximum_delta, abs(quantized - continuous))
        for segment in segments:
            require(integer(segment['tx_time_ns'], 'TX ns') == component_ns[0]
                    and integer(segment['arrival_ns'], 'arrival ns') == rounded_ns(selected),
                    f'{label}: timing record is not bound to actual segment transport')
            tx_key = (case, hex64(tx), _segment_identity(segment, transport=True, transmit=True))
            arrival_key = (case, hex64(selected), _segment_identity(segment, transport=True))
            expected['tx_start'][tx_key] += 1
            for name in (('loss',) if segment['decision'] == 'drop' else ('ingress_before','ingress_after')):
                expected[name][arrival_key] += 1
    for name, expected_rows in expected.items():
        observed = Counter((event['case'], hex64(times[event['case'], integer(event['order'], 'event order')]),
                            _segment_identity(event)) for event in events if event['event'] == name)
        require(observed == expected_rows, f'{label}: full-precision {name} observations do not close against transport')
    return {'transmissions': len(rows), 'precision_events': len(precision),
            'continuous_vs_component_conversion_different': changed,
            'maximum_conversion_shift_seconds': format(maximum_delta, '.17g'),
            'actual_arrival_times_bound_to_transport_and_protocol_events': True,
            'duration_scope': 'Actual production MAC callback duration independently recomputed from emitted aggregate payload, preamble and exact source rate; PHY/ECC unchanged.'}


def verify_partial_cases(directory, actual, summary):
    results = records(summary.get('CaseResults'), 'case results')
    count = 0
    for index, case in enumerate(loss.CASES, 1):
        partial = directory / ('c' + str(index))
        require(json_object(partial / 'result.json') == results[index - 1], 'Per-case result differs from branch summary')
        count += 1
        for name, fields in (*FAMILIES, *EXTRA_FAMILIES):
            require(csv_rows(partial / (name + '.csv'), fields) == [row for row in actual[name] if row['case'] == case],
                    f'Per-case {name} rows differ from aggregate evidence')
            count += 1
    return count


def verify_original_continuous(actual, source_root):
    """This is a real reviewed owner archive, never synthesized pass evidence."""
    path = source_root / 'evidence/t13/owner.zip'
    require(sha256(path) == '82fb77cc5724f79f554e7c0d91169e79d89da5b47713064f003d380a2fd7d9b1',
            'Accepted T13 owner archive binding mismatch')
    with evidence_directory(path) as root:
        metadata = json_object(root / 'metadata.json')
        inventory(root, metadata.get('Artifacts'), excluded=('metadata.json',))
        require(metadata.get('Status') == 'completed' and metadata.get('TestsPassed') is True
                and metadata.get('CandidateSHA256') == '3c9ba4a9d9029180b82611d71dcbb01ac6cd2ddc273ee6ecf6dec36ba81881e0',
                'T13 baseline owner completion/candidate mismatch')
        for name, fields in FAMILIES:
            baseline = csv_rows(root / 'loss' / (name + '.csv'), fields)
            require(actual[name] == baseline, f'Continuous baseline changed: {name}; diagnostic fork not accepted')
    return {'matches_all_six_accepted_owner_tables_exactly': True, 'owner_sha256': sha256(path)}


def _time_statistics(values):
    if not values:
        return {'count': 0, 'minimum_seconds': None, 'maximum_seconds': None, 'mean_seconds': None}
    return {'count': len(values), 'minimum_seconds': str(min(values)), 'maximum_seconds': str(max(values)),
            'mean_seconds': str(sum(values) / len(values))}


def outcome_metrics(actual):
    """Identity-aligned outcomes; ACK-loss delivery/failed-terminal overlap is retained."""
    output = {}
    precision = {(row['case'], row['order']): Decimal.from_float(full_time(row['time_seconds'], row['time_hex'], 'metric time'))
                 for row in actual.get('precision', [])}
    def when(row):
        return precision.get((row['case'], row['order']), Decimal(row['time_ns']) / 1_000_000_000)
    for case in loss.CASES:
        events = [row for row in actual['events'] if row['case'] == case]
        segments = [row for row in actual['transport'] if row['case'] == case]
        terminals = [row for row in actual['terminal'] if row['case'] == case]
        apps = defaultdict(dict)
        hop_starts, hop_first_tx = {}, {}
        releases = defaultdict(list)
        def appkey(row):
            return f"{int(row['app_source'])}:{int(row['app_id'])}"
        for row in events:
            event, source, node = row['event'], int(row['app_source']), int(row['node'])
            key = appkey(row)
            if event in ('generate','admit','deliver'):
                apps[key][event] = when(row)
            hop_key = f'{node}/{key}'
            if event == 'admit' or (event == 'ingress_before' and node == 5 and source == 4):
                hop_starts.setdefault(hop_key, Decimal(row['time_ns']) / 1_000_000_000)
            if event == 'tx_start' and source:
                hop_first_tx.setdefault(hop_key, Decimal(row['time_ns']) / 1_000_000_000)
            if event == 'release':
                releases[f'{node}/{source}'].append({'time_seconds': str(when(row)),
                    'nsdp4': int(row['nsdp4']), 'nsdp5': int(row['nsdp5']), 'nwk_custody': int(row['nwk_custody']),
                    'hop_pending': int(row['hop_pending']), 'resend_queue': int(row['resend_queue'])})
        identities = {}
        for key, values in sorted(apps.items()):
            identities[key] = {name + '_seconds': str(value) for name, value in values.items()}
            for name, start, stop in (('admission_wait', 'generate', 'admit'), ('delivery_latency', 'generate', 'deliver')):
                if start in values and stop in values:
                    identities[key][name + '_seconds'] = str(values[stop] - values[start])
        data_counts = Counter(f"{int(row['sender'])}/{appkey(row)}" for row in segments if row['kind'] == 'DATA')
        tx_groups = defaultdict(list)
        for row in segments:
            tx_groups[int(row['tx_id'])].append(row)
        terminal_records = {}
        for row in terminals:
            key = f"{int(row['node'])}/{appkey(row)}"
            record = {'time_seconds': str(Decimal(row['time_ns']) / 1_000_000_000),
                      'success': loss.logical(row['success'], 'terminal success'), 'reason': row['reason']}
            # Release log intentionally uses app_id=0. Do not infer identity
            # linkage from a coincident callback time. Per-identity retirement
            # retention uses only bound terminal identities and ns-rounded times.
            terminal_time = Decimal(row['time_ns']) / 1_000_000_000
            if key in hop_starts:
                record['custody_retirement_seconds'] = str(terminal_time - hop_starts[key])
            if key in hop_first_tx:
                record['retirement_after_first_tx_seconds'] = str(terminal_time - hop_first_tx[key])
            terminal_records[key] = record
        delivered = {key for key, values in apps.items() if 'deliver' in values}
        failed = {key.split('/', 1)[1] for key, row in terminal_records.items() if not row['success']}
        totals = {'generated': sum('generate' in row for row in apps.values()),
                  'admitted': sum('admit' in row for row in apps.values()), 'delivered': len(delivered),
                  'terminal_records': len(terminals), 'terminal_failures': sum(not row['success'] for row in terminal_records.values()),
                  'delivered_and_failed_terminal_identities': len(delivered & failed),
                  'envelope_transmissions': len(tx_groups), 'data_segments': sum(data_counts.values()),
                  'data_retries': sum(value - 1 for value in data_counts.values()),
                  'ack_segments': sum(row['kind'] == 'ACK' for row in segments),
                  'dack_segments': sum(row['kind'] == 'DACK' for row in segments),
                  'feedback_envelopes': sum(any(row['kind'] != 'DATA' for row in group) for group in tx_groups.values()),
                  'blocked_polls': sum(row['event'] == 'blocked' for row in events),
                  'capacity_release_callbacks': sum(row['event'] == 'release' for row in events)}
        for node in loss.NODES:
            final = [row for row in events if row['event'] == 'final' and int(row['node']) == node]
            require(len(final) == 1, 'Metrics require one actual final node snapshot')
            for field in ('hop_pending','resend_queue','dack_holds','nwk_waiting','nwk_custody','nsdp4','nsdp5','ack_queue','data_queue'):
                totals[f'final_node{node}_{field}'] = int(final[0][field])
        output[case] = {'totals': totals, 'applications': identities, 'hop_retirements': terminal_records,
                        'data_attempts_by_hop_application': dict(sorted(data_counts.items())),
                        'capacity_release_series_by_node_source': dict(releases),
                        'retirement_resolution': 'integer nanoseconds; release series has no per-application ID claim',
                        'delivery_latency': _time_statistics([v['deliver'] - v['generate'] for v in apps.values() if 'deliver' in v]),
                        'admission_wait': _time_statistics([v['admit'] - v['generate'] for v in apps.values() if 'admit' in v])}
    return output


def metric_differences(left, right):
    result = {}
    for case in loss.CASES:
        l, r = left[case], right[case]
        result[case] = {'totals_right_minus_left': {key: r['totals'][key] - value for key, value in l['totals'].items()},
                        'application_identity_changes': [], 'hop_retirement_changes': [],
                        'capacity_release_series_changed': l['capacity_release_series_by_node_source'] != r['capacity_release_series_by_node_source']}
        for field, title in (('applications','application_identity_changes'), ('hop_retirements','hop_retirement_changes')):
            for key in sorted(set(l[field]) | set(r[field])):
                a, b = l[field].get(key), r[field].get(key)
                if a != b:
                    deltas = {name: str(Decimal(b[name]) - Decimal(a[name])) for name in set(a or {}) & set(b or {})
                              if name.endswith('_seconds')}
                    result[case][title].append({'identity': key, 'left': a, 'right': b, 'seconds_right_minus_left': deltas})
    return result


def verify_timing(root, metadata, source_root, candidate):
    require(metadata.get('TimingDirectory') == 'timing', 'Unexpected timing output directory')
    plan, old = verify_plan(source_root, candidate)
    directory = root / 'timing'
    combined = json_object(directory / 'summary.json')
    require(combined.get('Schema') == 'csr-tranche15-loss-timing-contract-v1'
            and combined.get('DiagnosticCompleted') is True and combined.get('Passed') is True
            and combined.get('ShapeMatchesPlan') is True
            and combined.get('NumericalParityEstablished') is False,
            'Timing experiment completion/scope claim disagrees')
    reports, modes, metrics = {}, {}, {}
    checkpoint_count, partial_count = 0, 0
    for mode in MODES:
        branch = directory / mode
        summary = json_object(branch / 'summary.json')
        require(summary.get('TimingMode') == ('continuous' if mode == 'c' else 'nanoseconds'), 'Mode summary identity mismatch')
        actual = {name: csv_rows(branch / (name + '.csv'), fields) for name, fields in (*FAMILIES, *EXTRA_FAMILIES)}
        # T13 expects a loss/ directory and counters. This adapter supplies only
        # its API shape; all claims still undergo T13 raw-data recomputation.
        old_meta = {'Runtime': metadata['Runtime'], 'RecoveryDirectory': 'loss',
                    'RecoveryCompleted': summary.get('DiagnosticCompleted'), 'RecoveryPassed': summary.get('Passed'),
                    'RecoveryMatchesNative': summary.get('MatchesNative')}
        for field in ('CaseCount','EventCount','DrawCount','CheckpointCount','UnmatchedCount'):
            old_meta['Recovery' + field] = summary.get(field)
        with tempfile.TemporaryDirectory(prefix='t15-check-') as temporary:
            adapted = Path(temporary)
            shutil.copytree(branch, adapted / 'loss')
            recovery = loss.verify_recovery(adapted, old_meta, source_root, old)
        arithmetic = validate_timing(actual['timing'], actual['transport'], actual['events'], actual['precision'], mode, label=mode)
        require(integer(summary.get('TimingCount'), 'timing count') == len(actual['timing'])
                and integer(summary.get('PrecisionCount'), 'precision count') == len(actual['precision']),
                'Branch timing/precision counts disagree')
        partial_count += verify_partial_cases(branch, actual, summary)
        require(combined.get('ContinuousSummary' if mode == 'c' else 'NanosecondsSummary') == summary,
                'Combined branch summary does not equal actual branch summary')
        checkpoint_count += recovery['checkpoint_count']
        reports[mode] = {'recovery': recovery, 'arithmetic': arithmetic}
        modes[mode], metrics[mode] = actual, outcome_metrics(actual)
    baseline = verify_original_continuous(modes['c'], source_root)
    for field, value in (('ModeCount', 2), ('CaseCount', 8), ('CheckpointCount', checkpoint_count), ('FailedCount', 0)):
        require(integer(combined.get(field), field) == value, 'Combined timing counters disagree')
    require(metadata.get('TimingCompleted') is True and metadata.get('TimingPassed') is True,
            'Timing metadata completion disagrees')
    require(integer(candidate.get('ExpectedStructuralCheckCount'), 'expected checks') == checkpoint_count == 528,
            'Declared/observed paired structural check count changed')
    require(combined.get('PlanSHA256') == candidate.get('TimingPlanSHA256')
            and combined.get('Scope') == plan.get('scope') and combined.get('Runtime') == metadata['Runtime']['Version'],
            'Combined timing plan/scope/runtime binding mismatch')
    for field, value in (('TimingModeCount',2), ('TimingCaseCount',8), ('TimingCheckpointCount',checkpoint_count), ('TimingFailedCount',0)):
        require(integer(metadata.get(field), field) == value, f'{field} metadata disagrees')
    native = {name: csv_rows(source_root / loss.REFERENCE / (name + '.csv'), fields) for name, fields in loss.FAMILIES}
    native_metrics = outcome_metrics(native)
    exact_native = {mode: [loss.compare_rows(modes[mode][name], native[name], fields, family=name, time_tolerance_ns=0)
                           for name, fields in loss.FAMILIES] for mode in MODES}
    return {'structural_complete': True, 'case_count': 8, 'checkpoint_count': checkpoint_count,
            'per_case_artifacts_verified': partial_count, 'continuous_baseline': baseline,
            'modes': reports, 'metrics': metrics, 'native_metrics': native_metrics,
            'nanoseconds_minus_continuous': metric_differences(metrics['c'], metrics['n']),
            'continuous_minus_native': metric_differences(native_metrics, metrics['c']),
            'nanoseconds_minus_native': metric_differences(native_metrics, metrics['n']),
            'exact_nanosecond_native_comparisons': exact_native,
            'interpretation': 'Totals align identities, hop attempts and real callbacks. Legacy 1 ns comparison remains separately visible; exact zero-tolerance comparisons never erase a timing difference. Native times are integer ns; owner callback metrics retain binary64 precision. No automatic improvement or full-network parity claim.'}


def review(evidence, source_root, output):
    evidence, source_root, output = Path(evidence).resolve(), Path(source_root).resolve(), Path(output).resolve()
    candidate = json_object(source_root / CANDIDATE)
    with evidence_directory(evidence) as root:
        metadata = json_object(root / 'metadata.json')
        runtime = verify_run_identity(root, metadata, source_root, candidate)
        artifacts = inventory(root, metadata.get('Artifacts'), excluded=('metadata.json',))
        required = {'run.log','source.json','references.json','tests.csv','timing/summary.json'}
        required |= {f'timing/{mode}/{name}.csv' for mode in MODES for name, _ in (*FAMILIES, *EXTRA_FAMILIES)}
        required |= {f'timing/{mode}/summary.json' for mode in MODES}
        require(required <= set(artifacts), 'Required paired timing evidence missing')
        source = verify_sources(root, metadata, source_root)
        baseline = verify_baseline(metadata, source_root, candidate)
        references = verify_references(root, metadata, source_root, candidate)
        tests = verify_tests(root, metadata, source_root, candidate)
        timing = verify_timing(root, metadata, source_root, candidate)
        result = {'schema': REVIEW_SCHEMA, 'status': 'focused_diagnostic_review_completed',
                  'evidence_integrity_verified': True, 'focused_structural_gate_completed': True,
                  'acceptance_established': False, 'numerical_parity_established': False,
                  'matlab_executed_by_reviewer': False, 'runtime': runtime,
                  'evidence': {'path': evidence.name, 'sha256': sha256(evidence), 'bytes': evidence.stat().st_size},
                  'source': source, 'baseline': baseline, 'references': references, 'tests': tests, 'timing': timing}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = review(args.evidence, args.source_root, args.output)
    except (ValueError, OSError, csv.Error, zipfile.BadZipFile, KeyError, TypeError, OverflowError) as error:
        args.output.mkdir(parents=True, exist_ok=True)
        failure = {'schema': REVIEW_SCHEMA, 'status': 'review_failed', 'evidence_integrity_verified': False,
                   'focused_structural_gate_completed': False, 'acceptance_established': False,
                   'numerical_parity_established': False, 'matlab_executed_by_reviewer': False, 'error': str(error)}
        (args.output / 'review.json').write_text(json.dumps(failure, indent=2) + '\n', encoding='utf-8')
        print(f'T15 evidence rejected: {error}')
        return 1
    print(f"T15 focused structural review complete: {result['timing']['case_count']} cases. Exact numerical and outcome differences retained.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
