#!/usr/bin/env python3
"""Read-only coverage audit of the two previously returned MATLAB short-test ZIPs."""
import csv,hashlib,json,zipfile
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REC=ROOT.parent/'recovered'/'NS3 to MATLAB Network Simulation'
SHORT='out_short_20260924_083651'
NEXT='out_next_20260924_100916'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return list(csv.DictReader(p.open(newline='')))
def save(name,rr,fields=None):
 p=ROOT/name
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields or list(rr[0]));w.writeheader();w.writerows(rr)
archives={}
for name in [SHORT,NEXT]:
 p=REC/(name+'.zip')
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  assert all(not Path(x.filename).is_absolute() and '..' not in Path(x.filename).parts for x in z.infolist())
  if not (ROOT/name).exists():z.extractall(ROOT/name)
  archives[name]={'sha256':sha(p),'members':len(z.infolist()),'crc_valid':True}
prov=[json.loads((ROOT/n/'run_provenance.json').read_text()) for n in [SHORT,NEXT]]
assert prov[0]['candidate_sources']==prov[1]['candidate_sources']
model=ROOT.parents[1]/'return6000/kit/csr6000/model'
checks=[{'path':x['path'],'sha256':x['sha256'],'matches_current_model':sha(model/x['path'])==x['sha256']} for x in prov[0]['candidate_sources']]
assert all(x['matches_current_model'] for x in checks)
save('source_hashes.csv',checks)
stage=ROOT/SHORT/'replays/source5_mac/staging'
fidelity=json.loads((stage/'reference/fidelity.json').read_text())
hash_checks=[]
for folder,section in [('inputs','input_sha256'),('reference','reference_sha256')]:
 for n,h in fidelity[section].items():
  p=stage/folder/n
  rec={'path':str(p.relative_to(ROOT)),'present':p.exists(),'expected_sha256':h}
  if p.exists():rec['hash_matches']=sha(p)==h;assert rec['hash_matches']
  hash_checks.append(rec)
ins=rows(stage/'inputs/inputs.csv');fr=rows(stage/'inputs/frames.csv');tx=rows(stage/'reference/tx.csv')
edge=lambda r:r['node'] in ['2','8'] and r['peer'] in ['2','8']
edgeins=[x for x in ins if edge(x)]
save('native_edge_inputs_0_330.csv',edgeins)
edgefr=[x for x in fr if (x['source'],x['destination']) in [('2','8'),('8','2')]]
save('native_edge_frames_0_330.csv',edgefr)
ids={x['frame_id'] for x in edgefr}
edgetx=[x for x in tx if ids.intersection(x['frame_ids'].split(';'))]
save('native_edge_tx_0_330.csv',edgetx)
win=[x for x in edgeins if 300000000000<=int(x['time_ns'])<330000000000]
fb=[x for x in edgefr if x['source']=='2' and x['destination']=='8' and x['is_ack']=='1']
fbids={x['frame_id'] for x in fb}
fbtx=[x for x in tx if fbids.intersection(x['frame_ids'].split(';')) and int(x['time_ns'])>=300000000000]
fbrx=[x for x in win if x['node']=='8' and x['kind']=='cancel_ack']
fbqueue=[x for x in win if x['node']=='2' and x['kind']=='enqueue' and x['frame_id'] in fbids]
data=[x for x in edgefr if x['source']=='8' and x['destination']=='2' and x['type']=='0']
summary={'archives':archives,'candidate_source_count':len(checks),'all_source_hashes_equal_between_returns':True,'all_source_hashes_equal_to_current_6000_model':True,'native_pins':{k:fidelity[k] for k in ['source_commit_gate','engine_commit_gate','observer_sha256']},'native_fidelity':fidelity,'available_file_hash_checks':hash_checks,'staged_native_coverage':{'inputs_rows':len(ins),'frames_rows':len(fr),'tx_rows':len(tx),'nodes':sorted(set(x['node'] for x in ins),key=int),'time_bounds_ns':[min(int(x['time_ns']) for x in ins),max(int(x['time_ns']) for x in ins)],'native_8_to_2_data_frame_records':len(data),'native_8_to_2_unique_data_sequences':len(set(x['sequence'] for x in data)),'native_2_to_8_feedback_frames_all_time':len(fb),'native_2_to_8_feedback_enqueues_300_330':len(fbqueue),'native_2_to_8_feedback_tx_300_330':len(fbtx),'native_node8_peer2_cancel_ack_300_330':len(fbrx),'native_node8_peer2_cancel_ack_unique_windows_300_330':len(set((x['sequence'],x['ack_bitmap'],x['dack_bitmap']) for x in fbrx)),'native_node8_peer2_nonzero_dack_windows_300_330':sum(int(x['dack_bitmap'])!=0 for x in fbrx)},'limitations':['Staged capture is native-only; MATLAB replay profile executes node5 only.','MAC received inputs have peer/time only, not DATA identity, receiver NSDP-before, or first-reception flag.','Cancel_ack bitmap inputs record the MAC cancellation boundary; they are not independent proof of HOP ownership or NWK release.','The returned ZIPs do not carry original native observer streams, tx_raw.csv, tx_wire_hex.csv, or tx_frames.csv.']}
(ROOT/'coverage_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'sources_verified':len(checks),'coverage':summary['staged_native_coverage']},indent=2))
