"""Independent read-only T8 event/feedback audit. Does not use reporting helpers."""
import csv
import gzip
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import statistics
from zipfile import ZipFile

ROOT = Path('/workspace/scratch/1a5b1ad6ce1b')
SOURCE = ROOT / 'tranche8'
UPLOAD = ROOT / 'upload/tranche8_evidence.zip'
OUTPUT = ROOT / 't8_outcomes'

def zrows(z, path):
    with io.TextIOWrapper(z.open(path), encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)

def frows(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)

def desc(values, cv=False):
    value = dict(values=values, mean=statistics.fmean(values), minimum=min(values), maximum=max(values),
                 sample_sd=statistics.stdev(values))
    if cv:
        value['sample_cv_percent'] = 100*statistics.stdev(values)/statistics.fmean(values)
    return value

def apps_summary(sent, receives, drops, attempts, duration, width, matlab):
    ids = set()
    delays = []
    buckets = defaultdict(list)
    flows = defaultdict(lambda: dict(admitted=0, delivered=0, delay_sum_s=0.0, delay_samples=0))
    for key, send in sent.items():
        flows[(send['src'], send['dst'])]['admitted'] += 1
    for key, time, size in receives:
        assert key in sent and size == sent[key]['size'] and time >= sent[key]['time']
        assert 0 <= time < duration
        delay = time - sent[key]['time']
        delays.append(delay)
        buckets[math.floor(time/width)].append(delay)
        f = flows[(sent[key]['src'], sent[key]['dst'])]
        f['delivered'] += 1
        f['delay_sum_s'] += delay
        f['delay_samples'] += 1
        ids.add(key)
    assert not (ids & set(drops))
    for f in flows.values():
        f['mean_packet_latency_s'] = f['delay_sum_s']/f['delay_samples'] if f['delay_samples'] else None
        f['unmatched_admitted'] = f['admitted']-f['delivered']
    return dict(attempts=attempts, admitted=len(sent), admission_blocked=attempts-len(sent),
                delivered=len(receives), delivered_unique=len(ids), duplicate_delivery_events=len(receives)-len(ids),
                explicit_drops=len(drops) if matlab else None,
                pending=len(sent)-len(ids)-len(drops) if matlab else None,
                unmatched_admitted=len(sent)-len(ids),
                delay_samples=len(delays), delay_sum_s=math.fsum(delays), mean_packet_latency_s=statistics.fmean(delays),
                max_packet_latency_s=max(delays),
                mean_populated_bucket_latency_s=statistics.fmean(statistics.fmean(v) for v in buckets.values()),
                network_bytes_received=sum(size for _,_,size in receives),
                flows=[dict(source=key[0],destination=key[1],**value) for key,value in sorted(flows.items())])

def matlab_apps(z, key, case):
    directory = f'b/{key}'
    sent, receives, drops, counts = {}, [], {}, Counter()
    for r in zrows(z, directory+'/raw/protocol_trace.csv'):
        event = r['Event']; counts[event] += 1
        packet = int(r['PacketId'])
        if event == 'app_generate':
            assert packet not in sent
            sent[packet] = dict(time=float(r['TimeSeconds']),src=int(r['NodeId']),dst=int(r['PeerId']),size=int(r['ApplicationBytes'])+7)
        elif event == 'app_receive':
            assert packet in sent
            assert sent[packet]['src'] == int(r['PeerId']) and sent[packet]['dst'] == int(r['NodeId'])
            receives.append((packet,float(r['TimeSeconds']),int(r['ApplicationBytes'])+7))
        elif event == 'app_drop':
            assert packet in sent and packet not in drops
            drops[packet] = r['Reason']
    attempts = sum(int(r['Attempts']) for r in zrows(z,directory+'/raw/application_admission_statistics.csv'))
    result = apps_summary(sent, receives, drops, attempts, case['duration_s'], case['bucket_width_s'], True)
    receive_map = {packet:time for packet,time,_ in receives}
    application_rows = list(zrows(z,directory+'/analysis/applications.csv'))
    assert len(application_rows) == len(sent)
    for r in application_rows:
        packet = int(r['PacketId']); s=sent[packet]
        assert (int(r['SourceId']),int(r['DestinationId']),int(r['ApplicationBytes'])+7) == (s['src'],s['dst'],s['size'])
        assert float(r['GeneratedSeconds']) == s['time']
        expected = 'delivered' if packet in receive_map else 'dropped' if packet in drops else 'pending'
        assert r['Outcome'] == expected
        if expected == 'delivered':
            assert receive_map[packet] == float(r['ReceivedSeconds'])
            assert math.isclose(float(r['LatencySeconds']),receive_map[packet]-s['time'],abs_tol=2e-10)
    result['raw_event_count'] = sum(counts.values())
    result['application_rows_reconstructed_exactly'] = True
    return result

