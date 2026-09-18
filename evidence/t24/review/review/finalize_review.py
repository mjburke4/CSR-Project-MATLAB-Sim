#!/usr/bin/env python3
"""Compare separately reconstructed T24 evidence and bind the reviewed gate."""
import argparse,csv,hashlib,json,zipfile
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jread(p):return json.loads(p.read_text())
def close(a,b):return abs(a-b)<1e-5

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--tranche-root',type=Path,default=Path(__file__).resolve().parents[1])
 parser.add_argument('--baseline-root',type=Path,default=Path(__file__).resolve().parents[2]/'t23-return-review/issued-overlay')
 args=parser.parse_args();root=args.tranche_root.resolve();baseline=args.baseline_root.resolve()
 raw=jread(root/'review/independent-raw.json')['results'];lifetimes=jread(root/'review/repeat-lifetime-audit.json')['results']
 candidate=jread(baseline/'evidence/tranche-23-candidate.json')
 assert sha(baseline/'evidence/tranche-23-candidate.json')=='b40afd3755ceb47576ea2c9854b4af15a14cebcf87024331e67bf53e069f0818'
 ref={x['path']:x for x in candidate['ReferenceFileInventory']};pins={}
 source_pins=jread(root/'review/pinned-source.json')
 for b in source_pins['files']:
  assert sha(root/'review/pinned'/Path(b['path']).name)==b['sha256']
 verified=[]
 for a in raw:
  seed=a['seed'];assert not a['errors']
  primary=jread(root/f'analysis/results/s{seed}-census.json');assert primary['verification']['passed']
  assert a['trace_sha256']==primary['input']['gzip_sha256'];assert a['rows']==primary['input']['rows']
  for key,count in a['event_counts'].items():assert primary['event_counts'][key]==count,(seed,key)
  for stem in ('ns3-trace.csv.gz','scenario.csv','ns3-aggregates.provenance.json'):
   rel=f'evidence/tranche-20-ns3-reference/s{seed}/{stem}';digest=sha(baseline/rel)
   assert digest==ref[rel]['sha256'],rel
   assert (baseline/rel).stat().st_size==ref[rel]['bytes']
   pins[rel]=digest
  flowmap={(x['node'],x['source'],x['destination']):x for x in primary['flows']}
  assert len(flowmap)==len(a['flows'])
  for f in a['flows']:
   p=flowmap[f['node'],f['src'],f['dst']]
   assert f['enqueues']==p['all_instances']['enqueues']
   assert f['unique_applications']==p['distinct_application_identities']
   assert f['repeated_enqueues']==p['repeat_enqueue_count']
   assert f['applications_repeated']==p['identities_enqueued_more_than_once']
   assert f['max_enqueues_per_app']==p['maximum_enqueues_of_one_identity']
   assert f['nsdp_owners_at_stop']==p['nsdp']['at_stop']
   assert f['peak_nsdp']==p['nsdp']['peak']
   assert close(f['nsdp_owner_seconds_300_6000'],p['nsdp']['area_owner_seconds'])
  with (root/f'analysis/results/s{seed}-owners.csv').open(newline='') as f:
   owners=list(csv.DictReader(f))
  by_event={int(x['enqueue_event']):x for x in owners}
  own=next(x for x in lifetimes if x['seed']==seed);assert not own['errors']
  assert own['repeated_totals']['count']==sum(x['repeat_enqueue_count'] for x in primary['flows'])
  for r in own['repeated_instances']:
   p=by_event[r['enqueue_event']]
   for k,l in [('node','node'),('source','source'),('destination','destination'),('application_sequence','app_sequence'),('ordinal','identity_ordinal'),('other_owners_at_enqueue','same_app_nsdp_owners_before_enqueue'),('forward_event','forward_event'),('admission_event','hop_admission_event'),('completion_event','completion_event'),('hop_sequence','hop_sequence')]:assert r[k]==int(p[l]),(seed,k,r,p)
   for k,l in [('enqueue_s','enqueue_s'),('forward_s','forward_s'),('admission_s','hop_admission_s'),('completion_s','completion_s'),('capacity_release_s','capacity_release_s')]:assert close(r[k],float(p[l]))
   assert r['completion_reason']==p['completion_reason']
  for k,l in [('custody_owner_seconds','nsdp_owner_seconds'),('waiting_owner_seconds','nwk_wait_owner_seconds'),('hop_capacity_seconds','hop_capacity_owner_seconds')]:
   assert close(own['repeated_totals'][k],sum(x['repeated_instances'][l] for x in primary['flows']))
  focus=flowmap[8,7,1];assert focus['repeat_enqueue_count']==0
  service=jread(root/f'analysis/results/s{seed}-service-summary.json')
  assert not any('tx_' in k or 'transmission_attempt' in k for k in service),'Incomplete TX attribution must not be published'
  assert service['matched_upstream_admissions']==own['repeated_totals']['count']
  assert service['propagated_upstream_repeated_instances']==4
  with (root/f'analysis/results/s{seed}-repeated-owner-lineage.csv').open(newline='') as f:
   lineage=list(csv.DictReader(f))
  assert len(lineage)==own['repeated_totals']['count']
  for r in lineage:
   owner=by_event[int(r['enqueue_event'])];upstream=by_event[int(r['upstream_enqueue_event'])]
   assert owner['ingress_peer']==upstream['node'] and owner['node']==upstream['next_hop']
   assert owner['ingress_hop_sequence']==upstream['hop_sequence']
   assert all(owner[k]==upstream[k] for k in ('source','destination','app_sequence'))
   if owner['ingress_same_hop_replay']!='True':assert int(upstream['identity_ordinal'])>1
  peak_shares={field:max(100*x['repeated_instances'][field]/x['all_instances'][field] for x in primary['flows'] if x['all_instances'][field]) for field in ('hop_capacity_owner_seconds','nsdp_owner_seconds')}
  verified.append({'seed':seed,'native_rows':a['rows'],'flow_count':len(flowmap),'owner_instances':len(owners),'repeat_instances':own['repeated_totals']['count'],'repeat_lifetimes_independently_matched':True,'propagated_copy_upstream_joins':4,'maximum_repeat_share_percent_by_node_and_flow':peak_shares,'node8_source7_repeat_count':0,'mean_node8_source7_nsdp':focus['nsdp']['mean_300_6000']})
 matlab=jread(root/'matlab/matlab-census.json');assert matlab['status']=='pass';assert matlab['script_sha256']==sha(root/'analyze_matlab.py')
 for result in matlab['results']:
  seed=result['seed'];case=root/f'inputs/t20/s{seed}'
  receipt=jread(case/'receipt.json');assert sha(case/'receipt.json')==result['receipt_sha256']==(case/'receipt.sha256').read_text().strip()
  assert receipt['identity']['CandidateSHA256']=='ba4cedf3551a0bc1fe31385108e1f33011d1c97211bba993b6061a2de31389c1'
  assert receipt['SourceFilesStableDuringRun'] and receipt['ReferenceFilesStableDuringRun']
  assert receipt['summary']['DurationSeconds']==6000 and receipt['summary']['DefaultContinuousTiming'] and receipt['summary']['Policy']=='actual-tx'
  inventory={x['path']:x for x in receipt['artifacts']}
  for rel,b in result['verified_artifacts'].items():assert sha(case/rel)==b['sha256']==inventory[rel]['sha256'];assert (case/rel).stat().st_size==b['bytes']==inventory[rel]['bytes']
  assert result['protocol_rows']==receipt['summary']['Performance']['ProtocolTraceRecords']
  assert result['repeat_enqueues']==0
  for f in result['flows']:
   assert f['enqueues']==f['released']+f['pending_at_stop'];assert f['enqueues']==f['submitted']+f['waiting_at_stop'];assert f['repeat_enqueues']==0
 checks=jread(root/'input-verification.json');assert checks['status']=='pass';assert checks['script_sha256']==sha(root/'verify_inputs.py')
 for n,b in checks['archives'].items():assert sha(root/'inputs/NS3 to MATLAB Network Simulation'/n)==b['sha256']
 with zipfile.ZipFile(root/'inputs/NS3 to MATLAB Network Simulation/t21review.zip') as z:
  assert z.read('SHA256SUMS.json')==(root/'inputs/t21review/SHA256SUMS.json').read_bytes()
 paths=['analysis/custody_census.py','analyze_matlab.py','verify_inputs.py','input-verification.json','matlab/matlab-census.json','matlab/matlab-flows.csv','T24_Review.md','README.md','review/source-method.md','review/independent_raw.py','review/independent-raw.json','review/audit_repeat_lifetimes.py','review/repeat-lifetime-audit.json','review/pinned-source.json','review/finalize_review.py']
 paths += [p.relative_to(root).as_posix() for p in sorted((root/'analysis/results').glob('*')) if p.is_file()]
 for p in ('analysis/service_lineage.py','analysis/README.md'):
  if (root/p).exists():paths.append(p)
 paths += [p.relative_to(root).as_posix() for p in sorted((root/'review/pinned').glob('*')) if p.is_file()]
 paths += [p.relative_to(root).as_posix() for p in sorted((root/'review').glob('s*.json')) if p.is_file()]
 if (root/'review/propagated-repeat-joins.json').exists():paths.append('review/propagated-repeat-joins.json')
 review={'schema':'csr-tranche24-independent-gate-v1','status':'pass','blocking_findings':[],
   'scope':'Source semantics, independent native identity/state census and all repeated-owner lifetimes, MATLAB analyzer code and bound-receipt verification, input validator and final report review.',
   'native_results':verified,'native_input_bindings':pins,'native_raw_reconstruction_total_rows':sum(x['rows'] for x in raw),
   'matlab_protocol_records_receipt_verified':sum(x['protocol_rows'] for x in matlab['results']),
   'matlab_independent_full_rescan':False,
   'matlab_review':'Code, receipt hashes, complete-protocol count, zero-repeat result, final conservation and T21 crosschecks reviewed. No fresh MATLAB execution.',
   'source_conclusions':['Distinct native owner instances are observable; zero-DSCP FIFO resolves matching per application.','DACK NSDP custody ends at completion; HOP capacity continues until delayed release.','Node8/source7 has zero repeated enqueue identities in both full-campus runs.','All 19 repeated owners elsewhere overlap an earlier owner and are forwarded, completed and capacity-released by stop.','tx_start identifies only the leading aggregate member; per-owner OTA counts and airtime are unavailable.'],
   'engineering_gate':'Accept T24 offline diagnostic; retain default, keep rare duplicate contract discrepancy documented, no immediate production change justified.',
   'limitations':['Observational results do not establish counterfactual delivery impact.','Rare downstream repeats may affect later stochastic event history.','No final unique delivery is assigned to a specific duplicate owner.','Two detailed native seeds do not establish universal behavior; historical128 lacks equivalent telemetry.'],
   'reviewed_files':{p:{'sha256':sha(root/p),'bytes':(root/p).stat().st_size} for p in sorted(set(paths))}}
 (root/'review/independent-review.json').write_text(json.dumps(review,indent=2)+'\n')
 print(json.dumps({'status':'pass','native_rows':review['native_raw_reconstruction_total_rows'],'repeated_owner_lifetimes':sum(x['repeat_instances'] for x in verified),'reviewed_files':len(review['reviewed_files'])}))
if __name__=='__main__':main()
