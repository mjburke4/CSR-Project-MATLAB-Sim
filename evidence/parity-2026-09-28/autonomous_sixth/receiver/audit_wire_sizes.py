#!/usr/bin/env python3
"""Offline size-formula audit of the captured seed-132 0–330 s fixture.

This evaluates the issued MATLAB formulas on observed native fields. It does
not execute MATLAB and does not claim that the autonomous MATLAB population
continues to match native after its first strict stop at 25.298 s.
"""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
FIXTURE = ROOT / 'autonomous/native_capture/fixture/tx_signatures.csv'
ISSUED = ROOT / 'autonomous_fifth/kit/autocase/ref/native/tx_signatures.csv'
MODEL = ROOT / 'autonomous_fifth/kit/autocase/model'


def counts(values):
    return dict(sorted(Counter(values).items()))


def routing_parts(row):
    payload = bytes.fromhex(row['payload_hex'])
    plain = payload[3:-2] if int(row['flags']) & 128 else payload
    assert len(plain) >= 32
    offset = 30 + (16 if plain[26] == 4 else 0)
    chirps = plain[offset]
    offset += 1 + 3 * chirps
    routes = plain[offset]
    offset += 1
    for _ in range(routes):
        path_count = plain[offset + 11]
        offset += 12 + 3 * path_count
    raw = plain[offset:]
    semantic = bytes.fromhex(row['routing_section_hex'])
    if raw:
        assert row['routing_section_origin'] == 'actual_arl_section'
        assert semantic == raw
    else:
        assert row['routing_section_origin'] == 'normalized_legacy_request'
        assert plain[26] == 3 and chirps == routes == 0
        assert semantic == plain[20:26] + bytes([3])
    return raw, semantic


def operations(section):
    # All captured sections are single-section complete messages, checked below.
    offset = 6
    result = []
    while offset < len(section):
        opcode = section[offset]
        offset += 1
        result.append({0: 'FLUSH', 1: 'DELETE', 2: 'UPDATE', 3: 'REQUEST', 4: 'INFO'}[opcode])
        if opcode == 1:
            offset += 3
        elif opcode == 2:
            offset += 10 + 3 * int.from_bytes(section[offset + 4:offset + 6], 'big')
        elif opcode == 4:
            offset += 16
        assert offset <= len(section)
    return result


