#!/usr/bin/env python3
"""Extract the first K draw-time divergence and all preceding key updates."""
import csv
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
K = ROOT / 'autonomous_ninth/data/K_receiver_timers'
NATIVE = ROOT / 'autonomous/native_capture/run/observations.tsv'


def dump_csv(name, rows):
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def main():
    events = [json.loads(line) for line in (K / 'ordered_events.jsonl').open()]
    updates = []
    for i, r in enumerate(events):
        if r['kind'] != 'protocol' or r['details']['event'] != 'neighbor_control_send' or r['details']['details'].get('Kind') != 'KEY_UPDATE':
            continue
        node = r['node']; peer = r['details']['frame']['DestinationId']
        before, after = events[max(0, i - 80):i], events[i:i + 150]
        state = [x['details'] for x in before if x['node'] == node and x['kind'] == 'mac_boundary'][-1]
        returned = next(x for x in after if x['node'] == node and x['kind'] == 'mac_state_transition' and x['details']['Current'] == 'Search')
        enqueued = next(x for x in after if x['node'] == node and x['kind'] == 'protocol' and x['details']['event'] == 'mac_enqueue' and x['details']['frame'].get('Control', {}).get('Type') == 'KEY_UPDATE')
        assert returned['observation_order'] < enqueued['observation_order']
        assert state['State'] == 'Track'
        assert enqueued['time_s'] == returned['time_s'] == r['time_s']
        masking = 'existing ACK/data queue or active preparation' if state['DataQueueCount'] + state['AckQueueCount'] > 0 or state['PreparationActive'] else 'carried nonnegative reservation' if state['ReservationCounter'] >= 0 else 'exposed empty queue and unassigned reservation'
        updates.append({'time_s': r['time_s'], 'node': node, 'peer': peer,
            'state_before': state['State'], 'data_queue_before': state['DataQueueCount'],
            'ack_queue_before': state['AckQueueCount'], 'preparation_active_before': state['PreparationActive'],
            'reservation_counter_before': state['ReservationCounter'], 'reservation_slot_before': state['ReservationSlot'],
            'post_tx_wait_before': state['PostTxWaitActive'], 'control_send_order': r['observation_order'],
            'return_to_search_order': returned['observation_order'], 'mac_enqueue_order': enqueued['observation_order'],
            'mac_enqueue_control_id': enqueued['details']['frame']['Control']['Id'], 'masking_condition': masking})
    assert len(updates) == 10
    assert sum(x['masking_condition'].startswith('exposed') for x in updates) == 1

    requests = [json.loads(line) for line in (K / 'random_requests.jsonl').open()]
    timed = [r for r in requests if round(r['time_s'] * 1e9) != int(r['expected']['time_ns'])]
    first = timed[0]
    assert (first['node'], first['purpose'], first['ordinal']) == (4, 'mac_slot', 25)
    assert first['time_s'] == 62.881 and int(first['expected']['time_ns']) == 62870833632
    tx = next(r for r in events if r['kind'] == 'physical_tx_context' and r['node'] == 4 and r['time_s'] == 62.998)
    expected = tx['details']['expected']; expected = expected[0] if isinstance(expected, list) else expected
    assert int(expected['time_ns']) == 62985000000
    assert not tx['details']['mismatches']

    native = []
    for r in csv.DictReader(NATIVE.open(), delimiter='\t'):
        if r['node'] == '4' and 62870833632 <= int(r['time_ns']) <= 62870833632:
            native.append(r)
    dump_csv('native_first_divergence_context.csv', native)
    selected = [r for r in events if 144122 <= r['observation_order'] <= 144203]
    with (OUT / 'matlab_first_divergence_context.jsonl').open('w') as f:
        for r in selected: f.write(json.dumps(r, separators=(',', ':')) + '\n')
    dump_csv('key_update_masking_cases.csv', updates)
    inputs = [K / 'ordered_events.jsonl', K / 'random_requests.jsonl', NATIVE,
        ROOT / 'autonomous_eighth/kit/autocase/+ac/ControlWireNwk.m',
        ROOT / 'autonomous_eighth/kit/autocase/+ac/ReceiverTimerMac.m',
        ROOT / 'autonomous_eighth/kit/autocase/+ac/ReceiverTimerSignalEngine.m',
        ROOT / 'autonomous/native_env/csr/model/csr-hop-layer.h',
        ROOT / 'autonomous/native_env/csr/model/csr-nwk-layer.h',
        ROOT / 'autonomous/native_env/csr/model/csr-mac-core.h']
    summary = {'method': 'Read-only evidence/source review; no simulation or MATLAB execution.',
        'key_update_generations': len(updates), 'all_enqueued_after_Track_to_Search': True,
        'existing_queue_or_preparation': sum(r['masking_condition'].startswith('existing') for r in updates),
        'carried_reservation': sum(r['masking_condition'].startswith('carried') for r in updates),
        'exposed_empty_queue_unassigned_slot': sum(r['masking_condition'].startswith('exposed') for r in updates),
        'first_random_time_divergence': {'node': first['node'], 'purpose': first['purpose'], 'ordinal': first['ordinal'],
            'matlab_time_ns': round(first['time_s'] * 1e9), 'native_time_ns': int(first['expected']['time_ns']),
            'delay_ns': round(first['time_s'] * 1e9) - int(first['expected']['time_ns']),
            'raw_slot': first['value'], 'semantic_context_matched': first['context_matched']},
        'first_shifted_TX': {'node': 4, 'source_tx_ordinal': int(expected['source_tx_ordinal']),
            'native_semantic_tx_id': int(tx['details']['native_semantic_tx_id']),
            'matlab_time_ns': round(tx['time_s'] * 1e9), 'native_time_ns': int(expected['time_ns']),
            'delay_ns': round(tx['time_s'] * 1e9) - int(expected['time_ns']),
            'signature_matched': not tx['details']['mismatches'], 'kind': 'KEY_UPDATE', 'destination': 2, 'wire_bytes': 62},
        'cause': 'NWK defers newly created reliable KEY_UPDATE to same-time pump after PHY returns Track to Search; native sends synchronously inside receive.',
        'recommended_scope': 'Inline only the new KEY_UPDATE owner with reliable admission/capacity/rollback checks; keep native post-TX-wait ownership and MAC rules unchanged.',
        'limits': ['This is the first recorded random-request time difference, not the earliest protocol-state difference: the independent SNMP finding predates it.',
                   'The earlier masking rows show contextual conditions, not corrected-run validation.',
                   'No corrected network continuation or 15-percent parity claim.'],
        'inputs_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (OUT / 'key_update_order_audit.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
