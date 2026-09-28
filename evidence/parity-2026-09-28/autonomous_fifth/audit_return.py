#!/usr/bin/env python3
"""Verify the actual E/F owner return and its issued source identity."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
ISSUED = ROOT / 'autonomous_fourth/kit/autocase'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text())


def main():
    archive = ROOT / 'upload/out_auto_20260925_135836.zip'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        members = len(z.namelist())
    report, provenance = read(DATA / 'report.json'), read(DATA / 'provenance.json')
    manifest = read(ISSUED / 'FILES.json')
    assert provenance['manifest'] == manifest
    for row in manifest['files']:
        assert sha(ISSUED / row['path']) == row['sha256'], row['path']
    assert not report['error_identifier'] and report['import_preflight']['passed']
    for field, count in [('key_request_preflight', 7), ('check_gate_preflight', 8)]:
        pre = report[field]
        assert pre['passed'] and len(pre['checks']) == count and all(r['passed'] for r in pre['checks'])
    assert report['accepted_natural_reuse']['reused']
    assert report['accepted_natural_reuse']['prefix_gate_recomputed']
    for name in ['protocol_trace.csv', 'phy_trace.csv', 'application_admission_trace.csv']:
        assert (DATA / 'A_natural' / name).read_bytes() == (ISSUED / 'ref/matlab' / name).read_bytes()
    cases = []
    for name in ['E_check_gate', 'F_message_flag']:
        folder = DATA / name
        item = read(folder / 'case_summary.json')
        assert item['diagnostic_status'] == 'context_divergence'
        assert item['error_identifier'] == 'autocase:DrawContextDivergence'
        assert item['reached_time_s'] == 14.534
        requests = [json.loads(s) for s in (folder / 'random_requests.jsonl').read_text().splitlines()]
        summary = read(folder / 'random_summary.json')
        assert len(requests) == 97 and all(r['context_matched'] for r in requests[:96])
        assert all(r['value'] == r['expected']['value'] for r in requests[:96])
        assert not requests[-1]['context_matched'] and requests[-1]['value'] is None
        assert sum(r['consumed'] for r in summary['counts']) == 96
        assert summary['native_transmissions_checked'] == 16
        divergence = read(folder / 'first_divergence.json')
        assert divergence['fields'] == ['active_nodes'] and divergence['node'] == 1
        assert divergence['purpose'] == 'mac_slot' and divergence['ordinal'] == 8
        assert divergence['actual']['active_nodes'] == 3 and divergence['expected']['active_nodes'] == 2
        events = [json.loads(s) for s in (folder / 'ordered_events.jsonl').read_text().splitlines()]
        repaired = [r for r in events if r['kind'] == 'physical_tx_context' and
                    r['details']['native_semantic_tx_id'] == 21474836483]
        assert len(repaired) == 1 and not repaired[0]['details']['mismatches']
        assert repaired[0]['details']['actual']['child_count'] == 4
        assert repaired[0]['details']['actual']['total_wire_bytes'] == 82
        observer = read(folder / 'observer_status.json')
        timing = read(folder / 'transport_timing_summary.json')
        assert observer['Complete'] and observer['OmittedServiceRecords'] == 0
        assert timing['Mode'] == 'nanoseconds' and timing['Omitted'] == 0
        raw = {}
        for fn in ['protocol_trace.csv', 'phy_trace.csv', 'application_admission_trace.csv']:
            with (folder / fn).open() as f:
                raw[fn] = sum(1 for _ in csv.DictReader(f))
        assert raw['application_admission_trace.csv'] == 0
        cases.append({'name': name, 'endpoint_s': item['reached_time_s'], 'status': item['diagnostic_status'],
                      'requests': 97, 'consumed_matched_samples': 96,
                      'consumed_by_purpose': dict(Counter(r['purpose'] for r in requests[:96])),
                      'verified_transmissions': 16, 'first_time_difference': summary['first_time_difference'],
                      'previous_missing_frame_resolved': True,
                      'gateway_mac_population_actual': 3, 'gateway_mac_population_expected': 2,
                      'raw_rows': raw, 'ordered_event_rows': len(events), 'timing_records': timing['Count'],
                      'service_records': observer['CapturedServiceRecords'], 'wall_seconds': item['wall_seconds']})
    result = {'schema': 'csr-autonomous-neighbor-return-v1', 'status': 'pass',
              'archive': archive.name, 'archive_sha256': sha(archive), 'archive_members': members,
              'issued_manifest_sha256': sha(ISSUED / 'FILES.json'), 'issued_bound_files': len(manifest['files']),
              'runtime': report['runtime'], 'import_preflight_passed_in_matlab': True,
              'key_preflight_checks_passed_in_matlab': 7, 'neighbor_preflight_checks_passed_in_matlab': 8,
              'accepted_natural_reused': True, 'cases': cases,
              'target_percent': 15, 'network_parity_established': False,
              'scope': 'Actual startup captures stop before application traffic begins at 300 seconds.'}
    (HERE / 'return_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    (HERE / 'return_input_manifest.json').write_text(json.dumps([
        {'path': p.relative_to(DATA).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
        for p in sorted(DATA.rglob('*')) if p.is_file()], indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
