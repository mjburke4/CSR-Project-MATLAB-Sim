#!/usr/bin/env python3
"""Independent read-only audit of the owner T23 return and frozen issued update.

Uses the standard library only. No original tranche checker is imported.
Run: python audit.py --workspace /path/to/workspace --source-root /restored/csr23
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

ISSUED_SHA = '933fe4b6d09253786e38fbb43091ea62702bb01264ef9147a029cea45b71db64'
CANDIDATE_SHA = 'b40afd3755ceb47576ea2c9854b4af15a14cebcf87024331e67bf53e069f0818'
BASELINE_SHA = 'c5ca0672545bb213bd262d3d02f1008fd99d6c64e5355b8248ac102257477fd2'
SOURCE_PIN = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
ENGINE_PIN = '6b5cd24ea80713ce16d88575869aedd6f432bdae'
CANDIDATE_PATH = 'evidence/tranche-23-candidate.json'
TOLERANCE = Decimal('1e-9')


def require(value, message):
    if not value:
        raise AssertionError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def decode(data):
    return json.loads(data, object_pairs_hook=no_duplicate_keys)


def safe_name(name):
    p = PurePosixPath(name)
    require(name and '\\' not in name and ':' not in name and not p.is_absolute()
            and str(p) == name and all(part not in ('.', '..', '') for part in name.split('/')),
            'Noncanonical archive or inventory path: ' + name)
    return name


def read_zip(path):
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        require(len(entries) <= 10000, 'Archive entry limit')
        require(sum(e.file_size for e in entries) < 1024**3, 'Archive expanded size limit')
        names = [safe_name(e.filename) for e in entries if not e.is_dir()]
        require(len(names) == len(set(n.casefold() for n in names)), 'Duplicate/case-colliding ZIP paths')
        for e in entries:
            if e.is_dir():
                safe_name(e.filename.rstrip('/'))
            require(not stat.S_ISLNK(e.external_attr >> 16), 'ZIP symlink: ' + e.filename)
            require(not e.flag_bits & 1, 'Encrypted ZIP entry: ' + e.filename)
        result = {e.filename: archive.read(e) for e in entries if not e.is_dir()}
        require(all(len(result[e.filename]) == e.file_size for e in entries if not e.is_dir()),
                'ZIP size mismatch')
        return result


def records(rows):
    result = {}
    for row in rows:
        name = safe_name(row['path'])
        require(name not in result, 'Duplicate inventory path: ' + name)
        require(re.fullmatch('[a-f0-9]{64}', row['sha256']), 'Invalid SHA256: ' + name)
        result[name] = row
    return result


def csv_data(data, columns=None):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''))
    require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), 'CSV schema')
    if columns is not None:
        require(reader.fieldnames == columns, 'CSV columns differ from frozen schema')
    rows = list(reader)
    require(all(None not in row and all(value is not None for value in row.values()) for row in rows),
            'Malformed CSV row')
    return rows


def int_value(value):
    v = Decimal(value)
    require(v.is_finite() and v == int(v), 'Invalid integer: ' + str(value))
    return int(v)


def compare(actual, native):
    require(len(actual) == len(native), 'This owner return has unexpected comparison membership')
    differences = []
    maximum_time_delta = Decimal(0)
    for i, (a, b) in enumerate(zip(actual, native), 1):
        require(list(a) == list(b), 'Comparison schema mismatch')
        fields = []
        for key in a:
            if key == 'time_s':
                delta = abs(Decimal(a[key]) - Decimal(b[key]))
                maximum_time_delta = max(maximum_time_delta, delta)
                same = delta <= TOLERANCE
            else:
                same = a[key] == b[key]
            if not same:
                fields.append(key)
        if fields:
            differences.append({'row': i, 'case_id': a['case_id'], 'step': int(a['step']),
                                'fields': fields, 'matlab': {k: a[k] for k in fields},
                                'native': {k: b[k] for k in fields}})
    return {'actual_rows': len(actual), 'reference_rows': len(native),
            'matched_rows': len(actual) - len(differences), 'unmatched_rows': len(differences),
            'failed_rows': [d['row'] for d in differences], 'differences': differences,
            'maximum_time_difference_seconds': str(maximum_time_delta)}


def verify_receipt(receipt, comparison):
    require(receipt['ReferencePresent'] is True and receipt['SchemaMatches'] is True,
            'Comparison presence/schema receipt mismatch')
    for a, b in [('ActualRows', 'actual_rows'), ('ReferenceRows', 'reference_rows'),
                 ('MatchedRows', 'matched_rows'), ('UnmatchedRows', 'unmatched_rows'),
                 ('FailedRows', 'failed_rows')]:
        require(receipt[a] == comparison[b], 'Comparison receipt mismatch: ' + a)


def audit(workspace, source_root):
    issued_path = workspace/'t23-review-recovery/NS3 to MATLAB Network Simulation/t23up.zip'
    owner_path = workspace/'upload/t23.zip'
    issued = read_zip(issued_path)
    owner = read_zip(owner_path)
    require(digest(issued_path.read_bytes()) == ISSUED_SHA, 'Frozen issued ZIP SHA mismatch')
    require(digest(issued[CANDIDATE_PATH]) == CANDIDATE_SHA, 'Frozen candidate SHA mismatch')
    require(owner['candidate.json'] == issued[CANDIDATE_PATH], 'Owner candidate differs from issued candidate')
    c = decode(issued[CANDIDATE_PATH])
    m = decode(owner['metadata.json'])
    summary = decode(owner['contract/summary.json'])
    require(c['SourceCommit'] == SOURCE_PIN and c['EngineCommit'] == ENGINE_PIN, 'Pinned source mismatch')
    require(c['SourceFilesExcludedPaths'] == [CANDIDATE_PATH], 'Unexpected candidate exclusion')
    require(m['Schema'] == 'csr-matlab-tranche-23-validation-v1' and m['Tranche'] == 23,
            'Owner tranche identity mismatch')
    require(m['InventoryExcludedPaths'] == ['metadata.json', 't23.zip'], 'Unexpected inventory exclusion')
    artifact_map = records(m['Artifacts'])
    require(set(owner) == set(artifact_map) | {'metadata.json'}, 'Owner inventory is not closed')
    for name, row in artifact_map.items():
        require(digest(owner[name]) == row['sha256'] and len(owner[name]) == row['bytes'],
                'Owner artifact hash or size mismatch: ' + name)
    require(m['CandidateSHA256'] == CANDIDATE_SHA and m['CandidateFile'] == CANDIDATE_PATH,
            'Metadata candidate binding mismatch')
    for snapshot, field in [('source.json', 'SourceSnapshotSHA256'), ('references.json', 'ReferenceSnapshotSHA256')]:
        require(digest(owner[snapshot]) == m[field], 'Snapshot SHA mismatch: ' + snapshot)
    expected_sources = records(c['SourceFiles'])
    expected_sources[CANDIDATE_PATH] = {'path': CANDIDATE_PATH, 'sha256': CANDIDATE_SHA}
    source_map = records(decode(owner['source.json']))
    require(source_map == expected_sources and records(m['SourceFilesFinal']) == source_map,
            'Owner initial/final source snapshot does not match trusted candidate')
    ref_map = records(decode(owner['references.json']))
    expected_refs = records(c['ReferenceFileInventory'])
    require(ref_map == expected_refs and records(m['ReferenceFilesFinal']) == ref_map,
            'Owner initial/final reference snapshot does not match trusted candidate')
    require(c['ReferenceFiles'] == sorted(ref_map) and c['ReferenceRoots'] == [], 'Reference membership mismatch')
    require(m['SourceFilesStableDuringRun'] is True and m['ReferenceFilesStableDuringRun'] is True,
            'Stable-run flags disagree')
    baseline_bytes = issued[c['BaselineSourceSnapshot']]
    require(digest(baseline_bytes) == BASELINE_SHA == c['BaseSourceSnapshotSHA256'], 'T22 baseline identity')
    baseline = records(decode(baseline_bytes))
    require(len(baseline) == 390 and sum(p.endswith('.m') for p in baseline) == 178,
            'T22 baseline membership')
    require(all(expected_sources.get(p) == row for p, row in baseline.items()), 'Changed T22 source')
    require(c['AllowedModifiedSourceFiles'] == [] and c['AllBaselineSourcesUnchanged'] is True,
            'Baseline preservation candidate claims')
    require(m['AllBaselineSourcesUnchanged'] is True and m['BaselineSourceFilesVerified'] == 390
            and m['BaselineMatlabFilesVerified'] == 178, 'Baseline preservation metadata claims')
    for field in ['BaselineCandidate', 'BaselineAcceptance']:
        require(digest(issued[c[field]]) == c[field+'SHA256'], 'Baseline binding: ' + field)
    require(digest(issued['evidence/t22/accepted/owner.zip']) == c['BaselineOwnerEvidenceSHA256'],
            'T22 accepted original return binding')
    byte_checks = {}
    for label, mapping in [('source', expected_sources), ('reference', expected_refs)]:
        checked, unavailable = [], []
        for name, row in mapping.items():
            path = source_root/name
            data = path.read_bytes() if path.is_file() else issued.get(name)
            if data is None:
                unavailable.append(name)
                continue
            require(digest(data) == row['sha256'], 'Trusted original byte SHA mismatch: ' + name)
            if 'bytes' in row:
                require(len(data) == row['bytes'], 'Trusted original byte size mismatch: ' + name)
            checked.append(name)
        byte_checks[label] = {'verified': len(checked), 'missing_count': len(unavailable),
                             'unavailable_paths': unavailable}
    require(owner['plan.json'] == issued[c['Plan']] and digest(owner['plan.json']) == c['PlanSHA256'],
            'Frozen plan binding')
    plan = decode(owner['plan.json'])
    contract = decode(issued['scenarios/t23/contract.json'])
    require(plan['comparison']['time_absolute_tolerance_seconds'] == '1e-9'
            and plan['comparison']['campus_percent_target_applies'] is False, 'Tolerance changed')
    for name, field in [('actions.csv', 'ActionsSHA256'), ('cases.csv', 'CasesSHA256')]:
        require(owner['contract/'+name] == issued['scenarios/t23/'+name], 'Controlled inputs changed: ' + name)
        require(digest(owner['contract/'+name]) == summary[field], 'Input summary SHA mismatch: ' + name)
    for name, key, field in [('checkpoints.csv', 'NativeReference', 'NativeReferenceSHA256'),
                             ('feedback.csv', 'NativeFeedbackReference', 'NativeFeedbackReferenceSHA256')]:
        require(digest(issued[c[key]]) == c[field] == summary[field], 'Native binding mismatch: ' + name)
    tests = csv_data(owner['tests.csv'], ['Name', 'Passed', 'Failed', 'Incomplete', 'DurationSeconds'])
    require(len(tests) == 79 and [t['Name'] for t in tests] == c['ExpectedTestNames']
            and len(set(c['ExpectedTestNames'])) == 79, 'Test membership/order mismatch')
    require(m['ExpectedTestNames'] == c['ExpectedTestNames'] and m['TestFiles'] == c['TestFiles'],
            'Metadata test names/files mismatch')
    for t in tests:
        require(t['Passed'] == '1' and t['Failed'] == '0' and t['Incomplete'] == '0', 'Test failure: '+t['Name'])
        require(Decimal(t['DurationSeconds']).is_finite() and Decimal(t['DurationSeconds']) >= 0,
                'Invalid test duration')
    require(m['TestsExecuted'] is True and m['TestsPassed'] is True and m['TestCount'] == m['PassedTests'] == 79
            and m['FailedTests'] == m['IncompleteTests'] == 0, 'Metadata tests disagreement')
    test_sources_verified, missing_test_files = [], []
    derived_names = []
    for name in c['TestFiles']:
        path = source_root/name
        data = path.read_bytes() if path.is_file() else issued.get(name)
        if data is None:
            missing_test_files.append(name)
            continue
        require(digest(data) == expected_sources[name]['sha256'], 'Selected test file identity')
        text = data.decode()
        # These frozen class files indent the methods-closing `end` exactly
        # like `methods (Test)`. Bound the block there; otherwise a final Test
        # block can absorb nested helper functions following the class end.
        # Expected candidate membership and order remain mandatory below.
        blocks = list(re.finditer(
            r'(?ms)^(?P<indent>[ \t]*)methods[ \t]*\([ \t]*Test[ \t]*\)[^\n]*\n'
            r'(?P<body>.*?)^(?P=indent)end[ \t]*(?:%[^\n]*)?$', text))
        require(blocks, 'No bounded Test methods block found: '+name)
        names = [Path(name).stem+'/'+fn for block in blocks
                 for fn in re.findall(r'(?m)^[ \t]*function[ \t]+(\w+)[ \t]*\(', block.group('body'))]
        require(names == [x for x in c['ExpectedTestNames'] if x.startswith(Path(name).stem+'/')],
                'Selected test declarations disagree: '+name)
        derived_names.extend(names)
        test_sources_verified.append(name)
    actual_state = csv_data(owner['contract/checkpoints.csv'], contract['state_columns'])
    native_state = csv_data(issued[c['NativeReference']], contract['state_columns'])
    actual_feedback = csv_data(owner['contract/feedback.csv'], contract['feedback_columns'])
    native_feedback = csv_data(issued[c['NativeFeedbackReference']], contract['feedback_columns'])
    require(len(actual_state) == c['ExpectedCheckpointCount'] == 123
            and len(actual_feedback) == c['ExpectedFeedbackCount'] == 91, 'Row membership/count mismatch')
    actions = csv_data(owner['contract/actions.csv'], contract['action_columns'])
    states = {}
    for action, row in zip(actions, actual_state):
        key = (row['case_id'], int_value(row['step']))
        require(key not in states, 'Duplicate checkpoint identity')
        states[key] = row
        require(all(row[k] == action[k] for k in ['case_id', 'step', 'action', 'packet'])
                and abs(Decimal(row['time_s'])-Decimal(action['observe_s'])) <= TOLERANCE,
                'Checkpoint lineage/settled time mismatch')
        numeric = {k: int_value(v) for k, v in row.items()
                   if k not in ('case_id', 'time_s', 'action', 'packet', 'rx_ack_hex', 'rx_dack_hex')}
        require(numeric['nwk_owned'] == numeric['nsdp_relay']+numeric['nsdp_local']
                == numeric['nwk_waiting']+numeric['hop_resend'], 'NWK ownership conservation')
        require(numeric['hop_pending'] == numeric['hop_outstanding']
                == numeric['hop_resend']+numeric['hop_holds'], 'HOP custody conservation')
        require(numeric['nsdp_releases'] == numeric['ack_completed']+numeric['dack_completed'], 'Release conservation')
        require(all(re.fullmatch('[0-9A-F]{16}', row[k]) for k in ['rx_ack_hex','rx_dack_hex']), 'State bitmap encoding')
    assertion_count = 0
    for milestone in contract['milestones']:
        row = states[(milestone['case_id'], milestone['step'])]
        for key, expected in milestone['equals'].items():
            require(int_value(row[key]) == expected, 'Shared milestone mismatch: '+str(milestone))
            assertion_count += 1
    for feedback in actual_feedback:
        row = states[(feedback['case_id'], int_value(feedback['step']))]
        require(row['action'] == 'RX' and Decimal(feedback['time_s']) < Decimal(row['time_s']), 'Feedback RX lineage')
        require(feedback['kind'] in ('ACK','DACK') and all(re.fullmatch('[0-9A-F]{16}',feedback[k]) for k in ['ack_hex','dack_hex']), 'Feedback encoding')
        for a, b in [('sequence','rx_highest'), ('ack_hex','rx_ack_hex'), ('dack_hex','rx_dack_hex'),
                     ('relay_nsdp','nsdp_relay'), ('local_nsdp','nsdp_local'), ('nwk_owned','nwk_owned')]:
            require(feedback[a] == row[b], 'Feedback/state reconciliation: '+a)
    for key, row in states.items():
        emitted = [f for f in actual_feedback if f['case_id'] == key[0] and int(f['step']) <= key[1]]
        require(sum(f['kind'] == 'ACK' for f in emitted) == int(row['ack_generated'])
                and sum(f['kind'] == 'DACK' for f in emitted) == int(row['dack_generated']),
                'Per-step actual feedback/counter mismatch')
    state_comparison = compare(actual_state, native_state)
    feedback_comparison = compare(actual_feedback, native_feedback)
    verify_receipt(summary['NativeComparison'], state_comparison)
    verify_receipt(summary['NativeFeedbackComparison'], feedback_comparison)
    for field, expected in [('CaseCount',7),('CheckpointCount',123),('FailedCount',state_comparison['unmatched_rows']),
                            ('FeedbackCount',91),('FeedbackFailedCount',feedback_comparison['unmatched_rows'])]:
        require(summary[field] == m['Contract'+field] == expected, 'Summary count mismatch: '+field)
    require(summary['DiagnosticCompleted'] is True and m['ContractCompleted'] is True, 'Incomplete diagnostic')
    cross_engine_pass = not state_comparison['unmatched_rows'] and not feedback_comparison['unmatched_rows']
    require(summary['Passed'] == m['ContractPassed'] == cross_engine_pass, 'Comparison pass claim mismatch')
    expected_status = 'completed-review-required' if cross_engine_pass else 'completed-differences-review-required'
    require(m['Status'] == expected_status, 'Final status disagrees with actual comparisons')
    require(m['MATLABExecuted'] is True and m['NativeExecuted'] is False and m['FocusedGateExecuted'] is True,
            'Execution scope flags')
    require(all(m[f] is False for f in ['FullAcceptanceGateExecuted','AcceptanceEstablished','NumericalParityEstablished']),
            'Owner makes unsupported broad acceptance claim')
    require(m['Runtime']['Runtime'] == 'MATLAB' and m['Runtime']['DefaultBackend'] == 'portable', 'Runtime identity')
    started = datetime.fromisoformat(m['StartedUTC'].replace('Z','+00:00'))
    completed = datetime.fromisoformat(m['CompletedUTC'].replace('Z','+00:00'))
    require(completed >= started, 'Completion precedes start')
    runtime_seconds = (completed-started).total_seconds()
    complete_bytes = all(not row['missing_count'] for row in byte_checks.values())
    return {
        'schema': 'csr-tranche23-independent-return-integrity-audit-v1',
        'verdict': 'PASS: diagnostic return integrity verified; cross-engine mismatches retained' if complete_bytes else
                   'PASS owner-to-issued bindings; historical source/reference byte reconstruction remains incomplete',
        'return_integrity_verified': True, 'all_original_source_reference_bytes_verified': complete_bytes,
        'cross_engine_contract_passed': cross_engine_pass, 'acceptance_established': False,
        'owner_archive_sha256': digest(owner_path.read_bytes()), 'issued_update_sha256': ISSUED_SHA,
        'candidate_sha256': CANDIDATE_SHA, 'owner_archive_files': len(owner),
        'closed_inventory_artifacts_verified': len(artifact_map), 'source_snapshot_entries': len(source_map),
        'matlab_source_snapshot_entries': sum(n.endswith('.m') for n in source_map),
        'reference_snapshot_entries': len(ref_map), 'initial_final_snapshot_records_identical': True,
        'baseline_sources_unchanged': 390, 'baseline_matlab_sources_unchanged': 178,
        'original_byte_verification': byte_checks, 'tests_passed': 79, 'test_declarations_verified': len(derived_names),
        'test_source_files_verified': test_sources_verified, 'missing_test_source_files': missing_test_files,
        'runtime': m['Runtime'], 'elapsed_seconds': runtime_seconds,
        'shared_milestones_verified': len(contract['milestones']), 'shared_assertions_verified': assertion_count,
        'state_comparison': state_comparison, 'feedback_comparison': feedback_comparison,
        'comparison_receipts_truthful': True,
        'limitations': [
            'Owner-returned hashes and logs do not independently prove MATLAB execution.',
            'Controlled receiver/HOP behavior does not establish an effect on full-campus traffic or the +/-10% parity target.',
            'No MATLAB, native simulation, or broad regression was re-executed by this independent audit.',
        ]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('audit.json'))
    args = parser.parse_args()
    root = args.source_root or args.workspace/'t23-return-review/issued-overlay'
    result = audit(args.workspace, root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['verdict','owner_archive_sha256','tests_passed','elapsed_seconds',
                                          'all_original_source_reference_bytes_verified']}, indent=2))
