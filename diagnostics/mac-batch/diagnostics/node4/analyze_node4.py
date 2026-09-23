"""Offline node-4 HOP history audit; stdlib only; no production changes.

With the original workspace available, refresh compact input extracts. When
distributed with those extracts, rerun the derived checks without the archives.
"""
from pathlib import Path
import csv, io, json, hashlib, zipfile, collections

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
NATIVE=ROOT/'queue132/native/first_failure_observed/ns3-trace.csv'
MAT_EVENTS=ROOT/'queue132/matlab/events.csv'
ARCHIVE=ROOT/'original_extracted/t25review/owner.zip'

def read(path):
    with open(path,newline='') as f: yield from csv.DictReader(f)
def write(name,rows):
    rows=list(rows)
    with open(OUT/name,'w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def details(text): return dict(s.split('=',1) for s in text.split(';') if '=' in s)
def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(4<<20),b''): h.update(b)
    return h.hexdigest()

if NATIVE.exists() and MAT_EVENTS.exists() and ARCHIVE.exists():
    keep=[]
    for r in read(NATIVE):
        t=float(r['time_s'])
        if t>=600: break
        if (r['node']=='4' and r['event']=='hop_completion') or (r['node']=='5' and r['src']=='4' and r['event'] in ['rx_accept','rx_drop']): keep.append(r)
    write('native_trace_node4_0_600.csv',keep)
    write('matlab_events_node4_0_600.csv',(r for r in read(MAT_EVENTS) if r['node']=='4' and float(r['time_s'])<600))
    provenance={'native_trace_sha256':digest(NATIVE),'matlab_derived_events_sha256':digest(MAT_EVENTS),'archive_sha256':digest(ARCHIVE),'case':'s132','seed':132,'native_trace':'queue132/native/first_failure_observed/ns3-trace.csv','matlab_archive':'original_extracted/t25review/owner.zip'}
    with zipfile.ZipFile(ARCHIVE) as z:
        for kind in ['protocol','phy']:
            keep=[]
            with z.open(f's132/raw/{kind}_trace.csv') as f:
                for r in csv.DictReader(io.TextIOWrapper(f)):
                    t=float(r['TimeSeconds'])
                    if t>=600:break
                    if t>=490 and r['NodeId'] in ['4','5']:keep.append(r)
            write(f'matlab_{kind}_490_600.csv',keep)
            provenance[f'matlab_{kind}_archive_member']=f's132/raw/{kind}_trace.csv'
    (OUT/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')

native=list(read(OUT/'native_trace_node4_0_600.csv'))
mat=list(read(OUT/'matlab_events_node4_0_600.csv'))
protocol=list(read(OUT/'matlab_protocol_490_600.csv'))
phy=list(read(OUT/'matlab_phy_490_600.csv'))
history=[]; checked=collections.Counter()
for engine,rs in [('native',native),('matlab',mat)]:
    streak=0;threshold=0
    for r in rs:
        if engine=='native':
            if r['event']!='hop_completion' or r['packet_type']!='data':continue
            d=details(r['detail']);action=r['reason'];retries=int(d['resend_count'])
            before=int(d['threshold_before']);after=int(d['threshold_after'])
            t=float(r['time_s']);seq=int(d['hop_sequence']);src=r['src'];packet=f"{r['src']}:{r['dst']}:{r['sequence']}";order=r['event_index']
        else:
            if r['event'] not in ['hop_ack','hop_dack','hop_failed']:continue
            action={'hop_ack':'ack','hop_dack':'dack','hop_failed':'no_ack'}[r['event']]
            retries=int(r['retry_count']);before=int(r['threshold_before']);after=int(r['threshold_after'])
            t=float(r['time_s']);seq=int(r['sequence']);src=r['source'];packet=r['packet_key'];order=r['event_order']
            assert streak==int(r['ack_streak_before'])
        assert threshold==before,(engine,t,threshold,before)
        prior=streak
        if action=='ack':
            streak+=1
            if streak>=3:threshold=min(16,threshold+1);streak=0
            if retries:streak=0
        elif action=='no_ack':threshold=max(0,threshold-1);streak=0
        else:streak=0
        assert threshold==after,(engine,t,threshold,after)
        if engine=='matlab':assert streak==int(r['ack_streak_after'])
        checked[engine]+=1
        history.append(dict(engine=engine,time_s=t,source=src,packet_key=packet,hop_sequence=seq,feedback=action,retries=retries,window_before=before+1,window_after=after+1,streak_before=prior,streak_after=streak,source_order=order))
write('feedback_history.csv',history)
write('window_changes.csv',(r for r in history if r['window_before']!=r['window_after']))

failed=[]
ends={(r['NodeId'],r['PacketId']):r for r in phy if r['Event']=='phy_signal_end'}
for r in protocol:
    if r['NodeId']!='4' or r['Event']!='tx_start' or r['Sequence'] not in ['86','89','91']:continue
    rx=ends[('5',r['PacketId'])]
    assert rx['Success']=='0'
    failed.append(dict(engine='matlab',hop_sequence=int(r['Sequence']),tx_s=float(r['TimeSeconds']),physical_packet=r['PacketId'],rx_end_s=float(rx['TimeSeconds']),receiver=5,rx_outcome=rx['Reason'],collisions=int(rx['CollisionCount'])))
assert collections.Counter(r['hop_sequence'] for r in failed)=={86:3,89:3,91:3}
for seq in [86,89,91]:
    last_tx=max(r['tx_s'] for r in failed if r['hop_sequence']==seq)
    completion=[r for r in history if r['engine']=='matlab' and r['hop_sequence']==seq and r['feedback']=='no_ack']
    assert len(completion)==1
    assert abs(completion[0]['time_s']-last_tx-4-1/36e6)<1e-9
write('matlab_failed_attempts.csv',failed)
growth=[]
for r in native:
    if r['node']=='5' and r['src']=='4' and r['packet_type']=='data' and r['event'] in ['rx_accept','rx_drop'] and r['sequence'] in ['72','75'] and float(r['time_s'])>570:
        growth.append(dict(engine='native',hop_sequence=int(r['sequence']),rx_end_s=float(r['time_s']),receiver=5,rx_outcome=r['reason'],source_order=r['event_index']))
assert len(growth)==5
write('native_growth_attempts.csv',growth)

summary={'scope':'Node4 DATA HOP flow to5, feedback history before600; focused PHY histories490–600. MATLAB windows reconstructed from archived events, native windows directly traced.','checks':dict(checked),'boundary':{},'feedback_528_433_to_600':{},'matlab_failed_attempts':len(failed),'matlab_failed_attempt_outcomes':dict(collections.Counter(r['rx_outcome'] for r in failed)),'native_growth_after_retry':[],'runtime_test_status':'run_hop_window.m prepared; no MATLAB runtime available in this workspace.'}
for engine in ['native','matlab']:
    rs=[r for r in history if r['engine']==engine]
    summary['boundary'][engine]={'last_feedback_s':rs[-1]['time_s'],'window_at600':rs[-1]['window_after'],'ack_streak_at600':rs[-1]['streak_after']}
    focused=[r for r in rs if r['time_s']>=528.433000027778]
    summary['feedback_528_433_to_600'][engine]={'feedback':dict(collections.Counter(r['feedback'] for r in focused)),'acks_after_retry':sum(r['feedback']=='ack' and r['retries']>0 for r in focused),'growths':sum(r['window_after']>r['window_before'] for r in focused),'shrinks':sum(r['window_after']<r['window_before'] for r in focused)}
summary['native_growth_after_retry']=[r for r in history if r['engine']=='native' and r['time_s']>570 and r['window_after']>r['window_before']]
assert summary['boundary']['native']['window_at600']==3
assert summary['boundary']['matlab']['window_at600']==1
oracle={'scope':'Native DATA HOP completion history; compact retry/feedback vector, not original event times or queue replay.','initial_window':1,'initial_ack_streak':0,'native_growth_history':[r for r in history if r['engine']=='native' and 577<r['time_s']<600], 'other_edges':'Failed owner decrements threshold with floor0 and resets ACK streak; DACK resets streak, retains capacity until expiry.','native_source':'csr/model/csr-hop-layer.h: FlowCtrlEntry / HandleAck / CheckResend','matlab_source':'core/+csr/+hop/Layer.m: complete / failEntry / checkDacks'}
assert [r['hop_sequence'] for r in oracle['native_growth_history']]==[70,71,72,73,74,76,77,75]
(OUT/'hop_window_oracle.json').write_text(json.dumps(oracle,indent=2)+'\n')
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
