#!/usr/bin/env python3
"""Cross-engine comparison of node8 observable post-event HOP capacity."""
import collections
import csv
import json
from pathlib import Path
import observer_decoder as obs
from audit_prefix import compare

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
MAT=ROOT/'node8_return2/data/S132_1200/ordered_events.jsonl'
NATIVE=ROOT/'node8_1200/native/s132_1200/run/ns3-trace.csv'
CUTOFF=895115000000
m=[];n=[];mat_dack=[];native_dack=[]
for line in MAT.open():
    if '"kind":"protocol","node":8,' not in line: continue
    r=json.loads(line);t=obs.ns(r['time_s'])
    if t>=CUTOFF:continue
    d=r['details'];e=d['event'];v=d['details'];f=d['frame'];app=f.get('App',f)
    if 'FlowOrdinal' not in app:continue
    key=(int(app['SourceId']),int(app['FlowOrdinal']))
    if e in ('hop_admit','hop_ack','hop_dack_expired'):
        m.append((t,e,key,int(f['DestinationId']),int(f['Sequence']),
            int(v['PendingData']),int(v['PendingThreshold']),int(v['NeighborOutstanding']),int(v['NeighborThreshold'])))
    if e=='hop_dack':
        mat_dack.append((t,key,int(f['DestinationId']),int(f['Sequence']),bool(v['CapacityReleased'])))
ids={}
for r in csv.DictReader(NATIVE.open()):
    t=obs.ns(r['time_s'])
    if t>=CUTOFF:continue
    e=r['event'];d=obs.details(r['detail'])
    if e=='app_admission' and r['success']=='1':
        ids[int(r['sequence'])]=(int(r['src']),int(d['attempt_index']))
    if r['node']!='8' or r['packet_type']!='data':continue
    mapped=None
    if e=='hop_admission' and r['success']=='1':mapped='hop_admit'
    elif e=='hop_completion' and r['reason']=='ack':mapped='hop_ack'
    elif e=='hop_capacity_release' and r['reason']=='dack_expiry':mapped='hop_dack_expired'
    if mapped:
        n.append((t,mapped,ids[int(r['sequence'])],int(r['peer']),int(d['hop_sequence']),
            int(d['pending_after']),int(d['pending_limit']),int(d['outstanding_after']),int(d.get('threshold_after',d.get('threshold')))))
    if e=='hop_completion' and r['reason']=='dack':
        native_dack.append((t,ids[int(r['sequence'])],int(r['peer']),int(d['hop_sequence']),d['capacity_released']=='1'))
out={'schema':'csr-node8-prefix-capacity-audit-v1','stop_ns_exclusive':CUTOFF,
    'post_event_capacity_identity_order_values':compare([x[1:] for x in m],[x[1:] for x in n]),
    'dack_preserves_capacity_comparison':compare(mat_dack,native_dack),
    'time_delta_ns_by_event':{e:dict(collections.Counter(str(a[0]-b[0]) for a,b in zip(m,n) if a[1]==e)) for e in sorted({x[1] for x in m})},
    'limits':['Compares observed post-admit, post-ACK, and DACK expiry pending count, limit, neighbor outstanding and threshold. Failed-owner releases have no equivalent MATLAB snapshot here.',
              'Nanosecond rounding is for reporting times; no simulator comparator tolerance is changed.'],
    'inputs_sha256':{str(p.relative_to(ROOT)):obs.sha(p)for p in (MAT,NATIVE)}}
out['status']='pass' if out['post_event_capacity_identity_order_values']['equal'] and out['dack_preserves_capacity_comparison']['equal'] else 'mismatch'
(OUT/'capacity_audit.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
