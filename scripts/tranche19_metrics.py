#!/usr/bin/env python3
"""T19 descriptive DATA ownership, admission and retry observations.

Original protocol callback order is authoritative. All packet joins are within
one engine. Counters are reconstructed after callbacks, never hidden-queue
polls; retry requests and transmissions deliberately are not a bijection.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from decimal import Decimal, InvalidOperation
import gzip
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, label, minimum=0):
    require(not isinstance(value, bool), f'{label}: Boolean is not an integer')
    if isinstance(value, float):
        require(math.isfinite(value) and abs(value) < 2**53, f'{label}: ambiguous float integer')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f'{label}: invalid integer') from exc
    require(number.is_finite() and number == number.to_integral_value()
            and minimum <= number <= 2**64-1, f'{label}: invalid exact unsigned integer')
    return int(number)


def finite(value, label):
    require(not isinstance(value, bool), f'{label}: Boolean is not numeric')
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{label}: invalid number') from exc
    require(math.isfinite(number), f'{label}: nonfinite number')
    return number


def rows(path, fields=()):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames))
                and set(fields) <= set(reader.fieldnames), f'Invalid CSV schema: {path}')
        for row in reader:
            require(None not in row and None not in row.values(), f'Malformed CSV row: {path}')
            yield row


def entries(value):
    value = [value] if isinstance(value, dict) else value
    require(isinstance(value, list) and all(isinstance(row, dict) for row in value), 'Invalid object array')
    return value


def distribution(values):
    values = sorted(values)
    if not values:
        return {'count': 0, 'minimum_s': None, 'median_s': None, 'mean_s': None, 'maximum_s': None}
    n = len(values)
    return {'count': n, 'minimum_s': values[0], 'median_s': (values[(n-1)//2]+values[n//2])/2,
            'mean_s': math.fsum(values)/n, 'maximum_s': values[-1]}


def bucket(when, horizon, width):
    require(0 <= when <= horizon and horizon > 0 and width > 0 and horizon % width == 0,
            'Invalid finite-stop bucket boundary')
    return min(int(when//width), int(horizon/width)-1)


def applications(directory, horizon):
    result = {}
    for row in rows(Path(directory)/'analysis/applications.csv', ('PacketId','SourceId','DestinationId',
            'ApplicationBytes','GeneratedSeconds','LastEventSeconds','ReceivedSeconds','LatencySeconds','Outcome','DropReason')):
        packet = integer(row['PacketId'], 'application identity', 1)
        require(packet not in result, 'Duplicate application identity')
        generated = finite(row['GeneratedSeconds'], 'generated')
        last = finite(row['LastEventSeconds'], 'last event')
        require(0 <= generated < horizon and generated <= last <= horizon, 'Application time outside finite stop')
        outcome = row['Outcome']
        require(outcome in ('pending','delivered','dropped'), 'Unknown application outcome')
        app = {'packet_id': packet, 'source': integer(row['SourceId'],'source'),
               'destination': integer(row['DestinationId'],'destination'), 'generated_s': generated,
               'last_event_s': last, 'outcome': outcome, 'drop_reason': row['DropReason'],
               'application_bytes':integer(row['ApplicationBytes'],'application bytes')}
        if outcome == 'delivered':
            received = finite(row['ReceivedSeconds'],'received')
            delay = finite(row['LatencySeconds'],'latency')
            require(generated <= received <= horizon and math.isclose(received-generated,delay,
                    rel_tol=2e-12,abs_tol=1e-9), 'Invalid application delivery latency')
            app.update(received_s=received, delay_s=delay)
        else:
            require(row['ReceivedSeconds'].lower() in ('','nan') and row['LatencySeconds'].lower() in ('','nan'),
                    'Undelivered application has delivery timing')
        require(outcome != 'dropped' or bool(row['DropReason']), 'Dropped application lacks reason')
        result[packet] = app
    return result


def _attempt_bins(flow, horizon, width):
    """Exact schedule counts, without reconstructing absent blocked reasons."""
    start = Decimal(str(flow['StartSeconds']))
    step = Decimal(str(flow['IntervalSeconds']))
    count = integer(flow['PacketCount'],'scheduled packet count')
    require(start >= 0 and step > 0, 'Invalid traffic schedule')
    result = []
    for index in range(int(horizon/width)):
        left, right = Decimal(str(index*width)), Decimal(str((index+1)*width))
        a = max(0, int(((left-start)/step).to_integral_value(rounding='ROUND_CEILING')))
        b = max(0, int(((right-start)/step).to_integral_value(rounding='ROUND_CEILING')))
        result.append(max(0,min(count,b)-min(count,a)))
    return result


def _occupancy_integral(changes, horizon, width):
    """Post-callback state integration; callbacks at H change endpoint only."""
    integrals = [0.0]*int(horizon/width)
    peaks = [0]*len(integrals)
    endpoints = [0]*len(integrals)
    previous, current = 0.0, 0
    for when, value in [*changes, (horizon, None)]:
        require(previous <= when <= horizon, 'Ownership changes out of order')
        cursor = previous
        while cursor < when:
            index = bucket(cursor,horizon,width)
            end = min(when,(index+1)*width)
            integrals[index] += current*(end-cursor)
            peaks[index] = max(peaks[index],current)
            endpoints[index] = current
            cursor = end
        if value is not None:
            current = value
            peaks[bucket(when,horizon,width)] = max(peaks[bucket(when,horizon,width)],current)
            endpoints[bucket(when,horizon,width)] = current
        previous = when
    endpoints[-1] = current
    return [{'start_s': i*width, 'end_s': (i+1)*width, 'mean_count':integrals[i]/width,
             'peak_count':peaks[i], 'end_count':endpoints[i]} for i in range(len(integrals))]


def analyze_case(directory, case, *, bin_width_s=300):
    directory = Path(directory)
    horizon = finite(case['duration_s'],'duration')
    width = finite(bin_width_s,'bin width')
    config = json.loads((directory/'raw/summary.json').read_text(encoding='utf-8-sig'))['Config']
    apps = applications(directory,horizon)
    configured_nodes = {integer(row['Id'],'node') for row in entries(config['Nodes'])}
    traffic = entries(config['Traffic'])
    sources = [integer(row['SourceId'],'flow source') for row in traffic]
    require(len(sources) == len(set(sources)), 'Expected distinct campus flow source identities')
    flow_bins = {(source,i):Counter() for source in sources for i in range(int(horizon/width))}
    for flow in traffic:
        source = integer(flow['SourceId'],'flow source')
        for index,count in enumerate(_attempt_bins(flow,horizon,width)):
            flow_bins[source,index]['attempts'] = count
    for app in apps.values():
        require(app['source'] in sources, 'Unconfigured application source')
        flow_bins[app['source'],bucket(app['generated_s'],horizon,width)]['admitted'] += 1
    # Admission reasons are complete only in whole-run counters, not in bins.
    admission = {}
    for row in rows(directory/'raw/application_admission_statistics.csv', ('SourceId','Attempts','Admitted')):
        source = integer(row['SourceId'],'admission source')
        require(source in sources and source not in admission, 'Duplicate/unknown admission source')
        values = {key:integer(value,key) for key,value in row.items() if key in ('Attempts','Admitted') or key.startswith('Blocked')}
        require(values['Attempts'] == values['Admitted']+sum(v for k,v in values.items() if k.startswith('Blocked')),
                'Admission outcomes do not partition attempts')
        require(values['Attempts'] == sum(flow_bins[source,i]['attempts'] for i in range(int(horizon/width)))
                and values['Admitted'] == sum(a['source'] == source for a in apps.values()), 'Per-flow admission counts disagree')
        admission[source] = values
    require(set(admission) == set(sources), 'Missing admission source')
    hop_active, nwk_active, episodes, custody = {}, {}, [], []
    hop_count, nwk_count, dack_count = Counter(), Counter(), Counter()
    hop_changes, nwk_changes = defaultdict(list), defaultdict(list)
    hop_cohort_changes, nwk_cohort_changes = defaultdict(list), defaultdict(list)
    hop_cohort_count, nwk_cohort_count = Counter(), Counter()
    event_counts, hop_link_counts = Counter(), Counter()
    state, app_events, tx_at = {}, [], set()
    previous = -1.0
    terminals = {'hop_ack','hop_failed','hop_dack_expired'}
    hop_events = {'hop_admit','hop_sent','hop_retry','hop_dack',*terminals}
    for ordinal,row in enumerate(rows(directory/'raw/protocol_trace.csv', ('TimeSeconds','Event','NodeId','PeerId',
            'PacketId','FrameKind','Sequence','ApplicationBytes')),1):
        when = finite(row['TimeSeconds'],'callback time')
        require(previous <= when <= horizon and when >= 0, 'Protocol callbacks out of order/horizon')
        previous = when
        event,node = row['Event'],integer(row['NodeId'],'callback node')
        require(node in configured_nodes, 'Protocol callback has unknown node')
        if event == 'tx_start':
            require((node,when) not in tx_at, 'Ambiguous simultaneous same-node TX')
            tx_at.add((node,when))
        if event not in hop_events | {'network_enqueue','network_custody_release','network_submit',
                'app_generate','app_receive','app_drop','relay_accept'}:
            continue
        if row['FrameKind'] not in ('APP','DATA'):
            continue
        packet = integer(row['PacketId'],'DATA application identity',1)
        require(packet in apps, 'Unknown DATA application identity')
        app = apps[packet]; source = app['source']; peer = integer(row['PeerId'],'peer')
        require(when+1e-9 >= app['generated_s'], 'Application callback before generation')
        cohort = (node,source)
        event_counts[node,source,event] += 1
        observation = {'row':ordinal,'time_s':when,'event':event}
        if event.startswith('app_') or event == 'relay_accept':
            require(integer(row['ApplicationBytes'],'callback payload') == app['application_bytes'],
                    'Application payload changed across callback')
            before = state.get(packet)
            if event == 'app_generate':
                require(before is None and node == source and when == app['generated_s'], 'Ambiguous app generation')
                after = 'pending'
            else:
                require(before is not None, 'Application outcome precedes generation')
                if event == 'app_receive':
                    require(before != 'delivered' and node == app['destination'] and app['outcome'] == 'delivered'
                            and math.isclose(when,app['received_s'],rel_tol=0,abs_tol=1e-9),
                            'Duplicate/inconsistent application delivery endpoint or time')
                require(not (before == 'delivered' and event == 'app_drop'), 'Delivered app dropped again')
                after = before if before == 'delivered' else {'app_receive':'delivered','app_drop':'dropped','relay_accept':'pending'}[event]
            state[packet] = after
            if before != after:
                app_events.append((when,source,before,after))
                if after in ('delivered','dropped'):
                    flow_bins[source,bucket(when,horizon,width)][after+'_events'] += 1
            continue
        if event == 'network_enqueue':
            key = node,packet
            require(key not in nwk_active, 'Duplicate NWK custody acquisition')
            entry = {'node':node,'source':source,'packet_id':packet,'enqueue':observation,'submit':None,'release':None}
            nwk_active[key] = entry; custody.append(entry)
            nwk_count[node] += 1; nwk_cohort_count[cohort] += 1
            nwk_changes[node].append((when,nwk_count[node])); nwk_cohort_changes[cohort].append((when,nwk_cohort_count[cohort]))
        elif event == 'network_submit':
            require((node,packet) in nwk_active, 'NWK submit without custody')
            entry = nwk_active[node,packet]
            # A retried route handoff is retained as an event list if repeated.
            entry.setdefault('submissions',[]).append(observation)
            if entry['submit'] is None: entry['submit'] = observation
        elif event == 'network_custody_release':
            require((node,packet) in nwk_active, 'NWK release without acquired custody')
            entry = nwk_active.pop((node,packet)); entry['release'] = observation
            nwk_count[node] -= 1; nwk_cohort_count[cohort] -= 1
            require(nwk_count[node] >= 0 and nwk_cohort_count[cohort] >= 0, 'Negative NWK ownership')
            nwk_changes[node].append((when,nwk_count[node])); nwk_cohort_changes[cohort].append((when,nwk_cohort_count[cohort]))
        elif event in hop_events:
            require(row['FrameKind'] == 'DATA', 'HOP DATA lifecycle has wrong namespace')
            sequence = integer(row['Sequence'],'hop sequence')
            key = node,peer,packet,sequence
            hop_link_counts[node,peer,event] += 1
            if event == 'hop_admit':
                require(key not in hop_active, 'Duplicate HOP capacity acquisition')
                entry = {'node':node,'peer':peer,'source':source,'packet_id':packet,'sequence':sequence,
                         'admit':observation,'release':None,'dack':None,'transmissions':[],'retry_requests':[],'events':[]}
                hop_active[key] = entry; episodes.append(entry)
                hop_count[node] += 1; hop_cohort_count[cohort] += 1
                hop_changes[node].append((when,hop_count[node])); hop_cohort_changes[cohort].append((when,hop_cohort_count[cohort]))
            else:
                require(key in hop_active, 'HOP callback has no acquired DATA capacity')
                entry = hop_active[key]
            entry['events'].append(observation)
            if event == 'hop_sent':
                require(entry['dack'] is None, 'Actual HOP sent while DACK capacity hold is active')
                entry['transmissions'].append(observation)
            elif event == 'hop_retry':
                require(entry['dack'] is None, 'Retry request during DACK hold')
                entry['retry_requests'].append(observation)
            elif event == 'hop_dack':
                require(entry['dack'] is None, 'Duplicate DACK capacity hold')
                entry['dack'] = observation; dack_count[node] += 1
            elif event in terminals:
                require((event == 'hop_dack_expired') == (entry['dack'] is not None), 'DACK hold/release mismatch')
                entry['release'] = observation
                hop_active.pop(key); hop_count[node] -= 1; hop_cohort_count[cohort] -= 1
                if event == 'hop_dack_expired': dack_count[node] -= 1
                require(hop_count[node] >= 0 and hop_cohort_count[cohort] >= 0 and dack_count[node] >= 0, 'Negative HOP ownership')
                hop_changes[node].append((when,hop_count[node])); hop_cohort_changes[cohort].append((when,hop_cohort_count[cohort]))
    require(set(state) == set(apps) and all(state[p] == app['outcome'] for p,app in apps.items()), 'Application protocol terminal states disagree')
    # HOP onTx callbacks may precede tx_start export at the same time: join after full pass.
    for entry in episodes:
        require(all((entry['node'],tx['time_s']) in tx_at for tx in entry['transmissions']), 'HOP sent has no same-node physical TX')
        terminal = entry['dack'] or entry['release']
        entry['retry_request_waits'] = []
        for request in entry['retry_requests']:
            next_tx = next((tx for tx in entry['transmissions'] if tx['row'] > request['row']
                           and (terminal is None or tx['row'] < terminal['row'])),None)
            end = next_tx or terminal
            finish = end['time_s'] if end else horizon
            require(finish >= request['time_s'], 'Negative retry service observation')
            entry['retry_request_waits'].append({'request_row':request['row'],'request_s':request['time_s'],
                'end_row':end['row'] if end else None,'end_s':finish,'seconds':finish-request['time_s'],
                'completion':'next_observed_hop_sent' if next_tx else 'terminal_before_next_hop_sent' if terminal else 'censored_at_stop'})
        entry['capacity_retention_s'] = (entry['release']['time_s'] if entry['release'] else horizon)-entry['admit']['time_s']
        entry['capacity_right_censored'] = entry['release'] is None
        if entry['dack']:
            entry['dack_capacity_hold_s'] = (entry['release']['time_s'] if entry['release'] else horizon)-entry['dack']['time_s']
    hop_rows = {integer(r['NodeId'],'node'):r for r in rows(directory/'raw/hop_nodes.csv',('NodeId','PendingData','DackHoldCount','Admitted','Transmitted','Retransmissions','Acknowledged','Dacked','Failed','DackExpired'))}
    nwk_rows = {integer(r['NodeId'],'node'):r for r in rows(directory/'raw/nwk_nodes.csv',('NodeId','PendingCustody'))}
    require(set(hop_rows) == configured_nodes == set(nwk_rows),'Missing ownership endpoint node')
    transmission_coverage = []
    for node in configured_nodes:
        h = hop_rows[node]
        require(hop_count[node] == integer(h['PendingData'],'pending DATA') and dack_count[node] == integer(h['DackHoldCount'],'DACK holds')
                and nwk_count[node] == integer(nwk_rows[node]['PendingCustody'],'pending custody'), 'Reconstructed ownership endpoint disagrees')
        observed_sent = sum(count for (n,_,e),count in event_counts.items() if n == node and e == 'hop_sent')
        total_sent = integer(h['Transmitted'],'Transmitted')
        require(observed_sent <= total_sent, 'More observed HOP confirmations than DATA sent indications')
        transmission_coverage.append({'node':node,'data_sent_indications':total_sent,
            'observed_owned_hop_sent_callbacks':observed_sent,
            'sent_indications_without_owned_confirmation':total_sent-observed_sent})
        for event,field in {'hop_admit':'Admitted','hop_retry':'Retransmissions',
                'hop_ack':'Acknowledged','hop_dack':'Dacked','hop_failed':'Failed','hop_dack_expired':'DackExpired'}.items():
            require(sum(count for (n,_,e),count in event_counts.items() if n == node and e == event) == integer(h[field],field),
                    'HOP event/counter mismatch: '+field)
    # Dynamic pending population includes reinstatement after relay_accept.
    populations = {source:Counter() for source in sources}
    event_index = 0
    timeline = []
    for index in range(int(horizon/width)):
        end = (index+1)*width
        while event_index < len(app_events) and (app_events[event_index][0] < end or end == horizon and app_events[event_index][0] <= end):
            _,source,before,after = app_events[event_index]
            if before: populations[source][before] -= 1
            populations[source][after] += 1
            require(all(v >= 0 for v in populations[source].values()), 'Negative per-source application population')
            event_index += 1
        for source in sources:
            b = flow_bins[source,index]
            require(b['attempts'] >= b['admitted'], 'More admitted applications than attempts in bin')
            timeline.append({'source':source,'start_s':index*width,'end_s':end,'attempts':b['attempts'],
                'admitted':b['admitted'],'blocked':b['attempts']-b['admitted'],'delivery_events':b['delivered_events'],
                'drop_events':b['dropped_events'],'delivered_at_end':populations[source]['delivered'],
                'dropped_at_end':populations[source]['dropped'],'pending_at_end':populations[source]['pending']})
    flows = []
    for source in sources:
        population = [a for a in apps.values() if a['source'] == source]
        outcomes = Counter(a['outcome'] for a in population)
        flows.append({'source':source,'attempts':admission[source]['Attempts'],'admitted':len(population),
            'blocked':admission[source]['Attempts']-len(population),'delivered':outcomes['delivered'],
            'dropped':outcomes['dropped'],'pending':outcomes['pending'],'blocked_reason_totals':
            {k:v for k,v in admission[source].items() if k.startswith('Blocked')},
            'delivered_latency':distribution([a['delay_s'] for a in population if a['outcome']=='delivered'])})
    ownership = []
    for node in sorted(configured_nodes):
        ownership.append({'node':node,'hop_pending_at_stop':hop_count[node],'dack_holds_at_stop':dack_count[node],
            'nwk_custody_at_stop':nwk_count[node], 'hop_data_capacity_300s':_occupancy_integral(hop_changes[node],horizon,width),
            'nwk_custody_300s':_occupancy_integral(nwk_changes[node],horizon,width),
            'source_cohorts':[{'source':source,'local_at_node':source==node,
                'hop_pending_at_stop':hop_cohort_count[node,source],'nwk_custody_at_stop':nwk_cohort_count[node,source],
                'hop_data_capacity_300s':_occupancy_integral(hop_cohort_changes[node,source],horizon,width),
                'nwk_custody_300s':_occupancy_integral(nwk_cohort_changes[node,source],horizon,width)} for source in sources]})
    link = [e for e in episodes if (e['node'],e['peer']) == (4,5)]
    waits = [w for e in link for w in e['retry_request_waits']]
    result = {'schema':'csr-tranche19-ownership-metrics-v1','case_id':case['case_id'],'policy':case['policy'],
        'duration_s':horizon,'bin_width_s':width,'flows':flows,'flow_timeline':timeline,'ownership':ownership,
        'totals':{key:sum(f[key] for f in flows) for key in ('attempts','admitted','blocked','delivered','dropped','pending')},
        'hop_4_to_5':{'episodes':len(link),'retry_requests':sum(len(e['retry_requests']) for e in link),
            'hop_sent_callbacks':sum(len(e['transmissions']) for e in link),
            'capacity_release_events':dict(Counter(e['release']['event'] for e in link if e['release'])),
            'retry_request_next_sent_waits':distribution([w['seconds'] for w in waits if w['completion']=='next_observed_hop_sent']),
            'retry_request_completion_counts':dict(Counter(w['completion'] for w in waits)),
            'pending_capacity_at_stop':sum(e['release'] is None for e in link)},
        'hop_episodes':episodes,'nwk_custody_episodes':custody,'data_transmission_callback_coverage':transmission_coverage,
        'limitations':['Ownership is reconstructed after exported callbacks; no hidden queue polling or instantaneous free-capacity claim.',
            'DACK ends retry service but holds HOP DATA capacity until hop_dack_expired; NWK custody may release earlier.',
            'Each retry request is retained separately. Next observed hop_sent is descriptive; overlapping requests may share it and are not uniquely assigned to an actual queued retry.',
            'hop_sent denotes an exported owned HOP confirmation callback at actual radio TX time. DATA Transmitted counts unmatched sent indications too; the exact per-node remainder is reported without packet/link attribution because the original trace does not expose those aggregate member identities or resend count.',
            'All 300-second attempts are reconstructed from exact configured schedules and validated complete per-flow counters. Per-bin blocked totals are attempts minus admitted; omitted blocked-reason timing is never inferred.',
            'Bins are [start,end), final bin includes callbacks at H. Drop events may later be superseded by relay_accept; endpoint populations use callback order.',
            'Single-seed descriptive policy intervention; subsequent event/RNG consumption can diverge. No cross-engine packet identity joins.']}
    json.dumps(result,allow_nan=False)
    return result


def native_applications(directory, duration_s=6000, bin_width_s=300):
    """Native application-only comparison with native's own source/sequence key."""
    directory = Path(directory); sent, delivered, bins = {}, {}, defaultdict(Counter)
    previous = -1.0
    with gzip.open(directory/'ns3-trace.csv.gz','rt',encoding='utf-8-sig',newline='') as stream:
        reader = csv.DictReader(stream,strict=True)
        for row in reader:
            when = finite(row['time_s'],'native event time')
            require(previous <= when <= duration_s and when >= 0,'Native event outside ordered window')
            previous = when
            if row['event'] not in ('app_send','nwk_delivery'): continue
            source = integer(row['src'],'native app source')
            key = source,integer(row['sequence'],'native app sequence')
            if row['event'] == 'app_send':
                require(key not in sent and when < duration_s,'Duplicate native app generation')
                sent[key] = when; bins[source,bucket(when,duration_s,bin_width_s)]['admitted'] += 1
            else:
                require(key in sent and key not in delivered and when >= sent[key],'Unknown/duplicate native delivery')
                delivered[key] = when; bins[source,bucket(when,duration_s,bin_width_s)]['delivered'] += 1
    flows = []
    for row in rows(directory/'app-admission-diagnostics.csv',('source','attempts','admitted')):
        source = integer(row['source'],'native flow source')
        admitted = sum(k[0] == source for k in sent); received = sum(k[0] == source for k in delivered)
        require(admitted == integer(row['admitted'],'native admitted'),'Native admission/trace count mismatch')
        attempts = integer(row['attempts'],'native attempts')
        require(attempts >= admitted,'Native attempts below admissions')
        flows.append({'source':source,'attempts':attempts,'admitted':admitted,'blocked':attempts-admitted,
            'delivered':received,'unmatched_sends':admitted-received})
    require(len(flows) == len({f['source'] for f in flows}) and {k[0] for k in sent} <= {f['source'] for f in flows},'Native flow identities mismatch')
    return {'schema':'csr-tranche19-native-app-metrics-v1','flows':flows,
        'totals':{key:sum(f[key] for f in flows) for key in ('attempts','admitted','blocked','delivered','unmatched_sends')},
        'flow_timeline':[{'source':f['source'],'start_s':i*bin_width_s,'end_s':(i+1)*bin_width_s,
            'admitted':bins[f['source'],i]['admitted'],'delivered':bins[f['source'],i]['delivered']}
            for f in flows for i in range(int(duration_s/bin_width_s))],
        'scope':'Native source/sequence identities only. Unmatched sends do not distinguish drops from pending ownership.'}


