#!/usr/bin/env python3
"""Extract bounded public native receiver interval/RNG ordering evidence."""
import csv, hashlib, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
report={'schema':'csr-native-receiver-order-probe-v1','passed':True,
 'native_source_pin':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b',
 'ns3_source_pin':'6b5cd24ea80713ce16d88575869aedd6f432bdae',
 'observer_scope':'Existing passive overlay; no scheduling, state override, RNG replacement or private access',
 'fixture':{'wire_payload_bytes':198,'rate_key_kbps':8,'preamble':'short','noise_floor_dbm':0,
            'tx_power_dbm':0,'distance_to_receiver_m':1,'receiver':3,'second_tx_seconds':0.026009895}}
for name,arrival,drawsources in [('reverse',[2,1],[1,1,2]),('ascending',[1,2],[1,2,2])]:
 path=HERE/f'native_{name}.tsv'
 rows=list(csv.DictReader(path.open(),delimiter='\t'))
 rows=[dict(r,detail=json.loads(r['detail_json'])) for r in rows if r['node']=='3']
 starts=[int(r['tx_id'])>>32 for r in rows if r['event']=='rx_signal_arrival']
 tracks=[int(r['tx_id'])>>32 for r in rows if r['event']=='rx_acquire']
 assert starts==arrival and tracks[0]==arrival[0]
 draws=[r for r in rows if r['event']=='rx_binomial_draw']
 assert len(draws)==4 and all(r['detail']['rng_consumed']=='1' for r in draws)
 firsttime=int(draws[0]['time_ns'])
 selected=[r for r in draws if int(r['time_ns'])==firsttime]
 assert len(selected)==3
 intervals=[int(r['tx_id'])>>32 for r in rows if r['event']=='rx_error_interval' and int(r['time_ns'])==firsttime]
 assert intervals==[1,2]
 sources=[int(r['tx_id'])>>32 for r in selected]
 assert sources==drawsources
 contexts=[]
 for r in selected:
  d=r['detail']; c={'tx_id':int(r['tx_id']),'component':d['component'],'probability':float(d['probability'])}
  for key in ['interval_ordinal','bits','interval_start_ns','interval_end_ns','component_start_ns','component_end_ns']:
   c[key]=int(d[key])
  assert c['bits']>0 and 0<c['probability']<1
  contexts.append(c)
 report[name]={'arrival_sources':starts,'first_track_source':tracks[0],'close_sources':intervals,
               'close_time_ns':firsttime,'draw_sources':sources,'draw_contexts':contexts,
               'native_total_receiver_uniform_draws':len(draws),'raw_sha256':sha(path)}
report['driver_sha256']=sha(HERE/'receiver_interval_order_probe.cc')
(HERE/'native_receiver_order.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':report['passed'],'reverse_draw_sources':report['reverse']['draw_sources'],
 'ascending_draw_sources':report['ascending']['draw_sources'],'native_total_draws':8}))
