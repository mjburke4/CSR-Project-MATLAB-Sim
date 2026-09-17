#!/usr/bin/env python3
"""Review T17 portable regression and the unchanged 6,000-second campus run.

Inputs are immutable owner evidence, not a request to execute MATLAB. The gate
requires complete identities, inventories, regression and finite-stop accounting.
Delivery loss, pending work and numerical residuals remain observations. Matching
seed numbers do not imply shared random streams between MATLAB and ns-3.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile

from analyze_tranche11_return import (all_files, candidate_snapshot, csv_rows,
    integer, json_object, json_value, logical, number, record_map, records, require,
    safe_path, selected_test_names, sha256, verify_sources)
import analyze_tranche7_return as t7
import analyze_research_sweep as sweep
import compare_benchmark_aggregates as aggregate
import tranche10_metrics as retained

SCHEMA = 'csr-matlab-tranche-17-validation-v1'
REVIEW_SCHEMA = 'csr-matlab-tranche-17-return-review-v1'
CANDIDATE = 'evidence/tranche-17-candidate.json'
BASELINE = 'evidence/tranche-17-baseline.json'
BASELINE_SHA = '90b5506f4fdb54f64ae7dac61c0e48df9da2253a8408a4b50b3ad30309ac1905'
OWNER_SHA = '4fbfb17ba654bee0a137f1fc2d3ac3f65a091bf936d6c44589b1db9db1f4be60'
PARENT_SHA = 'f22a893457fd7927342ed7fa176c1e227d387f6a6be3631fd0204f9a53bc1a36'
CASE_ID = 'campus_multihop_6000'
CONFIG_REFERENCE = 'evidence/tranche-7-r2025a-accepted/benchmarks/campus_multihop_6000/raw/summary.json'
CATALOG = 'scenarios/benchmarks/catalog.json'
PHASES = ('tests', 'campus')
LIMITATIONS = [
    'Hashes bind candidate inputs and owner-returned records; they are not independent proof of MATLAB execution.',
    'One seed and one unchanged campus case do not establish statistical or full-network numerical parity.',
    'Seed 128 identifies each experiment; MATLAB and ns-3 do not share random streams.',
    'Pending applications, receiver observations and HOP/NWK ownership are censored at 6,000 seconds; no forced drain is required.',
    'Admission counters cover every scheduled attempt; only the separately declared 100,000-record admission trace may be truncated.',
    'OPNET supplies archived aggregates, not packet/path/retry/PHY event truth. No PHY/ECC tuning or timing-policy promotion follows automatically.',
    'Control-drain flags cover exported HOP/NWK ownership; current MAC feedback queue depth is unavailable.'
]


@contextmanager
def evidence_directory(path):
    """T7-sized evidence with the T11 path/JSON discipline and T17 root name."""
    path = Path(path).resolve()
    if path.is_dir():
        all_files(path)
        require(all(item.is_file() or item.is_dir() for item in path.rglob('*')), 'Nonregular directory evidence member')
        yield path
        return
    require(path.is_file() and zipfile.is_zipfile(path), 'Expected evidence ZIP or directory')
    with tempfile.TemporaryDirectory(prefix='csr-t17-') as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(path) as bundle:
            require(len(bundle.infolist()) <= 20000, 'Evidence ZIP contains too many members')
            seen, size = set(), 0
            for member in bundle.infolist():
                name = member.filename.rstrip('/') if member.is_dir() else member.filename
                target = safe_path(root, name)
                require(name.casefold() not in seen, 'Duplicate/case-colliding ZIP member')
                seen.add(name.casefold())
                mode = member.external_attr >> 16
                require(not stat.S_ISLNK(mode) and not member.flag_bits & 1
                        and (not mode or stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)),
                        'Nonregular/symlink/encrypted ZIP member')
                size += member.file_size
                require(size <= 20 * 1024**3, 'Evidence ZIP expands beyond 20 GiB')
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(member) as source, target.open('xb') as destination:
                        shutil.copyfileobj(source, destination)
        require((root/'metadata.json').is_file(), 'ZIP has no root metadata.json')
        yield root


def timestamp(value, label):
    require(isinstance(value, str), label+': timestamp missing')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, label+': timezone missing')
    return result


def source_map(value, label):
    return {name: row['sha256'] for name, row in record_map(value, label).items()}


def verify_frozen_candidate(source_root, candidate):
    require(candidate.get('Schema') == 'csr-tranche-17-candidate-v1'
            and candidate.get('Tranche') == 17 and candidate.get('SourceCommit') == t7.PIN,
            'Candidate identity/source pin mismatch')
    actual = candidate_snapshot(source_root)
    require(source_map(candidate.get('SourceFiles'), 'candidate sources') ==
            {name: digest for name, digest in actual.items() if name != CANDIDATE},
            'Candidate source membership or hash mismatch')
    require(candidate.get('SourceFilesExcludedPaths') == [CANDIDATE], 'Candidate source exclusion policy changed')
    files = sorted(path.relative_to(source_root).as_posix() for path in (source_root/'tests').glob('Test*.m'))
    names = selected_test_names(source_root, files)
    require(candidate.get('TestFiles') == files and candidate.get('ExpectedTestNames') == names,
            'Candidate must select every portable MATLAB class and exact test method')
    require(set(names) == t7.portable_test_names(source_root), 'Portable test discovery differs')
    return actual


def verify_reference_membership(source_root, candidate):
    require(candidate.get('ReferenceRoots') == [], 'T17 requires explicit reference membership')
    names = candidate.get('ReferenceFiles')
    require(isinstance(names, list) and names and names == sorted(set(names)),
            'Missing/duplicate/unsorted explicit reference membership')
    bindings = record_map(candidate.get('ReferenceFileInventory'), 'candidate references', sizes=True)
    require(set(bindings) == set(names), 'Candidate reference inventory membership mismatch')
    required = {BASELINE, 'evidence/t16/owner.zip', 'evidence/t16/candidate.json', CONFIG_REFERENCE}
    for tree in ('evidence/tranche-7-ns3-reference', 'evidence/tranche-7-benchmark-inputs'):
        required.update(f'{tree}/{name}' for name in all_files(source_root/tree))
    require(required <= set(bindings), 'Required native/input/baseline reference membership missing')
    for name, row in bindings.items():
        path = safe_path(source_root, name)
        require(path.is_file() and sha256(path) == row['sha256'] and path.stat().st_size == row['bytes'],
                'Candidate reference hash or size mismatch: '+name)
    return bindings


def verify_baseline(source_root, candidate, metadata=None):
    require(candidate.get('BaselineSourceSnapshot') == BASELINE and
            candidate.get('BaseSourceSnapshotSHA256') == sha256(source_root/BASELINE) == BASELINE_SHA,
            'T16 baseline snapshot identity mismatch')
    baseline = record_map(json_value(source_root/BASELINE), 'T16 source baseline')
    require(len(baseline) == 304 and sum(name.endswith('.m') for name in baseline) == 155,
            'T16 baseline source membership mismatch')
    for name, row in baseline.items():
        require(sha256(safe_path(source_root, name)) == row['sha256'],
                'Previously validated T16 source changed: '+name)
    for key, name, digest in (('BaselineOwnerEvidence', 'evidence/t16/owner.zip', OWNER_SHA),
                              ('BaselineCandidate', 'evidence/t16/candidate.json', PARENT_SHA)):
        require(candidate.get(key) == name and candidate.get(key+'SHA256') == sha256(source_root/name) == digest,
                'T16 owner/candidate provenance mismatch')
    with evidence_directory(source_root/'evidence/t16/owner.zip') as owner:
        parent = json_object(owner/'metadata.json')
        t7.inventory(owner, parent.get('Artifacts'), 'T16 owner artifacts', excluded=('metadata.json',),
                     local=parent.get('LocalArtifacts', []))
        require(parent.get('Status') == 'completed' and parent.get('TestsPassed') is True
                and parent.get('CandidateSHA256') == PARENT_SHA
                and parent.get('SourceSnapshotSHA256') == sha256(owner/'source.json') == BASELINE_SHA,
                'Baseline is not bound to completed T16 owner evidence')
    if metadata is not None:
        require(integer(metadata.get('BaselineSourceFilesVerified'), 'baseline sources') == 304
                and integer(metadata.get('BaselineMatlabFilesVerified'), 'baseline MATLAB') == 155
                and metadata.get('AllBaselineSourcesUnchanged') is True, 'Baseline verification claims disagree')
    return {'source_files': 304, 'matlab_files': 155, 'all_unchanged': True, 'sha256': BASELINE_SHA}


def verify_plan(source_root, candidate):
    require(candidate.get('Plan') == 'scenarios/t17/plan.json'
            and candidate.get('PlanSHA256') == sha256(source_root/candidate['Plan']), 'Plan identity/hash mismatch')
    plan = json_object(source_root/candidate['Plan'])
    expected = {'schema': 'csr-tranche17-campus-release-plan-v1', 'tranche': 17,
        'case_id': CASE_ID, 'storage_key': 'c', 'ns3_source_commit': t7.PIN, 'duration_s': 6000,
        'seed': 128, 'timing_policy': 'continuous', 'full_portable_regression': True,
        'bucket_width_s': 60, 'flow_limit': 0, 'opnet_available': True,
        'protocol_trace_max_records': 1500000, 'phy_trace_max_records': 1500000,
        'admission_trace_max_records': 100000, 'max_events': 12000000,
        'application_admission_counts_complete_required': True,
        'admission_trace_omissions_permitted_and_reported': True,
        'native_reference_reused': True}
    expected.update(dict.fromkeys(('observer_enabled', 'stimuli_changed', 'phy_ecc_changed',
        'default_policy_changed', 'post_horizon_drain', 'native_tests_included',
        'protocol_and_phy_omissions_permitted', 'native_execution_required', 'numerical_parity_required'), False))
    require(all(plan.get(name) == value for name, value in expected.items()), 'Campus release plan scope/configuration mismatch')
    catalog = json_object(source_root/CATALOG)
    require(catalog.get('schema') == 'csr-benchmark-catalog-v1' and catalog.get('ns3_source_commit') == t7.PIN
            and plan.get('catalog_sha256') == sha256(source_root/CATALOG), 'Catalog identity/hash mismatch')
    cases = records(catalog.get('cases'), 'catalog cases')
    require(len({row['case_id'] for row in cases}) == len(cases), 'Duplicate catalog case')
    selected = [row for row in cases if row['case_id'] == CASE_ID]
    require(len(selected) == 1, 'Campus catalog case missing or duplicated')
    case = selected[0]
    for field in ('case_id', 'scenario', 'scenario_file', 'scenario_sha256', 'profile_id', 'duration_s',
                  'seed', 'bucket_width_s', 'reference_directory', 'source_kind', 'opnet_available', 'flow_limit'):
        require(plan.get(field) == case[field], 'Plan differs from original campus catalog: '+field)
    require(sha256(source_root/case['scenario_file']) == case['scenario_sha256'], 'Original campus input hash mismatch')
    t7.verify_reference_suite(source_root, catalog)
    return plan, case


def verify_preparation(source_root):
    source_root = Path(source_root).resolve()
    candidate = json_object(source_root/CANDIDATE)
    source = verify_frozen_candidate(source_root, candidate)
    references = verify_reference_membership(source_root, candidate)
    baseline = verify_baseline(source_root, candidate)
    plan, case = verify_plan(source_root, candidate)
    return {'source': source, 'references': references, 'baseline': baseline, 'plan': plan, 'case': case}


def verify_identity(root, metadata, source_root, candidate):
    require(metadata.get('Schema') == SCHEMA and metadata.get('Tranche') == 17
            and metadata.get('Status') == 'completed-review-required', 'Return is not a finalized complete T17 run')
    require(metadata.get('CandidateFile') == CANDIDATE
            and metadata.get('CandidateSHA256') == sha256(source_root/CANDIDATE)
            and sha256(root/'candidate.json') == sha256(source_root/CANDIDATE), 'Returned candidate hash mismatch')
    require(metadata.get('MATLABExecuted') is True and metadata.get('NativeExecuted') is False
            and metadata.get('SourceCommit') == t7.PIN, 'MATLAB/native execution identity mismatch')
    runtime = metadata.get('Runtime')
    require(isinstance(runtime, dict) and runtime.get('Runtime') == 'MATLAB'
            and runtime.get('DefaultBackend') == 'portable'
            and all(isinstance(runtime.get(key), str) and runtime[key] for key in ('Version', 'Release')),
            'Missing portable MATLAB runtime/release')
    require(timestamp(metadata.get('CompletedUTC'), 'completion') >= timestamp(metadata.get('StartedUTC'), 'start'),
            'Owner completion precedes start')
    require(metadata.get('FullAcceptanceGateExecuted') is True
            and metadata.get('AcceptanceEstablished') is False and metadata.get('NumericalParityEstablished') is False,
            'Missing full regression/campus execution or unsupported numerical-acceptance claim')
    require(metadata.get('EvidenceArchive') == 't17.zip', 'Return archive identity mismatch')
    require(sha256(root/'plan.json') == candidate['PlanSHA256'], 'Returned plan differs from candidate')
    return runtime


def verify_references(root, metadata, expected):
    before = record_map(json_value(root/'references.json'), 'returned references', sizes=True)
    after = record_map(metadata.get('ReferenceFilesFinal'), 'final references', sizes=True)
    require(before == expected == after, 'Returned reference membership/hash changed')
    require(metadata.get('ReferenceFilesStableDuringRun') is True
            and metadata.get('ReferenceSnapshotSHA256') == sha256(root/'references.json'),
            'Reference snapshot hash or stability missing')
    return {'count': len(before), 'sha256': sha256(root/'references.json')}


def verify_stage(root, phase, entry, metadata, source, references, runtime):
    require(entry.get('Phase') == phase and entry.get('File') == f'{phase}/receipt.json',
            'Stage receipt path or phase mismatch')
    directory = root/phase
    path = directory/'receipt.json'
    digest = sha256(path)
    require(entry.get('SHA256') == digest and (directory/'receipt.sha256').read_text().strip() == digest,
            'Stage receipt hash mismatch')
    receipt = json_object(path)
    require(receipt.get('schema') == 'csr-tranche17-stage-receipt-v1'
            and receipt.get('phase') == phase and receipt.get('status') == 'completed',
            'Stage receipt incomplete or wrong phase')
    require(timestamp(receipt.get('completed_utc'), 'stage completion') <= timestamp(metadata['CompletedUTC'], 'finalize'),
            'Stage completion after finalize')
    identity = receipt.get('identity', {})
    require(isinstance(identity, dict), 'Stage identity must be a JSON object')
    require(identity.get('CandidateSHA256') == metadata['CandidateSHA256']
            and identity.get('SourceCommit') == t7.PIN and identity.get('Runtime') == runtime,
            'Stage candidate/source/runtime identity mismatch')
    require(source_map(identity.get('SourceFiles'), 'stage sources') == source
            and record_map(identity.get('ReferenceFiles'), 'stage references', sizes=True) == references,
            'Stage source/reference snapshot differs from final candidate')
    require(receipt.get('SourceFilesStableDuringRun') is True and receipt.get('ReferenceFilesStableDuringRun') is True
            and source_map(receipt.get('SourceFilesFinal'), 'stage final sources') == source
            and record_map(receipt.get('ReferenceFilesFinal'), 'stage final references', sizes=True) == references,
            'Stage source/reference stability unproven')
    started = json_object(directory/'start.json')
    require(started.get('schema') == 'csr-tranche17-stage-start-v1' and started.get('phase') == phase
            and started.get('status') == 'started' and started.get('identity') == identity,
            'Stage start identity or status differs from completed receipt')
    require(timestamp(started.get('started_utc'), 'stage start') <= timestamp(receipt['completed_utc'], 'stage completion'),
            'Stage completion precedes its start')
    t7.inventory(directory, receipt.get('artifacts'), phase+' artifacts',
                 excluded=('receipt.json', 'receipt.sha256'), local=receipt.get('local_artifacts', []))
    summary = json_object(directory/'summary.json')
    require(receipt.get('summary') == summary, 'Stage receipt summary hash-bound content mismatch')
    return summary


def verify_tests(root, metadata, source_root, candidate, summary):
    files, names = candidate['TestFiles'], candidate['ExpectedTestNames']
    require(summary.get('Schema') == 'csr-tranche17-portable-tests-summary-v1'
            and summary.get('TestResultsFile') == 'results.csv' and summary.get('TestFiles') == files
            and summary.get('ExpectedTestNames') == names, 'Portable tests summary selection mismatch')
    require(names == selected_test_names(source_root, files), 'Test source methods changed')
    rows = csv_rows(root/'tests/results.csv', ('Name', 'Passed', 'Failed', 'Incomplete', 'DurationSeconds'))
    require(len(rows) == len(names) and {row['Name'] for row in rows} == set(names),
            'Missing or duplicate portable MATLAB test identity')
    for row in rows:
        require(logical(row['Passed'], 'Passed') and not logical(row['Failed'], 'Failed')
                and not logical(row['Incomplete'], 'Incomplete'), 'MATLAB test failed or incomplete')
        number(row['DurationSeconds'], 'test duration', minimum=0)
    for reported in (summary, metadata):
        require(reported.get('TestsExecuted') is True and reported.get('TestsPassed') is True
                and all(integer(reported.get(key), key) == count for key, count in
                        (('TestCount', len(names)), ('PassedTests', len(names)), ('FailedTests', 0), ('IncompleteTests', 0))),
                'MATLAB test counters disagree with exact results')
    return {'status': 'passed', 'count': len(names), 'classes': len(files), 'names': names,
            'scope': 'All top-level portable Test*.m classes; native adapter tests excluded.'}


def verify_node_metrics(directory, config, performance):
    """Reject duplicate/missing ownership rows; finite-stop queues may be nonzero."""
    nodes = {integer(row['Id'], 'node') for row in records(config['Nodes'], 'nodes')}
    mappings = {
        'nodes.csv': {'Generated': 'Generated', 'Received': 'Received', 'Dropped': 'Dropped'},
        'hop_nodes.csv': {'PendingData': 'HopPendingData', 'ResendQueueDepth': 'ResendQueueDepth',
            'DackHoldCount': 'DackHoldCount', 'ControlPending': 'ControlPending',
            'ControlPendingTargets': 'ControlPendingTargets', 'Retransmissions': 'HopDataRetransmissions',
            'ControlRetransmissions': 'HopControlRetransmissions'},
        'nwk_nodes.csv': {'PendingCustody': 'NwkPendingCustody', 'PendingControlMessages': 'NwkPendingControlMessages'},
        'mac_nodes.csv': {'Transmissions': 'PhysicalTransmissions', 'SegmentsTransmitted': 'MacMemberTransmissions',
            'AckTransmissions': 'AckFeedbackMemberTransmissions'}}
    totals = {}
    for filename, mapping in mappings.items():
        key = 'Id' if filename == 'nodes.csv' else 'NodeId'
        rows = list(t7.csv_records(directory/'raw'/filename, (key, *mapping)))
        require(len(rows) == len(nodes) and {integer(row[key], 'node') for row in rows} == nodes,
                'Missing/duplicate per-node ownership identity: '+filename)
        totals[filename] = {}
        for field, metric in mapping.items():
            count = sum(integer(row[field], field) for row in rows)
            require(integer(performance[metric], metric) == count, 'Per-node ownership/counter mismatch: '+metric)
            totals[filename][field] = count
        if filename == 'nwk_nodes.csv':
            require(all(integer(row['PendingCustody'], 'custody') <= config['Nwk']['QueueLimit'] for row in rows),
                    'NWK custody queue bound exceeded')
        if filename == 'mac_nodes.csv':
            require(all(integer(row['MaxDataQueueDepth'], 'MAC max queue') <= config['Mac']['DataQueueLimit'] for row in rows),
                    'MAC data queue bound exceeded')
    return totals


def verify_phy(directory, config, stats, performance):
    """Join physical receiver outcomes to actual OTA frames without timing injection."""
    horizon = config['DurationSeconds']
    nodes = {integer(row['Id'], 'node') for row in records(config['Nodes'], 'nodes')}
    tx, protocol_count = {}, 0
    for row in t7.csv_records(directory/'raw/protocol_trace.csv', ('TimeSeconds', 'Event', 'NodeId', 'PacketId')):
        protocol_count += 1
        if row['Event'] != 'tx_start':
            continue
        frame = integer(row['PacketId'], 'TX frame', 1)
        require(frame not in tx, 'Duplicate OTA frame identity')
        tx[frame] = integer(row['NodeId'], 'TX source'), float(number(row['TimeSeconds'], 'TX time', minimum=0))
        require(tx[frame][0] in nodes and tx[frame][1] < horizon, 'OTA source/horizon mismatch')
    require(len(tx) == integer(stats['PhysicalTransmissions'], 'TX count') > 0
            and integer(stats['PhysicalAttempts'], 'receiver attempts') == len(tx)*(len(nodes)-1),
            'Physical TX/receiver target accounting mismatch')
    starts, ends, previous, count = set(), {}, -1.0, 0
    for row in t7.csv_records(directory/'raw/phy_trace.csv', ('TimeSeconds', 'Event', 'PacketId', 'NodeId', 'SourceId', 'Success', 'Reason')):
        count += 1
        frame, receiver = integer(row['PacketId'], 'PHY frame'), integer(row['NodeId'], 'receiver')
        require(frame in tx and receiver in nodes and receiver != tx[frame][0]
                and integer(row['SourceId'], 'PHY source') == tx[frame][0], 'PHY receiver/frame identity mismatch')
        when = float(number(row['TimeSeconds'], 'PHY time', minimum=0))
        require(previous <= when <= horizon and when+1e-9 >= tx[frame][1], 'PHY callback order/horizon mismatch')
        previous = when
        key = frame, receiver
        require(row['Event'] != 'post_phy_drop', 'Unexpected post-PHY fault injection')
        if row['Event'] == 'phy_signal_start':
            require(key not in starts and key not in ends, 'Duplicate/out-of-order PHY start')
            starts.add(key)
        elif row['Event'] == 'phy_signal_end':
            require(key not in ends, 'Duplicate PHY completion')
            require((key in starts) == (row['Reason'] != 'closure'), 'PHY start/closure coverage mismatch')
            ends[key] = logical(row['Success'], 'PHY success')
    received = sum(ends.values())
    require(received == integer(stats['PhysicalReceived'], 'physical received')
            and len(ends)-received == integer(stats['PhysicalDropped'], 'physical dropped')
            and integer(stats['PhysicalAttempts'], 'attempts')-len(ends) == integer(stats['PhysicalPending'], 'physical pending'),
            'PHY completion outcomes disagree with counters')
    require(integer(performance['ProtocolTraceRecords'], 'protocol records') == protocol_count
            and integer(performance['PhyTraceRecords'], 'PHY records') == count, 'Trace record totals disagree')
    return {'ota_transmissions': len(tx), 'receiver_completions': len(ends), 'protocol_records': protocol_count,
            'phy_records': count, 'pending_receivers': integer(stats['PhysicalPending'], 'physical pending')}


def verify_campus(root, metadata, source_root, case, source, runtime, summary):
    require(summary.get('Schema') == 'csr-tranche17-campus-release-summary-v1'
            and summary.get('CaseId') == CASE_ID and summary.get('StorageKey') == 'c'
            and summary.get('CompletedCaseCount') == 1 and summary.get('DurationSeconds') == 6000
            and summary.get('SchedulerStopSeconds') == 6000
            and summary.get('Seed') == 128 and summary.get('PostHorizonDrain') is False
            and all(summary.get(key) is False for key in ('AcceptanceEstablished', 'NumericalParityEstablished', 'FiniteStopPendingIsFailure'))
            and integer(summary.get('ProtocolTraceOmissions'), 'protocol omissions') == 0
            and integer(summary.get('PhyTraceOmissions'), 'PHY omissions') == 0
            and all(summary.get(key) is True for key in ('StructuralChecksPassed', 'DefaultContinuousTiming', 'RealPHY', 'AutonomousRouting')),
            'Campus stage identity/configuration/completion mismatch')
    entries = records(metadata.get('Cases'), 'completed campus cases')
    require(len(entries) == 1 and entries[0].get('CaseId') == CASE_ID
            and metadata.get('CompletedCaseCount') == 1 and metadata.get('CampusCompleted') is True
            and metadata.get('CampusStructuralChecksPassed') is True, 'Missing/duplicate/uncompleted campus case')
    require(summary.get('Case') == entries[0], 'Campus summary case binding differs from metadata')
    directory = root/'campus/c'
    observed = t7.verify_case(root, entries[0], case, source, runtime, sha256(root/'source.json'),
                              expected_directory='campus/c')
    raw = json_object(directory/'raw/summary.json')
    config, stats, md = raw['Config'], raw['Statistics'], raw['Metadata']
    baseline = json_object(source_root/CONFIG_REFERENCE)
    observed['configuration'] = retained.same_configuration(baseline['Config'], config, source_root, case)
    require(md.get('ChannelModel') == 'csr-phy' and md.get('Backend') == 'portable'
            and md.get('ModelStage') == 'tranche-3-autonomous-network-routing'
            and md.get('Runtime') == 'MATLAB' and md.get('Version') == runtime['Version'] and md.get('Release') == runtime['Release']
            and not any(key in raw for key in ('TransportTiming', 'ServiceDiagnostics', 'LinkDiagnostics')),
            'Controlled, instrumented or different-runtime execution supplied as unchanged campus')
    require(sha256(directory/'raw/trace.csv') == sha256(directory/'raw/protocol_trace.csv'), 'Protocol trace copies disagree')
    needed = {'trace.csv', 'protocol_trace.csv', 'phy_trace.csv', 'summary.json', 'scenario.csv', 'case_manifest.json',
              'nodes.csv', 'mac_nodes.csv', 'hop_nodes.csv', 'nwk_nodes.csv', 'neighbors.csv', 'routes.csv',
              'application_admission_statistics.csv', 'application_admission_trace.csv'}
    require(needed <= all_files(directory/'raw'), 'Required campus exports missing')
    performance = csv_rows(directory/'analysis/performance_summary.csv')
    require(len(performance) == 1, 'Missing/duplicate performance summary')
    verify_campus_summary(summary, performance[0], observed['admission'])
    benchmark_rows = list(t7.csv_records(root/'campus/benchmark_summary.csv', ('CaseId', *t7.COUNTS, 'Attempts', 'AdmissionBlocked')))
    require(len(benchmark_rows) == 1 and benchmark_rows[0]['CaseId'] == CASE_ID
            and t7.count_balance(benchmark_rows[0], 'campus stage') == observed['counts']
            and integer(benchmark_rows[0]['Attempts'], 'attempts') == observed['admission']['attempts']
            and integer(benchmark_rows[0]['AdmissionBlocked'], 'blocked') == observed['admission']['blocked'],
            'Campus benchmark summary counters or membership disagree')
    observed['node_counter_totals'] = verify_node_metrics(directory, config, performance[0])
    observed['physical_trace'] = verify_phy(directory, config, stats, performance[0])
    require(observed['admission']['trace_records'] == min(100000, observed['admission']['attempts']),
            'Admission trace omitted records before its declared capacity')
    observed['ns3_flows'] = t7.reference_flow_progress(source_root/case['reference_directory'])
    observed['horizon_seconds'] = 6000
    observed['seed'] = 128
    observed['default_continuous_timing'] = True
    observed['performance'] = performance[0]
    return observed


def verify_campus_summary(summary, performance, admission):
    rendered = summary.get('Performance')
    require(isinstance(rendered, dict) and set(rendered) == set(performance), 'Campus Performance summary fields disagree')
    for name, expected in rendered.items():
        actual = performance[name]
        if expected is None:
            require(actual.lower() in ('', 'nan'), 'Campus summary missing-value disagreement: '+name)
        elif isinstance(expected, bool):
            require(logical(actual, name) == expected, 'Campus summary Boolean disagreement: '+name)
        elif isinstance(expected, (int, float)):
            require(math.isclose(float(number(actual, name)), expected, rel_tol=5e-13, abs_tol=1e-12),
                    'Campus summary numeric disagreement: '+name)
        else:
            require(actual == expected, 'Campus summary text disagreement: '+name)
    expected_admission = {'Attempts': admission['attempts'], 'Admitted': admission['admitted'],
        'Blocked': admission['blocked'], 'TraceRecords': admission['trace_records'],
        'OmittedTraceRecords': admission['omitted_trace_records'], 'CountsComplete': True}
    require(summary.get('Admissions') == expected_admission, 'Campus summary admission counters disagree')


def output_location(evidence, source_root, output):
    requested_output = Path(output)
    require(not requested_output.is_symlink(), 'Review output cannot be a symlink')
    evidence, source_root, output = (Path(value).resolve() for value in (evidence, source_root, output))
    require(not output.is_relative_to(evidence), 'Review output would modify input evidence')
    require(not output.is_relative_to(source_root) or output.is_relative_to(source_root/'results'),
            'Review output must be outside source inputs (or under results/)')
    require(not output.exists() or output.is_dir() and not any(output.iterdir()),
            'Choose a fresh or empty review output directory')
    return evidence, source_root, output


def review(evidence, source_root, output):
    evidence, source_root, output = output_location(evidence, source_root, output)
    prepared = verify_preparation(source_root)
    candidate = json_object(source_root/CANDIDATE)
    with evidence_directory(evidence) as root:
        require(evidence.is_dir() or not (root/'t17.zip').exists(), 'Unexpected nested return archive')
        metadata = json_object(root/'metadata.json')
        runtime = verify_identity(root, metadata, source_root, candidate)
        t7.inventory(root, metadata.get('Artifacts'), 'T17 outer artifacts', excluded=('metadata.json', 't17.zip'),
                     local=metadata.get('LocalArtifacts', []))
        source = verify_sources(root, metadata, source_root)
        references = verify_references(root, metadata, prepared['references'])
        baseline = verify_baseline(source_root, candidate, metadata)
        stage_entries = records(metadata.get('StageReceipts'), 'stage receipts')
        require(len(stage_entries) == 2 and {entry.get('Phase') for entry in stage_entries} == set(PHASES),
                'Missing/duplicate stage receipts')
        summaries = {entry['Phase']: verify_stage(root, entry['Phase'], entry, metadata, prepared['source'], prepared['references'], runtime)
                     for entry in stage_entries}
        tests = verify_tests(root, metadata, source_root, candidate, summaries['tests'])
        campus = verify_campus(root, metadata, source_root, prepared['case'], prepared['source'], runtime, summaries['campus'])
        comparisons = aggregate.compare_case(root/'campus/c', source_root/prepared['case']['reference_directory'], output/'aggregates')
        require(set(comparisons['inputs']) == {'matlab', 'ns3', 'opnet'} and comparisons['duration_s'] == 6000
                and comparisons['bucket_width_s'] == 60 and comparisons['bucket_count'] == 100,
                'Campus aggregate comparison omitted a source or changed its grid')
        result = {'schema': REVIEW_SCHEMA, 'status': 'structural_review_completed', 'evidence_integrity_verified': True,
            'full_structural_gate_completed': True, 'acceptance_established': False, 'numerical_parity_established': False,
            'matlab_executed_by_reviewer': False, 'runtime': runtime, 'source': source, 'baseline': baseline,
            'references': references, 'tests': tests, 'campus': campus, 'aggregate_comparison': comparisons,
            'metadata_sha256': sha256(root/'metadata.json'), 'limitations': LIMITATIONS}
    output.mkdir(parents=True, exist_ok=True)
    (output/'review.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        output_location(args.evidence, args.source_root, args.output)
    except ValueError as error:
        print('T17 review output rejected without modifying inputs: '+str(error))
        return 1
    try:
        result = review(args.evidence, args.source_root, args.output)
    except (ValueError, OSError, csv.Error, zipfile.BadZipFile, KeyError, TypeError, AttributeError, OverflowError, StopIteration) as error:
        # Even partial, interrupted or corrupt returns yield an explicit failed
        # review, never an inferred acceptance based on the surviving files.
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output/'review.json').write_text(json.dumps({'schema': REVIEW_SCHEMA, 'status': 'review_failed',
            'evidence_integrity_verified': False, 'full_structural_gate_completed': False,
            'acceptance_established': False, 'numerical_parity_established': False,
            'matlab_executed_by_reviewer': False, 'error': str(error)}, indent=2)+'\n', encoding='utf-8')
        print('T17 evidence rejected: '+str(error))
        return 1
    print(f"T17 structural review complete: {result['tests']['count']} portable tests and one unchanged 6,000-second campus case; numerical differences require review.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