def compare_cases(default, experimental, native, band_percent=5.0):
    require(band_percent >= 0 and math.isfinite(band_percent),'Invalid descriptive band')
    result = []
    maps = [{row['source']:row for row in item['flows']} for item in (default,experimental,native)]
    require(set(maps[0]) == set(maps[1]) == set(maps[2]), 'Compared source populations differ')
    for source in [None,*sorted(maps[0])]:
        a,p,n = [item['totals'] for item in (default,experimental,native)] if source is None else [m[source] for m in maps]
        for metric in ('admitted','delivered'):
            def residual(value):
                return 100*(value-n[metric])/n[metric] if n[metric] else None
            ra,rp = residual(a[metric]),residual(p[metric])
            result.append({'source':source,'metric':metric,'actual_tx':a[metric],'native_provisional':p[metric],
                'ns3':n[metric],'policy_delta':p[metric]-a[metric],'actual_tx_vs_ns3_percent':ra,
                'native_provisional_vs_ns3_percent':rp,'actual_tx_within_descriptive_band':abs(ra)<=band_percent if ra is not None else None,
                'native_provisional_within_descriptive_band':abs(rp)<=band_percent if rp is not None else None})
    return {'schema':'csr-tranche19-descriptive-comparison-v1','band_percent':band_percent,
        'band_is_acceptance_gate':False,'numerical_parity_established':False,'rows':result,
        'scope':'One seed, full original campus. A 5% band is a descriptive engineering target, not statistical equivalence or proof of a model improvement.'}
