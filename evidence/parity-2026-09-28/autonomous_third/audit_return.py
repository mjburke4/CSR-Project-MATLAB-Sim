#!/usr/bin/env python3
"""Audit actual repaired-run acceptance, provenance and diagnostic stop."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
ISSUED = ROOT / 'autonomous_return/kit/autocase'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    archive = ROOT / 'upload/out_auto_20260925_131150.zip'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        count = len(z.namelist())
    report = json.loads((DATA / 'report.json').read_text())
    provenance = json.loads((DATA / 'provenance.json').read_text())
    manifest = json.loads((ISSUED / 'FILES.json').read_text())
    assert provenance['manifest'] == manifest
    for row in manifest['files']:
        assert sha(ISSUED / row['path']) == row['sha256'], row['path']
    assert report['import_preflight']['passed']
    assert report['accepted_natural_reuse']['reused']
    assert report['accepted_natural_reuse']['prefix_gate_recomputed']
    for name in ['protocol_trace.csv', 'phy_trace.csv', 'application_admission_trace.csv']:
        assert (DATA / 'A_natural' / name).read_bytes() == (ISSUED / 'ref/matlab' / name).read_bytes()
    rows = [json.loads(s) for s in (DATA / 'B_common/random_requests.jsonl').read_text().splitlines()]
    assert len(rows) == 7 and all(r['context_matched'] for r in rows[:6])
    assert not rows[-1]['context_matched'] and rows[-1]['value'] is None
    for row in rows[:6]:
        assert row['value'] == row['expected']['value']
    mismatch = json.loads((DATA / 'B_common/first_divergence.json').read_text())
    assert mismatch['fields'] == ['bits']
    assert mismatch['actual']['bits'] == 184 and mismatch['expected']['bits'] == 183
    summary = json.loads((DATA / 'B_common/random_summary.json').read_text())
    assert sum(r['consumed'] for r in summary['counts']) == 6
    assert summary['native_transmissions_checked'] == 1
    result = {'schema': 'csr-autonomous-coupled-return-audit-v1', 'status': 'pass',
              'archive': archive.name, 'archive_sha256': sha(archive), 'archive_members': count,
              'issued_bound_files': len(manifest['files']), 'issued_manifest_matches_return': True,
              'runtime': report['runtime'], 'import_preflight_passed_in_matlab': True,
              'accepted_natural_reuse_passed': True, 'per_channel_samples_consumed': 6,
              'requests_logged': 7, 'physical_transmissions_semantically_verified': 1,
              'first_guarded_difference': mismatch,
              'global_draw_order_parity_claimed': False,
              'global_order_note': 'See independent review: two earlier native MAC requests have not occurred in MATLAB.',
              'network_parity_established': False, 'target_percent': 15}
    (HERE / 'return_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    (HERE / 'return_input_manifest.json').write_text(json.dumps([
        {'path': str(p.relative_to(DATA)), 'bytes': p.stat().st_size, 'sha256': sha(p)}
        for p in sorted(DATA.rglob('*')) if p.is_file()], indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'first_guarded_difference'}, indent=2))


if __name__ == '__main__':
    main()
