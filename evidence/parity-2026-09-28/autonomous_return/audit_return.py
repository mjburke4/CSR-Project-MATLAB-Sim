#!/usr/bin/env python3
"""Audit the actual MATLAB return without executing a simulator."""
from pathlib import Path
import collections
import csv
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
ISSUED = ROOT / 'autonomous/kit/autocase'
ARCHIVE = ROOT / 'upload/out_auto_20260925_124644.zip'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    with zipfile.ZipFile(ARCHIVE) as z:
        assert z.testzip() is None
        archive_members = len(z.namelist())
    provenance = json.loads((DATA / 'provenance.json').read_text())
    manifest = json.loads((ISSUED / 'FILES.json').read_text())
    assert provenance['manifest'] == manifest
    assert provenance['source_transform'] == json.loads((ISSUED / 'source_transform.json').read_text())
    for row in manifest['files']:
        assert sha(ISSUED / row['path']) == row['sha256'], row['path']
    checks = []
    for name in ['protocol_trace.csv', 'phy_trace.csv', 'application_admission_trace.csv']:
        actual_path = DATA / 'A_natural' / name
        reference_path = ISSUED / 'ref/matlab' / name
        with actual_path.open(newline='') as a, reference_path.open(newline='') as b:
            actual, reference = list(csv.DictReader(a)), list(csv.DictReader(b))
        assert actual == reference, name
        checks.append({'file': name, 'rows': len(actual),
                       'csv_field_strings_equal': True,
                       'actual_sha256': sha(actual_path),
                       'reference_sha256': sha(reference_path)})
    report = json.loads((DATA / 'report.json').read_text())
    natural, common = report['cases']
    assert natural['completed'] and natural['natural_prefix_passed']
    assert common['diagnostic_status'] == 'unexpected_harness_error'
    error = json.loads((DATA / 'B_common/error.json').read_text())
    assert error['identifier'] == 'MATLAB:string:CannotConvertMissingElementToChar'
    common_random = json.loads((DATA / 'B_common/random_summary.json').read_text())
    assert common_random['draw_count'] == 0
    assert sum(row['requested'] for row in common_random['counts']) == 1
    assert sum(row['consumed'] for row in common_random['counts']) == 0
    assert common_random['native_unrequested_draws'] == 4430
    assert common_random['native_transmissions_checked'] == 0
    assert (DATA / 'B_common/random_requests.jsonl').stat().st_size == 0
    counts = collections.Counter()
    ordinals = collections.Counter()
    with (DATA / 'A_natural/random_requests.jsonl').open() as f:
        for line in f:
            row = json.loads(line)
            key = (row['node'], row['purpose'])
            ordinals[key] += 1
            assert row['ordinal'] == ordinals[key]
            counts[row['purpose']] += 1
    assert sum(counts.values()) == 4460
    summary = {'schema': 'csr-autonomous-return-audit-v1', 'status': 'pass',
               'input_archive': ARCHIVE.name, 'input_sha256': sha(ARCHIVE),
               'archive_members': archive_members,
               'issued_manifest_matches_return': True,
               'issued_bound_files': len(manifest['files']),
               'runtime': report['runtime'], 'natural_prefix_checks': checks,
               'natural_random_counts': dict(counts),
               'common_case': common,
               'common_requested_draws': 1, 'common_consumed_draws': 0,
               'common_network_comparison_available': False,
               'numeric_network_parity_established': False,
               'target_percent': 15}
    (HERE / 'return_audit.json').write_text(json.dumps(summary, indent=2) + '\n')
    inventory = [{'path': str(p.relative_to(DATA)), 'bytes': p.stat().st_size,
                  'sha256': sha(p)} for p in sorted(DATA.rglob('*')) if p.is_file()]
    (HERE / 'return_input_manifest.json').write_text(json.dumps(inventory, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
