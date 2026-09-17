"""Review source-derived (not observed) MATLAB 7→8 flow-control state."""
import csv
import json
import math
from collections import Counter
from pathlib import Path
from audit_inputs import BASE, WORKSPACE, digest

def main():
    root=BASE/'matlab'
    report=json.loads((root/'matlab_threshold_replay.json').read_text())
    assert digest(root/'replay_flow_threshold.py')==report['analysis_script_sha256']
    assert digest(root/'extract_matlab.py')==report['helper_sha256']
    assert digest(WORKSPACE/report['source'])==report['source_sha256']
    assert not report['matlab_executed'] and not report['source_modified']
    with (root/'matlab_threshold_events.csv').open(newline='') as f:
        events=list(csv.DictReader(f))
    summaries=[]
    for r in report['results']:
        seed=r['seed'];rows=[x for x in events if int(x['seed'])==seed]
        state=(0,0,0);counts=Counter();hist=Counter();last=-1
        for row in rows:
            before=tuple(int(row[k])for k in ['threshold_before','ack_count_before','outstanding_before'])
            after=tuple(int(row[k])for k in ['threshold_after','ack_count_after','outstanding_after'])
            assert before==state
            th,ack,out=before;ev=row['event'];retry=int(row['retry_requests_before'])
            assert int(row['row'])>last;last=int(row['row'])
            if ev=='hop_admit':
                assert out<=th and out<=16
                hist[th]+=1;out+=1
            elif ev=='hop_ack':
                out-=1
                if ack==2:
                    th=min(16,th+1);ack=0
                else:
                    ack+=1
                if retry:
                    ack=0
            elif ev=='hop_dack':ack=0
            elif ev=='hop_failed':out-=1;th=max(0,th-1);ack=0
            elif ev=='hop_dack_expired':out-=1
            else:assert ev=='hop_retry'
            assert (th,ack,out)==after
            state=after;counts[ev]+=1
        assert {str(k):v for k,v in hist.items()}==r['threshold_at_admission_histogram']
        assert dict(counts)==r['event_counts']
        assert state==(r['source_derived_threshold_at_stop'],r['source_derived_ack_count_at_stop'],r['pending_data_at_stop'])
        assert math.isclose(sum(r['threshold_seconds_300_to_6000'].values()),5700,abs_tol=1e-8)
        assert r['all_admissions_neighbor_and_global_data_thresholds_satisfied'] and r['pending_endpoint_verified']
        summaries.append({'seed':seed,'callback_rows_checked':len(rows),'admission_histogram':r['threshold_at_admission_histogram'],'state_transition_rule_and_endpoint_checks_passed':True})
    out={'schema':'csr-tranche21-independent-threshold-replay-review-v1','passed':True,'seeds':summaries,
        'source_review':'Layer.m flow initialization, admission, DATA ACK, DACK, failed and DACK-expiry paths independently inspected. Third ACK grows threshold before any retried-ACK reset. Controls do not alter this DATA state.',
        'scope':'Threshold and AckCount are reconstructed from verified complete ordered callbacks, not directly observed raw fields. Final pending DATA/resend/DACK counters validate populations but no final exported per-neighbor threshold snapshot exists.',
        'causality':'Distinct threshold histories do not establish a differing update rule or statistical equivalence between engines.',
        'reviewed_sha256':{p.name:digest(p)for p in root.glob('*')if p.is_file() and ('threshold' in p.name)}}
    (Path(__file__).parent/'threshold-replay-review.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
