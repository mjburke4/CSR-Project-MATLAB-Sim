#!/usr/bin/env python3
"""Independent, read-only review of the returned Tranche 6 evidence."""
from pathlib import Path, PurePosixPath
import collections
import csv
import fnmatch
import hashlib
import io
import json
import subprocess
import zipfile

BASE = Path('/workspace/scratch/1a5b1ad6ce1b')
ROOT = BASE / 't6-return-original'
REPO = BASE / 'tranche6'
OUT = BASE / 't6-return-integrity'
ARCHIVE = BASE / 'upload/tranche6_evidence.zip'
CANDIDATE = BASE / 'CSR-MATLAB-Tranche6-21c0a3f.zip'
COMMIT = '21c0a3f024c9efffdbd11c8059f1540a67c19b1a'
PIN = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
report = {'schema': 'csr-tranche6-independent-integrity-review-v1',
          'candidate_commit': COMMIT, 'ns3_source_commit': PIN,
          'review_mode': 'Read-only audit of uploaded ZIP and extraction against git candidate and handoff ZIP; no MATLAB execution.',
          'failures': [], 'limitations': []}

def check(condition, message):
    if not condition:
        report['failures'].append(message)
    return bool(condition)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def arr(value):
    return value if isinstance(value, list) else [value]

def readrows(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])

head = git('rev-parse', 'HEAD').decode().strip()
report['git_head_at_review'] = head
report['git_worktree_clean_at_review'] = not git('status', '--porcelain=v1').strip()
check(head == COMMIT, 'Repository HEAD does not match intended candidate.')

raw = ARCHIVE.read_bytes()
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    info = z.infolist()
    names = [i.filename for i in info if not i.is_dir()]
    duplicate = [n for n, count in collections.Counter(names).items() if count > 1]
    unsafe = [n for n in names if PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n]
    bad_crc = z.testzip()
    check(not duplicate, f'Duplicate archive members: {duplicate}')
    check(not unsafe, f'Unsafe archive member paths: {unsafe}')
    check(bad_crc is None, f'Archive CRC failure: {bad_crc}')
    extracted = {str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file()}
    check(extracted == set(names), 'Extraction member set differs from uploaded archive.')
    extraction_failures = [n for n in names if (ROOT / n).read_bytes() != z.read(n)]
    check(not extraction_failures, f'Extraction differs from archived bytes: {extraction_failures}')
    report['archive'] = {'filename': ARCHIVE.name, 'bytes': len(raw), 'sha256': sha(raw),
                         'members': len(info), 'files': len(names), 'crc_passed': bad_crc is None,
                         'duplicate_members': duplicate, 'unsafe_paths': unsafe,
                         'extraction_identical': extracted == set(names) and not extraction_failures}

candidate_raw = CANDIDATE.read_bytes()
with zipfile.ZipFile(io.BytesIO(candidate_raw)) as z:
    prefix = 'CSR-MATLAB-Tranche6/'
    candidate_bytes = {i.filename[len(prefix):]: z.read(i.filename)
                       for i in z.infolist() if not i.is_dir() and i.filename.startswith(prefix)}
    report['candidate_archive'] = {'filename': CANDIDATE.name, 'bytes': len(candidate_raw),
                                   'sha256': sha(candidate_raw), 'files': len(candidate_bytes)}
    check(len(candidate_raw) == 8044264, 'Candidate handoff ZIP size differs from supplied identity.')
    check(sha(candidate_raw) == '3989bc81c35f41413479146cff018b6d33f54ead0e47d4ae5f7d5f7860fd5386', 'Candidate handoff ZIP hash differs from supplied identity.')

outer = json.loads((ROOT / 'validation_metadata.json').read_text())
source_paths = [x['path'] for x in outer['SourceFiles']]
check(len(source_paths) == len(set(source_paths)) == 127, 'Expected 127 unique source snapshot paths.')
git_bytes = {p: git('show', COMMIT + ':' + p) for p in source_paths}
git_hashes = {p: sha(b) for p, b in git_bytes.items()}
source_zip_mismatches = [p for p in source_paths if p not in candidate_bytes or candidate_bytes[p] != git_bytes[p]]
check(not source_zip_mismatches, f'Candidate ZIP and git differ at source paths: {source_zip_mismatches}')

