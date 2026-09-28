#!/usr/bin/env python3
"""Bind the actual G/H owner results to the issued kit; no MATLAB execution."""
from pathlib import Path
from collections import Counter
import csv, hashlib, json, zipfile
ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
DATA=HERE/'data'
ISSUED=ROOT/'autonomous_fifth/kit/autocase'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def main():
 archive=ROOT/'upload/out_auto_20260928_071516.zip'
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for name in z.namelist(): assert z.read(name)==(DATA/name).read_bytes(),name
  members=len(z.namelist())
 report,provenance=read(DATA/'report.json'),read(DATA/'provenance.json')
 manifest=read(ISSUED/'FILES.json')
 assert provenance['manifest']==manifest
 for row in manifest['files']: assert sha(ISSUED/row['path'])==row['sha256'],row['path']
 assert len(manifest['files'])==247 and not report['error_identifier']
 assert report['import_preflight']['passed']
 passed={}
 for field,count in [('key_request_preflight',7),('check_gate_preflight',8),('population_preflight',6),('route_admission_preflight',8)]:
  pre=report[field];assert pre['passed'] and len(pre['checks'])==count and all(r['passed'] for r in pre['checks'])
  passed[field]=count
 reuse=report['accepted_natural_reuse']
 assert all(reuse[k] for k in ['reused','runtime_matches','configuration_matches','prefix_gate_recomputed'])
 assert not reuse['fresh_natural_simulation_executed']
 for name in ['protocol_trace.csv','phy_trace.csv','application_admission_trace.csv']:
  assert (DATA/'A_natural'/name).read_bytes()==(ISSUED/'ref/matlab'/name).read_bytes()
 cases=[]
 for name,end,nr,nt in [('G_population',14.534,97,16),('H_admission_route',25.298,276,47)]:
  folder=DATA/name;item=read(folder/'case_summary.json');summary=read(folder/'random_summary.json')
  assert item['diagnostic_status']=='context_divergence' and item['error_identifier']=='autocase:TxContextDivergence'
  assert item['reached_time_s']==end
  requests=[json.loads(s) for s in (folder/'random_requests.jsonl').read_text().splitlines()]
  assert len(requests)==nr and all(r['context_matched'] for r in requests)
  assert all(r['value']==r['expected']['value'] for r in requests)
  assert sum(r['consumed'] for r in summary['counts'])==nr
  assert summary['draw_count']==nr and summary['native_transmissions_checked']==nt
  assert summary['first_time_difference']==[]
  old_draw=[r for r in requests if r['node']==1 and r['purpose']=='mac_slot' and r['ordinal']==8]
  assert len(old_draw)==1 and old_draw[0]['actual']['active_nodes']==2 and old_draw[0]['value']==13
  events=[json.loads(s) for s in (folder/'ordered_events.jsonl').read_text().splitlines()]
  tx=[r for r in events if r['kind']=='physical_tx_context']
  assert sum(not r['details']['mismatches'] for r in tx)==nt
  assert len(tx)==nt+1 and tx[-1]['details']['mismatches']
  repaired=[r for r in tx if r['details']['native_semantic_tx_id']==21474836483]
  assert len(repaired)==1 and not repaired[0]['details']['mismatches']
  assert repaired[0]['details']['actual']['child_count']==4 and repaired[0]['details']['actual']['total_wire_bytes']==82
  old_tx=[r for r in tx if r['details']['native_semantic_tx_id']==4294967303]
  assert len(old_tx)==1
  divergence=read(folder/'first_divergence.json')
  if name=='G_population':
   assert divergence['actual']['child_count']==8 and divergence['actual']['total_wire_bytes']==241
   assert divergence['expected'][0]['child_count']==7 and divergence['expected'][0]['total_wire_bytes']==215
  else:
   assert not old_tx[0]['details']['mismatches']
   assert old_tx[0]['details']['actual']['child_count']==7 and old_tx[0]['details']['actual']['total_wire_bytes']==215
   assert divergence['fields']==['parent.total_wire_bytes','child1.wire_bytes','child2.wire_bytes']
   assert divergence['actual']['total_wire_bytes']==77 and divergence['expected'][0]['total_wire_bytes']==63
   assert [x['wire_bytes'] for x in divergence['actual']['children']]==[23,23,31]
   assert [x['wire_bytes'] for x in divergence['expected']]==[16,16,31]
   for a,e in zip(divergence['actual']['children'][:2],divergence['expected'][:2]):
    assert a['routing_section_hex']==e['routing_section_hex']
    assert e['routing_section_origin']=='normalized_legacy_request'
  observer=read(folder/'observer_status.json');timing=read(folder/'transport_timing_summary.json')
  assert observer['Complete'] and observer['OmittedServiceRecords']==0
  assert timing['Mode']=='nanoseconds' and timing['Omitted']==0
  raw={}
  for fn in ['protocol_trace.csv','phy_trace.csv','application_admission_trace.csv']:
   with (folder/fn).open() as f: raw[fn]=sum(1 for _ in csv.DictReader(f))
  assert raw['application_admission_trace.csv']==0
  cases.append(dict(name=name,endpoint_s=end,requests_consumed_matched=nr,consumed_by_purpose=dict(Counter(r['purpose'] for r in requests)),verified_transmissions=nt,rejected_transmissions=1,first_time_difference=summary['first_time_difference'],mac_population_guard_cleared=True,previous_extra_route_removed=name=='H_admission_route',raw_rows=raw,ordered_event_rows=len(events),timing_records=timing['Count'],service_records=observer['CapturedServiceRecords'],wall_seconds=item['wall_seconds'],stop_fields=divergence['fields']))
 result=dict(schema='csr-autonomous-population-route-return-v1',status='pass',archive=archive.name,archive_sha256=sha(archive),archive_members=members,issued_manifest_sha256=sha(ISSUED/'FILES.json'),issued_bound_files=len(manifest['files']),runtime=report['runtime'],import_preflight_passed=True,matlab_passed_component_checks=passed,accepted_natural_reused=True,cases=cases,target_percent=15,network_parity_established=False,scope='Actual startup captures stop before application traffic begins at 300 seconds.')
 (HERE/'return_audit.json').write_text(json.dumps(result,indent=2)+'\n')
 (HERE/'return_input_manifest.json').write_text(json.dumps([dict(path=p.relative_to(DATA).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(DATA.rglob('*')) if p.is_file()],indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__': main()