def ns3_apps(directory, case):
    sent, receives = {}, []
    for r in frows(directory/'ns3-trace.csv.gz'):
        if r['event'] not in ('app_send', 'nwk_delivery'): continue
        key = (int(r['src']),int(r['dst']),int(r['sequence']))
        if r['event'] == 'app_send':
            assert key not in sent
            sent[key] = dict(time=float(r['time_s']),src=key[0],dst=key[1],size=int(r['size_bytes']))
        else:
            receives.append((key,float(r['time_s']),int(r['size_bytes'])))
    attempts = sum(int(r['attempts']) for r in frows(directory/'app-admission-diagnostics.csv'))
    return apps_summary(sent,receives,{},attempts,case['duration_s'],case['bucket_width_s'],False)

def feedback_summary(selected, actual, ns3=False, contexts=None):
    f = dict(window='has_ack_window',kind='frame_type',rate='selected_rate_key_kbps',power='selected_power_dbm',
             actual_rate='actual_rate_key_kbps',actual_power='actual_power_dbm',time='time_s',decision='decision_id') if ns3 else dict(
             window='HasAckWindow',kind='FrameKind',rate='SelectedRateKeyKbps',power='SelectedPowerDbm',actual_rate='RateKeyKbps',
             actual_power='TxPowerDbm',time='TimeSeconds',decision='DecisionId')
    def dist(rows,rate,power):
        return [dict(kind=k[0],rate_key_kbps=k[1],power_dbm=k[2],count=n) for k,n in sorted(Counter(
            (r[f['kind']],float(r[rate]),float(r[power])) for r in rows).items())]
    out = dict(selection_count=len(selected),actual_feedback_members=len(actual),
               distinct_decisions_transmitted=len({r[f['decision']] for r in actual}),forms=[])
    for flag,label in [('1','ordinary_data_window'),('0','exact_sequence_control')]:
        s=[r for r in selected if r[f['window']]==flag]; a=[r for r in actual if r[f['window']]==flag]
        changes=[r for r in a if float(r[f['actual_rate']])!=float(r[f['rate']]) or float(r[f['actual_power']])!=float(r[f['power']])]
        out['forms'].append(dict(form=label,selection_count=len(s),actual_feedback_members=len(a),
            selected_distribution=dist(s,f['rate'],f['power']),actual_distribution=dist(a,f['actual_rate'],f['actual_power']),
            rate_override_count=sum(float(r[f['actual_rate']])!=float(r[f['rate']]) for r in a),
            power_override_count=sum(float(r[f['actual_power']])!=float(r[f['power']]) for r in a),
            first_override_time_s=min(float(r[f['time']]) for r in changes) if changes else None,
            last_override_time_s=max(float(r[f['time']]) for r in changes) if changes else None,
            first_selection_time_s=min(float(r[f['time']]) for r in s),last_selection_time_s=max(float(r[f['time']]) for r in s)))
    if ns3:
        out['ordinary_data_context_count']=len(contexts)
        assert {r['decision_id'] for r in selected if r['has_ack_window']=='1'} == {r['decision_id'] for r in contexts}
        out['incoming_vs_selected_rate_differences']=sum(float(r['incoming_rate_key_kbps'])!=float(r['selected_rate_key_kbps']) for r in contexts)
        out['incoming_vs_selected_power_differences']=sum(float(r['incoming_power_dbm'])!=float(r['selected_power_dbm']) for r in contexts)
        out['selection_input_values']={k:sorted({float(r[k]) for r in selected}) for k in ('peer_s0_dbm','path_loss_db','hop_failure_count')}
        out['queue_admission_not_observed']=True
    else:
        assert all(r['InputContextAvailable']=='1' and r['FrameKind']=='ACK' for r in selected)
        assert all((r['HasAckWindow']=='1')==(r['InputFrameKind']=='DATA') for r in selected)
        out['queue_dispositions']=dict(Counter(r['QueueDisposition'] for r in selected))
        out['queue_dispositions_by_form']={label:dict(Counter(r['QueueDisposition'] for r in selected if r['HasAckWindow']==flag)) for flag,label in [('1','ordinary_data_window'),('0','exact_sequence_control')]}
        out['incoming_vs_selected_rate_differences']=sum(float(r['InputRateKeyKbps'])!=float(r['SelectedRateKeyKbps']) for r in selected)
        out['incoming_vs_selected_power_differences']=sum(float(r['InputPowerDbm'])!=float(r['SelectedPowerDbm']) for r in selected)
        out['control_types']=dict(Counter(r['InputControlType'] for r in selected if r['InputFrameKind']=='CONTROL'))
        decision_map={r['DecisionId']:r for r in selected}
        for row in actual:
            assert row['DecisionMatched']=='1'
            d=decision_map[row['DecisionId']]
            assert all(row[k]==d[k] for k in ('NodeId','PeerId','FrameKind','Sequence','HasAckWindow','AckBitmap','DackBitmap','SelectedRateKeyKbps','SelectedPowerDbm'))
        out['all_actual_members_correlated_independently']=True
        out['selected_decisions_without_observed_transmission']=len(selected)-out['distinct_decisions_transmitted']
        out['maximum_actual_repeats_per_decision']=max(Counter(r['DecisionId'] for r in actual).values())
    return out

