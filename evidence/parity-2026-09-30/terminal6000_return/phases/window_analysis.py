#!/usr/bin/env python3
import csv,json,gzip,statistics
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];P=Path(__file__).resolve().parent
T=[400,600,675,900,1200,2000,3000,4000,5000,6000]
def read(p):return list(csv.DictReader(p.open()))
def write(p,rr):
 with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
qs=[];horizons=[];intervals=[]
for mod in ['native','matlab']:
 a=read(P/f'{mod}_s132_applications.csv');h=read(P/f'{mod}_s132_custody_phases.csv');h8=[r for r in h if r['custody_node']=='8']
 for t in T:
  q=[r for r in h8 if int(r['enqueue_ns'])<=t*1e9 and (not r['hop_admit_ns'] or int(r['hop_admit_ns'])>t*1e9)]
  qs.append({'model':mod,'seed':132,'node':8,'time_s':t,'NWK_queue':len(q),'source7_relay_copies':sum(r['source']=='7' for r in q),'source8_local_copies':sum(r['source']=='8' for r in q)})
 for src in [7,8]:
  d=[r for r in a if r['source']==str(src) and r['outcome']=='delivered']
  for t in [400,675,900,1200,2000]:
   dd=[r for r in d if int(r['end_ns'])<t*1e9]
   horizons.append({'model':mod,'seed':132,'source':src,'horizon_s':t,'first_delivery_s':min(int(r['end_ns']) for r in d)/1e9,'delivered_by_horizon':len(dd)})
 for lo,hi in [(300,600),(600,900),(900,1200),(1200,2000),(2000,4000),(4000,6000)]:
  hh=[r for r in h8 if r['hop_admit_ns'] and lo*1e9<=int(r['hop_admit_ns'])<hi*1e9]
  enters=[r for r in h8 if lo*1e9<=int(r['enqueue_ns'])<hi*1e9]
  intervals.append({'model':mod,'seed':132,'node':8,'start_s':lo,'end_s':hi,'NWK_accepted_local_or_relay':len(enters),'accepted_source7_relay':sum(r['source']=='7' for r in enters),'accepted_source8_local':sum(r['source']=='8' for r in enters),'hop_admitted':len(hh),'hop_admitted_source7':sum(r['source']=='7' for r in hh),'hop_admitted_source8':sum(r['source']=='8' for r in hh),'mean_NWK_wait_of_hop_admitted_s':statistics.fmean(float(r['nwk_wait_s']) for r in hh) if hh else None})
# Check reconstructed native queue against raw per-source application-admission diagnostics.
checks=[];target=set(T)-{6000}
with gzip.open(ROOT/'recovered/native_origin/evidence/tranche-25-ns3-reference/s132/ns3-trace.csv.gz','rt',newline='') as f:
 rd=csv.reader(f);header=next(rd);ix={v:i for i,v in enumerate(header)}
 for row in rd:
  if row[ix['event']]!='app_admission' or row[ix['node']]!='8':continue
  t=float(row[ix['time_s']])
  if t not in target:continue
  d=dict(v.split('=',1) for v in row[ix['detail']].split(';') if '=' in v)
  q=next(r for r in qs if r['model']=='native' and r['time_s']==t)
  assert int(d['nwk_queue'])==q['NWK_queue'],(t,d['nwk_queue'],q)
  checks.append({'model':'native','node':8,'time_s':t,'raw_diagnostic_queue':int(d['nwk_queue']),'reconstructed_queue':q['NWK_queue']})
assert len(checks)==len(target)
# Direct new MATLAB diagnostics cover 600s and terminal cutoff.
row=next(r for r in read(ROOT/'terminal6000_return/data/s132/attempt_001/service_trace.csv') if r['NodeId']=='8' and r['Event']=='application_attempt' and float(r['TimeSeconds'])==600)
q=next(r for r in qs if r['model']=='matlab' and r['time_s']==600);assert int(row['NwkQueueSize'])==q['NWK_queue']
checks.append({'model':'matlab','node':8,'time_s':600,'raw_diagnostic_queue':int(row['NwkQueueSize']),'reconstructed_queue':q['NWK_queue']})
row=next(r for r in read(ROOT/'terminal6000_return/data/s132/attempt_001/raw/nwk_nodes.csv') if r['NodeId']=='8');q=next(r for r in qs if r['model']=='matlab' and r['time_s']==6000);assert int(row['WaitingForHop'])==q['NWK_queue']
checks.append({'model':'matlab','node':8,'time_s':6000,'raw_diagnostic_queue':int(row['WaitingForHop']),'reconstructed_queue':q['NWK_queue']})
write(P/'seed132_node8_queue_snapshots.csv',qs);write(P/'seed132_node8_interval_accounting.csv',intervals);write(P/'seed132_remote_delivery_horizons.csv',horizons)
(P/'window_analysis.json').write_text(json.dumps({'status':'pass','queue_checks':checks,'recommendation':'Extend seed132 common-input from time zero to1200s, with full node8 NWK/HOP admission/capacity/feedback tracing. This includes early queue growth and at least one completed native source7/source8 path (first at733.289/699.255s). If divergence precedes1200s stop at first consequential event; if prefix remains exact, compare natural-run ensembles rather than infer bugs from same numeric seed. Natural node8 queue difference visible by600s and strong by900s; do not assume autonomous trajectories should event-match.'},indent=2)+'\n')
print('PASS',len(checks),'queue diagnostic checks')
