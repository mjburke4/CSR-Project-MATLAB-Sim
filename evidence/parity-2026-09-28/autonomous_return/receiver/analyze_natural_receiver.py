#!/usr/bin/env python3
"""Offline direct-observation audit of accepted natural seed132 return."""
import csv,json,hashlib
from pathlib import Path
from collections import defaultdict,Counter
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
A=ROOT/'autonomous_return/data/A_natural'; N=ROOT/'autonomous/native_capture/fixture'
def dump(name,value): (OUT/name).write_text(json.dumps(value,indent=2)+'\n')
def write(name,rows):
 if not rows:return
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def readcsv(path):
 with path.open() as f:return list(csv.DictReader(f))
random=[]
with (A/'random_requests.jsonl').open() as f:
 for line in f:random.append(json.loads(line))
native=readcsv(N/'random_draws.csv')
first=[]
for node in (1,2,3,4,5,7,8):
 m=next(r for r in random if r['purpose']=='mac_slot' and r['node']==node and (node==1 or r['time_s']>=300))
 n=next(r for r in native if r['purpose']=='mac_slot' and int(r['node'])==node and (node==1 or int(r['time_ns'])>=300000000000))
 first.append({'node':node,'matlab_time_s':m['time_s'],'matlab_ordinal':m['ordinal'],'matlab_draw':m['value'],'native_time_ns':n['time_ns'],'native_ordinal':n['ordinal'],'native_draw':n['value'],'matlab_active_nodes':m['actual']['active_nodes'],'native_active_nodes':n['active_nodes'],'matlab_low':m['actual']['low'],'matlab_high':m['actual']['high'],'native_low':n['low'],'native_high':n['high'],'matlab_counter':m['actual']['reservation_counter'],'native_counter':n['reservation_counter'],'matlab_state':m['actual']['state'],'native_state':n['state']})
write('direct_mac_draws.csv',first)
# Retain scheduler metadata to interpret passive timer handles without callbacks.
schedules={}; pending=set(); initial={}; transmissions=[]; transitions=[]; series=[]; firsttracks={}; event_counts=Counter(); selected=[]
TIMERS=['SlotEvent','HoldoffEvent','IdleRtsEvent','FinishEvent','WakeEvent','SleepEvent','PostTxEvent','PackingRetryEvent']
def enrich(r):
 d=r['details'];x={'observation_order':r['observation_order'],'time_s':r['time_s'],'node':r['node'],'kind':r['kind'],'details':d,'timers':{}}
 for name in TIMERS:
  key=d.get(name,0)
  if key: x['timers'][name]={'EventId':key,'pending':key in pending,**schedules.get(key,{})}
 return x
with (A/'ordered_events.jsonl').open() as f:
 for line in f:
  r=json.loads(line); kind=r['kind'];d=r['details'];t=r['time_s'];node=r['node']; event_counts[kind]+=1
  if kind=='scheduler_schedule':
   key=d['EventId'];schedules[key]={'DeadlineSeconds':d['DeadlineSeconds'],'Callback':d['Callback']};pending.add(key)
  elif kind in ('scheduler_cancel','scheduler_fire'): pending.discard(d['EventId'])
  elif kind=='mac_boundary':
   if node in (2,4,7,8) and t>=300 and node not in initial:initial[node]=enrich(r)
   if node in (7,8,2) and 300<=t<=302.05:
    if d['Cause'] in ('slotTick_before','slotTick_after','receiverChanged_before','receiverChanged_after','prepare_before','prepare_after','transmit_before','transmit_after','finishTx_after'):
     series.append({'observation_order':r['observation_order'],'time_s':t,'node':node,'cause':d['Cause'],'state':d['State'],'reservation_counter':d['ReservationCounter'],'reservation_slot':d['ReservationSlot'],'preparation_active':d['PreparationActive'],'holdoff_over':d['HoldoffOver'],'post_tx_wait_active':d['PostTxWaitActive'],'data_depth':d['DataQueueCount'],'ack_depth':d['AckQueueCount']})
   if d['Cause']=='transmit_before' and ((node==1 and t<11) or (node in (2,4,7,8) and 300<=t<304)):
    selected.append(enrich(r))
  elif kind=='phy_state_transition':
   if d['Changed'] and d['Current']=='Track' and node in (4,2,8,7) and node not in firsttracks: firsttracks[node]=r
   if node in (2,4,7,8) and 300<=t<=302.05:transitions.append(r)
  elif kind=='protocol' and d['event']=='mac_transmit' and (t<11 or 300<=t<304):
   frame=d['frame'];children=frame.get('Segments',[frame]);
   transmissions.append({'time_s':t,'node':node,'destination':frame['DestinationId'],'preamble':frame['Preamble'],'duration_s':d['details']['DurationSeconds'],'reservation_slot':frame['ReservationSlot'],'children': [{'kind':c['Kind'],'sequence':c['Sequence'],'source':c['SourceId'],'destination':c['DestinationId'],'application_source':c.get('App',{}).get('SourceId'),'application_destination':c.get('App',{}).get('DestinationId'),'application_generated_s':c.get('App',{}).get('GeneratedSeconds'),'application_id':c.get('App',{}).get('Id'),'application_flow_index':c.get('App',{}).get('FlowIndex'),'application_attempt_index':c.get('App',{}).get('FlowOrdinal')} for c in children]})
