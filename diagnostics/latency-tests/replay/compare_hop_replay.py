#!/usr/bin/env python3
"""Report discrete trajectory differences; never equate sampled with exact TX time."""
import argparse, csv, json, math
from pathlib import Path

STATE = ['mac_tx','ack_queue','data_queue','hop_pending','neighbor_outstanding',
         'neighbor_threshold','released','delivered']
def inspect(path, cases):
    with Path(path).open(newline='') as stream: rows = list(csv.DictReader(stream))
    if {r['case_id'] for r in rows} != {r['case_id'] for r in cases}:
        raise ValueError('Missing or extra cases')
    results = {}
    for case in cases:
        selected = [r for r in rows if r['case_id'] == case['case_id']]
        times = [float(r['observed_time_s']) for r in selected]
        if not all(math.isfinite(t) and 0<=t<=float(case['stop_s'])+1e-5 for t in times) or times != sorted(times): raise ValueError('Invalid observations')
        for r in selected:
            if any(not math.isfinite(float(r[f])) or float(r[f]) != int(float(r[f])) or int(float(r[f]))<0 for f in STATE): raise ValueError('Invalid state field')
        def one(event):
            values = [r for r in selected if r['event'] == event]
            if len(values) != 1: raise ValueError('Expected one ' + event)
            return values[0]
        before,after = one('feedback_before'),one('feedback_after')
        upstream = sum(float(case[f]) >= 0 for f in ['upstream_first_s','upstream_second_s'])
        final = one('final'); initial = one('admit')
        expired=case.get('feedback_effect','ack')=='expired'
        if case.get('feedback_effect','ack') not in ('ack','expired'): raise ValueError('Unknown expected effect')
        checks = {
            'local_initial_pending_one': int(initial['hop_pending']) == 1,
            'expected_pre_feedback_custody': int(before['hop_pending']) == int(not expired) and int(before['released']) == int(expired) and int(before['neighbor_outstanding']) == int(not expired),
            'expected_feedback_effect': int(after['hop_pending']) == 0 and int(after['released']) == 1 and int(after['neighbor_outstanding']) == 0 and int(after['released'])-int(before['released'])==int(not expired),
            'upstream_final_deliveries': int(final['delivered']) == upstream,
            'final_no_pending_data': int(final['hop_pending']) == 0 and int(final['data_queue']) == 0,
            'final_capacity_released': int(final['neighbor_outstanding'])==0 and int(final['released'])==1,
        }
        results[case['case_id']] = {'checks': checks, 'rows': selected}
    return results

def main():
    p=argparse.ArgumentParser();p.add_argument('matlab');p.add_argument('native')
    p.add_argument('--inputs',default=str(Path(__file__).with_name('inputs.csv')))
    p.add_argument('--output');args=p.parse_args()
    with Path(args.inputs).open(newline='') as stream: cases=list(csv.DictReader(stream))
    a,b=inspect(args.matlab,cases),inspect(args.native,cases)
    out={'schema':'node2-decoded-hop-replay-v1','runtime_files_supplied':True,
         'scope':'One MAC/HOP node; prescribed decoded ingress; no NWK or PHY equivalence',
         'sampling_seconds':.001,'time_parity_gate':False,'cases':{}}
    for case in a:
        left,right=a[case]['rows'],b[case]['rows']
        def signature(row): return [row['event']]+[int(row[f]) for f in STATE]
        same=[signature(r) for r in left]==[signature(r) for r in right]
        difference=None
        for i in range(max(len(left),len(right))):
            l=left[i] if i<len(left) else None;r=right[i] if i<len(right) else None
            if l is None or r is None or signature(l)!=signature(r):
                difference={'row_ordinal':i+1,'matlab':l,'native':r};break
        out['cases'][case]={'matlab_checks':a[case]['checks'],'native_checks':b[case]['checks'],
                            'discrete_rows_equal':same,'first_discrete_difference':difference}
    out['structural_pass']=all(all(v['checks'].values()) for runtime in (a,b) for v in runtime.values())
    out['discrete_trajectories_equal']=all(c['discrete_rows_equal'] for c in out['cases'].values())
    text=json.dumps(out,indent=2)
    if args.output:
        if Path(args.output).exists(): raise ValueError('Use a fresh output file')
        Path(args.output).write_text(text+'\n')
    print(text)
    return 0 if out['structural_pass'] and out['discrete_trajectories_equal'] else 1
if __name__=='__main__': raise SystemExit(main())
