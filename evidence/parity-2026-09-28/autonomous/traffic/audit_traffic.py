#!/usr/bin/env python3
"""Offline seed132 autonomous offered-load and admission-state audit.

No simulator execution. The first 30 s after source start has paired complete
admission detail; long-run admitted application populations are joined to the
20 ms attempt grid. Native raw admission detail is checked over all 6,000 s.
"""
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
MAT = ROOT / 'return6000/data/s132/attempt_001'
NAT = ROOT / 'next_feedback/native_archive/evidence/tranche-25-ns3-reference/s132'
LEDGER = ROOT / 'return6000/kit/csr6000/reference/s132/applications.csv'
START = 300_000_000_000
STEP = 20_000_000
SOURCES = [2, 3, 4, 5, 7, 8]

def ns(value):
    return int((Decimal(value) * 10**9).to_integral_value(rounding=ROUND_HALF_EVEN))

def read(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))

def write(name, rows):
    if not rows:
        return
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def details(value):
    return dict(p.split('=', 1) for p in value.split(';') if '=' in p)

matapps = read(MAT / 'analysis/applications.csv')
natapps = read(LEDGER)
ma = defaultdict(dict)
na = defaultdict(dict)
for r in matapps:
    tick = (ns(r['GeneratedSeconds']) - START) // STEP
    assert ns(r['GeneratedSeconds']) == START + STEP*tick
    assert tick not in ma[int(r['SourceId'])]
    ma[int(r['SourceId'])][tick] = r
for r in natapps:
    tick = int(r['attempt_index_0based'])
    assert int(r['generated_time_ns']) == START + STEP*tick
    assert tick not in na[int(r['source'])]
    na[int(r['source'])][tick] = r

matstats = {int(r['SourceId']): r for r in read(MAT / 'raw/application_admission_statistics.csv')}
natstats = {int(r['source']): r for r in read(NAT / 'app-admission-diagnostics.csv')}
mprefix = {}
mchecked = Counter()
mat_grid_max_error_ns = 0
for r in read(MAT / 'raw/application_admission_trace.csv'):
    s = int(r['SourceId']); tick = int(r['AttemptIndex']) - 1
    err = ns(r['TimeSeconds']) - (START + STEP*tick)
    mat_grid_max_error_ns = max(mat_grid_max_error_ns, abs(err))
    accepted = bool(int(r['Accepted']))
    expected = int(r['NsdpCount']) < 16
    assert not int(r['DiscoveryActive']) and int(r['TopologyKnown'])
    assert accepted == expected
    mchecked[s] += 1
    if ns(r['TimeSeconds']) < 330_000_000_000:
        mprefix[(s, tick)] = {
            'source': s, 'attempt_0based': tick, 'time_ns': ns(r['TimeSeconds']),
            'accepted': accepted, 'reason': r['Reason'], 'nsdp': int(r['NsdpCount']),
            'nwk_queue': int(r['NwkQueueSize']), 'packet_id': r['PacketId'],
        }

nprefix = {}
ncounts = Counter(); nreasons = defaultdict(Counter); ngeneration = Counter()
native_grid_max_error_ns = 0
native_gate_mismatch = []
native_early = []
native_admit_grid_admitted_mismatch = []
native_initial_source_hop = {}
interesting = {'tx_start', 'rx_accept', 'hop_completion', 'nwk_nsdp_release',
               'reservation_prepare', 'reservation_advertise', 'hop_admission'}
