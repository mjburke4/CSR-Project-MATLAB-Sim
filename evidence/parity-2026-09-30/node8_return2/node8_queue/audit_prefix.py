#!/usr/bin/env python3
"""Offline node-8 and application accounting of the failed run's complete prefix.

Does not simulate, alter model code, or treat the partial run as a 1,200-s run.
Usage: python node8_return2/node8_queue/audit_prefix.py
"""
import collections
import csv
import json
from pathlib import Path
import observer_decoder as obs

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
MAT = ROOT / 'node8_return2/data/S132_1200'
NATIVE = ROOT / 'node8_1200/native/s132_1200/run/ns3-trace.csv'

def compare(left, right):
    first = next(({'ordinal_1based': i + 1, 'matlab': m, 'native': n}
                  for i, (m, n) in enumerate(zip(left, right)) if m != n), None)
    if first is None and len(left) != len(right):
        first = {'ordinal_1based': min(len(left), len(right)) + 1,
                 'matlab': left[min(len(left),len(right)):] or None,
                 'native': right[min(len(left),len(right)):] or None}
    return {'equal': left == right, 'matlab_count': len(left),
            'native_count': len(right), 'first_difference': first}

def app_accounting(cutoff):
    mids, nids = {}, {}
    mg, ng, md, nd = [], [], [], []
    attempts = {'matlab': collections.Counter(), 'native': collections.Counter()}
    snapshots = {'matlab': [], 'native': []}
    drops = collections.defaultdict(list)
    for r in csv.DictReader((MAT / 'application_admission_trace.csv').open()):
        t = obs.ns(r['TimeSeconds'])
        if t >= cutoff: continue
        src, attempt = int(r['SourceId']), int(r['AttemptIndex'])
        key = (src, attempt)
        attempts['matlab'][src] += 1
        if r['Accepted'] == '1':
            mids[int(r['PacketId'])] = key
            mg.append((t, key))
        if src == 8:
            snapshots['matlab'].append((t, key, int(r['Accepted']),
                int(r['NsdpCount']), int(r['NsdpLimit']), int(r['NwkQueueSize'])))
    for r in csv.DictReader((MAT / 'protocol_trace.csv').open()):
        t = obs.ns(r['TimeSeconds'])
        if t >= cutoff: continue
        if r['Event'] == 'app_receive': md.append((t, mids[int(r['PacketId'])]))
        if r['Event'] == 'app_drop': drops[mids[int(r['PacketId'])]].append((t, r['Reason']))
    for r in csv.DictReader(NATIVE.open()):
        t = obs.ns(r['time_s'])
        if t >= cutoff: continue
        if r['event'] == 'app_admission':
            d = obs.details(r['detail'])
            src, attempt = int(r['src']), int(d['attempt_index'])
            key = (src, attempt)
            attempts['native'][src] += 1
            if r['success'] == '1':
                nids[int(r['sequence'])] = key
                ng.append((t, key))
            if src == 8:
                snapshots['native'].append((t, key, int(r['success']),
                    int(d['nsdp_count']), int(d['nsdp_limit']), int(d['nwk_queue'])))
        elif r['event'] == 'nwk_delivery': nd.append((t, nids[int(r['sequence'])]))
    result = {'admitted_identity_order_time_comparison': compare(mg, ng),
              'delivered_identity_order_time_comparison': compare(md, nd),
              'node8_application_snapshot_comparison': compare(snapshots['matlab'], snapshots['native']),
              'attempts': attempts, 'source_populations': []}
    for src in sorted(attempts['matlab']):
        row = {'source': src}
        for label, generated, delivered in [('matlab', mg, md), ('native', ng, nd)]:
            g = {k: t for t, k in generated if k[0] == src}
            de = [(t, k) for t, k in delivered if k[0] == src]
            first = {}
            for t, k in de: first.setdefault(k, t)
            assert set(first).issubset(g)
            latency = [t - g[k] for k, t in first.items()]
            unresolved = set(g) - set(first)
            row[label] = {'attempted': attempts[label][src], 'admitted': len(g),
                'delivered_unique': len(first), 'delivered_raw_rows': len(de),
                'admitted_unresolved_at_cutoff': len(unresolved),
                'delivered_mean_latency_s': (sum(latency)/len(latency)/1e9) if latency else None,
                'first_delivery_s': (min(first.values())/1e9) if first else None}
            if label == 'matlab':
                row[label]['unresolved_with_prior_provisional_drop'] = len(unresolved & set(drops))
                row[label]['unresolved_without_prior_drop'] = len(unresolved - set(drops))
                row[label]['delivered_with_prior_provisional_drop'] = len(set(first) & set(drops))
        result['source_populations'].append(row)
    result['accounting_notes'] = [
        'Application key is (source, scheduled attempt), independently mapped from each engine admitted packet IDs.',
        'Delivered latency uses the first observed final delivery and that same key admission time.',
        'Admitted minus unique delivered is unresolved at the partial cutoff, not a terminal loss count.',
        'MATLAB app_drop is a provisional ownership event; late copies may deliver after it. No equivalence to a native end-to-end terminal drop is asserted.',
        'The first divergence stops execution, so nothing is inferred about [895.115,1200] from this prefix.'
    ]
    return result

