#!/usr/bin/env python3
"""T21 offline source-4 decomposition; reads accepted T20 evidence, never runs a model."""
import argparse
import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from zipfile import ZipFile


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def describe(values):
    values = sorted(values)
    if not values:
        return {'n': 0, 'mean_s': None, 'median_s': None, 'maximum_s': None}
    return {'n': len(values), 'mean_s': mean(values), 'median_s': median(values), 'maximum_s': values[-1]}


def hop_summary(episodes, apps):
    reasons = Counter(e['release']['event'] if e['release'] else 'pending_at_stop' for e in episodes)
    waits = [w for e in episodes for w in e['retry_request_waits']]
    failed = [e for e in episodes if e['release'] and e['release']['event'] == 'hop_failed']
    terminal_failed = [e for e in failed if apps[e['packet_id']]['Outcome'] == 'dropped'
        and math.isclose(float(apps[e['packet_id']]['LastEventSeconds']),e['release']['time_s'],rel_tol=0,abs_tol=1e-8)]
    return {
        'episodes': len(episodes), 'unique_applications': len(set(e['packet_id'] for e in episodes)),
        'completion_counts': dict(sorted(reasons.items())),
        'hop_sent_callbacks': sum(len(e['transmissions']) for e in episodes),
        'retry_requests': sum(len(e['retry_requests']) for e in episodes),
        'retry_requests_per_episode': sum(len(e['retry_requests']) for e in episodes)/len(episodes) if episodes else None,
        'initial_admit_to_first_sent': describe([e['transmissions'][0]['time_s']-e['admit']['time_s'] for e in episodes if e['transmissions']]),
        'retry_next_sent_wait': describe([w['seconds'] for w in waits if w['completion']=='next_observed_hop_sent']),
        'retry_wait_completion_counts': dict(Counter(w['completion'] for w in waits)),
        'capacity_retention_completed': describe([e['capacity_retention_s'] for e in episodes if e['release']]),
        'hop_service_to_ack_dack_or_failure': describe([(e['dack'] or e['release'])['time_s']-e['admit']['time_s'] for e in episodes if e['dack'] or e['release']]),
        'capacity_retention_censored': describe([e['capacity_retention_s'] for e in episodes if not e['release']]),
        'dack_hold_completed': describe([e['dack_capacity_hold_s'] for e in episodes if e.get('dack') and e['release']]),
        'dack_hold_censored': describe([e['dack_capacity_hold_s'] for e in episodes if e.get('dack') and not e['release']]),
        'failed_episodes_final_application_outcomes': dict(Counter(apps[e['packet_id']]['Outcome'] for e in failed)),
        'failed_episodes_matching_final_application_drop_time': len(terminal_failed),
    }


