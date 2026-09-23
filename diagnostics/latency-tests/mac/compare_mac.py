#!/usr/bin/env python3
"""Validate complete MAC fixtures, then compare discrete decisions and timing separately."""
import argparse,csv,json,math
from pathlib import Path
FIELDS=['case_id','ordinal','ack_segments','data_segments','data_queue_after','ack_queue_after','wire_bytes','rate_kbps','reservation_after']
def read(path):
    with Path(path).open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def integer(value):
    n=float(value)
    if not math.isfinite(n) or n!=int(n):raise ValueError('Nonintegral event field')
    return int(n)
def validate(rows,cases):
    if set(r['case_id'] for r in rows)!=set(c['case_id'] for c in cases):raise ValueError('Missing or unexpected cases')
    reports=[]
    for c in cases:
        rr=[r for r in rows if r['case_id']==c['case_id']]
        data=[];ack=0;previous=-1
        for i,r in enumerate(rr,1):
            n={f:integer(r[f]) for f in FIELDS[1:]}
            t=float(r['tx_time_s']); sample=float(r['sample_time_s'])
            if not all(math.isfinite(x) for x in (t,sample)) or not 0<=t<=sample+1e-10 or sample-t>0.00010001 or t<=previous:
                raise ValueError('Invalid, unordered, or stale TX observation')
            previous=t
            if n['ordinal']!=i or n['ack_segments'] not in (0,1) or n['data_segments'] not in (0,1) or not n['ack_segments']+n['data_segments']:
                raise ValueError('Invalid TX membership/ordinal')
            if n['wire_bytes']!=41*n['ack_segments']+(int(c['payload_bytes'])+32)*n['data_segments'] or n['rate_kbps']!=int(c['rate_kbps']):
                raise ValueError('Frame byte/rate mismatch')
            if n['data_segments']:data.append(i)
            ack+=n['ack_segments']
            if n['data_queue_after']!=1-len(data) or n['ack_queue_after'] not in (0,1):raise ValueError('Invalid queue accounting')
        if integer(rr[-1]['data_queue_after']) or integer(rr[-1]['ack_queue_after']):raise ValueError('Undrained fixture')
        reports.append({'case_id':c['case_id'],'data_ordinals':data,'ack_count':ack,
            'expected_data_ordinal':int(c['expected_data_ordinal']),'expected_ack_count':int(c['expected_ack_count']),
            'passed':data==[int(c['expected_data_ordinal'])] and ack==int(c['expected_ack_count'])})
    return reports

def compare(a,b,cases):
    checks={'matlab':validate(a,cases),'native':validate(b,cases)}
    diffs=[];timing=[]
    for c in cases:
        aa=[r for r in a if r['case_id']==c['case_id']];bb=[r for r in b if r['case_id']==c['case_id']]
        for i in range(max(len(aa),len(bb))):
            if i>=len(aa) or i>=len(bb):diffs.append({'case_id':c['case_id'],'ordinal':i+1,'field':'row_count'});continue
            for f in FIELDS[1:]:
                if integer(aa[i][f])!=integer(bb[i][f]):diffs.append({'case_id':c['case_id'],'ordinal':i+1,'field':f,'matlab':aa[i][f],'native':bb[i][f]})
            timing.append({'case_id':c['case_id'],'ordinal':i+1,'delta_matlab_minus_native_s':float(aa[i]['tx_time_s'])-float(bb[i]['tx_time_s'])})
    return {'schema':'csr-latency-mac-comparison-v1','structural_passed':all(r['passed'] for rr in checks.values() for r in rr),
        'discrete_rows_match':not diffs,'first_discrete_difference':next(iter(diffs),None),'differences':diffs,
        'checks':checks,'timing_deltas':timing,'timing_is_diagnostic_only':True,
        'shared_absolute_inputs_for_nonrefresh_cases':True,'refresh_inputs_are_state_relative':True,
        'scope':'MAC only; no HOP/NWK/RF. Fixed slot 1 removes MAC random draws. Refreshed ACK scheduled 1 ms after observed ACK #2; native observation adds up to 0.1 ms.'}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('matlab',type=Path);p.add_argument('native',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    here=Path(__file__).resolve().parent
    if args.output.exists():p.error('Use a fresh comparison output file')
    result=compare(read(args.matlab),read(args.native),read(here/'cases.csv'))
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('structural_passed','discrete_rows_match','first_discrete_difference')}))
    return 0 if result['structural_passed'] and result['discrete_rows_match'] else 1
if __name__=='__main__':raise SystemExit(main())