def main():
    case = json.loads((MAT / 'case_summary.json').read_text())
    assert case['completed'] is False and case['diagnostic_status'] == 'context_divergence'
    cutoff = obs.ns(case['reached_time_s'])
    assert cutoff == 895115000000
    checkpoints = [400000000000, 600000000000, 675000000000, cutoff]
    matlab, me, ma, mr = obs.read_matlab(MAT / 'ordered_events.jsonl', cutoff, 8, checkpoints)
    native, ne, na, nr = obs.read_native(NATIVE, cutoff, 8, checkpoints)
    checks = {
        'nwk_arrival_identity_order_time': compare(me, ne),
        'hop_handoff_identity_order_peer_sequence': compare([r[1:] for r in ma], [r[1:] for r in na]),
        'custody_release_identity_order_time_reason': compare(mr, nr),
        'ordered_queue_and_custody_checkpoints_equal': matlab['queue_checkpoints'] == native['queue_checkpoints'],
        'final_ordered_queue_and_custody_equal': matlab['final'] == native['final'],
    }
    shifts = collections.Counter(str(m[0]-n[0]) for m,n in zip(ma,na))
    timing_differences = [{'ordinal_1based':i+1,'matlab':m,'native':n,'delta_ns':m[0]-n[0]}
                          for i,(m,n) in enumerate(zip(ma,na)) if m[0] != n[0]]
    accounting = app_accounting(cutoff)
    semantic_pass = all(v['equal'] if isinstance(v,dict) else v for v in checks.values())
    result = {'schema':'csr-node8-partial-prefix-audit-v1',
        'status':'node8_semantic_prefix_pass' if semantic_pass else 'node8_semantic_prefix_mismatch',
        'completed_1200_second_run':False, 'stop_ns_exclusive':cutoff,
        'first_tx_context_divergence_node':4,
        'scope':'Observed complete prefix strictly before the failed TX context at 895.115 s; no extrapolation.',
        'checks':checks, 'matlab':matlab, 'native':native,
        'handoff_matlab_minus_native_time_ns_counts':dict(shifts),
        'handoff_timing_differences':timing_differences,
        'timing_policy':'The first local handoff retains its previously known -28 ns delta; this audit changes no comparator tolerance. All later node8 handoff times match.',
        'application_accounting':accounting,
        'limits':['Native candidate queue checks are verified against native reconstructed state. MATLAB does not log every rejected NWK pump candidate.',
                  'MATLAB post-event live HOP capacity and NSDP are checked against its actual callbacks; this is not a complete physical-copy reconstruction.',
                  'Checkpoint states are before every event at the exact checkpoint time.'],
        'inputs_sha256': {str(p.relative_to(ROOT)):obs.sha(p) for p in [MAT/'case_summary.json',MAT/'ordered_events.jsonl',MAT/'application_admission_trace.csv',MAT/'protocol_trace.csv',NATIVE]},
        'decoder_sha256':obs.sha(OUT/'observer_decoder.py')}
    (OUT/'prefix_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'checks':checks,'handoff_timing':dict(shifts),
                      'application_checks':{k:v for k,v in accounting.items() if 'comparison' in k},
                      'source_populations':accounting['source_populations']}))

if __name__ == '__main__': main()