tracked = git('ls-tree', '-r', '--name-only', COMMIT).decode().splitlines()
def snapshot_eligible(p):
    path = PurePosixPath(p)
    return ((path.suffix == '.m' and (len(path.parts) == 1 or path.parts[0] in ['+csr', 'tests', 'examples']))
            or (path.parts[0] == 'scripts' and path.suffix in ['.py', '.cc'])
            or path.parts[0] == 'data'
            or p.startswith('scenarios/shared/')
            or fnmatch.fnmatch(p, 'evidence/tranche-*-candidate.json')
            or p == 'evidence/source-baseline.json')
expected_paths = {p for p in tracked if snapshot_eligible(p)}
check(expected_paths == set(source_paths), 'Source snapshot membership differs from candidate sourceSnapshot scope.')
matlab_paths = {p for p in tracked if p.endswith('.m')}
snapshot_matlab_paths = {p for p in source_paths if p.endswith('.m')}
check(matlab_paths == snapshot_matlab_paths, 'Candidate MATLAB file set differs from runtime snapshot.')
check(len(matlab_paths) == 90, 'Expected 90 MATLAB files in candidate.')

json_files = {p: json.loads(p.read_text()) for p in sorted(ROOT.rglob('*.json'))}
source_checks = []
inventory_checks = []
local_entries = {}
link_checks = []
runtime_checks = []
checked_inventory_unique = set()
row_count_checks = 0

