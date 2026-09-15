#!/usr/bin/env python3
"""Reproduce the read-only reporting-repair gate without executing tests again."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

BASE = Path('/workspace/scratch/1a5b1ad6ce1b')
ROOT, FROZEN, QA = BASE/'csr9', BASE/'t9r/src', BASE/'t9r/qa'
PIN = '99fff0381fe9621ccd76fbdce41eac9aba5a9469'
EXPECTED = {'scripts/analyze_tranche9_return.py', 'scripts/tranche9_metrics.py', 'scripts/tests/test_tranche9_return.py'}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(p):
    return json.loads(p.read_text())

snapshot = read(FROZEN/'evidence/tranche-9-local-checks/source-snapshot.json')
if isinstance(snapshot, dict):
    raise ValueError('Unexpected candidate snapshot schema; inspect explicitly')
matlab = [x['path'] for x in snapshot if x['path'].endswith('.m')]
assert len(matlab) == 115
assert all((ROOT/p).read_bytes() == (FROZEN/p).read_bytes() for p in matlab)
code = [x['path'] for x in snapshot if x['path'].endswith(('.m', '.py', '.cc', '.h'))]
modified = {p for p in code if (ROOT/p).read_bytes() != (FROZEN/p).read_bytes()}
assert modified == EXPECTED, modified
python_result, review_result = (read(BASE/'t9r'/n) for n in ('python-result.json', 'review-result.json'))
assert python_result['exit_code'] == review_result['exit_code'] == 0
assert '--source-root' in review_result['command'] and str(FROZEN) in review_result['command']
test_log = (BASE/'t9r/python-tests.log').read_text()
assert 'Ran 254 tests' in test_log and '\nOK\n' in test_log
review = read(BASE/'t9r/r3/review.json')
assert review['status'] == 'structural_review_completed' and review['default_structural_gate_completed'] is True
assert review['uploaded_zip_sha256'] == 'ddcede0a83b5ff906a7736f63406fc4cecb11e841795e39e93237364e0e11edf'
assert review['source_files_verified'] == 206 and review['reference_files_verified'] == 294
assert review['source_snapshot_sha256'] == '657b84111d5dadf7e8099b1f28f26865b2a7c55f551e83f50d81623dbf1bf7b5'
anchors = []
with zipfile.ZipFile(BASE/'upload/tranche9_evidence.zip') as current, zipfile.ZipFile(FROZEN/'evidence/tranche-8-r2025a-accepted/tranche8_evidence.zip') as old:
    plan = json.loads(current.read('diagnostic_plan.json'))
    for case in plan['cases']:
        key = case['storage_key']; prefix = f'b/{key}/raw/'
        before, after = (json.loads(z.read(prefix+'summary.json')) for z in (old, current))
        paths = [obj['Config']['SharedScenario'].pop('SourcePath') for obj in (before, after)]
        assert before['Config'] == after['Config']
        assert all(p.replace('\\', '/').endswith('/'+case['scenario_file']) for p in paths)
        assert before['Config']['SharedScenario']['SourceSHA256'] == case['scenario_sha256']
        count_fields = ('Generated', 'Received', 'Dropped', 'Pending')
        assert all(before['Statistics'][n] == after['Statistics'][n] for n in count_fields)
        anchors.append({'key': key, 'only_config_difference': 'SharedScenario.SourcePath', 'before_path': paths[0], 'after_path': paths[1], 'input_sha256': case['scenario_sha256'], 'application_counts_unchanged': True, 'all_statistics_exact_equal': before['Statistics'] == after['Statistics'], 'differing_statistics': {n: {'before': before['Statistics'][n], 'after': after['Statistics'][n]} for n in before['Statistics'] if before['Statistics'][n] != after['Statistics'][n]}})
receipt = {'schema': 'csr-tranche9-independent-reporting-repair-gate-v1', 'frozen_owner_candidate': PIN, 'status': 'passed',
           'repaired_code_files': {p: {'before_sha256': sha(FROZEN/p), 'after_sha256': sha(ROOT/p)} for p in sorted(EXPECTED)},
           'unchanged_matlab_files': 115, 'python_tests_reported_passed': 254, 'tests_reexecuted_by_independent_reviewer': False,
           'primary_review_exit_code': review_result['exit_code'], 'full_return_review': {'path': str(BASE/'t9r/r3/review.json'), 'sha256': sha(BASE/'t9r/r3/review.json')},
           'bound_checks': {n: sha(BASE/'t9r'/n) for n in ('python-result.json', 'python-tests.log', 'review-result.json', 'review.log')},
           't8_configuration_and_count_checks': anchors,
           'review_findings': ['Logical JSON conversion is limited to six declared logical admission fields; generic numeric identity handling still rejects booleans.', 'Only the installation prefix of SharedScenario.SourcePath may differ, and both paths must retain exact planned suffix and scenario SHA256; all other configuration fields compare exactly.', 'Ten regression tests address the two real owner-return representations and reject changed logical values, nonboolean numbers, boolean numeric identities, changed input hashes, changed seeds, wrong input filenames, and changes in other path fields.', 'Frozen original candidate remains the source-root authority for owner return; reporting repair does not retroactively change the executed MATLAB provenance.'],
           'recommendation': 'Accept the owner portable R2025a execution and the reporting-only repair. No MATLAB rerun is required for these two reviewer defects. Numerical parity and performance improvement remain unestablished.'}
(QA/'repair-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt, indent=2))
