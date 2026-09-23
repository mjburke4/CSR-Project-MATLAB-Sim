#!/usr/bin/env python3
"""Freeze accepted 128-130 campus data for T25; execute no simulator.

The original owner archives and accepted T20 review are immutable inputs.
Counts and delay sums are reconstructed from receipt-bound application tables
and original native first-delivery identities, then compared to that review.
"""
import argparse
from collections import Counter, defaultdict
import copy
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import sys
import zipfile
import tranche25_metrics as metric

T20_OWNER='41ee42fd72d3246b005cffa6eb0731aef1f465ac19747be82feb481571a72861'
T19_OWNER='525758669b8f84fa5dada46e293b8482980ef389efc5408ff056aac0e804ee30'
T20_REVIEW='2d4dfbb66aa657cbfa230f3cf088c4be3815e0558e5573fbc9ba143aa4800b79'
T20_ACCEPTANCE='69d9bafef93c64a674e8226a434c7c1a5d3b7ebb6f6f2fb76e64461fc497bc28'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def js(path):return json.loads(Path(path).read_text())
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def original_snapshot(root,folder,archive,acceptance):
    raw=archive.read('source.json')
    digest=hashlib.sha256(raw).hexdigest()
    assert digest==acceptance['source_snapshot_sha256']
    path=root/f'evidence/{folder}/source.json';path.write_bytes(raw)
    for binding in json.loads(raw):
        assert sha(root/binding['path'])==binding['sha256'],binding['path']
    return path.relative_to(root).as_posix(),digest

def matlab_run(archive,case,old):
    receipt_bytes=archive.read(case+'/receipt.json')
    assert hashlib.sha256(receipt_bytes).hexdigest()==archive.read(case+'/receipt.sha256').decode().strip()
    receipt=json.loads(receipt_bytes)
    assert receipt['status']=='completed'
    bindings={r['path']:r for r in receipt['artifacts']}
    member='analysis/applications.csv';raw=archive.read(case+'/'+member)
    assert len(raw)==bindings[member]['bytes'] and hashlib.sha256(raw).hexdigest()==bindings[member]['sha256']
    counts=defaultdict(Counter);latency=defaultdict(list);seen=set()
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
        key=int(row['PacketId']);source=int(row['SourceId'])
        assert key not in seen;seen.add(key)
        counts[source]['admitted']+=1;counts[source][row['Outcome']]+=1
        if row['Outcome']=='delivered':
            v=float(row['LatencySeconds']);assert math.isfinite(v) and v>=0
            latency[source].append(v)
    source=copy.deepcopy(old)
    for row in source['flows']:
        node=row['source'];c=counts[node]
        for k in ('admitted','delivered','dropped','pending'):assert c[k]==row[k],(case,node,k)
        values=latency[node];total=math.fsum(values);mean=total/len(values) if values else None
        assert (mean is None and row['delivered_latency']['mean_s'] is None) or math.isclose(mean,row['delivered_latency']['mean_s'],rel_tol=1e-12,abs_tol=1e-8)
        row['delivered_latency'].update(count=len(values),mean_s=mean,sum_s=total)
    return metric.normalize_matlab(source),{'receipt_sha256':hashlib.sha256(receipt_bytes).hexdigest(),
        'application_table_sha256':hashlib.sha256(raw).hexdigest(),'application_rows':len(seen)}

