#!/usr/bin/env python3
"""Check replay boundaries, identity joins and finite integer draw support."""
from pathlib import Path
import csv,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'inputs'
def read(name):return list(csv.DictReader(open(P/name,newline='')))
inputs=read('inputs.csv');frames=read('frames.csv');draws=read('draws.csv');tx=read('tx.csv')
ids={r['frame_id'] for r in frames};assert len(ids)==len(frames)
queued=[r for r in inputs if r['kind']=='enqueue'];assert {r['frame_id'] for r in queued}==ids
assert len(queued)==len(frames)
allowed={'enqueue','receiver_state','sync','received','cancel_ack','cancel_type','active','reported'}
assert all(r['kind'] in allowed for r in inputs)
assert all(r['value'] in {'idle','search','track'} for r in inputs if r['kind']=='receiver_state'),'Own TX must not be prescribed'
assert len({int(r['event_order']) for r in inputs+draws})==len(inputs)+len(draws)
for node in ['2','4','8']:
 rs=[r for r in inputs if r['node']==node]
 assert rs and [(int(r['time_ns']),int(r['event_order'])) for r in rs]==sorted((int(r['time_ns']),int(r['event_order'])) for r in rs)
 ds=[r for r in draws if r['node']==node]
 assert [int(r['ordinal']) for r in ds]==list(range(1,len(ds)+1))
 assert all(int(r['min'])<=int(r['draw'])<=int(r['max']) for r in ds)
for r in tx:
 assert set(r['frame_ids'].split(';'))<=ids
 assert int(r['duration_ns'])>0
# Original target DATA timing sanity check catches nominal-rate conversion errors.
for r in tx:
 if r['node']=='8' and int(r['time_ns']) in [658164000000,661882000000,664261000000]:
  assert int(r['duration_ns'])==244800000 and int(r['wirebytes'])==217
receipt={'pass':True,'queued_frames':len(frames),'external_inputs':len(inputs),'integer_draws':len(draws),'native_tx_rows':len(tx),'own_tx_is_input':False,'input_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(P.glob('*.csv'))}}
(ROOT/'review/input_validation.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
