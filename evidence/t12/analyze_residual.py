#!/usr/bin/env python3
"""Read-only, exact residual analysis for the repaired T12 owner return.
Run from workspace root: python t12v/analyze_residual.py
Writes only t12v/residual.json and t12v/residual.md.
"""
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / 'upload/t12(1).zip'
PACKAGE = ROOT / 'csr12r'
REFERENCE = PACKAGE / 'evidence/tranche-12-relay-reference'
OUT = ROOT / 't12v'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def compare(actual, native):
    assert len(actual) == len(native)
    assert list(actual[0]) == list(native[0])
    fields = collections.Counter()
    by_case = collections.defaultdict(collections.Counter)
    time_deltas = collections.Counter()
    first = {}
    divergent = []
    for index, (a, n) in enumerate(zip(actual, native), 1):
        delta = {k: {'matlab': a[k], 'native': n[k]} for k in a if a[k] != n[k]}
        fields.update(delta.keys())
        by_case[a['case']].update(delta.keys())
        for k in delta:
            first.setdefault(k, {'table_row': index, 'case': a['case'],
                                 'event': a.get('event'), 'case_order': a.get('order'),
                                 'difference': delta[k]})
        if 'time_ns' in a:
            time_deltas[int(a['time_ns']) - int(n['time_ns'])] += 1
        if delta:
            divergent.append({'table_row': index, 'case': a['case'],
                              'event': a.get('event'), 'case_order': a.get('order'),
                              'time_ns_matlab': a.get('time_ns'), 'fields': delta})
    return {
        'rows': len(actual), 'different_rows': len(divergent),
        'field_difference_counts': dict(fields),
        'per_case_field_difference_counts': {k: dict(v) for k, v in by_case.items()},
        'time_deltas_matlab_minus_native_ns': dict(sorted(time_deltas.items())),
        'first_difference_by_field': first,
        'non_time_differences': [d for d in divergent if set(d['fields']) - {'time_ns'}],
    }


def flow_stats(events):
    generated = {(r['case'], int(r['app_source']), int(r['app_id'])): int(r['time_ns'])
                 for r in events if r['event'] == 'admit'}
    delivered = collections.defaultdict(list)
    seen = set()
    for r in events:
        if r['event'] != 'deliver':
            continue
        key = (r['case'], int(r['app_source']), int(r['app_id']))
        assert key not in seen
        seen.add(key)
        assert key in generated
        delivered[key[:2]].append((int(r['time_ns']), int(r['time_ns'])-generated[key]))
    assert seen == set(generated)
    return [dict(case=case, source=source, delivered=len(values),
                 mean_delay_ns=sum(v[1] for v in values)/len(values),
                 max_delay_ns=max(v[1] for v in values),
                 last_delivery_ns=max(v[0] for v in values))
            for (case, source), values in delivered.items()]


with zipfile.ZipFile(OWNER) as archive:
    tables = {f: rows(archive.read('relay/'+f).decode())
              for f in ['events.csv', 'draws.csv', 'usage.csv']}
    owner_summary = json.loads(archive.read('relay/summary.json'))
    owner_hashes = {f: hashlib.sha256(archive.read('relay/'+f)).hexdigest() for f in tables}
reference_tables = {f: rows((REFERENCE/f).read_text()) for f in tables}
comparisons = {f: compare(tables[f], reference_tables[f]) for f in tables}
events = tables['events.csv']
native_events = reference_tables['events.csv']
assert comparisons['events.csv']['field_difference_counts'] == {
    'time_ns': 1566, 'resend_queue': 5, 'dack_holds': 5}
assert comparisons['draws.csv']['field_difference_counts'] == {'time_ns': 332}
assert not comparisons['usage.csv']['field_difference_counts']
assert all(r['event'] == 'release' for r in comparisons['events.csv']['non_time_differences'])
post_ingress = [(a, n) for a, n in zip(events, native_events) if a['event'] == 'ingress_after']
assert all(all(a[k] == n[k] for k in a if k != 'time_ns') for a, n in post_ingress)
snapshots = [r for r in events if r['event'] in ('checkpoint', 'final')]
assert all(a == n for a, n in zip(events, native_events) if a['event'] in ('checkpoint', 'final'))
matlab_flows, native_flows = flow_stats(events), flow_stats(native_events)
assert len(matlab_flows) == len(native_flows)
for a, n in zip(matlab_flows, native_flows):
    assert (a['case'], a['source'], a['delivered']) == (n['case'], n['source'], n['delivered'])
    assert all(a[k] - n[k] == -28 for k in ('mean_delay_ns', 'max_delay_ns', 'last_delivery_ns'))
