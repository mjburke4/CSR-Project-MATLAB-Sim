"""Independent, read-only T14 owner/native trace comparison; no MATLAB execution."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import struct
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
OWNER = ROOT / 'upload/t14(2).zip'
NATIVE = ROOT / 'csr14s/evidence/tranche-14-edge-reference'
CASES = ['tie_early', 'tie_late', 'before', 'after', 'continuous', 'quantized']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rows(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))


def from_hex(value):
    return struct.unpack('>d', bytes.fromhex(value))[0]


def as_hex(value):
    return struct.pack('>d', value).hex()


def for_case(table, name):
    return [r for r in table if r['case'] == name]


def diff_rows(actual, reference, fields):
    mismatches = []
    for i in range(max(len(actual), len(reference))):
        a = actual[i] if i < len(actual) else None
        b = reference[i] if i < len(reference) else None
        changes = ({key: {'matlab': a[key], 'native': b[key]}
                    for key in fields if a[key] != b[key]}
                   if a is not None and b is not None else {'missing_row': True})
        if changes:
            mismatches.append({'row': i + 1, 'fields': changes})
    return mismatches


def metrics(events):
    acks = [r for r in events if r['phase'] == 'ack_tx']
    updated = [r for r in acks if r['hop_seq'] == '3' and r['ack_bits'] == '7']
    delivery = [r for r in events if r['phase'] == 'deliver']
    settled = [r for r in events if r['phase'] == 'settled']
    assert len({(r['app_source'], r['app_id']) for r in delivery}) == 3
    assert len(settled) == 3
    assert all(r['ack_queue'] == r['data_queue'] == '0' for r in settled)
    return {
        'events': len(events), 'deliveries': len(delivery),
        'delivery_identities': [[r['app_source'], r['app_id']] for r in delivery],
        'first_ack_sequence': int(acks[0]['hop_seq']),
        'first_ack_bitmap': int(acks[0]['ack_bits']),
        'first_ack_time_ns': int(acks[0]['time_ns']),
        'first_updated_ack_time_ns': int(updated[0]['time_ns']),
        'last_ack_time_ns': int(acks[-1]['time_ns']),
        'gateway_ack_transmissions': len(acks),
        'ack_and_data_queues_empty_at_horizon': True,
    }


def main():
    z = ZipFile(OWNER)
    actual = {name: rows(z.read(f'edge/{name}.csv'))
              for name in ['events', 'boundary', 'draws', 'usage', 'scheduler']}
    native = {name: rows((NATIVE / f'{name}.csv').read_bytes())
              for name in ['events', 'boundary', 'draws', 'usage']}
    summary = json.loads(z.read('edge/summary.json'))
    fields = {
        'semantic': [k for k in actual['events'][0]
                     if k not in ['time_seconds_dec', 'time_seconds_hex', 'scheduler_id']],
        'boundary': [k for k in actual['boundary'][0]
                     if not k.endswith('_seconds_dec') and k != 'ingress_event_id'],
        'precision': ['case', 'order', 'phase', 'time_seconds_hex'],
        'draws': list(actual['draws'][0]), 'usage': list(actual['usage'][0]),
    }
    tables = {'semantic': 'events', 'precision': 'events', 'boundary': 'boundary',
              'draws': 'draws', 'usage': 'usage'}
    case_results = []
    counts = Counter()
    for name in CASES:
        ae = for_case(actual['events'], name)
        ne = for_case(native['events'], name)
        a = for_case(actual['boundary'], name)[0]
        n = for_case(native['boundary'], name)[0]
        compares = {kind: diff_rows(for_case(actual[tables[kind]], name),
                                   for_case(native[tables[kind]], name), keys)
                    for kind, keys in fields.items()}
        for kind, mismatches in compares.items():
            counts[kind] += len(mismatches)
        am, nm = metrics(ae), metrics(ne)
        first_ack = next(r for r in ae if r['phase'] == 'ack_tx')
        ingress = next(r for r in ae if r['phase'] == 'ingress_before')
        schedule = for_case(actual['scheduler'], name)
        execution = [r for r in schedule if r['operation'] == 'execute'
                     and r['event_id'] in [first_ack['scheduler_id'], ingress['scheduler_id']]]
        assert len(execution) == 2
        assert all(r['observed_hex'] == r['scheduled_hex'] for r in execution)
        assert execution[0]['event_id'] == (ingress['scheduler_id']
               if int(ingress['order']) < int(first_ack['order']) else first_ack['scheduler_id'])
        record = {
            'case': name, 'matlab': am, 'native': nm,
            'updated_ack_delay_ns': am['first_updated_ack_time_ns'] - nm['first_updated_ack_time_ns'],
            'arrival_minus_tick_seconds_matlab': from_hex(a['arrival_minus_tick_seconds_hex']),
            'arrival_minus_tick_seconds_native': from_hex(n['arrival_minus_tick_seconds_hex']),
            'arrival_hex_matlab': a['arrival_seconds_hex'],
            'arrival_hex_native': n['arrival_seconds_hex'],
            'matlab_ingress_event_id': int(a['ingress_event_id']),
            'matlab_first_ack_event_id': int(first_ack['scheduler_id']),
            'matlab_execution_order': [r['event_id'] for r in execution],
            'comparisons': compares,
        }
        case_results.append(record)
    expected_counts = {'semantic': 11, 'boundary': 6, 'precision': 9, 'draws': 1, 'usage': 1}
    assert dict(counts) == expected_counts
    for kind, key in [('semantic', 'EventComparison'), ('boundary', 'BoundaryComparison'),
                      ('precision', 'FullPrecisionComparison'), ('draws', 'DrawComparison'),
                      ('usage', 'UsageComparison')]:
        assert counts[kind] == summary[key]['UnmatchedCount']
    assert sum(counts.values()) == summary['UnmatchedCount'] == 28
    assert all(not r['comparisons']['semantic'] and not r['comparisons']['precision']
               for r in case_results if r['case'] != 'continuous')
    assert case_results[4]['updated_ack_delay_ns'] == 26000000
    assert case_results[4]['arrival_minus_tick_seconds_matlab'] == math.ulp(3.144961)
    # Both duration encodings yield the same late arrival under binary64 sum.
    # Duration encoding is therefore separate evidence, not itself the remedy.
    binary64_arrivals = {}
    for duration_hex in ['3f998f1d3ed527e5', '3f998f1d3ed527e6']:
        arrival = from_hex('4008f5c28f5c28f6') + from_hex(duration_hex) + 1e-6
        binary64_arrivals[duration_hex] = as_hex(arrival)
        assert as_hex(arrival) == '400928e15011904c'
    checks = rows(z.read('edge/check.csv'))
    assert len(checks) == 222 and all(r['pass'] == '1' for r in checks)
    tests = rows(z.read('tests.csv'))
    result = {
        'schema': 'csr-tranche14-independent-return-differences-v1',
        'reviewer_matlab_executed': False,
        'owner_zip_sha256': digest(OWNER.read_bytes()),
        'candidate_sha256': json.loads(z.read('metadata.json'))['CandidateSHA256'],
        'script_sha256': digest(Path(__file__).read_bytes()),
        'source_bindings': {
            f'owner:edge/{name}.csv': digest(z.read(f'edge/{name}.csv')) for name in actual},
        'native_bindings': {
            f'evidence/tranche-14-edge-reference/{name}.csv': digest((NATIVE / f'{name}.csv').read_bytes())
            for name in native},
        'cases': case_results,
        'comparison_row_counts': dict(counts),
        'reported_total_row_differences': sum(counts.values()),
        'counter_interpretation': 'Overlapping positional row comparisons, not independent defects or a network error rate.',
        'duration_binary64_arithmetic_probe': binary64_arrivals,
        'duration_difference_seconds': from_hex('3f998f1d3ed527e6') - from_hex('3f998f1d3ed527e5'),
        'checkpoints_recomputed': {'total': len(checks), 'passed': len(checks)},
        'bounded_conclusion': 'Five controls exactly match semantic and full-precision event traces. Continuous binary64 transport places DATA one ULP after ACK service, delays updated feedback 26 ms and adds one gateway ACK plus one draw. All 18 unique deliveries occur and all final ACK/DATA queues are empty.',
        'not_established': ['Full network numerical parity', 'Source sender custody or admission-capacity gain',
                            'Loss-recovery improvement', 'Global clock change suitability', 'PHY/ECC or RF behavior'],
        'next_investigation': 'A separately reviewed, opt-in transport nanosecond conversion experiment in the T13 continued-traffic loss/recovery harness, paired against the accepted default and pinned native trace. Observe real sender custody, retry count, capacity release, delivery latency, and unchanged 1 ns before/tie/after ordering before considering production adoption.',
    }
    (OUT / 'differences.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_metrics': [{k: v for k, v in r.items() if k != 'comparisons'}
                                    for r in case_results], 'counts': dict(counts)}, indent=2))


if __name__ == '__main__':
    main()
