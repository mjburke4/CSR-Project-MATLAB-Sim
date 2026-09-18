#!/usr/bin/env python3
"""Independent raw-data comparison for the owner T23 return; no simulations."""
from pathlib import Path
import csv, hashlib, io, json, zipfile
from datetime import datetime
from collections import Counter
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
ISSUED = ROOT / 't23-return-review/issued-overlay'
NATIVE = ISSUED / 'evidence/t23/native'
ARCHIVE = ROOT / 'upload/t23.zip'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def rows(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))

def compare(actual, reference):
    assert len(actual) == len(reference)
    found = []
    for position, (a, b) in enumerate(zip(actual, reference), 1):
        assert a.keys() == b.keys()
        assert (a['case_id'], a['step']) == (b['case_id'], b['step'])
        diff = {k: {'matlab': a[k], 'ns3': b[k]} for k in a
                if (abs(Decimal(a[k]) - Decimal(b[k])) > Decimal('1e-9') if k == 'time_s'
                    else a[k] != b[k])}
        if diff:
            found.append({'row': position, 'case_id': a['case_id'],
                          'step': int(a['step']), 'differences': diff})
    return found

with zipfile.ZipFile(ARCHIVE) as z:
    metadata = json.loads(z.read('metadata.json'))
    owner_summary = json.loads(z.read('contract/summary.json'))
    actual_states = rows(z.read('contract/checkpoints.csv'))
    actual_feedback = rows(z.read('contract/feedback.csv'))
    tests = rows(z.read('tests.csv'))
    source = json.loads(z.read('source.json'))
    artifact_hashes = {n: digest(z.read(n)) for n in z.namelist()}

reference_states = rows((NATIVE / 'checkpoints.csv').read_bytes())
reference_feedback = rows((NATIVE / 'feedback.csv').read_bytes())
contract = json.loads((ISSUED / 'scenarios/t23/contract.json').read_text())
state_diffs = compare(actual_states, reference_states)
feedback_diffs = compare(actual_feedback, reference_feedback)
state_map = {(r['case_id'], int(r['step'])): r for r in actual_states}
common_assertions = []
for milestone in contract['milestones']:
    row = state_map[milestone['case_id'], milestone['step']]
    for field, expected in milestone['equals'].items():
        actual = int(row[field])
        common_assertions.append({'case_id': milestone['case_id'], 'step': milestone['step'],
            'field': field, 'actual': actual, 'expected': expected, 'passed': actual == expected})
assert all(x['passed'] for x in common_assertions)
assert all(int(t['Passed']) == 1 and int(t['Failed']) == 0 and int(t['Incomplete']) == 0 for t in tests)

fields = ['case_id','step','kind','sequence','ack_hex','dack_hex']
feedback_values_equal = all(all(a[f] == b[f] for f in fields)
                            for a,b in zip(actual_feedback,reference_feedback))
max_feedback_time_diff = max(abs(Decimal(a['time_s']) - Decimal(b['time_s']))
                            for a,b in zip(actual_feedback,reference_feedback))
max_state_time_diff = max(abs(Decimal(a['time_s']) - Decimal(b['time_s']))
                         for a,b in zip(actual_states,reference_states))
assert feedback_values_equal and max_feedback_time_diff <= Decimal('1e-9')

native_summary = json.loads((NATIVE / 'summary.json').read_text())
source_provenance = {}
for name in ['csr-nwk-layer.h','csr-hop-layer.h']:
    file = OUT / 'source' / name
    sha = digest(file.read_bytes())
    assert sha == native_summary['model_sources']['model/' + name]
    source_provenance[name] = {'sha256': sha, 'native_reference_match': True,
        'source_commit': native_summary['source_pin'],
        'url': 'https://github.com/mjburke4/CSR-Project-NS3-part2/blob/' +
        native_summary['source_pin'] + '/model/' + name}
matlab_name = '+csr/+nwk/Layer.m'
matlab_bytes = (ISSUED / matlab_name).read_bytes()
sha = digest(matlab_bytes)
entry = next(x for x in source if x['path'] == matlab_name)
assert entry['sha256'] == sha
(OUT / 'source' / 'matlab-nwk-Layer.m').write_bytes(matlab_bytes)
source_provenance[matlab_name] = {'sha256': sha, 'owner_source_snapshot_match': True}

special = []
for case, step in [('dack_duplicate_pressure',18),('dack_reassessment_after_release',24)]:
    a = state_map[case,step]
    b = next(r for r in reference_states if r['case_id'] == case and int(r['step']) == step)
    fb = next(r for r in actual_feedback if r['case_id'] == case and int(r['step']) == step)
    special.append({'case_id': case, 'step': step, 'settled_time_s': float(a['time_s']),
        'matlab_custody': int(a['nwk_owned']), 'ns3_custody': int(b['nwk_owned']),
        'matlab_waiting': int(a['nwk_waiting']), 'ns3_waiting': int(b['nwk_waiting']),
        'feedback_time_s': fb['time_s'],
        'feedback_equal_fields': {k: fb[k] for k in ['kind','sequence','ack_hex','dack_hex']}})

