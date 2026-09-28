#!/usr/bin/env python3
"""Read-only arithmetic/lifecycle audit; no MATLAB or network execution."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
J = ROOT / 'autonomous_eighth/data/J_discovery_identity'
NATIVE = ROOT / 'autonomous/native_capture/fixture'


def write_csv(name, rows):
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    clock_path = ROOT / 'autonomous_eighth/native/clock_values.csv'
    clock = {int(r['time_ns']): float(r['native_seconds']) for r in csv.DictReader(clock_path.open())}
    native_acq = Counter()
    native_finish = Counter()
    acquisition = []
    for r in csv.DictReader((NATIVE / 'receiver_history.csv').open()):
        d = json.loads(r['detail_json'])
        if d.get('cause') == 'CsrNetDevice::OnMacTxFinished' and d.get('phase') == 'enter':
            native_finish[(int(r['node']), int(r['time_ns']))] += 1
        if r['event'] != 'timer_lifecycle' or d.get('action') != 'schedule' or d.get('timer') != 'm_acquisitionEvent':
            continue
        start, end = int(r['time_ns']), int(d['deadline_ns'])
        assert end == start + 6630000
        native_acq[(int(r['node']), start, end)] += 1
        old = start / 1e9 + 0.00663
        canonical = end / 1e9
        exact_old = clock[start] + 0.00663
        exact_end = clock[end]
        acquisition.append({'node': int(r['node']), 'event_order': r['event_order'],
            'start_ns': start, 'deadline_ns': end, 'ns_division_seconds': canonical,
            'pinned_native_seconds': exact_end,
            'double_add_counterfactual_seconds': old,
            'different_binary64': old != canonical,
            'pinned_native_double_add_counterfactual_seconds': exact_old,
            'pinned_native_double_add_different': exact_old != exact_end,
            'ulp_difference': (old - canonical) / math.ulp(canonical)})

    native_tx = []
    durations = {8: .00051, 16: .000254, 32: .000126, 64: .000062, 128: .000030,
                 500: 4 / 500000, 1000: 4 / 1000000}
    for r in csv.DictReader((NATIVE / 'tx_signatures.csv').open()):
        if r['child_index'] != '0':
            continue
        start = int(r['time_ns'])
        preamble = 7888 if int(r['preamble']) else 104
        rate = 4 / durations[int(r['rate_kbps'])]
        duration = (preamble + 48) / 4 * .00051 + (int(r['total_wire_bytes']) * 8 + 32) / rate
        end = start + round(duration * 1e9)
        old, canonical = start / 1e9 + duration, end / 1e9
        native_tx.append({'tx_id': r['tx_id'], 'source': int(r['source']),
            'start_ns': start, 'duration_seconds': duration,
            'duration_ns': round(duration * 1e9), 'deadline_ns': end,
            'ns_division_seconds': canonical, 'double_add_counterfactual_seconds': old,
            'different_binary64': old != canonical,
            'ulp_difference': (old - canonical) / math.ulp(canonical),
            'native_completion_observed': bool(native_finish[(int(r['source']), end)])})

    events = [json.loads(line) for line in (J / 'ordered_events.jsonl').open()]
    fired = {r['details']['EventId'] for r in events if r['kind'] == 'scheduler_fire'}
    callback_types = {'@()obj.acquire(index)': 'acquisition', '@()obj.finishTx(txIndex)': 'phy_tx_finish',
                      '@()obj.finishTx()': 'mac_tx_finish', '@()obj.returnRejectedToSearch(index)': 'rejected_return'}
    observed = []
    last_phy_node = last_tx_node = None
    for r in events:
        if r['kind'] == 'phy_boundary':
            last_phy_node = r['node']
        if r['kind'] == 'physical_tx_context':
            last_tx_node = r['node']
        if r['kind'] != 'scheduler_schedule' or r['details']['Callback'] not in callback_types:
            continue
        d = r['details']; kind = callback_types[d['Callback']]
        start, old = r['time_s'], d['DeadlineSeconds']
        delay = .00663 if kind == 'acquisition' else 28e-9 if kind == 'rejected_return' else old - start
        start_ns = round(start * 1e9)
        end_ns = start_ns + round(delay * 1e9)
        canonical = end_ns / 1e9
        node = last_phy_node if kind in ('acquisition', 'rejected_return') else last_tx_node
        match = bool(native_acq[(node, start_ns, end_ns)]) if kind == 'acquisition' else None
        observed.append({'kind': kind, 'node': node, 'event_id': d['EventId'],
            'observation_order': r['observation_order'], 'start_seconds': start,
            'start_ns': start_ns, 'deadline_ns': end_ns,
            'actual_deadline_seconds': old, 'ns_division_deadline_seconds': canonical,
            'different_binary64': old != canonical,
            'ulp_difference': (old - canonical) / math.ulp(canonical),
            'fired_in_J': d['EventId'] in fired, 'native_acquisition_lifecycle_match': match})
    groups = {}
    for kind in callback_types.values():
        rows = [r for r in observed if r['kind'] == kind]
        groups[kind] = {'scheduled': len(rows), 'fired': sum(r['fired_in_J'] for r in rows),
                       'different_binary64': sum(r['different_binary64'] for r in rows),
                       'different_binary64_and_fired': sum(r['different_binary64'] and r['fired_in_J'] for r in rows)}
    acq = [r for r in observed if r['kind'] == 'acquisition']
    assert len(acq) == 230 and all(r['native_acquisition_lifecycle_match'] for r in acq)
    phy_fin = [r for r in observed if r['kind'] == 'phy_tx_finish']
    mac_fin = [r for r in observed if r['kind'] == 'mac_tx_finish']
    assert len(phy_fin) == len(mac_fin) == 129
    for phy, mac in zip(phy_fin, mac_fin):
        assert phy['node'] == mac['node'] and phy['actual_deadline_seconds'] == mac['actual_deadline_seconds']
        assert phy['event_id'] < mac['event_id']

    first = json.loads((J / 'first_divergence.json').read_text())
    start_ns = int(first['actual']['interval_start_ns'])
    end_ns = int(first['actual']['interval_end_ns'])
    start = start_ns / 1e9
    actual_end = float(first['actual_time_s'])
    native_end = end_ns / 1e9
    rate = 4 / .00051
    actual_product, native_product = (actual_end - start) * rate, (native_end - start) * rate
    assert math.floor(actual_product) == first['actual']['bits'] == 52
    assert math.floor(native_product) == first['expected']['bits'] == 51
    inputs = [J / 'ordered_events.jsonl', J / 'first_divergence.json', NATIVE / 'receiver_history.csv', NATIVE / 'tx_signatures.csv', clock_path]
    for suffix in ['+csr/+phy/SignalEngine.m', '+csr/+phy/Model.m', '+csr/+mac/Layer.m', '+csr/+sim/TransportTiming.m', '+csr/+sim/EventScheduler.m']:
        inputs.append(ROOT / 'autonomous_seventh/kit/autocase/model' / suffix)
    summary = {'method': 'Source-derived binary64 arithmetic on existing records; no MATLAB/network execution.',
        'observed_J': groups, 'all_J_acquisition_lifecycle_keys_match_native': True,
        'paired_MAC_PHY_TX_finish_deadlines_and_insertion_order_match': True,
        'native_acquisition_counterfactual': {'scheduled': len(acquisition),
            'using_ns_division_old_double_add_differs': sum(r['different_binary64'] for r in acquisition),
            'using_pinned_native_GetSeconds_old_double_add_differs': sum(r['pinned_native_double_add_different'] for r in acquisition),
            'all_native_deadlines_equal_start_ns_plus_6630000': True},
        'native_TX_finish_counterfactual': {'scheduled': len(native_tx),
            'old_double_add_differs': sum(r['different_binary64'] for r in native_tx),
            'native_completion_observed': sum(r['native_completion_observed'] for r in native_tx),
            'unobserved_completion_deadlines_ns': [r['deadline_ns'] for r in native_tx if not r['native_completion_observed']]},
        'first_stop': {'interval_start_ns': start_ns, 'interval_end_ns': end_ns,
            'start_double_17g': format(start, '.17g'), 'actual_end_double_17g': format(actual_end, '.17g'),
            'native_end_double_17g': format(native_end, '.17g'),
            'actual_product_17g': format(actual_product, '.17g'), 'native_product_17g': format(native_product, '.17g'),
            'actual_bits': math.floor(actual_product), 'native_bits': math.floor(native_product)},
        'limits': ['Future native-row arithmetic counterfactuals are not a corrected MATLAB trajectory.',
                   'Observed J comparison targets and native TX arithmetic use integer-ns/1e9. This is not a bitwise-equivalent implementation of every ns-3 GetSeconds value.',
                   'J has no rejected-return28ns execution.', 'Native TX completion after330s is only a scheduled target.',
                   'Do not change continuous physical signal fields or Model truncation.',
                   'Global scheduler rounding requires broader call-site mapping and is not established by this scope.'],
        'inputs_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    write_csv('observed_J_relative_timers.csv', observed)
    write_csv('native_acquisition_arithmetic.csv', acquisition)
    write_csv('native_TX_finish_arithmetic.csv', native_tx)
    (OUT / 'relative_timer_audit.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: summary[k] for k in ['observed_J', 'native_acquisition_counterfactual', 'native_TX_finish_counterfactual', 'first_stop']}, indent=2))


if __name__ == '__main__':
    main()
