#!/usr/bin/env python3
"""Verify the actual two-case return without running either network."""
from pathlib import Path
import collections
import csv
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
ISSUED = ROOT / 'autonomous_third/kit/autocase'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text())


def main():
    archive = ROOT / 'upload/out_auto_20260925_133710.zip'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        members = len(z.namelist())
    report = read(DATA / 'report.json')
    provenance = read(DATA / 'provenance.json')
    manifest = read(ISSUED / 'FILES.json')
    assert provenance['manifest'] == manifest
    for row in manifest['files']:
        assert sha(ISSUED / row['path']) == row['sha256'], row['path']
    assert not report['error_identifier']
    assert report['import_preflight']['passed']
    key = report['key_request_preflight']
    assert key['passed'] and len(key['checks']) == 7 and all(r['passed'] for r in key['checks'])
    assert report['accepted_natural_reuse']['reused']
    assert report['accepted_natural_reuse']['prefix_gate_recomputed']
    for name in ['protocol_trace.csv', 'phy_trace.csv', 'application_admission_trace.csv']:
        assert (DATA / 'A_natural' / name).read_bytes() == (ISSUED / 'ref/matlab' / name).read_bytes()
    cases = []
    for name in ['C_timing', 'D_inline_key']:
        folder = DATA / name
        item = read(folder / 'case_summary.json')
        assert item['diagnostic_status'] == 'context_divergence'
        assert item['error_identifier'] == 'autocase:TxContextDivergence'
        assert item['reached_time_s'] == 12.402
        requests = [json.loads(s) for s in (folder / 'random_requests.jsonl').read_text().splitlines()]
        summary = read(folder / 'random_summary.json')
        assert len(requests) == 40 and all(r['context_matched'] for r in requests)
        assert all(r['value'] == r['expected']['value'] for r in requests)
        assert summary['draw_count'] == 40 and summary['native_transmissions_checked'] == 6
        previous_stop = [r for r in requests if r['node'] == 4 and r['purpose'] == 'phy_binomial' and r['ordinal'] == 2]
        assert len(previous_stop) == 1
        phy = previous_stop[0]
        assert phy['expected']['bits'] == 183
        divergence = read(folder / 'first_divergence.json')
        assert divergence['fields'] == ['parent.child_count', 'parent.total_wire_bytes', 'ordered_child_count']
        assert divergence['actual']['child_count'] == 3 and divergence['actual']['total_wire_bytes'] == 66
        assert all(r['child_count'] == 4 and r['total_wire_bytes'] == 82 for r in divergence['expected'])
        observed = read(folder / 'observer_status.json')
        assert observed['Complete'] and observed['OmittedServiceRecords'] == 0
        timing = read(folder / 'transport_timing_summary.json')
        assert timing['Mode'] == 'nanoseconds' and timing['Omitted'] == 0
        raw = {}
        for fn in ['protocol_trace.csv', 'phy_trace.csv', 'application_admission_trace.csv']:
            with (folder / fn).open() as f:
                raw[fn] = sum(1 for _ in csv.DictReader(f))
        assert raw['application_admission_trace.csv'] == 0
        cases.append({'name': name, 'endpoint_s': item['reached_time_s'], 'status': item['diagnostic_status'],
                      'matched_samples': len(requests), 'samples_by_purpose': dict(collections.Counter(r['purpose'] for r in requests)),
                      'verified_transmissions': 6, 'attempted_transmissions': 7,
                      'prior_payload_bits': phy['expected']['bits'],
                      'first_time_difference': summary['first_time_difference'],
                      'actual_children': 3, 'native_children': 4, 'actual_wire_bytes': 66, 'native_wire_bytes': 82,
                      'raw_rows': raw, 'timing_records': timing['Count'], 'service_records': observed['CapturedServiceRecords'],
                      'wall_seconds': item['wall_seconds']})
    result = {'schema': 'csr-autonomous-control-timing-return-v1', 'status': 'pass',
              'archive': archive.name, 'archive_sha256': sha(archive), 'archive_members': members,
              'issued_manifest_sha256': sha(ISSUED / 'FILES.json'), 'issued_bound_files': len(manifest['files']),
              'runtime': report['runtime'], 'import_preflight_passed_in_matlab': True,
              'key_preflight_checks_passed_in_matlab': 7, 'accepted_natural_reused': True, 'cases': cases,
              'target_percent': 15, 'network_parity_established': False,
              'scope': 'Actual startup captures stop before application traffic begins at 300 seconds.'}
    (HERE / 'return_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    (HERE / 'return_input_manifest.json').write_text(json.dumps([
        {'path': p.relative_to(DATA).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
        for p in sorted(DATA.rglob('*')) if p.is_file()], indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