result = {
    'schema': 'csr-t23-independent-behavioral-findings-v1',
    'owner_archive_sha256': digest(ARCHIVE.read_bytes()),
    'status': 'completed_diagnostic_with_confirmed_custody_difference',
    'runtime': metadata['Runtime'],
    'owner_runtime_seconds': (datetime.fromisoformat(metadata['CompletedUTC'].replace('Z','+00:00')) -
                              datetime.fromisoformat(metadata['StartedUTC'].replace('Z','+00:00'))).total_seconds(),
    'tests': {'total': len(tests), 'passed': len(tests), 'failed': 0, 'incomplete': 0},
    'case_count': len(set(r['case_id'] for r in actual_states)),
    'state_checkpoints': {'total': len(actual_states), 'matched': len(actual_states)-len(state_diffs),
                          'mismatched': len(state_diffs), 'differences': state_diffs,
                          'timestamp_tolerance_s': 1e-9,
                          'max_absolute_timestamp_difference_s': float(max_state_time_diff),
                          'max_absolute_timestamp_difference_decimal_s': str(max_state_time_diff)},
    'feedback_records': {'total': len(actual_feedback),
        'matched_including_occupancy_metadata': len(actual_feedback)-len(feedback_diffs),
        'mismatched_including_occupancy_metadata': len(feedback_diffs),
        'captured_control_field_matches': len(actual_feedback),
        'control_field_mismatches': 0, 'timestamp_tolerance_s': 1e-9,
        'max_absolute_timestamp_difference_s': float(max_feedback_time_diff),
        'max_absolute_timestamp_difference_decimal_s': str(max_feedback_time_diff),
        'differences': feedback_diffs,
        'scope': 'Captured ACK/DACK kind, HOP sequence, ACK/DACK bitmap and enqueue time; no RF or full serialized protected-frame comparison.'},
    'common_milestones': len(contract['milestones']),
    'common_assertions': {'total': len(common_assertions), 'passed': len(common_assertions), 'failed': 0},
    'key_observations': special,
    'source_cause': {
        'matlab': 'NWK.receiveData returns accepted at Seen(SourceId,Id) before queue insertion. enqueueApplication also prevents another pending owner for the same app identity.',
        'ns3': 'HOP CheckReceivedSeq regards a DACK-marked replay as a new admissible pass; NWK ReceiveFromHop adds a relay queue entry and increments NSDP for each callback.',
        'feedback': 'Both implementations choose feedback from pre-enqueue pressure. The replay under pressure remains DACK; the replay after three releases is ACK. All captured control fields match.',
        'ack_dack_overlap': 'After reassessment the ACK bitmap ends in 1FFFF and DACK retains bit 0. This is equal in both returns; native ACK-window processing masks DACK bits covered by ACK.'},
    'source_provenance': source_provenance,
    'accepted_for_behavioral_review': True,
    'requires_matlab_rerun_for_behavioral_evidence': False,
    'cross_engine_exact_contract_passed': False,
    'campus_parity_established': False,
    'production_change_recommended_now': False,
    'next_experiment': [
        'First census accepted campus traces for repeated relay admissions of the same source/application identity after a DACK and before prior custody ends, especially node 8 / 8-to-2.',
        'If existing traces cannot resolve identity/custody lineage, use a bounded observer-only replay covering DACK loss/retry and subsequent queue drain; count extra owners, their lifetime, outgoing duplicate traffic, admission decisions and per-flow completions.',
        'Only if material incidence is demonstrated, evaluate a narrowly scoped optional custody model with distinct ownership tokens and completion bookkeeping; changing the Seen guard alone is insufficient.',
        'Judge any future behavioral variant against matched per-flow delivery and delay at the existing plus/minus 10 percent campus goal before changing the default.'
    ],
    'limitations': [
        'Decoded-packet controlled callback experiment; autonomous MAC/RF transmission, PHY/ECC, security ingress, routing convergence and stochastic campus throughput are not exercised.',
        'State snapshots are taken one microsecond after each action; same-tick callback ordering is not compared.',
        'The two replay cases end immediately after the occupancy divergence, so subsequent downstream service, admission or throughput impact is not measured.',
        'Local-origin admission was not attempted after these divergent replay events; T23 does not establish that the extra relay owner changes the independent local quota.',
        'Full provenance/candidate/source inventory acceptance is a separate independent integrity check.'
    ],
    'artifact_sha256': artifact_hashes,
}
(OUT / 'findings.json').write_text(json.dumps(result,indent=2) + '\n')
(OUT / 'common_assertions.json').write_text(json.dumps(common_assertions,indent=2) + '\n')
print(json.dumps({k: result[k] for k in ['status','owner_runtime_seconds','tests','case_count','common_milestones','common_assertions']},indent=2))
