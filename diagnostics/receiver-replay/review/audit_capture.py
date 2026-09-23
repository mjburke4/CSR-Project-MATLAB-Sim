#!/usr/bin/env python3
"""Independent captured-input checks against the earlier exact-prefix observer."""
import collections, csv, hashlib, json, math, re
from pathlib import Path
root=Path(__file__).resolve().parents[2]
capture=root/'receiver_replay/native/capture/receiver-input.log'
original=root/'queue132/native/first_failure_observed/run.log'
records=[line.rstrip().split('|') for line in capture.open()]
start=620_000_000_000; stop=675_000_000_000
want={'signal':[],'own_tx':[],'acquire':[],'rx_end':[]}
for line in original.open():
    m=re.match(r'time_ns=(\d+) (.*)',line)
    if not m:continue
    now=int(m[1]); s=m[2]
    if not start<=now<stop:continue
    for kind,pattern in [('signal',r'RX SYNC at node 2 from node (\d+) seq (\d+)'),('own_tx',r'TX from node 2 to dest (\d+) seq (\d+)'),('acquire',r'MAC 2 enters Track on node (\d+) seq (\d+)')]:
        n=re.search(pattern,s)
        if n:want[kind].append((now,int(n[1]),int(n[2])))
    n=re.search(r'\[FRAME_RX\] node=2 signal=(\d+) child=0 .*source=(\d+) .*sequence=(\d+) event=(\S+) reason=(\S+)',s)
    if n:want['rx_end'].append((now,int(n[1]),int(n[2]),int(n[3]),n[4],n[5]))
got={'signal':[],'own_tx':[],'acquire':[],'rx_end':[]}
inputs={};children=collections.defaultdict(list);drawkeys=[];syncids=[]
for r in records:
    if r[0]=='INPUT':
        kind=r[3]; now=int(r[2]);source=int(r[5]);dest=int(r[6]);seq=int(r[7]);sid=int(r[4]);inputs[sid]=r
        got[kind].append((now,source if kind=='signal' else dest,seq))
        payload,preamble,packet=map(int,r[8:11]);assert packet==preamble+48+8*payload+32
        rate=int(r[11]);assert rate==8,rate
        a,b,c=map(float,r[16:19]);duration=(preamble+48)*.000510/4+(8*payload+32)/(4/.000510)
        assert abs((b-a)-duration)<2e-12,(sid,b-a,duration)
        assert abs((c-a)-preamble*.000510/4)<2e-12
    elif r[0]=='CHILD':children[int(r[1])].append(r)
    elif r[0]=='SYNC':syncids.append(int(r[1]))
    elif r[0]=='DRAW':
        key=(int(r[1]),round(float(r[2])*1e9),round(float(r[3])*1e9),r[4]);drawkeys.append(key)
        assert 0<=float(r[5])<=1 and int(r[6])>0 and 0<float(r[7])<1
    elif r[0]=='EVENT':
        if r[4] in ('acquire','track'):got['acquire'].append((int(r[2]),int(r[5]),int(r[6])))
        elif r[4] in ('rx_end','signal_end'):got['rx_end'].append((int(r[2]),int(r[3]),int(r[5]),int(r[6]),'rx_accept' if r[7]=='accepted' else 'rx_drop',r[8]))
for k in want:assert got[k]==want[k],(k,len(got[k]),len(want[k]),next(((a,b) for a,b in zip(got[k],want[k]) if a!=b),None))
assert len(drawkeys)==len(set(drawkeys))
assert set(syncids)=={sid for sid,r in inputs.items() if r[3]=='signal'}
for sid,r in inputs.items():
    kids=children[sid];assert len(kids)==len(set(int(k[2]) for k in kids))
    assert sum(int(k[7]) for k in kids)==int(r[8])
checks={'original_precise_event_sequences':{k:len(v) for k,v in got.items()},'all_input_packet_bits_and_airtimes_consistent':True,'all_input_children_accounted':True,'all_signal_sync_thresholds_captured':True,'unique_semantic_random_draws':len(drawkeys),'capture_sha256':hashlib.sha256(capture.read_bytes()).hexdigest(),'original_observer_log_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'scope':'capture integrity; does not establish native replay or MATLAB pass'}
(root/'receiver_replay/review/capture_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
