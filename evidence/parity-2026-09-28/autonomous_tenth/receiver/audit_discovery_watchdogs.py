#!/usr/bin/env python3
"""Read-only L watchdog/late-route and prior-milestone evidence extraction."""
import csv
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CASE = ROOT / 'autonomous_tenth/data/L_discovery_lifecycle'


def ns(value):
    return round(value * 1e9)


def write_csv(name, rows):
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    rows = [json.loads(line) for line in (CASE / 'ordered_events.jsonl').open()]
    requests = [json.loads(line) for line in (CASE / 'random_requests.jsonl').open()]
    management = []
    route7 = []
    for r in rows:
        if r['kind'] != 'protocol': continue
        d = r['details']; frame = d.get('frame', {}); control = frame.get('Control', {})
        if d['event'] in ('hop_control_receive', 'mac_enqueue') and control.get('Type', '').startswith('SNMP'):
            payload = control['Payload']
            management.append({'order': r['observation_order'], 'time_s': r['time_s'], 'time_ns': ns(r['time_s']),
                'node': r['node'], 'event': d['event'], 'kind': control['Type'],
                'source': payload['SourceId'], 'destination': payload['DestinationId'],
                'hop_peer': frame['DestinationId'] if d['event'] == 'mac_enqueue' else frame['SourceId'],
                'advertised_nodes': ';'.join(map(str, payload.get('Nodes', [])))})
        if r['node'] != 3 or d['event'] != 'hop_control_receive' or control.get('Type') != 'ROUTING': continue
        b = bytes(control['Payload']['Bytes']); offset = 6
        while offset < len(b):
            op = b[offset]; offset += 1
            if op == 1: offset += 3
            elif op == 4: offset += 16
            elif op == 2:
                destination = int.from_bytes(b[offset:offset + 3], 'big'); capability = b[offset + 3]
                hops = int.from_bytes(b[offset + 4:offset + 6], 'big')
                cost = int.from_bytes(b[offset + 6:offset + 10], 'big')
                path = [int.from_bytes(b[offset + 10 + 3*k:offset + 13 + 3*k], 'big') for k in range(hops)]
                offset += 10 + 3*hops
                if destination == 7:
                    route7.append({'time_s': r['time_s'], 'order': r['observation_order'], 'receiver': 3,
                        'peer': frame['SourceId'], 'routing_sequence': int.from_bytes(b[:4], 'big'),
                        'destination': 7, 'capability': capability, 'advertised_hops': hops,
                        'advertised_cost': cost, 'advertised_path': ';'.join(map(str, path))})
            else: assert op in (0, 3)
            assert offset <= len(b)

    fires = {r['details']['EventId']: r for r in rows if r['kind'] == 'scheduler_fire'}
    returns = {r['details']['EventId']: r for r in rows if r['kind'] == 'scheduler_return'}
    timers = []
    for r in rows:
        if r['kind'] != 'scheduler_schedule' or r['details']['Callback'] != '@()obj.scanWatchdog(generation)': continue
        d = r['details']; eid = d['EventId']
        starts = [m for m in management if m['event'] == 'mac_enqueue' and m['kind'] == 'SNMP_START' and m['time_ns'] == ns(r['time_s'])]
        assert len(starts) == 1
        start = starts[0]; fire = fires.get(eid); ret = returns.get(eid)
        spawned = []
        if fire and ret:
            spawned = [x for x in rows[fire['observation_order']:ret['observation_order']-1] if x['kind'] == 'scheduler_schedule']
        timers.append({'event_id': eid, 'node': start['node'], 'target': start['destination'],
            'creation_time_s': r['time_s'], 'creation_ns': ns(r['time_s']),
            'deadline_s': d['DeadlineSeconds'], 'deadline_ns': ns(d['DeadlineSeconds']),
            'delay_ns': ns(d['DeadlineSeconds']) - ns(r['time_s']),
            'fired': fire is not None, 'fire_ns': ns(fire['time_s']) if fire else '',
            'spawned_events_during_callback': len(spawned)})
    assert len(timers) == 14 and all(t['delay_ns'] == 60000000000 for t in timers)
    old = next(t for t in timers if t['event_id'] == 9815)
    current = next(t for t in timers if t['event_id'] == 16021)
    assert old['node'] == current['node'] == 3 and old['target'] == 5 and current['target'] == 4
    assert old['fired'] and old['spawned_events_during_callback'] == 0
    assert current['fire_ns'] == 116340299163 and current['spawned_events_during_callback'] == 2
    explicit = [m for m in management if m['node'] == 3 and ((m['event'] == 'mac_enqueue' and m['kind'] == 'SNMP_DONE') or (m['event'] == 'hop_control_receive' and m['kind'] == 'SNMP_DONE'))]
    assert [m['advertised_nodes'] for m in explicit] == ['5;1', '4;3;1']
    assert route7[0]['time_s'] == 96.268879163
    first = next(r for r in requests if ns(r['time_s']) != int(r['expected']['time_ns']))
    assert (first['node'], first['purpose'], first['ordinal']) == (3, 'mac_slot', 102)
    milestones = []
    draw = next(r for r in requests if (r['node'], r['purpose'], r['ordinal']) == (4, 'mac_slot', 25))
    assert draw['context_matched'] and ns(draw['time_s']) == int(draw['expected']['time_ns']) == 62870833632
    milestones.append({'name': 'KEY_UPDATE first draw', 'time_ns': 62870833632, 'passed': True})
    for node, target_ns, label in [(4, 62985000000, 'KEY_UPDATE transmission'), (5, 71942000000, 'SNMP requester target1 transmission')]:
        r = next(r for r in rows if r['kind'] == 'physical_tx_context' and r['node'] == node and ns(r['time_s']) == target_ns)
        assert not r['details']['mismatches']
        milestones.append({'name': label, 'time_ns': target_ns, 'passed': True})
    summary = {'method': 'Existing evidence extraction; no MATLAB execution, simulation or production edits.',
        'watchdogs_scheduled': len(timers), 'all_watchdog_delays_ns': 60000000000,
        'node3_superseded_watchdog': old, 'node3_current_watchdog': current,
        'node3_explicit_discovery_membership_inputs': explicit, 'node3_received_route7_updates': route7,
        'first_draw_time_difference': {'node': 3, 'purpose': 'mac_slot', 'ordinal': 102,
            'actual_time_ns': ns(first['time_s']), 'expected_time_ns': int(first['expected']['time_ns']),
            'interpretation': 'Extra scan traffic consumes the next slot draw before native application traffic; not a clock-delay measurement.'},
        'prior_milestones': milestones,
        'conclusion': 'Correct watchdog scheduling and superseded-callback invalidation; extra target7 arises from live-route membership refresh in advanceScan.',
        'limits': ['Membership seeding is source-reviewed; private ScanKnown was not logged.',
                   'A received valid route update is not a discovery advertisement.',
                   'Unmatched or duplicate DONE semantics are outside this actual failure; do not change ownership gates based on this trace.',
                   'No corrected autonomous continuation or full-run parity claim.'],
        'inputs_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            CASE / 'ordered_events.jsonl', CASE / 'random_requests.jsonl',
            ROOT / 'autonomous_ninth/kit/autocase/+ac/DiscoveryLifecycleNwk.m',
            ROOT / 'autonomous/native_env/csr/model/csr-nwk-layer.h']}}
    write_csv('watchdog_history.csv', timers)
    write_csv('management_events.csv', management)
    write_csv('node3_route7_updates.csv', route7)
    (OUT / 'watchdog_membership_audit.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'watchdogs': len(timers), 'all_delays_60s': True, 'route7_first_s': route7[0]['time_s'], 'milestones': milestones}, indent=2))


if __name__ == '__main__': main()