write('mac_countdown_context_300_302.csv',series)
dump('direct_state_at_application_start.json',initial);dump('direct_transmission_context.json',transmissions);dump('direct_transmit_snapshots.json',selected);dump('direct_phy_transitions_300_302.json',transitions);dump('direct_first_track_transitions.json',firsttracks)
# Verify key direct facts, fail rather than infer if the passive return disagrees.
assert first[0]['matlab_draw']==10 and int(first[0]['native_draw'])==11
expected_states={2:'Idle',4:'Search',7:'Search',8:'Search'}
assert {n:r['details']['State'] for n,r in initial.items()}==expected_states
assert all(r['time_s']==300 for r in initial.values())
assert initial[8]['details']['ActiveNodes']==3
node8hears=next(x for x in initial[8]['details']['Neighbors'] if x['PeerId']==2)
node8tx=next(x for x in transmissions if x['node']==8 and any(c['kind']=='DATA' for c in x['children']))
assert node8tx['time_s']==300.144 and node8tx['preamble']=='long'
first7=next(x for x in transmissions if x['node']==7 and any(c['kind']=='DATA' for c in x['children']))
assert first7['time_s']==301.496
hold=[r for r in series if r['node']==7 and r['cause']=='slotTick_before' and r['state']=='Track' and 300.15<r['time_s']<301.39]
assert hold and all(r['reservation_counter']==8 for r in hold)
protocol=readcsv(A/'protocol_trace.csv')
ack7=next(r for r in protocol if r['NodeId']=='7' and r['Event']=='hop_ack' and r['PacketId']=='5' and r['FrameKind']=='DATA' and r['Sequence']=='12' and float(r['TimeSeconds'])>=300)
assert abs(float(ack7['TimeSeconds'])-302.029292441945)<1e-10
summary={'scope':'Read-only direct natural observations, independently checked against passed prefix gate; no new simulations.',
 'prefix_gate':json.loads((A/'prefix_gate.json').read_text()),'event_counts':dict(event_counts),
 'first_gateway_draw':first[0], 'application_start_states_direct':expected_states,
 'node8_data':node8tx,'node8_last_heard2_s':node8hears['LastHeardSeconds'],
 'node8_freshness_limit_s':15.5+1.5*initial[8]['details']['ActiveNodes'],
 'node8_freshness_age_at_first_data_s':node8tx['time_s']-node8hears['LastHeardSeconds'],
 'node7_first_data':first7,'node7_frozen_track_ticks':len(hold),'node7_frozen_counter':8,
 'node7_first_track_tick':hold[0]['time_s'],'node7_last_track_tick':hold[-1]['time_s'],
 'node7_first_hop_ack':ack7,
 'limitation':'B_common failed harness import normalization before its first native sample at10.01; these findings do not establish coupled parity or a same-input production defect.'}
dump('summary.json',summary)
native_states={}; native_timers={}
for r in readcsv(N/'receiver_history.csv'):
 if int(r['time_ns'])>=300000000000:break
 if r['node'] not in ('2','4','7','8'):continue
 d=json.loads(r['detail_json'])
 if r['event']=='receiver_boundary':native_states[r['node']]={'time_ns':r['time_ns'],'event_order':r['event_order'],'state':r['state_before'],'details':d}
 if r['event']=='timer_lifecycle' and d.get('timer')=='m_postTxWaitEvent':native_timers[r['node']]={'time_ns':r['time_ns'],'event_order':r['event_order'],'details':d}
for n in native_states:native_states[n]['last_post_tx_timer_record']=native_timers.get(n)
dump('native_state_at_application_start.json',native_states)
first_native_data=[]
for r in readcsv(N/'tx_signatures.csv'):
 if r['kind']=='0' and r['source'] in ('7','8') and r['source']==r['network_source'] and r['app_attempt_index']=='1' and r['app_generated_time_ns']=='300000000000':
  first_native_data.append(r)
assert len(first_native_data)==2
write('native_first_source_data_signature.csv',first_native_data)

paths=[A/'random_requests.jsonl',A/'ordered_events.jsonl',A/'prefix_gate.json',A/'protocol_trace.csv',N/'random_draws.csv',N/'receiver_history.csv',N/'tx_signatures.csv']
manifest=[]
for p in paths:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''): h.update(chunk)
 manifest.append({'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':h.hexdigest()})
write('input_manifest.csv',manifest)
print(json.dumps({k:v for k,v in summary.items() if k not in ('event_counts','prefix_gate')},indent=2))
