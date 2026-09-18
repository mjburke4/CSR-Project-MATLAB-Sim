#!/usr/bin/env python3
"""T24 read-only native custody census; no simulator behavior is modified.

Time is rounded from ns-3 CSV floating-point formatting to integer nanoseconds.
The largest timestamp is below 6000 seconds, so binary float precision is finer
than a nanosecond; this removes decimal-printing noise from integer ns-3 times.
The six accepted campus flows have DSCP zero. For each identical app, waiting
owners therefore leave NWK in enqueue order. HOP lifetimes use receiver neighbor
and HOP sequence, additionally verifying source/destination/application identity.
NSDP releases have no app sequence: each synchronous, same-time flow release is
paired with its following HOP completion. DACK ownership and capacity endpoints
remain distinct. Every area uses the observation window [300,6000] seconds.
"""
import argparse
import csv
import gzip
import hashlib
import json
import statistics
from collections import Counter, defaultdict, deque
from pathlib import Path

START = 300_000_000_000
STOP = 6_000_000_000_000
SPAN = STOP - START
EXPECTED = {
    129: 'aa4ae4e40309ef956d5e89d20040828c3fab47062747eaa51a637506764c2643',
    130: '404b719dcb8c2762cb60a2f60eb2489b0b5c41f198baa25b3fe93630c1b07930',
}
RELEVANT = {'nwk_enqueue', 'nwk_forward', 'nwk_admission',
            'nwk_nsdp_release', 'hop_admission', 'hop_completion',
            'hop_capacity_release', 'hop_feedback', 'nwk_delivery', 'app_send'}


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def detail(value):
    return dict(item.split('=', 1) for item in value.split(';') if '=' in item)


def ns(value):
    return round(float(value) * 1_000_000_000)


def sec(value):
    return None if value is None else value / 1_000_000_000


def area(start, end):
    return max(0, min(end, STOP) - max(start, START))


def stats(values):
    values = sorted(values)
    return {'count': len(values), 'mean': sum(values) / len(values) if values else None,
            'median': statistics.median(values) if values else None,
            'max': values[-1] if values else None}


