#!/usr/bin/env python3
"""Offline seed-132 feedback reconstruction. No simulation or source edits.

Ordinary trace facts are separated from queue/bitmap values reconstructed
using the pinned production rules. Cross-checks test every inferred TX head,
its PHY envelope, and every DATA completion at node 8.
"""
from pathlib import Path
from collections import Counter, defaultdict
from statistics import mean, median
import csv, json, hashlib

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'return6000/data/s132/attempt_001/raw'
OUT = Path(__file__).resolve().parent

def read(name):
    with (RAW/name).open(newline='') as f:
        return list(csv.DictReader(f))

def ns(row): return round(float(row['TimeSeconds'])*1e9)
def num(row, key): return int(row[key])
def dump(name, rows):
    with (OUT/name).open('w',newline='') as f:
        fields=list(dict.fromkeys(k for row in rows for k in row))
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader();w.writerows(rows)

rows=read('protocol_trace.csv')
sources={num(r,'PacketId'):num(r,'NodeId') for r in rows if r['Event']=='app_generate'}
feedback={}
decisions=[]
terminals={}
counts=Counter()
for i,r in enumerate(rows):
    node,peer=num(r,'NodeId'),num(r,'PeerId')
    if node==2 and peer==8 and float(r['TimeSeconds'])>=300 and r['FrameKind'] in ('ACK','DACK'):
        assert r['Event'] in ('mac_enqueue','mac_ack_replace'),r
        assert ns(r) not in feedback
        feedback[ns(r)] = (i,r)
        counts[(r['Event'],r['FrameKind'])]+=1
    if node==2 and r['Event']=='hop_receive':
        assert peer==8
        fi,fr=feedback[ns(r)]
        assert fi<i
        decisions.append({'packet_id':num(r,'PacketId'),'source':sources[num(r,'PacketId')],
            'sequence':num(r,'Sequence'),'receive_s':float(r['TimeSeconds']),
            'receiver_decision':fr['FrameKind'],'queue_event':fr['Event'],
            'feedback_highest_sequence':num(fr,'Sequence')})
    if node==8 and peer==2 and r['Event'] in ('hop_ack','hop_dack','hop_failed'):
        k=(num(r,'PacketId'),num(r,'Sequence'));assert k not in terminals
        terminals[k]=r
assert len(decisions)==len(feedback)==1132
for d in decisions:
    r=terminals[(d['packet_id'],d['sequence'])]
    assert r['Event']=={'ACK':'hop_ack','DACK':'hop_dack'}[d['receiver_decision']]
    d['completion_event']=r['Event'];d['completion_s']=float(r['TimeSeconds'])
    d['feedback_delay_s']=d['completion_s']-d['receive_s']
    assert d['feedback_delay_s']>=0

# All node-2 DATA feedback after 300 s is for node 8; all control receives
# precede 300 s. Consequently the post-start queue contains at most one
# cumulative feedback frame and its first member is exposed by tx_start.
assert not any(num(r,'NodeId')==2 and r['Event']=='hop_control_receive' and float(r['TimeSeconds'])>=300 for r in rows)
assert not any(num(r,'NodeId')==2 and r['FrameKind'] in ('ACK','DACK') and num(r,'PeerId')!=8 and float(r['TimeSeconds'])>=300 for r in rows)
bytime={round(d['receive_s']*1e9):d for d in decisions}
highest=-1; ack=dack=0;mask=(1<<64)-1
queue=None; txs=[]; generation=0; replaces=[]
for r in rows:
    if num(r,'NodeId')!=2 or float(r['TimeSeconds'])<300:continue
    ev=r['Event']
    if ev in ('mac_enqueue','mac_ack_replace') and r['FrameKind'] in ('ACK','DACK'):
        d=bytime[ns(r)];seq=d['sequence']
        if highest<0: highest=seq;ack=1
        else:
            delta=(seq-highest+32768)%65536-32768
            if delta>0:
                ack=((ack<<delta)|1)&mask;dack=(dack<<delta)&mask;highest=seq
            else:
                assert -delta<64
                assert not (ack>>(-delta))&1
                ack|=1<<(-delta)
        if r['FrameKind']=='DACK':
            bit=(highest-seq)%65536;ack&=~(1<<bit);dack|=1<<bit
        assert highest==num(r,'Sequence')
        generation+=1
        if ev=='mac_enqueue': assert queue is None
        else:
            assert queue is not None
            replaces.append({'replaced_generation':queue['generation'],'replacement_s':float(r['TimeSeconds']),
                'replaced_kind':queue['kind'],'new_kind':r['FrameKind'],'transmissions_before_replacement':queue['repeat_count']})
        queue={'generation':generation,'queued_s':float(r['TimeSeconds']),'sequence':highest,
               'ack':ack,'dack':dack,'repeat_count':0,'kind':r['FrameKind']}
    elif ev=='tx_start':
        if queue:
            assert num(r,'PeerId')==8 and num(r,'Sequence')==queue['sequence'] and num(r,'ApplicationBytes')==0,r
            txs.append(dict(queue,tx_s=float(r['TimeSeconds']),tx_id=num(r,'PacketId')))
            queue['repeat_count']+=1
            if queue['repeat_count']==5:queue=None
        else:
            assert num(r,'PeerId')==4 and num(r,'ApplicationBytes')==185,r
assert queue is None

phy=read('phy_trace.csv')
ends={num(r,'PacketId'):r for r in phy if r['Event']=='phy_signal_end' and num(r,'SourceId')==2 and num(r,'NodeId')==8}
assert len(ends)==sum(1 for r in rows if r['Event']=='tx_start' and num(r,'NodeId')==2)
for t in txs:
    p=ends[t['tx_id']];assert num(p,'DestinationId')==8
    t.update(phy_end_s=float(p['TimeSeconds']),phy_success=num(p,'Success'),phy_reason=p['Reason'])

