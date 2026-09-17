#!/usr/bin/env python3
"""Replay source-derived MATLAB 7→8 DATA flow-control state from existing traces.

Run: python3 t21-work/matlab/replay_flow_threshold.py [--workspace ROOT]
Required layout is the same as extract_matlab.py. No simulation is executed.
Threshold and AckCount are NOT raw trace columns. They are derived by applying
the hash-verified Layer.m update rules to its ordered, complete DATA callbacks.
"""
from __future__ import annotations
import argparse
import collections
import csv
import json
import math
from pathlib import Path
from extract_matlab import Evidence, sha, csv_out, area, PARENT_SHA


def replay(root, seed):
    ev = Evidence(root,seed)
    cfg = ev.js('raw/summary.json')['Config']['Hop']
    assert cfg['DataQueuedRetryPolicy'] == 'actual-tx'
    endpoint = next(r for r in ev.rows('raw/hop_nodes.csv') if int(r['NodeId'])==7)
    active = {}
    threshold, ack_count, outstanding = 0, 0, 0
    admits = collections.Counter()
    counts = collections.Counter()
    rows, transitions = [], []
    threshold_intervals = []
    capacity_intervals = []
    threshold_since = 0.0
    capacity_since = 0.0
    retry_at_ack = collections.Counter()
    retry_at_dack = collections.Counter()
    observed_peers = set()
    used = {'hop_admit','hop_retry','hop_ack','hop_dack','hop_failed','hop_dack_expired'}
    for ordinal, r in enumerate(ev.rows('raw/protocol_trace.csv'),1):
        if int(r['NodeId']) != 7 or r['FrameKind'] != 'DATA' or r['Event'] not in used:
            continue
        event, peer, seq, packet, t = r['Event'], int(r['PeerId']), int(r['Sequence']), int(r['PacketId']), float(r['TimeSeconds'])
        observed_peers.add(peer)
        assert peer==8, 'Unexpected DATA peer: add a per-neighbor state map before replaying.'
        key = peer, seq
        before_threshold, before_ack, before_out = threshold, ack_count, outstanding
        before_retry = 0
        counts[event] += 1
        if event=='hop_admit':
            assert key not in active
            assert outstanding <= threshold, ('Neighbor admission rule violated',seed,ordinal,outstanding,threshold)
            assert outstanding <= cfg['PendingThreshold'], ('Global DATA admission rule violated',seed,ordinal)
            admits[threshold] += 1
            active[key] = {'packet':packet,'retries':0,'dack':False,'dack_s':None,'admit_s':t}
            outstanding += 1
        else:
            assert key in active and active[key]['packet']==packet, (seed,ordinal,key)
            entry = active[key]
            before_retry = entry['retries']
            if event=='hop_retry':
                assert not entry['dack']
                entry['retries'] += 1
                assert entry['retries'] <= cfg['MaxResends']
            elif event=='hop_ack':
                assert not entry['dack']
                retry_at_ack[entry['retries']] += 1
                outstanding -= 1
                ack_count += 1
                if ack_count >= 3:
                    threshold = min(cfg['FlowThresholdMax'],threshold+1)
                    ack_count = 0
                # Source applies this reset AFTER possible third-ACK growth.
                if entry['retries'] > 0:
                    ack_count = 0
                del active[key]
            elif event=='hop_dack':
                assert not entry['dack']
                retry_at_dack[entry['retries']] += 1
                entry['dack'] = True
                entry['dack_s'] = t
                ack_count = 0
                # Capacity remains allocated until hop_dack_expired.
            elif event=='hop_failed':
                assert not entry['dack']
                outstanding -= 1
                ack_count = 0
                threshold = max(0,threshold-1)
                del active[key]
            elif event=='hop_dack_expired':
                assert entry['dack']
                requested_hold = cfg['DackHoldSeconds']*(2 if entry['retries'] >= cfg['MaxResends'] else 1)
                assert t-entry['dack_s'] >= requested_hold-1e-8
                outstanding -= 1
                del active[key]
        assert outstanding == len(active) and outstanding >= 0
        if threshold != before_threshold:
            threshold_intervals.append((threshold_since,t,before_threshold))
            threshold_since=t
            transitions.append({'seed':seed,'row':ordinal,'time_s':t,'event':event,
                'threshold_before':before_threshold,'threshold_after':threshold,
                'ack_count_before':before_ack,'retry_requests_before':before_retry})
        if outstanding != before_out:
            capacity_intervals.append((capacity_since,t,before_out))
            capacity_since=t
        rows.append({'seed':seed,'row':ordinal,'time_s':t,'event':event,'peer':peer,
            'packet_id':packet,'sequence':seq,'threshold_before':before_threshold,
            'threshold_after':threshold,'ack_count_before':before_ack,'ack_count_after':ack_count,
            'outstanding_before':before_out,'outstanding_after':outstanding,
            'retry_requests_before':before_retry})
    threshold_intervals.append((threshold_since,6000.0,threshold))
    capacity_intervals.append((capacity_since,6000.0,outstanding))
    assert outstanding == int(endpoint['PendingData'])
    assert sum(e['dack'] for e in active.values()) == int(endpoint['DackHoldCount'])
    assert sum(not e['dack'] for e in active.values())+int(endpoint['ControlPending']) == int(endpoint['ResendQueueDepth'])
    fields={'hop_admit':'Admitted','hop_retry':'Retransmissions','hop_ack':'Acknowledged',
        'hop_dack':'Dacked','hop_failed':'Failed','hop_dack_expired':'DackExpired'}
    for event, field in fields.items():
        assert counts[event] == int(endpoint[field]), (seed,event)
    seconds = collections.Counter()
    for a,b,state in threshold_intervals:
        seconds[state] += max(0,min(6000,b)-max(300,a))
    assert math.isclose(sum(seconds.values()),5700,abs_tol=1e-8)
    timeline=[]
    for i in range(20):
        lo,hi=i*300,(i+1)*300
        trows=[r for r in rows if lo<=r['time_s']<hi or hi==6000 and r['time_s']==6000]
        timeline.append({'seed':seed,'start_s':lo,'end_s':hi,
            'hop_admissions':sum(r['event']=='hop_admit' for r in trows),
            'mean_source_derived_threshold':sum(max(0,min(hi,b)-max(lo,a))*state for a,b,state in threshold_intervals)/300,
            'mean_callback_derived_data_outstanding':sum(max(0,min(hi,b)-max(lo,a))*state for a,b,state in capacity_intervals)/300,
            'threshold_growth_events':sum(r['threshold_after']>r['threshold_before'] for r in trows),
            'threshold_decrease_events':sum(r['threshold_after']<r['threshold_before'] for r in trows)})
    return {'seed':seed,'node':7,'peer':8,'state_kind':'source-derived replay; not exported threshold observations',
        'receipt_sha256':ev.receipt_sha,'verified_artifacts':ev.verified,
        'threshold_at_admission_histogram':dict(sorted(admits.items())),
        'threshold_seconds_300_to_6000':dict(sorted(seconds.items())),
        'threshold_growth_count':sum(r['threshold_after']>r['threshold_before'] for r in transitions),
        'threshold_decrease_count':sum(r['threshold_after']<r['threshold_before'] for r in transitions),
        'ack_retry_request_histogram':dict(sorted(retry_at_ack.items())),
        'dack_retry_request_histogram':dict(sorted(retry_at_dack.items())),
        'event_counts':dict(counts),'all_admissions_neighbor_and_global_data_thresholds_satisfied':True,
        'pending_endpoint_verified':True,'pending_data_at_stop':outstanding,
        'pending_controls_at_stop':int(endpoint['ControlPending']),
        'source_derived_threshold_at_stop':threshold,'source_derived_ack_count_at_stop':ack_count,
        'mean_data_outstanding_300_to_6000':sum(max(0,min(6000,b)-max(300,a))*state for a,b,state in capacity_intervals)/5700,
        'threshold_transitions':transitions}, rows, timeline


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent)
    args=p.parse_args(); root=args.workspace.resolve();out=args.output.resolve()
    assert sha(root/'csr20/evidence/t19/owner.zip') == PARENT_SHA
    base=json.loads((out/'matlab_node8.json').read_text())
    metadata_path=root/'t20-return-review/owner/metadata.json'
    assert sha(metadata_path)==base['t20_metadata_sha256']
    metadata=json.loads(metadata_path.read_text())
    for stage in metadata['StageReceipts']:
        if stage['Phase'] in ('s129','s130'):
            assert sha(root/'t20-return-review/owner'/stage['File']) == stage['SHA256']
    source='csr20/+csr/+hop/Layer.m'
    assert sha(root/source)==base['source_files_read_sha256'][source]
    results=[]; rows=[];timeline=[]
    for seed in (128,129,130):
        result,r,t=replay(root,seed);results.append(result);rows.extend(r);timeline.extend(t)
        print(seed,json.dumps(result['threshold_at_admission_histogram']),flush=True)
    report={'schema':'csr-tranche21-matlab-flow-threshold-replay-v1','status':'completed',
        'matlab_executed':False,'source_modified':False,'analysis_script_sha256':sha(Path(__file__)),
        'helper_sha256':sha(Path(__file__).with_name('extract_matlab.py')),
        'source_sha256':sha(root/source),'source':source,'t20_metadata_sha256':sha(metadata_path),
        'rules':['Initial Threshold=0, AckCount=0, Outstanding=0.',
            'DATA ACK releases outstanding, increments AckCount, grows threshold on third ACK up to FlowThresholdMax; then any retried ACK resets AckCount.',
            'DATA DACK resets AckCount and retains outstanding through DACK expiry.',
            'DATA failure releases outstanding, resets AckCount, decrements threshold to floor zero.',
            'hop_retry counts queued resend requests; it does not prove a distinct radio transmission.'],
        'limitations':['Threshold and AckCount are source-derived state; neither is an exported raw column. Replay is conditional on the accepted source and complete callbacks.',
            'No final per-neighbor threshold/AckCount snapshot exists; final DATA/resend/DACK populations and all event counters provide independent endpoint checks.',
            'Every DATA admission satisfies reconstructed neighbor/global DATA limits. Shared DATA/control resend-table limit is not reconstructed by this supplement.',
            'Different engines and seeds need not share packet, callback, or random-number histories; threshold differences do not alone prove an implementation defect.'],
        'results':results}
    (out/'matlab_threshold_replay.json').write_text(json.dumps(report,indent=2)+'\n')
    csv_out(out/'matlab_threshold_events.csv',rows)
    csv_out(out/'matlab_threshold_timeline_300s.csv',timeline)


if __name__=='__main__':
    main()
