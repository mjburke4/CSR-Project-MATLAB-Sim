#!/usr/bin/env python3
"""Verify that accepted 0–665 s owner replay already covers proposed 0–330 s cases.
No simulation; compare issued inputs, returned observations, and runtime hashes.
"""
from pathlib import Path
from decimal import Decimal
import csv,difflib,hashlib,json
R=Path(__file__).resolve().parent
OLD=R.parent/'mac_kit/macfix';OWNER=R.parent/'mac_owner'
NEW=R/'out_short_20260924_083651/replays/source5_mac/staging'
ADAPTER=R.parent/'short_kit/two_case_next/source5_replay/mac_adapter'
MODEL=R.parents[1]/'return6000/kit/csr6000/model'
def rows(p):return list(csv.DictReader(p.open()))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def integer(s):return int(Decimal(s))
def prefix(rr,node):return [x for x in rr if x['node']==str(node) and integer(x['time_ns'])<330000000000]
def equal_fields(a,b,fields):return all(a[k]==b[k] for k in fields)
rt=json.loads((OWNER/'runtime_binding.json').read_text())
assert rt['pass'] and all(x['match'] for x in rt['files'])
assert all((OLD/x['path']).exists() and sha(OLD/x['path'])==x['actual_sha256'] for x in rt['files'])
assert (OLD/'matlab/+mac_replay/MacLayer.m').read_bytes()==(ADAPTER/'matlab/+mac_replay/MacLayer.m').read_bytes()
assert (OLD/'matlab/+mac_replay/Scheduler.m').read_bytes()==(ADAPTER/'matlab/+mac_replay/Scheduler.m').read_bytes()
odriver=(OLD/'matlab/run_mac_history.m').read_text();ndriver=(ADAPTER/'matlab/run_mac_history.m').read_text()
oldlabel="    window=compareRows(refTx(refSelected,:),tx(selected,:),fields,'target 657–665 second TX events');"
newlabel="    label=sprintf('target %g–%g second TX events',compareStart/1e9,compareStop/1e9);\n    window=compareRows(refTx(refSelected,:),tx(selected,:),fields,label);"
assert odriver.replace(oldlabel,newlabel)==ndriver
model_same=[];model_changed=[]
for p in (OLD/'core').rglob('*'):
 if not p.is_file():continue
 rel=p.relative_to(OLD/'core');q=MODEL/rel;assert q.exists()
 (model_same if p.read_bytes()==q.read_bytes() else model_changed).append(str(rel))
assert model_changed==['+csr/+hop/Layer.m']
oi=rows(OLD/'inputs/inputs.csv');ni=rows(NEW/'inputs/inputs.csv')
of={x['frame_id']:x for x in rows(OLD/'inputs/frames.csv')};nf={x['frame_id']:x for x in rows(NEW/'inputs/frames.csv')}
od=rows(OLD/'inputs/draws.csv');nd=rows(NEW/'inputs/draws.csv');nt=rows(NEW/'reference/tx.csv')
summary=[];maprows=[]
for node in [2,8]:
 a=prefix(oi,node);b=prefix(ni,node);assert len(a)==len(b)
 fmap={}
 for j,(x,y) in enumerate(zip(a,b)):
  assert equal_fields(x,y,set(x)-{'event_order','frame_id'}),(node,j,'input')
  assert bool(x['frame_id'])==bool(y['frame_id'])
  if x['frame_id']:
   assert x['frame_id'] not in fmap or fmap[x['frame_id']]==y['frame_id']
   fmap[x['frame_id']]=y['frame_id']
   assert equal_fields(of[x['frame_id']],nf[y['frame_id']],set(of[x['frame_id']])-{'frame_id'}),(node,j,'frame')
 assert len(set(fmap.values()))==len(fmap)
 for old,new in fmap.items():maprows.append({'node':node,'prior_frame_id':old,'short_frame_id':new})
 a_draw=prefix(od,node);b_draw=prefix(nd,node);assert len(a_draw)==len(b_draw)
 assert all(equal_fields(x,y,set(x)-{'event_order'}) for x,y in zip(a_draw,b_draw))
 actual_tx=rows(OWNER/f'history/node{node}/tx.csv');actual_tx=[x for x in actual_tx if integer(x['time_ns'])<330000000000]
 ref_tx=prefix(nt,node);assert len(actual_tx)==len(ref_tx)
 for j,(x,y) in enumerate(zip(actual_tx,ref_tx)):
  for k in y:
   if k=='frame_ids':assert ';'.join(fmap[p] for p in x[k].split(';'))==y[k],(node,j,k)
   else:assert Decimal(x[k])==Decimal(y[k]),(node,j,k,x[k],y[k])
 actual_draw=rows(OWNER/f'history/node{node}/draws.csv');actual_draw=[x for x in actual_draw if integer(x['time_ns'])<330000000000]
 assert len(actual_draw)==len(b_draw)
 for j,(x,y) in enumerate(zip(actual_draw,b_draw)):
  assert all(Decimal(x[k])==Decimal(y[k]) for k in ['time_ns','node','ordinal','min','max','draw']),(node,j,'owner_draw')
 applied=rows(OWNER/f'history/node{node}/input_application.csv');applied=[x for x in applied if integer(x['time_ns'])<330000000000]
 assert len(applied)==len(a)
 for j,(x,y) in enumerate(zip(applied,a)):
  assert integer(x['event_order'])==integer(y['event_order']) and integer(x['time_ns'])==integer(y['time_ns']) and x['kind']==y['kind'],(node,j,'applied')
 summary.append({'node':node,'input_prefix_rows_matched':len(a),'full_frame_records_matched':len(fmap),'native_draw_prefix_matched':len(a_draw),'prior_owner_tx_prefix_matched':len(actual_tx),'prior_owner_draw_prefix_matched':len(actual_draw),'prior_owner_input_application_prefix_matched':len(applied)})
with (R/'prior_to_short_frame_ids.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=maprows[0].keys());w.writeheader();w.writerows(maprows)
report={'schema':'csr-prior-mac-acceptance-reuse-v1','pass':True,'method':'Read-only verification of previously returned real MATLAB execution; no new simulation.','runtime':'25.1.0.2943329 (R2025a)','runtime_binding_files_verified':len(rt['files']),'adapter_mac_bytes_identical':True,'adapter_scheduler_bytes_identical':True,'driver_difference':'Only text label for target window changed from fixed 657–665 to profile-derived bounds.','current_model_files_same':len(model_same),'current_model_files_different':model_changed,'changed_model_file_executed_by_mac_replay':False,'nodes':summary,'normalization':['Global observer event_order IDs differ because capture node sets differ; per-node ordered input rows including tied timestamps match exactly.','Frame IDs differ by capture; a bijection is established from ordered enqueue events, validating every other frame field including packet_hex, ACK/DACK fields and link control.','Decimal/scientific CSV numbers compared exactly with Decimal, not rounded binary floats.'],'conclusion':'Do not issue the proposed nodes2/8 0–330 MAC replay. Its full input/draw/TX populations, including specific feedback-priority waits, already passed in the September23 owner return.','scope_limit':'This validates conditional MAC service given the captured native queue, feedback-cancellation, receiver availability and draw history. It does not validate autonomous PHY receiver inputs, ACK generation, HOP/NWK custody or network parity.'}
(R/'prior_acceptance_reuse.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
