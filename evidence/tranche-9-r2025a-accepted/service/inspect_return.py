#!/usr/bin/env python3
"""Independent read-only T9 outcome and ordered-service inspection."""
from pathlib import Path
from zipfile import ZipFile
import csv, io, gzip, json, hashlib, math, collections

BASE = Path('/workspace/scratch/1a5b1ad6ce1b')
ROOT = BASE/'t9r/src'
OUT = BASE/'t9r/service'
KEYS = ['c129', 'c128', 'c130', 'c131', 'c132', 'a129']
Z9 = BASE/'upload/tranche9_evidence.zip'
Z8 = ROOT/'evidence/tranche-8-r2025a-accepted/tranche8_evidence.zip'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rows_z(z, path):
    return list(csv.DictReader(io.StringIO(z.read(path).decode('utf-8-sig'))))

def rows_f(path):
    with (gzip.open if path.suffix == '.gz' else open)(path, 'rt', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def integer(x):
    return int(x)

def matlab_apps(rows):
    ans = {}
    for source in sorted({integer(r['SourceId']) for r in rows}):
        rr = [r for r in rows if integer(r['SourceId']) == source]
        dr = [r for r in rr if r['Outcome'] == 'delivered']
        ans[str(source)] = {
            'admitted': len(rr), 'delivered': len(dr),
            'pending': sum(r['Outcome'] == 'pending' for r in rr),
            'dropped': sum(r['Outcome'] == 'dropped' for r in rr),
            'first_delivery_s': min(float(r['ReceivedSeconds']) for r in dr),
            'delivered_300_320': sum(300 <= float(r['ReceivedSeconds']) < 320 for r in dr),
            'admitted_300_320': sum(300 <= float(r['GeneratedSeconds']) < 320 for r in rr),
            'delay_sum_s': math.fsum(float(r['LatencySeconds']) for r in dr),
        }
        ans[str(source)]['mean_latency_s'] = ans[str(source)]['delay_sum_s']/len(dr)
    return ans

def native_apps(rows):
    sends = {(r['src'], r['dst'], r['sequence']): r for r in rows if r['event'] == 'app_send'}
    delivered = [r for r in rows if r['event'] == 'nwk_delivery']
    assert len(sends) == sum(r['event'] == 'app_send' for r in rows)
    assert len(delivered) == len({(r['src'], r['dst'], r['sequence']) for r in delivered})
    ans = {}
    for source in sorted({integer(r['src']) for r in sends.values()}):
        rr = [r for r in sends.values() if integer(r['src']) == source]
        dr = [r for r in delivered if integer(r['src']) == source]
        delays = [float(r['time_s'])-float(sends[r['src'],r['dst'],r['sequence']]['time_s']) for r in dr]
        ans[str(source)] = {
            'admitted': len(rr), 'delivered': len(dr),
            'unmatched_sends': len(rr)-len(dr),
            'first_delivery_s': min(float(r['time_s']) for r in dr),
            'delivered_300_320': sum(300 <= float(r['time_s']) < 320 for r in dr),
            'admitted_300_320': sum(300 <= float(r['time_s']) < 320 for r in rr),
            'delay_sum_s': math.fsum(delays),
            'mean_latency_s': math.fsum(delays)/len(dr),
        }
    return ans

def radio_counts(rows, fields):
    c = collections.Counter(tuple(r[f] for f in fields) for r in rows)
    return [dict(zip(fields, k), count=v) for k,v in sorted(c.items())]

result = {
    'schema': 'csr-tranche9-independent-service-inspection-v1',
    'candidate_commit': '99fff0381fe9621ccd76fbdce41eac9aba5a9469',
    'candidate_source_root': str(ROOT),
    'returned_archive': str(Z9), 'returned_archive_sha256': sha(Z9),
    'accepted_t8_archive': str(Z8), 'accepted_t8_archive_sha256': sha(Z8),
    'ns3_commit': '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b',
    'ns3_suite_sha256': sha(ROOT/'evidence/tranche-9-ns3-reference/manifest.json'),
    'service_window_seconds': [300,320], 'end_exclusive': True,
    'scope': 'Independent analysis of uploaded owner evidence; no simulation or test rerun and no source mutation.',
    'cases': [],
}

with ZipFile(Z9) as z9, ZipFile(Z8) as z8:
    result['contract_summary'] = json.loads(z9.read('contracts/summary.json'))
    for key in KEYS:
        prefix = f'b/{key}/'
        app9, app8 = (rows_z(z,prefix+'analysis/applications.csv') for z in (z9,z8))
        service = rows_z(z9,prefix+'raw/service_trace.csv')
        protocol9, protocol8 = (rows_z(z,prefix+'raw/protocol_trace.csv') for z in (z9,z8))
        admission9 = rows_z(z9,prefix+'raw/application_admission_trace.csv')
        summary9, summary8 = (json.loads(z.read(prefix+'raw/summary.json')) for z in (z9,z8))
        native_dir = ROOT/'evidence/tranche-9-ns3-reference'/key
        native_trace = rows_f(native_dir/'ns3-trace.csv.gz')
        native_service = rows_f(native_dir/'ns3-service.csv.gz')
        mat9, mat8, ns3 = matlab_apps(app9), matlab_apps(app8), native_apps(native_trace)
        assert set(mat9) == set(mat8) == set(ns3)
        flows = [{'source': int(src), 'destination': 1, 't8': mat8[src], 't9': mat9[src], 'ns3': ns3[src],
                  'delivery_change_t9_minus_t8': mat9[src]['delivered']-mat8[src]['delivered'],
                  'delivery_gap_t9_minus_ns3': mat9[src]['delivered']-ns3[src]['delivered'],
                  'delivery_gap_percent_of_ns3': 100*(mat9[src]['delivered']/ns3[src]['delivered']-1),
                  'early_delivery_gap_t9_minus_ns3': mat9[src]['delivered_300_320']-ns3[src]['delivered_300_320']}
                 for src in mat9]
        b = {r['PacketId']: r for r in app8}
        changed_apps = []
        for r in app9:
            a=b[r['PacketId']]
            if a != r:
                assert a['SourceId']==r['SourceId'] and a['DestinationId']==r['DestinationId']
                assert a['GeneratedSeconds']==r['GeneratedSeconds'] and a['Outcome']==r['Outcome']
                changed_apps.append({'packet_id':r['PacketId'],'source':integer(r['SourceId']),
                                     'received_before_s':float(a['ReceivedSeconds']),
                                     'received_after_s':float(r['ReceivedSeconds']),
                                     'latency_change_s':float(r['LatencySeconds'])-float(a['LatencySeconds'])})
        cancelled=[]
        for i, r in enumerate(service):
            if r['Event']!='mac_cancel_after' or not float(r['RemovedCount'])>0: continue
            before=service[i-1]
            assert before['Event']=='mac_cancel_before' and before['NodeId']==r['NodeId']
            assert integer(r['ObservationId'])==integer(before['ObservationId'])+1
            t=float(r['TimeSeconds']); n=r['NodeId']
            next_admit=next(x for x in service[i+1:] if x['NodeId']==n and x['Event']=='hop_admit')
            next_tx=next(x for x in protocol9 if x['NodeId']==n and x['Event']=='hop_sent' and x['FrameKind']=='DATA' and float(x['TimeSeconds'])>t)
            old_tx=next(x for x in protocol8 if x['NodeId']==n and x['Event']=='hop_sent' and x['FrameKind']=='DATA' and x['PacketId']==next_tx['PacketId'])
            next_app=next(x for x in admission9 if x['SourceId']==n and x['Accepted']=='1' and float(x['TimeSeconds'])>t)
            cancelled.append({'node':integer(n),'hop_sequence':integer(r['Sequence']), 'time_s':t,
                              'state':r['State'],'before':json.loads(before['DetailsJSON']),'after':json.loads(r['DetailsJSON']),
                              'before_observation_id':integer(before['ObservationId']),
                              'after_observation_id':integer(r['ObservationId']),
                              'next_hop_admission_time_s':float(next_admit['TimeSeconds']),
                              'next_hop_admission_observation_id':integer(next_admit['ObservationId']),
                              'wake_delta_ns_from_csv':(float(next_admit['TimeSeconds'])-t)*1e9,
                              'next_app_admitted_s':float(next_app['TimeSeconds']),
                              'next_data_packet_id':next_tx['PacketId'],
                              'next_data_tx_t8_s':float(old_tx['TimeSeconds']),
                              'next_data_tx_t9_s':float(next_tx['TimeSeconds']),
                              'next_data_tx_change_s':float(next_tx['TimeSeconds'])-float(old_tx['TimeSeconds'])})
        feedback=rows_z(z9,prefix+'raw/actual_feedback.csv')
        old_feedback=rows_z(z8,prefix+'raw/actual_feedback.csv')
        decisions=rows_z(z9,prefix+'raw/link_decisions.csv')
        native_feedback=rows_f(native_dir/'ns3-link-decisions.csv.gz')
        first_ack={}
        for src in mat9:
            m=next(r for r in feedback if r['NodeId']=='1' and r['PeerId']==src and r['HasAckWindow']=='1')
            d=next(r for r in decisions if r['DecisionId']==m['DecisionId'])
            n=next(r for r in native_feedback if r['node_id']=='1' and r['peer_id']==src and r['has_ack_window']=='1' and r['stage']=='ota_segment')
            nd=next(r for r in native_feedback if r['decision_id']==n['decision_id'] and r['stage']=='feedback_selection')
            first_md=next(r for r in decisions if r['NodeId']=='1' and r['PeerId']==src and r['HasAckWindow']=='1')
            first_nd=next(r for r in native_feedback if r['node_id']=='1' and r['peer_id']==src and r['has_ack_window']=='1' and r['stage']=='feedback_selection')
            resume_m=[r for r in admission9 if r['SourceId']==src and r['Accepted']=='1'][16]
            resume_n=[r for r in native_service if r['event']=='app_admission' and r['node']==src and r['success']=='1'][16]
            first_ack[src]={'matlab_first_decision_time_s':float(first_md['TimeSeconds']),
                            'matlab_first_decision_id':first_md['DecisionId'],
                            'ns3_first_decision_time_s':float(first_nd['time_s']),
                            'ns3_first_decision_id':first_nd['decision_id'],
                            'matlab_transmitted_decision_queue_s':float(d['TimeSeconds']), 'matlab_decision_id':d['DecisionId'],
                            'matlab_ota_time_s':float(m['TimeSeconds']), 'matlab_selected_rate_kbps':float(m['SelectedRateKeyKbps']),
                            'matlab_power_dbm':float(m['TxPowerDbm']),
                            'ns3_transmitted_decision_queue_s':float(nd['time_s']),'ns3_decision_id':n['decision_id'],
                            'ns3_ota_time_s':float(n['time_s']),'ns3_selected_rate_kbps':float(n['selected_rate_key_kbps']),
                            'ns3_power_dbm':float(n['actual_power_dbm']),
                            'matlab_admission_resume_s':float(resume_m['TimeSeconds']),
                            'ns3_admission_resume_s':float(resume_n['time_s'])}
        raw_names=[p for p in z9.namelist() if p.startswith(prefix+'raw/') and p.endswith('.csv') and p in z8.namelist()]
        raw_equality=[{'path':p.removeprefix(prefix),'byte_equal':z9.read(p)==z8.read(p)} for p in raw_names]
        case={'storage_key':key, 'flows':flows,
              'counts':{'t8':{k:summary8['Statistics'][k] for k in ['Generated','Received','Dropped','Pending']},
                        't9':{k:summary9['Statistics'][k] for k in ['Generated','Received','Dropped','Pending']},
                        'ns3':{'admitted':sum(f['admitted'] for f in ns3.values()),
                               'delivered':sum(f['delivered'] for f in ns3.values()),
                               'unmatched_sends':sum(f['unmatched_sends'] for f in ns3.values())}},
              'statistics_exact_equal':summary8['Statistics']==summary9['Statistics'],
              'changed_statistics':{k:{'t8':summary8['Statistics'][k],'t9':v} for k,v in summary9['Statistics'].items() if summary8['Statistics'][k]!=v},
              'changed_application_records':changed_apps, 'service':summary9['ServiceDiagnostics'],
              'cancellation_removals':cancelled, 'first_ordinary_ack':first_ack,
              'ordinary_matlab_actual_radio_counts':radio_counts([r for r in feedback if r['HasAckWindow']=='1'], ['FrameKind','RateKeyKbps','RateBps','TxPowerDbm']),
              'ordinary_native_actual_radio_counts':radio_counts([r for r in native_feedback if r['has_ack_window']=='1' and r['stage']=='ota_segment'], ['frame_type','actual_rate_key_kbps','actual_rate_bps','actual_power_dbm']),
              'actual_feedback_changed_fields':dict(collections.Counter(k for old,new in zip(old_feedback,feedback) for k in new if old[k]!=new[k])),
              'actual_feedback_equal_excluding_decision_id':([{k:v for k,v in r.items() if k!='DecisionId'} for r in old_feedback]==[{k:v for k,v in r.items() if k!='DecisionId'} for r in feedback]),
              'existing_raw_csvs':raw_equality,
              'protocol_row_count':{'t8':len(protocol8),'t9':len(protocol9)},
              'protocol_equal_ignoring_mac_prepare':([r for r in protocol8 if r['Event']!='mac_prepare']==[r for r in protocol9 if r['Event']!='mac_prepare']),
              'native_artifact_hashes':{p.name:sha(p) for p in [native_dir/'ns3-trace.csv.gz',native_dir/'ns3-service.csv.gz',native_dir/'ns3-link-decisions.csv.gz']}}
        result['cases'].append(case)

result['interpretation'] = [
    'All six application admission/delivery/drop/pending totals and per-source delivery totals are unchanged; c129 source2 delivery gap remains157.',
    'The correction demonstrably changes c131 scheduling: active counter0 can transmit the next queued DATA at the next slot,78ms earlier than T8. Eight application receive times change with net+0.052s latency sum; aggregate mean+58.100559microseconds. This is not a measured throughput improvement.',
    'At the four other early contention cancellations, a positive counter survives the next slot. T8 reactivated preparation without redrawing that still-valid reservation; T9 avoids the redundant activation. Protocol rows match exactly after excluding mac_prepare. a129 protocol rows are unchanged.',
    'Both simulators release capacity before the next queued HOP admission. T9 callbacks are separated by approximately27.7778ns (configuredTIC); native nanosecond resolution reports28ns. No sampled admission-release defect warrants an additional policy change.',
    'c129 differing first DATA reception order and reservation draws precede its ACK divergence; the present correction does not align simulator random streams or certify statistical parity.',
]
result['limits'] = [
    'MATLAB owner run is evidence; this independent script executes no MATLAB/ns3 simulations.',
    'Ordinary ACK rate/power equivalence is limited to these fixed direct-path cases; relay/DACK and varied link state remain unexercised.',
    'Native unmatched sends retain their source semantics and are not reclassified as MATLAB pending or dropped.',
    'No arbitrary numerical pass tolerance or cross-simulator local packet-ID identity is introduced.',
]
(OUT/'inspection.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
with (OUT/'flows.csv').open('w',newline='') as f:
    fields=['case','source','destination','t8_admitted','t9_admitted','ns3_admitted','t8_delivered','t9_delivered','ns3_delivered','t9_ns3_gap','gap_percent','t9_early_delivered','ns3_early_delivered','t9_first_delivery_s','ns3_first_delivery_s']
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for case in result['cases']:
        for flow in case['flows']:
            w.writerow({'case':case['storage_key'],'source':flow['source'],'destination':flow['destination'],
                        't8_admitted':flow['t8']['admitted'],'t9_admitted':flow['t9']['admitted'],'ns3_admitted':flow['ns3']['admitted'],
                        't8_delivered':flow['t8']['delivered'],'t9_delivered':flow['t9']['delivered'],'ns3_delivered':flow['ns3']['delivered'],
                        't9_ns3_gap':flow['delivery_gap_t9_minus_ns3'],'gap_percent':flow['delivery_gap_percent_of_ns3'],
                        't9_early_delivered':flow['t9']['delivered_300_320'],'ns3_early_delivered':flow['ns3']['delivered_300_320'],
                        't9_first_delivery_s':flow['t9']['first_delivery_s'],'ns3_first_delivery_s':flow['ns3']['first_delivery_s']})
print(json.dumps({'cases':len(result['cases']),'flows':sum(len(c['flows']) for c in result['cases']),
                  'service_records':sum(c['service']['CapturedServiceRecords'] for c in result['cases']),
                  'cancellation_pairs':sum(c['service']['CancellationAfterCount'] for c in result['cases']),
                  'removals':sum(len(c['cancellation_removals']) for c in result['cases']),
                  'changed_app_records':sum(len(c['changed_application_records']) for c in result['cases']),
                  'output':str(OUT/'inspection.json')},indent=2))