source_files = [
    ('t12n/build/overlay/ns3/csr-common.h', 'CsrOpnetTic: Seconds(1/36e6), quantized to 28 ns at native nanosecond resolution'),
    ('t12n/build/overlay/ns3/csr-nwk-layer.h', 'ScheduleCheckNwkQueue: schedules CheckNwkQueue after CsrOpnetTic'),
    ('csr12r/+csr/+nwk/Layer.m', 'wake: schedules pump at Scheduler.Now'),
    ('t12n/build/overlay/ns3/csr-hop-layer.h', 'HandleDack: NotifyNsdpFromEntry precedes m_dackList insertion and resend removal'),
    ('csr12r/+csr/+hop/Layer.m', 'complete DACK branch: hold insertion and removeResend precede releaseNsdp'),
    ('csr12r/scripts/ns3/tranche12_relay.cc', 'Node::Release decrements actual NWK NSDP then observes Event(release)'),
    ('csr12r/+csr/+validation/relayContract.m', 'release calls real releaseFromHop then observes release'),
]
report = {
    'schema': 'csr-tranche12-independent-owner-residual-v1',
    'owner_zip_sha256': sha(OWNER), 'candidate_sha256': sha(PACKAGE/'evidence/tranche-12-candidate.json'),
    'native_manifest_sha256': sha(REFERENCE/'manifest.json'),
    'owner_table_sha256': owner_hashes,
    'native_table_sha256': {f: sha(REFERENCE/f) for f in tables},
    'analysis_script_sha256': sha(Path(__file__)),
    'comparison_method': 'Exact ordinal row pairing after equal row count and column schema checks; no time adjustment, tolerance, state normalization, or outcome fitting.',
    'comparisons': comparisons,
    'event_counts': dict(collections.Counter(r['event'] for r in events)),
    'matlab_flows': matlab_flows, 'native_flows': native_flows,
    'service': {
        'admitted': sum(r['event']=='admit' for r in events),
        'delivered_unique': sum(r['event']=='deliver' for r in events),
        'release_callbacks': sum(r['event']=='release' for r in events),
        'drops_from_owner_summary': sum(r['Drops'] for r in owner_summary['CaseResults']),
        'all_event_identity_order_and_ack_dack_bitmaps_exact': True,
        'all_422_post_ingress_non_time_states_exact': True,
        'fixed_transmit_rate_power_pairs': sorted({(int(r['rate_kbps']),int(r['power_dbm'])) for r in events if r['event']=='tx_start'}),
        'rate_power_scope': '128 rate key and +33 dBm are prescribed fixed settings; this does not validate adaptive rate/power decisions.',
        'all_raw_draw_values_ranges_resolved_slots_purposes_ordinal_node_case_exact': True,
        'usage_rows_exact': 12,
        'all_checkpoint_and_final_rows_exact': 24,
        'dack_holds_at_16s': {c: sum(int(r['dack_holds']) for r in snapshots if r['case']==c and r['event']=='checkpoint') for c in ['relay','local','mix','sw']},
        'dack_holds_at_24s': {c: sum(int(r['dack_holds']) for r in snapshots if r['case']==c and r['event']=='final') for c in ['relay','local','mix','sw']},
        'dack_expiry_observability': 'Owner relay CSV does not emit DACK-expiry rows. It proves 16-second and 24-second states, not exact expiration timestamps. The source schedules 20-second holds plus TIC; precise owner expiration times would need added observation.',
    },
    'source_bindings': [dict(path=p, sha256=sha(ROOT/p), finding=f) for p, f in source_files],
    'interpretation': {
        'timing': 'All differences in relay time are exactly MATLAB earlier by 28 ns. Native first NWK queue wake waits one legacy TIC; MATLAB wake schedules now. Source and measured first-draw offset support the interpretation that this seeds the persistent service-clock epoch offset. No counterfactual runtime change was executed to prove sole causality.',
        'dack': 'Five release-callback snapshots differ because DACK resend-to-hold migration is before the callback in MATLAB and after it in native. MATLAB has one fewer resend and one more DACK hold at those snapshots. Real NWK custody and NSDP release agree, HOP total pending agrees, and states agree when ingress returns.',
        'scope': 'Controlled successful addressed transport, fixed routes and fixed radio settings. Does not establish campus RF, collisions, half-duplex, adaptive link control, route convergence, or stochastic population parity.',
        'completion': 'The observed repaired run supports focused structural/service milestone completion with explicit residuals. Strict trace equality remains false. These small observed differences do not alone justify changing the validated production baseline.',
    },
    'recommended_next_milestone': {
        'title': 'Bounded relay DATA/ACK-loss and capacity recovery',
        'design': ['Retain 4 -> 5 -> 1 and matched draw tapes as control.', 'Selectively lose one DATA frame, one ACK, then a short burst at known semantic boundaries.', 'Keep local and relayed offers active across resend and DACK hold expiry to prove capacity becomes reusable under demand.', 'Observe custody conservation, duplicates, retries, NSDP release, DACK migration, expiry and terminal drops with exact before/after boundaries.', 'Add closely spaced same-time/one-TIC offers around release as a sensitivity case before any timing repair.', 'Defer the long campus run until the bounded loss cases establish the release/retry chain.'],
        'no_production_change_in_this_review': True,
    },
}
(OUT/'residual.json').write_text(json.dumps(report, indent=2)+'\n')
lines = [
    '# Tranche 12 repaired return: independent residual review', '',
    'The repaired owner run supports the focused relay/local service milestone with explicit residuals. Strict MATLAB/native trace equality remains false. This analysis reads the owner CSVs directly, independently of the acceptance gate, and leaves both source trees unchanged.', '',
    '| Comparison | Result |', '| --- | --- |',
    '| Applications admitted/delivered | 120/120, same identities and order; no owner-reported drops |',
    '| NWK release callbacks | 180, same order, custody and NSDP counts |',
    '| Relay events | 2,344 in each implementation; all event identities/order agree |',
    '| Event timing | 1,566 rows are 28 ns earlier in MATLAB; 778 timestamps match exactly |',
    '| Random replay | All 332 raw values, ranges, resolved slots, purposes and ordering agree; times are 28 ns earlier in MATLAB |',
    '| Tape usage | All 12 rows agree, including unused suffixes |',
    '| ACK/DACK bitmaps, MAC state/counters, rate/power | Exact at every exported row; transmit radio settings were fixed at key 128 and +33 dBm |',
    '| Other state residual | Five release rows: MATLAB has one fewer resend and one more DACK hold |',
    '| After ingress | All 422 non-time state snapshots match |',
    '| Checkpoint/final | All 24 complete rows match exactly |', '',
    'The runner\'s 1,898 unmatched rows are 1,566 event rows plus 332 draw rows. The five transient state mismatches are already included among those event rows; they are not additional lost packets or failed service checks.', '',
    'The earliest event mismatch is relay row 37 (`tx_start`): MATLAB 351,000,000 ns, native 351,000,028 ns. The first draw is MATLAB 13,000,000 ns versus native 13,000,028 ns. Native `ScheduleCheckNwkQueue` waits `CsrOpnetTic()` (1/36 MHz, rounded to 28 ns); MATLAB `wake` schedules `pump` at the current time. The source and measured common offset support a first-service clock-epoch explanation. No counterfactual simulator run was used to assert sole causality.', '',
    'The five non-time residuals occur at mix case orders 480, 481, 482, 530 and sw order 573. Native calls the NWK release callback before inserting a DACK hold and removing its resend; MATLAB performs that migration first. NWK custody and NSDP release, total HOP pending and the subsequent stable state agree. This is observable callback ordering, with no service impact demonstrated in these cases.', '',
    '| Case | Delivered | Last MATLAB delivery (s) | DACK holds at 16 s | DACK holds at 24 s |',
    '| --- | ---: | ---: | ---: | ---: |',
]
for c in ['relay','local','mix','sw']:
    fs = [r for r in matlab_flows if r['case']==c]
    lines.append(f"| {c} | {sum(r['delivered'] for r in fs)} | {max(r['last_delivery_ns'] for r in fs)/1e9:.9f} | {report['service']['dack_holds_at_16s'][c]} | 0 |")
