#!/usr/bin/env python3
"""Independent read-only audit of the returned partial seed-132 replay.

Run from workspace root: python node8_return2/redteam/audit_return.py
No MATLAB or ns-3 executions. Raw files remain untouched.
"""
import csv, collections, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
DATA=ROOT/'node8_return2/data'
CASE=DATA/'S132_1200'
KIT=ROOT/'node8_return/kit/node8case'
NATIVE=ROOT/'node8_1200/native/s132_1200'

def read(p): return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def rows(p,**kw):
    with p.open(newline='') as f: yield from csv.DictReader(f,**kw)
def write(name,x): (OUT/name).write_text(json.dumps(x,indent=2)+'\n')
def ns(x): return round(float(x)*1e9)

report=read(DATA/'report.json'); provenance=read(DATA/'provenance.json')
manifest=read(KIT/'FILES.json')
checks={}
checks['manifest_hash_matches']=sha(KIT/'FILES.json')==provenance['manifest_sha256']
checks['embedded_manifest_matches']=manifest==provenance['manifest']
files=[]
for x in manifest['files']:
    p=KIT/x['path']; files.append({'path':x['path'],'matched':p.exists() and sha(p)==x['sha256']})
checks['all_sealed_files_match']=all(x['matched'] for x in files)
resolved=[]
for x in provenance['resolved_matlab_files']:
    path=x['path'].replace('\\','/').split('/node8case/')[-1]
    p=KIT/path
    resolved.append({'name':x['name'],'path':path,'matched':p.exists() and sha(p)==x['sha256']})
checks['all_resolved_runtime_hashes_match']=all(x['matched'] for x in resolved)
checks['preflights_all_pass']=all(x['passed'] for x in report['preflights'])
write('provenance_check.json',{'checks':checks,'sealed_file_count':len(files),'resolved_file_count':len(resolved),'preflights':[{k:x[k] for k in ['name','passed']} for x in report['preflights']],'sealed_files':files,'resolved_files':resolved})

native_tx=list(rows(NATIVE/'fixture/tx_signatures.csv'))
heads=[r for r in native_tx if int(r['child_index'])==0]
ptx=[r for r in rows(CASE/'protocol_trace.csv') if r['Event']=='tx_start']
counts=collections.Counter(); txcmp=[]
for i,r in enumerate(ptx):
    node=int(r['NodeId']);counts[node]+=1;n=heads[i]
    txcmp.append({'global_ordinal':i+1,'actual_node':node,'native_node':int(n['source']),'actual_source_ordinal':counts[node],'native_source_ordinal':int(n['source_tx_ordinal']),'actual_time_ns':ns(r['TimeSeconds']),'native_time_ns':int(n['time_ns']),'identity_order_match':node==int(n['source']) and counts[node]==int(n['source_tx_ordinal']),'time_match':ns(r['TimeSeconds'])==int(n['time_ns'])})
