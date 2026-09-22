#!/usr/bin/env python3
"""Static binding/schema checks; does not execute or emulate MATLAB MAC."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[1]
read = lambda name: list(csv.DictReader((root / name).open()))
profile = json.loads((root / 'inputs/profile.json').read_text())
fidelity = json.loads((root / 'reference/fidelity.json').read_text())
assert fidelity['all_passed'] and fidelity['source_capture']['exact_prefix']
frames = read('inputs/frames.csv')
inputs = read('inputs/inputs.csv')
draws = read('inputs/draws.csv')
txs = read('reference/tx.csv')
nodes = profile['nodes']
stop = profile['replay_stop_ns']
by_id = {int(row['frame_id']): row for row in frames}
assert len(by_id) == len(frames)
assert len({int(row['event_order']) for row in inputs}) == len(inputs)
assert all(int(row['has_link_control']) == 1 for row in frames)
assert all(int(row['rate']) == 8 and float(row['tx_power_dbm']) == 33 for row in frames)
supported = {'receiver_state', 'sync', 'received', 'active', 'reported', 'enqueue', 'cancel_ack', 'cancel_type'}
for row in inputs:
    assert row['kind'] in supported
    assert 0 <= int(row['time_ns']) < stop
    assert int(row['node']) in nodes
    if row['kind'] == 'enqueue':
        frame = by_id[int(row['frame_id'])]
        assert frame['node'] == row['node']
    elif row['kind'] == 'cancel_ack':
        assert 0 <= int(row['ack_bitmap']) <= 2**64-1
        assert 0 <= int(row['dack_bitmap']) <= 2**64-1
    elif row['kind'] == 'receiver_state':
        assert row['value'] in {'idle', 'search', 'track'}
for node in nodes:
    rows = [row for row in draws if int(row['node']) == node]
    assert [int(row['ordinal']) for row in rows] == list(range(1,len(rows)+1))
    assert all(int(row['min']) <= int(row['draw']) <= int(row['max']) for row in rows)
for tx in txs:
    ids = [int(value) for value in tx['frame_ids'].split(';')]
    assert ids and all(by_id[i]['node'] == tx['node'] for i in ids)
    assert sum(int(by_id[i]['wirebytes']) for i in ids) == int(tx['wirebytes'])
record = {
    'pass': True,
    'scope': 'Static schema/binding check only; MATLAB runtime has not been executed here.',
    'native_fidelity_pass': True,
    'frames': len(frames), 'inputs': len(inputs), 'draws': len(draws), 'reference_transmissions': len(txs),
    'input_kinds': dict(Counter(row['kind'] for row in inputs)),
    'all_frames_explicit_link_control': True,
    'all_frames_rate_key': 8, 'all_frames_tx_power_dbm': 33,
    'bitmap_precision': 'Decimal strings retained; MATLAB converts by exact uint64 digit accumulation.',
    'per_node': {str(node): {
        'inputs': sum(int(row['node']) == node for row in inputs),
        'draws': sum(int(row['node']) == node for row in draws),
        'reference_transmissions': sum(int(row['node']) == node for row in txs)
    } for node in nodes}
}
(root / 'matlab/static_fixture_check.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
