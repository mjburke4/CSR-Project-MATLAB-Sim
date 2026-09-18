#!/usr/bin/env python3
"""Independent T22 owner-return integrity audit. No issued checker imports."""
import csv
import hashlib
import io
import json
import re
import stat
import zipfile
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'csr22'
ARCHIVE = ROOT / 'upload/t22.zip'
OUT = Path(__file__).resolve().parent
checks = []

def digest(data):
    return hashlib.sha256(data).hexdigest()

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def check(name, condition, **details):
    checks.append({'check': name, 'passed': bool(condition), **details})
    if not condition:
        raise AssertionError(name)

def rows(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))

def entries(value):
    check('distinct inventory paths', len({v['path'] for v in value}) == len(value), count=len(value))
    return {v['path']: v for v in value}

def safe(name):
    p = PurePosixPath(name)
    return bool(name) and str(p) == name and not p.is_absolute() and not any(x in ('..', '.') for x in p.parts) and '\\' not in name and ':' not in name and '\x00' not in name

with zipfile.ZipFile(ARCHIVE) as z:
    members = z.infolist()
    expected = {'candidate.json','contract/actions.csv','contract/cases.csv','contract/checkpoints.csv',
                'contract/summary.json','plan.json','references.json','run.log','source.json','tests.csv','metadata.json'}
    check('ZIP exact membership and distinct paths', len(members) == 11 and {x.filename for x in members} == expected)
    check('ZIP canonical non-symlink unencrypted regular members', all(safe(x.filename) and not x.is_dir() and not stat.S_ISLNK(x.external_attr >> 16) and not x.flag_bits & 1 for x in members))
    check('ZIP CRC integrity', z.testzip() is None)
    data = {x.filename: z.read(x) for x in members}

c = json.loads(data['candidate.json'])
m = json.loads(data['metadata.json'])
plan = json.loads(data['plan.json'])
actual_source = entries(json.loads(data['source.json']))
actual_refs = entries(json.loads(data['references.json']))
candidate_path = 'evidence/tranche-22-candidate.json'
check('issued candidate exact bytes', data['candidate.json'] == (SOURCE/candidate_path).read_bytes())
check('candidate metadata digest', digest(data['candidate.json']) == m['CandidateSHA256'])
check('source snapshot digest', digest(data['source.json']) == m['SourceSnapshotSHA256'])
check('reference snapshot digest', digest(data['references.json']) == m['ReferenceSnapshotSHA256'])
bound_source = entries(c['SourceFiles'])
check('source exact membership including candidate', actual_source == {**bound_source, candidate_path: {'path':candidate_path, 'sha256':digest(data['candidate.json'])}}, count=len(actual_source))
check('source bytes match issued installation', all(safe(p) and sha(SOURCE/p) == row['sha256'] for p,row in actual_source.items()), count=len(actual_source))
check('references exact candidate inventory', actual_refs == entries(c['ReferenceFileInventory']) and sorted(actual_refs) == c['ReferenceFiles'], count=len(actual_refs))
check('reference hashes and sizes match issued installation', all(safe(p) and (SOURCE/p).stat().st_size == r['bytes'] and sha(SOURCE/p) == r['sha256'] for p,r in actual_refs.items()), count=len(actual_refs))
check('source stable final snapshot', entries(m['SourceFilesFinal']) == actual_source and m['SourceFilesStableDuringRun'] is True)
check('reference stable final snapshot', entries(m['ReferenceFilesFinal']) == actual_refs and m['ReferenceFilesStableDuringRun'] is True)

baseline_path = SOURCE/c['BaselineSourceSnapshot']
baseline = entries(json.loads(baseline_path.read_bytes()))
check('accepted T20 baseline identity', sha(baseline_path) == '3b0fd01057f1d498759331d9db024a1fce8df5d51e1b1ba9d8d0531e96c9a428' == c['BaseSourceSnapshotSHA256'])
check('all 376 accepted T20 sources including 175 MATLAB unchanged', len(baseline) == 376 and sum(p.endswith('.m') for p in baseline) == 175 and all(actual_source.get(p) == r and sha(ROOT/'csr20'/p) == r['sha256'] for p,r in baseline.items()))
check('baseline metadata and no modified production source', m['AllBaselineSourcesUnchanged'] is True and m['BaselineSourceFilesVerified'] == 376 and m['BaselineMatlabFilesVerified'] == 175 and c['AllowedModifiedSourceFiles'] == [] and c['ProductionSourceChanged'] is False)