def main():
    out=dict(schema='csr-t8-independent-outcomes-review-v1',upload_sha256=hashlib.sha256(UPLOAD.read_bytes()).hexdigest(),
             method='Independent raw protocol/application/feedback CSV reconstruction; no tranche8 reporting helpers imported.',cases=[])
    with ZipFile(UPLOAD) as z:
        plan=json.loads(z.read('diagnostic_plan.json'))
        summary_rows={r['CaseId']:r for r in zrows(z,'benchmark_summary.csv')}
        for case in plan['cases']:
            key=('a' if case['base_case_id'].startswith('two') else 'c')+str(case['seed'])
            ref=SOURCE/case['reference_directory']
            row=dict(case_id=case['case_id'],seed=case['seed'],base_case_id=case['base_case_id'])
            row['ns3_reference'] = dict(directory=case['reference_directory'],
                files={name:hashlib.sha256((ref/name).read_bytes()).hexdigest() for name in
                       ['ns3-trace.csv.gz','ns3-link-decisions.csv.gz','app-admission-diagnostics.csv']})
            row['matlab']=matlab_apps(z,key,case); row['ns3']=ns3_apps(ref,case)
            for k,field in [('admitted','Generated'),('delivered','Received'),('explicit_drops','Dropped'),('pending','Pending')]:
                assert row['matlab'][k]==int(summary_rows[case['case_id']][field])
            assert math.isclose(row['matlab']['mean_packet_latency_s'],float(summary_rows[case['case_id']]['MeanLatencySeconds']),abs_tol=2e-10)
            ms=list(zrows(z,f'b/{key}/raw/link_decisions.csv')); ma=list(zrows(z,f'b/{key}/raw/actual_feedback.csv'))
            nr=list(frows(ref/'ns3-link-decisions.csv.gz'))
            ns=[r for r in nr if r['stage']=='feedback_selection']; na=[r for r in nr if r['stage']=='ota_segment']; nc=[r for r in nr if r['stage']=='ack_response_context']
            row['matlab_feedback']=feedback_summary(ms,ma)
            row['ns3_feedback']=feedback_summary(ns,na,True,nc)
            row['delivered_difference']=row['matlab']['delivered']-row['ns3']['delivered']
            row['delivered_relative_difference_percent']=100*row['delivered_difference']/row['ns3']['delivered']
            row['flow_pairs']=[]
            for mf,nf in zip(row['matlab']['flows'],row['ns3']['flows']):
                assert (mf['source'],mf['destination']) == (nf['source'],nf['destination'])
                row['flow_pairs'].append(dict(source=mf['source'],destination=mf['destination'],matlab=mf,ns3=nf,
                    delivered_difference=mf['delivered']-nf['delivered'],
                    delivered_relative_difference_percent=100*(mf['delivered']-nf['delivered'])/nf['delivered']))
            out['cases'].append(row)
    out['groups']=[]
    for base in sorted({r['base_case_id'] for r in out['cases']}):
        cases=[r for r in out['cases'] if r['base_case_id']==base]
        group=dict(base_case_id=base,seeds=[r['seed'] for r in cases],simulators={})
        for sim in ['matlab','ns3']:
            data=[r[sim] for r in cases]
            group['simulators'][sim]=dict(delivered=desc([r['delivered'] for r in data],True),admitted=desc([r['admitted'] for r in data],True),
                pooled_admitted=sum(r['admitted'] for r in data),pooled_delivered=sum(r['delivered'] for r in data),
                explicit_drops=sum(r['explicit_drops'] for r in data) if sim=='matlab' else None,
                pending=sum(r['pending'] for r in data) if sim=='matlab' else None,
                pooled_packet_weighted_latency_s=math.fsum(r['delay_sum_s'] for r in data)/sum(r['delay_samples'] for r in data),
                per_seed_packet_weighted_latency_s=desc([r['mean_packet_latency_s'] for r in data],True))
        group['paired_delivered_difference']=desc([r['delivered_difference'] for r in cases])
        group['paired_delivered_relative_difference_percent']=desc([r['delivered_relative_difference_percent'] for r in cases])
        m,n=group['simulators']['matlab'],group['simulators']['ns3']
        group['pooled_delivered_relative_difference_percent']=100*(m['pooled_delivered']-n['pooled_delivered'])/n['pooled_delivered']
        group['pooled_latency_relative_difference_percent']=100*(m['pooled_packet_weighted_latency_s']-n['pooled_packet_weighted_latency_s'])/n['pooled_packet_weighted_latency_s']
        out['groups'].append(group)
    out['feedback_totals']={}
    for sim in ['matlab','ns3']:
        feedback=[r[sim+'_feedback'] for r in out['cases']]
        total=dict(selection_count=sum(f['selection_count'] for f in feedback),
                   actual_feedback_members=sum(f['actual_feedback_members'] for f in feedback),forms=[])
        for index in [0,1]:
            forms=[f['forms'][index] for f in feedback]
            counts=dict(form=forms[0]['form'],
                **{key:sum(f[key] for f in forms) for key in ['selection_count','actual_feedback_members','rate_override_count','power_override_count']},
                last_override_time_s=max((f['last_override_time_s'] for f in forms if f['last_override_time_s'] is not None),default=None))
            for field in ['selected_distribution','actual_distribution']:
                dist=Counter()
                for form in forms:
                    for r in form[field]: dist[r['kind'],r['rate_key_kbps'],r['power_dbm']]+=r['count']
                counts[field]=[dict(kind=k[0],rate_key_kbps=k[1],power_dbm=k[2],count=v) for k,v in sorted(dist.items())]
            total['forms'].append(counts)
        if sim=='matlab':
            queues=Counter()
            for f in feedback: queues.update(f['queue_dispositions'])
            total['queue_dispositions']=dict(queues)
        out['feedback_totals'][sim]=total
    out['largest_observed_flow_gap']=max((dict(case_id=case['case_id'],**flow) for case in out['cases'] for flow in case['flow_pairs']),
                                         key=lambda f:abs(f['delivered_relative_difference_percent']))
    timing_path=OUTPUT/'contention_s129_timing.json'
    out['contention_s129_timing']=json.loads(timing_path.read_text())
    out['contention_s129_interpretation']={
        'source2_delivery_difference':157,
        'first20_traffic_seconds_matlab_delivered':152,
        'first20_traffic_seconds_ns3_delivered':35,
        'first20_traffic_seconds_difference':117,
        'fraction_of_full_window_gap_accumulated_before320s':117/157,
        'observed': 'The source2 gap is dominated by early contention/feedback service. Both simulators begin traffic at300s. The first ns3 source2 delivery precedes MATLAB, but first actual ordinary ACK and resumed admission occur1.3s later in ns3. Long3.963s/4.080s ns3 delivery gaps occur around309–318s.',
        'causal_limit': 'The traces localize a service/admission difference but do not identify whether scheduler details, random draws, collisions, or another mechanism caused it. Equal seeds are descriptive labels, not common random samples. The first ns3 ACK selection52 never transmits; later selection54 for the same HOP sequence11/bitmap1 transmits. The observed2.447896s first-delivery-to-ACK interval is not the residence time of one unchanged retained ACK frame.',
        'recommendation': 'Inspect early contention and ACK scheduling/capacity release for seed129 next, keeping the validated PHY/ECC and current ACK radio policy unchanged during diagnosis.'}
    out['ack_policy_conclusion']={
        'ordinary_data_matches':True,
        'immediate_radio_policy_change_supported':False,
        'startup_control_policy_matches':False,
        'reason': 'All ordinary DATA feedback selections and transmitted members use key128/+33dBm in both simulators, with no override. Exact-sequence startup control ACK distributions differ because MATLAB copies incoming rate while ns3 applies reverse-link control; this is a bounded policy discrepancy, not evidence that changing it resolves current delivery differences. All actual rate overrides occur before application traffic begins at300s.'}
    out['limits']=[
        'This review is descriptive for two direct-to-gateway topologies, five seeds per topology. Numerical seed labels do not align simulator RNG streams or packet IDs.',
        'ns-3 unmatched admitted sends have no certified terminal drop/pending split; null is intentional.',
        'No campus 6000-second multiseed runs, relay DACK, varied power profiles, asymmetric pathloss, unknown-peer fallback, or nonzero HOP failures are tested.',
        'MATLAB selections are observed after MAC admission; ns-3 selections are constructed before MAC admission. Counts are not proof of queue equivalence.',
        'The prior17.10% campus flow8 discrepancy is one measured case, not an established worst-case bound.'
    ]
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT/'findings.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'sha256':out['upload_sha256'],'groups':out['groups'],'feedback':[
        {'case_id':r['case_id'],'matlab':r['matlab_feedback'],'ns3':r['ns3_feedback']} for r in out['cases']]},indent=2))

if __name__=='__main__': main()
