#!/usr/bin/env python3
"""Trace node-4 first mismatching TX back to queue occurrence creation.

Raw identities are joined only through accepted application admissions, never
through a packet-id equality assumption between the two implementations.
"""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
MAT = ROOT / 'node8_return2/data/S132_1200'
NAT = ROOT / 'node8_1200/native/s132_1200/run'
FIX = ROOT / 'node8_1200/native/s132_1200/fixture'
STOP = 895.115


def details(s):
    return dict(x.split('=', 1) for x in s.split(';') if '=' in x)


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n')


matmap = {}
for r in csv.DictReader((MAT / 'application_admission_trace.csv').open()):
    if r['Accepted'] == '1':
        matmap[int(r['PacketId'])] = (int(r['SourceId']), int(r['AttemptIndex']))

natmap = {}
native4 = []
native_all = []
native_context = []
native_queue_events = []
targets = {(7, 2873), (8, 3684)}
for r in csv.DictReader((NAT / 'ns3-trace.csv').open()):
    t = float(r['time_s'])
    if t > STOP:
        break
    if r['event'] == 'app_admission' and r['success'] == '1':
        d = details(r['detail'])
        natmap[(int(r['src']), int(r['sequence']))] = (int(r['src']), int(d['attempt_index']))
    if r['event'] not in ['nwk_enqueue', 'nwk_admission', 'hop_admission', 'nwk_forward', 'hop_feedback', 'hop_completion', 'hop_capacity_release']:
        continue
    key = natmap.get((int(r['src'] or 0), int(r['sequence'] or 0)))
    if key is None:
        continue
    rr = dict(time_s=t, time_ns=round(t * 1e9), event=r['event'], node=int(r['node']),
              peer=r['peer'], source=key[0], attempt=key[1], native_sequence=int(r['sequence']),
              event_index=int(r['event_index']), reason=r['reason'], details=details(r['detail']))
    if r['event'] == 'nwk_enqueue':
        native_all.append(rr)
        if r['node'] == '4':
            native4.append(rr)
    if r['node']=='4' and (r['event']=='nwk_enqueue' or (r['event']=='nwk_admission' and r['success']=='1')):
        native_queue_events.append(rr)
    if key in targets and r['event']!='nwk_admission':
        native_context.append(rr)

mat4 = []
mat_all = []
mat_context = []
mat_release_context = []
matlab_queue_events = []
for r in csv.DictReader((MAT / 'service_trace.csv').open()):
    key = matmap.get(int(r['PacketId']))
    if key is None:
        continue
    rr = dict(time_s=float(r['TimeSeconds']), time_ns=round(float(r['TimeSeconds']) * 1e9),
              event=r['Event'], node=int(r['NodeId']), peer=r['PeerId'],
              source=key[0], attempt=key[1], packet_id=int(r['PacketId']),
              hop_sequence=r['Sequence'], observation_id=int(r['ObservationId']),
              details=json.loads(r['DetailsJSON'] or '{}'))
    if r['Event'] == 'network_enqueue':
        mat_all.append(rr)
        if r['NodeId'] == '4':
            mat4.append(rr)
    if r['NodeId']=='4' and r['Event'] in ['network_enqueue','network_submit']:
        matlab_queue_events.append(rr)
    if key in targets and r['Layer'] in ['NWK', 'HOP', 'MAC'] and r['Event'] not in ['mac_state']:
        mat_context.append(rr)
    if r['NodeId'] == '4' and 894.46 < rr['time_s'] < 894.47:
        mat_release_context.append(rr)


def identity(row):
    return row['node'], row['source'], row['attempt'], row['time_ns']


def prefix_comparison(native, matlab):
    n = 0
    for x, y in zip(native, matlab):
        if identity(x) != identity(y):
            break
        n += 1
    return dict(exact_prefix_rows=n, native_count=len(native), matlab_count=len(matlab),
                first_native=native[n] if n < len(native) else None,
                first_matlab=matlab[n] if n < len(matlab) else None)


def occurrence_gaps(native, matlab):
    from collections import Counter
    a, b = Counter(map(identity, native)), Counter(map(identity, matlab))
    return dict(native_only=[dict(node=k[0], source=k[1], attempt=k[2], time_ns=k[3], count=v)
                             for k, v in (a-b).items()],
                matlab_only=[dict(node=k[0], source=k[1], attempt=k[2], time_ns=k[3], count=v)
                             for k, v in (b-a).items()])


node4 = prefix_comparison(native4, mat4)
gaps4 = occurrence_gaps(native4, mat4)
all_gaps = occurrence_gaps(native_all, mat_all)

