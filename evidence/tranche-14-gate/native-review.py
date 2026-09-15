"""Independent read-only T14 native trace/inventory audit. No MATLAB execution."""
from pathlib import Path
from collections import Counter
import csv, hashlib, json, struct
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return list(csv.DictReader(p.open()))
def hx(x):return struct.pack('>d',x).hex()
def main():
 native=ROOT/'t14n/native/pre'; source=ROOT/'csr14'; output=ROOT/'t14n/review-native.json'
 baseline=json.loads((source/'evidence/t13/source.json').read_text())
 assert len(baseline)==271 and sum(r['path'].endswith('.m') for r in baseline)==138
 assert all(sha(source/r['path'])==r['sha256'] for r in baseline)
 result={}
 for case in ['tie_early','tie_late','before','after','continuous','quantized']:
  directory=native/case; e=rows(directory/'events.csv'); b=rows(directory/'boundary.csv'); checks=rows(directory/'checks.csv')
  assert len(b)==1 and len(checks)==37 and all(x['pass']=='1' for x in checks)
  assert [int(x['order']) for x in e]==list(range(1,len(e)+1))
  assert all(hx(float(x['time_seconds_dec']))==x['time_seconds_hex'] for x in e)
  for key in ['tx','duration','tick','arm','arrival','arrival_minus_tick']:
   assert hx(float(b[0][key+'_seconds_dec']))==b[0][key+'_seconds_hex']
  assert int(b[0]['wire_payload_bytes'])==89 and int(b[0]['segment_count'])==2
  assert int(b[0]['tx_time_ns'])==3120000000 and int(b[0]['duration_ns'])==24960000
  assert int(b[0]['ingress_event_id'])>0
  assert int(b[0]['arm_time_ns'])==(3144960998 if case=='tie_late' else 3120000000)
  tx=[x for x in e if x['phase']=='aggregate_tx']; ingress=[x for x in e if x['phase']=='ingress_before']; ack=[x for x in e if x['phase']=='ack_tx']; delivery=[x for x in e if x['phase']=='deliver']; feedback=[x for x in e if x['phase']=='feedback_ingress']
  assert len(tx)==6 and [(x['kind'],x['peer'],x['hop_seq']) for x in tx[:2]]==[('ACK','4','4'),('DATA','1','3')]
  assert [(x['app_source'],x['app_id']) for x in delivery]==[('5','1'),('5','2'),('5','3')]
  assert len(ingress)==1 and len(feedback)==5+len(ack)
  assert all(x['kind']=='ACK' and x['peer']=='4' and x['hop_seq']=='4' and x['ack_bits']=='15' for x in tx if x['kind']=='ACK')
  follows=case in ['tie_late','after']; assert (int(ingress[0]['order'])>int(ack[0]['order']))==follows
  assert int(ack[0]['time_ns'])==3144961000 and len(ack)==5+int(follows)
  assert (ack[0]['hop_seq'],ack[0]['ack_bits'])==(('2','3') if follows else ('3','7'))
  assert all(x['hop_seq']=='3' and x['ack_bits']=='7' and x['dack_bits']=='0' for x in ack[int(follows):])
  identity=lambda x:(x['node'],x['peer'],x['kind'],x['app_source'],x['app_id'],x['hop_seq'],x['ack_bits'],x['dack_bits'])
  sent=Counter(identity(x) for x in tx+ack if x['kind']=='ACK')
  received=Counter((x['peer'],x['node'],x['kind'],x['app_source'],x['app_id'],x['hop_seq'],x['ack_bits'],x['dack_bits']) for x in feedback)
  assert sent==received
  settled=[x for x in e if x['phase']=='settled']; assert len(settled)==3 and all(x['ack_queue']=='0' and x['data_queue']=='0' for x in settled)
  result[case]={'events':len(e),'checks':len(checks),'delivery_count':3,'source5_mixed_aggregates':1,'source5_additional_ack_frames':4,'gateway_ack_frames':len(ack),'first_ack_sequence':int(ack[0]['hop_seq']),'first_ack_bitmap':ack[0]['ack_bits'],'data_precedes_first_ack':not follows,'all_feedback_ingress_conserved':True,'queues_drained':True,'artifact_sha256':{p.name:sha(p) for p in directory.iterdir() if p.is_file()}}
 output.write_text(json.dumps({'schema':'csr-tranche14-independent-native-review-v1','status':'passed','reviewer_executed_matlab':False,'reviewer_reran_native':False,'source_baseline_files_verified':271,'matlab_baseline_files_verified':138,'case_count':6,'native_check_count':sum(x['checks'] for x in result.values()),'native_event_count':sum(x['events'] for x in result.values()),'cases':result},indent=2)+'\n')
 print(output)
if __name__=='__main__':main()
