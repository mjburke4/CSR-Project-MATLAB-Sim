#!/usr/bin/env python3
"""Independent read-only audit; imports no project analyzer modules."""
import collections
import csv
import datetime as dt
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile

BASE = Path('/workspace/scratch/1a5b1ad6ce1b')
SOURCE = BASE / 'tranche8'
OUT = BASE / 't8_audit'
ARCHIVE = BASE / 'upload/tranche8_evidence.zip'
COMMIT = '89b62e729e588f396bb919afdff522f7e9419268'
PIN = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
EXPECTED_ARCHIVE_SHA = 'bfc4f7f05f0800316b371df3ec316f309f14e3482ef259c3f9c7bd7eea025d77'
UNCHANGED = ['trace.csv', 'protocol_trace.csv', 'phy_trace.csv', 'nodes.csv',
             'mac_nodes.csv', 'hop_nodes.csv', 'nwk_nodes.csv', 'routes.csv',
             'neighbors.csv', 'application_admission_statistics.csv',
             'application_admission_trace.csv']
failures = []
checks = collections.Counter()
inventory_counts = collections.Counter()
csv_counts = {}

def check(condition, label, group='structure'):
    checks[group] += 1
    if not condition:
        failures.append(label)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def safe(name):
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and '\\' not in name and ':' not in name and not any(x in ('', '.', '..') for x in name.split('/'))

def aslist(value):
    return value if isinstance(value, list) else [value]

def source_bytes(relative):
    return (SOURCE/relative).read_bytes()