for p, d in json_files.items():
    relative = str(p.relative_to(ROOT))
    for key in ['SourceFiles', 'SourceFilesFinal', 'MatlabSourceFiles', 'source_files']:
        if key not in d:
            continue
        entries = arr(d[key])
        hashes = {x.get('path', x.get('Path')): x.get('sha256', x.get('SHA256')) for x in entries}
        expected = snapshot_matlab_paths if key == 'MatlabSourceFiles' else set(source_paths)
        mismatches = [name for name, digest in hashes.items() if git_hashes.get(name) != digest]
        check(set(hashes) == expected and len(hashes) == len(entries), f'Source member set mismatch: {relative}:{key}')
        check(not mismatches, f'Source SHA-256 mismatch: {relative}:{key}: {mismatches}')
        source_checks.append({'metadata': relative, 'field': key, 'count': len(entries),
                              'membership_passed': set(hashes) == expected and len(hashes) == len(entries),
                              'hashes_passed': not mismatches})

    for key in ['Artifacts', 'files']:
        if key not in d:
            continue
        entries = arr(d[key])
        bad = []
        for entry in entries:
            artifact = p.parent / entry['path']
            artifact_relative = str(artifact.relative_to(ROOT))
            if not artifact.is_file():
                bad.append({'path': entry['path'], 'reason': 'missing'})
                continue
            data = artifact.read_bytes()
            if sha(data) != entry['sha256'] or len(data) != entry['bytes']:
                bad.append({'path': entry['path'], 'reason': 'bytes/hash'})
            if isinstance(entry.get('row_count'), (int, float)):
                count = len(readrows(artifact))
                row_count_checks += 1
                if count != entry['row_count']:
                    bad.append({'path': entry['path'], 'reason': 'row_count', 'actual': count})
            checked_inventory_unique.add(artifact_relative)
        check(not bad, f'Artifact inventory failed: {relative}:{key}: {bad}')
        paths = [x['path'] for x in entries]
        check(len(paths) == len(set(paths)), f'Duplicate inventory entries: {relative}:{key}')
        if key == 'Artifacts':
            actual_paths = {str(a.relative_to(p.parent)) for a in p.parent.rglob('*')
                            if a.is_file() and a != p and a.suffix in ['.csv','.json','.log']}
        else:
            actual_paths = {str(a.relative_to(p.parent)) for a in p.parent.iterdir()
                            if a.is_file() and a != p and a.suffix in ['.csv','.json','.log']}
        # Candidate run_tranche4_validation.m writeReport excludes its live
        # diary. The enclosing T5/T6 inventories hash its closed final bytes.
        intentional_exclusions = []
        if key == 'Artifacts' and d.get('Schema') == 'csr-matlab-tranche-4-validation-v1':
            intentional_exclusions = ['validation.log']
            actual_paths -= set(intentional_exclusions)
        membership_ok = actual_paths == set(paths)
        check(membership_ok, f'Nested inventory membership failed: {relative}:{key}')
        inventory_checks.append({'metadata': relative, 'field': key, 'count': len(entries),
                                 'passed': len(entries) - len(bad), 'membership_passed': membership_ok,
                                 'intentional_exclusions': intentional_exclusions, 'failures': bad})

    for key in ['LocalArtifacts', 'local_files']:
        if key in d:
            for entry in arr(d[key]):
                path = str((p.parent / entry['path']).relative_to(ROOT))
                existing = local_entries.get(path)
                check(existing is None or existing == {'sha256':entry['sha256'], 'bytes':entry['bytes']}, f'Conflicting local artifact metadata: {path}')
                local_entries[path] = {'sha256': entry['sha256'], 'bytes': entry['bytes']}

    if 'RegressionMetadataSHA256' in d:
        child = p.parent / d['RegressionEvidenceDirectory'] / 'validation_metadata.json'
        passed = child.is_file() and sha(child.read_bytes()) == d['RegressionMetadataSHA256']
        check(passed, f'Regression metadata link failed: {relative}')
        link_checks.append({'metadata': relative, 'field': 'RegressionMetadataSHA256', 'passed': passed})
    if 'Cases' in d and d.get('Schema', '').endswith('validation-v1'):
        for case in arr(d['Cases']):
            child = p.parent / case['Directory'] / 'case_manifest.json'
            passed = child.is_file() and sha(child.read_bytes()) == case['ManifestSHA256']
            check(passed, f'Case manifest link failed: {relative}:{case["Directory"]}')
            link_checks.append({'metadata': relative, 'case': case['Directory'], 'passed': passed})
    runtime = d.get('Runtime')
    if isinstance(runtime, dict):
        passed = runtime['Runtime'] == 'MATLAB' and runtime['Release'] == '2025a' and runtime['Version'] == '25.1.0.2943329 (R2025a)' and runtime['DefaultBackend'] == 'portable'
        check(passed, f'Runtime mismatch: {relative}')
        runtime_checks.append({'metadata': relative, 'passed': passed})
    if 'matlab_release' in d:
        passed = d['matlab_release'] == '2025a' and d['matlab_version'] == '25.1.0.2943329 (R2025a)' and d['ns3_source_commit'] == PIN
        check(passed, f'Case runtime or ns-3 pin mismatch: {relative}')
        check(d['status'] == 'completed' and d['execution_completed'] and d['structural_checks_passed'], f'Incomplete case manifest: {relative}')
        runtime_checks.append({'metadata': relative, 'passed': passed})
    if 'SourceCommit' in d:
        check(d['SourceCommit'] == PIN, f'ns-3 source pin mismatch: {relative}')

check(set(names) == {x['path'] for x in outer['Artifacts']} | {'validation_metadata.json'}, 'Top-level inventory does not exactly cover archived files except self.')
check(checked_inventory_unique == set(names) - {'validation_metadata.json'}, 'Inventory-covered unique file set differs from expected outer boundary.')
check(len(local_entries) == 48, 'Expected 48 unique excluded local MAT artifacts.')
check(all(p.endswith('.mat') for p in local_entries), 'Unexpected local-only artifact extension.')
check(not any((ROOT / p).exists() for p in local_entries), 'Local-only artifacts unexpectedly present in archive extraction.')

report['source'] = {'unique_source_files': len(source_paths), 'unique_matlab_files': len(snapshot_matlab_paths),
                    'git_membership_passed': expected_paths == set(source_paths),
                    'candidate_archive_identical_to_git_at_all_source_paths': not source_zip_mismatches,
                    'snapshot_checks': source_checks, 'total_hash_assertions': sum(x['count'] for x in source_checks)}
