#!/usr/bin/env python3
"""Offline observer audit; never modifies or invokes either simulator.

Input identities are mapped independently to (source, scheduled attempt).
Internal HOP admissions retain measured ns differences; no timing relaxation
is introduced into the runtime common-input comparator.
"""
import argparse, collections, csv, hashlib, json
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

def ns(v): return int((Decimal(str(v))*10**9).to_integral_value(rounding=ROUND_HALF_EVEN))
def details(v): return dict(p.split('=',1) for p in v.split(';') if '=' in p)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()
def identity(app): return (int(app['SourceId']),int(app['FlowOrdinal']))
def snapshot(queue,owners):
    return {'waiting':len(queue),'waiting_by_source':dict(collections.Counter(str(k[0]) for k in queue)),
            'ordered_source_attempts':[list(k) for k in queue],
            'custody_count':len(owners),'custody_by_source':dict(collections.Counter(str(k[0]) for k in owners))}
def read_matlab(path,cutoff,node,checkpoints):
    pending={}; queue=[]; ids={}; live=set(); holds=set(); counts=collections.Counter()
    enters=[]; admits=[]; releases=[]; snapshots={}; previous_order=0; previous_t=-1
    for line in path.open():
        r=json.loads(line); t=ns(r['time_s']); order=int(r['observation_order'])
        assert order==previous_order+1, ('order_gap',previous_order,order)
        assert t>=previous_t,('time_regression',t,previous_t)
        previous_order=order;previous_t=t
        for c in checkpoints:
            if t>=c and str(c) not in snapshots: snapshots[str(c)]=snapshot(queue,pending)
        if t>=cutoff:continue
        if r['kind']=='application_attempt':
            d=r['details']; key=(int(d['SourceId']),int(d['AttemptIndex']))
            if d['Accepted']:
                aid=int(d['PacketId']);assert aid not in ids;ids[aid]=key
            if int(r['node'])==node:
                assert int(d['NwkQueueSize'])==len(queue),('matlab_application_queue',t,d['NwkQueueSize'],len(queue))
                pair=[k for k,v in pending.items() if k[0]==node and int(v['app']['DestinationId'])==int(d['DestinationId'])]
                assert int(d['NsdpCount'])==len(pair),('matlab_application_nsdp',t,d['NsdpCount'],len(pair))
                counts['application_state_checks']+=1
            continue
        if int(r['node'])!=node or r['kind']!='protocol':continue
        d=r['details']; e=d['event'];frame=d['frame'];v=d['details'];app=frame.get('App',frame)
        if 'FlowOrdinal' not in app:continue
        key=identity(app);assert ids[int(app['Id'])]==key
        if e=='network_enqueue':
            assert key not in pending,('repeated_matlab_custody',key)
            pending[key]={'app':app,'submitted':False}
            queue.insert(0,key) if app.get('Dscp',0)>0 else queue.append(key)
            assert int(v['QueueDepth'])==len(pending)
            enters.append((t,key));counts[e]+=1
        elif e=='hop_admit':
            assert key in pending and not pending[key]['submitted']
            queue.remove(key);pending[key]['submitted']=True
            owner=(int(frame['DestinationId']),int(frame['Sequence']))
            assert owner not in live and owner not in holds;live.add(owner)
            admits.append((t,key,int(frame['DestinationId']),int(frame['Sequence'])))
            counts[e]+=1
        elif e=='network_submit':
            assert pending[key]['submitted'];counts[e]+=1
        elif e=='network_custody_release':
            assert key in pending
            if not pending[key]['submitted']:queue.remove(key)
            del pending[key]
            raw_reason=v['Reason'];counts['custody_release_reason_'+raw_reason]+=1
            reason={'retry_exhausted':'no_ack'}.get(raw_reason,raw_reason)
            releases.append((t,key,reason));counts[e]+=1
        elif e in ('hop_ack','hop_failed','hop_dack'):
            owner=(int(frame['DestinationId']),int(frame['Sequence']))
            assert owner in live,(e,'owner_missing',t,owner)
            live.remove(owner)
            if e=='hop_dack':
                assert not v['CapacityReleased'];holds.add(owner)
            counts[e]+=1
        elif e=='hop_dack_expired':
            owner=(int(frame['DestinationId']),int(frame['Sequence']))
            assert owner in holds;holds.remove(owner);counts[e]+=1
        elif e=='hop_receive':
            pair=[k for k,p in pending.items() if k[0]==key[0] and p['app']['DestinationId']==app['DestinationId']]
            assert int(v['NsdpAfter'])==len(pair),('matlab_receive_nsdp',t,key,v['NsdpAfter'],len(pair))
            counts['receive_nsdp_checks']+=1
        if e in ('hop_admit','hop_ack','hop_dack_expired'):
            assert int(v['PendingData'])==len(live)+len(holds),(e,'pending_capacity',t,v['PendingData'],len(live),len(holds))
            peer=int(frame['DestinationId'])
            assert int(v['NeighborOutstanding'])==sum(o[0]==peer for o in live|holds)
            counts['post_event_capacity_checks']+=1
    for c in checkpoints:
        if str(c) not in snapshots:snapshots[str(c)]=snapshot(queue,pending)
    return {'events':dict(counts),'queue_checkpoints':snapshots,'final':snapshot(queue,pending),'live_hop_owners':len(live),'dack_holds':len(holds)},enters,admits,releases

