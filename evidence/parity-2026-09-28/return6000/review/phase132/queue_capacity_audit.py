#!/usr/bin/env python3
"""Reconstruct MATLAB NWK custody and HOP capacity from complete DATA events.

This is observational state arithmetic from the supplied source semantics;
it is not independent evidence that the MATLAB/ns-3 mechanisms differ.
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
RAW=ROOT/'return6000/data/s132/attempt_001/raw'
def rows(p):
    with p.open(newline='') as f: return list(csv.DictReader(f))
def write(p,rs):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0])); w.writeheader(); w.writerows(rs)
def main():
    apps={int(r['PacketId']):r for r in rows(RAW.parent/'analysis/applications.csv')}
    state={n:dict(t=300.,pending={},outstanding=0,threshold=0,acks=0,retries={},holds={},
                 integral=Counter(),events=Counter(),peak_wait=0,peak_pending=0,peak_outstanding=0,
                 peer=None,admissions=0) for n in (2,3,4,5,7,8)}
    pending_rows=[]; holds=[]; traffic=Counter()
    relevant={'network_enqueue','network_submit','network_custody_release','hop_admit',
              'hop_retry','hop_ack','hop_dack','hop_dack_expired','hop_failed'}
    def integrate(s,t):
        t=max(300.,min(6000.,t)); dt=t-s['t']; assert dt>=0
        wait=sum(not p['submitted'] for p in s['pending'].values())
        closed=(s['outstanding']>s['threshold'] or s['outstanding']>16)
        s['integral']['waiting_count_seconds']+=wait*dt
        s['integral']['custody_count_seconds']+=len(s['pending'])*dt
        s['integral']['hop_capacity_count_seconds']+=s['outstanding']*dt
        s['integral']['dack_hold_count_seconds']+=len(s['holds'])*dt
        s['integral']['neighbor_threshold_seconds']+=s['threshold']*dt
        if wait:s['integral']['waiting_seconds']+=dt
        if closed:s['integral']['closed_gate_seconds']+=dt
        if wait and closed:s['integral']['waiting_and_closed_seconds']+=dt
        if wait and not closed:s['integral']['waiting_and_open_seconds']+=dt
        s['t']=t
    with (RAW/'protocol_trace.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            ev=row['Event']; n=int(row['NodeId'])
            if n not in state or ev not in relevant or float(row['ApplicationBytes'])<=0:continue
            s=state[n]; t=float(row['TimeSeconds']); pid=int(row['PacketId']); peer=int(row['PeerId'])
            if n in (2,8) and ev in ('network_enqueue','network_submit','hop_admit','hop_ack','hop_dack','hop_failed','hop_dack_expired'):
                traffic[n,int(apps[pid]['SourceId']),ev]+=1
            integrate(s,t); s['events'][ev]+=1
            if ev=='network_enqueue':
                assert pid not in s['pending']; s['pending'][pid]=dict(enqueued=t,submitted=False,submitted_t=None)
                assert len(s['pending'])==int(row['QueueDepth'])
            elif ev=='network_submit':
                assert pid in s['pending'] and not s['pending'][pid]['submitted']
                s['pending'][pid].update(submitted=True,submitted_t=t)
            elif ev=='network_custody_release':
                assert pid in s['pending']; s['pending'].pop(pid)
            elif ev=='hop_admit':
                assert row['FrameKind']=='DATA'
                if s['peer'] is not None:assert s['peer']==peer
                s['peer']=peer
                assert s['outstanding']<=s['threshold'] and s['outstanding']<=16
                assert pid not in s['retries']; s['retries'][pid]=0
                s['outstanding']+=1; s['admissions']+=1
            elif ev=='hop_retry':
                if row['FrameKind']!='DATA':continue
                assert pid in s['retries'];s['retries'][pid]+=1
            elif ev=='hop_ack':
                retry=s['retries'].pop(pid);s['outstanding']-=1;s['acks']+=1
                if s['acks']>=3:s['threshold']=min(16,s['threshold']+1);s['acks']=0
                if retry>0:s['acks']=0
            elif ev=='hop_dack':
                retry=s['retries'].pop(pid);s['acks']=0
                s['holds'][pid]=dict(start=t,expected_hold_s=40 if retry>=2 else 20,retries=retry)
            elif ev=='hop_dack_expired':
                h=s['holds'].pop(pid);s['outstanding']-=1
                holds.append(dict(node=n,source=int(apps[pid]['SourceId']),packet_id=pid,
                                  hold_start_s=h['start'],expiry_s=t,observed_hold_s=t-h['start'],
                                  expected_hold_s=h['expected_hold_s'],retry_count=h['retries']))
                assert abs(t-h['start']-h['expected_hold_s']-1/36e6)<1e-7
            elif ev=='hop_failed':
                s['retries'].pop(pid);s['outstanding']-=1;s['acks']=0;s['threshold']=max(0,s['threshold']-1)
            assert s['outstanding']==len(s['holds'])+len(s['retries'])
            wait=sum(not p['submitted'] for p in s['pending'].values())
            s['peak_wait']=max(s['peak_wait'],wait)
            s['peak_pending']=max(s['peak_pending'],len(s['pending']))
            s['peak_outstanding']=max(s['peak_outstanding'],s['outstanding'])
    nwk={int(r['NodeId']):r for r in rows(RAW/'nwk_nodes.csv')}
    hop={int(r['NodeId']):r for r in rows(RAW/'hop_nodes.csv')}
    node_rows=[]
    for node,s in state.items():
        integrate(s,6000)
        assert len(s['pending'])==int(nwk[node]['PendingCustody'])
        assert sum(not p['submitted'] for p in s['pending'].values())==int(nwk[node]['WaitingForHop'])
        assert s['peak_pending']==int(nwk[node]['MaxNetworkQueueDepth'])
        assert s['outstanding']==int(hop[node]['PendingData'])
        assert s['peak_outstanding']==int(hop[node]['PeakPendingData'])
        assert len(s['holds'])==int(hop[node]['DackHoldCount'])
        assert s['admissions']==int(hop[node]['Admitted'])
        node_rows.append(dict(node=node,next_hop=s['peer'],mean_waiting_nwk=s['integral']['waiting_count_seconds']/5700,
            mean_owned_copies=s['integral']['custody_count_seconds']/5700,
            mean_hop_capacity_in_use=s['integral']['hop_capacity_count_seconds']/5700,
            mean_dack_holds=s['integral']['dack_hold_count_seconds']/5700,
            mean_neighbor_threshold=s['integral']['neighbor_threshold_seconds']/5700,
            percent_time_nwk_waiting=100*s['integral']['waiting_seconds']/5700,
            percent_time_capacity_gate_closed=100*s['integral']['closed_gate_seconds']/5700,
            percent_time_waiting_and_gate_closed=100*s['integral']['waiting_and_closed_seconds']/5700,
            waiting_while_gate_open_s=s['integral']['waiting_and_open_seconds'],
            max_waiting_nwk=s['peak_wait'],max_owned_copies=s['peak_pending'],
            end_waiting_nwk=int(nwk[node]['WaitingForHop']),end_submitted_custody=len(s['pending'])-int(nwk[node]['WaitingForHop']),
            end_hop_capacity=s['outstanding'],end_neighbor_threshold=s['threshold'],end_dack_holds=len(s['holds']),
            data_admissions=s['admissions'],acks=s['events']['hop_ack'],dacks=s['events']['hop_dack'],failures=s['events']['hop_failed']))
        for pid,p in s['pending'].items():
            a=apps[pid]
            pending_rows.append(dict(node=node,source=int(a['SourceId']),packet_id=pid,model_outcome=a['Outcome'],
                state='submitted_custody' if p['submitted'] else 'waiting_nwk',
                enqueued_s=p['enqueued'],submitted_s=p['submitted_t'],
                application_age_s=6000-float(a['GeneratedSeconds']),current_node_residence_s=6000-p['enqueued']))
    assert len(pending_rows)==sum(a['Outcome']=='pending' for a in apps.values())
    assert all(a['model_outcome']=='pending' for a in pending_rows)
    assert len({p['packet_id'] for p in pending_rows})==len(pending_rows)
    write(OUT/'queue_capacity_by_node.csv',node_rows)
    write(OUT/'pending_copy_locations.csv',pending_rows)
    write(OUT/'dack_capacity_holds.csv',holds)
    native_folder=ROOT/'return6000/history/longrun_recovery/extracted/latency-review/latency-review/native/output'
    native_capacity=json.loads((native_folder/'s132-capacity.json').read_text())
    assert not native_capacity['state_continuity_errors']
    cap_rows=[]
    for link in native_capacity['links']:
        n=link['node']; ours=next(r for r in node_rows if r['node']==n)
        occ=link['occupancy'];counts=link['event_counts']
        cap_rows.append(dict(node=n,peer=link['peer'],
            matlab_mean_outstanding_slots=ours['mean_hop_capacity_in_use'],ns3_mean_outstanding_slots=occ['mean_outstanding_slots'],
            matlab_mean_dack_held_slots=ours['mean_dack_holds'],ns3_mean_dack_held_slots=occ['mean_dack_held_slots'],
            matlab_mean_effective_window_slots=ours['mean_neighbor_threshold']+1,ns3_mean_effective_window_slots=occ['mean_window_slots'],
            matlab_admissions=ours['data_admissions'],ns3_admissions=counts['hop_admission:admitted'],
            matlab_acks=ours['acks'],ns3_acks=counts['hop_completion:ack'],
            matlab_dacks=ours['dacks'],ns3_dacks=counts['hop_completion:dack'],
            matlab_failures=ours['failures'],ns3_no_ack_completions=counts['hop_completion:no_ack']))
    write(OUT/'link_capacity_comparison.csv',cap_rows)
    event_map={'nwk_enqueue':'network_enqueue','nwk_forward':'network_submit','hop_admission:admitted':'hop_admit',
        'hop_completion:ack':'hop_ack','hop_completion:dack':'hop_dack','hop_completion:no_ack':'hop_failed',
        'hop_capacity_release:dack_expiry':'hop_dack_expired'}
    native_traffic=Counter()
    for row in rows(native_folder/'s132-capacity-cohorts.csv'):
        for k,v in event_map.items():native_traffic[int(row['node']),int(row['source']),v]+=int(row[k])
    traffic_rows=[]
    for n,src in sorted({(n,s) for n,s,e in traffic}|{(n,s) for n,s,e in native_traffic}):
        row=dict(node=n,source=src)
        for ev in event_map.values():
            row['matlab_'+ev]=traffic[n,src,ev];row['ns3_'+ev]=native_traffic[n,src,ev]
        traffic_rows.append(row)
    write(OUT/'link_source_traffic_comparison.csv',traffic_rows)
    print(json.dumps(node_rows,indent=2))
    (OUT/'queue_capacity_validation.json').write_text(json.dumps(dict(
        pending_copies=len(pending_rows),expired_dack_holds=len(holds),
        all_nwk_enqueue_depths_match=True,all_final_node_counters_match=True,
        all_hop_admissions_satisfy_reconstructed_capacity=True,
        all_dack_hold_durations_match_policy_plus_tick=True,
        scope='Current MATLAB only; observed state accounting, not proof of a cross-engine rule mismatch.'),indent=2)+'\n')

if __name__=='__main__':main()
