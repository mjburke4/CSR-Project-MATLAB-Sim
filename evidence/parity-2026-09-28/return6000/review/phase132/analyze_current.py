#!/usr/bin/env python3
"""Offline seed-132 causal phase review using the validated archived parser.

Execute the archived per-case parser unchanged, restricting inputs to the new
owner return and omitting only the original five-case final source-bind report.
This launches no simulator and edits no production source.
"""
import ast
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
HISTORY = ROOT / 'return6000/history'
OLDMAT = HISTORY / 'longrun_recovery/extracted/latency-review/latency-review/matlab'
RAW = ROOT / 'return6000/data/s132/attempt_001/raw'
OWNER = ROOT / 'upload/out_6000_20260924_152302.zip'

def table(p):
    with p.open(newline='') as f:
        return list(csv.DictReader(f))

def csvout(p, rows):
    with p.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

def ns(v):
    return int((Decimal(str(v))*1_000_000_000).to_integral_value(rounding=ROUND_HALF_EVEN))

def mean(vals):
    return math.fsum(vals) / len(vals) if vals else None

def main():
    parser = OLDMAT / 'analyze_matlab_latency.py'
    tree = ast.parse(parser.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'analyze')
    stop = next(i for i,n in enumerate(fn.body) if isinstance(n, ast.Assign) and
                any(isinstance(t, ast.Name) and t.id == 'source_files' for t in n.targets))
    fn.body = fn.body[:stop] + [ast.Return(value=ast.Name(id='cases', ctx=ast.Load()))]
    tree.body = [n for n in tree.body if not isinstance(n, ast.If)]
    ast.fix_missing_locations(tree)
    mod = {'__file__':str(parser), '__name__':'archived_parser_for_new_return'}
    exec(compile(tree, str(parser), 'exec'), mod)
    mod['CASES'] = [(132, 's132/attempt_001', str(OWNER.relative_to(ROOT)))]
    case = mod['analyze'](ROOT, OUT)[0]
    assert not case['decomposition_failures']
    packet = table(OUT / 'packets-132.csv')
    hops = table(OUT / 'causal-hops-132.csv')
    native_p = table(HISTORY / 'longrun_review/native_s132/applications.csv')
    native_h = table(HISTORY / 'longrun_review/native_s132/causal_hops.csv')
    old_p = table(OLDMAT / 'packets-132.csv')
    old_h = table(OLDMAT / 'causal-hops-132.csv')
    path = defaultdict(list)
    for h in hops: path[h['packet_id']].append(h)
    ns_closure = []
    for p in packet:
        if p['outcome'] != 'delivered': continue
        hs = sorted(path[p['packet_id']], key=lambda h: int(h['hop_index']))
        previous = ns(p['generated_s']); total_nwk = total_post = 0
        for h in hs:
            arrival, admitted, received = map(ns, (h['arrival_s'], h['hop_admit_s'], h['causal_receipt_s']))
            assert arrival == previous and arrival <= admitted <= received
            total_nwk += admitted-arrival; total_post += received-admitted; previous = received
        ns_closure.append(total_nwk+total_post-(previous-ns(p['generated_s'])))
    assert ns_closure and set(ns_closure) == {0}
    summary = json.loads((RAW / 'summary.json').read_text())
    assert summary['Statistics']['OmittedTraceRecords'] == 0
    assert case['outcomes']['delivered'] == case['decomposition_complete_count'] == summary['Statistics']['Received']
    assert case['admitted'] == summary['Statistics']['Generated']
    for outcome,key in [('dropped','Dropped'),('pending','Pending')]:
        assert case['outcomes'][outcome] == summary['Statistics'][key]
    result = []
    by_node = []
    for label, pp, hh in [('matlab_current',packet,hops), ('matlab_original',old_p,old_h), ('ns3_reference',native_p,native_h)]:
        native = label == 'ns3_reference'
        for src in (2,3,4,5,7,8):
            delivered = [p for p in pp if int(p['source']) == src and p['status' if native else 'outcome']=='delivered']
            latency = [int(p['latency_ns'])/1e9 if native else float(p['delivered_delay_s']) for p in delivered]
            nwk = [int(p['total_nwk_wait_ns'])/1e9 if native else float(p['nwk_admission_wait_s']) for p in delivered]
            post = [int(p['post_admission_ns'])/1e9 if native else float(p['post_admission_to_causal_receipt_s']) for p in delivered]
            result.append(dict(model=label, seed=132, source=src, delivered=len(delivered),
                mean_latency_s=mean(latency), mean_nwk_wait_s=mean(nwk), mean_post_hop_admission_s=mean(post)))
            rows = [h for h in hh if int(h['source']) == src]
            for node in sorted({int(h['node']) for h in rows}):
                selected = [h for h in rows if int(h['node'])==node]
                waits = [int(h['nwk_wait_ns'])/1e9 if native else float(h['nwk_admission_wait_s']) for h in selected]
                service = [int(h['post_admission_ns'])/1e9 if native else float(h['post_admission_to_causal_receipt_s']) for h in selected]
                by_node.append(dict(model=label, seed=132, source=src, node=node, delivered_population=len(delivered),
                    causal_hops_at_node=len(selected), mean_nwk_wait_per_delivered_app_s=math.fsum(waits)/len(delivered),
                    mean_post_admission_per_delivered_app_s=math.fsum(service)/len(delivered),
                    mean_nwk_wait_per_visit_s=mean(waits), max_nwk_wait_s=max(waits),
                    mean_queue_at_arrival=None if native else mean([float(h['network_queue_depth_at_arrival']) for h in selected])))
    csvout(OUT/'source_phase_comparison.csv',result)
    csvout(OUT/'source_node_phase_comparison.csv',by_node)
    validation = dict(parser_sha256=hashlib.sha256(parser.read_bytes()).hexdigest(),
        return_sha256=case['input_archive_sha256'], protocol_sha256=case['protocol_sha256'],
        protocol_rows=case['protocol_rows'], outcomes=case['outcomes'],
        all_delivered_paths_decomposed=case['decomposition_complete_count'], causal_hops=len(hops),
        max_float_closure_error_s=case['max_abs_closure_error_s'], exact_ns_closure_error=0,
        omitted_trace_records=0, fresh_simulations_executed=False, production_source_changed=False)
    (OUT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    print(json.dumps(validation,indent=2))
    print(json.dumps(result,indent=2))

if __name__ == '__main__': main()
