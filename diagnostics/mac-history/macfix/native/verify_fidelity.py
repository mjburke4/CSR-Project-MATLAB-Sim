#!/usr/bin/env python3
"""Prove passive native capture and isolated replay preserve the source MAC history."""
from pathlib import Path
import csv,json,hashlib,subprocess,collections,itertools
R=Path(__file__).resolve().parents[2];N=R/'mac_replay/native';I=R/'mac_replay/inputs';O=R/'mac_replay/reference'
def read(p):
 with p.open() as f:return list(csv.DictReader(f))
def write(p,rows,fields):
 temp=p.with_suffix(p.suffix+'.tmp')
 with temp.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 assert read(temp)==rows,(str(p),'CSV readback mismatch')
 temp.replace(p)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canon_event(r):return {k:v for k,v in r.items() if k!='event_index'}
events={'mac_state','reservation_tick','reservation_prepare','reservation_advertise','reservation_holdoff','tx_start'}
def relevant(r,node):return r['node']==str(node) and (r['event'] in events or (r['event']=='statistic_sample' and r['statistic'].startswith('MAC.')))
original=read(N/'capture/ns3-trace.csv');tx=read(I/'tx.csv');draws=read(I/'draws.csv');report={'schema':'csr-mac-replay-native-fidelity-v1','scope':'Production MAC under captured external receiver availability, queue arrivals/cancellations, neighbor observations, active counts, and raw integer draws. Duty-cycle receiver lifecycle is outside this replay boundary.','time_tolerance_ns':0,'source_capture':json.loads((N/'capture/prefix-equality.json').read_text()),'nodes':[]};alltx=[];alldraw=[];allevents=[]
for node in [2,4,8]:
 d=O/f'node{node}';subprocess.run(['python3',str(N/'convert_capture.py'),str(N/f'replay{node}/replay.log'),str(d)],check=True)
 actual=read(d/'tx.csv');expected=[r for r in tx if r['node']==str(node)];assert actual==expected,('TX mismatch',node,next(((i,a,b) for i,(a,b) in enumerate(itertools.zip_longest(actual,expected)) if a!=b),None))
 ad=read(d/'draws.csv');ed=[r for r in draws if r['node']==str(node)];dfields=['time_ns','node','ordinal','min','max','draw'];assert [{k:r[k]for k in dfields}for r in ad]==[{k:r[k]for k in dfields}for r in ed]
 ae=[canon_event(r)for r in read(N/f'replay{node}/ns3-trace.csv') if relevant(r,node)];ee=[canon_event(r)for r in original if relevant(r,node)];assert ae==ee,('MAC trace mismatch',node,next(((i,a,b)for i,(a,b) in enumerate(itertools.zip_longest(ae,ee))if a!=b),None))
 window=[r for r in actual if 657000000000<=int(r['time_ns'])<665000000000]
 rec=dict(node=node,full_warmup_tx=len(actual),target_window_tx=len(window),raw_draws=len(ad),unused_draws=0,mac_trace_rows=len(ae),mac_event_counts=dict(collections.Counter(r['event']for r in ae)),canonical_tx_exact=True,draw_time_range_ordinal_value_exact=True,mac_trace_exact_except_global_event_index=True)
 report['nodes'].append(rec);alltx.extend(actual);alldraw.extend({k:r[k] for k in dfields}for r in ad);allevents.extend(ae)
alltx.sort(key=lambda r:(int(r['time_ns']),int(r['node'])));alldraw.sort(key=lambda r:(int(r['time_ns']),int(r['node'])));allevents.sort(key=lambda r:(float(r['time_s']),int(r['node'])))
write(O/'tx.csv',alltx,list(alltx[0]));write(O/'draws.csv',alldraw,dfields);write(O/'mac_events.csv',allevents,list(allevents[0]));
profile=dict(schema='csr-mac-history-replay-v1',nodes=[2,4,8],replay_start_ns=0,replay_stop_ns=665000000000,comparison_start_ns=657000000000,comparison_stop_ns=665000000000,slot_profile='hist-2014-next-tslot-modulo-probe',initial_active_nodes=1,initial_reported_nodes=0,initial_native_mac_state='search',external_state_initialization='captured receiver_state inputs at time zero',duty_cycle_enabled=True,receiver_lifecycle='external recorded receiver_state and sync inputs; native receiver timer functions suppressed in isolated replay',same_time_order='Inputs prequeued in ascending (time_ns,event_order); full native fidelity verified against original, including raw draw times and state/tick history',rate_key=8,rate_bps=4/.00051)
(I/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
report['reference_sha256']={p.name:digest(p) for p in [O/'tx.csv',O/'draws.csv',O/'mac_events.csv']}
report['reference_readback_counts']={p.name:len(read(p)) for p in [O/'tx.csv',O/'draws.csv',O/'mac_events.csv']}
assert report['reference_readback_counts']=={'tx.csv':1761,'draws.csv':2018,'mac_events.csv':50033}
report['input_sha256']={p.name:digest(p)for p in sorted(I.glob('*'))if p.is_file()};report['original_source_sha256']={name:digest(R/'startup131/environment/csr/model'/name)for name in ['csr-mac-core.h','csr-net-device.h','csr-phy-model.h']};report['fixture_source_sha256']={p.relative_to(N).as_posix():digest(p)for p in sorted(N.glob('*.py'))+sorted(N.glob('*.h'))+sorted(N.glob('*.cc'))};assert report['source_capture']['exact_prefix']
report['all_passed']=True
(O/'fidelity.json.tmp').write_text(json.dumps(report,indent=2)+'\n');(O/'fidelity.json.tmp').replace(O/'fidelity.json');print(json.dumps(report['reference_readback_counts'],indent=2))