artifacts = entries(m['Artifacts'])
check('artifact inventory exact membership', set(artifacts) == expected-{'metadata.json'} and m['InventoryExcludedPaths'] == ['metadata.json','t22.zip'])
check('all artifact hashes and lengths', all(digest(data[p]) == r['sha256'] and len(data[p]) == r['bytes'] for p,r in artifacts.items()))
check('frozen plan bytes and digest', data['plan.json'] == (SOURCE/c['Plan']).read_bytes() and digest(data['plan.json']) == c['PlanSHA256'])
check('frozen action and case bytes', data['contract/actions.csv'] == (SOURCE/plan['actions_file']).read_bytes() and data['contract/cases.csv'] == (SOURCE/plan['cases_file']).read_bytes())

tests = rows(data['tests.csv'])
check('89 exact test methods once', len(tests) == 89 and Counter(r['Name'] for r in tests) == Counter(c['ExpectedTestNames']) and len(set(c['ExpectedTestNames'])) == 89)
check('all tests passed with no failed or incomplete', all((r['Passed'],r['Failed'],r['Incomplete']) == ('1','0','0') for r in tests))
check('test durations finite nonnegative', all(Decimal(r['DurationSeconds']).is_finite() and Decimal(r['DurationSeconds']) >= 0 for r in tests))
check('test metadata counters exact', [m[k] for k in ['TestCount','PassedTests','FailedTests','IncompleteTests']] == [89,89,0,0] and m['TestsExecuted'] is True and m['TestsPassed'] is True and m['TestFiles'] == c['TestFiles'] and m['ExpectedTestNames'] == c['ExpectedTestNames'])
test_methods = []
for p in c['TestFiles']:
    text = (SOURCE/p).read_text()
    # Each selected file places test methods before local/private helper functions.
    test_block = re.search(r'methods\s*\(Test\)(.*?)(?:\n\s*methods\b|\nend\s*$)', text, re.S)
    check('selected test class has Test methods block: '+p, test_block is not None)
    names = re.findall(r'^        function\s+(\w+)\s*\(\w+\)', test_block.group(1), re.M)
    test_methods.extend(Path(p).stem+'/'+name for name in names)
check('frozen test names match actual MATLAB test source declarations', Counter(test_methods) == Counter(c['ExpectedTestNames']), count=len(test_methods))

start = datetime.fromisoformat(m['StartedUTC'].replace('Z','+00:00'))
finish = datetime.fromisoformat(m['CompletedUTC'].replace('Z','+00:00'))
elapsed = (finish-start).total_seconds()
check('runtime MATLAB R2025a portable', m['Runtime']['Runtime'] == 'MATLAB' and m['Runtime']['Version'] == '25.1.0.2943329 (R2025a)' and m['Runtime']['Release'] == '2025a' and m['Runtime']['DefaultBackend'] == 'portable' and m['MATLABExecuted'] is True)
check('completed time and status consistent', 0 < elapsed < 3600 and m['Status'] == 'completed-review-required' and not any(k in m for k in ['Failure','InputCheckFailure','EvidencePackagingFailure']))
check('honest bounded scope flags', m['FocusedGateExecuted'] is True and m['FullAcceptanceGateExecuted'] is False and m['NumericalParityEstablished'] is False and m['NativeExecuted'] is False and m['DiagnosticOnly'] is True and c['DataQueuedRetryPolicy'] == 'actual-tx' and c['TimingPolicy'] == 'continuous' and c['FullCampusRun'] is False and c['PHYExecuted'] is False)
check('log class completion and replay entry', all(('Done '+Path(p).stem) in data['run.log'].decode() for p in c['TestFiles']) and 'Replaying the frozen action sequence against native reference states.' in data['run.log'].decode())