with gzip.open(NAT / 'ns3-trace.csv.gz', 'rt', newline='') as f:
    for r in csv.DictReader(f):
        ev = r['event']
        if ev == 'app_admission':
            d = details(r['detail'])
            s = int(r['node']); tick = int(d['attempt_index']) - 1
            t = ns(r['time_s']); accepted = r['success'] == '1'
            error = t - (START + STEP*tick)
            native_grid_max_error_ns = max(native_grid_max_error_ns, abs(error))
            assert tick == ncounts[s]
            ncounts[s] += 1; nreasons[s][r['reason']] += 1
            expected = (d['discovery_active'] == '0' and d['topology_known'] == '1'
                        and int(d['nsdp_count']) < 16)
            if accepted != expected:
                native_gate_mismatch.append(r)
            if accepted != (tick in na[s]):
                native_admit_grid_admitted_mismatch.append([s, tick])
            if t < 330_000_000_000:
                nprefix[(s, tick)] = {
                    'source': s, 'attempt_0based': tick, 'time_ns': t,
                    'accepted': accepted, 'reason': r['reason'], 'nsdp': int(d['nsdp_count']),
                    'nwk_queue': int(d['nwk_queue']), 'packet_id': r['sequence'],
                }
        elif ev == 'app_send':
            s = int(r['node']); t = ns(r['time_s']); tick = (t-START)//STEP
            assert t == START + STEP*tick
            assert r['sequence'] == na[s][tick]['native_app_id']
            ngeneration[s] += 1
        elif ev in interesting and r['node'] in {'2','3','4','5','7','8'}:
            t = ns(r['time_s'])
            if 300_000_000_000 <= t < 318_000_000_000:
                if ev == 'hop_admission' and r['node'] == r['src']:
                    native_initial_source_hop.setdefault(int(r['node']), {
                        'time_ns': t, 'application_id': r['sequence'],
                        'delay_from_first_app_attempt_ns': t-START,
                    })
                if r['node'] in {'7','8'}:
                    native_early.append(r)

assert set(mprefix) == set(nprefix)
assert not native_gate_mismatch and not native_admit_grid_admitted_mismatch
paired = []
for key in sorted(mprefix, key=lambda k: (k[1], k[0])):
    m, n = mprefix[key], nprefix[key]
    assert m['time_ns'] == n['time_ns']
    paired.append({
        'source': key[0], 'attempt_1based': key[1]+1,
        'time_s': str(Decimal(m['time_ns'])/10**9),
        **{'matlab_'+k: m[k] for k in ('accepted','reason','nsdp','nwk_queue','packet_id')},
        **{'ns3_'+k: n[k] for k in ('accepted','reason','nsdp','nwk_queue','packet_id')},
        'same_admission_outcome': m['accepted'] == n['accepted'],
    })
write('paired_attempts_300_330.csv', paired)
write('native_node7_8_early_service.csv', native_early)

mat_early = []
with (MAT / 'raw/protocol_trace.csv').open(newline='') as f:
    for r in csv.DictReader(f):
        t = ns(r['TimeSeconds'])
        if t >= 330_000_000_000:
            break
        if t >= START and r['NodeId'] in {'7','8'} and r['Event'] in {
            'hop_admit','hop_sent','hop_retry','hop_ack','hop_dack','network_custody_release',
            'hop_receive','mac_prepare','network_submit'}:
            mat_early.append(r)
write('matlab_node7_8_early_service.csv', mat_early)

flowrows = []; firstrows = []; cohorts = []
for s in SOURCES:
    ms, ns_ = matstats[s], natstats[s]
    assert int(ms['Attempts']) == int(ns_['attempts']) == ncounts[s] == 285000
    assert int(ms['Admitted']) == len(ma[s])
    assert int(ns_['admitted']) == len(na[s]) == ngeneration[s]
    assert not any(int(ms[f]) for f in ['BlockedDiscovery','BlockedTopology','BlockedGatewayRoute','BlockedDestination'])
    assert not any(int(ns_[f]) for f in ['blocked_discovery','blocked_topology','blocked_gateway_route','blocked_destination'])
    first = min(set(ma[s]) ^ set(na[s]))
    firstrows.append(next(r for r in paired if r['source'] == s and r['attempt_1based'] == first+1))
    flowrows.append({
        'source': s, 'attempts_each': 285000,
        'matlab_admitted': len(ma[s]), 'ns3_admitted': len(na[s]),
        'matlab_blocked_nsdp': int(ms['BlockedNsdp']), 'ns3_blocked_nsdp': int(ns_['blocked_nsdp']),
        'both_admitted_same_attempt': len(set(ma[s]) & set(na[s])),
        'matlab_only_admitted_attempt': len(set(ma[s])-set(na[s])),
        'ns3_only_admitted_attempt': len(set(na[s])-set(ma[s])),
        'first_outcome_difference_s': str(Decimal(START+STEP*first)/10**9),
        'matlab_admitted_300_330': sum(t<1500 for t in ma[s]),
        'ns3_admitted_300_330': sum(t<1500 for t in na[s]),
        'matlab_first_replacement_admitted_s': str(Decimal(START+STEP*sorted(ma[s])[16])/10**9),
        'ns3_first_replacement_admitted_s': str(Decimal(START+STEP*sorted(na[s])[16])/10**9),
    })
    for start in range(300,6000,100):
        end = min(start+100,6000)
        lo=(start-300)*50; hi=(end-300)*50
        cohorts.append({'source':s,'interval_start_s':start,'interval_end_s_exclusive':end,
                        'matlab_admitted':sum(lo<=t<hi for t in ma[s]),
                        'ns3_admitted':sum(lo<=t<hi for t in na[s])})
