#!/usr/bin/env python3
"""Validate T21 derived evidence against the accepted T20 input inventory."""
import argparse,csv,json,hashlib
from pathlib import Path
from collections import Counter
from analyze_native import sha,CANDIDATE_SHA256

def audit(source,out):
 candidate=source/'evidence/tranche-20-candidate.json';assert sha(candidate)==CANDIDATE_SHA256
 inventory={x['path']:x for x in json.loads(candidate.read_text())['ReferenceFileInventory']};proofs=[]
 for seed in(128,129,130):
  p=source/('evidence/tranche-7-ns3-reference/campus_multihop_6000' if seed==128 else f'evidence/tranche-20-ns3-reference/s{seed}')
  d=json.loads((out/f's{seed}.json').read_text())
  for name,key in [('manifest.json','manifest_sha256'),('ns3-trace.csv.gz','trace_gzip_sha256')]:
   path=p/name;digest=sha(path);assert digest==d['input'][key]==inventory[path.relative_to(source).as_posix()]['sha256']
  agg=p/'ns3-aggregates.provenance.json';assert sha(agg)==inventory[agg.relative_to(source).as_posix()]['sha256'];a=json.loads(agg.read_text())
  assert d['input']['trace_raw_sha256']==a['input']['sha256'];assert d['input']['trace_raw_bytes']==a['input']['size_bytes'];assert d['input']['last_event_time_s']<6000
  assert d['nsdp_snapshot_mismatch_count']==0 and d['queue_snapshot_mismatch_count']==0 and not d['unmatched_episode_events']
  if seed==128:
   assert not d['full_custody_telemetry_available'] and not d['nsdp_state'] and not d['pending_enqueues']
   assert {x['source']:x['unique_delivered'] for x in d['flows']}=={int(x['src']):x['count'] for x in a['delay_matching']['matched_by_flow']}
   assert {x['source']:x['unmatched_sends'] for x in d['flows']}=={int(x['src']):x['count'] for x in a['delay_matching']['unmatched_sends']}
  else:
   metrics=p/'native-applications.json';assert sha(metrics)==inventory[metrics.relative_to(source).as_posix()]['sha256'];native=json.loads(metrics.read_text())
   for flow in d['flows']:
    other=next(f for f in native['flows'] if f['source']==flow['source'])
    for k in('admitted','unique_delivered','duplicate_delivery_events','unmatched_sends'):assert flow[k]==other[k]
    assert abs(flow['first_delivery_delay_s']['mean']-other['first_delivery_delay_s']['mean'])<1e-9
   joins=json.loads((out/f's{seed}-outcome-joins.json').read_text());assert joins['input_binding']==d['input'] and not joins['capacity_release_without_admission']
   admission=Counter((int(r['node']),int(r['source'])) for r in csv.DictReader((out/f's{seed}-capacity-episodes.csv').open()))
   admission.update((r['node'],r['source']) for r in joins['capacity_pending_at_stop'])
   expected=Counter()
   for r in joins['threshold_histograms']:expected[r['node'],r['source']]+=r['admissions']
   assert admission==expected
   pending=Counter((r['node'],r['source']) for r in d['pending_enqueues']);pending.update((r['node'],r['source']) for r in d['pending_hop'])
   assert all(pending[r['node'],r['source']]==r['last'] for r in d['nsdp_state'])
  proofs.append({'seed':seed,'rows':d['input']['rows'],'gzip_and_raw_hash_bound':True,'exact_app_totals_reconciled':True,'mean_delays_reconciled_to_saved_metrics':None if seed==128 else True,'occupancy_and_custody_reconciled':None if seed==128 else True})
 result={'schema':'csr-t21-native-audit-v1','status':'passed','candidate_sha256':CANDIDATE_SHA256,'proofs':proofs,'new_simulations':0,'matlab_executed':False,'source_files_changed':0,'script_sha256':{p.name:sha(p) for p in out.glob('*.py')}}
 (out/'audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':
 base=Path(__file__).resolve().parents[2];p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,default=base/'csr20');p.add_argument('--out',type=Path,default=Path(__file__).resolve().parent);a=p.parse_args();audit(a.source_root,a.out)
