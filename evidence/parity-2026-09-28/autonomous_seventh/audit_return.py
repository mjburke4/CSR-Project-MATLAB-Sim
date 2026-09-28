#!/usr/bin/env python3
"""Verify the actual I owner return; no MATLAB execution or guard changes."""
from pathlib import Path
from collections import Counter
import csv,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]; HERE=Path(__file__).resolve().parent
DATA=HERE/'data'; ISSUED=ROOT/'autonomous_sixth/kit/autocase'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def main():
 archive=ROOT/'upload/out_auto_20260928_073809.zip'
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for name in z.namelist(): assert z.read(name)==(DATA/name).read_bytes(),name
  members=len(z.namelist())
 report=read(DATA/'report.json'); provenance=read(DATA/'provenance.json'); manifest=read(ISSUED/'FILES.json')
 assert provenance['manifest']==manifest
 for row in manifest['files']: assert sha(ISSUED/row['path'])==row['sha256'],row['path']
 assert len(manifest['files'])==294 and not report['error_identifier'] and report['import_preflight']['passed']
 passed={}
 for field,count in [('key_request_preflight',7),('check_gate_preflight',8),('population_preflight',6),('route_admission_preflight',8),('request_wire_preflight',6),('no_path_wire_preflight',3)]:
  pre=report[field];assert pre['passed'] and len(pre['checks'])==count and all(r['passed'] for r in pre['checks']);passed[field]=count
 reuse=report['accepted_natural_reuse']
 assert all(reuse[k] for k in ['reused','runtime_matches','configuration_matches','prefix_gate_recomputed'])
 assert not reuse['fresh_natural_simulation_executed']
 for name in ['protocol_trace.csv','phy_trace.csv','application_admission_trace.csv']:
  assert (DATA/'A_natural'/name).read_bytes()==(ISSUED/'ref/matlab'/name).read_bytes()
 folder=DATA/'I_control_wire'; item=read(folder/'case_summary.json'); summary=read(folder/'random_summary.json')
 assert item['diagnostic_status']=='context_divergence' and item['error_identifier']=='autocase:TxContextDivergence'
 assert item['reached_time_s']==25.74
 requests=[json.loads(s) for s in (folder/'random_requests.jsonl').read_text().splitlines()]
 assert len(requests)==290 and all(r['context_matched'] for r in requests)
 assert all(r['value']==r['expected']['value'] for r in requests)
 assert sum(r['consumed'] for r in summary['counts'])==290
 assert summary['draw_count']==290 and summary['native_transmissions_checked']==49 and summary['first_time_difference']==[]
 events=[json.loads(s) for s in (folder/'ordered_events.jsonl').read_text().splitlines()]
 tx=[r for r in events if r['kind']=='physical_tx_context']
 assert len(tx)==50 and sum(not r['details']['mismatches'] for r in tx)==49
 repaired=[r for r in tx if r['details']['native_semantic_tx_id']==4294967314]
 assert len(repaired)==1 and not repaired[0]['details']['mismatches']
 a=repaired[0]['details']['actual'];assert a['child_count']==3 and a['total_wire_bytes']==63
 assert [r['wire_bytes'] for r in a['children']]==[16,16,31]
 d=read(folder/'first_divergence.json')
 assert d['fields']==['child3.hop_sequence'] and d['node']==3 and d['ordinal']==17
 assert d['actual']['total_wire_bytes']==109 and d['actual']['child_count']==3
 c=d['actual']['children'][2];e=d['expected'][2]
 assert c['hop_sequence']==1 and e['hop_sequence']==4
 assert c['kind']==e['kind']==4 and c['hop_destination']==e['hop_destination']==16777215
 assert c['wire_bytes']==e['wire_bytes']==19 and c['ackable']==e['ackable']==0
 assert c['discover_sequence']==e['discover_sequence']==1 and c['discover_subtype']==e['discover_subtype']=='broadcast'
 observer=read(folder/'observer_status.json');timing=read(folder/'transport_timing_summary.json')
 assert observer['Complete'] and observer['OmittedServiceRecords']==0
 assert timing['Mode']=='nanoseconds' and timing['Omitted']==0
 raw={}
 for fn in ['protocol_trace.csv','phy_trace.csv','application_admission_trace.csv']:
  with (folder/fn).open() as f: raw[fn]=sum(1 for _ in csv.DictReader(f))
 assert raw['application_admission_trace.csv']==0
 result=dict(schema='csr-autonomous-control-wire-return-v1',status='pass',archive=archive.name,archive_sha256=sha(archive),archive_members=members,issued_manifest_sha256=sha(ISSUED/'FILES.json'),issued_bound_files=len(manifest['files']),runtime=report['runtime'],import_preflight_passed=True,matlab_passed_component_checks=passed,accepted_natural_reused=True,case=dict(name='I_control_wire',endpoint_s=25.74,requests_consumed_matched=290,consumed_by_purpose=dict(Counter(r['purpose'] for r in requests)),verified_transmissions=49,rejected_transmissions=1,first_time_difference=[],previous_wire_guard_cleared=True,raw_rows=raw,ordered_event_rows=len(events),timing_records=timing['Count'],service_records=observer['CapturedServiceRecords'],wall_seconds=item['wall_seconds'],stop_fields=d['fields'],discovery_outer_sequence_actual=1,discovery_outer_sequence_native=4,discovery_payload_session_both=1),target_percent=15,network_parity_established=False,scope='Actual startup capture ends before application traffic begins at300 seconds; NoPath only validated by separate public component checks.')
 (HERE/'return_audit.json').write_text(json.dumps(result,indent=2)+'\n')
 (HERE/'return_input_manifest.json').write_text(json.dumps([dict(path=p.relative_to(DATA).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(DATA.rglob('*')) if p.is_file()],indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__': main()
