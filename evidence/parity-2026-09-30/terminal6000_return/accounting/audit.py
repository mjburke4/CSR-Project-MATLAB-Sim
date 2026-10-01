#!/usr/bin/env python3
"""Independent offline full-run accounting, using protocol events as primary evidence.

Run from the workspace root: python terminal6000_return/accounting/audit.py
No simulation is executed. The issued ZIP is read directly for native ledgers.
"""
import csv
import hashlib
import io
import json
import math
from collections import Counter
from decimal import Decimal
from pathlib import Path
from statistics import mean
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA = ROOT / 'terminal6000_return/data'
KIT = ROOT / 'recovered/csr-6000-terminal-parity-tests.zip'
SOURCES = (2, 3, 4, 5, 7, 8)
STOP = 6000_000_000_000
START = 300_000_000_000
INTERVAL = 20_000_000
inputs = {}
checks = []


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    checks.append(message)


def record_hash(path):
    inputs[str(path.relative_to(ROOT))] = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def rows(path):
    record_hash(path)
    with path.open(newline='', encoding='utf-8-sig') as f:
        yield from csv.DictReader(f)


def ns(value):
    return int((Decimal(value) * 1_000_000_000).to_integral_value())


def read_json(path):
    record_hash(path)
    return json.loads(path.read_text())


def quantile(values, q):
    if not values:
        return None
    v = sorted(values)
    pos = (len(v)-1)*q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    return v[lo] + (v[hi]-v[lo])*(pos-lo)


def write_csv(name, content):
    with (OUT/name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(content[0]))
        w.writeheader()
        w.writerows(content)