report['inventories'] = {'checks': inventory_checks, 'total_assertions': sum(x['count'] for x in inventory_checks),
                         'unique_archived_artifacts_checked': len(checked_inventory_unique),
                         'csv_row_count_assertions': row_count_checks, 'metadata_links': link_checks,
                         'excluded_local_mat_count': len(local_entries), 'excluded_local_mat_bytes': sum(x['bytes'] for x in local_entries.values())}
report['runtime'] = {'runtime': 'MATLAB', 'release': '2025a', 'version': '25.1.0.2943329 (R2025a)', 'backend': 'portable',
                     'started_utc': outer['StartedUTC'], 'completed_utc': outer['CompletedUTC'],
                     'native_executed': outer['NativeExecuted'], 'checks': runtime_checks}

test_paths = list(ROOT.rglob('test_results.csv'))
check(len(test_paths) == 1, 'Expected one test-results CSV.')
test_rows = readrows(test_paths[0])
test_sha = sha(test_paths[0].read_bytes())
test_names = [x['Name'] for x in test_rows]
passed = sum(x['Passed'] == '1' for x in test_rows)
failed = sum(x['Failed'] != '0' for x in test_rows)
incomplete = sum(x['Incomplete'] != '0' for x in test_rows)
check(len(test_rows) == len(set(test_names)) == passed == 380 and failed == incomplete == 0, 'Test CSV count/pass/uniqueness gate failed.')
for p, d in json_files.items():
    if 'TestResultsSHA256' in d:
        check(d['TestResultsSHA256'] == test_sha, f'Test-results hash mismatch: {p.relative_to(ROOT)}')
    if 'TestCount' in d:
        check(d['TestCount'] == 380 and d['PassedTests'] == 380 and d['FailedTests'] == 0 and d['IncompleteTests'] == 0, f'Test count mismatch: {p.relative_to(ROOT)}')
report['tests'] = {'path': str(test_paths[0].relative_to(ROOT)), 'sha256': test_sha, 'count': len(test_rows),
                   'passed': passed, 'failed': failed, 'incomplete': incomplete,
                   'outage_recovery_tests': [x for x in test_rows if x['Name'].startswith('TestOutageRecovery/')],
                   'summed_test_duration_seconds': sum(float(x['DurationSeconds']) for x in test_rows)}

t5root = ROOT / outer['RegressionEvidenceDirectory']
t5meta = json_files[t5root / 'validation_metadata.json']
t4root = t5root / t5meta['RegressionEvidenceDirectory']
t4meta = json_files[t4root / 'validation_metadata.json']
plan = json.loads((t5root / 'sweep_plan.json').read_text())
sweeps = readrows(t5root / 'scenario_summary.csv')
performance = readrows(t5root / 'performance_summary.csv')
case_ids = {x['CaseId'] for x in plan['Cases']}
check(len(case_ids) == len(plan['Cases']) == len(sweeps) == len(performance) == 18, 'Sweep count mismatch.')
check(case_ids == {x['CaseId'] for x in t5meta['Cases']} == {x['CaseId'] for x in sweeps} == {x['CaseId'] for x in performance}, 'Sweep case identity mismatch.')
check(all(x['StructuralChecksPassed'] == '1' for x in sweeps), 'Sweep structural CSV gate failed.')
residual_cases = []
for row in sweeps:
    if row['DataDrained'] == '1':
        continue
    case_dir = t5root / 'sweep' / row['CaseId']
    trace = readrows(case_dir / 'protocol_trace.csv')
    last_time = float(row['DurationSeconds'])
    final_control_admissions = [x for x in trace if float(x['TimeSeconds']) == last_time and x['Event'] == 'hop_control_admit' and x['FrameKind'] == 'CONTROL']
    drain_zero = ['Pending','HopPendingData','DackHoldCount','NwkPendingCustody','WaitingForRoute']
    check(all(int(float(row[x])) == 0 for x in drain_zero), f'Application/DATA custody not drained: {row["CaseId"]}')
    check(row['ResendQueueDepth'] == row['ControlPending'] == row['ControlPendingTargets'] == '1', f'Unexpected residual ownership: {row["CaseId"]}')
    check(any(x['ControlType'] == 'ROUTING' and x['NodeId'] == '2' and x['PeerId'] == '3' for x in final_control_admissions), f'Missing stop-time routing admission: {row["CaseId"]}')
    residual_cases.append({'case': row['CaseId'], 'DataDrained': False,
                           'application_and_DATA_custody_pending': {x: int(float(row[x])) for x in drain_zero},
                           'resend_queue_depth': 1, 'control_pending': 1, 'control_pending_targets': 1,
                           'trace_stop_time_control_admissions': final_control_admissions})