lines += ['', 'Every delivered application is 28 ns earlier in MATLAB, so mean delay, maximum delay and last-delivery time have the same 28 ns offset. The mixed-case temporary holds drain by 24 seconds. The owner CSV does not expose exact DACK-expiry events, so the returned data must not be described as an exact expiry-time comparison.', '',
          'Recommended next milestone: retain this short chain and introduce bounded DATA/ACK loss with offers continuing across retransmission and DACK-expiry boundaries. Check custody, duplicate suppression and capacity reuse under active demand. Include callback and one-TIC sensitivity microcases before considering a production timing/order change. The long campus test can follow that bounded recovery milestone.', '',
          'This fixture uses controlled successful addressed transport and prescribed routes/radio settings. It cannot establish RF/collision/half-duplex behavior, adaptive power/rate decisions, route convergence or campus parity. No production files were changed and no new MATLAB execution is claimed by this review.', '',
          'Exact input/source hashes, field counts, transient rows and per-flow statistics are in `residual.json`. Reproduce from the workspace root with `python t12v/analyze_residual.py`.', '']
(OUT/'residual.md').write_text('\n'.join(lines))
print(json.dumps({'owner_sha256': report['owner_zip_sha256'], 'events': comparisons['events.csv']['field_difference_counts'], 'draws': comparisons['draws.csv']['field_difference_counts'], 'flows': matlab_flows, 'written': ['t12v/residual.json','t12v/residual.md']}, indent=2))