def write_csv(path, records):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main():
    rows = list(csv.DictReader(FIXTURE.open()))
    issued = list(csv.DictReader(ISSUED.open()))
    common = set(rows[0]) & set(issued[0])
    assert len(rows) == len(issued)
    # Additional passive metadata columns are allowed; original fields are exact.
    for observed, original in zip(rows, issued):
        assert all(observed[k] == original[k] for k in common)

    groups = defaultdict(list)
    audit = []
    raw_ops = []
    for row in rows:
        packet = bytes.fromhex(row['packet_hex'])
        header_bytes = int(row['compatibility_header_bytes'])
        assert len(packet) == header_bytes + int(row['compatibility_payload_bytes'])
        assert packet[header_bytes:] == bytes.fromhex(row['payload_hex'])
        kind = int(row['kind'])
        native = int(row['wire_bytes'])
        raw_bytes = ''
        semantic_bytes = ''
        ops = []
        if kind == 0:
            # All captured ordinary DATA/ACKs use the issued historical bare profile.
            assert not row['security_count']
            classification = 'DATA_bare'
            matlab = int(row['application_bytes']) + 32
        elif kind in (1, 2):
            assert not row['security_count']
            classification = ('ACK' if kind == 1 else 'DACK') + ('_window_bare' if int(row['has_ack_window']) else '_exact_bare')
            matlab = 25 + 16 * int(row['has_ack_window'])
        elif kind == 4:
            classification = 'DISCOVER_' + row['discover_subtype']
            matlab = 19
        elif kind == 5:
            classification = 'NEIGHBOR_CHECK_' + row['check_subtype']
            matlab = 16 + 3 * (row['check_subtype'] == 'no_path')
        elif kind == 6:
            assert row['routing_section'] == '0' and row['routing_total_sections'] == '1'
            raw, semantic = routing_parts(row)
            raw_bytes, semantic_bytes = len(raw), len(semantic)
            classification = 'ROUTING_' + row['routing_section_origin']
            matlab = 16 + semantic_bytes
            assert native == 16 + raw_bytes
            if raw:
                ops = operations(raw)
                raw_ops.extend(ops)
        elif kind == 7:
            classification = 'SNMP_' + {'1': 'START', '2': 'DONE'}[row['snmp_command']]
            matlab = 31
        elif kind == 8:
            classification = 'KEY_REQUEST'
            matlab = 18
        elif kind == 9:
            classification = 'KEY_UPDATE'
            matlab = 62
        else:
            raise AssertionError(('unclassified kind', kind))
        record = {
            'time_s': int(row['time_ns']) / 1e9, 'tx_id': row['tx_id'],
            'source': int(row['source']), 'source_tx_ordinal': int(row['source_tx_ordinal']),
            'child_index': int(row['child_index']), 'frame_id': row['frame_id'],
            'kind': kind, 'classification': classification,
            'hop_destination': row['hop_destination'], 'hop_sequence': row['hop_sequence'],
            'routing_sequence': row['routing_sequence'],
            'native_wire_bytes': native, 'issued_matlab_formula_bytes': matlab,
            'excess_bytes': matlab - native,
            'actual_routing_raw_bytes': raw_bytes,
            'normalized_routing_semantic_bytes': semantic_bytes,
            'actual_section_operations': ';'.join(ops),
        }
        audit.append(record)
        groups[row['tx_id']].append(row)

    aggregate_errors = []
    for tx_id, children in groups.items():
        count = int(children[0]['child_count'])
        total = int(children[0]['total_wire_bytes'])
        if not (len(children) == count and sorted(int(c['child_index']) for c in children) == list(range(count))
                and sum(int(c['wire_bytes']) for c in children) == total
                and all(int(c['child_count']) == count and int(c['total_wire_bytes']) == total for c in children)):
            aggregate_errors.append(tx_id)
    assert not aggregate_errors

    mismatches = [r for r in audit if r['excess_bytes']]
    assert len(mismatches) == 17
    assert all(r['classification'] == 'ROUTING_normalized_legacy_request' and r['excess_bytes'] == 7 for r in mismatches)
    classes = []
    for name in sorted({r['classification'] for r in audit}):
        sub = [r for r in audit if r['classification'] == name]
        classes.append({'classification': name, 'children': len(sub),
                        'native_sizes': counts(r['native_wire_bytes'] for r in sub),
                        'matlab_sizes': counts(r['issued_matlab_formula_bytes'] for r in sub),
                        'mismatches': sum(bool(r['excess_bytes']) for r in sub)})
    inputs = [FIXTURE, ISSUED, MODEL / '+csr/+nwk/controlWireBytes.m',
              MODEL / '+csr/+hop/Frames.m', MODEL / '+csr/+nwk/Layer.m',
              ROOT / 'autonomous/native_env/csr/model/csr-opnet-envelope.h',
              ROOT / 'autonomous/native_env/csr/model/csr-nwk-layer.h',
              ROOT / 'autonomous/native_env/csr/model/csr-hop-layer.h',
              ROOT / 'autonomous/native_capture/normalize.py',
              ROOT / 'autonomous_sixth/data/H_admission_route/first_divergence.json']
    summary = {
        'method': 'Offline issued-MATLAB-formula evaluation on captured native child fields; no MATLAB execution or simulation.',
        'native_fixture_matches_issued_common_fields': True,
        'child_transmissions': len(rows), 'physical_transmissions': len(groups),
        'captured_time_range_s': [min(r['time_s'] for r in audit), max(r['time_s'] for r in audit)],
        'matching_children': len(audit) - len(mismatches), 'mismatching_children': len(mismatches),
        'affected_physical_transmissions': len({r['tx_id'] for r in mismatches}),
        'mismatch_time_range_s': [min(r['time_s'] for r in mismatches), max(r['time_s'] for r in mismatches)],
        'mismatch_children_by_source': counts(r['source'] for r in mismatches),
        'request_source_destination_sequence_keys': len({(r['source'], r['hop_destination'], r['routing_sequence']) for r in mismatches}),
        'fixed_fixture_sum_excess_bytes': sum(r['excess_bytes'] for r in mismatches),
        'fixed_fixture_excess_warning': '119 bytes is repeated-child accounting on fixed native rows, not a prediction of changed autonomous airtime or delivery.',
        'aggregate_consistency_errors': aggregate_errors,
        'classes': classes, 'actual_routing_section_record_occurrences': counts(raw_ops),
        'snmp_node_list_lengths': counts(len(r['snmp_nodes'].split(';')) if r['snmp_nodes'] else 0 for r in rows if r['kind'] == '7'),
        'routing_destination_list_lengths': counts(len(r['destination_sequences'].split(';')) if r['destination_sequences'] else 0 for r in rows if r['kind'] == '6'),
        'uncaptured_variants': ['NEIGHBOR_CHECK no_path/verify/message', 'DISCOVER chirp', 'compact non-REQUEST routing markers',
                              'actual ARL REQUEST records', 'multi-section routing', 'DACK', 'pairwise-protected ordinary DATA/ACK', 'other native-only packet kinds'],
        'source_confirmed_uncaptured_matlab_mismatch': {'variant': 'generated NEIGHBOR_CHECK no_path', 'native_bytes': 16, 'issued_matlab_bytes': 19,
                                                       'reason': 'Target is compatibility CsrHelloHeader metadata; native creates zero raw payload bytes.'},
        'inputs_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
    }
    write_csv(OUT / 'fixture_child_size_audit.csv', audit)
    write_csv(OUT / 'compact_request_disagreements.csv', mismatches)
    (OUT / 'wire_size_audit.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: summary[k] for k in ('child_transmissions', 'physical_transmissions', 'matching_children',
          'mismatching_children', 'affected_physical_transmissions', 'aggregate_consistency_errors')}, indent=2))


if __name__ == '__main__':
    main()
