"""Independent read-only analysis of the returned T7 ZIP and pinned references.

This script does not import the candidate's benchmark/return reviewers. The
separately recorded strict shared gate uses the existing strict comparator.
"""
import collections
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import zipfile
from datetime import datetime

BASE = Path('/workspace/scratch/1a5b1ad6ce1b')
REPO = BASE / 'tranche7'
OUT = BASE / 't7-independent-outcomes'
ZIP = BASE / 'upload/tranche7_evidence.zip'
REF = REPO / 'evidence/tranche-7-ns3-reference'
NAMES = [
    'Generator.Traffic Sent (packets/sec)',
    'Generator.Traffic Sent (bits/sec)',
    'Generator.Packet Size (bits)',
    'Sink.Traffic Received (packets/sec)',
    'Sink.Traffic Received (packets)',
    'Sink.Traffic Received (bits/sec)',
    'Sink.Traffic Received (bits)',
    'Sink.End-to-End Delay (seconds)',
]

def csv_zip(z, name):
    return csv.DictReader(io.TextIOWrapper(z.open(name), encoding='utf-8-sig', newline=''))

def relative(a, b):
    return (a-b)*100/b if b else None

def bucket(t, width):
    q = t/width
    if abs(q-round(q)) <= 1e-12:
        q = round(q)
    i = math.floor(q)
    assert 0 <= i < 100
    return i

def aggregate(sent, received, width):
    sc, sb, rc, rb, delay = [[0.0]*100 for _ in range(5)]
    for key, (t, size) in sent.items():
        i = bucket(t, width)
        sc[i] += 1
        sb[i] += 8*size
    for key, (t, size) in received.items():
        i = bucket(t, width)
        rc[i] += 1
        rb[i] += 8*size
        delay[i] += t-sent[key][0]
    values = [
        [v/width for v in sc], [v/width for v in sb],
        [b/c if c else None for b, c in zip(sb, sc)],
        [v/width for v in rc], rc, [v/width for v in rb], rb,
        [d/c if c else None for d, c in zip(delay, rc)],
    ]
    return dict(zip(NAMES, values))

def check_aggregates(rows, reconstructed, width):
    found = set()
    for r in rows:
        if r['statistic'] not in NAMES:
            continue
        end = float(r['time_s'])
        i = round(end/width)-1
        assert math.isclose(end, (i+1)*width, abs_tol=1e-9)
        key = (r['statistic'], i)
        assert key not in found
        found.add(key)
        expected = reconstructed[r['statistic']][i]
        actual = float(r['value']) if r['value_status'] == 'observed' else None
        if expected is None:
            assert actual is None
        else:
            assert actual is not None and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8), (key, actual, expected)
    assert len(found) == 800
    return len(found)

def mean_observed(values):
    return statistics.mean(v for v in values if v is not None)

def flows(sent, received, outcomes=None):
    result = []
    for src in sorted({key[0] for key in sent}):
        keys = [k for k in sent if k[0] == src]
        delivered = [k for k in keys if k in received]
        latencies = [received[k][0]-sent[k][0] for k in delivered]
        r = {'source': src, 'admitted': len(keys), 'delivered': len(delivered),
             'mean_packet_latency_s': statistics.mean(latencies)}
        if outcomes is not None:
            r['dropped'] = sum(outcomes[k] == 'dropped' for k in keys)
            r['pending'] = sum(outcomes[k] == 'pending' for k in keys)
        else:
            r['unmatched_sends_not_classified_as_loss'] = len(keys)-len(delivered)
        result.append(r)
    return result

report = {'schema': 'csr-tranche7-independent-outcomes-v1',
          'uploaded_zip_sha256': hashlib.sha256(ZIP.read_bytes()).hexdigest(),
          'candidate_commit': '28ed878f5673e308047cbea7878b933697d932f3',
          'scope': 'Independent raw application identity/count/bucket reconstruction; retained outcome comparison; separately rerun strict shared application comparators. No local MATLAB execution.',
          'cases': [], 'retained_t6_comparisons': []}