# Replay the already observed ownership inputs through reconstructed feedback
# bitmaps, and check that each received bitmap predicts the exact completion
# set in the ordinary trace. Not an execution of the MATLAB implementation.
completion_at=defaultdict(list)
events=[]
for r in rows:
    if num(r,'NodeId')==8 and num(r,'PeerId')==2 and r['FrameKind']=='DATA':
        if r['Event'] in ('hop_admit','hop_failed'):
            events.append((ns(r),1,r))
        if r['Event'] in ('hop_ack','hop_dack'):
            completion_at[ns(r)].append((num(r,'PacketId'),num(r,'Sequence'),r['Event']))
for t in txs:
    if t['phy_success']:events.append((round(t['phy_end_s']*1e9),0,t))
owners={};predicted=0;unknown=0;effective=0;consumed=set();residual=[];completion_tx={}
for stamp,kind,obj in sorted(events,key=lambda x:(x[0],x[1])):
    if kind:
        seq=num(obj,'Sequence')
        if obj['Event']=='hop_admit':assert seq not in owners;owners[seq]=num(obj,'PacketId')
        else:assert owners.pop(seq)==num(obj,'PacketId')
    else:
        actual=completion_at.get(stamp,[]);prediction=[]
        for bit in range(64):
            a=(obj['ack']>>bit)&1;d=(obj['dack']>>bit)&1 and not a
            if not(a or d):continue
            seq=(obj['sequence']-bit)%65536
            if seq in owners:
                prediction.append((owners.pop(seq),seq,'hop_dack' if d else 'hop_ack'))
            else:unknown+=1
        assert sorted(prediction)==sorted(actual),(stamp,prediction,actual)
        for packet,sequence,outcome in prediction:
            completion_tx[(packet,sequence)]=obj
        if actual:effective+=1;consumed.add(stamp)
        predicted+=len(prediction)
        obj['new_data_completions']=len(prediction)
assert consumed==set(completion_at)
assert predicted==1132
for d in decisions:
    t=completion_tx[(d['packet_id'],d['sequence'])]
    d.update(completing_tx_id=t['tx_id'],completing_frame_kind=t['kind'],
             completing_bitmap_highest=t['sequence'],completing_queue_generation=t['generation'])
dump('receiver_decisions_and_completions.csv',decisions)
dump('feedback_transmissions_reconstructed.csv',txs)
dump('feedback_replacements_reconstructed.csv',replaces)

cohorts=[]
for source in (7,8):
    for outcome in ('ACK','DACK'):
        part=[d for d in decisions if d['source']==source and d['receiver_decision']==outcome]
        delays=sorted(d['feedback_delay_s'] for d in part)
        cohorts.append({'source':source,'receiver_decision':outcome,'count':len(part),
            'first_receive_s':min(d['receive_s'] for d in part),'last_receive_s':max(d['receive_s'] for d in part),
            'mean_feedback_delay_s':mean(delays),'median_feedback_delay_s':median(delays),
            'p95_feedback_delay_s':delays[int(.95*(len(delays)-1))],'max_feedback_delay_s':max(delays)})
dump('source_feedback_cohorts.csv',cohorts)
bins=[]
for start in range(300,6000,300):
    for source in (7,8):
        part=[d for d in decisions if start<=d['receive_s']<start+300 and d['source']==source]
        bins.append({'start_s':start,'end_s':start+300,'source':source,'DATA_receipts':len(part),
                    'ACK_decisions':sum(d['receiver_decision']=='ACK' for d in part),
                    'DACK_decisions':sum(d['receiver_decision']=='DACK' for d in part)})
dump('receiver_decisions_300s_bins.csv',bins)
summary={'scope':'seed 132 corrected MATLAB, 300–6000 s, node 2 feedback to node 8',
 'receiver_data_receptions':len(decisions),'receiver_data_duplicates':0,
 'receiver_decisions':dict(Counter(d['receiver_decision'] for d in decisions)),
 'queue_events':{':'.join(k):v for k,v in counts.items()},
 'all_receiver_decisions_have_matching_completion':True,
 'completion_by_carrier_kind':dict(Counter(d['receiver_decision']+' carried by '+d['completing_frame_kind'] for d in decisions)),
 'mean_receiver_decision_to_completion_s':mean(d['feedback_delay_s'] for d in decisions),
 'max_receiver_decision_to_completion_s':max(d['feedback_delay_s'] for d in decisions),
 'completion_bitmap_reconstruction_mismatches':0,'data_completions_reproduced':predicted,
 'feedback_transmissions':len(txs),'phy_results':dict(Counter(t['phy_reason'] for t in txs)),
 'success_feedback_transmissions':sum(t['phy_success'] for t in txs),
 'success_feedback_transmissions_with_new_data_completion':effective,
 'unknown_or_already_complete_bitmap_bits':unknown,
 'replacement_before_first_transmission':sum(r['transmissions_before_replacement']==0 for r in replaces),
 'replacements_total':len(replaces),'remaining_data_resend_owners':owners,
 'source_cohorts':cohorts,
 'limitations':['Queue contents and bitmaps are inferred from pinned production rules and complete observed receive/queue/tx events, not directly captured bitmap fields.',
 'Each inferred transmission is cross-checked against the observed TX head/PHY envelope and every corresponding node-8 DATA completion.',
 'This does not establish equality to native receiver NSDP state or receiver choice under common inputs.']}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
