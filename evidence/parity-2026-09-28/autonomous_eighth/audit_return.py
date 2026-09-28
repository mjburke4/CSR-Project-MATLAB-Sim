#!/usr/bin/env python3
"""Verify the actual J owner return without executing MATLAB or changing guards."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
ISSUED = ROOT / 'autonomous_seventh/kit/autocase'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text())


def main():
    archive = ROOT / 'upload/out_auto_20260928_075726.zip'
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
    assert len(manifest['files']) == 322
    assert not report['error_identifier'] and report['import_preflight']['passed']
    passed = {}
    for field, count in [('key_request_preflight', 7), ('check_gate_preflight', 8),
                         ('population_preflight', 6), ('route_admission_preflight', 8),
                         ('request_wire_preflight', 6), ('no_path_wire_preflight', 3),
                         ('discovery_identity_preflight', 7)]:
        pre = report[field]
        assert pre['passed'] and len(pre['checks']) == count
        assert all(r['passed'] for r in pre['checks'])
        passed[field] = count
    reuse = report['accepted_natural_reuse']
    assert all(reuse[k] for k in ['reused', 'runtime_matches', 'configuration_matches',
                                'prefix_gate_recomputed'])
    assert not reuse['fresh_natural_simulation_executed']
    for name in ['protocol_trace.csv', 'phy_trace.csv', 'application_admission_trace.csv']:
        assert (DATA / 'A_natural' / name).read_bytes() == (ISSUED / 'ref/matlab' / name).read_bytes()
    folder = DATA / 'J_discovery_identity'
    item = read(folder / 'case_summary.json')
    summary = read(folder / 'random_summary.json')
    requests = [json.loads(s) for s in (folder / 'random_requests.jsonl').read_text().splitlines()]
    assert len(requests) == 759
    assert all(r['context_matched'] for r in requests[:-1])
    assert not requests[-1]['context_matched']
    assert all(r['value'] == r['expected']['value'] for r in requests[:-1])
    assert sum(r['consumed'] for r in summary['counts']) == 758
    assert summary['native_transmissions_checked'] == 129 and summary['first_time_difference'] == []
    events = [json.loads(s) for s in (folder / 'ordered_events.jsonl').read_text().splitlines()]
    tx = [r for r in events if r['kind'] == 'physical_tx_context']
    assert len(tx) == 129 and all(not r['details']['mismatches'] for r in tx)
    repaired = [r for r in tx if r['details']['native_semantic_tx_id'] == 12884901905]
    assert len(repaired) == 1
    child = repaired[0]['details']['actual']['children'][2]
    identity = child['discovery_outer_sequence_identity']
    assert identity['actual'] == 1 and identity['native'] == 4
    identities = [c['discovery_outer_sequence_identity'] for r in tx
                  for c in r['details']['actual']['children']
                  if 'discovery_outer_sequence_identity' in c]
    divergence = read(folder / 'first_divergence.json')
    assert divergence['fields'] == ['bits'] and divergence['node'] == 3
    assert divergence['ordinal'] == 75 and divergence['purpose'] == 'phy_binomial'
    actual, expected = divergence['actual'], divergence['expected']
    assert actual['bits'] == 52 and expected['bits'] == 51
    for key in ['tx_id', 'interval_ordinal', 'interval_start_ns', 'interval_end_ns',
                'component', 'component_start_ns', 'component_end_ns', 'probability']:
        assert actual[key] == expected[key], key
    observer = read(folder / 'observer_status.json')
    timing = read(folder / 'transport_timing_summary.json')
    assert observer['Complete'] and observer['OmittedServiceRecords'] == 0
    assert timing['Mode'] == 'nanoseconds' and timing['Omitted'] == 0
    raw = {}
    for name in ['protocol_trace.csv', 'phy_trace.csv', 'application_admission_trace.csv']:
        with (folder / name).open() as f:
            raw[name] = sum(1 for _ in csv.DictReader(f))
    assert raw['application_admission_trace.csv'] == 0
    result = dict(
        schema='csr-autonomous-discovery-identity-return-v1', status='pass',
        archive=archive.name, archive_sha256=sha(archive), archive_members=members,
        issued_manifest_sha256=sha(ISSUED / 'FILES.json'), issued_bound_files=len(manifest['files']),
        runtime=report['runtime'], import_preflight_passed=True,
        matlab_passed_component_checks=passed, accepted_natural_reused=True,
        case=dict(name='J_discovery_identity', endpoint_s=item['reached_time_s'],
                  requests_consumed_matched=758, rejected_requests=1,
                  consumed_by_purpose=dict(Counter(r['purpose'] for r in requests[:-1])),
                  verified_transmissions=129, first_time_difference=[],
                  previous_discovery_identity_guard_cleared=True,
                  discovery_identity_annotations=len(identities),
                  discovery_different_outer_identifiers=sum(x['actual'] != x['native'] for x in identities),
                  raw_rows=raw, ordered_event_rows=len(events),
                  timing_records=timing['Count'], service_records=observer['CapturedServiceRecords'],
                  wall_seconds=item['wall_seconds'], stop_fields=divergence['fields'],
                  actual_bits=52, native_bits=51),
        target_percent=15, network_parity_established=False,
        scope='Startup ends before applications begin at 300 seconds; unfinished traffic and 6000-second parity remain open.')
    (HERE / 'return_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    (HERE / 'return_input_manifest.json').write_text(json.dumps([
        dict(path=p.relative_to(DATA).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(DATA.rglob('*')) if p.is_file()], indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
