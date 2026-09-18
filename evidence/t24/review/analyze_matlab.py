#!/usr/bin/env python3
"""T24 read-only custody census of receipt-bound T20 MATLAB returns.

No simulation. Counts retained application identities separately from duplicate
receive callbacks (the latter are available only as per-node final counters).
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

LO, HI = 300.0, 6000.0

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def analyze(root, seed, t21):
    root = root / f's{seed}'
    receipt = json.loads((root/'receipt.json').read_text())
    assert receipt['status'] == 'completed'
    assert sha(root/'receipt.json') == (root/'receipt.sha256').read_text().strip()
    inventory = {x['path']:x for x in receipt['artifacts']}
    verified = {}
    def bound(rel):
        path = root/rel
        digest = sha(path)
        assert digest == inventory[rel]['sha256'], rel
        assert path.stat().st_size == inventory[rel]['bytes'], rel
        verified[rel] = {'sha256':digest, 'bytes':path.stat().st_size}
        return path
    def rows(rel):
        with bound(rel).open(newline='', encoding='utf-8-sig') as stream:
            yield from csv.DictReader(stream)
    summary = json.loads(bound('raw/summary.json').read_text())
    assert summary['Config']['Seed'] == seed
    assert summary['Statistics']['OmittedTraceRecords'] == 0
    apps = {}
    for r in rows('analysis/applications.csv'):
        packet = int(r['PacketId'])
        assert packet not in apps
        apps[packet] = (int(r['SourceId']), int(r['DestinationId']))
    nodes = {int(r['NodeId']):r for r in rows('raw/nwk_nodes.csv')}
    episodes, active = [], {}
    seen = Counter()
    previous = -1.0
    relevant = Counter()
    for ordinal, r in enumerate(rows('raw/protocol_trace.csv'), 1):
        now = float(r['TimeSeconds'])
        assert previous <= now <= HI
        previous = now
        event = r['Event']
        if event not in ('network_enqueue','network_submit','network_custody_release'):
            continue
        relevant[event] += 1
        node, packet = int(r['NodeId']), int(r['PacketId'])
        src, dst = apps[packet]
        key = (node, src, dst, packet)
        if event == 'network_enqueue':
            # Native multiplicity is measured elsewhere; MATLAB must reconcile
            # its own exported identity-based queue contract here.
            assert key not in active, ('overlapping owner', ordinal, key)
            seen[key] += 1
            ep = {'node':node, 'source':src, 'destination':dst, 'packet_id':packet,
                  'ordinal_for_identity':seen[key], 'enqueue':now,
                  'enqueue_row':ordinal, 'submit':None, 'release':None}
            active[key] = ep
            episodes.append(ep)
        else:
            assert key in active, (event, ordinal, key)
            ep = active[key]
            if event == 'network_submit':
                assert ep['submit'] is None
                ep['submit'] = now
            else:
                ep['release'] = now
                ep['release_reason'] = r['Reason']
                del active[key]
    by_node = Counter(k[0] for k in active)
    waiting = Counter(e['node'] for e in active.values() if e['submit'] is None)
    for node, r in nodes.items():
        assert by_node[node] == int(r['PendingCustody'])
        assert waiting[node] == int(r['WaitingForHop']) + int(r['WaitingForRoute'])
    cohorts = defaultdict(list)
    for ep in episodes:
        cohorts[ep['node'],ep['source'],ep['destination']].append(ep)
    flows = []
    for (node,src,dst), eps in sorted(cohorts.items()):
        def area(end):
            return sum(max(0,min(HI,e[end] if e[end] is not None else HI)-max(LO,e['enqueue'])) for e in eps)
        identities = {e['packet_id'] for e in eps}
        row = {'seed':seed, 'node':node, 'source':src, 'destination':dst,
               'enqueues':len(eps), 'unique_application_identities':len(identities),
               'repeat_enqueues':len(eps)-len(identities),
               'overlapping_owners':0,
               'submitted':sum(e['submit'] is not None for e in eps),
               'released':sum(e['release'] is not None for e in eps),
               'pending_at_stop':sum(e['release'] is None for e in eps),
               'waiting_at_stop':sum(e['submit'] is None for e in eps),
               'custody_application_seconds':area('release'),
               'waiting_application_seconds':area('submit'),
               'mean_custody_300_6000s':area('release')/(HI-LO)}
        assert row['enqueues'] == row['released']+row['pending_at_stop']
        assert row['enqueues'] == row['submitted']+row['waiting_at_stop']
        if node == 8 and src in (7,8):
            prior = next(x for x in t21['node8_comparison'] if x['seed']==seed and x['source']==src)
            assert abs(row['mean_custody_300_6000s']-prior['matlab_mean_custody_apps']) < 1e-8
            assert row['pending_at_stop'] == prior['matlab_pending_custody_apps_at_stop']
        flows.append(row)
    return {'seed':seed, 'status':'pass', 'receipt_sha256':sha(root/'receipt.json'),
            'runtime':receipt['identity']['Runtime'], 'verified_artifacts':verified,
            'protocol_rows':ordinal, 'custody_event_counts':dict(relevant),
            'repeat_enqueues':sum(v-1 for v in seen.values()),
            'duplicate_receive_callbacks_by_node':{str(n):int(r['DuplicateApplications']) for n,r in nodes.items()},
            'flows':flows}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--owner-root',type=Path,required=True)
    p.add_argument('--t21-diagnostic',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    prior=json.loads(a.t21_diagnostic.read_text())
    result={'schema':'csr-tranche24-matlab-custody-census-v1', 'status':'pass',
            'simulation_executed':False, 'observation_window_s':[LO,HI],
            'method':'Identity is (node, SourceId, DestinationId, PacketId). Custody ends at network_custody_release. Unreleased intervals are right-censored at 6000 s.',
            'limitation':'DuplicateApplications counts repeated receive callbacks at each node; the counter has no source, packet identity, or time attribution.',
            'script_sha256':sha(Path(__file__)),
            'results':[analyze(a.owner_root,s,prior) for s in (129,130)]}
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'matlab-census.json').write_text(json.dumps(result,indent=2)+'\n')
    rows=[r for result in result['results'] for r in result['flows']]
    with (a.output/'matlab-flows.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({'status':'pass','seeds':2,'flows':len(rows),'repeat_enqueues':sum(x['repeat_enqueues'] for x in result['results'])}))

if __name__ == '__main__':
    main()
