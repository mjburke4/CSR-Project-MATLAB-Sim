from pathlib import Path
import csv,json,hashlib,re
base=Path(__file__).resolve().parents[1];out=base/'matlab'
root=base.parent
summaries=[];timeline=[]
for case in ['E_check_gate','F_message_flag']:
 folder=base/'data'/case
 last=None;records=[]
 for line in (folder/'ordered_events.jsonl').open():
  r=json.loads(line);d=r['details']
  if r['node']!=1:continue
  if r['kind']=='mac_boundary' and d['ActiveNodes']!=last:
   last=d['ActiveNodes'];timeline.append(dict(case=case,order=r['observation_order'],time_s=r['time_s'],event=d['Cause'],kind='MAC_population_observed',value=last))
  if r['kind']=='protocol' and r['time_s']>=14.4:
   f=d.get('frame') or {};c=f.get('Control') or {}
   if d['event'] in ['neighbor_active','hop_control_ack','mac_enqueue','hop_control_admit']:
    record=dict(order=r['observation_order'],time_s=r['time_s'],event=d['event'],kind=f.get('Kind'),source=f.get('SourceId'),destination=f.get('DestinationId'),sequence=f.get('Sequence'),targets=f.get('DestinationIds'),control=c,details=d.get('details'))
    records.append(record)
    timeline.append(dict(case=case,order=r['observation_order'],time_s=r['time_s'],event=d['event'],kind=c.get('Type',''),value=json.dumps(f.get('DestinationIds'))))
 divergence=json.loads((folder/'first_divergence.json').read_text());usage=json.loads((folder/'random_summary.json').read_text())
 assert divergence['fields']==['active_nodes']
 assert divergence['actual']['active_nodes']==3 and divergence['expected']['active_nodes']==2
 assert divergence['actual']['low']==divergence['expected']['low']==0
 assert divergence['actual']['high']==divergence['expected']['high']==31
 summaries.append(dict(case=case,stop_s=divergence['actual_time_s'],draw_ordinal=divergence['ordinal'],logged_requests=sum(1 for _ in (folder/'random_requests.jsonl').open()),consumed=sum(x['consumed'] for x in usage['counts']),native_transmissions_checked=usage['native_transmissions_checked'],first_time_difference=usage['first_time_difference'],divergence=divergence,relevant_events=records,ordered_log_sha256=hashlib.sha256((folder/'ordered_events.jsonl').read_bytes()).hexdigest()))
for line in (root/'autonomous/native_capture/run/run.log').open():
 match=re.search(r'time_ns=(\d+) \[MAC 1\] active_nodes set to (\d+)',line)
 if match and int(match[1])<20000000000:
  timeline.append(dict(case='native',order='',time_s=int(match[1])/1e9,event='SetActiveNodesForPostTx',kind='MAC_population_published',value=int(match[2])))
with (out/'population_chronology.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(timeline[0]));w.writeheader();w.writerows(timeline)
summary=dict(schema='csr-mac-population-publication-audit-v1',cases=summaries,
 internal_nwk_count=3,native_mac_latch=2,matlab_mac_latch=3,
 cause='Native ACKed NeighborCheck updates NWK lastHeard/current count but does not publish to MAC. MATLAB eagerly publishes at every addressed member and MAC enqueue.',
 same_draw_support=True,posttx_wait_native_s=18.5,posttx_wait_premature_population_counterfactual_s=20,
 production_model_changed=False,matlab_executed_by_analysis=False,
 future_scope='Event-owned publication only; retain current NWK/application/routing-advertisement count. Independent extra ROUTING owner is under separate investigation.')
(out/'population_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({x['case']:{k:x[k] for k in ['stop_s','logged_requests','consumed','native_transmissions_checked','first_time_difference']} for x in summaries},indent=2))