with zipfile.ZipFile(ARCHIVE) as bundle:
    entries = bundle.infolist()
    names = [item.filename for item in entries]
    check(sha(ARCHIVE.read_bytes()) == EXPECTED_ARCHIVE_SHA, 'Upload SHA differs', 'zip')
    check(len(names) == len(set(names)), 'Duplicate ZIP entries', 'zip')
    check(len(names) == len({n.casefold() for n in names}), 'Windows case-fold ZIP collision', 'zip')
    check(all(safe(n) for n in names), 'Unsafe ZIP path', 'zip')
    check(all(not stat.S_ISLNK(item.external_attr >> 16) for item in entries), 'ZIP contains symlink', 'zip')
    check(all(not item.is_dir() and not item.flag_bits & 1 for item in entries), 'Unexpected directory/encrypted ZIP entry', 'zip')
    # Reading all entries forces every ZIP CRC check and computes an independent inventory.
    actual = {n: {'sha256': sha(bundle.read(n)), 'bytes': bundle.getinfo(n).file_size} for n in names}
    checks['zip_crc'] = len(actual)

    def j(name):
        return json.loads(bundle.read(name))

    def rows(name):
        data = bundle.read(name).decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(data, newline=''), strict=True)
        check(bool(reader.fieldnames) and len(reader.fieldnames) == len(set(reader.fieldnames)), name+': header invalid', 'csv')
        result = list(reader)
        check(all(None not in row and None not in row.values() for row in result), name+': ragged CSV', 'csv')
        csv_counts[name] = len(result)
        return result

    def inventory(prefix, declared, excluded=(), local=(), group='inventory'):
        declared = aslist(declared)
        relative_actual = {n[len(prefix):] for n in names if n.startswith(prefix)}
        expected = {e['path'] for e in declared}
        check(len(expected) == len(declared), prefix+': duplicate inventory path', group)
        check(expected == relative_actual-set(excluded), prefix+': inventory set incomplete', group)
        for e in declared:
            full = prefix+e['path']
            check(safe(e['path']) and full in actual, full+': invalid inventory path', group)
            if full not in actual:
                continue
            check(e['sha256'] == actual[full]['sha256'] and e['bytes'] == actual[full]['bytes'], full+': byte inventory mismatch', group)
            inventory_counts[group] += 1
            count = e.get('row_count')
            if count is not None and count != []:
                check(full.endswith('.csv') and len(rows(full)) == count, full+': row count mismatch', 'csv_rows')
        for e in aslist(local) if local else []:
            check(e['path'].endswith('.mat') and prefix+e['path'] not in names,
                  prefix+e['path']+': local-only MAT policy mismatch', group)

    meta = j('validation_metadata.json')
    inventory('', meta['Artifacts'], excluded=['validation_metadata.json'], local=meta['LocalArtifacts'], group='top_inventory')
    check(meta['Status'] == 'completed' and meta['Tranche'] == 8, 'Incomplete top-level validation', 'execution')
    check(meta['MATLABExecuted'] is True and meta['Runtime']['Runtime'] == 'MATLAB', 'Runtime not MATLAB', 'execution')
    check(meta['Runtime']['Version'] == '25.1.0.2943329 (R2025a)' and meta['Runtime']['Release'] == '2025a', 'Unexpected owner runtime', 'execution')
    check(meta['Runtime']['DefaultBackend'] == 'portable' and meta['NativeExecuted'] is False, 'Unexpected backend/native claim', 'execution')
    check(meta['CrossSimulatorComparisonExecuted'] is False and meta['NumericalParityEstablished'] is False, 'Owner evidence overclaims numerical parity', 'execution')
    elapsed = (dt.datetime.fromisoformat(meta['CompletedUTC'].replace('Z','+00:00'))-
               dt.datetime.fromisoformat(meta['StartedUTC'].replace('Z','+00:00'))).total_seconds()

    # Rebuild the complete source set from the frozen checkout's published glob contract.
    source_files = set()
    for pattern in ['*.m', '+csr/**/*.m', 'tests/**/*.m', 'examples/**/*.m', 'scripts/**/*.py',
                    'scripts/**/*.cc', 'scripts/**/*.h', 'data/**/*', 'scenarios/**/*',
                    'evidence/tranche-*-candidate.json', 'evidence/source-baseline.json']:
        source_files.update(p.relative_to(SOURCE).as_posix() for p in SOURCE.glob(pattern) if p.is_file())
    declared_source = {e['path']:e['sha256'] for e in meta['SourceFiles']}
    check(len(declared_source) == len(meta['SourceFiles']) and set(declared_source) == source_files, 'Source membership mismatch', 'source')
    check(meta['SourceFiles'] == meta['SourceFilesFinal'] == j('source_snapshot.json'), 'Source snapshots differ', 'source')
    check(meta['SourceFilesStableDuringRun'] is True and sha(bundle.read('source_snapshot.json')) == meta['SourceSnapshotSHA256'], 'Source snapshot binding/stability mismatch', 'source')
    for name, digest in declared_source.items():
        current = source_bytes(name)
        frozen = subprocess.check_output(['git','show',f'{COMMIT}:{name}'], cwd=SOURCE)
        check(sha(current) == digest == sha(frozen), name+': executed/current/frozen source mismatch', 'source_file')
    source_extensions = collections.Counter(Path(name).suffix for name in source_files)

    reference_trees = ['evidence/tranche-8-ns3-reference', 'evidence/tranche-7-ns3-reference', 'evidence/tranche-7-benchmark-inputs']
    reference_files = {p.relative_to(SOURCE).as_posix() for tree in reference_trees for p in (SOURCE/tree).rglob('*') if p.is_file()}
    reference_files.add('evidence/tranche-7-r2025a-accepted/tranche7_evidence.zip')
    check(meta['ReferenceFiles'] == meta['ReferenceFilesFinal'] and meta['ReferenceFilesStableDuringRun'] is True, 'Reference snapshots changed', 'reference')
    check(len(meta['ReferenceFiles']) == len(reference_files) and {e['path'] for e in meta['ReferenceFiles']} == reference_files, 'Reference membership incomplete', 'reference')
    for e in meta['ReferenceFiles']:
        raw = source_bytes(e['path'])
        check(sha(raw) == e['sha256'] and len(raw) == e['bytes'], e['path']+': reference bytes mismatch', 'reference_file')

    # Parse test method names independently from source class/method attributes.
    expected_tests = set()
    for path in sorted((SOURCE/'tests').glob('Test*.m')):
        in_test_methods = False
        method_indent = None
        class_name = re.search(r'^classdef\s+(\w+)', path.read_text(), re.M).group(1)
        for line in path.read_text().splitlines():
            match = re.match(r'^(\s*)methods\s*(?:\(([^)]*)\))?\s*(?:%.*)?$', line)
            if match:
                in_test_methods = bool(re.search(r'\bTest\b', match.group(2) or ''))
                method_indent = len(match.group(1))
            fn = re.match(r'(\s*)function\s+(\w+)\s*\(', line)
            if in_test_methods and fn and len(fn.group(1)) == method_indent+4:
                expected_tests.add(class_name+'/'+fn.group(2))
    test_rows = rows('tests/test_results.csv')
    actual_tests = [r['Name'] for r in test_rows]
    check(set(actual_tests) == expected_tests and len(actual_tests) == len(set(actual_tests)), 'Executed test membership mismatch', 'tests')
    check(len(test_rows) == 485 == meta['TestCount'] == meta['PassedTests'], 'Test counts mismatch', 'tests')
    check(all(r['Passed'] == '1' and r['Failed'] == '0' and r['Incomplete'] == '0' and math.isfinite(float(r['DurationSeconds'])) and float(r['DurationSeconds']) >= 0 for r in test_rows), 'Raw test result failure/incomplete/invalid duration', 'tests')
    check(meta['FailedTests'] == meta['IncompleteTests'] == 0 and meta['TestsRequested'] is True and meta['TestsExecuted'] is True and meta['TestsPassed'] is True, 'Test metadata mismatch', 'tests')
    log = bundle.read('validation.log').decode('utf-8-sig')
    log_classes = re.findall(r'^Done (Test\w+)$', log, re.M)
    expected_classes = {n.split('/')[0] for n in expected_tests}
    check(set(log_classes) == expected_classes and len(log_classes) == len(expected_classes), 'Closed log class membership mismatch', 'tests')
    log_dots = {}
    for match in re.finditer(r'^Running (Test\w+)\r?\n(.*?)^Done \1$', log, re.M|re.S):
        log_dots[match.group(1)] = match.group(2).count('.')
    for cls in expected_classes:
        check(log_dots.get(cls) == sum(n.startswith(cls+'/') for n in expected_tests), cls+': closed log test count mismatch', 'tests')

    plan_raw = source_bytes('scenarios/link_diagnostics/plan.json')
    plan = json.loads(plan_raw)
    check(j('diagnostic_plan.json') == plan and meta['DiagnosticPlanSHA256'] == sha(plan_raw), 'Input plan mismatch', 'plan')
    planned = plan['cases']
    check([c['seed'] for c in planned] == [s for s in range(128,133) for _ in range(2)], 'Wrong fixed seed ordering', 'plan')
    check(len(planned) == 10 == meta['PlannedCaseCount'] == meta['CompletedCaseCount'] and [c['case_id'] for c in planned] == [c['CaseId'] for c in meta['Cases']], 'Case set/order mismatch', 'plan')
    summary_rows = rows('benchmark_summary.csv')
    check(len(summary_rows) == 10 and {r['CaseId'] for r in summary_rows} == {c['case_id'] for c in planned}, 'Summary case population mismatch', 'cases')
    summaries = {r['CaseId']: r for r in summary_rows}
    case_audits = []

    for item, exported in zip(planned, meta['Cases']):
        case_id = item['case_id']
        token = ('a' if item['base_case_id'].startswith('two_') else 'c')+str(item['seed'])
        directory = 'b/'+token+'/'
        rawdir = directory+'raw/'
        check(exported['Directory']+'/' == directory and actual[directory+'benchmark_manifest.json']['sha256'] == exported['ManifestSHA256'], case_id+': case identity/manifest mismatch', 'cases')
        manifest = j(directory+'benchmark_manifest.json')
        raw_manifest = j(rawdir+'case_manifest.json')
        summary = j(rawdir+'summary.json')
        config, stats, observer = summary['Config'], summary['Statistics'], summary['LinkDiagnostics']
        check(manifest['status'] == raw_manifest['status'] == 'completed' and raw_manifest['execution_completed'] is True, case_id+': execution incomplete', 'cases')
        check(manifest['structural_checks_passed'] is True and raw_manifest['structural_checks_passed'] is True, case_id+': claimed structural failure', 'cases')
        check(manifest['source_files'] == raw_manifest['source_files'] == meta['SourceFiles'] and manifest['source_snapshot_sha256'] == meta['SourceSnapshotSHA256'], case_id+': source provenance mismatch', 'cases')
        check(manifest['ns3_source_commit'] == raw_manifest['ns3_source_commit'] == summary['Metadata']['SourceCommit'] == PIN, case_id+': ns3 pin mismatch', 'cases')
        check(manifest['runtime'] == meta['Runtime'] and raw_manifest['matlab_version'] == meta['Runtime']['Version'], case_id+': runtime identity mismatch', 'cases')
        check(manifest['scenario'] == raw_manifest['scenario'] == config['Name'] == item['scenario'] and manifest['seed'] == config['Seed'] == item['seed'] and manifest['duration_s'] == config['DurationSeconds'] == item['duration_s'], case_id+': stimulus identity mismatch', 'cases')
        check(sha(bundle.read(rawdir+'scenario.csv')) == item['scenario_sha256'] == sha(source_bytes(item['scenario_file'])) and config['SharedScenario']['SourceSHA256'] == item['scenario_sha256'], case_id+': canonical scenario mismatch', 'cases')
        check(sha(source_bytes(item['recipe_file'])) == item['recipe_sha256'] == config['SharedScenario']['OriginalSourceSHA256'], case_id+': recipe provenance mismatch', 'cases')
        inventory(directory, manifest['files'], excluded=['benchmark_manifest.json'], local=manifest['local_files'], group='benchmark_inventory')
        inventory(rawdir, raw_manifest['files'], excluded=['case_manifest.json'], local=raw_manifest['local_files'], group='raw_inventory')
        check(stats['Generated'] == stats['Received']+stats['Dropped']+stats['Pending'], case_id+': application balance mismatch', 'application')
        check(all(stats[k] == 0 for k in ['OmittedTraceRecords','OmittedPhyTraceRecords','OmittedApplicationAdmissionRecords']), case_id+': raw observations omitted', 'application')
        check(stats['Dropped'] == 0 and raw_manifest['data_drained'] is (stats['Pending'] == 0), case_id+': drop/backlog claim mismatch', 'application')
        for k in ['Generated','Received','Dropped','Pending']:
            check(int(summaries[case_id][k]) == stats[k], case_id+': summary '+k+' mismatch', 'application')

        protocol = rows(rawdir+'protocol_trace.csv')
        generated = [r for r in protocol if r['Event'] == 'app_generate']
        received = [r for r in protocol if r['Event'] == 'app_receive']
        dropped = [r for r in protocol if r['Event'] == 'app_drop']
        generated_by_id = {r['PacketId']:r for r in generated}
        received_by_id = {r['PacketId']:r for r in received}
        check(len(generated) == len(generated_by_id) == stats['Generated'] and len(received) == len(received_by_id) == stats['Received'] and len(dropped) == stats['Dropped'], case_id+': raw protocol outcomes disagree', 'application')
        check(set(received_by_id) <= set(generated_by_id), case_id+': delivery without generation', 'application')
        for packet_id,r in received_by_id.items():
            g = generated_by_id[packet_id]
            check(r['NodeId'] == g['PeerId'] and r['ApplicationBytes'] == g['ApplicationBytes'] and r['Dscp'] == g['Dscp'] and float(r['TimeSeconds']) >= float(g['TimeSeconds']), case_id+': delivery identity mismatch '+packet_id, 'delivery_identity')
        apps = rows(directory+'analysis/applications.csv')
        check(len(apps) == len(generated) and {r['PacketId'] for r in apps} == set(generated_by_id), case_id+': application table membership mismatch', 'application')
        outcomes = collections.Counter(r['Outcome'] for r in apps)
        check(outcomes['delivered'] == stats['Received'] and outcomes['pending'] == stats['Pending'] and outcomes['dropped'] == stats['Dropped'], case_id+': application table outcome mismatch', 'application')

        admission = rows(rawdir+'application_admission_trace.csv')
        admissions = rows(rawdir+'application_admission_statistics.csv')
        flows = aslist(config['Traffic'])
        check(len(admissions) == len(flows), case_id+': admission flow count mismatch', 'admission')
        attempts_per_flow = collections.Counter()
        accepted_ids = []
        reasons = collections.Counter()
        for r in admission:
            f = int(r['FlowIndex'])
            attempts_per_flow[f] += 1
            flow = flows[f-1]
            check(int(r['AttemptIndex']) == attempts_per_flow[f] and int(r['SourceId']) == flow['SourceId'], case_id+': attempt ordinal/source mismatch', 'admission_attempt')
            expected_time = Decimal(str(flow['StartSeconds']))+(int(r['AttemptIndex'])-1)*Decimal(str(flow['IntervalSeconds']))
            check(abs(Decimal(r['TimeSeconds'])-expected_time) <= Decimal('1e-8'), case_id+': attempt timing mismatch', 'admission_attempt')
            reasons[(f,r['Reason'])] += 1
            if r['Accepted'] == '1':
                accepted_ids.append(r['PacketId'])
                check(r['Reason'] == 'admitted' and r['PacketId'] in generated_by_id, case_id+': accepted attempt not generated', 'admission_attempt')
            else:
                check(r['Accepted'] == '0' and r['PacketId'] == '0' and r['Reason'] == 'nsdp_full' and int(r['NsdpCount']) >= int(r['NsdpLimit']), case_id+': unexpected denied attempt', 'admission_attempt')
        check(len(accepted_ids) == len(set(accepted_ids)) and set(accepted_ids) == set(generated_by_id), case_id+': admitted/generation identity mismatch', 'admission')
        for index,(flow,r) in enumerate(zip(flows,admissions),1):
            expected_attempts = min(flow['PacketCount'], int((Decimal(str(config['DurationSeconds']))-Decimal(str(flow['StartSeconds'])))/Decimal(str(flow['IntervalSeconds']))))
            check(attempts_per_flow[index] == int(r['Attempts']) == expected_attempts and int(r['Admitted']) == reasons[index,'admitted'] and int(r['BlockedNsdp']) == reasons[index,'nsdp_full'], case_id+': attempt partition mismatch', 'admission')
            check(all(int(r[k]) == 0 for k in ['BlockedDiscovery','BlockedTopology','BlockedGatewayRoute','BlockedDestination']), case_id+': non-NSDP blocks mismatch', 'admission')

        decisions = rows(rawdir+'link_decisions.csv')
        feedback = rows(rawdir+'actual_feedback.csv')
        check(observer == manifest['observer_diagnostics'] and observer['Complete'] is True and observer['Passive'] is True, case_id+': observer completion mismatch', 'observer')
        check(all(observer[k] == 0 for k in ['OmittedDecisionRecords','OmittedActualFeedbackRecords','UnmatchedActualFeedbackRecords','CorrelationErrors','ScheduledEvents','RandomDraws']), case_id+': observer closure failure', 'observer')
        check(len(decisions) == observer['DecisionCount'] and len(feedback) == observer['ActualFeedbackCount'], case_id+': observer raw counts mismatch', 'observer')
        check([int(r['DecisionId']) for r in decisions] == list(range(1,len(decisions)+1)) and [int(r['ObservationId']) for r in feedback] == list(range(1,len(feedback)+1)), case_id+': observer sequence identity mismatch', 'observer')
        by_id = {r['DecisionId']:r for r in decisions}
        fields = ['NodeId','PeerId','FrameKind','Sequence','HasAckWindow','AckBitmap','DackBitmap','SelectedRateKeyKbps','SelectedRateBps','SelectedPowerDbm']
        for r in feedback:
            d = by_id.get(r['DecisionId'])
            check(r['DecisionMatched'] == '1' and d is not None and all(r[k] == d[k] for k in fields) and float(r['TimeSeconds']) >= float(d['TimeSeconds']), case_id+': feedback identity mismatch', 'feedback_identity')
        case_audits.append({'case_id':case_id,'directory':directory.rstrip('/'),'generated':stats['Generated'],'delivered':stats['Received'],'dropped':stats['Dropped'],'pending':stats['Pending'],'attempts':len(admission),'decisions':len(decisions),'actual_feedback':len(feedback),'protocol_rows':len(protocol),'runtime_seconds':summary['Metadata']['RuntimeSeconds']})

    controls = j('nonperturbation.json')
    check(controls['status'] == 'completed' and controls['passed'] is True and controls['planned_control_count'] == controls['completed_control_count'] == 2, 'Control completion mismatch', 'controls')
    control_audits = []
    for r in controls['cases']:
        on,off = r['observer_on_directory']+'/',r['observer_off_directory']+'/'
        left,right = j(on+'summary.json'),j(off+'summary.json')
        check(left['Statistics'] == right['Statistics'] and left['Config'] == right['Config'], r['case_id']+': observer on/off changed statistics/config', 'controls')
        check('LinkDiagnostics' not in right and off+'link_decisions.csv' not in names and off+'actual_feedback.csv' not in names, r['case_id']+': disabled observer emitted diagnostics', 'controls')
        off_manifest = j(off+'case_manifest.json')
        check(off_manifest['source_files'] == meta['SourceFiles'] and off_manifest['execution_completed'] is True, r['case_id']+': control source/completion mismatch', 'controls')
        inventory(off, off_manifest['files'], excluded=['case_manifest.json'], local=off_manifest['local_files'], group='control_inventory')
        expected = set(UNCHANGED+['scenario.csv'])
        check(len(r['compared_files']) == len(expected) and {x['path'] for x in r['compared_files']} == expected, r['case_id']+': compared file set mismatch', 'controls')
        for e in r['compared_files']:
            check(actual[on+e['path']]['sha256'] == actual[off+e['path']]['sha256'] == e['observer_on_sha256'] == e['observer_off_sha256'] and e['equal'] is True, r['case_id']+': byte-exact control mismatch '+e['path'], 'control_csv')
        control_audits.append({'case_id':r['case_id'],'statistics_equal':True,'config_equal':True,'byte_exact_csv_files':len(expected)})

    # Compare to the accepted T7 archive with exact numeric IDs and small floating export tolerance.
    t7 = SOURCE/plan['baseline_anchor']['archive']
    check(sha(t7.read_bytes()) == plan['baseline_anchor']['archive_sha256'] == 'ea39b86ef68f91a551e4e22d176e2e96dc5305f33673741eee0adc6039599655', 'T7 acceptance archive mismatch', 't7_anchor')
    anchor_audits = []
    with zipfile.ZipFile(t7) as old:
        for item in planned:
            if item['seed'] != 128:
                continue
            token = 'a128' if item['base_case_id'].startswith('two_') else 'c128'
            prefix = 'benchmarks/'+item['base_case_id']+'/raw/'
            new_prefix = 'b/'+token+'/raw/'
            old_stats = json.loads(old.read(prefix+'summary.json'))['Statistics']
            check(old_stats == j(new_prefix+'summary.json')['Statistics'], item['case_id']+': T7 complete statistics differ', 't7_anchor')
            file_audits = []
            for name in UNCHANGED:
                old_reader = csv.reader(io.StringIO(old.read(prefix+name).decode('utf-8-sig'),newline=''),strict=True)
                new_reader = csv.reader(io.StringIO(bundle.read(new_prefix+name).decode('utf-8-sig'),newline=''),strict=True)
                check(next(old_reader) == next(new_reader), name+': T7 CSV headers differ', 't7_anchor')
                count = 0
                numeric_reformatted = 0
                for old_row,new_row in itertools.zip_longest(old_reader,new_reader):
                    count += 1
                    check(old_row is not None and new_row is not None and len(old_row) == len(new_row), name+': T7 CSV rows differ', 't7_anchor_rows')
                    if old_row is None or new_row is None:
                        continue
                    for x,y in zip(old_row,new_row):
                        if x == y:
                            continue
                        try:
                            dx,dy = Decimal(x),Decimal(y)
                            if dx.is_nan() and dy.is_nan():
                                equal = True
                            elif dx.is_finite() and dy.is_finite():
                                integral = (dx == dx.to_integral_value() and dy == dy.to_integral_value()) or max(abs(dx),abs(dy)) >= 2**53
                                equal = dx == dy if integral else abs(dx-dy) <= max(Decimal('1e-9'),Decimal('2e-12')*max(abs(dx),abs(dy)))
                            else:
                                equal = dx == dy
                        except InvalidOperation:
                            equal = False
                        check(equal, item['case_id']+'/'+name+': T7 semantic value differs', 't7_anchor_numeric')
                        numeric_reformatted += 1
                file_audits.append({'path':name,'semantic_rows':count,'reformatted_numeric_fields':numeric_reformatted,'byte_exact':old.read(prefix+name) == bundle.read(new_prefix+name)})
            anchor_audits.append({'case_id':item['case_id'],'statistics_equal':True,'files':file_audits})

    # Independently verify the frozen reference inventories and every gzip original hash.
    ns3dir = SOURCE/'evidence/tranche-8-ns3-reference'
    ns3suite = json.loads((ns3dir/'manifest.json').read_text())
    ns3_inventory_count = 0
    gzip_count = 0
    ns3_inventory_members = set()
    ns3_controls = []
    ns3_t7_anchors = []
    for item in ns3suite['cases']:
        path = ns3dir/item['manifest']
        check(sha(path.read_bytes()) == item['manifest_sha256'], item['case_id']+': ns3 manifest hash differs', 'ns3_reference')
        manifest = json.loads(path.read_text())
        declared = manifest['files']
        check({e['path'] for e in declared} == {p.relative_to(path.parent).as_posix() for p in path.parent.rglob('*') if p.is_file()}-{'manifest.json'}, item['case_id']+': ns3 inventory incomplete', 'ns3_reference')
        raw_hashes = {}
        for e in declared:
            data = (path.parent/e['path']).read_bytes()
            check(len(data) == e['bytes'] and sha(data) == e['sha256'], item['case_id']+': ns3 file bytes differ '+e['path'], 'ns3_reference')
            ns3_inventory_count += 1
            ns3_inventory_members.add(str((path.parent/e['path']).relative_to(ns3dir)))
            raw_hashes[e['path']] = sha(data)
        for e in manifest['compressed_artifacts']+manifest['control_compressed_artifacts']:
            data = gzip.decompress((path.parent/e['path']).read_bytes())
            check(len(data) == e['original_bytes'] and sha(data) == e['original_sha256'], item['case_id']+': ns3 gzip roundtrip mismatch '+e['path'], 'ns3_gzip')
            raw_hashes[e['original_name']] = sha(data)
            gzip_count += 1
        nonperturbation = manifest['nonperturbation']
        comparisons = nonperturbation['compared_files'][:]
        pristine = nonperturbation.get('source_runner_vs_observer_off')
        if pristine:
            comparisons += pristine['compared_files']
        for e in comparisons:
            check(raw_hashes[e['first_path']] == raw_hashes[e['second_path']] == e['first_sha256'] == e['second_sha256'], item['case_id']+': ns3 observer/pristine raw mismatch', 'ns3_controls')
        ns3_controls.append({'case_id':item['case_id'],'observer_comparisons':len(nonperturbation['compared_files']),'pristine_comparisons':len(pristine['compared_files']) if pristine else 0})
        if manifest['case']['seed'] == 128:
            previous = SOURCE/'evidence/tranche-7-ns3-reference'/manifest['case']['base_case_id']
            anchor = manifest['baseline_anchor']
            check(sha((previous/'manifest.json').read_bytes()) == anchor['reference_manifest_sha256'], item['case_id']+': ns3 T7 manifest binding differs', 'ns3_t7_anchor')
            old_trace = gzip.decompress((previous/'ns3-trace.csv.gz').read_bytes())
            check(sha(old_trace) == raw_hashes['ns3-trace.csv'], item['case_id']+': ns3 T7 raw trace differs', 'ns3_t7_anchor')
            matched = []
            for name in ['app-admission-diagnostics.csv','ns3-aggregates.csv']:
                tables = []
                for base in [previous,path.parent]:
                    with (base/name).open(newline='') as stream:
                        table = list(csv.DictReader(stream))
                    tables.append([{k:v for k,v in row.items() if k != 'scenario'} for row in table])
                check(tables[0] == tables[1], item['case_id']+': ns3 T7 values differ '+name, 'ns3_t7_anchor')
                matched.append({'path':name,'equal_except_scenario_label':True,'rows':len(tables[0])})
            ns3_t7_anchors.append({'case_id':item['case_id'],'raw_trace_byte_exact':True,'files':matched})
    for e in ns3suite['files']:
        data = (ns3dir/e['path']).read_bytes()
        check(len(data) == e['bytes'] and sha(data) == e['sha256'], 'ns3 suite file mismatch '+e['path'], 'ns3_reference')
        ns3_inventory_count += 1

    audit = {
        'schema':'csr-tranche8-independent-return-integrity-audit-v1',
        'audit_kind':'Independent raw-byte and semantic acceptance audit; no project analyzer imports or simulator execution',
        'audited_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'archive':str(ARCHIVE),'archive_sha256':EXPECTED_ARCHIVE_SHA,
        'archive_bytes':ARCHIVE.stat().st_size,'archive_file_count':len(names),
        'expanded_bytes':sum(i.file_size for i in entries),
        'zip_crcs_verified':len(names),'zip_safe_paths':True,
        'frozen_matlab_candidate_commit':COMMIT,'ns3_source_commit':PIN,
        'runtime':meta['Runtime'],'started_utc':meta['StartedUTC'],'completed_utc':meta['CompletedUTC'],'elapsed_wall_seconds':elapsed,
        'source_files_verified':len(source_files),'source_extensions':dict(source_extensions),
        'matlab_files_verified':source_extensions['.m'],'source_snapshot_sha256':meta['SourceSnapshotSHA256'],
        'reference_files_verified':len(reference_files),'source_reference_stable':True,
        'inventory_verification_counts':dict(inventory_counts),
        'test_count':len(test_rows),'test_classes':len(expected_classes),'test_names_exact':True,
        'test_passed':sum(r['Passed']=='1' for r in test_rows),'test_failed':sum(r['Failed']=='1' for r in test_rows),'test_incomplete':sum(r['Incomplete']=='1' for r in test_rows),
        'test_duration_seconds_sum':sum(float(r['DurationSeconds']) for r in test_rows),
        'tests':test_rows,'plan_sha256':sha(plan_raw),'cases':case_audits,
        'controls':control_audits,'accepted_t7_anchors':anchor_audits,
        'ns3_reference_inventory_checks':ns3_inventory_count,'ns3_gzip_roundtrips':gzip_count,'ns3_controls':ns3_controls,'ns3_t7_anchors':ns3_t7_anchors,
        'check_counts':dict(checks),'failure_count':len(failures),'failures':failures,
        'passed':not failures,
        'limitations':['MATLAB execution is owner-supplied R2025a evidence, not a local rerun.',
                      '13 MAT objects remain on the execution laptop by declared archive policy; their contents were not inspected.',
                      'No native simulator execution, campus rerun, or numerical/statistical parity established.',
                      'T7 CSV comparison tolerates export floating-format differences; identifiers and large integer values compare exactly.',
                      'Full Config is identical for same-run observer controls. T7 anchor statistics and unchanged CSV observations compare semantically; scenario labels/provenance legitimately differ.']
    }
    (OUT/'independent-integrity-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps({k:v for k,v in audit.items() if k not in ['tests','runtime','cases','accepted_t7_anchors','ns3_controls','failures']},indent=2))
    if failures:
        print('FIRST FAILURES',json.dumps(failures[:20],indent=2))
        raise SystemExit(1)