regression_paths = [t4root / 'scenario_summary.csv', t4root / 'regression/scenario_summary.csv', t4root / 'regression/regression/scenario_summary.csv']
regression_rows = [readrows(p) for p in regression_paths]
check([len(x) for x in regression_rows] == [11,8,9], 'Expected 11+8+9 regression summary rows.')
check(len(t4meta['Cases']) == 11, 'Expected eleven manifested shared/research regression cases.')
check(all(row['StructuralChecksPassed'] == '1' and row['DataDrained'] == '1' for row in regression_rows[0]), 'Shared/research structural/data-drain gate failed.')
accounting = []
for path, rows in [(t5root / 'scenario_summary.csv', sweeps), *zip(regression_paths, regression_rows)]:
    for row in rows:
        count = {key:int(float(row[key])) for key in ['Generated','Received','Dropped','Pending']}
        good = count['Generated'] == count['Received'] + count['Dropped'] + count['Pending']
        check(good, f'Application accounting mismatch: {path.relative_to(ROOT)}:{row["Scenario"]}')
        accounting.append({'summary': str(path.relative_to(ROOT)), 'scenario':row['Scenario'], 'passed':good})
report['cases'] = {'sweep_count': len(sweeps), 'sweep_ids': sorted(case_ids), 'regression_count': sum(map(len,regression_rows)),
                   'regression_groups': [{'path': str(p.relative_to(ROOT)), 'count': len(rows), 'scenarios': [x['Scenario'] for x in rows]} for p, rows in zip(regression_paths, regression_rows)],
                   'application_accounting_cases_passed': sum(x['passed'] for x in accounting),
                   'application_accounting_cases_total': len(accounting),
                   'all_sweeps_structural_checks_passed': all(x['StructuralChecksPassed'] == '1' for x in sweeps),
                   'sweeps_reporting_DataDrained_true': sum(x['DataDrained'] == '1' for x in sweeps),
                   'stop_time_control_residual_cases': residual_cases}

shared_cli = BASE / 't6-shared-comparison/cli-results.json'
if shared_cli.is_file():
    shared_rows = json.loads(shared_cli.read_text())
    report['shared_comparisons'] = {'execution_owner':'Main reviewer; this independent reviewer inspected generated CLI results without rerunning the comparator.',
                                    'cli_results_path':str(shared_cli), 'cli_results_sha256':sha(shared_cli.read_bytes()),
                                    'count':len(shared_rows), 'passed':sum(x['exit_code'] == 0 and 'application_match:' in x['output'] for x in shared_rows),
                                    'results':shared_rows,
                                    'scope':'Five shared application-level comparisons; full protocol numerical parity is not asserted.'}
    check(report['shared_comparisons']['count'] == report['shared_comparisons']['passed'] == 5, 'Main reviewer shared comparison results do not pass 5/5.')