def custody_summary(episodes):
    return {
        'episodes': len(episodes),
        'submitted': sum(e['submit'] is not None for e in episodes),
        'released': sum(e['release'] is not None for e in episodes),
        'pending_at_stop': sum(e['release'] is None for e in episodes),
        'enqueue_to_first_submit': describe([e['submit']['time_s']-e['enqueue']['time_s'] for e in episodes if e['submit']]),
        'enqueue_to_release': describe([e['release']['time_s']-e['enqueue']['time_s'] for e in episodes if e['release']]),
        'censored_enqueue_to_stop': describe([6000-e['enqueue']['time_s'] for e in episodes if not e['release']]),
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--workspace', type=Path, default=Path.cwd())
    p.add_argument('--output', type=Path, default=Path(__file__).resolve().parent/'source4.json')
    p.add_argument('--native-root', type=Path, help='Optional T21 native diagnostic outputs; requires s129.json and s130.json')
    args=p.parse_args(); root=args.workspace
    review_path=root/'t20-return-review/analysis/review.json'
    review=json.loads(review_path.read_text())
    result={'schema':'csr-tranche21-source4-existing-trace-diagnostic-v1','working_band_percent':10,
        'model_modified':False,'simulations_executed':False,'input_files':[{'path':str(review_path.relative_to(root)),'sha256':digest(review_path)}], 'seeds':[],
        'limitations':['Finite-stop unique application deliveries; source identifiers never mean transmitter identifiers.',
        'Native unmatched sends combine pending and lost applications unless separately attributed from native traces.',
        'No cross-engine packet identity joins; identical seed numbers do not imply common RNG event histories.',
        'MATLAB retry waits pair a request to the next observed owned hop_sent callback; not unique queued-retry lineage.',
        'Completed waits are conditional on the corresponding completion; pending observations are right-censored at 6000 seconds.',
        'Application drop callbacks can later be superseded by relay acceptance; endpoint outcomes take precedence.',
        'Differences are descriptive decompositions and do not establish a causal model bug.']}
    for seed in (128,129,130):
        if seed==128:
            source=root/'csr20/evidence/t19/owner.zip'
            with ZipFile(source) as z:
                rows=list(csv.DictReader(io.StringIO(z.read('a128/analysis/applications.csv').decode('utf-8-sig'))))
            obs=review['reused_seed128']['observations']
        else:
            source=root/f't20-return-review/owner/s{seed}/analysis/applications.csv'
            rows=list(csv.DictReader(source.open(newline='')))
            obs=review['cases'][f's{seed}']['observations']
        result['input_files'].append({'path':str(source.relative_to(root)),'sha256':digest(source)})
        apps={int(r['PacketId']):r for r in rows}
        m=next(f for f in obs['flows'] if f['source']==4)
        n=next(f for f in review['native_application_reference'][str(seed)]['flows'] if f['source']==4)
        source4_apps=[a for a in apps.values() if int(a['SourceId'])==4]
        assert len(source4_apps)==m['admitted']
        assert Counter(a['Outcome'] for a in source4_apps)=={
            'delivered':m['delivered'],'dropped':m['dropped'],'pending':m['pending']}
        native_unmatched=n['admitted']-n['unique_delivered']; matlab_unmatched=m['dropped']+m['pending']
        assert m['admitted']==m['delivered']+matlab_unmatched
        delivery_delta=m['delivered']-n['unique_delivered']; admission_delta=m['admitted']-n['admitted']
        undelivered_delta=matlab_unmatched-native_unmatched
        assert delivery_delta==admission_delta-undelivered_delta
        s={'seed':seed,'matlab_source4':m,'native_source4':n,
           'decomposition':{'delivery_delta':delivery_delta,'admission_delta':admission_delta,
              'matlab_undelivered':matlab_unmatched,'native_undelivered':native_unmatched,
              'undelivered_delta':undelivered_delta,'identity':'delivery_delta = admission_delta - undelivered_delta',
              'delivered_residual_percent':100*delivery_delta/n['unique_delivered'],
              'admitted_residual_percent':100*admission_delta/n['admitted'],
              'matlab_delivery_fraction':m['delivered']/m['admitted'],
              'native_delivery_fraction':n['unique_delivered']/n['admitted'],
              'within_ten_percent_delivery_band':abs(delivery_delta)<=.1*n['unique_delivered']},
           'hops':[],'custody':[],'ownership':[],'flow_timeline':[r for r in obs['flow_timeline'] if r['source']==4]}
        for node,peer in ((4,5),(5,1)):
            for sourceid in sorted(set(e['source'] for e in obs['hop_episodes'] if e['node']==node and e['peer']==peer)):
                es=[e for e in obs['hop_episodes'] if e['node']==node and e['peer']==peer and e['source']==sourceid]
                s['hops'].append({'node':node,'peer':peer,'source':sourceid,'local_at_node':node==sourceid,**hop_summary(es,apps)})
        for node in (4,5):
            for sourceid in sorted(set(e['source'] for e in obs['nwk_custody_episodes'] if e['node']==node)):
                es=[e for e in obs['nwk_custody_episodes'] if e['node']==node and e['source']==sourceid]
                s['custody'].append({'node':node,'source':sourceid,'local_at_node':node==sourceid,**custody_summary(es)})
            ownership=next(e for e in obs['ownership'] if e['node']==node)
            for cohort in ownership['source_cohorts']:
                def summarize_bins(bins):
                    return {'mean_6000s':sum(b['mean_count']*(b['end_s']-b['start_s']) for b in bins)/6000,
                        'mean_active_300_to_6000s':sum(b['mean_count']*(b['end_s']-b['start_s']) for b in bins if b['start_s']>=300)/5700,
                        'peak_count':max(b['peak_count'] for b in bins),'end_count':bins[-1]['end_count']}
                s['ownership'].append({'node':node,'source':cohort['source'],'local_at_node':node==cohort['source'],
                    'hop_data_capacity':summarize_bins(cohort['hop_data_capacity_300s']),
                    'nwk_custody':summarize_bins(cohort['nwk_custody_300s'])})
        source4failures=[e for e in obs['hop_episodes'] if e['source']==4 and e['release'] and e['release']['event']=='hop_failed']
        s['source4_hop_failures_by_link']=dict(Counter(f"{e['node']}->{e['peer']}" for e in source4failures))
        final_drops={p for p,a in apps.items() if int(a['SourceId'])==4 and a['Outcome']=='dropped'}
        s['source4_final_drop_reasons']=dict(Counter(apps[p]['DropReason'] for p in final_drops))
        assert s['source4_final_drop_reasons']=={'retry_exhausted':m['dropped']}
        matched={e['packet_id'] for e in source4failures if e['packet_id'] in final_drops and math.isclose(float(apps[e['packet_id']]['LastEventSeconds']),e['release']['time_s'],rel_tol=0,abs_tol=1e-8)}
        assert matched==final_drops, 'Terminal source4 drop unaccounted for by same-application final HOP failure'
        s['all_source4_final_drops_matched_to_hop_failure']=True
        s['node4_hop_failures_all_sources']=dict(Counter(e['source'] for e in obs['hop_episodes'] if e['node']==4 and e['release'] and e['release']['event']=='hop_failed'))
        if args.native_root is not None and seed in (129,130):
            native_path=args.native_root/f's{seed}.json'
            native=json.loads(native_path.read_text())
            assert native['seed']==seed and native['nsdp_snapshot_mismatch_count']==0
            nf=next(f for f in native['flows'] if f['source']==4)
            assert (nf['admitted'],nf['unique_delivered'])==(n['admitted'],n['unique_delivered'])
            result['input_files'].append({'path':str(native_path),'sha256':digest(native_path)})
            s['native_node4_source4']={
                'original_trace_hashes':native['input'],
                'events':[e for e in native['node_source_event_reasons'] if e['node']==4 and e['source']==4],
                'residence':next(e for e in native['residence'] if e['node']==4 and e['source']==4),
                'nsdp':next(e for e in native['nsdp_state'] if e['node']==4 and e['source']==4),
                'comparison_scope':'native nwk_queue_wait_s vs MATLAB enqueue_to_first_submit; native hop_admission_to_nsdp_release_completion_s vs MATLAB hop_service_to_ack_dack_or_failure, excluding DACK capacity hold',
                'warning':'Native no_ack completions are not application terminal drops; receiver may accept despite missing sender feedback.'}
            outcome_path=args.native_root/f's{seed}-outcome-joins.json'
            outcomes=json.loads(outcome_path.read_text())
            assert outcomes['input_binding']==native['input']
            joined_counts=[o for o in outcomes['source_node_outcome_counts'] if o['node']==4 and o['source']==4]
            csv_path=args.native_root/f's{seed}-completion-outcomes.csv'
            with csv_path.open(newline='') as stream:
                joined_rows=[r for r in csv.DictReader(stream) if r['node']=='4' and r['source']=='4']
            assert sum(o['count'] for o in joined_counts)==len(joined_rows)
            computed=Counter((r['reason'],r['unique_delivered_by_stop']=='True') for r in joined_rows)
            assert computed==Counter({(o['hop_completion_reason'],o['unique_delivered_by_stop']):o['count'] for o in joined_counts})
            delivered_after_noack=[r for r in joined_rows if r['reason']=='no_ack' and r['unique_delivered_by_stop']=='True']
            assert all(r['delivery_after_hop_completion']=='True' and float(r['first_delivery_s'])>float(r['completion_s']) for r in delivered_after_noack)
            assert len(delivered_after_noack)=={129:11,130:2}[seed]
            for path in (outcome_path,csv_path):
                result['input_files'].append({'path':str(path),'sha256':digest(path)})
            s['native_node4_source4']['completion_endpoint_join']={
                'counts':joined_counts,
                'no_ack_followed_by_unique_delivery':len(delivered_after_noack),
                'all_first_deliveries_occurred_after_no_ack':True,
                'delivered_after_no_ack_rows':delivered_after_noack,
                'scope':'Same native run and original source/destination/application sequence; no cross-engine identity join. Undelivered by stop does not classify terminal drops.'}
        result['seeds'].append(s)
    pooled_matlab=sum(s['matlab_source4']['delivered'] for s in result['seeds'])
    pooled_native=sum(s['native_source4']['unique_delivered'] for s in result['seeds'])
    result['pooled_deliveries']={'matlab':pooled_matlab,'native':pooled_native,'residual_percent':100*(pooled_matlab-pooled_native)/pooled_native,'within_ten_percent':abs(pooled_matlab-pooled_native)<=.1*pooled_native,'scope':'ratio of three-seed sums; does not replace individual-seed gate'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'pooled':result['pooled_deliveries'],'seeds':[{'seed':s['seed'],**s['decomposition']} for s in result['seeds']]},indent=2))


if __name__=='__main__':
    main()
