#!/usr/bin/env python3
"""Cross-check prior R2025a output against the recovered 0–330 s native tape.

No MATLAB simulation is run. Expectations come from native CSV rows, and every
observed row comes from the actual September 23 owner-return archive.
"""
from __future__ import annotations

import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'next_feedback/recovered/NS3 to MATLAB Network Simulation/out_mh_20260923_121427.zip'
TAPE = ROOT / 'next_feedback/prior_coverage/out_short_20260924_083651/replays/source5_mac/staging'
OLD_TAPE = ROOT / 'next_feedback/mac_kit/macfix/inputs'
STOP = 330_000_000_000
START = 300_000_000_000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(data):
    return list(csv.DictReader(io.StringIO(data)))


def normalized(row):
    return {k: (v if k == 'frame_ids' else str(Decimal(v).normalize())) for k, v in row.items()}


def compare(left, right):
    for i, (a, b) in enumerate(zip(left, right)):
        if normalized(a) != normalized(b):
            return {'pass': False, 'row': i, 'expected': a, 'actual': b}
    return {'pass': len(left) == len(right), 'expected_rows': len(left), 'actual_rows': len(right)}


def main():
    native_tx = read_csv((TAPE / 'reference/tx.csv').read_text())
    native_inputs = read_csv((TAPE / 'inputs/inputs.csv').read_text())
    native_frames = {r['frame_id']: r for r in read_csv((TAPE / 'inputs/frames.csv').read_text())}
    old_inputs = read_csv((OLD_TAPE / 'inputs.csv').read_text())
    old_frames = {r['frame_id']: r for r in read_csv((OLD_TAPE / 'frames.csv').read_text())}
    # IDs and observer event_order are capture-local. Establish an independent
    # bijection from ordered enqueues with identical fields and full packet bytes.
    old_to_new = {}
    new_to_old_input = {}
    for node in [8, 2]:
        old = [r for r in old_inputs if int(r['node']) == node and int(r['time_ns']) < STOP and r['kind'] == 'enqueue']
        new = [r for r in native_inputs if int(r['node']) == node and r['kind'] == 'enqueue']
        assert len(old) == len(new)
        for a, b in zip(old, new):
            assert {k:v for k,v in a.items() if k not in ['frame_id','event_order']} == {k:v for k,v in b.items() if k not in ['frame_id','event_order']}
            af, bf = old_frames[a['frame_id']], native_frames[b['frame_id']]
            assert {k:v for k,v in af.items() if k != 'frame_id'} == {k:v for k,v in bf.items() if k != 'frame_id'}
            assert a['frame_id'] not in old_to_new or old_to_new[a['frame_id']] == b['frame_id']
            old_to_new[a['frame_id']] = b['frame_id']
            new_to_old_input[b['frame_id']] = a
    assert len(set(old_to_new.values())) == len(old_to_new)
    result = {'schema': 'csr-prior-actual-service-crosscheck-v1',
              'owner_archive': str(ARCHIVE.relative_to(ROOT)), 'owner_archive_sha256': sha(ARCHIVE),
              'native_reference_sha256': sha(TAPE / 'reference/tx.csv'),
              'scope': 'Prior real R2025a conditional MAC outputs under common native inputs; not autonomous-network parity.',
              'new_owner_run_required_for_these_mac_assertions': False, 'nodes': [], 'targets': [],
              'frame_identity_binding': {'method':'Ordered equal enqueue fields plus every frame field including packet_hex; frame_id/event_order are capture-local', 'bijective_frame_count':len(old_to_new)}}
    with zipfile.ZipFile(ARCHIVE) as z:
        assert z.testzip() is None
        suite = json.loads(z.read('history/run_summary.json'))
        result['original_history_completed'] = suite['completed']
        result['original_history_behavioral_pass'] = suite['behavioral_pass']
        actual_by_node = {}
        applied_by_node = {}
        for node in [8, 2]:
            old_actual = read_csv(z.read(f'history/node{node}/tx.csv').decode())
            actual_all = []
            for row in old_actual:
                if int(row['time_ns']) >= STOP:
                    continue
                converted = dict(row)
                converted['frame_ids'] = ';'.join(old_to_new[x] for x in row['frame_ids'].split(';'))
                actual_all.append(converted)
            actual_by_node[node] = actual_all
            applied_by_node[node] = read_csv(z.read(f'history/node{node}/input_application.csv').decode())
            actual = [r for r in actual_all if int(r['time_ns']) < STOP]
            expected = [r for r in native_tx if int(r['node']) == node and int(r['time_ns']) < STOP]
            actual_window = [r for r in actual if int(r['time_ns']) >= START]
            expected_window = [r for r in expected if int(r['time_ns']) >= START]
            node_result = {'node': node, 'full_0_330_tx': compare(expected, actual),
                           'target_300_330_tx': compare(expected_window, actual_window)}
            result['nodes'].append(node_result)
            with (HERE / f'prior_actual_node{node}_tx_0_330.csv').open('w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(actual[0])); w.writeheader(); w.writerows(actual)
        for node, fid, feedback_peer in [(8, '444', 7), (2, '439', None), (2, '619', 8)]:
            enqueue = next(r for r in native_inputs if r['kind'] == 'enqueue' and r['frame_id'] == fid)
            expected_first = next(r for r in native_tx if int(r['node']) == node and fid in r['frame_ids'].split(';'))
            actual_candidates = [r for r in actual_by_node[node] if fid in r['frame_ids'].split(';')]
            actual_first = actual_candidates[0] if actual_candidates else None
            if actual_first is None:
                result['targets'].append({'node': node, 'frame_id': fid, 'pass': False, 'error': 'not transmitted'})
                continue
            start = int(enqueue['time_ns']); end = int(actual_first['time_ns'])
            prior_actual = [r for r in actual_by_node[node] if start <= int(r['time_ns']) < end]
            prior_native = [r for r in native_tx if int(r['node']) == node and start <= int(r['time_ns']) < int(expected_first['time_ns'])]
            old_enqueue = new_to_old_input[fid]
            applied = [r for r in applied_by_node[node] if r['event_order'] == old_enqueue['event_order']]
            applied_pass = (len(applied) == 1 and applied[0]['applied'] == '1' and applied[0]['reason'] == 'applied'
                            and int(applied[0]['time_ns']) == start and applied[0]['kind'] == 'enqueue')
            feedback_pass = True
            if feedback_peer is not None:
                for tx in prior_actual:
                    children = tx['frame_ids'].split(';')
                    feedback_pass &= len(children) == 1
                    for child in children:
                        frame = native_frames[child]
                        feedback_pass &= int(frame['type']) in [1, 2] and int(frame['destination']) == feedback_peer and int(frame['node']) == node
            tx_match = normalized(expected_first) == normalized(actual_first)
            prior_match = compare(prior_native, prior_actual)
            checks = {'first_tx_exact': tx_match, 'enqueue_applied_at_expected_time': applied_pass,
                      'preceding_tx_exact': prior_match['pass'], 'preceding_feedback_peer_matches': feedback_pass}
            result['targets'].append({'node': node, 'new_capture_frame_id': int(fid), 'prior_capture_frame_id':int(old_enqueue['frame_id']), 'enqueue_time_ns': start,
                                      'native_first_tx': expected_first, 'actual_first_tx': actual_first,
                                      'waiting_ns': end-start, 'preceding_tx_count': len(prior_actual),
                                      'feedback_peer': feedback_peer, 'checks': checks, 'pass': all(checks.values())})
    result['all_passed'] = (result['original_history_completed'] and result['original_history_behavioral_pass']
                            and all(n['full_0_330_tx']['pass'] and n['target_300_330_tx']['pass'] for n in result['nodes'])
                            and all(t['pass'] for t in result['targets']))
    result['new_owner_run_required_for_these_mac_assertions'] = not result['all_passed']
    (HERE / 'prior_actual_service_assertions.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    assert result['all_passed']


if __name__ == '__main__':
    main()