def csvout(path, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


class State:
    def __init__(self):
        self.value = 0
        self.last = 0
        self.area_ns = 0
        self.peak = 0

    def move(self, t, value):
        assert t >= self.last and value >= 0
        self.area_ns += area(self.last, t) * self.value
        self.last = t
        self.value = value
        self.peak = max(self.peak, value)

    def finish(self):
        self.move(STOP, self.value)
        return {'at_stop': self.value, 'peak': self.peak,
                'area_owner_seconds': sec(self.area_ns),
                'mean_300_6000': self.area_ns / SPAN}


def analyze(source_root, seed, out):
    folder = source_root / f'evidence/tranche-20-ns3-reference/s{seed}'
    trace = folder / 'ns3-trace.csv.gz'
    digest = sha256(trace)
    assert digest == EXPECTED[seed], 'Input differs from accepted native trace'
    scenario = list(csv.DictReader((folder / 'scenario.csv').open()))
    dscp_values = [row['flow_dscp'] for row in scenario if row.get('flow_dscp')]
    assert dscp_values and all(value == '0' for value in dscp_values), dscp_values
    provenance = json.loads((folder / 'ns3-aggregates.provenance.json').read_text())

    owners = []
    owner_by_app = defaultdict(list)
    waiting = defaultdict(deque)
    live = Counter()
    forward_pending = defaultdict(deque)
    release_pending = defaultdict(deque)
    admitted = {}
    holds = {}
    feedback_enqueues = defaultdict(deque)
    previous_feedback = {}
    nsdp = defaultdict(State)
    nwk_queue = Counter()
    hop_capacity = Counter()
    peer_capacity = Counter()
    app_multiplicity = defaultdict(State)
    nsdp_redundancy = defaultdict(State)
    flow_owners = defaultdict(list)
    event_counts = Counter()
    check_counts = Counter()
    delivery_events = Counter()
    first_delivery = {}
    sent = {}
    captured = []
    raw_hash = hashlib.sha256()
    raw_bytes = 0
    previous_index = None
    previous_time = 0
    event_total = 0

    def check(condition, name, context):
        check_counts[name] += 1
        if not condition:
            raise AssertionError(f'{name}: {context}')

    def flow_of(row):
        return (int(row['node']), int(row['src']), int(row['dst']))

    def app_of(row):
        return (*flow_of(row), int(row['sequence']))

    def hop_of(row, d):
        return (int(row['node']), int(row['peer']), int(d['hop_sequence']))

    def capture(row):
        if row['node'] == '8' and row['src'] in ('7', '8'):
            captured.append(row)

    with gzip.open(trace, 'rb') as handle:
        def lines():
            nonlocal raw_bytes
            for raw in handle:
                raw_hash.update(raw)
                raw_bytes += len(raw)
                yield raw.decode('utf-8-sig')
        reader = csv.reader(lines())
        header = next(reader)
        column = {key: index for index, key in enumerate(header)}
        for values in reader:
            event_total += 1
            ev = values[column['event']]
            event_counts[ev] += 1
            index = int(values[column['event_index']])
            timestamp = ns(values[column['time_s']])
            check(previous_index is None or index == previous_index + 1,
                  'contiguous_event_index', [previous_index, index])
            check(previous_time <= timestamp < STOP, 'ordered_pre_stop_time', index)
            previous_index, previous_time = index, timestamp
            if ev not in RELEVANT:
                continue
            if ev == 'nwk_admission' and values[column['success']] != '1':
                continue
            row = dict(zip(header, values))
            d = detail(row['detail'])
            t = timestamp
            if ev == 'app_send':
                identity = tuple(int(row[k]) for k in ('src', 'dst', 'sequence'))
                check(identity not in sent, 'unique_generated_app', index)
                sent[identity] = t
                continue
            if ev == 'nwk_delivery':
                identity = tuple(int(row[k]) for k in ('src', 'dst', 'sequence'))
                check(identity in sent, 'delivered_app_generated', index)
                delivery_events[identity] += 1
                first_delivery.setdefault(identity, (index, t))
                continue
            capture(row)
            flow = flow_of(row)
            node = flow[0]
            if ev == 'nwk_nsdp_release':
                check(int(d['count_before']) == nsdp[flow].value,
                      'nsdp_release_before_snapshot', index)
                check(int(d['count_after']) == nsdp[flow].value - 1,
                      'nsdp_release_after_snapshot', index)
                check(int(d['nwk_queue']) == nwk_queue[node],
                      'nsdp_release_queue_snapshot', index)
                nsdp[flow].move(t, nsdp[flow].value - 1)
                release_pending[flow].append((index, t))
                continue
            app = app_of(row)
            if ev == 'nwk_enqueue':
                check(int(d['nsdp_count']) == nsdp[flow].value + 1,
                      'enqueue_nsdp_snapshot', index)
                check(int(d['queue_after']) == nwk_queue[node] + 1,
                      'enqueue_queue_snapshot', index)
                nsdp[flow].move(t, nsdp[flow].value + 1)
                nwk_queue[node] += 1
                multiplicity = app_multiplicity[app]
                redundancy = nsdp_redundancy[flow]
                redundancy.move(t, redundancy.value + int(live[app] > 0))
                multiplicity.move(t, live[app] + 1)
                owner = {'seed': seed, 'node': node, 'source': flow[1],
                         'destination': flow[2], 'app_sequence': app[3],
                         'origin': row['reason'], 'ingress_peer': row['peer'],
                         'enqueue_event': index, 'enqueue_ns': t,
                         'identity_ordinal': len(owner_by_app[app]) + 1,
                         'same_app_nsdp_owners_before_enqueue': live[app],
                         'same_app_waiting_before_enqueue': len(waiting[app]),
                         'forward_event': None, 'forward_ns': None,
                         'hop_admission_event': None, 'hop_admission_ns': None,
                         'next_hop': None, 'hop_sequence': None,
                         'nsdp_release_event': None, 'completion_event': None,
                         'completion_ns': None, 'completion_reason': None,
                         'completion_resend_count': None,
                         'capacity_release_event': None, 'capacity_release_ns': None,
                         'receiver_feedback_event': None, 'receiver_feedback_reason': None,
                         'ingress_hop_sequence': None, 'ingress_previous_feedback_event': None,
                         'ingress_previous_feedback_reason': None,
                         'ingress_same_hop_replay': None}
                owners.append(owner)
                owner_by_app[app].append(owner)
                waiting[app].append(owner)
                flow_owners[flow].append(owner)
                live[app] += 1
                if row['reason'] == 'relay':
                    feedback_enqueues[(app, int(row['peer']), t)].append(owner)
            elif ev == 'nwk_admission':
                check(int(d['queue_before']) == nwk_queue[node],
                      'admission_queue_before_snapshot', index)
                check(int(d['queue_after']) == nwk_queue[node] - 1,
                      'admission_queue_after_snapshot', index)
                check(int(d['nsdp_count']) == nsdp[flow].value,
                      'admission_nsdp_snapshot', index)
                check(bool(waiting[app]), 'admission_has_waiting_app', index)
            elif ev == 'nwk_forward':
                check(bool(waiting[app]), 'forward_has_waiting_owner', index)
                owner = waiting[app].popleft()
                owner.update(forward_event=index, forward_ns=t)
                nwk_queue[node] -= 1
                forward_pending[(app, int(row['next_hop']), t)].append(owner)
            elif ev == 'hop_admission':
                pending_key = (app, int(row['peer']), t)
                check(bool(forward_pending[pending_key]), 'hop_has_same_time_forward', index)
                owner = forward_pending[pending_key].popleft()
                hop = hop_of(row, d)
                check(hop not in admitted and hop not in holds, 'active_hop_key_unique', index)
                check(int(d['resend_tracked']) == 1 and int(d['resend_overflow']) == 0,
                      'admission_reliability_tracked', index)
                check(int(d['pending_before']) == hop_capacity[node],
                      'hop_admission_pending_before', index)
                check(int(d['pending_after']) == hop_capacity[node] + 1,
                      'hop_admission_pending_after', index)
                peer_key = hop[:2]
                check(int(d['outstanding_before']) == peer_capacity[peer_key],
                      'hop_admission_outstanding_before', index)
                check(int(d['outstanding_after']) == peer_capacity[peer_key] + 1,
                      'hop_admission_outstanding_after', index)
                owner.update(hop_admission_event=index, hop_admission_ns=t,
                             next_hop=hop[1], hop_sequence=hop[2])
                admitted[hop] = owner
                hop_capacity[node] += 1
                peer_capacity[peer_key] += 1
            elif ev == 'hop_completion':
                hop = hop_of(row, d)
                check(hop in admitted, 'completion_has_active_admission', index)
                owner = admitted.pop(hop)
                check((owner['node'], owner['source'], owner['destination'],
                       owner['app_sequence']) == app, 'completion_app_matches_hop', index)
                check(int(d['nsdp_released']) == 1, 'completion_releases_nsdp', index)
                check(bool(release_pending[flow]), 'completion_has_nsdp_release', index)
                release_index, release_time = release_pending[flow].popleft()
                check(release_time == t and release_index < index,
                      'completion_same_time_preceding_release', index)
                owner.update(nsdp_release_event=release_index,
                             completion_event=index, completion_ns=t,
                             completion_reason=row['reason'],
                             completion_resend_count=int(d['resend_count']))
                redundancy = nsdp_redundancy[flow]
                redundancy.move(t, redundancy.value - int(live[app] > 1))
                live[app] -= 1
                app_multiplicity[app].move(t, live[app])
                release_capacity = int(d['capacity_released'])
                check(release_capacity == int(row['reason'] != 'dack'),
                      'dack_capacity_separate', index)
                check(int(d['pending_before']) == hop_capacity[node],
                      'completion_pending_before', index)
                check(int(d['pending_after']) == hop_capacity[node] - release_capacity,
                      'completion_pending_after', index)
                check(int(d['outstanding_before']) == peer_capacity[hop[:2]],
                      'completion_outstanding_before', index)
                check(int(d['outstanding_after']) == peer_capacity[hop[:2]] - release_capacity,
                      'completion_outstanding_after', index)
                hop_capacity[node] -= release_capacity
                peer_capacity[hop[:2]] -= release_capacity
                if release_capacity:
                    owner.update(capacity_release_event=index, capacity_release_ns=t)
                else:
                    holds[hop] = owner
            elif ev == 'hop_capacity_release':
                hop = hop_of(row, d)
                check(hop in holds, 'capacity_release_has_dack_hold', index)
                owner = holds.pop(hop)
                check((owner['node'], owner['source'], owner['destination'],
                       owner['app_sequence']) == app, 'capacity_release_app_matches_hop', index)
                check(int(d['nsdp_released']) == 0 and int(d['capacity_released']) == 1,
                      'dack_expiry_capacity_only', index)
                check(int(d['pending_before']) == hop_capacity[node],
                      'capacity_release_pending_before', index)
                check(int(d['pending_after']) == hop_capacity[node] - 1,
                      'capacity_release_pending_after', index)
                check(int(d['outstanding_before']) == peer_capacity[hop[:2]],
                      'capacity_release_outstanding_before', index)
                check(int(d['outstanding_after']) == peer_capacity[hop[:2]] - 1,
                      'capacity_release_outstanding_after', index)
                hop_capacity[node] -= 1
                peer_capacity[hop[:2]] -= 1
                owner.update(capacity_release_event=index, capacity_release_ns=t)
            elif ev == 'hop_feedback':
                # Receiver feedback follows the synchronous relay enqueue.
                feedback_key = (app, int(row['peer']), t)
                hop_key = (node, int(row['peer']), int(d['hop_sequence']))
                prior = previous_feedback.get(hop_key)
                if feedback_enqueues[feedback_key]:
                    owner = feedback_enqueues[feedback_key].popleft()
                    check(int(d['first_reception']) == 1,
                          'enqueue_feedback_first_reception', index)
                    check(int(d['nsdp_state_valid']) == 1,
                          'enqueue_feedback_nsdp_valid', index)
                    check(int(d['nsdp_count_after']) == int(d['nsdp_count_before']) + 1,
                          'enqueue_feedback_nsdp_increments', index)
                    same_hop = prior is not None and prior['app'] == app
                    owner.update(receiver_feedback_event=index,
                                 receiver_feedback_reason=row['reason'],
                                 ingress_hop_sequence=hop_key[2],
                                 ingress_previous_feedback_event=prior['event'] if same_hop else None,
                                 ingress_previous_feedback_reason=prior['reason'] if same_hop else None,
                                 ingress_same_hop_replay=bool(same_hop))
                    if same_hop:
                        check(prior['reason'] == 'dack', 'reenqueue_prior_feedback_dack', index)
                previous_feedback[hop_key] = {'app': app, 'reason': row['reason'], 'event': index}

    check(raw_hash.hexdigest() == provenance['input']['sha256'], 'raw_trace_sha256', seed)
    check(raw_bytes == provenance['input']['size_bytes'], 'raw_trace_bytes', seed)
    check(not any(forward_pending.values()), 'all_forwards_admitted', seed)
    check(not any(release_pending.values()), 'all_nsdp_releases_completed', seed)
    check(not any(feedback_enqueues.values()), 'all_relay_enqueues_feedback_joined', seed)
    for flow, state in nsdp.items():
        check(state.value == sum(live[key] for key in live if key[:3] == flow),
              'nsdp_final_identity_count', flow)
    for node, count in nwk_queue.items():
        check(count == sum(len(q) for key, q in waiting.items() if key[0] == node),
              'queue_final_waiting_count', node)
    for node, count in hop_capacity.items():
        check(count == sum(key[0] == node for key in admitted) + sum(key[0] == node for key in holds),
              'capacity_final_active_plus_hold', node)

    owner_rows = []
    for owner in owners:
        row = dict(owner)
        for key in list(row):
            if key.endswith('_ns'):
                row[key[:-3] + '_s'] = sec(row.pop(key))
        app = (owner['source'], owner['destination'], owner['app_sequence'])
        row['app_unique_delivered_by_stop'] = app in first_delivery
        row['app_destination_delivery_events'] = delivery_events[app]
        row['app_first_delivery_event'] = first_delivery[app][0] if app in first_delivery else None
        row['app_first_delivery_s'] = sec(first_delivery[app][1]) if app in first_delivery else None
        row['status_at_stop'] = ('waiting' if owner['forward_ns'] is None else
                                 'active_hop' if owner['completion_ns'] is None else
                                 'dack_hold' if owner['capacity_release_ns'] is None else 'released')
        owner_rows.append(row)
    csvout(out / f's{seed}-owners.csv', owner_rows)
    with gzip.open(out / f's{seed}-node8-events.csv.gz', 'wt', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(captured)

    flow_results = []
    for flow, members in sorted(flow_owners.items()):
        n, source, destination = flow
        repeated = [o for o in members if o['identity_ordinal'] > 1]
        keys = [key for key in owner_by_app if key[:3] == flow]
        multiplicity = [app_multiplicity[key].finish() for key in keys]
        owner_area = sum(area(o['enqueue_ns'], o['completion_ns'] or STOP) for o in members)
        snapshot = nsdp[flow].finish()
        check(owner_area == nsdp[flow].area_ns, 'nsdp_lifetime_area_equals_snapshot_area', flow)
        def subgroup(group):
            forwarded = [o for o in group if o['forward_ns'] is not None]
            completed = [o for o in group if o['completion_ns'] is not None]
            capacities = [o for o in group if o['hop_admission_ns'] is not None]
            completed_cap = [o for o in capacities if o['capacity_release_ns'] is not None]
            return {
                'enqueues': len(group), 'forwards': len(forwarded),
                'completion_counts': dict(Counter(o['completion_reason'] for o in completed)),
                'waiting_at_stop': sum(o['forward_ns'] is None for o in group),
                'active_hop_at_stop': sum(o['forward_ns'] is not None and o['completion_ns'] is None for o in group),
                'dack_hold_at_stop': sum(o['completion_ns'] is not None and o['capacity_release_ns'] is None for o in group),
                'nsdp_owner_seconds': sec(sum(area(o['enqueue_ns'], o['completion_ns'] or STOP) for o in group)),
                'nwk_wait_owner_seconds': sec(sum(area(o['enqueue_ns'], o['forward_ns'] or STOP) for o in group)),
                'hop_capacity_owner_seconds': sec(sum(area(o['hop_admission_ns'], o['capacity_release_ns'] or STOP) for o in capacities)),
                'dack_hold_owner_seconds': sec(sum(area(o['completion_ns'], o['capacity_release_ns'] or STOP) for o in completed if o['completion_reason'] == 'dack')),
                'completed_nwk_wait_s': stats([sec(o['forward_ns'] - o['enqueue_ns']) for o in forwarded]),
                'completed_nsdp_lifetime_s': stats([sec(o['completion_ns'] - o['enqueue_ns']) for o in completed]),
                'completed_hop_capacity_s': stats([sec(o['capacity_release_ns'] - o['hop_admission_ns']) for o in completed_cap]),
                'receiver_feedback_counts': dict(Counter(o['receiver_feedback_reason'] for o in group if o['origin'] == 'relay')),
                'ingress_same_hop_replays': sum(o['ingress_same_hop_replay'] is True for o in group),
            }
        flow_result = {
            'seed': seed, 'node': n, 'source': source, 'destination': destination,
            'origin': 'local' if n == source else 'relay',
            'distinct_application_identities': len(keys),
            'identities_enqueued_more_than_once': sum(len(owner_by_app[key]) > 1 for key in keys),
            'repeat_enqueue_count': len(repeated),
            'repeat_while_same_app_nsdp_owned': sum(o['same_app_nsdp_owners_before_enqueue'] > 0 for o in repeated),
            'repeat_after_same_app_nsdp_released': sum(o['same_app_nsdp_owners_before_enqueue'] == 0 for o in repeated),
            'maximum_simultaneous_owners_of_one_identity': max((x['peak'] for x in multiplicity), default=0),
            'maximum_enqueues_of_one_identity': max((len(owner_by_app[key]) for key in keys), default=0),
            'nsdp': snapshot,
            'simultaneous_extra_owners': nsdp_redundancy[flow].finish(),
            'all_instances': subgroup(members),
            'first_instances': subgroup([o for o in members if o['identity_ordinal'] == 1]),
            'repeated_instances': subgroup(repeated),
            'unique_apps_delivered_by_stop': sum(key[1:] in first_delivery for key in keys),
        }
        check(flow_result['all_instances']['enqueues'] ==
              flow_result['all_instances']['forwards'] + flow_result['all_instances']['waiting_at_stop'],
              'enqueue_forward_waiting_conservation', flow)
        check(flow_result['all_instances']['forwards'] ==
              sum(flow_result['all_instances']['completion_counts'].values()) +
              flow_result['all_instances']['active_hop_at_stop'],
              'forward_completion_active_conservation', flow)
        flow_results.append(flow_result)

    # Complete raw event lineage for repeated node8/source7 application identities.
    examples = []
    wanted = sorted(key for key in owner_by_app if key[:3] == (8, 7, 1) and len(owner_by_app[key]) > 1)
    for app in wanted:
        examples.append({'node': app[0], 'source': app[1], 'destination': app[2],
                         'app_sequence': app[3],
                         'owners': [row for row in owner_rows if (row['node'], row['source'], row['destination'], row['app_sequence']) == app],
                         'events': [row for row in captured if row['node'] == str(app[0]) and row['src'] == str(app[1]) and row['dst'] == str(app[2]) and row['sequence'] == str(app[3])]})
    (out / f's{seed}-repeated-node8-source7-lineage.json').write_text(json.dumps(examples, indent=2) + '\n')
    result = {
        'schema': 'csr-tranche24-native-custody-census-v1', 'seed': seed,
        'duration_s': 6000, 'occupancy_window_s': [300, 6000],
        'input': {'path': str(trace), 'gzip_sha256': digest,
                  'raw_sha256': raw_hash.hexdigest(), 'raw_bytes': raw_bytes,
                  'rows': event_total, 'last_event_s': sec(previous_time),
                  'scenario_sha256': sha256(folder / 'scenario.csv'),
                  'all_flow_dscp': sorted(set(dscp_values))},
        'event_counts': dict(event_counts), 'flows': flow_results,
        'verification': {'passed': True, 'checked_assertion_counts': dict(check_counts),
                         'total_assertions': sum(check_counts.values())},
        'definitions': {
            'application_identity': '(source,destination,application sequence); scoped by node for custody',
            'repeat_enqueue': 'Every enqueue after the first for one node/application identity, including serial reacquisition',
            'simultaneous_extra_owner_area': 'Integral of max(active NSDP owners per identity - 1, 0), summed over identities',
            'repeat_instance_area': 'Lifetime area of later enqueued instances; can persist after the first instance has completed',
            'ownership_endpoint': 'ACK, DACK or no-ACK HOP completion releases NSDP',
            'capacity_endpoint': 'ACK/no-ACK completion, or later DACK capacity-release expiry',
            'pending': 'Right-censored at 6000 seconds; never called a drop',
        },
        'limits': [
            'Observational census does not quantify a counterfactual delivery change from deduplication.',
            'A final unique application delivery cannot be assigned to one duplicate custody instance without additional downstream lineage.',
            'Historical seed128 lacks detailed native custody events and is not included.',
            'The source8 NSDP quota is separate from source7; they share downstream queue service and HOP capacity.',
            'No fresh MATLAB, native or OPNET simulation was executed.',
        ],
    }
    (out / f's{seed}-census.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'seed': seed, 'owners': len(owners), 'relay_repeat_count':
                      sum(o['identity_ordinal'] > 1 and o['origin'] == 'relay' for o in owners),
                      'node8_source7': next(flow for flow in flow_results if (flow['node'], flow['source']) == (8, 7)),
                      'assertions': sum(check_counts.values())}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seeds', type=int, nargs='+', choices=[129, 130], default=[129, 130])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = [analyze(args.source_root.resolve(), seed, args.output.resolve()) for seed in args.seeds]
    rows = []
    for result in results:
        for flow in result['flows']:
            row = {k: v for k, v in flow.items() if not isinstance(v, dict)}
            for subgroup_name in ('all_instances', 'first_instances', 'repeated_instances'):
                for key, value in flow[subgroup_name].items():
                    if not isinstance(value, dict):
                        row[subgroup_name + '_' + key] = value
            row['mean_nsdp_owners'] = flow['nsdp']['mean_300_6000']
            row['simultaneous_extra_owner_seconds'] = flow['simultaneous_extra_owners']['area_owner_seconds']
            rows.append(row)
    csvout(args.output / 'flow-census.csv', rows)


if __name__ == '__main__':
    main()