def matlab(seed, base=DATA, legacy=False):
    folder = base/f's{seed}/attempt_001'
    tag=f's{seed}' if not legacy else f'priorO/s{seed}'
    apps = {}
    counts = Counter()
    transitions = Counter()
    prev = Decimal(-1)
    for row in rows(folder/'raw/protocol_trace.csv'):
        time = Decimal(row['TimeSeconds'])
        require_time = Decimal(0) <= time < Decimal(6000)
        if not require_time or time < prev:
            raise AssertionError(f's{seed}: invalid event time {time}, previous={prev}')
        prev = time
        ev = row['Event']
        counts[ev] += 1
        if ev not in ('app_generate', 'app_receive', 'app_drop', 'relay_accept'):
            continue
        pid = int(row['PacketId'])
        t = ns(row['TimeSeconds'])
        if ev == 'app_generate':
            if pid in apps:
                raise AssertionError(f'duplicate generation {seed}:{pid}')
            source = int(row['NodeId'])
            if source not in SOURCES or t < START or (t-START) % INTERVAL:
                raise AssertionError(f'off-grid or invalid source {seed}:{pid}')
            apps[pid] = dict(model='matlab', seed=seed, source=source,
                             destination=int(row['PeerId']), application_id=pid,
                             attempt_index=(t-START)//INTERVAL,
                             generation_ns=t, delivery_ns=None, latency_ns=None,
                             status='pending', delivery_events=0, drop_events=0,
                             late_delivery_count=0, late_custody_count=0,
                             bytes=int(row['ApplicationBytes']), dscp=int(row['Dscp']))
        else:
            a = apps[pid]
            if t < a['generation_ns'] or int(row['ApplicationBytes']) != a['bytes']:
                raise AssertionError(f'inconsistent application {seed}:{pid}')
            prior = a['status']
            if ev == 'app_receive':
                if int(row['NodeId']) != a['destination'] or int(row['Dscp']) != a['dscp']:
                    raise AssertionError(f'wrong delivery endpoint/DSCP {seed}:{pid}')
                a['delivery_events'] += 1
                if a['delivery_ns'] is None:
                    a['delivery_ns'] = t
                    a['latency_ns'] = t-a['generation_ns']
                    if prior == 'dropped':
                        a['late_delivery_count'] += 1
                        transitions['LateDeliveries'] += 1
                a['status'] = 'delivered'
            elif ev == 'app_drop':
                if prior == 'delivered':
                    raise AssertionError(f'drop after unique delivery {seed}:{pid}')
                if prior == 'dropped':
                    raise AssertionError(f'duplicate unresolved drop {seed}:{pid}')
                a['status'] = 'dropped'
                a['drop_events'] += 1
            elif prior != 'delivered':
                if prior == 'dropped':
                    a['late_custody_count'] += 1
                    transitions['LateCustodyRecoveries'] += 1
                a['status'] = 'pending'
    require(True, f's{seed}: every raw protocol row ordered and in [0,6000)')
    summary = read_json(folder/'raw/summary.json')['Statistics']
    states = Counter(a['status'] for a in apps.values())
    for field, observed in [('Generated',len(apps)), ('Received',states['delivered']),
                            ('Dropped',states['dropped']), ('Pending',states['pending']),
                            ('LateDeliveries',transitions['LateDeliveries']),
                            ('LateCustodyRecoveries',transitions['LateCustodyRecoveries']),
                            ('ApplicationBytesReceived',sum(a['bytes'] for a in apps.values() if a['delivery_ns'] is not None))]:
        if legacy and field in ('LateDeliveries','LateCustodyRecoveries') and field not in summary:
            require(observed==0, f'{tag}: no recovery transitions in prior implementation')
            continue
        require(summary[field] == observed, f'{tag}: raw reconstructed {field} equals counter ({observed})')
    require(summary['OmittedTraceRecords']==0, f's{seed}: complete protocol trace')
    require(summary['OmittedPhyTraceRecords']==0, f's{seed}: complete PHY trace')
    require(abs(summary['LatencySumSeconds']-sum(a['latency_ns'] or 0 for a in apps.values())/1e9) < 1e-5,
            f's{seed}: reconstructed latency sum agrees with accumulator')
    reported = {int(r['PacketId']):r for r in rows(folder/'analysis/applications.csv')}
    require(set(apps)==set(reported), f's{seed}: published application IDs equal raw generations')
    for pid,a in apps.items():
        r=reported[pid]
        if (a['source'] != int(r['SourceId']) or a['destination'] != int(r['DestinationId']) or
            a['generation_ns'] != ns(r['GeneratedSeconds']) or a['status'] != r['Outcome'] or
            (a['delivery_ns'] is not None and (a['delivery_ns'] != ns(r['ReceivedSeconds']) or abs(a['latency_ns']-ns(r['LatencySeconds']))>1))):
            raise AssertionError(f'published application mismatch {seed}:{pid}')
    require(True, f's{seed}: every published outcome and first delivery agrees with raw reconstruction')
    admission={int(r['SourceId']):r for r in rows(folder/'raw/application_admission_statistics.csv')}
    for source in SOURCES:
        r=admission[source]
        count=sum(a['source']==source for a in apps.values())
        require(int(r['Admitted'])==count, f's{seed}/source{source}: complete admission counter equals generations')
        blocked=sum(int(r[k]) for k in ('BlockedDiscovery','BlockedTopology','BlockedGatewayRoute','BlockedDestination','BlockedNsdp'))
        require(int(r['Attempts'])==285000 and count+blocked==285000,
                f's{seed}/source{source}: all 285000 attempted applications accounted for')
    if legacy:
        for a in apps.values():a['model']='matlab_prior_o'
    return list(apps.values()),dict(event_counts=counts,transitions=transitions,raw_statistics=summary,
                                   admission_counters=admission)


