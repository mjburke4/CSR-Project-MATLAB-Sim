#!/usr/bin/env python3
"""T21 read-only analysis of accepted MATLAB T19/T20 evidence.

Run from the project workspace:
  python3 t21-work/matlab/extract_matlab.py

No simulator execution. Episode reconstruction comes from the accepted T20
review; every used episode callback is checked against its receipt-bound raw
protocol row, and all read owner artifacts are independently SHA256 checked.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import zipfile

HORIZON = 6000.0
TRAFFIC_START = 300.0
BIN = 300.0
NODES = (2, 7, 8)
SOURCES = (2, 7, 8)
PARENT_SHA = '525758669b8f84fa5dada46e293b8482980ef389efc5408ff056aac0e804ee30'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


class Evidence:
    def __init__(self, root, seed):
        self.seed = seed
        self.case = 'a128' if seed == 128 else f's{seed}'
        self.base = root / 't20-return-review/owner' / self.case
        self.zip = zipfile.ZipFile(root / 'csr20/evidence/t19/owner.zip') if seed == 128 else None
        self.verified = {}
        receipt = self.read('receipt.json')
        expected = self.read('receipt.sha256').decode().strip()
        assert hashlib.sha256(receipt).hexdigest() == expected
        self.receipt_sha = expected
        self.receipt = json.loads(receipt)
        self.inventory = {r['path']:r for r in self.receipt['artifacts']}
        assert self.receipt['status'] == 'completed'

    def read(self, rel):
        return self.zip.read(self.case + '/' + rel) if self.zip else (self.base / rel).read_bytes()

    def bound(self, rel):
        value = self.read(rel)
        found = hashlib.sha256(value).hexdigest()
        assert found == self.inventory[rel]['sha256'], (self.seed, rel)
        assert len(value) == self.inventory[rel]['bytes'], (self.seed, rel)
        self.verified[rel] = {'sha256':found, 'bytes':len(value)}
        return value

    def js(self, rel):
        return json.loads(self.bound(rel))

    def rows(self, rel):
        return csv.DictReader(io.StringIO(self.bound(rel).decode('utf-8-sig')))


def dist(values):
    a = sorted(values)
    def quantile(p):
        i = (len(a)-1)*p
        low, high = math.floor(i), math.ceil(i)
        return a[low] + (a[high]-a[low])*(i-low)
    return {'count':len(a), 'minimum_s':min(a) if a else None,
            'mean_s':statistics.fmean(a) if a else None,
            'median_s':quantile(.5) if a else None,
            'p95_s':quantile(.95) if a else None,
            'maximum_s':max(a) if a else None}


def interval(entry, start, end):
    return (entry[start]['time_s'], entry[end]['time_s'] if entry.get(end) else HORIZON)


def area(intervals, lo, hi):
    return sum(max(0.0, min(b,hi)-max(a,lo)) for a,b in intervals)


def at_end(intervals):
    # Right-censor flags, not float endpoints, determine ownership at H.
    return sum(censored for _,_,censored in intervals)


def saturated_seconds(intervals, threshold, lo=TRAFFIC_START, hi=HORIZON):
    changes = collections.Counter()
    for a,b in intervals:
        begin, end = max(a,lo), min(b,hi)
        if begin >= end:
            continue
        changes[begin] += 1
        changes[end] -= 1
    count, previous, occupied = 0, lo, 0.0
    for t, delta in sorted(changes.items()):
        if t < lo or t > hi:
            continue
        if count >= threshold:
            occupied += t-previous
        count += delta
        previous = t
    return occupied


def bucket(t):
    return min(int(t // BIN), int(HORIZON // BIN)-1)


def csv_out(path, rows):
    assert rows
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def analyze_case(root, seed, obs):
    evidence = Evidence(root, seed)
    summary = evidence.js('summary.json')
    raw_summary = evidence.js('raw/summary.json')
    assert raw_summary['Config']['Seed'] == seed
    assert raw_summary['Statistics']['OmittedTraceRecords'] == 0
    apps = {int(x['PacketId']):x for x in evidence.rows('analysis/applications.csv')}
    nwk = {int(x['NodeId']):x for x in evidence.rows('raw/nwk_nodes.csv')}
    hop = {int(x['NodeId']):x for x in evidence.rows('raw/hop_nodes.csv')}
    routes = list(evidence.rows('raw/routes.csv'))
    admission_stats = list(evidence.rows('raw/application_admission_statistics.csv'))
    h = [e for e in obs['hop_episodes'] if e['node'] in NODES]
    c = [e for e in obs['nwk_custody_episodes'] if e['node'] in NODES]
    expected_rows = {}
    for entry in h + c:
        assert int(apps[entry['packet_id']]['SourceId']) == entry['source']
        callbacks = entry['events'] if 'admit' in entry else [entry['enqueue']] + entry.get('submissions',[]) + ([entry['release']] if entry['release'] else [])
        for callback in callbacks:
            expected_rows[callback['row']] = (entry, callback)
    bins = {(node,source,i):collections.Counter() for node in NODES for source in SOURCES for i in range(20)}
    generated = collections.Counter()
    neighbor_events = []
    route_events = []
    protocol_count = 0
    matched = 0
    for ordinal, row in enumerate(evidence.rows('raw/protocol_trace.csv'), 1):
        protocol_count += 1
        node, event, t = int(row['NodeId']), row['Event'], float(row['TimeSeconds'])
        if ordinal in expected_rows:
            entry, callback = expected_rows[ordinal]
            assert node == entry['node'] and int(row['PacketId']) == entry['packet_id']
            assert event == callback['event'] and t == callback['time_s']
            if 'admit' in entry:
                assert int(row['PeerId']) == entry['peer'] and int(row['Sequence']) == entry['sequence']
            matched += 1
        if event == 'app_generate':
            generated[node,bucket(t)] += 1
        if node not in NODES:
            continue
        if event in ('neighbor_active','neighbor_inactive','discovery_started','discovery_finished'):
            neighbor_events.append({'node':node,'event':event,'time_s':t,'peer':int(row['PeerId']),'reason':row['Reason']})
        if event.startswith('route_') or event.startswith('routing_'):
            route_events.append({'node':node,'event':event,'time_s':t,'peer':int(row['PeerId'])})
        packet = int(row['PacketId'])
        if packet in apps and row['FrameKind'] in ('APP','DATA'):
            source = int(apps[packet]['SourceId'])
            if source in SOURCES:
                bins[node,source,bucket(t)][event] += 1
    assert matched == len(expected_rows)
    for flow in obs['flow_timeline']:
        assert generated[flow['source'],int(flow['start_s']//BIN)] == flow['admitted']
    prefix_count = 0
    prefix_last = None
    prefix_summary = collections.defaultdict(collections.Counter)
    for row in evidence.rows('raw/application_admission_trace.csv'):
        prefix_count += 1
        prefix_last = float(row['TimeSeconds'])
        prefix_summary[int(row['SourceId'])][row['Reason']] += 1
    assert prefix_count == 100000
    assert sum(int(x['Attempts']) for x in admission_stats) == 1710000
    cohorts, timeline = [], []
    for node in NODES:
        observed = next(x for x in obs['ownership'] if x['node'] == node)
        assert sum(e['release'] is None for e in h if e['node']==node) == int(hop[node]['PendingData'])
        assert sum(e['release'] is None for e in c if e['node']==node) == int(nwk[node]['PendingCustody'])
        for source in SOURCES:
            hs = [e for e in h if e['node']==node and e['source']==source]
            cs = [e for e in c if e['node']==node and e['source']==source]
            if not hs and not cs:
                continue
            assert not any(e['release'] is not None and e['submit'] is None for e in cs), 'Released custody without a first submit needs a terminal-before-submit category.'
            hi = [interval(e,'admit','release') for e in hs]
            ci = [interval(e,'enqueue','release') for e in cs]
            wi = [interval(e,'enqueue','submit') for e in cs]
            di = [interval(e,'dack','release') for e in hs if e['dack']]
            cohort = next(x for x in observed['source_cohorts'] if x['source']==source)
            for intervals, key in [(hi,'hop_data_capacity_300s'),(ci,'nwk_custody_300s')]:
                assert math.isclose(area(intervals,0,HORIZON), sum(r['mean_count']*BIN for r in cohort[key]), rel_tol=1e-10, abs_tol=1e-7)
            row = {'seed':seed,'node':node,'source':source,'local_at_node':source==node,
                'nwk_enqueued':len(cs),'nwk_submitted':sum(e['submit'] is not None for e in cs),
                'nwk_released':sum(e['release'] is not None for e in cs),
                'nwk_pending_at_stop':sum(e['release'] is None for e in cs),
                'nwk_waiting_first_submit_at_stop':sum(e['submit'] is None for e in cs),
                'hop_admitted':len(hs),'hop_sent_callbacks':sum(len(e['transmissions']) for e in hs),
                'hop_retry_requests':sum(len(e['retry_requests']) for e in hs),
                'hop_acks':sum(e['release'] is not None and e['release']['event']=='hop_ack' for e in hs),
                'hop_dacks':sum(e['dack'] is not None for e in hs),
                'hop_failed':sum(e['release'] is not None and e['release']['event']=='hop_failed' for e in hs),
                'hop_dack_expired':sum(e['release'] is not None and e['release']['event']=='hop_dack_expired' for e in hs),
                'hop_pending_at_stop':sum(e['release'] is None for e in hs),
                'dack_pending_at_stop':sum(e['dack'] is not None and e['release'] is None for e in hs),
                'nwk_custody_app_seconds':area(ci,TRAFFIC_START,HORIZON),
                'nwk_pre_first_submit_app_seconds':area(wi,TRAFFIC_START,HORIZON),
                'nwk_completed_custody_app_seconds':area([interval(e,'enqueue','release') for e in cs if e['release']],TRAFFIC_START,HORIZON),
                'nwk_censored_custody_elapsed_app_seconds':area([interval(e,'enqueue','release') for e in cs if e['release'] is None],TRAFFIC_START,HORIZON),
                'nwk_completed_first_submit_wait_app_seconds':area([interval(e,'enqueue','submit') for e in cs if e['submit']],TRAFFIC_START,HORIZON),
                'nwk_censored_first_submit_elapsed_app_seconds':area([interval(e,'enqueue','submit') for e in cs if e['submit'] is None],TRAFFIC_START,HORIZON),
                'hop_capacity_app_seconds':area(hi,TRAFFIC_START,HORIZON),
                'hop_completed_capacity_app_seconds':area([interval(e,'admit','release') for e in hs if e['release']],TRAFFIC_START,HORIZON),
                'hop_censored_capacity_elapsed_app_seconds':area([interval(e,'admit','release') for e in hs if e['release'] is None],TRAFFIC_START,HORIZON),
                'dack_hold_app_seconds':area(di,TRAFFIC_START,HORIZON),
                'mean_nwk_custody_traffic_window':area(ci,TRAFFIC_START,HORIZON)/(HORIZON-TRAFFIC_START),
                'mean_nwk_pre_first_submit_traffic_window':area(wi,TRAFFIC_START,HORIZON)/(HORIZON-TRAFFIC_START),
                'mean_hop_capacity_traffic_window':area(hi,TRAFFIC_START,HORIZON)/(HORIZON-TRAFFIC_START),
                'mean_dack_capacity_traffic_window':area(di,TRAFFIC_START,HORIZON)/(HORIZON-TRAFFIC_START),
                'observed_nwk_custody_seconds_at_or_above_16':saturated_seconds(ci,16),
                'peers':dict(collections.Counter(e['peer'] for e in hs)),
                'completed_nwk_first_submit_wait':dist([e['submit']['time_s']-e['enqueue']['time_s'] for e in cs if e['submit']]),
                'completed_hop_first_sent_wait':dist([e['transmissions'][0]['time_s']-e['admit']['time_s'] for e in hs if e['transmissions']]),
                'first_sent_right_censored_count':sum(not e['transmissions'] and e['release'] is None for e in hs),
                'capacity_released_without_observed_first_sent_count':sum(not e['transmissions'] and e['release'] is not None for e in hs),
                'completed_nwk_custody_retention':dist([e['release']['time_s']-e['enqueue']['time_s'] for e in cs if e['release']]),
                'retry_request_wait':dist([w['seconds'] for e in hs for w in e['retry_request_waits'] if w['completion']=='next_observed_hop_sent']),
                'retry_request_completions':dict(collections.Counter(w['completion'] for e in hs for w in e['retry_request_waits']))}
            cohorts.append(row)
            for i in range(20):
                lo, upper = i*BIN, (i+1)*BIN
                counts = bins[node,source,i]
                flow = next(x for x in obs['flow_timeline'] if x['source']==source and x['start_s']==lo)
                timeline.append({'seed':seed,'node':node,'source':source,'start_s':lo,'end_s':upper,
                    'source_attempts':flow['attempts'],'source_admitted':flow['admitted'],
                    'source_blocked':flow['blocked'],'source_delivered_events':flow['delivery_events'],
                    'nwk_enqueued':counts['network_enqueue'],'nwk_submitted':counts['network_submit'],
                    'nwk_released':counts['network_custody_release'],'hop_admitted':counts['hop_admit'],
                    'hop_sent_callbacks':counts['hop_sent'],'hop_retry_requests':counts['hop_retry'],
                    'hop_acks':counts['hop_ack'],'hop_dacks':counts['hop_dack'],
                    'hop_dack_expired':counts['hop_dack_expired'],'hop_failed':counts['hop_failed'],
                    'mean_nwk_custody':area(ci,lo,upper)/BIN,
                    'mean_nwk_pre_first_submit':area(wi,lo,upper)/BIN,
                    'mean_hop_capacity':area(hi,lo,upper)/BIN,
                    'mean_dack_hold':area(di,lo,upper)/BIN})
    coverage = [x for x in obs['data_transmission_callback_coverage'] if x['node'] in NODES]
    assert all(x['sent_indications_without_owned_confirmation'] == 0 for x in coverage)
    return {'seed':seed,'case':evidence.case,'receipt_sha256':evidence.receipt_sha,
        'verified_artifacts':evidence.verified,'protocol_rows':protocol_count,
        'episode_callback_rows_verified':matched,'endpoint_counts_verified':True,
        'flow_counters':obs['flows'],'cohorts':cohorts,'timeline':timeline,
        'hop_callback_coverage':coverage,'admission_trace_prefix':{'rows':prefix_count,
            'last_time_s':prefix_last,'omitted_attempt_rows':1710000-prefix_count,
            'prefix_reason_counts':dict(prefix_summary)},
        'routing':{'node_counters':{node:{k:int(nwk[node][k]) for k in ['RouteChanges','NeighborActivations','NeighborDeactivations','WaitingForRoute']} for node in NODES},
            'neighbor_discovery_events':neighbor_events,'exported_routing_events':route_events,
            'final_routes':[x for x in routes if int(x['NodeId']) in NODES],
            'route_change_times_available':False}}, timeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    root, out = args.workspace.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    assert sha(root/'csr20/evidence/t19/owner.zip') == PARENT_SHA
    review_path = root/'t20-return-review/analysis/review.json'
    review = json.loads(review_path.read_text())
    assert review['evidence_integrity_verified'] and review['full_structural_gate_completed']
    metadata_path = root/'t20-return-review/owner/metadata.json'
    assert sha(metadata_path) == review['metadata_sha256']
    metadata = json.loads(metadata_path.read_text())
    for stage in metadata['StageReceipts']:
        if stage['Phase'] in ('s129','s130'):
            assert sha(root/'t20-return-review/owner'/stage['File']) == stage['SHA256']
    results, timelines = [], []
    for seed in (128,129,130):
        obs = review['reused_seed128']['observations'] if seed == 128 else review['cases'][f's{seed}']['observations']
        result, timeline = analyze_case(root,seed,obs)
        results.append(result)
        timelines.extend(timeline)
        print(f'Seed {seed}: receipt-bound rows and ownership endpoints verified; node 8 cohort metrics complete.', flush=True)
    flows=[]
    for r in review['comparisons']['rows']:
        if r['source'] in (7,8):
            flows.append({k:v for k,v in r.items() if k!='within_descriptive_band'} | {'within_descriptive_10_percent_band':abs(r['residual_percent'])<=10})
    source_paths = ['+csr/+nwk/Layer.m','+csr/+hop/Layer.m','scripts/tranche19_metrics.py','scripts/tranche20_metrics.py']
    source_hashes = {str(Path('csr20')/p):sha(root/'csr20'/p) for p in source_paths}
    accepted_sources = {x['path']:x['sha256'] for x in metadata['SourceFilesFinal']}
    assert all(source_hashes[str(Path('csr20')/p)] == accepted_sources[p] for p in source_paths)
    limitations = [
        'No MATLAB or native simulation was executed; all three MATLAB seeds reuse accepted evidence.',
        'The first 100,000 application attempt records end at about 633.32 s; no omitted per-attempt NSDP/route states are reconstructed.',
        'Complete per-flow admission counters and full protocol app_generate events determine all-time admissions. Scheduled attempts and admitted counts determine per-bin blocked totals; blocked-reason timing is not inferred.',
        'NWK custody, pre-first-submit wait, HOP capacity, and DACK hold occupancy are distinct quantities; integrals are application-seconds clipped to the observation horizon.',
        'Waiting intervals without a submit or release are right-censored at 6000 s. Completed-only wait distributions exclude censored intervals; occupancy includes them through stop. Pre-submit residence does not by itself identify capacity blocking: omitted per-attempt reasons are not available.',
        'Callback-derived occupancy is not hidden queue polling and does not establish instantaneous admission availability. An observed HOP sent callback is a DATA member service event, not a unique packet or whole-radio transmission.',
        'RouteChanges counters and final route snapshots exist, but route-change callbacks are not exported. Stable observed DATA next hops cannot establish that no transient route changes occurred.',
        'NSDP checks count own-source/destination NWK custody, while relay custody and HOP capacity are separately accounted. Occupancy alone does not prove a scheduling bias or code defect.',
        'Cross-engine packet identities and RNG sequences are not joined; three seeds are a descriptive variability screen, not a confidence or equivalence test.'
    ]
    report = {'schema':'csr-tranche21-matlab-node8-trace-analysis-v1','status':'completed',
        'matlab_executed':False,'native_executed':False,'simulation_source_modified':False,
        'analysis_script_sha256':sha(Path(__file__)),'t20_review_sha256':sha(review_path),
        't20_metadata_sha256':sha(metadata_path),
        'accepted_t19_owner_sha256':PARENT_SHA,'source_files_read_sha256':source_hashes,
        'working_descriptive_band_percent':10,'traffic_window_s':[300,6000],
        'results':results,'source7_8_cross_engine_counts':flows,'limitations':limitations}
    (out/'matlab_node8.json').write_text(json.dumps(report,indent=2)+'\n')
    csv_out(out/'matlab_timeline_300s.csv',timelines)
    csv_out(out/'matlab_cohorts.csv',[{k:v for k,v in x.items() if not isinstance(v,dict)} for r in results for x in r['cohorts']])
    csv_out(out/'source7_8_counts.csv',flows)
    lines = ['# T21 MATLAB node-8 trace analysis','',
        'No new simulation or simulator source change. Receipt hashes, all read owner artifact hashes, the full protocol rows used by the ownership episodes, and HOP/NWK ownership endpoints were checked.',
        '', '| Seed | Cohort at node 8 | NWK admissions | HOP admissions | HOP sends | DACKs | Mean NWK custody (apps) | Mean awaiting first submit (apps) | Mean HOP capacity (apps) |',
        '|---:|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in results:
        for x in r['cohorts']:
            if x['node']!=8: continue
            lines.append(f"| {r['seed']} | {'Local 8' if x['source']==8 else 'Relayed '+str(x['source'])} | {x['nwk_enqueued']} | {x['hop_admitted']} | {x['hop_sent_callbacks']} | {x['hop_dacks']} | {x['mean_nwk_custody_traffic_window']:.3f} | {x['mean_nwk_pre_first_submit_traffic_window']:.3f} | {x['mean_hop_capacity_traffic_window']:.3f} |")
    lines += ['', 'Means cover the active traffic window 300–6000 s. Counts of HOP sends include retries.', '',
        'The local source-8 NWK population averages 15.998 applications in every seed, nearly continuously filling its own 16-application NSDP cap. Relayed source-7 custody is additional; the source code counts NSDP by source and destination rather than by total queue size. Node-8 relay custody averages 20.69, 35.30, and 19.47 applications for seeds 128–130, respectively. Most of both cohorts’ custody residence is waiting for first HOP submission.', '',
        'All observed DATA HOP admissions use 7→8, 8→2, and 2→4. Both node-8 neighbors activate before traffic starts and none deactivate. This does not prove absence of transient route changes: only whole-run RouteChanges counts and final route snapshots are available.', '',
        'Seed 130 MATLAB admits 654 local source-8 applications and 802 source-7 applications, versus 181 and 1,381 in ns-3. MATLAB node 8 therefore does not reproduce the native seed-130 local-traffic suppression. A larger native relay queue delaying local-capacity release is a hypothesis to test against native occupancy and service traces; these MATLAB observations alone do not establish its cause.', '',
        'The CSV gives every 300-second cohort window at nodes 2, 7, and 8. The JSON includes complete/censored waits, DACK capacity holds, endpoint states, raw evidence hashes, and routing limits.', '', '## Limits', '']
    lines.extend('- '+x for x in limitations)
    (out/'matlab_findings.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'status':'passed','seeds':3,'cohorts':sum(len(r['cohorts']) for r in results),'timeline_rows':len(timelines),'output':str(out)}))


if __name__ == '__main__':
    main()
