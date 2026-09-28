from pathlib import Path
import csv,json,hashlib
base=Path(__file__).resolve().parents[1]; out=base/'matlab'
rows=[]; cases=[]
def short_frame(f):
 c=f.get('Control') or {}; p=c.get('Payload') or {}
 return {'kind':f.get('Kind',''),'source':f.get('SourceId'),'destination':f.get('DestinationId'),
  'hop_sequence':f.get('Sequence'),'wire_bytes':f.get('WirePayloadBytes'),
  'control_type':c.get('Type',''),'subtype':p.get('Subtype',''),'control_sequence':p.get('Sequence')}
for case in ['C_timing','D_inline_key']:
 folder=base/'data'/case; log=folder/'ordered_events.jsonl'; end=[]
 for line in log.open():
  r=json.loads(line);d=r['details']
  if r['node']!=5 or r['time_s']<11.5: continue
  if r['kind']=='protocol':
   f=d.get('frame') or {}; x=d.get('details') or {}
   rows.append(dict(case=case,order=r['observation_order'],time_s=r['time_s'],event=d['event'],
    **short_frame(f),details=json.dumps(x,separators=(',',':'))))
   if r['time_s']==12.402 and f.get('Segments'):end=[short_frame(k) for k in f['Segments']]
 mismatch=json.loads((folder/'first_divergence.json').read_text()); usage=json.loads((folder/'random_summary.json').read_text())
 expected=[dict(kind={1:'ACK',5:'CONTROL'}[x['kind']],source=x['source'],destination=x['hop_destination'],
  hop_sequence=x['hop_sequence'],wire_bytes=x['wire_bytes'],control_type='NEIGHBOR_CHECK' if x['kind']==5 else '',
  subtype=x['check_subtype'],control_sequence=x['check_sequence']) for x in mismatch['expected']]
 assert end==expected[:3],(case,end,expected[:3])
 assert expected[3]['subtype']=='overheard' and expected[3]['wire_bytes']==16
 assert sum(x['wire_bytes'] for x in end)==66 and sum(x['wire_bytes'] for x in expected)==82
 cases.append(dict(case=case,stop_time_s=mismatch['actual_time_s'],draws_consumed=usage['draw_count'],
  native_transmissions_checked=usage['native_transmissions_checked'],first_time_difference=usage['first_time_difference'],
  actual_children=end,expected_children=expected,missing_child=expected[3],
  ordered_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
with (out/'node5_control_chronology.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
summary=dict(schema='csr-node5-missing-overheard-audit-v1',cases=cases,
 observed_cause='Discovery proof is queued after KEY_UPDATE ACK; MATLAB generic CheckActive excludes otherwise-eligible Overheard proof in evaluate; native has no such Overheard exclusion.',
 proposed_scope='Remove only CheckActive from the Overheard send predicate in an isolated candidate; preserve the original not-yet-due branch and key/liveness/discovery/deadline gates.',
 model_modified=False,matlab_executed_by_analysis=False)
(out/'missing_child_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({x['case']:{k:x[k] for k in ['stop_time_s','draws_consumed','native_transmissions_checked','first_time_difference','missing_child']} for x in cases},indent=2))
