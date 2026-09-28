#!/usr/bin/env python3
"""Compare current MATLAB capacity arithmetic with archived ns-3 event inputs.

This is an offline source-semantics check, not execution of MATLAB production
callbacks or a replay of original ACK bitmaps/PHY behavior.
"""
import csv,json,hashlib
from collections import Counter
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
PATH=ROOT/'return6000/history/longrun_recovery/extracted/latency-review/latency-review/native/output/s132-capacity-events.csv'
def ns(v):return int(Decimal(v)*1_000_000_000)
def main():
    data=list(csv.DictReader(PATH.open()))
    reports=[]
    for node in (8,2):
        selected=[r for r in data if int(r['node'])==node]
        outstanding=threshold=ack_count=0; live=set();held={};issues=[];counts=Counter();checks=0
        for r in selected:
            t=ns(r['time_s']);key=(int(r['application_sequence']),int(r['hop_sequence']))
            before=(outstanding,threshold)
            observed_before=(int(r['outstanding_before']),int(r['threshold_before']))
            if before!=observed_before:issues.append(dict(event_index=r['event_index'],field='before',ours=before,ns3=observed_before))
            reason=r['reason'];event=r['event'];counts[event+':'+reason]+=1
            if event=='hop_admission':
                assert key not in live and key not in held
                assert outstanding<=threshold and outstanding<=16
                outstanding+=1;live.add(key)
            elif event=='hop_completion':
                assert key in live;live.remove(key); retry=int(r['resend_count'])
                if reason=='ack':
                    outstanding-=1;ack_count+=1
                    if ack_count>=3:threshold=min(16,threshold+1);ack_count=0
                    if retry>0:ack_count=0
                elif reason=='dack':
                    ack_count=0;hold_s=40 if retry>=2 else 20
                    assert hold_s==int(r['dack_hold_seconds'])
                    held[key]=t+hold_s*1_000_000_000+28
                elif reason=='no_ack':
                    outstanding-=1;ack_count=0;threshold=max(0,threshold-1)
                else:raise AssertionError(reason)
            elif event=='hop_capacity_release':
                assert reason=='dack_expiry' and key in held
                expected=held.pop(key)
                if t!=expected:issues.append(dict(event_index=r['event_index'],field='expiry_ns',ours=expected,ns3=t))
                outstanding-=1
            else:raise AssertionError(event)
            after=(outstanding,threshold,len(held))
            observed_after=(int(r['outstanding_after']),int(r['threshold_after']),int(r['dack_held_after']))
            if after!=observed_after:issues.append(dict(event_index=r['event_index'],field='after',ours=after,ns3=observed_after))
            assert outstanding==len(live)+len(held)
            checks+=5
        reports.append(dict(node=node,peer=2 if node==8 else 4,events=len(selected),scalar_state_checks=checks,
            event_counts=dict(counts),mismatches=issues,final_outstanding=outstanding,final_threshold=threshold,
            final_dack_held=len(held),final_resends=len(live)))
    result=dict(schema='csr-current-matlab-capacity-rule-arithmetic-vs-ns3-v1',
        scope='Translate current Layer.m capacity arithmetic and supply ns-3 ordered admission/completion/expiry inputs. Not executable MATLAB or receiver-ACK-decision validation.',
        inputs=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                for p in (ROOT/'return6000/kit/csr6000/model/+csr/+hop/Layer.m',PATH)],
        links=reports)
    (OUT/'native_capacity_rule_crosscheck.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    assert not any(r['mismatches'] for r in reports)
if __name__=='__main__':main()