def read_native(path,cutoff,node,checkpoints):
    ids={};dscps={};queue=[];pending=[];enters=[];admits=[];releases=[];checks=collections.Counter();snapshots={}
    for r in csv.DictReader(path.open()):
        t=ns(r['time_s'])
        for c in checkpoints:
            if t>=c and str(c) not in snapshots:snapshots[str(c)]=snapshot(queue,pending)
        if t>=cutoff:continue
        e=r['event'];d=details(r['detail'])
        if e=='app_admission' and r['success']=='1':ids[int(r['sequence'])]=(int(r['src']),int(d['attempt_index']))
        if e=='app_send':dscps[int(r['sequence'])]=int(d['dscp'])
        if int(r['node'])!=node or r['packet_type']!='data':continue
        if e=='app_admission':
            assert int(d['nwk_queue'])==len(queue),('native_application_queue',t,d,len(queue))
            checks['application_state_checks']+=1
            continue
        if e not in ('nwk_enqueue','nwk_admission','hop_admission','hop_completion'):continue
        aid=int(r['sequence']);key=ids[aid]
        if e=='nwk_enqueue':
            queue.insert(0,key) if dscps[aid]>0 else queue.append(key)
            pending.append(key);enters.append((t,key));checks[e]+=1
            assert int(d['queue_after'])==len(queue)
        elif e=='nwk_admission':
            assert int(d['queue_before'])==len(queue)
            if r['success']=='1':queue.remove(key)
            assert int(d['queue_after'])==len(queue)
            checks['candidate_queue_checks']+=1
        elif e=='hop_admission' and r['success']=='1':
            admits.append((t,key,int(r['peer']),int(d['hop_sequence'])));checks[e]+=1
        elif e=='hop_completion' and d.get('nsdp_released')=='1':
            pending.remove(key);releases.append((t,key,r['reason']));checks[e]+=1
    for c in checkpoints:
        if str(c) not in snapshots:snapshots[str(c)]=snapshot(queue,pending)
    return {'events':dict(checks),'queue_checkpoints':snapshots,'final':snapshot(queue,pending)},enters,admits,releases

def main():
    p=argparse.ArgumentParser();p.add_argument('--matlab',type=Path,required=True);p.add_argument('--native',type=Path,required=True)
    p.add_argument('--cutoff',type=int,required=True);p.add_argument('--node',type=int,default=8);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();cutoff=a.cutoff*10**9;checkpoints=[v*10**9 for v in [400,600,675,900,1200] if v<=a.cutoff]
    mat,me,ma,mr=read_matlab(a.matlab,cutoff,a.node,checkpoints)
    native,ne,na,nr=read_native(a.native,cutoff,a.node,checkpoints)
    assert me==ne,'NWK accepted-arrival identities/order/times differ'
    assert [r[1:] for r in ma]==[r[1:] for r in na],'HOP handoff source-attempt/peer/sequence order differs'
    assert mr==nr,'Custody release identities/order/reasons/times differ'
    assert mat['queue_checkpoints']==native['queue_checkpoints'],'Ordered waiting/custody checkpoints differ'
    shifts=collections.Counter(str(m[0]-n[0]) for m,n in zip(ma,na))
    out={'status':'pass','node':a.node,'stop_ns_exclusive':cutoff,'input_sha256':{str(a.matlab):sha(a.matlab),str(a.native):sha(a.native)},
         'matlab':mat,'native':native,'matched_enqueue_events':len(me),'matched_handoff_identity_events':len(ma),'matched_custody_releases':len(mr),
         'matlab_minus_native_handoff_time_ns_counts':dict(shifts),
         'complete_run_gate_required':True,
         'release_reason_mapping':{'MATLAB retry_exhausted':'native no_ack'},
         'timing_policy':'All measured handoff deltas retained; this offline identity comparison does not change runtime strict random/TX comparator tolerances.',
         'limits':['NWK skipped-candidate and coalesced wake callbacks are not observed in MATLAB.','Queue/custody state is reconstructed from actual callbacks, not complete live physical-copy state.','DACK releases NSDP custody while retaining HOP capacity until expiry.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['status','matched_enqueue_events','matched_handoff_identity_events','matched_custody_releases','matlab_minus_native_handoff_time_ns_counts']}))
if __name__=='__main__':main()
