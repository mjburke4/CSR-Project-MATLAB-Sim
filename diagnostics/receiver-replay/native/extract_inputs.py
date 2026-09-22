#!/usr/bin/env python3
import pathlib,csv,json,math,hashlib
R=pathlib.Path(__file__).resolve().parents[2];N=R/'receiver_replay/native';I=R/'receiver_replay/inputs';I.mkdir(exist_ok=True)
fields='event_order time_ns kind signal_id source dest sequence wirebytes preamblebits packetbits rate tx_dbm rx_dbm noise_watts distance_m start_s end_s preamble_end_s slot ackable channel_matched tx_frequency_hz tx_bandwidth_hz tx_gain_db tx_height_m'.split();rows=[];children={};sync={};draws=[];events=[];controls=[];finishes={}
for line in (N/'capture/receiver-input.log').open():
 p=line.rstrip('\n').split('|');kind=p.pop(0)
 if kind=='CONTROL':controls.append(dict(zip('event_order time_ns kind value'.split(),p)))
 elif kind=='FINISH':finishes[p[0]]=dict(queues_empty_at_end=p[1],active_nodes=p[2])
 elif kind=='INPUT':rows.append(dict(zip(fields,p)))
 elif kind=='CHILD':children[(p[0],p[1])]=dict(zip('signal_id child_index source dest sequence type wirebytes packet_hex'.split(),p))
 elif kind=='SYNC':sync[p[0]]=p[1]
 elif kind=='DRAW':
  d=dict(zip('signal_id interval_start_s interval_end_s phase uniform bits probability'.split(),p));d['interval_start_ns']=round(float(d['interval_start_s'])*1e9);d['interval_end_ns']=round(float(d['interval_end_s'])*1e9);draws.append(d)
 elif kind=='EVENT':events.append(dict(zip('event_index time_ns signal_id stage source hop_sequence result reason state_before state_after'.split(),p)))
for r in rows:
 r['sync_threshold_db']=sync.get(r['signal_id'],'')
 # ns3 callback schedules offsets relative to already quantized callback Now.
 r['end_ns']=int(r['time_ns'])+round((float(r['end_s'])-int(r['time_ns'])/1e9)*1e9)
 r['preamble_end_ns']=int(r['time_ns'])+round((float(r['preamble_end_s'])-int(r['time_ns'])/1e9)*1e9)
 r['queues_empty_at_end']='';r['active_nodes']='3'
 if r['kind']=='own_tx':
  duration=(int(r['preamblebits'])+48)/4*.00051+(int(r['wirebytes'])*8+32)/(int(r['rate'])*1000/1.02)
  r['end_ns']=int(r['time_ns'])+round(duration*1e9)
  r.update(finishes.get(str(r['end_ns']),{}))
 r['duration_s']=format(float(r['end_s'])-float(r['start_s']),'.17g')
def write(path,rows):
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
prior=[c for c in controls if int(c['time_ns'])<620000000000 and c['kind']=='prep_tx'];initial_prep=prior[-1]['value'] if prior else '0'
controls=[dict(event_order=0,time_ns='620000000000',kind='prep_tx',value=initial_prep)]+[c for c in controls if int(c['time_ns'])>=620000000000]
write(I/'controls.csv',controls)
write(I/'inputs.csv',rows);write(I/'children.csv',list(children.values()));write(I/'draws.csv',draws);write(N/'capture/events.csv',events)
profile=dict(receiver_id=2,warmup_start_ns=620000000000,comparison_start_ns=657000000000,comparison_stop_ns=669000000000,replay_stop_ns=669000000000,absolute_times=True,initial_state='IDLE',duty_cycle='opnet-aligned',receiver_frequency_hz=400000000,bandwidth_hz=1000000,antenna_height_m=1,noise_floor_dbm=-106.975,ecc_threshold=.1,active_nodes=3,randomness='captured original per-signal SYNC threshold and per-signal interval/header-or-payload uniform',own_tx_semantics='physical NotifyPhyTxStart/FinishTx only; no autonomous queue scheduling',fixture_counts=dict(inputs=len(rows),signals=sum(r['kind']=='signal' for r in rows),own_tx=sum(r['kind']=='own_tx' for r in rows),children=len(children),draws=len(draws)))
profile.update(start_ns=620000000000,stop_ns=669000000000,compare_start_ns=657000000000,compare_end_ns=669000000000,ActiveNodes=3)
assert all(r['channel_matched']=='1' for r in rows)
(I/'profile.json').write_text(json.dumps(profile,indent=2)+'\n');print(profile['fixture_counts'])
