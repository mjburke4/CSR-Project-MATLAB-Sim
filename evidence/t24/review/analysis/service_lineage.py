#!/usr/bin/env python3
"""Extract rare-repeat custody service and source-grounded upstream lineage.

Service means NWK forwarding, HOP admission and held HOP capacity. tx_start
contains only the leading aggregate member and cannot measure per-owner
physical transmission attempts or airtime, so neither is computed here.
"""
import argparse
import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path
from custody_census import EXPECTED, RELEVANT, csvout, ns, sha256


def identity(owner):
    return tuple(int(owner[k]) for k in ('node', 'source', 'destination', 'app_sequence'))


def analyze(source_root, census_dir, seed):
    trace = source_root / f'evidence/tranche-20-ns3-reference/s{seed}/ns3-trace.csv.gz'
    assert sha256(trace) == EXPECTED[seed]
    owners = list(csv.DictReader((census_dir / f's{seed}-owners.csv').open()))
    repeats = [o for o in owners if int(o['identity_ordinal']) > 1]
    repeated_identities = {identity(o) for o in repeats}
    rare_owners = [o for o in owners if identity(o) in repeated_identities]
    admission_owners = defaultdict(list)
    for owner in owners:
        if owner['hop_admission_event']:
            key = tuple(int(owner[k]) for k in ('node', 'next_hop', 'hop_sequence', 'source', 'destination', 'app_sequence'))
            admission_owners[key].append(owner)
    upstream_rows = []
    for owner in repeats:
        key = tuple(int(owner[k]) for k in ('ingress_peer', 'node', 'ingress_hop_sequence', 'source', 'destination', 'app_sequence'))
        matches = [u for u in admission_owners[key] if ns(u['hop_admission_s']) <= ns(owner['enqueue_s'])]
        assert len(matches) == 1, ('ambiguous upstream admission', seed, key)
        upstream = matches[0]
        same_hop = owner['ingress_same_hop_replay'] == 'True'
        if not same_hop:
            assert int(upstream['identity_ordinal']) > 1, ('new ingress HOP not a propagated duplicate', seed, key)
        upstream_rows.append({**owner,
                              'upstream_node': upstream['node'],
                              'upstream_enqueue_event': upstream['enqueue_event'],
                              'upstream_identity_ordinal': upstream['identity_ordinal'],
                              'upstream_hop_admission_event': upstream['hop_admission_event'],
                              'upstream_hop_admission_s': upstream['hop_admission_s'],
                              'mechanism': 'same-HOP DACK-marked replay' if same_hop else 'propagated upstream repeated owner'})
    special_ids = {}
    for owner in rare_owners:
        app = identity(owner)
        for field in ('enqueue_event', 'forward_event', 'hop_admission_event',
                      'nsdp_release_event', 'completion_event', 'capacity_release_event',
                      'receiver_feedback_event', 'ingress_previous_feedback_event'):
            if owner[field]:
                special_ids.setdefault(int(owner[field]), set()).add(app)
    for owner in upstream_rows:
        app = identity(owner)
        for field in ('upstream_enqueue_event', 'upstream_hop_admission_event'):
            special_ids.setdefault(int(owner[field]), set()).add(app)
    raw_lineages = defaultdict(list)
    found_ids = set()
    with gzip.open(trace, 'rt', newline='') as handle:
        reader = csv.reader(handle)
        header = next(reader)
        ix = {key: index for index, key in enumerate(header)}
        for values in reader:
            ev = values[ix['event']]
            if ev not in RELEVANT:
                continue
            if ev == 'nwk_admission' and values[ix['success']] != '1':
                continue
            event_index = int(values[ix['event_index']])
            keys = set(special_ids.get(event_index, ()))
            if keys:
                found_ids.add(event_index)
            if all(values[ix[k]] for k in ('node', 'src', 'dst', 'sequence')):
                app = tuple(int(values[ix[k]]) for k in ('node', 'src', 'dst', 'sequence'))
                if app in repeated_identities:
                    keys.add(app)
            for app in keys:
                raw_lineages[app].append(dict(zip(header, values)))
    assert found_ids == set(special_ids), 'A declared lineage record is absent'
    csvout(census_dir / f's{seed}-repeated-owner-lineage.csv', upstream_rows)
    examples = []
    for key in sorted(repeated_identities):
        examples.append({'node': key[0], 'source': key[1], 'destination': key[2],
                         'app_sequence': key[3],
                         'owners': [o for o in rare_owners if identity(o) == key],
                         'repeat_upstream_joins': [o for o in upstream_rows if identity(o) == key],
                         'raw_events': raw_lineages[key]})
    (census_dir / f's{seed}-all-repeated-lineage.json').write_text(json.dumps(examples, indent=2) + '\n')
    census = json.loads((census_dir / f's{seed}-census.json').read_text())
    relay_owners = [o for o in owners if o['origin'] == 'relay']
    relay_flows = [f for f in census['flows'] if f['origin'] == 'relay']
    repeated_capacity = sum(f['repeated_instances']['hop_capacity_owner_seconds'] for f in relay_flows)
    relay_capacity = sum(f['all_instances']['hop_capacity_owner_seconds'] for f in relay_flows)
    all_relay_forwards = sum(f['all_instances']['forwards'] for f in relay_flows)
    repeat_forwards = sum(f['repeated_instances']['forwards'] for f in relay_flows)
    summary = {
        'seed': seed, 'all_owners': len(owners), 'all_relay_owners': len(relay_owners),
        'repeated_relay_owners': len(repeats),
        'repeated_relay_enqueue_percent': 100 * len(repeats) / len(relay_owners),
        'all_relay_forwards': all_relay_forwards, 'repeated_relay_forwards': repeat_forwards,
        'repeated_relay_forward_percent': 100 * repeat_forwards / all_relay_forwards,
        'direct_same_hop_replay_instances': sum(r['ingress_same_hop_replay'] == 'True' for r in repeats),
        'propagated_upstream_repeated_instances': sum(r['ingress_same_hop_replay'] != 'True' for r in repeats),
        'repeat_nsdp_owner_seconds': sum(f['repeated_instances']['nsdp_owner_seconds'] for f in relay_flows),
        'repeat_nwk_wait_owner_seconds': sum(f['repeated_instances']['nwk_wait_owner_seconds'] for f in relay_flows),
        'simultaneous_extra_owner_seconds': sum(f['simultaneous_extra_owners']['area_owner_seconds'] for f in relay_flows),
        'repeat_capacity_owner_seconds': repeated_capacity,
        'all_relay_capacity_owner_seconds': relay_capacity,
        'repeat_capacity_percent_of_all_relay_capacity': 100 * repeated_capacity / relay_capacity,
        'all_repeat_owners_released_by_stop': all(r['status_at_stop'] == 'released' for r in repeats),
        'matched_upstream_admissions': len(upstream_rows),
        'raw_lineage_event_bindings_checked': len(special_ids),
        'limits': ['Service measures are NWK forwards/HOP admissions and capacity owner-seconds, not physical transmissions or airtime.',
                   'Rare-copy occupancy and service are measured exposure; their removal is not a simulated counterfactual.'],
    }
    (census_dir / f's{seed}-service-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--census-dir', type=Path, required=True)
    parser.add_argument('--seeds', type=int, nargs='+', choices=[129, 130], default=[129, 130])
    args = parser.parse_args()
    summary = [analyze(args.source_root, args.census_dir, seed) for seed in args.seeds]
    (args.census_dir / 'service-summary.json').write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