def native(seed,z):
    path=f'csr6000/reference/s{seed}/applications.csv'
    content=z.read(path)
    inputs[f'{KIT.relative_to(ROOT)}::{path}']=hashlib.sha256(content).hexdigest()
    apps=[]
    for r in csv.DictReader(io.StringIO(content.decode())):
        delivery=int(r['first_delivery_time_ns']) if r['first_delivery_time_ns'] else None
        gen=int(r['generated_time_ns'])
        latency=None if delivery is None else delivery-gen
        if latency is not None and latency!=int(r['latency_ns']):
            raise AssertionError(f'native inconsistent latency {seed}:{r["native_app_id"]}')
        if not START<=gen<STOP or (delivery is not None and not gen<=delivery<STOP):
            raise AssertionError('native event outside comparable interval')
        apps.append(dict(model='native',seed=seed,source=int(r['source']),destination=int(r['destination']),
                         application_id=int(r['native_app_id']),attempt_index=int(r['attempt_index_0based']),
                         generation_ns=gen,delivery_ns=delivery,latency_ns=latency,status=r['status'],
                         delivery_events=int(r['delivery_event_count']),drop_events=None,
                         late_delivery_count=None,late_custody_count=None,bytes=185,dscp=0))
    require(len({a['application_id'] for a in apps})==len(apps),f's{seed}: native normalized IDs unique')
    path=f'csr6000/reference/s{seed}/app-admission-diagnostics.csv'
    content=z.read(path)
    inputs[f'{KIT.relative_to(ROOT)}::{path}']=hashlib.sha256(content).hexdigest()
    admission={int(r['source']):r for r in csv.DictReader(io.StringIO(content.decode()))}
    for source in SOURCES:
        r=admission[source]
        admitted=sum(a['source']==source for a in apps)
        require(admitted==int(r['admitted']),f's{seed}/source{source}: native ledger matches admission diagnostic')
        require(int(r['attempts'])==285000 and sum(int(r[k]) for k in ('admitted','blocked_discovery','blocked_topology','blocked_gateway_route','blocked_destination','blocked_nsdp'))==285000,
                f's{seed}/source{source}: native attempted population closes')
    return apps


def account(pop, model, seed, source):
    a=[a for a in pop if source==0 or a['source']==source]
    lat=[a['latency_ns']/1e9 for a in a if a['delivery_ns'] is not None]
    ages=[(STOP-a['generation_ns'])/1e9 for a in a if a['delivery_ns'] is None]
    return dict(model=model,seed=seed,source=source,attempted=285000*(6 if source==0 else 1),
                admitted=len(a),not_admitted=285000*(6 if source==0 else 1)-len(a),delivered=len(lat),
                unresolved=len(a)-len(lat),raw_dropped=sum(a['status']=='dropped' for a in a) if model.startswith('matlab') else None,
                raw_pending=sum(a['status']=='pending' for a in a) if model.startswith('matlab') else None,
                delivery_events=sum(a['delivery_events'] for a in a),duplicate_delivery_events=sum(max(0,a['delivery_events']-1) for a in a),
                late_deliveries=sum(a['late_delivery_count'] for a in a) if model.startswith('matlab') else None,
                late_custody_recoveries=sum(a['late_custody_count'] for a in a) if model.startswith('matlab') else None,
                mean_latency_s=mean(lat) if lat else None,median_latency_s=quantile(lat,.5),p95_latency_s=quantile(lat,.95),
                max_latency_s=max(lat) if lat else None,mean_unresolved_age_s=mean(ages) if ages else None,
                max_unresolved_age_s=max(ages) if ages else None)


