"""Independent inspection of the original, failed T12 owner return.

Reads the immutable delivered ZIP, not an editable repaired candidate. It does
not import the project's acceptance checker or relax its successful-run gate.
"""
import csv
import fnmatch
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import struct
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
sha = lambda data: hashlib.sha256(data).hexdigest()
rows = lambda data: list(csv.DictReader(io.StringIO(data.decode())))


def indexed(items):
    result = {r['path']: r for r in items}
    assert len(result) == len(items)
    return result


def source_path(name):
    p = PurePosixPath(name)
    return ((len(p.parts) == 1 and p.suffix == '.m')
            or (p.parts[0] in ('+csr', 'tests', 'examples') and p.suffix == '.m')
            or (p.parts[0] == 'scripts' and p.suffix in ('.py', '.cc', '.h'))
            or p.parts[0] in ('data', 'scenarios')
            or (len(p.parts) == 2 and p.parts[0] == 'evidence'
                and (fnmatch.fnmatch(p.name, 'tranche-*-candidate.json')
                     or p.name == 'source-baseline.json')))


def audit():
    owner_bytes = (ROOT/'upload/t12.zip').read_bytes()
    package_bytes = (ROOT/'csr12.zip').read_bytes()
    assert sha(package_bytes) == '3bee81b079d77269cb533673820fd5ee5df099452acf99dff86e60d6f2ded6bc'
    with zipfile.ZipFile(io.BytesIO(owner_bytes)) as owner, zipfile.ZipFile(io.BytesIO(package_bytes)) as package:
        assert owner.testzip() is None
        names = owner.namelist()
        assert len(names) == len(set(names)) == len({n.casefold() for n in names}) == 14
        assert all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts and '\\' not in n for n in names)
        m = json.loads(owner.read('metadata.json'))
        candidate_path = 'evidence/tranche-12-candidate.json'
        candidate_bytes = package.read(candidate_path)
        c = json.loads(candidate_bytes)
        candidate_sha = sha(candidate_bytes)
        assert candidate_sha == '65a6fe4edd6d925ec596fad6c0ec257be483d623616aa7f41bbd9805a6548703'
        assert m['CandidateSHA256'] == candidate_sha
        assert m['SourceCommit'] == c['SourceCommit'] == '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
        artifacts = indexed(m['Artifacts'])
        assert set(artifacts) == set(names)-{'metadata.json'}
        assert m['InventoryExcludedPaths'] == ['metadata.json'] and m['LocalArtifacts'] == []
        for n, record in artifacts.items():
            data = owner.read(n)
            assert sha(data) == record['sha256'] and len(data) == record['bytes'], n
        source = json.loads(owner.read('source.json'))
        refs = json.loads(owner.read('references.json'))
        src = indexed(source)
        ref = indexed(refs)
        assert len(src) == 259 and len(ref) == 130
        assert source == m['SourceFilesFinal'] and refs == m['ReferenceFilesFinal']
        assert m['SourceFilesStableDuringRun'] and m['ReferenceFilesStableDuringRun']
        assert sha(owner.read('source.json')) == m['SourceSnapshotSHA256']
        assert sha(owner.read('references.json')) == m['ReferenceSnapshotSHA256']
        package_files = {i.filename for i in package.infolist() if not i.is_dir()}
        assert set(src) == {n for n in package_files if source_path(n)}
        expected_refs = set(c['ReferenceFiles'])
        for directory in c['ReferenceRoots']:
            expected_refs.update(n for n in package_files if n.startswith(directory+'/'))
        assert set(ref) == expected_refs
        for n, r in {**src, **ref}.items():
            data = package.read(n)
            assert sha(data) == r['sha256'], n
            if 'bytes' in r:
                assert len(data) == r['bytes'], n
        baselines = {}
        for label, path, expected_sources, expected_matlab in (
            ('tranche11', c['BaselineSourceSnapshot'], 241, 130),
            ('tranche10_core', c['CoreBaselineSourceSnapshot'], 225, 124),
        ):
            baseline = indexed(json.loads(package.read(path)))
            assert len(baseline) == expected_sources
            assert sum(n.endswith('.m') for n in baseline) == expected_matlab
            assert all(src[n]['sha256'] == r['sha256'] for n, r in baseline.items())
            baselines[label] = {'source_files': expected_sources, 'matlab_files': expected_matlab, 'all_unchanged': True}
        native_counts = {}
        for prefix in ('Relay', 'Clock'):
            manifest_path = c[prefix+'ReferenceManifest']
            data = package.read(manifest_path)
            assert sha(data) == c[prefix+'ReferenceManifestSHA256']
            files = json.loads(data)['files']
            directory = str(PurePosixPath(manifest_path).parent)
            actual_names = {n[len(directory)+1:] for n in package_files if n.startswith(directory+'/')}
            assert actual_names == set(files) | {'manifest.json'}
            for n, digest in files.items():
                assert sha(package.read(directory+'/'+n)) == digest
            native_counts[prefix.lower()] = len(files)
        tests = rows(owner.read('tests.csv'))
        assert [r['Name'] for r in tests] == c['ExpectedTestNames'] == m['ExpectedTestNames']
        assert c['TestFiles'] == m['TestFiles']
        assert len(tests) == len({r['Name'] for r in tests}) == 72
        totals = {field.lower(): sum(int(r[field]) for r in tests) for field in ('Passed', 'Failed', 'Incomplete')}
        assert totals == {'passed': 63, 'failed': 9, 'incomplete': 1}
        for field, key in [('passed','PassedTests'), ('failed','FailedTests'), ('incomplete','IncompleteTests')]:
            assert totals[field] == m[key]
        by_class = {}
        for r in tests:
            cls = r['Name'].split('/')[0]
            bucket = by_class.setdefault(cls, {'total': 0, 'passed': 0, 'failed': 0, 'incomplete': 0})
            bucket['total'] += 1
            for field in ('Passed','Failed','Incomplete'):
                assert r[field] in ('0','1')
                bucket[field.lower()] += int(r[field])
            assert int(r['Passed'])+int(r['Failed']) == 1
            assert math.isfinite(float(r['DurationSeconds'])) and float(r['DurationSeconds']) >= 0
        assert by_class['TestRelayContract'] == {'total':12,'passed':3,'failed':9,'incomplete':1}
        assert by_class['TestClockBoundaryContract'] == {'total':8,'passed':8,'failed':0,'incomplete':0}
        assert all(r['Failed'] == '0' for r in tests if not r['Name'].startswith('TestRelayContract/'))
        clock = json.loads(owner.read('clock/summary.json'))
        clock_events = rows(owner.read('clock/events.csv'))
        native_events = rows(package.read('evidence/tranche-12-clock-reference/events.csv'))
        checks = rows(owner.read('clock/checks.csv'))
        boundary = rows(owner.read('clock/boundary.csv'))
        assert len(clock_events) == len(native_events) == 18 and len(checks) == 72 and len(boundary) == 6
        fields = ('local_counter','neighbor_counter','data_queue','transmissions')
        key = lambda r: (r['case'], r['phase'])
        event_map = {key(r):r for r in clock_events}
        assert len(event_map) == 18
        checked = set()
        for r in checks:
            assert r['field'] in fields
            check_key = (r['case'],r['phase'],r['field'])
            assert check_key not in checked
            checked.add(check_key)
            assert r['actual'] == r['expected'] == event_map[key(r)][r['field']]
            assert r['pass'] == '1'
        differences = []
        for actual, native in zip(clock_events, native_events):
            assert key(actual) == key(native)
            for field in actual:
                if actual[field] != native[field]:
                    differences.append({'case':actual['case'],'phase':actual['phase'],'field':field,'matlab':int(actual[field]),'native':int(native[field])})
        assert len(differences) == 4 and {d['case'] for d in differences} == {'continuous'}
        assert len({d['phase'] for d in differences}) == 3
        assert all(d['field'] in ('local_counter','neighbor_counter') for d in differences)
        boundary_records = []
        for r in boundary:
            arrival = struct.unpack('>d', bytes.fromhex(r['arrival_seconds_hex']))[0]
            tick = struct.unpack('>d', bytes.fromhex(r['tick_seconds_hex']))[0]
            assert tick == 2011501000/1e9
            assert math.isclose(float(r['arrival_minus_tick_seconds']), arrival-tick, rel_tol=1e-14, abs_tol=0)
            case = r['case']
            assert r['transport_quantized'] == str(int(case == 'quantized'))
            assert r['late_insertion'] == str(int(case == 'tie_late'))
            expected = {'tie_early':tick,'tie_late':tick,'before':2011500999/1e9,'after':2011501001/1e9,'continuous':math.nextafter(tick,math.inf),'quantized':tick}[case]
            assert arrival == expected
            ev = [e for e in clock_events if e['case']==case]
            late = case in ('tie_late','after','continuous')
            pairs = [(15,15),(15,16),(15,16)] if late else [(16,16),(16,16),(15,15)]
            assert [(int(e['local_counter']),int(e['neighbor_counter'])) for e in ev] == pairs
            assert all(e['data_queue']=='1' and e['transmissions']=='0' for e in ev)
            boundary_records.append({'case':case,'arrival_seconds_hex':r['arrival_seconds_hex'],'tick_seconds_hex':r['tick_seconds_hex'],'arrival_minus_tick_seconds':arrival-tick,'counter_pairs':pairs,'native_exact':case!='continuous','checks_passed':12})
        assert all(clock[k] is True for k in ('DiagnosticCompleted','Passed','SharedIntegerMatchesNative','ExpectedContinuousResidual'))
        assert clock['MatchesNative'] is False and clock['GlobalClockChanged'] is False
        assert clock['UnmatchedCount'] == 3 and clock['FailedCount'] == 0
        assert clock['InputSHA256'] == c['ClockPlanSHA256']
        assert clock['ReferenceSHA256'] == sha(package.read('evidence/tranche-12-clock-reference/events.csv'))
        relay = json.loads(owner.read('relay/summary.json'))
        relay_checks = rows(owner.read('relay/check.csv'))
        relay_events = rows(owner.read('relay/events.csv'))
        relay_draws = rows(owner.read('relay/draws.csv'))
        assert len(relay_checks) == 164 and sum(r['pass']=='0' for r in relay_checks) == 63
        assert len(relay_events) == relay['EventCount'] == 244
        assert len(relay_draws) == relay['DrawCount'] == 10
        failures = []
        for r in relay['CaseResults']:
            assert not r['Completed'] and r['ErrorIdentifier']=='MATLAB:structRefFromNonStruct'
            assert r['ErrorStack'][0]['line']==103
            failures.append({'case':r['Case'],'identifier':r['ErrorIdentifier'],'message':r['ErrorMessage'],'first_stack_frame':{'name':r['ErrorStack'][0]['name'],'line':103},'admitted':sum(r['Admitted']),'delivered':sum(r['Delivered'])})
        assert len(failures)==4
        assert m['Status']=='failed' and m['MATLABExecuted'] is True and m['TestsPassed'] is False
        assert not m['AcceptanceEstablished'] and not m['NumericalParityEstablished']
        return {
            'schema':'csr-tranche12-original-return-independent-review-v1',
            'disposition':'rejected_structural_relay_fixture_failure; clock_diagnostic_valid',
            'owner_archive_sha256':sha(owner_bytes),'immutable_package_sha256':sha(package_bytes),'candidate_sha256':candidate_sha,
            'source_commit':c['SourceCommit'],'runtime':m['Runtime'],'started_utc':m['StartedUTC'],'completed_utc':m['CompletedUTC'],
            'integrity':{'archive_crc_passed':True,'closed_archive_members':14,'artifact_hashes_verified':13,'candidate_source_files_verified':259,'reference_files_verified':130,'source_and_reference_pre_post_identical':True,'source_and_reference_closed_against_immutable_package':True,'native_manifest_files_verified':native_counts,'baselines':baselines},
            'tests':{'total':72,**totals,'incomplete_included_in_failed':True,'by_class':by_class,'failed_names':[r['Name'] for r in tests if r['Failed']=='1']},
            'clock':{'cases':6,'matlab_tests_passed':8,'checks_passed':72,'checks_failed':0,'five_shared_integer_cases_exact':True,'continuous_difference_rows':3,'continuous_difference_fields':4,'differences':differences,'case_details':boundary_records,'global_clock_changed':False},
            'relay':{'completed':False,'passed':False,'cases_aborted':4,'partial_event_count':244,'partial_draw_count':10,'failed_check_count':63,'case_failures':failures,'reported_unmatched_count':2649,'unmatched_count_is_accepted_parity_measure':False,'note':'All cases abort in the NSDP diagnostic callback before first delivery. No delivery percentage or relay service parity conclusion is valid.'},
            'acceptance_established':False,'numerical_parity_established':False,
            'method':'Independent Python standard-library parsing, SHA256 and closed-set checks against the immutable delivered csr12.zip. Did not execute MATLAB or ns-3; inspected actual owner-returned R2025a execution. No project acceptance-checker code imported.'}


