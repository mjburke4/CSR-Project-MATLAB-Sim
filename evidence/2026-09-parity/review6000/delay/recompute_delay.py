#!/usr/bin/env python3
"""Independently aggregate preserved application/hop CSVs. No simulator execution."""
import argparse,csv,json,math,statistics,hashlib
from pathlib import Path
from collections import defaultdict,Counter
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input',type=Path,required=True,help='Extracted original latency-review directory')
parser.add_argument('--output',type=Path,required=True,help='Output directory for fresh summaries')
args=parser.parse_args()
ROOT=args.input.resolve()
OUT=args.output.resolve()
OUT.mkdir(parents=True,exist_ok=True)
inputs={}
def rows(rel):
 p=ROOT/rel; inputs[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
 with p.open(newline='') as f:return list(csv.DictReader(f))
def mean(x):return math.fsum(x)/len(x) if x else None
def writecsv(name,data):
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
flow=[];node=[];validation={};hops_by={}
for eng in ['matlab','ns3']:
 vmax=0;hmax=0;count=0;hc=0;methods=Counter();neg=0
 for seed in range(128,133):
  packets=rows(f'matlab/packets-{seed}.csv' if eng=='matlab' else f'native/output/s{seed}-packets.csv')
  hops=rows(f'matlab/causal-hops-{seed}.csv' if eng=='matlab' else f'native/output/s{seed}-hops.csv')
  decomp=defaultdict(lambda: [0.,0.,0]); gh=defaultdict(list)
  for r in hops:
   pid=r['packet_id'] if eng=='matlab' else r['sequence'];key=(r['source'],pid)
   q=float(r['nwk_admission_wait_s' if eng=='matlab' else 'nwk_wait_s']);post=float(r['post_admission_to_causal_receipt_s' if eng=='matlab' else 'post_admission_s'])
   hres=float(r['residence_s' if eng=='matlab' else 'residence_to_next_node_s']);hc+=1
   hmax=max(hmax,abs(q+post-hres));neg+=q < -1e-9 or post < -1e-9
   decomp[key][0]+=q;decomp[key][1]+=post;decomp[key][2]+=1
   gh[(r['source'],r['node'])].append(r)
   methods[r.get('join_method','matlab_logical_hop_sequence')]+=1
  for (src,n),rs in gh.items():
   node.append(dict(engine=eng,seed=seed,source=int(src),node=int(n),hops=len(rs),nwk_wait_s=mean([float(r['nwk_admission_wait_s' if eng=='matlab' else 'nwk_wait_s']) for r in rs]),post_admission_s=mean([float(r['post_admission_to_causal_receipt_s' if eng=='matlab' else 'post_admission_s']) for r in rs])))
  groups=defaultdict(list)
  for p in packets:
   if (p['outcome']=='delivered' if eng=='matlab' else p['delivered']=='True'):
    pid=p['packet_id'] if eng=='matlab' else p['sequence'];key=(p['source'],pid)
    q=float(p['nwk_admission_wait_s' if eng=='matlab' else 'nwk_wait_s']);post=float(p['post_admission_to_causal_receipt_s' if eng=='matlab' else 'post_admission_s']);lat=float(p['delivered_delay_s' if eng=='matlab' else 'latency_s'])
    d=decomp[key]; assert d[2]==int(p['causal_hops' if eng=='matlab' else 'hops'])
    vmax=max(vmax,abs(q+post-lat),abs(d[0]-q),abs(d[1]-post));count+=1
    assert (p['decomposition_complete'] if eng=='matlab' else p['chain_complete'])=='True'
    p['_q'],p['_post'],p['_lat']=q,post,lat;groups[p['source']].append(p)
  for src,ps in groups.items():
   rec=dict(engine=eng,seed=seed,source=int(src),delivered=len(ps),mean_latency_s=mean([p['_lat'] for p in ps]),nwk_wait_s=mean([p['_q'] for p in ps]),post_admission_s=mean([p['_post'] for p in ps]))
   rec['nwk_fraction_of_delivered_latency']=rec['nwk_wait_s']/rec['mean_latency_s']
   for k in ['first_tx_access_wait_s','elapsed_between_first_and_last_tx_s','last_tx_to_causal_receipt_s']:
    rec[k]=mean([float(p[k]) for p in ps]) if eng=='matlab' else None
   flow.append(rec)
 validation[eng]=dict(delivered_packets=count,hop_intervals=hc,max_packet_closure_or_hop_sum_error_s=vmax,max_hop_closure_error_s=hmax,negative_intervals=neg,join_methods=methods)
writecsv('recomputed_flow_stages.csv',flow);writecsv('recomputed_node_stages.csv',node)
lookup={(r['engine'],r['seed'],r['source']):r for r in flow}
deltas=[]
for seed in range(128,133):
 for src in [2,3,4,5,7,8]:
  m=lookup.get(('matlab',seed,src));n=lookup.get(('ns3',seed,src))
  if not m or not n:continue
  gap=m['mean_latency_s']-n['mean_latency_s'];dq=m['nwk_wait_s']-n['nwk_wait_s'];dp=m['post_admission_s']-n['post_admission_s']
  deltas.append(dict(seed=seed,source=src,matlab_delivered=m['delivered'],ns3_delivered=n['delivered'],matlab_mean_s=m['mean_latency_s'],ns3_mean_s=n['mean_latency_s'],total_gap_s=gap,nwk_wait_gap_s=dq,post_admission_gap_s=dp,share_of_signed_gap_in_nwk=dq/gap if abs(gap)>1e-9 else None))
writecsv('stage_gap_by_source_seed.csv',deltas)
# Reintegrate all native capacity transitions for the four retained links.
cap=[]
for seed in [130,132]:
 groups=defaultdict(list)
 for r in rows(f'native/output/s{seed}-capacity-events.csv'):groups[(r['node'],r['peer'])].append(r)
 for (n,p),rs in groups.items():
  t=300.;out=0;threshold=0;dack=0;sums=[0.,0.,0.,0.];errs=[]
  for r in rs:
   tt=float(r['time_s']);assert 300<=tt<=6000 and tt>=t
   dt=tt-t
   for i, val in enumerate([out,dack,threshold+1,out>threshold]):sums[i]+=dt*val
   if int(r['outstanding_before'])!=out or int(r['threshold_before'])!=threshold:errs.append(r['event_index'])
   out=int(r['outstanding_after']);threshold=int(r['threshold_after']);dack=int(r['dack_held_after']);t=tt
  dt=6000-t
  for i,val in enumerate([out,dack,threshold+1,out>threshold]):sums[i]+=dt*val
  cap.append(dict(seed=seed,node=int(n),peer=int(p),transitions=len(rs),state_discontinuities=len(errs),mean_occupied=sums[0]/5700,mean_dack_held=sums[1]/5700,mean_effective_window=sums[2]/5700,capacity_full_fraction=sums[3]/5700,dack_fraction_occupied=sums[1]/sums[0]))
writecsv('native_capacity_reintegrated.csv',cap)
result=dict(validation=validation,capacity=cap,inputs_sha256=inputs,limits=['Independent aggregation of exported analyst ledgers, not independent raw trace lineage parsing.','Native per-child first/last physical TX timing unavailable for complete retry subdivision.','Differences are between own delivered populations; no common-input causal effect or paired packet comparison.'])
(OUT/'recomputation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'validation':validation,'capacity':cap,'focus_deltas':[d for d in deltas if d['source'] in [7,8] and d['seed'] in [130,132]]},indent=2))
