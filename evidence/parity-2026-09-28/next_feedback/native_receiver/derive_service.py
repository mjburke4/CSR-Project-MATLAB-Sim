#!/usr/bin/env python3
"""Reproducible source/time service summaries from filtered native original rows."""
import csv,json,collections,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
with (P/'filtered_native_events.csv').open() as f:events=list(csv.DictReader(f))
with (P/'receiver_decisions.csv').open() as f:receipts=list(csv.DictReader(f))
def save(n,rs):
 with (P/n).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
intervals=[('initial30',300,330)]+[('100s',i,i+100) for i in range(300,6000,100)]
out=[]
for label,start,end in intervals:
 for source in (2,7,8):
  z=collections.Counter(r['event']+':'+r['reason'] for r in events if r['node']=='2' and r['src']==str(source) and r['packet_type']=='data' and start<=float(r['time_s'])<end)
  rs=[r for r in receipts if r['source']==str(source) and start<=float(r['time_s'])<end];bs=[int(r['nsdp_before']) for r in rs]
  out.append(dict(interval=label,source=source,start_s=start,end_s=end,node2_nwk_enqueue=sum(v for k,v in z.items() if k.startswith('nwk_enqueue:')),node2_hop_admit=z['hop_admission:admitted'],node2_hop_ack=z['hop_completion:ack'],node2_hop_dack=z['hop_completion:dack'],node2_hop_failed=z['hop_completion:no_ack'],incoming_8_2_receptions=len(rs),incoming_8_2_acks=sum(r['emitted_kind']=='ack' for r in rs),incoming_8_2_dacks=sum(r['emitted_kind']=='dack' for r in rs),receiver_nsdp_before_mean=statistics.mean(bs) if bs else '',receiver_nsdp_before_max=max(bs) if bs else ''))
save('receiver_service_100s_bins.csv',out)
firsts=[]
for source in (2,7,8):
 for ev in ('nwk_enqueue','nwk_forward','hop_completion'):
  rs=[r for r in events if r['node']=='2' and r['src']==str(source) and r['event']==ev and r['packet_type']=='data']
  r=rs[0] if rs else None
  if r:firsts.append({k:r[k] for k in ('event_index','time_s','event','node','peer','src','sequence','reason','detail')})
save('first_node2_flow_events.csv',firsts)
runs=[]
for source in (7,8):
 selected=[r for r in receipts if r['source']==str(source)]
 for kind,group in __import__('itertools').groupby(selected,key=lambda r:r['emitted_kind']):
  rs=list(group)
  runs.append(dict(source=source,kind=kind,receipt_count=len(rs),start_s=rs[0]['time_s'],end_s=rs[-1]['time_s'],start_event_index=rs[0]['event_index'],end_event_index=rs[-1]['event_index'],minimum_nsdp_before=min(int(r['nsdp_before']) for r in rs),maximum_nsdp_before=max(int(r['nsdp_before']) for r in rs)))
save('feedback_decision_runs.csv',runs)
print('initial bins',json.dumps(out[:6],indent=2));print('firsts',json.dumps(firsts,indent=2));print('longestDACKruns',json.dumps(sorted([r for r in runs if r['kind']=='dack'],key=lambda r:-r['receipt_count'])[:4],indent=2))
# Cross-engine schema counterpart, computed entirely from native receipts/outcomes.
with (P/'link_8_2_application_outcomes.csv').open() as f:outcomes=list(csv.DictReader(f))
flows=[]
for source in (7,8):
 rs=[r for r in receipts if r['source']==str(source)];oo=[r for r in outcomes if r['source']==str(source)]
 ack=[r for r in rs if r['emitted_kind']=='ack'];dack=[r for r in rs if r['emitted_kind']=='dack']
 flows.append(dict(source=source,admissions=len(oo),receptions=len(rs),receiver_acks=len(ack),receiver_dacks=len(dack),ack_fraction_of_receptions=len(ack)/len(rs),no_reception_failures=sum(r['completion_kind']=='no_ack' and r['receiver_event_count']=='0' for r in oo),unfinished=sum(r['completion_kind']=='unresolved' for r in oo),first_reception_s=float(rs[0]['time_s']),first_dack_s=float(dack[0]['time_s']),first_dack_nsdp=int(dack[0]['nsdp_before']),mean_nsdp_at_arrival=statistics.mean(int(r['nsdp_before']) for r in rs),max_nsdp_at_arrival=max(int(r['nsdp_before']) for r in rs),max_ack_nsdp=max(int(r['nsdp_before']) for r in ack),min_dack_nsdp=min(int(r['nsdp_before']) for r in dack),mean_receipt_to_completion_s=statistics.mean(float(r['first_receipt_to_completion_s']) for r in oo if r['first_receipt_to_completion_s']!='')))
save('flow_summary.csv',flows)
summary=json.loads((P/'summary.json').read_text());summary['flow_summary']=flows;(P/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
