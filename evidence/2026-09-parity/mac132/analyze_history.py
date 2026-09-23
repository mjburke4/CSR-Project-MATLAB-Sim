"""Rebuild seed-132 bounded scheduling evidence from archived traces; no simulator changes."""
import csv,json,re,collections,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'mac132'
def rows(p): return csv.DictReader(open(ROOT/p,newline=''))
def write(name,rs):
 if not rs:return
 with open(OUT/name,'w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
N=[]; ns={}; windows=[]; states={}; native_rx=[]; delays={}
for r in rows('queue132/native/first_failure_observed/ns3-trace.csv'):
 t=float(r['time_s']);node=r['node'];ev=r['event']
 if t>=675:continue
 if ev=='nwk_admission' and node in ['2','4','8']:
  d=dict(x.split('=',1) for x in r['detail'].split(';') if '=' in x)
  if 'threshold' in d:
   win=int(d['threshold'])+1
   if states.get(node)!=win:
    windows.append(dict(engine='native',time_s=t,node=node,window=win));states[node]=win
   if t<600:ns[node]={'time_s':t,**d}
 if ev=='statistic_sample' and r['statistic']=='MAC.Tx Queuing Delay (sec)':delays[(node,round(t,9))]=float(r['value'])
 if ev=='tx_start' and t>=600 and node in ['2','4','8']:
  N.append(dict(engine='native',time_s=t,node=node,peer=r['peer'],kind=r['packet_type'],sequence=r['sequence'],packet_id='',duration_s=.2448 if r['packet_type']=='data' else '',consumed_slot='',next_slot=r['reservation_slot'],queue_delay_s=delays.get((node,round(t,9)),''),log_line=''))
 if ev in ['rx_accept','rx_drop'] and node=='2' and r['src']=='8' and r['packet_type']=='data' and t>=600:
  native_rx.append(r)
M=[]; mr=list(rows('queue132/matlab/focused_600_675/protocol_trace.csv'))
hops={(r['NodeId'],round(float(r['TimeSeconds']),9)) for r in mr if r['Event']=='hop_sent'}
for r in mr:
 t=float(r['TimeSeconds']);node=r['NodeId']
 if r['Event']=='tx_start' and node in ['2','4','8'] and 600<=t<675:
  data=(node,round(t,9)) in hops
  M.append(dict(engine='matlab',time_s=t,node=node,peer=r['PeerId'],kind='data' if data else 'feedback_or_control',sequence=r['Sequence'],packet_id=r['PacketId'],duration_s=.2448 if data else '',consumed_slot='',next_slot='',queue_delay_s='',log_line=''))
slots={}
for ln,line in enumerate(open(ROOT/'queue132/native/first_failure_observed/run.log'),1):
 m=re.search(r'time_ns=(\d+) \[MAC (\d+)\] TX opportunity reached currentSlot=(\d+) reserveNextSlot=(\d+)',line)
 if m: slots[(m[2],int(m[1]))]=(m[3],m[4],ln)
for r in N:
 s=slots.get((r['node'],round(r['time_s']*1e9)))
 if s:r['consumed_slot'],_,r['log_line']=s
ms={};prev={}
for r in rows('queue132/matlab/events.csv'):
 t=float(r['time_s']);node=r['node'];win=int(r['threshold_after'])+1
 if t>=675:continue
 if prev.get(node)!=win:windows.append(dict(engine='matlab',time_s=t,node=node,window=win));prev[node]=win
 if t<600:ms[node]={k:r[k] for k in ['time_s','waiting_after','outstanding_after','threshold_after']}
phy={}
for r in rows('queue132/matlab/focused_600_675/phy_trace.csv'):
 if r['Event']=='phy_signal_end' and r['NodeId']=='2':phy[r['PacketId']]=r
exposure=[]
for engine,tx in [('native',N),('matlab',M)]:
 blocks=[r for r in tx if r['node']=='4' and r['peer']=='5' and r['kind']=='data']
 for r in tx:
  if not(r['node']=='8' and r['peer']=='2' and r['kind']=='data'):continue
  start=r['time_s']+.000015346;end=start+.2448
  overlaps=[b for b in blocks if b['time_s']+.000013632<end and b['time_s']+.000013632+.2448>start]
  prior=[b for b in overlaps if b['time_s']+.000013632<start]
  if engine=='native':
   rx=[x for x in native_rx if x['sequence']==r['sequence'] and abs(float(x['time_s'])-end)<1e-6]
   assert len(rx)==1,(r,rx)
   result=rx[0]['reason'] or 'accepted'
  else:
   x=phy.get(r['packet_id']);result=x['Reason'] if x else 'unfinished_at_cutoff'
  exposure.append(dict(engine=engine,time_s=r['time_s'],sequence=r['sequence'],result=result,overlaps_4_to_5=len(overlaps),earlier_4_to_5=len(prior)))
summary={'interval':'600 <= t < 675 seconds','state_before_600':{'native':ns,'matlab':ms},'links':{},'receiver_2':{},'node4_mean_window':{}}
for eng,tx in [('native',N),('matlab',M)]:
 summary['links'][eng]=dict(collections.Counter(f"{r['node']}->{r['peer']} {r['kind']}" for r in tx))
 er=[r for r in exposure if r['engine']==eng]
 summary['receiver_2'][eng]={'8_to_2_data_attempts':len(er),'outcomes':dict(collections.Counter(r['result'] for r in er)),'overlap_4_to_5':sum(r['overlaps_4_to_5']>0 for r in er),'4_to_5_started_first':sum(r['earlier_4_to_5']>0 for r in er)}
 ws=sorted([r for r in windows if r['engine']==eng and r['node']=='4'],key=lambda r:r['time_s']);total=0
 for i,r in enumerate(ws):
  a=max(600,r['time_s']);b=min(675,ws[i+1]['time_s'] if i+1<len(ws) else 675)
  total+=max(0,b-a)*r['window']
 summary['node4_mean_window'][eng]=total/75
write('transmissions.csv',N+M);write('window_history.csv',windows);write('receiver_exposure.csv',exposure)
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
# Independent checks on the measurement assumptions used in the report.
starts={};ends={}
for r in rows('queue132/matlab/focused_600_675/phy_trace.csv'):
 key=(r['NodeId'],r['PacketId'])
 if r['Event']=='phy_signal_start':starts[key]=float(r['TimeSeconds'])
 if r['Event']=='phy_signal_end':ends[key]=float(r['TimeSeconds'])
checked=0
for r in M:
 if r['node']=='4' and r['peer']=='5' and r['kind']=='data':
  key=('5',r['packet_id'])
  assert key in starts and key in ends
  assert abs(ends[key]-starts[key]-.2448)<1e-8
  checked+=1
assert all(r['consumed_slot']!='' for r in N)
assert all(r['result']!='unfinished_at_cutoff' for r in exposure)
(OUT/'validation.json').write_text(json.dumps({'matlab_4_to_5_frame_durations_verified':checked,'native_transmissions_with_consumed_slot':len(N),'receiver_2_outcomes_resolved':len(exposure),'checks_passed':True},indent=2)+'\n')