write('source_accounting.csv', flowrows)
write('first_admission_difference.csv', firstrows)
write('admission_100s_cohorts.csv', cohorts)

scenario_match = (MAT/'raw/scenario.csv').read_bytes() == (NAT/'scenario.csv').read_bytes()
assert scenario_match
summary = {
    'scope': 'Seed132, fixed-destination offered load and endogenous admission; offline existing traces only',
    'scenario_bytes_identical': scenario_match,
    'source_ids': SOURCES, 'attempt_start_ns':START, 'attempt_interval_ns':STEP,
    'attempt_stop_ns_exclusive':6000_000_000_000,
    'attempts_each_source':285000, 'native_all_raw_attempts_checked':sum(ncounts.values()),
    'matlab_exported_attempts_checked':sum(mchecked.values()),
    'matlab_admission_trace_is_truncated':sum(mchecked.values()) != 1710000,
    'matlab_grid_max_abs_error_ns':mat_grid_max_error_ns,
    'native_grid_max_abs_error_ns':native_grid_max_error_ns,
    'both_generated_application_ledgers_are_exact_on_attempt_grid':True,
    'native_all_raw_admission_outcomes_match_generated_ledger':True,
    'native_all_raw_gate_outcomes_match_observed_nsdp_threshold':True,
    'matlab_exported_gate_outcomes_match_observed_nsdp_threshold':True,
    'paired_complete_attempts_300_330':len(paired),
    'paired_same_outcome_count':sum(r['same_admission_outcome'] for r in paired),
    'paired_same_nsdp_count':sum(r['matlab_nsdp']==r['ns3_nsdp'] for r in paired),
    'all_first_16_admitted_in_both':all(t in ma[s] and t in na[s] for s in SOURCES for t in range(16)),
    'first_difference':min(firstrows,key=lambda r:Decimal(r['time_s'])),
    'native_first_source_hop_admission':native_initial_source_hop,
    'traffic_rng_draws_required_by_config':0,
    'flow_comparisons':flowrows,
    'native_block_reason_counts':dict(nreasons),
    'matlab_admission_prefix_last_time_s':max((r['TimeSeconds'] for r in read(MAT/'raw/application_admission_trace.csv')),key=Decimal),
    'limitations':[
        'MATLAB full long-run blocked-attempt state rows are not exported after its100000-record admission budget; full counters and all admitted apps remain available.',
        'The 28ns native source NWK-to-HOP callback delay is not a source-attempt offset.',
        'Same numeric seed does not imply matching MAC/PHY/NWK/synchronization RNG histories.',
        'No inference that the early race alone explains the entire6000s latency difference.',
        'Generated application counts refer to admitted attempts; suppressed attempts do not create packets.',
    ],
}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
inputs = [MAT/'raw/scenario.csv',NAT/'scenario.csv',MAT/'raw/application_admission_trace.csv',
          MAT/'raw/application_admission_statistics.csv',MAT/'analysis/applications.csv',
          NAT/'app-admission-diagnostics.csv',NAT/'ns3-trace.csv.gz',LEDGER]
(OUT/'input_manifest.json').write_text(json.dumps([
    {'path':str(p.relative_to(ROOT)),'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),'bytes':p.stat().st_size}
    for p in inputs],indent=2)+'\n')
print(json.dumps({'source_accounting':flowrows,'native_attempts_checked':sum(ncounts.values()),
                  'paired_attempts':len(paired),'first_divergence':summary['first_difference']},indent=2))