def native_run(directory,old):
    sent={};received=set();latency=defaultdict(list);duplicates=Counter();events=0
    with gzip.open(directory/'ns3-trace.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            events+=1
            if row['event'] not in ('app_send','nwk_delivery'):continue
            key=tuple(int(row[k]) for k in ('src','dst','sequence'));t=float(row['time_s'])
            assert 0<=t<6000
            if row['event']=='app_send':
                assert key not in sent;sent[key]=t
            else:
                assert key in sent and t>=sent[key]
                if key in received:duplicates[key[0]]+=1
                else:received.add(key);latency[key[0]].append(t-sent[key])
    override={}
    for row in old['flows']:
        source=row['source'];values=latency[source]
        assert sum(k[0]==source for k in sent)==row['admitted']
        assert len(values)==row['delivered']
        assert duplicates[source]==row['duplicate_delivery_events']
        total=math.fsum(values);mean=total/len(values) if values else None
        if 'first_delivery_delay_s' in row:
            assert math.isclose(mean,row['first_delivery_delay_s']['mean'],rel_tol=1e-12,abs_tol=1e-8)
        override[source]={'count':len(values),'mean':mean,'sum_s':total}
    return metric.normalize_native(old,delay_override=override),{'compressed_trace_sha256':sha(directory/'ns3-trace.csv.gz'),
        'trace_rows':events,'duplicate_delivery_events':dict(duplicates),
        'method':'Unique first-delivery time minus original same-engine app_send time; math.fsum of complete per-flow populations.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--accepted-t20-review-root',type=Path,required=True)
    a=p.parse_args();root=a.source_root.resolve();previous=a.accepted_t20_review_root.resolve()
    assert sha(previous/'analysis/review.json')==T20_REVIEW
    assert sha(previous/'acceptance.json')==T20_ACCEPTANCE
    assert sha(previous/'original-t20.zip')==T20_OWNER
    review=js(previous/'analysis/review.json')
    assert review['status']=='structural_review_completed' and review['evidence_integrity_verified']
    folder=root/'evidence/t20';folder.mkdir(exist_ok=True)
    for source,target in [('original-t20.zip','owner.zip'),('candidate.json','candidate.json'),('acceptance.json','acceptance.json')]:
        shutil.copyfile(previous/source,folder/target)
    accept20=js(folder/'acceptance.json');accept19=js(root/'evidence/t19/acceptance.json')
    assert sha(root/'evidence/t19/owner.zip')==T19_OWNER
    scenario=root/'scenarios/benchmarks/campus_multihop_6000.csv'
    cases=[]
    for seed in (128,129,130):
        group='t19' if seed==128 else 't20';case='a128' if seed==128 else f's{seed}'
        acceptance=accept19 if seed==128 else accept20
        old=review['reused_seed128']['observations'] if seed==128 else review['cases'][case]['observations']
        owner=root/f'evidence/{group}/owner.zip'
        with zipfile.ZipFile(owner) as z:
            snapshot,snapshot_sha=original_snapshot(root,group,z,acceptance)
            metadata=json.loads(z.read('metadata.json'))
            assert metadata['TestsPassed'] and metadata['Runtime']==acceptance['runtime']
            assert metadata['CandidateSHA256']==acceptance['candidate_sha256']==sha(root/f'evidence/{group}/candidate.json')
            matlab,matproof=matlab_run(z,case,old)
        native_dir='evidence/tranche-7-ns3-reference/campus_multihop_6000' if seed==128 else f'evidence/tranche-20-ns3-reference/s{seed}'
        native,natproof=native_run(root/native_dir,review['native_application_reference'][str(seed)])
        record={'case_id':case,'seed':seed,'policy':'actual-tx','fresh_execution':False,'duration_s':6000,
                'scenario_sha256':sha(scenario),'owner_file':owner.relative_to(root).as_posix(),'owner_sha256':sha(owner),
                'candidate_file':f'evidence/{group}/candidate.json','candidate_sha256':acceptance['candidate_sha256'],
                'acceptance_file':f'evidence/{group}/acceptance.json','acceptance_sha256':sha(root/f'evidence/{group}/acceptance.json'),
                'source_snapshot_file':snapshot,'source_snapshot_sha256':snapshot_sha,'runtime':metadata['Runtime'],
                'ns3_reference_directory':native_dir,'matlab':matlab,'ns3':native,
                'verification':{'matlab':matproof,'native':natproof}}
        cases.append(record);print('Verified reused seed',seed,flush=True)
    result={'schema':'csr-tranche25-reused-campus-v1','seeds':[128,129,130],'cases':cases,
            'source_compatibility':'All original MATLAB source snapshot files remain byte-identical in T25.',
            'accepted_t20_review_sha256':T20_REVIEW,'accepted_t20_acceptance_sha256':T20_ACCEPTANCE,
            'preparation_script_sha256':sha(Path(__file__)),
            'fresh_simulations_executed':False,'numerical_parity_established':False}
    write(root/'evidence/t25/reused-campus.json',result)
    print('Wrote evidence/t25/reused-campus.json',flush=True)

if __name__=='__main__':main()