def fixed_age(pop,model,seed,source,horizon):
    allapps=[a for a in pop if source==0 or a['source']==source]
    eligible=[a for a in allapps if START<=a['generation_ns']<STOP-horizon*10**9]
    delivered=[a for a in eligible if a['delivery_ns'] is not None]
    timely=[a for a in delivered if a['latency_ns']<=horizon*10**9]
    attempts=((STOP-horizon*10**9-START)//INTERVAL)*(6 if source==0 else 1)
    return dict(model=model,seed=seed,source=source,horizon_s=horizon,scheduled_attempts=attempts,
                admitted=len(eligible),not_admitted=attempts-len(eligible),delivered_by_age=len(timely),
                delivered_later_by_stop=len(delivered)-len(timely),unresolved_at_stop=len(eligible)-len(delivered),
                raw_model_dropped_by_stop=sum(a['status']=='dropped' for a in eligible) if model.startswith('matlab') else None,
                raw_model_pending_at_stop=sum(a['status']=='pending' for a in eligible) if model.startswith('matlab') else None,
                fraction_of_scheduled=len(timely)/attempts,
                fraction_of_admitted=len(timely)/len(eligible) if eligible else None,
                admissions_outside_window=len(allapps)-len(eligible))


def main():
    record_hash(KIT)
    populations={}
    details={}
    accounting=[]
    horizons=[]
    with zipfile.ZipFile(KIT) as z:
        for seed in (131,132):
            populations['matlab',seed],details[seed]=matlab(seed)
            populations['native',seed]=native(seed,z)
            for model in ('matlab','native'):
                pop=populations[model,seed]
                accounting.extend(account(pop,model,seed,source) for source in (0,)+SOURCES)
                horizons.extend(fixed_age(pop,model,seed,source,h) for h in (60,300,600,1200) for source in (0,)+SOURCES)
            recorded={(r['model'],int(r['source']),int(r['horizon_s'])):r for r in rows(DATA/f's{seed}/attempt_001/analysis/fixed_age_delivery.csv')}
            for r in (r for r in horizons if r['seed']==seed):
                v=recorded[r['model'],r['source'],r['horizon_s']]
                for key in ('scheduled_attempts','admitted','not_admitted','delivered_by_age','delivered_later_by_stop','unresolved_at_stop','admissions_outside_window'):
                    if r[key]!=int(v[key]):raise AssertionError(f'fixed age mismatch: {seed} {r} {key}')
            require(True,f's{seed}: all 56 fixed-age populations agree with raw reconstruction')
    index={(r['model'],r['seed'],r['source']):r for r in accounting}
    targets=[]
    for seed in (131,132):
        for source in SOURCES:
            m=index['matlab',seed,source];n=index['native',seed,source]
            dc=None if n['delivered']==0 else 100*(m['delivered']/n['delivered']-1)
            dl=None if n['mean_latency_s'] is None else 100*(m['mean_latency_s']/n['mean_latency_s']-1)
            targets.append(dict(seed=seed,source=source,native_admitted=n['admitted'],matlab_admitted=m['admitted'],
                                native_delivered=n['delivered'],matlab_delivered=m['delivered'],count_delta_percent=dc,
                                native_mean_latency_s=n['mean_latency_s'],matlab_mean_latency_s=m['mean_latency_s'],latency_delta_percent=dl,
                                count_within_15=None if dc is None else abs(dc)<=15,
                                latency_within_15=None if dl is None else abs(dl)<=15,
                                both_within_15=None if dc is None or dl is None else abs(dc)<=15 and abs(dl)<=15))
    pooled={}
    for model in ('matlab','native'):
        allapps=sum((populations[model,s] for s in (131,132)),[])
        totals=account(allapps,model,0,0)
        totals['attempted']*=2
        totals['not_admitted']=totals['attempted']-totals['admitted']
        pooled[model]=totals
    native_count=pooled['native']['delivered']
    weighted=sum(r['native_delivered']*r['matlab_mean_latency_s'] for r in targets if r['native_delivered'])/native_count
    raw_gap=100*(pooled['matlab']['mean_latency_s']/pooled['native']['mean_latency_s']-1)
    weighted_gap=100*(weighted/pooled['native']['mean_latency_s']-1)
    extra_apps=[a for a in populations['matlab',131] if a['source'] in (2,7,8)]
    extra_delivered=[a for a in extra_apps if a['delivery_ns'] is not None]
    common_lat=[a['latency_ns']/1e9 for (model,seed),pop in populations.items() if model=='matlab' for a in pop if a['delivery_ns'] is not None and not (seed==131 and a['source'] in (2,7,8))]
    contribution=[]
    for r in targets:
        if r['native_delivered']:
            contribution.append(dict(seed=r['seed'],source=r['source'],native_delivery_weight=r['native_delivered']/native_count,
                                     weighted_latency_gap_s=r['native_delivered']/native_count*(r['matlab_mean_latency_s']-r['native_mean_latency_s'])))
    contribution.sort(key=lambda r:r['weighted_latency_gap_s'],reverse=True)
    # Prior O is rebuilt from its complete raw protocol, not paired by local IDs.
    prior={}
    prior_details={}
    for seed in (131,132):
        prior[seed],prior_details[seed]=matlab(seed,ROOT/'full6000_return/data',legacy=True)
    prior_accounting=[account(prior[seed],'matlab_prior_o',seed,source) for seed in (131,132) for source in (0,)+SOURCES]
    prior_total=account(prior[131]+prior[132],'matlab_prior_o',0,0)
    prior_total['attempted']*=2
    prior_total['not_admitted']=prior_total['attempted']-prior_total['admitted']
    prior_index={(r['seed'],r['source']):r for r in prior_accounting}
    prior_weighted=sum(r['native_delivered']*prior_index[r['seed'],r['source']]['mean_latency_s'] for r in targets if r['native_delivered'])/native_count
    previous=dict(pooled=prior_total,native_delivery_weighted_matlab_mean_s=prior_weighted,
                  native_delivery_weighted_latency_gap_percent=100*(prior_weighted/pooled['native']['mean_latency_s']-1),
                  raw_latency_gap_percent=100*(prior_total['mean_latency_s']/pooled['native']['mean_latency_s']-1),
                  both_metrics_within_15=sum(abs(prior_index[r['seed'],r['source']]['delivered']/r['native_delivered']-1)<=.15 and abs(prior_index[r['seed'],r['source']]['mean_latency_s']/r['native_mean_latency_s']-1)<=.15 for r in targets if r['native_delivered']),
                  comparison_scope='Descriptive independent autonomous runs; no application-ID matching across O and P.')
    strata=[]
    p_all=populations['matlab',131]+populations['matlab',132]
    for seed in (0,131,132):
        for source in ((0,) if seed==0 else (0,)+SOURCES):
            delivered=[a for a in p_all if (seed==0 or a['seed']==seed) and (source==0 or a['source']==source) and a['delivery_ns'] is not None]
            total_lat=sum(a['latency_ns'] for a in delivered)
            for with_drop in (False,True):
                selected=[a for a in delivered if bool(a['drop_events'])==with_drop]
                latency=sum(a['latency_ns'] for a in selected)
                strata.append(dict(seed=seed,source=source,prior_provisional_drop=with_drop,delivered=len(selected),
                                   mean_latency_s=latency/len(selected)/1e9 if selected else None,
                                   latency_sum_s=latency/1e9,fraction_of_deliveries=len(selected)/len(delivered) if delivered else None,
                                   fraction_of_latency_sum=latency/total_lat if total_lat else None,
                                   late_delivery_counter_events=sum(a['late_delivery_count'] for a in selected),
                                   late_custody_counter_events=sum(a['late_custody_count'] for a in selected),
                                   unique_delivered_with_late_custody=sum(a['late_custody_count']>0 for a in selected)))
    write_csv('prior_o_source_accounting.csv',prior_accounting)
    write_csv('delivery_drop_history_strata.csv',strata)
    prior_vs_current=[]
    for r in targets:
        o=prior_index[r['seed'],r['source']];p=index['matlab',r['seed'],r['source']]
        prior_vs_current.append(dict(seed=r['seed'],source=r['source'],o_admitted=o['admitted'],p_admitted=p['admitted'],
                                     o_delivered=o['delivered'],p_delivered=p['delivered'],o_unresolved=o['unresolved'],p_unresolved=p['unresolved'],
                                     o_mean_latency_s=o['mean_latency_s'],p_mean_latency_s=p['mean_latency_s'],
                                     native_mean_latency_s=r['native_mean_latency_s']))
    write_csv('prior_o_vs_current_p.csv',prior_vs_current)
    pooled_fixed=[]
    for h in (60,300,600,1200):
        for model in ('native','matlab','matlab_prior_o'):
            pop=prior[131]+prior[132] if model=='matlab_prior_o' else populations[model,131]+populations[model,132]
            r=fixed_age(pop,model,0,0,h)
            r['scheduled_attempts']*=2
            r['not_admitted']=r['scheduled_attempts']-r['admitted']
            r['fraction_of_scheduled']=r['delivered_by_age']/r['scheduled_attempts']
            pooled_fixed.append(r)
    write_csv('pooled_fixed_age_with_prior.csv',pooled_fixed)
    result=dict(schema='csr-terminal6000-independent-accounting-v1',audit_status='PASS',
                cutoff_s=6000,simulations_executed=False,primary_evidence='MATLAB complete raw protocol trace; native archived normalized first-delivery ledger and admission diagnostics',
                native_raw_trace_independently_rebuilt_this_script=False,checks=checks,input_sha256=inputs,
                pooled=pooled,raw_latency_gap_percent=raw_gap,
                pooled_delivery_count_gap_percent=100*(pooled['matlab']['delivered']/native_count-1),
                native_delivery_weighted_matlab_mean_s=weighted,native_delivery_weighted_latency_gap_percent=weighted_gap,
                defined_cells=9,undefined_native_zero_cells=3,both_metrics_within_15=sum(r['both_within_15'] is True for r in targets),
                count_cells_within_15=sum(r['count_within_15'] is True for r in targets),latency_cells_within_15=sum(r['latency_within_15'] is True for r in targets),
                full_network_15_percent_parity=False,
                seed131_native_zero_source_matlab=dict(sources=[2,7,8],admitted=len(extra_apps),delivered=len(extra_delivered),unresolved=len(extra_apps)-len(extra_delivered),mean_latency_s=mean(a['latency_ns']/1e9 for a in extra_delivered)),
                matlab_common_source_only_unweighted_mean_s=mean(common_lat),weighted_gap_contributions=contribution,
                per_seed_details=details,prior_o=previous,prior_o_per_seed_details=prior_details,
                pooled_drop_history_strata=[r for r in strata if r['seed']==0],
                descriptive_decomposition_s=dict(current_raw_minus_native=pooled['matlab']['mean_latency_s']-pooled['native']['mean_latency_s'],
                                                current_native_weighted_minus_native=weighted-pooled['native']['mean_latency_s'],
                                                current_raw_minus_native_weighted=pooled['matlab']['mean_latency_s']-weighted,
                                                prior_raw_minus_native_weighted=prior_total['mean_latency_s']-prior_weighted,
                                                raw_current_minus_prior=pooled['matlab']['mean_latency_s']-prior_total['mean_latency_s'],
                                                weighted_current_minus_prior=weighted-prior_weighted),
                caveats=['Native-zero source cells have undefined relative ratios; they remain reported and block a complete 15% claim.',
                         'All admitted-but-undelivered applications are unresolved. Provisional dropped and pending counters do not prove final loss or all-copy liveness.',
                         'Autonomous engines with equal numeric seed do not share random streams; application IDs are not paired across engines.',
                         'Source standardization changes weights among delivered source/seed populations; it does not remove survivor bias or make admitted populations identical.',
                         'Fixed-age cohorts use [300,6000-horizon), with delivery age <= horizon and scheduled versus admitted denominators kept separate.',
                         'Raw terminal statistics may use a different sample quantile interpolation from CSV summaries; this audit uses linear interpolation at (n-1)*p.'])
    write_csv('source_accounting.csv',accounting)
    write_csv('source_targets.csv',targets)
    write_csv('fixed_age.csv',horizons)
    write_csv('weighted_contributions.csv',contribution)
    write_csv('reconstructed_applications.csv',sum(populations.values(),[]))
    (OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    report=['INDEPENDENT FULL 6000-SECOND ACCOUNTING REVIEW — 2026-09-30',
            '', 'Verdict: valid completed evidence; 15% network parity is NOT met.',
            'Reconstruction: both current and prior MATLAB complete raw protocol traces. Native population: exact issued normalized application ledger and full admission counters. No simulations executed.',
            f'Checks passed: {len(checks)}. Native raw-ledger verification belongs to the separate independent phase review.',
            '', 'POOLED POPULATIONS (BOTH SEEDS)',
            'model | attempted | admitted | delivered | unresolved | delivered mean (s)']
    for label,r in [('native',pooled['native']),('prior O',prior_total),('current P',pooled['matlab'])]:
        report.append(f"{label} | {r['attempted']} | {r['admitted']} | {r['delivered']} | {r['unresolved']} | {r['mean_latency_s']:.9f}")
    report.extend(['',f"Current raw latency gap: +{raw_gap:.6f}%; native-delivery-weighted gap: +{weighted_gap:.6f}% (90.748322181 s vs 64.496589532 s).",
                   f"Prior O raw gap: +{previous['raw_latency_gap_percent']:.6f}%; weighted: +{previous['native_delivery_weighted_latency_gap_percent']:.6f}%.",
                   f"Current delivery count gap: {result['pooled_delivery_count_gap_percent']:.6f}%. Current passed source/seed cells: 4/9 with both count and latency within 15%; prior O: {previous['both_metrics_within_15']}/9.",
                   'Three native-zero cells (seed 131, sources 2/7/8) have undefined relative metrics, and are retained as population mismatches.',
                   '', 'SOURCE MIX',
                   'Seed 131, sources 2/7/8: native admits/delivers zero; current MATLAB admits 1727, delivers 1238, unresolved 489. Their delivered mean is 1016.437590569 s.',
                   'Current MATLAB mean among the nine common nonzero source/seed cells is 82.145921880 s before weighting; native-delivery weights yield 90.748322181 s.',
                   'The raw-minus-standardized component is 40.160377349 s now versus 12.150067289 s previously. Standardized latency improves only 0.534480401 s, while raw latency worsens 27.475829659 s. This is a descriptive weighting identity, not a causal separation.',
                   'Largest positive contributions to the standardized 26.251732649-second gap: seed 132/source 7 +11.626402026 s; seed 131/source 4 +10.193043092 s; seed 132/source 8 +4.012968649 s. Other cells offset some of this total.',
                   '', 'LATE COPIES AND UNFINISHED TRAFFIC',
                   'Reconstructed current status: raw provisional drops 769, raw pending 509, unresolved 1278. All remain unresolved until a final application outcome is proved; no all-copy-live or terminal-loss split is inferred.',
                   'Direct late delivery count 2109 and late custody recovery count 46 exactly match raw event histories and counters.',
                   '2139 delivered apps had any prior provisional app_drop: 9.0177066% of deliveries, mean 268.249503508 s, 18.4784917% of total delivered latency. This includes 2109 direct-late deliveries and 45 apps delivered after a custody recovery, with 15 in both categories. The remaining custody recovery is undelivered at cutoff.',
                   '21581 delivered apps without a prior drop still average 117.296170930 s. Excluding recovered deliveries would change the measured population and would not prove parity; it also would not remove the large difference.',
                   'The prior O and current P histories differ. Do not pair local application IDs or interpret O dropped apps as the same apps later recovered in P.',
                   '', 'FIXED-AGE COHORTS',
                   'Each horizon uses identical generation windows [300,6000-horizon), distinct scheduled and admitted denominators, and delivery age <= horizon. All 112 returned per-case fixed-age rows independently reconstruct.',
                   'horizon | native by-age delivery count | current by-age delivery count | relative delta'])
    for h in (60,300,600,1200):
        n=next(r for r in pooled_fixed if r['model']=='native' and r['horizon_s']==h)
        p=next(r for r in pooled_fixed if r['model']=='matlab' and r['horizon_s']==h)
        report.append(f"{h}s | {n['delivered_by_age']} | {p['delivered_by_age']} | {100*(p['delivered_by_age']/n['delivered_by_age']-1):.4f}%")
    report.extend(['These aggregate timely-delivery counts are supplementary; passing them does not override failed per-source delivered-mean/count targets.',
                   '', 'METHOD LIMITS', *['- '+v for v in result['caveats']],
                   '', 'Reproduce: python terminal6000_return/accounting/audit.py from the workspace root. Exact input hashes are recorded in audit.json. Source tables, cohorts, reconstructed application ledgers, late-copy strata, and O/P comparisons accompany this review.'])
    (OUT/'REVIEW.txt').write_text('\n'.join(report)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','input_sha256','per_seed_details','prior_o_per_seed_details','caveats')},indent=2))


if __name__=='__main__':main()