with (OUT/'physical_tx_prefix.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=txcmp[0]);w.writeheader();w.writerows(txcmp)
tx_summary={'observed_tx_starts':len(ptx),'successful_context_checked':read(CASE/'random_summary.json')['native_transmissions_checked'],'all_observed_physical_source_ordinals_order_and_ns_times_equal':all(r['identity_order_match'] and r['time_match'] for r in txcmp),'last_tx_start':txcmp[-1], 'scope':'Includes the attempted mismatching TX start; it throws before Engine transmission completes and is not counted as a successful context check.'}
write('physical_tx_prefix_summary.json',tx_summary)

ndraws=[r for r in rows(NATIVE/'fixture/random_draws.csv') if int(r['rng_consumed'])]
key=lambda r:(int(r['node']),r['purpose'],int(r['ordinal']))
nd={key(r):r for r in ndraws}
requests=0;keys=[]; bad_times=[];bad_values=[];bad_context=[];interval_differences=[];unmatched=[]
for line in (CASE/'random_requests.jsonl').open():
    r=json.loads(line);requests+=1;k=key(r);keys.append(k);n=nd[k]
    if ns(r['time_s'])!=int(n['time_ns']):bad_times.append({'key':k,'actual':ns(r['time_s']),'native':int(n['time_ns'])})
    if float(r['value'])!=float(n['value']):bad_values.append(k)
    if not r['context_matched']:unmatched.append(k)
    for field,value in r['actual'].items():
        if field not in n or field=='reported_nodes':continue
        wanted=n[field]
        if field.endswith('_ns'):
            if value is not None and wanted and float(value)!=float(wanted):interval_differences.append({'key':k,'field':field,'actual':value,'native':wanted})
            continue
        if isinstance(value,str):same=value==wanted
        elif field=='probability':same=abs(float(value)-float(wanted))<=1e-12*max(abs(float(value)),abs(float(wanted)))
        else:same=value is None and wanted=='' or value is not None and wanted!='' and float(value)==float(wanted)
        if not same:bad_context.append({'key':k,'field':field,'actual':value,'native':wanted})
native_order=[key(r) for r in sorted(ndraws,key=lambda x:int(x['event_order']))[:requests]]
order_diffs=[{'index':i+1,'actual':a,'native':b} for i,(a,b) in enumerate(zip(keys,native_order)) if a!=b]
rng_summary={'request_count':requests,'time_mismatch_count':len(bad_times),'value_mismatch_count':len(bad_values),'semantic_context_mismatch_count':len(bad_context),'row_context_false_count':len(unmatched),'excluded_interval_timestamp_mismatch_count':len(interval_differences),'global_draw_order_difference_count':len(order_diffs),'first_global_draw_order_difference':order_diffs[:1],'first_excluded_interval_timestamp_difference':interval_differences[:1],'scope':'Request ns and values compared to fixture keyed by node/purpose/ordinal. Also checked global request order and excluded interval timing fields independently; reported_nodes intentionally excluded by issued profile-4 contract.'}
write('random_prefix_summary.json',rng_summary)
write('random_interval_differences.json',interval_differences)

# Extract transmitted payload directly from passive MAC wire bytes, independent
# of fixture normalizer and native HOP/application lineage join.
first=read(CASE/'first_divergence.json'); expected=first['expected']; expected=expected[0] if isinstance(expected,list) else expected
match_time=str(int(expected['time_ns']));node=str(first['node']); raw_hex=None;raw_frame=None
for line in (NATIVE/'run/mac-input.log').open():
    p=line.rstrip().split('|')
    if p[0]=='TXHEX' and p[1:4]==[match_time,node,'0']:raw_hex=p[-1]
    if p[0]=='TXFRAME' and p[1:4]==[match_time,node,'0']:raw_frame=p
assert raw_hex is not None and raw_frame is not None
b=bytes.fromhex(raw_hex); flags=b[9]; off=13
if flags&8:off+=16
if flags&32:off+=4
if flags&64:off+=2
if flags&16:off+=1+b[off]*5
wire_source=int.from_bytes(b[off:off+3],'big')
actual=first['actual']['children']; actual=actual[0] if isinstance(actual,list) else actual
native_lineage=[]
for r in rows(NATIVE/'run/observations.tsv',delimiter='\t'):
    if r['node']=='4' and r['event']=='hop_admit' and r['peer']=='5':
        d=json.loads(r['detail_json'])
        if int(d['sequence'])==int(expected['hop_sequence']):native_lineage.append(r)
native_admissions=[]
for r in rows(NATIVE/'run/ns3-trace.csv'):
    if r['event']=='app_admission' and r['success']=='1' and r['src']==str(wire_source) and r['sequence']==str(int(expected['native_app_sequence'])):native_admissions.append(r)
payload_summary={'actual':actual,'native_wire_network_source':wire_source,'fixture_network_source':int(expected['network_source']),'native_wire_hex_equals_fixture':raw_hex==expected['packet_hex'],'network_source_differs_independently_of_application_lineage':wire_source!=int(actual['network_source']),'native_raw_hop_admission':native_lineage,'native_raw_source_admission':native_admissions,'raw_TXFRAME':raw_frame,'raw_TXHEX':raw_hex}
write('payload_identity_proof.json',payload_summary)

# Ordered sink is passive and streamed. Scan only relevant rows to avoid
# retaining the 2-GB log in memory, while checking contiguous observation IDs.
seen=0;gaps=[];context_counts=collections.Counter();first_context_bad=None;tx_attempt_timing=[]
for line in (CASE/'ordered_events.jsonl').open():
    # The sink is JSONL and order integrity requires every row.
    r=json.loads(line);seen+=1
    if r['observation_order']!=seen:gaps.append({'row':seen,'observation_order':r['observation_order']})
    if r['kind']=='physical_tx_context':
        d=r['details'];bad=d.get('mismatches',[]);context_counts['failed' if bad else 'passed']+=1
        if bad and first_context_bad is None:first_context_bad=r
ordered={'rows':seen,'observation_order_gaps':len(gaps),'physical_contexts':dict(context_counts),'first_failed_context':first_context_bad}
write('ordered_sink_check.json',ordered)

statistics=read(CASE/'partial_statistics.json'); service=read(CASE/'observer_status.json'); receiver=read(CASE/'receiver_timing_summary.json'); transport=read(CASE/'transport_timing_summary.json')
omissions={'protocol':statistics['OmittedTraceRecords'],'phy':statistics['OmittedPhyTraceRecords'],'application_admission':statistics['OmittedApplicationAdmissionRecords'],'service':service['OmittedServiceRecords'],'receiver_timing':receiver['Omitted'],'transport_timing':transport['Omitted'],'ordered_sink_gaps':len(gaps)}
result={'schema':'csr-node8-return2-independent-redteam-v1','provenance_checks':checks,'physical_tx':tx_summary,'random_prefix':rng_summary,'omissions':omissions,'all_recorded_partial_streams_complete':all(v==0 for v in omissions.values()),'first_failed_physical_context_ns':int(expected['time_ns']),'native_source_from_raw_wire':wire_source,'matlab_source':int(actual['network_source']),'wire_disagreement_independent_of_lineage':wire_source!=int(actual['network_source']),'requested_stop_seconds':1200,'actual_stop_seconds':read(CASE/'case_summary.json')['reached_time_s'],'full_parity_established':False,'target_percent':20,'native_context_passes':context_counts['passed'],'native_context_failures':context_counts['failed']}
write('audit.json',result)
print(json.dumps(result,indent=2))
