#!/usr/bin/env python3
"""Extract the independently confirmed NWK DACK-retry retention difference."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
native=[]
with (ROOT/'node8_1200/native/s132_1200/run/ns3-trace.csv').open() as f:
    for r in csv.DictReader(f):
        if r['node']=='4' and r['src']=='7' and r['sequence']=='1398' and r['event'] in ['nwk_enqueue','hop_feedback']:
            native.append(r)
matlab=[]
with (ROOT/'node8_return2/data/S132_1200/ordered_events.jsonl').open() as f:
    for line in f:
        if '"node":4,' not in line or '"time_s":694.' not in line or '"kind":"protocol"' not in line or '"FlowOrdinal":2873' not in line:continue
        r=json.loads(line)
        if r['details']['event'] in ['network_enqueue','hop_receive']:matlab.append(r)
nr=[r for r in native if r['event']=='hop_feedback'];mr=[r for r in matlab if r['details']['event']=='hop_receive']
assert len(nr)==len(mr)==2
get_detail=lambda r:dict(x.split('=',1) for x in r['detail'].split(';'))
assert [get_detail(r)['first_reception'] for r in nr]==['1','1']
assert [r['details']['details']['FirstReception'] for r in mr]==[True,True]
assert [get_detail(r)['nsdp_count_after'] for r in nr]==['26','27']
assert [r['details']['details']['NsdpAfter'] for r in mr]==[26,26]
assert len([r for r in native if r['event']=='nwk_enqueue'])==2
assert len([r for r in matlab if r['details']['event']=='network_enqueue'])==1
result={'schema':'csr-node8-return2-redteam-retry-proof-v1','confirmed':True,'source_application':{'source':7,'attempt':2873,'native_sequence':1398,'matlab_local_id':297},'receiver':4,'previous_hop':2,'incoming_hop_sequence':162,'first_receive_ns':694262813632,'second_receive_ns':694821813632,'native_enqueues':2,'matlab_enqueues':1,'native_nsdp_after':[26,27],'matlab_nsdp_after':[26,26],'native_raw_rows':native,'matlab_raw_rows':matlab,'source_explanation':{'active_class':'ac.DiscoveryMembershipNwk','first_guard':'receiveData Seen(appKey) accepted=true early return','second_guard':'enqueueApplication pendingPosition(app)>0 accepted=true early return','queue_ownership':'Pending/pump/release lookup also use application key, so allowing duplicate insertion alone is insufficient','native_semantics':'DACK clears ACK bit; retry remains first reception, so each native relay callback pushes a queue occurrence and increments NSDP'},'limitation':'This is a confirmed mismatch to current pinned ns-3, not proof that either algorithm is the best design or that this explains the full autonomous 6000-second latency gap.'}
(OUT/'retry_cause_proof.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if not k.endswith('_rows')},indent=2))