actual = rows(data['contract/checkpoints.csv'])
native_data = (SOURCE/c['NativeReference']).read_bytes()
native = rows(native_data)
actions = rows(data['contract/actions.csv'])
check('native checkpoint reference identity', digest(native_data) == c['NativeReferenceSHA256'])
check('exact row count and case membership', len(actual) == len(native) == len(actions) == 364 and list(dict.fromkeys(r['case_id'] for r in actual)) == plan['case_order'] and len(plan['case_order']) == 9)
check('exact checkpoint column schema', all(list(r) == plan['state_columns'] for r in actual+native))
discrete = [k for k in plan['state_columns'] if k not in ('time_s','case_id','action','packet')]
text_fields = ['case_id','action','packet']
differences = []
nonzero_time = 0
max_time = Decimal(0)
by_case = Counter()
accepted = Counter()
for idx,(a,n,action) in enumerate(zip(actual,native,actions),1):
    by_case[a['case_id']] += 1
    assert int(a['step']) == by_case[a['case_id']]
    assert all(a[k] == action[k] == n[k] for k in ['case_id','step','action','packet','peer'])
    for k in discrete:
        assert str(int(a[k])) == a[k] and str(int(n[k])) == n[k]
        if int(a[k]) != int(n[k]):
            differences.append({'row':idx,'field':k,'matlab':a[k],'native':n[k]})
    for k in text_fields:
        if a[k] != n[k]:
            differences.append({'row':idx,'field':k,'matlab':a[k],'native':n[k]})
    delta = abs(Decimal(a['time_s'])-Decimal(n['time_s']))
    max_time = max(max_time,delta)
    nonzero_time += int(delta != 0)
    assert delta <= Decimal('1e-9')
    assert abs(Decimal(a['time_s'])-Decimal(action['time_s'])) <= Decimal('1e-9')
    v = {k:int(a[k]) for k in discrete}
    accepted[a['case_id']] += int(v['accepted'] == 1)
    assert v['global_pending'] == v['resend'] + v['dack_holds']
    assert v['can_send'] == int(v['outstanding'] <= v['threshold'] and v['global_pending'] <= 16)
    assert accepted[a['case_id']] == v['ack_total'] + v['dack_total'] + v['fail_total'] + v['resend']
    assert v['nsdp_release_total'] == v['ack_total'] + v['dack_total'] + v['fail_total']
check('independent actual/native discrete and text comparison', not differences, rows=len(actual), integer_fields=len(discrete), integer_comparisons=len(actual)*len(discrete), text_comparisons=len(actual)*len(text_fields))
check('independent action alignment, timing and ownership invariants', True, maximum_time_difference_s=str(max_time), nonzero_time_differences=nonzero_time)
contract = json.loads((SOURCE/plan['contract_file']).read_bytes())
lookup = {(r['case_id'],int(r['step'])):r for r in actual}
assertions = 0
for item in contract['milestones']:
    row = lookup[(item['case_id'],item['step'])]
    for key,value in item['equals'].items():
        assert int(row[key]) == value
        assertions += 1
check('independent milestone assertions', True, milestones=len(contract['milestones']), integer_assertions=assertions)

result = {
    'schema':'csr-t22-independent-return-integrity-v1','passed':True,
    'created_utc':datetime.now(timezone.utc).isoformat(),
    'archive_sha256':sha(ARCHIVE),'archive_bytes':ARCHIVE.stat().st_size,
    'candidate_sha256':digest(data['candidate.json']),
    'source_snapshot_sha256':digest(data['source.json']),
    'reference_snapshot_sha256':digest(data['references.json']),
    'checkpoint_sha256':digest(data['contract/checkpoints.csv']),
    'checks':checks,'checks_passed':len(checks),
    'source_files':len(actual_source),'reference_files':len(actual_refs),
    'baseline_source_files':376,'baseline_matlab_files':175,
    'test_count':len(tests),'tests_passed':len(tests),
    'sum_test_duration_seconds':str(sum(Decimal(r['DurationSeconds']) for r in tests)),
    'runtime':m['Runtime'],'elapsed_seconds':elapsed,
    'case_checkpoint_counts':dict(by_case),'checkpoint_count':len(actual),
    'discrete_integer_comparisons':len(actual)*len(discrete),
    'native_state_mismatches':differences,
    'maximum_action_time_delta_s':str(max_time),'nonzero_time_differences':nonzero_time,
    'milestone_count':len(contract['milestones']),'milestone_integer_assertions':assertions,
    'limitations':['Independent audit verifies supplied owner evidence and issued-file identities; it does not independently witness MATLAB execution.', 'Controlled HOP callback replay is not a PHY, full-campus, random-stream or numerical performance parity gate.']}
(OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('checks','runtime','limitations')},indent=2))
