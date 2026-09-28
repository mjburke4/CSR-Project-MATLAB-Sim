#!/usr/bin/env python3
"""Verify the actual L owner return without executing MATLAB or changing guards."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
ISSUED = ROOT / 'autonomous_ninth/kit/autocase'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text())


def main():
    archive = ROOT / 'upload/out_auto_20260928_090828.zip'
    assert sha(archive) == '979706b7d4f545b60cb5bfd1b4ac11c485783ec91a1eaa49b4858c50a3e0f2a7'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name in z.namelist():
            assert z.read(name) == (DATA / name).read_bytes(), name
        members = len(z.namelist())
    report = read(DATA / 'report.json')
    provenance = read(DATA / 'provenance.json')
    manifest = read(ISSUED / 'FILES.json')
    assert provenance['manifest'] == manifest
    for row in manifest['files']:
        assert sha(ISSUED / row['path']) == row['sha256'], row['path']
    assert len(manifest['files']) == 389
    assert not report['error_identifier'] and report['import_preflight']['passed']
    passed = {}
    for field, count in [('key_request_preflight', 7), ('check_gate_preflight', 8),
                         ('population_preflight', 6), ('route_admission_preflight', 8),
                         ('request_wire_preflight', 6), ('no_path_wire_preflight', 3),
                         ('discovery_identity_preflight', 7), ('receiver_timer_preflight', 8),
                         ('discovery_lifecycle_preflight', 8)]:
        pre = report[field]
        assert pre['passed'] and len(pre['checks']) == count
        assert all(r['passed'] for r in pre['checks'])
        passed[field] = count
    assert sum(passed.values()) == 61
    reuse = report['accepted_natural_reuse']
    assert all(reuse[k] for k in ['reused', 'runtime_matches', 'configuration_matches',
                                'prefix_gate_recomputed'])
    assert not reuse['fresh_natural_simulation_executed']
    for name in ['protocol_trace.csv', 'phy_trace.csv', 'application_admission_trace.csv']:
        assert (DATA / 'A_natural' / name).read_bytes() == (ISSUED / 'ref/matlab' / name).read_bytes()
    folder = DATA / 'L_discovery_lifecycle'
    item = read(folder / 'case_summary.json')
    summary = read(folder / 'random_summary.json')
    requests = [json.loads(s) for s in (folder / 'random_requests.jsonl').read_text().splitlines()]
    assert len(requests) == 2731
    assert all(r['context_matched'] for r in requests)
    assert all(r['value'] == r['expected']['value'] for r in requests)
    assert sum(r['consumed'] for r in summary['counts']) == 2731
    assert summary['native_transmissions_checked'] == 487
    first_time_difference = summary['first_time_difference']
    assert first_time_difference['node'] == 3 and first_time_difference['ordinal'] == 102
    assert first_time_difference['rounded_delta_ns'] == -183651000000
    kinds = Counter()
    tx = []
    for line in (folder / 'ordered_events.jsonl').open():
        event = json.loads(line)
        kinds[event['kind']] += 1
        if event['kind'] == 'physical_tx_context':
            tx.append(event)
    assert len(tx) == 488 and all(not r['details']['mismatches'] for r in tx[:-1])
    divergence = read(folder / 'first_divergence.json')
    assert tx[-1]['details']['mismatches'] == divergence['fields']
    assert divergence['node'] == 3 and divergence['ordinal'] == 86 and divergence['purpose'] == 'physical_tx'
    actual = divergence['actual']['children'][0]
    expected = divergence['expected']
    if isinstance(expected, list):
        assert len(expected) == 1
        expected = expected[0]
    assert actual['control_type'] == 'SNMP_START'
    assert actual['hop_destination'] == 5 and actual['snmp_destination'] == 7
    assert expected['kind'] == 0 and expected['network_destination'] == 1
    assert expected['time_ns'] == 300365000000
    repaired_draw = [r for r in requests if r['node'] == 4 and r['purpose'] == 'mac_slot' and r['ordinal'] == 25]
    assert len(repaired_draw) == 1 and repaired_draw[0]['context_matched']
    repaired_tx = [r for r in tx if r['node'] == 5 and
                   (r['details']['expected'][0] if isinstance(r['details']['expected'], list)
                    else r['details']['expected'])['source_tx_ordinal'] == 68]
    assert len(repaired_tx) == 1 and not repaired_tx[0]['details']['mismatches']
    identities = [c['discovery_outer_sequence_identity'] for r in tx
                  for c in r['details']['actual']['children']
                  if 'discovery_outer_sequence_identity' in c]
    observer = read(folder / 'observer_status.json')
    timing = read(folder / 'transport_timing_summary.json')
    receiver = read(folder / 'receiver_timing_summary.json')
    assert observer['Complete'] and observer['OmittedServiceRecords'] == 0
    assert timing['Mode'] == 'nanoseconds' and timing['Omitted'] == 0
    assert receiver['Count'] == 1818 and receiver['Omitted'] == 0
    raw = {}
    for name in ['protocol_trace.csv', 'phy_trace.csv', 'application_admission_trace.csv']:
        with (folder / name).open() as f:
            raw[name] = sum(1 for _ in csv.DictReader(f))
    assert raw['application_admission_trace.csv'] == 0
    result = dict(
        schema='csr-autonomous-discovery-lifecycle-return-v1', status='return_integrity_pass',
        archive=archive.name, archive_sha256=sha(archive), archive_members=members,
        issued_manifest_sha256=sha(ISSUED / 'FILES.json'), issued_bound_files=len(manifest['files']),
        runtime=report['runtime'], import_preflight_passed=True,
        matlab_passed_component_checks=passed, accepted_natural_reused=True,
        case=dict(name='L_discovery_lifecycle', endpoint_s=item['reached_time_s'],
                  requests_consumed_context_matched=len(requests), rejected_requests=0,
                  consumed_by_purpose=dict(Counter(r['purpose'] for r in requests)),
                  verified_transmission_contexts=len(tx)-1, rejected_transmissions=1,
                  first_time_difference=first_time_difference,
                  temporal_prefix_match_through_stop=False,
                  previous_key_update_and_requester_guards_cleared=True,
                  discovery_identity_annotations=len(identities),
                  discovery_different_outer_identifiers=sum(x['actual'] != x['native'] for x in identities),
                  raw_rows=raw, ordered_event_rows=sum(kinds.values()), ordered_event_kinds=dict(kinds),
                  timing_records=timing['Count'], receiver_timer_records=receiver['Count'],
                  service_records=observer['CapturedServiceRecords'],
                  wall_seconds=item['wall_seconds'], stop_fields=divergence['fields'],
                  actual_snmp_hop_destination=5, actual_snmp_destination=7,
                  expected_next_node3_tx_s=expected['time_ns']/1e9,
                  expected_next_node3_kind='DATA'),
        target_percent=15, network_parity_established=False,
        scope='Startup ends before applications begin at 300 seconds; unfinished traffic and 6000-second parity remain open.')
    (HERE / 'return_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    (HERE / 'return_input_manifest.json').write_text(json.dumps([
        dict(path=p.relative_to(DATA).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(DATA.rglob('*')) if p.is_file()], indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
