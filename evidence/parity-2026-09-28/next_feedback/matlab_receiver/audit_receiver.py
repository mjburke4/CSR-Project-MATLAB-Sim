#!/usr/bin/env python3
"""Offline node-2 receiver/8->2 feedback audit from full seed-132 MATLAB trace.

Reconstructs receiver per-original-(source,destination) custody from emitted
enqueue/release events, validates ACK/DACK choice against emitted MAC feedback
kind, and joins outcomes by the run's packet and HOP sequence identities.
No simulation and no generated-input replay are performed.
"""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
RAW = ROOT / 'return6000/data/s132/attempt_001/raw'
ANALYSIS = RAW.parent / 'analysis'


def rows(path):
    with path.open(newline='') as f:
        yield from csv.DictReader(f)


def write(name, records):
    if not records:
        return
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)


def main():
    apps = {int(r['PacketId']): r for r in rows(ANALYSIS / 'applications.csv')}
    pending = {}
    flow_custody = Counter()
    enqueues = {}
    completions = {}
    admissions = {}
    transmissions = defaultdict(list)
    retries = Counter()
    feedback = []
    receptions = []
    custody_events = []
    node2_service = []
    checks = Counter()
    trace_rows = 0
    for index, r in enumerate(rows(RAW / 'protocol_trace.csv'), 1):
        trace_rows = index
        node = int(r['NodeId']); peer = int(r['PeerId']); pid = int(r['PacketId'])
        ev = r['Event']; t = float(r['TimeSeconds']); seq = int(r['Sequence'])
        positive_data = float(r['ApplicationBytes']) > 0
        if node == 2 and positive_data and ev in {'network_enqueue', 'hop_admit', 'hop_ack', 'hop_dack', 'hop_failed'}:
            a = apps[pid]
            node2_service.append(dict(trace_row=index,time_s=t,event=ev,packet_id=pid,
                source=int(a['SourceId']),destination=int(a['DestinationId']),peer=peer,hop_sequence=seq))
        if node == 2 and positive_data and ev in {'network_enqueue', 'network_custody_release', 'network_submit'}:
            a = apps[pid]; pair = (int(a['SourceId']), int(a['DestinationId']))
            before = flow_custody[pair]
            if ev == 'network_enqueue':
                assert pid not in pending
                enqueues[pid] = dict(trace_row=index, time_s=t, nsdp_before=before,
                                     total_custody_before=len(pending),
                                     submitted_same_flow_before=sum(p['pair'] == pair and p['submitted'] for p in pending.values()))
                pending[pid] = dict(pair=pair, submitted=False)
                flow_custody[pair] += 1
                assert len(pending) == int(r['QueueDepth'])
                checks['enqueue_depth'] += 1
            elif ev == 'network_custody_release':
                assert pending.pop(pid)['pair'] == pair
                flow_custody[pair] -= 1
                checks['custody_release_owner'] += 1
            else:
                assert not pending[pid]['submitted']
                pending[pid]['submitted'] = True
                checks['submit_owner'] += 1
            custody_events.append(dict(trace_row=index, time_s=t, event=ev, packet_id=pid,
                source=pair[0], destination=pair[1], reason=r['Reason'], nsdp_before=before,
                nsdp_after=flow_custody[pair], total_custody_after=len(pending),
                source2_custody=flow_custody[(2,1)], source7_custody=flow_custody[(7,1)],
                source8_custody=flow_custody[(8,1)]))
        if node == 2 and peer == 8 and r['FrameKind'] in {'ACK', 'DACK'} and ev in {'mac_enqueue', 'mac_ack_replace', 'mac_queue_drop'}:
            feedback.append(dict(trace_row=index, time_s=t, event=ev, kind=r['FrameKind'], sequence=seq))
        if node == 2 and peer == 8 and ev == 'hop_receive' and positive_data:
            a = apps[pid]; pair = (int(a['SourceId']), int(a['DestinationId']))
            # All target receptions are unique and accepted in this return.
            assert pid in enqueues and enqueues[pid]['time_s'] == t
            assert not any(x['packet_id'] == pid for x in receptions)
            assert feedback[-1]['time_s'] == t and feedback[-1]['trace_row'] < index
            q = enqueues[pid]; fb = feedback[-1]
            prediction = 'DACK' if q['nsdp_before'] >= 16 else 'ACK'
            assert fb['kind'] == prediction
            checks['receiver_choice_vs_emitted_feedback_kind'] += 1
            receptions.append(dict(trace_row=index, time_s=t, packet_id=pid, source=pair[0],
                destination=pair[1], incoming_hop_sequence=seq, nsdp_before=q['nsdp_before'],
                nsdp_after=flow_custody[pair], submitted_same_flow_before=q['submitted_same_flow_before'],
                total_custody_before=q['total_custody_before'], total_custody_after=len(pending),
                predicted_kind=prediction, emitted_kind=fb['kind'], feedback_queue_event=fb['event'],
                feedback_highest_sequence=fb['sequence'], feedback_trace_row=fb['trace_row'],
                native_application_id_comparable=False))
        if node == 8 and peer == 2 and positive_data:
            if ev == 'hop_admit':
                assert pid not in admissions
                admissions[pid] = dict(trace_row=index, time_s=t, sequence=seq)
            elif ev == 'hop_retry':
                retries[pid] += 1
            elif ev == 'hop_sent':
                transmissions[pid].append(t)
            elif ev in {'hop_ack', 'hop_dack', 'hop_failed'}:
                assert pid not in completions
                completions[pid] = dict(trace_row=index, time_s=t, event=ev, sequence=seq,
                                        retries_before_completion=retries[pid])
    rx_by_pid = {r['packet_id']: r for r in receptions}
    ledger = []
    for pid, ad in admissions.items():
        a = apps[pid]; rx = rx_by_pid.get(pid); c = completions.get(pid)
        if rx:
            assert rx['incoming_hop_sequence'] == ad['sequence']
            assert c and c['event'] == ('hop_ack' if rx['predicted_kind'] == 'ACK' else 'hop_dack')
            assert c['time_s'] >= rx['time_s']
            checks['reception_to_same_packet_sequence_completion'] += 1
        if c:
            assert ad['sequence'] == c['sequence']
        txs = transmissions[pid]
        ledger.append(dict(packet_id=pid, source=int(a['SourceId']), destination=int(a['DestinationId']),
            hop_sequence=ad['sequence'], admitted_s=ad['time_s'], received_s=rx['time_s'] if rx else '',
            receiver_nsdp_before=rx['nsdp_before'] if rx else '', receiver_feedback_kind=rx['emitted_kind'] if rx else '',
            completion_s=c['time_s'] if c else '', completion_event=c['event'] if c else 'unfinished',
            retries_before_completion=c['retries_before_completion'] if c else retries[pid],
            hop_sent_count=len(txs), first_hop_sent_s=txs[0] if txs else '',
            last_hop_sent_s=txs[-1] if txs else '',
            receipt_to_completion_s=c['time_s']-rx['time_s'] if rx and c else '',
            application_outcome=a['Outcome']))
    counts = Counter(r['completion_event'] for r in ledger)
    hop2 = next(r for r in rows(RAW/'hop_nodes.csv') if r['NodeId']=='2')
    nwk2 = next(r for r in rows(RAW/'nwk_nodes.csv') if r['NodeId']=='2')
    assert int(hop2['DataReceived']) == len(receptions)
    assert int(hop2['Duplicates']) == 0
    assert int(hop2['CustodyRefused']) == 0 and int(hop2['NoRouteSuppressed']) == 0
    assert int(hop2['DackGenerated']) == sum(r['emitted_kind']=='DACK' for r in receptions)
    assert len(pending) == int(nwk2['PendingCustody'])
    assert sum(not p['submitted'] for p in pending.values()) == int(nwk2['WaitingForHop'])
    checks['end_counter_closure'] += 7
    assert set(rx_by_pid) <= set(admissions)
    by_flow = []
    for source in (7,8):
        rs = [r for r in receptions if r['source'] == source]
        ls = [r for r in ledger if r['source'] == source]
        ds = [r for r in rs if r['emitted_kind']=='DACK']
        aa = [r for r in rs if r['emitted_kind']=='ACK']
        by_flow.append(dict(source=source, admissions=len(ls), receptions=len(rs),
            receiver_acks=len(aa), receiver_dacks=len(ds),
            ack_fraction_of_receptions=len(aa)/len(rs),
            no_reception_failures=sum(r['completion_event']=='hop_failed' and r['received_s']=='' for r in ls),
            unfinished=sum(r['completion_event']=='unfinished' for r in ls),
            first_reception_s=rs[0]['time_s'], first_dack_s=ds[0]['time_s'],
            first_dack_nsdp=ds[0]['nsdp_before'], mean_nsdp_at_arrival=sum(r['nsdp_before'] for r in rs)/len(rs),
            max_nsdp_at_arrival=max(r['nsdp_before'] for r in rs),
            max_ack_nsdp=max(r['nsdp_before'] for r in aa), min_dack_nsdp=min(r['nsdp_before'] for r in ds),
            mean_receipt_to_completion_s=sum(r['receipt_to_completion_s'] for r in ls if r['received_s']!='')/len(rs),
            end_custody=flow_custody[(source,1)]))
    hist = Counter((r['source'],r['nsdp_before'],r['emitted_kind']) for r in receptions)
    bins = []
    for source in (7,8):
        for lo in range(300,6000,300):
            rr=[r for r in receptions if r['source']==source and lo<=r['time_s']<lo+300]
            bins.append(dict(source=source,start_s=lo,end_s=lo+300,receptions=len(rr),
                acks=sum(r['emitted_kind']=='ACK' for r in rr),dacks=sum(r['emitted_kind']=='DACK' for r in rr),
                mean_nsdp_before=sum(r['nsdp_before'] for r in rr)/len(rr) if rr else ''))
    combined_bins = []
    intervals = [('initial30',300,330)] + [('100s',lo,lo+100) for lo in range(300,6000,100)]
    for name,lo,hi in intervals:
        for source in (2,7,8):
            rr=[r for r in receptions if r['source']==source and lo<=r['time_s']<hi]
            ss=[r for r in node2_service if r['source']==source and lo<=r['time_s']<hi]
            ec=Counter(r['event'] for r in ss)
            combined_bins.append(dict(interval=name,source=source,start_s=lo,end_s=hi,
                node2_nwk_enqueue=ec['network_enqueue'],node2_hop_admit=ec['hop_admit'],
                node2_hop_ack=ec['hop_ack'],node2_hop_dack=ec['hop_dack'],node2_hop_failed=ec['hop_failed'],
                incoming_8_2_receptions=len(rr),incoming_8_2_acks=sum(r['emitted_kind']=='ACK' for r in rr),
                incoming_8_2_dacks=sum(r['emitted_kind']=='DACK' for r in rr),
                receiver_nsdp_before_mean=sum(r['nsdp_before'] for r in rr)/len(rr) if rr else '',
                receiver_nsdp_before_max=max((r['nsdp_before'] for r in rr),default='')))
    dack_runs = []
    for source in (7,8):
        current=[]
        def finish_run(run):
            if run:
                dack_runs.append(dict(source=source,receptions=len(run),start_s=run[0]['time_s'],end_s=run[-1]['time_s'],
                    elapsed_s=run[-1]['time_s']-run[0]['time_s'],
                    first_packet_id=run[0]['packet_id'],last_packet_id=run[-1]['packet_id'],
                    min_nsdp_before=min(r['nsdp_before'] for r in run),max_nsdp_before=max(r['nsdp_before'] for r in run)))
        for rx in [r for r in receptions if r['source']==source]:
            if rx['emitted_kind']=='DACK':current.append(rx)
            else:finish_run(current);current=[]
        finish_run(current)
    summary = dict(seed=132, link='8->2', trace_records=trace_rows, checks=dict(checks),
        data_admissions=len(admissions), receiver_receptions=len(receptions), unique_received_packets=len(rx_by_pid),
        emitted_data_ack=counts['hop_ack'], emitted_data_dack=counts['hop_dack'],
        data_completion_counts=dict(counts), final_node2_custody=len(pending),
        final_node2_custody_by_original_source={str(src):flow_custody[(src,1)] for src in (2,7,8)},
        flow_summary=by_flow, raw_feedback_queue_events=len(feedback),
        longest_consecutive_dack_runs=[max((r for r in dack_runs if r['source']==source),key=lambda r:r['receptions']) for source in (7,8)],
        limitations=[
          'ACK/DACK bitmaps are not exported. MAC queue feedback kind predicts the new reception classification, not every bit in that cumulative frame.',
          'Same-packet/sequence completion matches do not identify the physical ACK envelope that caused completion; cumulative later feedback can complete an earlier packet.',
          'All audited receptions are first/unique accepted DATA, verified by full trace and node counters. Conclusions do not validate duplicate, no-route, or custody-refusal branches.',
          'NSDP reconstructed from actual enqueue/release stream using production custody definition; this is observational consistency, not a MATLAB runtime common-input test.',
          'No per-application identity alignment exists across engines. Compare per-flow cohorts, never join MATLAB PacketId to native application_sequence.'
        ],
        input_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (RAW/'protocol_trace.csv', RAW/'hop_nodes.csv', RAW/'nwk_nodes.csv', ANALYSIS/'applications.csv')})
    write('receiver_decisions.csv',receptions)
    write('node2_custody_events.csv',custody_events)
    write('link_8_2_application_outcomes.csv',ledger)
    write('flow_summary.csv',by_flow)
    write('arrival_nsdp_histogram.csv',[dict(source=k[0],nsdp_before=k[1],feedback_kind=k[2],count=v) for k,v in sorted(hist.items())])
    write('receiver_300s_bins.csv',bins)
    write('node2_service_events.csv',node2_service)
    write('receiver_service_100s_bins.csv',combined_bins)
    write('consecutive_dack_runs.csv',dack_runs)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