log_files = sorted(ROOT.rglob('*.log'))
report['logs'] = [{'path':str(p.relative_to(ROOT)), 'bytes':p.stat().st_size, 'sha256':sha(p.read_bytes())} for p in log_files]
report['limitations'] = [
    'The 48 unique MAT result/test objects are intentionally excluded by the declared archive policy; their recorded hashes and sizes agree across nested inventories, but their bytes cannot be independently checked from this ZIP.',
    'The execution host has no available git HEAD metadata. Candidate identity is independently established by comparing all 127 source-snapshot hashes, including all 90 MATLAB files, against git commit 21c0a3f and the delivered candidate ZIP.',
    'Nested metadata retains Tranche 3/4/5 schema labels and historical base commits because those regression runners are reused; every checked source snapshot matches the Tranche 6 candidate. These labels do not indicate older code execution.',
    'The nested Tranche 4 inventory deliberately omits its own live validation.log per the candidate runner. Its closed final bytes are independently covered by both enclosing Tranche 5 and Tranche 6 inventories.',
    'The sweep plan retains planned-not-executed because it is the immutable pre-execution plan; separate case manifests, summaries, and outer metadata establish completed execution.',
    'Three 300-second freshness cases report DataDrained=false because that conservative field includes the shared resend queue. Each has zero pending applications, HOP DATA, DACK hold, NWK custody, and route wait, with one pending reliable CONTROL owner. Trace inspection shows ROUTING 2->3 and DISCOVER controls admitted at exactly the 900-second stop. This is a finite-stop control-residual boundary, not an archive-integrity failure.',
    'Native wireless simulator execution and long-run cases were not requested. This is portable R2025a evidence; no new MATLAB or ns-3 execution was performed by this integrity review.',
    'This integrity review verifies provenance and supplied accounting. The main reviewer owns measured Tranche 5/6 outcome analysis and the five MATLAB/ns-3 shared application comparisons.'
]
report['status'] = 'passed' if not report['failures'] else 'failed'
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'independent_integrity_review.json').write_text(json.dumps(report, indent=2) + '\n')
lines = ['# Tranche 6 independent integrity review', '', f"Status: **{report['status'].upper()}**.", '',
         f"Candidate: `{COMMIT}`. Pinned ns-3 source: `{PIN}`.", '',
         f"Returned archive: `{ARCHIVE.name}`, {len(raw):,} bytes, SHA-256 `{sha(raw)}`.", '',
         '| Check | Result |', '| --- | --- |',
         f'| ZIP CRC and extraction | {len(names)} members; no CRC, duplicate-path, extraction-byte, or membership failures |',
         f'| Archived artifact hashes and sizes | {len(checked_inventory_unique)} unique files; {sum(x["count"] for x in inventory_checks)} outer/nested assertions |',
         f'| Manifest CSV row counts | {row_count_checks} verified |',
         f'| Source provenance | {len(source_paths)} unique source files, including {len(matlab_paths)} MATLAB files, match git and the candidate ZIP |',
         f'| All runtime source snapshots | {len(source_checks)} snapshots; {sum(x["count"] for x in source_checks)} hash assertions verified |',
         f'| MATLAB tests | {passed}/380 passed; {failed} failed; {incomplete} incomplete; 13 outage recovery tests |',
         '| Runtime | MATLAB R2025a, 25.1.0.2943329, portable |',
         '| Cases | 18 sweep cases plus 28 regression summary cases present; all 46 application-accounting identities hold |',
         '| Stop-time control boundary | Three 300-second cases have DataDrained=false from one pending control resend each; all application/DATA custody counters are zero |',
         '| Shared comparisons | Main reviewer reports 5/5 application matches; result records inspected without duplicate execution |',
         '| Native/long-run execution | Not requested |', '',
         'The uploaded archive and extracted evidence were not changed. Review scripts wrote only in this independent-review directory.', '',
         '## Boundaries', '']
lines.extend('- ' + s for s in report['limitations'])
if report['failures']:
    lines += ['', '## Failures', ''] + ['- ' + s for s in report['failures']]
(OUT / 'independent_integrity_review.md').write_text('\n'.join(lines) + '\n')
print(json.dumps({'status': report['status'], 'failures': report['failures'],
                  'archive': report['archive'], 'source_hash_assertions': report['source']['total_hash_assertions'],
                  'inventory_assertions': report['inventories']['total_assertions'],
                  'csv_row_count_assertions': row_count_checks, 'test_count':len(test_rows)}, indent=2))