def reconstruct(events, native):
    q=[]
    snapshots=[]
    for r in events:
        key=(r['source'],r['attempt'])
        before=q.copy()
        if r['event'] in ['nwk_enqueue','network_enqueue']:
            q.append(key)
        else:
            assert key in q, (r,q)
            q.remove(key)
        if native:
            depth=int(r['details']['queue_after'])
            assert depth==len(q), (r,len(q))
        if r['time_s']>694 and (r['source'],r['attempt']) in targets:
            snapshots.append(dict(time_s=r['time_s'],event=r['event'],source=r['source'],attempt=r['attempt'],
                                  before_depth=len(before),after_depth=len(q),before_head=before[:5],after_head=q[:5]))
    return snapshots,q

native_snapshots, native_final_queue=reconstruct(native_queue_events,True)
matlab_snapshots, matlab_final_queue=reconstruct(matlab_queue_events,False)
dump('node4_queue_snapshots.json',dict(native=native_snapshots,matlab=matlab_snapshots,
    final_native_head=native_final_queue[:5],final_matlab_head=matlab_final_queue[:5],
    final_native_depth=len(native_final_queue),final_matlab_depth=len(matlab_final_queue),
    scope='NWK waiting only; MATLAB Submitted custody owners removed at network_submit. All traced DSCP values are zero.'))
assert node4['first_native']['time_ns'] == 694821813632
assert gaps4['native_only'] == [dict(node=4,source=7,attempt=2873,time_ns=694821813632,count=1)]
assert not gaps4['matlab_only']
matches = [r for r in native_context if r['node']==4 and r['event']=='hop_admission' and r['source']==7 and r['attempt']==2873]
assert [r['details']['hop_sequence'] for r in matches] == ['211', '212']
matches_mat = [r for r in mat_context if r['node']==4 and r['event']=='hop_admit' and r['source']==7 and r['attempt']==2873]
assert [r['hop_sequence'] for r in matches_mat] == ['211']

summary = dict(
    status='confirmed_behavioral_mismatch',
    first_physical_tx_mismatch=dict(node=4,time_s=STOP,source_tx_ordinal=962,hop_sequence=212,
                                   native_application=[7,2873],matlab_application=[8,3684]),
    causal_missing_occurrence=dict(node=4,time_s=694.821813632,source=7,attempt=2873,
                                  native_sequence=1398,matlab_packet_id=297,ingress_peer=2,
                                  ingress_hop_sequence=162,native_nsdp_before=26,native_nsdp_after=27,
                                  matlab_nsdp_before=26,matlab_nsdp_after=26),
    node4_enqueue_prefix=node4,node4_occurrence_gaps=gaps4,all_node_occurrence_gaps=all_gaps,
    explanation='Both HOP implementations classify the DACK-marked retry as a first reception. '
                'Native NWK accepts another relay occurrence; MATLAB NWK returns early because '
                'the end-to-end application identity is already in Seen. This extra native '
                'occurrence reaches the head after the first copy is handed off, so the next '
                'capacity release chooses source 7 again while MATLAB chooses source 8.',
    runtime_sources=dict(simulation='node8_return/kit/node8case/+ac/TerminalSimulation.m:162',
                         seen_guard='node8_return/kit/node8case/+ac/DiscoveryMembershipNwk.m:124',
                         seen_write='node8_return/kit/node8case/+ac/DiscoveryMembershipNwk.m:153',
                         secondary_enqueue_guard='node8_return/kit/node8case/+ac/DiscoveryMembershipNwk.m:459',
                         identity_based_owner_lookup='node8_return/kit/node8case/+ac/DiscoveryMembershipNwk.m:980'),
    caveat='This establishes one cause of replay divergence, not the effect of a fix on 6000-second autonomous latency. '
           'The first physical mismatch can lag the first internal state mismatch. Do not remove final-destination '
           'application reporting deduplication merely to admit repeated relay custody occurrences.')
dump('findings.json', summary)
dump('native_target_applications.json', native_context)
dump('matlab_target_applications.json', mat_context)
dump('matlab_final_release_context.json', mat_release_context)
dump('node4_enqueues_native.json', native4)
dump('node4_enqueues_matlab.json', mat4)
files = [MAT/'service_trace.csv',MAT/'application_admission_trace.csv',MAT/'first_divergence.json',
         NAT/'ns3-trace.csv',FIX/'tx_signatures.csv']
dump('input_hashes.json',{str(p.relative_to(ROOT)):hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in files})
print(json.dumps(summary,indent=2))