result = audit()
(OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
lines = ['# Tranche 12 returned-run independent audit','',
    'The returned run is **not accepted**: all four relay cases stopped in the diagnostic NSDP callback. The clock diagnostic is valid and passed. This review changes no simulator, candidate, or reference files.','',
    f"Owner archive SHA256: `{result['owner_archive_sha256']}`.",'',
    'The return binds exactly to the delivered candidate. All 13 archived artifacts, 259 source entries and 130 reference entries verify. Pre-run and post-run snapshots match. The 241-file Tranche 11 baseline, including all 130 MATLAB files, and the 225-file/124-MATLAB-file core baseline are unchanged. Native reference manifests close over 41 relay and five clock artifacts.','',
    'MATLAB R2025a (25.1.0.2943329) ran all 72 selected tests: **63 passed, nine failed**. One failed test is also marked incomplete; it is included in the nine. All 52 retained tests and all eight new clock tests passed. The relay class passed three of 12 tests.','',
    '| Clock case | Arrival relative to tick | Native result |','| --- | --- | --- |',
    '| tie_early | Exact tie; earlier insertion | Exact |',
    '| tie_late | Exact tie; later insertion | Exact |',
    '| before | One ns before | Exact |',
    '| after | One ns after | Exact |',
    '| continuous | One binary64 ULP after (4.440892098500626e-16 s) | Expected counter residual |',
    '| quantized | Exact tie using test transport quantization | Exact |','',
    'All 72 clock checks pass. The continuous control differs from native in three observation rows and four counter fields; all time_ns, queue and transmission fields match. The five shared integer-time cases match exactly. The production global scheduler is unchanged.','',
    'All four relay cases report `MATLAB:structRefFromNonStruct` at `relayContract.m` line 103, in `@(a)networks{node}.nsdpCount(a)`. They stop before first application delivery. The 244 observations and ten draws are partial failure traces. The reported 2,649 comparison differences must not be interpreted as delivery performance or accepted parity data.','',
    'Repair the diagnostic callback and repeat the bounded T12 run. No complete-tranche acceptance or numerical-parity claim follows from this failed run.']
(OUT/'audit.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({'audit':'passed_as_failed_run_review','owner_archive_sha256':result['owner_archive_sha256'],'tests':result['tests'],'clock':{'checks':72,'native_difference_rows':3,'native_difference_fields':4},'integrity':result['integrity']},indent=2))
