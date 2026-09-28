#!/usr/bin/env python3
"""Read-only reconstruction from existing seed-132 captures; no simulation."""
import csv,gzip,json,hashlib
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
MAT=ROOT/'return6000/data/s132/attempt_001/raw'
NAT=ROOT/'next_feedback/short_kit/two_case_next/schema_review/native_s132_prefix_0_330.csv.gz'
INPUT=ROOT/'next_feedback/prior_coverage/out_short_20260924_083651/replays/source5_mac/staging/inputs'
def read(p):
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return list(csv.DictReader(f))
def prefix(p,tname,stop=330):
 out=[]
 with p.open() as f:
  for r in csv.DictReader(f):
   if float(r[tname])>stop:break
   out.append(r)
 return out
def write(name,rows):
 if not rows:return
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
nt=read(NAT); mt=prefix(MAT/'protocol_trace.csv','TimeSeconds'); phy=prefix(MAT/'phy_trace.csv','TimeSeconds'); ins=read(INPUT/'inputs.csv');draws=read(INPUT/'draws.csv')
first=[]; contexts=[]
for node in ('1','4','2','8','7'):
 ns=[r for r in nt if r['node']==node and r['event']=='mac_state']
 ms=[r for r in mt if r['NodeId']==node and r['Event']=='mac_state']
 i=next(i for i,(n,m) in enumerate(zip(ns,ms)) if abs(float(n['time_s'])-float(m['TimeSeconds']))>1e-9)
 tr=next((r for r in phy if r['NodeId']==node and r['Event']=='phy_track' and abs(float(r['TimeSeconds'])-float(ms[i]['TimeSeconds']))<1e-9),None)
 first.append(dict(node=int(node),matched_transition_times=i,matlab_next_transition_s=float(ms[i]['TimeSeconds']),native_next_transition_s=float(ns[i]['time_s']),native_next_state=ns[i]['detail'],matlab_state_evidence=('Tx: paired mac_transmit' if node=='1' else 'Track: paired phy_track'),matlab_tracked_source=tr['SourceId'] if tr else '',matlab_tracked_destination=tr['DestinationId'] if tr else '',matlab_phy_observation_id=tr['PacketId'] if tr else '',native_first_track_s=next((r['time_s'] for r in ns if r['detail']=='track'),'')))
 for model,rs in [('matlab',ms[max(i-3,0):i+3]),('native',ns[max(i-3,0):i+3])]:
  for r in rs:contexts.append(dict(model=model,node=node,time_s=r.get('TimeSeconds',r.get('time_s')),state=r.get('detail','not exported'),frame_kind=r.get('FrameKind',''),peer=r.get('PeerId','')))
write('first_state_timing_divergence.csv',first);write('first_state_timing_context.csv',contexts)
# Before300 the last MAC state after a TX or tracked receipt is inferred Search
# in MATLAB from paired PHY completion + production state bridge; native state direct.
rows=[]
for node,peer in [('2','4'),('4','5'),('7','8'),('8','2')]:
 mtx=[r for r in mt if r['NodeId']==node and r['Event']=='mac_transmit' and float(r['TimeSeconds'])<300][-1]
 ntx=[r for r in nt if r['node']==node and r['event']=='tx_start' and float(r['time_s'])<300][-1]
 ms=[r for r in mt if r['NodeId']==node and r['Event']=='mac_state' and float(r['TimeSeconds'])<300][-1]
 ns=[r for r in nt if r['node']==node and r['event']=='mac_state' and float(r['time_s'])<300][-1]
 mh=[r for r in phy if r['NodeId']==node and r['SourceId']==peer and r['Event']=='phy_signal_end' and r['Success']=='1' and float(r['TimeSeconds'])<300][-1]
 nh=[r for r in ins if r['node']==node and r['peer']==peer and r['kind']=='received' and int(r['time_ns'])<300e9][-1]
 ma=[r for r in mt if r['NodeId']==node and r['Event']=='hop_sent' and r['FrameKind']=='DATA' and float(r['TimeSeconds'])>=300][0]
 na=[r for r in nt if r['node']==node and r['event']=='tx_start' and r['packet_type']=='data' and float(r['time_s'])>=300][0]
 rows.append(dict(node=int(node),next_peer=int(peer),matlab_last_tx_s=float(mtx['TimeSeconds']),matlab_last_state_time_s=float(ms['TimeSeconds']),matlab_state_300_inferred=('Idle' if node=='2' else 'Search'),native_last_tx_s=float(ntx['time_s']),native_last_tx_type=ntx['packet_type'],native_last_state_time_s=float(ns['time_s']),native_state_300_direct=ns['detail'],matlab_last_heard_peer_s=float(mh['TimeSeconds']),native_last_heard_peer_s=float(nh['value']),matlab_first_data_tx_s=float(ma['TimeSeconds']),native_first_data_tx_s=float(na['time_s']),native_first_data_preamble=na['detail']))
write('receiver_context_at_300.csv',rows)
# Capture actual first native receiver inputs and slot, alongside timeline-derived MATLAB slot.
node1draw=next(r for r in draws if r['node']=='1')
startup={
 'native_first_draw':node1draw,
 'common_initial_rts_s':10.01,'common_holdoff_expiry_s':10.31,
 'first_eligible_tick_s':10.322,'slot_period_s':0.013,
 'matlab_first_tx_s':10.452,'native_first_tx_s':10.465,
 'matlab_first_slot_inferred':10,
 'matlab_slot_reason':'11 eligible countdown ticks before first TX, starting from10 and ending at-1; no RF before first TX and no pre-existing neighbors. Raw draw not exported.',
 'not_claimed':'This initial split alone is not proven to explain later network latency.'}
checks=[r for r in mt if r['NodeId']=='1' and float(r['TimeSeconds'])<10.466 and r['Event'] in ('mac_prepare','mac_holdoff','mac_transmit')]
startup['matlab_timeline_rows']=checks
write('matlab_initial_gateway_timeline.csv',checks)
windows=[('4',19.74,19.88),('2',41.0,42.10),('8',56.29,57.46),('7',61.23,61.40)]
pairs=[]
for node,start,end in windows:
 for r in phy:
  if r['NodeId']==node and start<=float(r['TimeSeconds'])<=end:
   pairs.append(r)
write('matlab_first_track_phy_context.csv',pairs)
summary={'scope':'Existing full MATLAB seed132 capture plus native 0–330 reference; no simulations or production edits','startup':startup,'first_state_timing_divergence':first,'receiver_context_at_300':rows,'matlab_state_warning':'mac_state labels not exported. At300 state is reconstructed from terminal transition cause; first Track labels are confirmed by phy_track rows. Same timestamp prefix is not a full hidden-state parity proof.'}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
manifest=[]
for p in [NAT,INPUT/'inputs.csv',INPUT/'draws.csv',MAT/'protocol_trace.csv',MAT/'phy_trace.csv',ROOT/'return6000/kit/csr6000/model/+csr/+mac/Layer.m',ROOT/'return6000/kit/csr6000/model/+csr/+phy/SignalEngine.m',ROOT/'autonomous/native_env/csr/model/csr-net-device.h',ROOT/'autonomous/native_env/csr/model/csr-mac-core.h']:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 manifest.append(dict(path=str(p.relative_to(ROOT)),sha256=h.hexdigest(),bytes=p.stat().st_size))
write('input_manifest.csv',manifest)
print(json.dumps(summary,indent=2))