with zipfile.ZipFile(ZIP) as z:
    metadata = json.loads(z.read('validation_metadata.json'))
    report['recorded_run'] = {k: metadata[k] for k in ('StartedUTC','CompletedUTC','TestCount','PassedTests','FailedTests','IncompleteTests')}
    report['recorded_run']['elapsed_wall_seconds'] = (datetime.fromisoformat(metadata['CompletedUTC'])-datetime.fromisoformat(metadata['StartedUTC'])).total_seconds()
    for case, duration, width in [('campus_multihop_6000',6000,60),('two_node_admission_1200',1200,12),('three_node_contention_360',360,3.6)]:
        sent, recv, outcomes, id_to_key = {}, {}, {}, {}
        prefix = 'benchmarks/'+case+'/'
        for r in csv_zip(z, prefix+'raw/protocol_trace.csv'):
            if r['Event'] not in ('app_generate','app_receive','app_drop','relay_accept'):
                continue
            packet = int(r['PacketId'])
            t = float(r['TimeSeconds'])
            size = int(r['ApplicationBytes'])+7
            if r['Event'] == 'app_generate':
                key = (int(r['NodeId']),int(r['PeerId']),packet)
                assert packet not in id_to_key
                id_to_key[packet] = key
                sent[key] = (t, size)
                outcomes[key] = 'pending'
            else:
                key = id_to_key[packet]
                assert sent[key][0] <= t and sent[key][1] == size
                if r['Event'] == 'app_receive':
                    assert key not in recv and int(r['NodeId']) == key[1]
                    recv[key] = (t,size)
                    outcomes[key] = 'delivered'
                elif key not in recv:
                    outcomes[key] = 'dropped' if r['Event'] == 'app_drop' else 'pending'
        raw_summary = json.loads(z.read(prefix+'raw/summary.json'))
        stats = raw_summary['Statistics']
        counts = collections.Counter(outcomes.values())
        assert len(sent) == stats['Generated']
        assert len(recv) == stats['Received'] == counts['delivered']
        assert counts['dropped'] == stats['Dropped'] and counts['pending'] == stats['Pending']
        mat_aggregates = aggregate(sent, recv, width)
        mat_checked = check_aggregates(csv_zip(z, prefix+'analysis/aggregates.csv'), mat_aggregates, width)
        admission = list(csv_zip(z,prefix+'raw/application_admission_statistics.csv'))
        for r in admission:
            assert int(r['Admitted']) == sum(k[0] == int(r['SourceId']) for k in sent)
            assert sum(int(r[k]) for k in ('BlockedDiscovery','BlockedTopology','BlockedGatewayRoute','BlockedDestination')) == 0
            assert int(r['Attempts']) == int(r['Admitted'])+int(r['BlockedNsdp'])
        nsent, nrecv = {}, {}
        with gzip.open(REF/case/'ns3-trace.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                if r['event'] not in ('app_send','nwk_delivery'):
                    continue
                key = (int(r['src']),int(r['dst']),r['sequence'])
                t, size = float(r['time_s']), int(r['size_bytes'])
                if r['event'] == 'app_send':
                    assert key not in nsent
                    nsent[key] = (t,size)
                else:
                    assert key in nsent and key not in nrecv and nsent[key][1] == size and nsent[key][0] <= t
                    nrecv[key] = (t,size)
        ns_aggregates = aggregate(nsent,nrecv,width)
        with (REF/case/'ns3-aggregates.csv').open() as f:
            ns_checked = check_aggregates(csv.DictReader(f), ns_aggregates, width)
        mflows, nflows = flows(sent,recv,outcomes), flows(nsent,nrecv)
        for m,n in zip(mflows,nflows):
            m['admitted_relative_to_ns3_percent'] = relative(m['admitted'],n['admitted'])
            m['delivered_relative_to_ns3_percent'] = relative(m['delivered'],n['delivered'])
        cmp = {}
        for name in NAMES:
            a,b = mat_aggregates[name],ns_aggregates[name]
            differences = [[(i+1)*width, v-w] for i,(v,w) in enumerate(zip(a,b)) if v is not None and w is not None]
            # Retain a single reproducible maximum for review, not just totals.
            max_end,max_diff = max(differences, key=lambda x:abs(x[1]))
            cmp[name] = {'matlab_observed_bucket_mean':mean_observed(a),'ns3_observed_bucket_mean':mean_observed(b),
                         'relative_difference_percent':relative(mean_observed(a),mean_observed(b)),
                         'maximum_absolute_bucket_difference':abs(max_diff),'maximum_difference_bucket_end_s':max_end,
                         'maximum_bucket_signed_matlab_minus_ns3':max_diff}
        c = {'case_id':case,'duration_s':duration,'bucket_width_s':width,
             'matlab_counts':dict(generated=len(sent),received=len(recv),dropped=counts['dropped'],pending=counts['pending']),
             'ns3_counts':dict(admitted=len(nsent),delivered=len(nrecv),unmatched_sends_not_classified_as_loss=len(nsent)-len(nrecv)),
             'matlab_flows':mflows,'ns3_flows':nflows,
             'raw_aggregate_points_reconstructed':dict(matlab=mat_checked,ns3=ns_checked),
             'matlab_runtime_seconds':raw_summary['Metadata']['RuntimeSeconds'],
             'matlab_admission_attempts':sum(int(r['Attempts']) for r in admission),
             'matlab_nsdp_blocked_attempts':sum(int(r['BlockedNsdp']) for r in admission),
             'matlab_packet_weighted_mean_latency_s':statistics.mean(recv[k][0]-sent[k][0] for k in recv),
             'ns3_packet_weighted_mean_latency_s':statistics.mean(nrecv[k][0]-nsent[k][0] for k in nrecv),
             'matlab_vs_ns3_series':cmp,'matlab_physical_drop_reasons':stats['PhysicalDropReasons'],
             'matlab_application_drop_reasons':stats['DropReasons']}
        if case == 'campus_multihop_6000':
            observed = collections.defaultdict(list)
            missing = collections.Counter()
            with (REF/case/'opnet-aggregates.csv').open() as f:
                for r in csv.DictReader(f):
                    if r['statistic'] not in NAMES:
                        continue
                    if r['value_status'] == 'observed':
                        observed[r['statistic']].append(float(r['value']))
                    else:
                        missing[r['statistic']] += 1
            c['archived_opnet'] = {
                'derived_sent_total_from_100_equal_width_rate_buckets':sum(observed[NAMES[0]])*width,
                'derived_received_total_from_100_equal_width_rate_buckets':sum(observed[NAMES[3]])*width,
                'received_total_from_95_observed_count_buckets':sum(observed[NAMES[4]]),
                'sent_mean_rate_packets_per_second':statistics.mean(observed[NAMES[0]]),
                'received_mean_rate_packets_per_second':statistics.mean(observed[NAMES[3]]),
                'populated_bucket_mean_delay_s':statistics.mean(observed[NAMES[7]]),
                'missing_bucket_counts':dict(missing),
                'matlab_received_rate_relative_percent':relative(mean_observed(mat_aggregates[NAMES[3]]),statistics.mean(observed[NAMES[3]])),
                'matlab_populated_bucket_delay_relative_percent':relative(mean_observed(mat_aggregates[NAMES[7]]),statistics.mean(observed[NAMES[7]])),
            }
            assert len(observed[NAMES[0]]) == len(observed[NAMES[3]]) == 100
            assert len(observed[NAMES[7]]) == 95
        report['cases'].append(c)
    accepted = REPO/'evidence/tranche-6-r2025a-accepted'
    for name in z.namelist():
        if not name.endswith('/scenario_summary.csv'):
            continue
        rows = list(csv_zip(z,name))
        f = 'scenario_summary.csv' if 'CaseId' in rows[0] else 'tranche4_scenario_summary.csv' if 'Seed' in rows[0] else 'tranche3_scenario_summary.csv' if 'ApplicationBytesReceived' in rows[0] else 'tranche2_scenario_summary.csv'
        with (accepted/f).open() as stream:
            previous = list(csv.DictReader(stream))
        assert len(previous) == len(rows)
        checked = 0
        for a,b in zip(previous,rows):
            assert a.keys() == b.keys()
            for key in a:
                if key != 'RuntimeSeconds':
                    assert a[key] == b[key], (f,a['Scenario'],key,a[key],b[key])
                    checked += 1
        report['retained_t6_comparisons'].append({'accepted_file':f,'returned_member':name,'rows':len(rows),'non_runtime_cells_exactly_equal':checked,'excluded_columns':['RuntimeSeconds']})
    perf_name = next(n for n in z.namelist() if n.endswith('/performance_summary.csv') and '/diagnostics/' not in n and not n.startswith('benchmarks/'))
    current = list(csv_zip(z,perf_name))
    with (accepted/'performance_summary.csv').open() as stream:
        previous = list(csv.DictReader(stream))
    assert len(current) == len(previous) == 18
    checked = 0
    for a,b in zip(previous,current):
        assert a.keys() == b.keys()
        for key in a:
            if key != 'RuntimeSeconds':
                assert a[key] == b[key], (a['Scenario'],key,a[key],b[key])
                checked += 1
    report['retained_t6_performance_comparison']={'rows':18,'non_runtime_cells_exactly_equal':checked,'excluded_columns':['RuntimeSeconds']}
report['strict_shared_gate'] = json.loads((OUT/'strict-shared-gate.json').read_text())
report['limitations'] = [
    'One seed (128) per benchmark; no across-seed uncertainty estimate or numerical tolerance acceptance.',
    'Exact application identity matching is internal to each simulator; IDs are not equated across runtimes.',
    'NS-3 unmatched sends are not sufficient to distinguish terminal loss from finite-stop pending work.',
    'OPNET is archived aggregate evidence only; no new OPNET runtime or packet-level trace.',
    'Mean of populated bucket delay means differs from the packet-weighted global mean.',
    'OPNET has five missing initial packet-count/bit-count buckets, whereas MATLAB/ns-3 report zero counts; compare full-window rates or equal-support paired means.',
    'Physical receiver-observation losses are not application loss counts and do not establish a causal explanation for aggregate residuals.',
]
(OUT/'outcomes.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'case_counts':[{k:v for k,v in c.items() if k in ('case_id','matlab_counts','ns3_counts','raw_aggregate_points_reconstructed','matlab_packet_weighted_mean_latency_s','ns3_packet_weighted_mean_latency_s','matlab_flows','ns3_flows')} for c in report['cases']], 'retained_comparisons':report['retained_t6_comparisons'], 'retained_performance':report['retained_t6_performance_comparison'],'strict_shared_cases':len(report['strict_shared_gate'])},indent=2))
