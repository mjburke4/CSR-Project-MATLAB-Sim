#!/usr/bin/env python3
from pathlib import Path
import csv,json,sys
R=Path(__file__).resolve().parents[2];log=Path(sys.argv[1]) if len(sys.argv)>1 else R/'mac_replay/native/capture/mac-input.log';out=Path(sys.argv[2]) if len(sys.argv)>2 else R/'mac_replay/inputs';out.mkdir(parents=True,exist_ok=True)
def write(name,rows,fields):
 with (out/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
fields='time_ns event_order node kind peer sequence frame_id value value2 value3 ack_bitmap dack_bitmap'.split();ff='frame_id node source destination sequence type dscp ackable is_ack is_dack has_ack_window ack_bitmap dack_bitmap rate has_link_control tx_power_dbm rx_power_dbm wirebytes envelope_format compatibility_payload_bytes destination_sequences packet_hex'.split();tf='time_ns node child_index source destination sequence type wirebytes frame_id'.split()
inputs=[];frames=[];draws=[];txs=[];children=[]
for line in log.open():
 v=line.rstrip('\n').split('|');k=v.pop(0)
 if k=='INPUT':
  order,time,node,kind,*x=v;r=dict.fromkeys(fields,'');r.update(time_ns=time,event_order=order,node=node,kind=kind)
  if kind=='enqueue':r.update(peer=x[0],value=x[1],value2=x[2],frame_id=x[3])
  elif kind in ['receiver_state','sync','active','reported']:r['value']=x[0]
  elif kind=='received':r.update(peer=x[0],value=x[1],value2=x[2],value3=x[3])
  elif kind=='cancel_ack':r.update(peer=x[0],sequence=x[1],ack_bitmap=x[2],dack_bitmap=x[3])
  elif kind=='cancel_type':r.update(peer=x[0],value=x[1])
  else:raise ValueError(kind)
  inputs.append(r)
 elif k=='FRAME':assert len(v)==len(ff),(len(v),len(ff));frames.append(dict(zip(ff,v)))
 elif k=='DRAW':draws.append(dict(zip('event_order time_ns node ordinal min max draw'.split(),v)))
 elif k=='TX':txs.append(dict(zip('event_order time_ns node rate power preamble next_slot consumed_slot segments'.split(),v)))
 elif k=='TXFRAME':children.append(dict(zip(tf,v)))
 else:raise ValueError(k)
write('inputs.csv',inputs,fields);write('frames.csv',frames,ff);write('draws.csv',draws,'event_order time_ns node ordinal min max draw'.split());write('tx_raw.csv',txs,'event_order time_ns node rate power preamble next_slot consumed_slot segments'.split());write('tx_frames.csv',children,tf)
by={}
for r in children:by.setdefault((r['time_ns'],r['node']),[]).append(r)
canonical=[]
for r in txs:
 c=by[(r['time_ns'],r['node'])];wire=sum(int(a['wirebytes']) for a in c);bits=7888 if int(r['preamble'])==1 else 104
 # Native enum: SHORT=0, LONG=1.
 assert int(r["rate"])==8, "Capture-specific converter must be extended using CsrRateKeyToBps for another rate"
 duration=round(((bits+48)/4*.00051+(wire*8+32)/(4/.00051))*1e9)
 canonical.append(dict(time_ns=r['time_ns'],node=r['node'],consumed_slot=r['consumed_slot'],next_slot=r['next_slot'],wirebytes=wire,rate=r['rate'],power=r['power'],preamble_bits=bits,duration_ns=duration,frame_ids=';'.join(a['frame_id'] for a in c)))
write('tx.csv',canonical,'time_ns node consumed_slot next_slot wirebytes rate power preamble_bits duration_ns frame_ids'.split())
(out/'counts.json').write_text(json.dumps(dict(inputs=len(inputs),frames=len(frames),draws=len(draws),tx=len(txs),children=len(children)),indent=2)+'\n')
print((out/'counts.json').read_text())
