"""Independent standard-library audit of the completed repaired T12 owner run.

Uses immutable delivered ZIPs as the source of truth, not project checker imports.
No MATLAB/native execution or production-source mutation is performed.
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
sha = lambda b: hashlib.sha256(b).hexdigest()
rows = lambda b: list(csv.DictReader(io.StringIO(b.decode())))


def indexed(records):
    result = {r['path']: r for r in records}
    assert len(result) == len(records)
    return result


def read_zip(path):
    data = (ROOT/path).read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.testzip() is None
        names = z.namelist()
        assert len(names) == len(set(names)) == len({n.casefold() for n in names})
        assert all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts and '\\' not in n for n in names)
        return {i.filename: z.read(i.filename) for i in z.infolist() if not i.is_dir()}, sha(data)


def source_path(name):
    p = PurePosixPath(name)
    return ((len(p.parts) == 1 and p.suffix == '.m')
            or (p.parts[0] in ('+csr', 'tests', 'examples') and p.suffix == '.m')
            or (p.parts[0] == 'scripts' and p.suffix in ('.py', '.cc', '.h'))
            or p.parts[0] in ('data', 'scenarios')
            or (len(p.parts) == 2 and p.parts[0] == 'evidence'
                and (fnmatch.fnmatch(p.name, 'tranche-*-candidate.json') or p.name == 'source-baseline.json')))


def main():
    owner, owner_sha = read_zip('upload/t12(1).zip')
    package, package_sha = read_zip('csr12.zip')
    repair, repair_sha = read_zip('t12fix.zip')
    assert owner_sha == '266a47c167e9b2d50d47abcd77a349b8f474334c9e9742d7abc8cca22547633d'
    assert package_sha == '3bee81b079d77269cb533673820fd5ee5df099452acf99dff86e60d6f2ded6bc'
    assert repair_sha == '046055cf20a8435c41e74fa8435ba21d46eb65c11d0291e3358a96abe854108e'
    package.update(repair)
    manifest = json.loads(package['PACKAGE.json'])
    inventory = indexed(manifest['Files'])
    assert len(inventory) == manifest['FileCountExcludingManifest'] == 1598
    assert set(inventory) == set(package)-{'PACKAGE.json'}
    for n, r in inventory.items():
        assert sha(package[n]) == r['sha256'] and len(package[n]) == r['bytes'], n
        assert (ROOT/'csr12r'/n).read_bytes() == package[n], n
    assert (ROOT/'csr12r/PACKAGE.json').read_bytes() == package['PACKAGE.json']
    m = json.loads(owner['metadata.json'])
    c = json.loads(package['evidence/tranche-12-candidate.json'])
    candidate_sha = sha(package['evidence/tranche-12-candidate.json'])
    assert candidate_sha == m['CandidateSHA256'] == manifest['CandidateSHA256'] == 'ebf493fc8d34dc7c7819f14e266bf19b99f0f94441a79da38a801cd7f52292c4'
    assert m['SourceCommit'] == c['SourceCommit'] == '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
    assert c['EngineCommit'] == '6b5cd24ea80713ce16d88575869aedd6f432bdae'
    assert c['BaseGitCommit'] is None and c['CandidateGitCommit'] is None
    artifacts = indexed(m['Artifacts'])
    assert len(artifacts) == 13 and set(artifacts) == set(owner)-{'metadata.json'}
    assert m['InventoryExcludedPaths'] == ['metadata.json'] and m['LocalArtifacts'] == []
    for n, r in artifacts.items():
        assert sha(owner[n]) == r['sha256'] and len(owner[n]) == r['bytes'], n
    src = indexed(json.loads(owner['source.json']))
    ref = indexed(json.loads(owner['references.json']))
    assert len(src) == 259 and len(ref) == 132
    assert json.loads(owner['source.json']) == m['SourceFilesFinal']
    assert json.loads(owner['references.json']) == m['ReferenceFilesFinal']
    assert m['SourceFilesStableDuringRun'] is True and m['ReferenceFilesStableDuringRun'] is True
    assert sha(owner['source.json']) == m['SourceSnapshotSHA256']
    assert sha(owner['references.json']) == m['ReferenceSnapshotSHA256']
    assert set(src) == {n for n in package if source_path(n)}
    expected_refs = set(c['ReferenceFiles'])
    for directory in c['ReferenceRoots']:
        expected_refs.update(n for n in package if n.startswith(directory+'/'))
    assert set(ref) == expected_refs
    for n, r in {**src, **ref}.items():
        assert sha(package[n]) == r['sha256'], n
        if 'bytes' in r:
            assert len(package[n]) == r['bytes'], n
    baselines = {}
    for label, path, digest_field, source_count, matlab_count in (
        ('tranche11', c['BaselineSourceSnapshot'], 'BaseSourceSnapshotSHA256', 241, 130),
        ('tranche10_core', c['CoreBaselineSourceSnapshot'], 'CoreBaselineSourceSnapshotSHA256', 225, 124),
    ):
        assert sha(package[path]) == c[digest_field]
        baseline = indexed(json.loads(package[path]))
        assert len(baseline) == source_count
        assert sum(n.endswith('.m') for n in baseline) == matlab_count
        assert all(src[n]['sha256'] == r['sha256'] for n,r in baseline.items())
        baselines[label] = {'source_files':source_count,'matlab_files':matlab_count,'all_unchanged':True}
    # Confirm repair changed only the new T12 diagnostic MATLAB file.
    original, _ = read_zip('csr12.zip')
    changed_matlab = [n for n in repair if n.endswith('.m') and repair[n] != original.get(n)]
    assert changed_matlab == ['+csr/+validation/relayContract.m']
    native_counts = {}
    for prefix in ('Relay','Clock'):
        path = c[prefix+'ReferenceManifest']
        assert sha(package[path]) == c[prefix+'ReferenceManifestSHA256']
        files = json.loads(package[path])['files']
        directory = str(PurePosixPath(path).parent)
        names = {n[len(directory)+1:] for n in package if n.startswith(directory+'/')}
        assert names == set(files)|{'manifest.json'}
        for n,digest in files.items():
            assert sha(package[directory+'/'+n]) == digest
        native_counts[prefix.lower()] = len(files)
    assert native_counts == {'relay':41,'clock':5}
    tests = rows(owner['tests.csv'])
    assert [r['Name'] for r in tests] == c['ExpectedTestNames'] == m['ExpectedTestNames']
    assert c['TestFiles'] == m['TestFiles']
    assert len(tests) == len({r['Name'] for r in tests}) == 72
    assert all(r['Passed']=='1' and r['Failed']=='0' and r['Incomplete']=='0' for r in tests)
    assert all(math.isfinite(float(r['DurationSeconds'])) and float(r['DurationSeconds'])>=0 for r in tests)
    assert m['TestCount'] == m['PassedTests'] == 72 and m['FailedTests'] == m['IncompleteTests'] == 0
    by_class = {}
    for r in tests:
        cls = r['Name'].split('/')[0]
        by_class[cls] = by_class.get(cls,0)+1
    assert by_class['TestRelayContract']==12 and by_class['TestClockBoundaryContract']==8
    assert sum(n for cls,n in by_class.items() if cls not in ('TestRelayContract','TestClockBoundaryContract'))==52
    relay = json.loads(owner['relay/summary.json'])
    events = rows(owner['relay/events.csv'])
    draws = rows(owner['relay/draws.csv'])
    usage = rows(owner['relay/usage.csv'])
    checks = rows(owner['relay/check.csv'])
    assert len(events)==relay['EventCount']==2344 and len(draws)==relay['DrawCount']==332 and len(usage)==12
    assert len(checks)==relay['CheckpointCount']==164 and relay['FailedCount']==0
    assert relay['DiagnosticCompleted'] is True and relay['Passed'] is True and relay['MatchesNative'] is False
    for rec in relay['InputBindings']+relay['ReferenceBindings']:
        assert sha(package[rec['Path']])==rec['SHA256']
    case_results = {}
    for case, count4, count5 in [('relay',20,0),('local',0,20),('mix',20,20),('sw',20,20)]:
        ev = [r for r in events if r['case']==case]
        assert [int(r['order']) for r in ev]==list(range(1,len(ev)+1))
        assert [int(r['time_ns']) for r in ev]==sorted(int(r['time_ns']) for r in ev)
        ck = [r for r in checks if r['case']==case]
        actual = {(r['checkpoint'],int(r['node'])):int(r['actual']) for r in ck}
        expected = {}
        for node,count in ((4,count4),(5,count5)):
            for event in ('admitted','delivered'):
                expected[event,node]=count
                observations = [r for r in ev if r['event']==('admit' if event=='admitted' else 'deliver') and int(r['app_source'])==node]
                assert len(observations)==count
                assert {int(r['app_id']) for r in observations}==set(range(1,count+1))
            expected['nsdp_blocked_seen',node]=int(count>16)
            assert bool([r for r in ev if r['event']=='blocked' and int(r['node'])==node])==bool(count>16)
        for node in (1,4,5):
            final = [r for r in ev if r['event']=='final' and int(r['node'])==node]
            assert len(final)==1 and final[0]['time_ns']=='24000000000'
            for field in ('hop_pending','dack_holds','resend_queue','nwk_waiting','nwk_custody','nsdp4','nsdp5'):
                expected[field,node]=0
                assert int(final[0][field])==0
            expected['released',node]=0 if node==1 else count4 if node==4 else count4+count5
            assert sum(r['event']=='release' and int(r['node'])==node for r in ev)==expected['released',node]
        expected.update({('relay_custody',5):count4,('drops',0):0,('release_order_failures',0):0,
                         ('draw_resolution_failures',0):0,('custody_conservation_failures',0):0,
                         ('direct_source_gateway_transmissions',4):0,('source4_wrong_next_hop',4):0,
                         ('relay_wrong_next_hop',5):0,('relay_ack_seen',5):int(count4>0),
                         ('gateway_ack_seen',1):1,('case_completed',0):1})
        assert len(actual)==len(ck)==len(expected)==41 and actual==expected
        assert all(int(r['expected'])==expected[r['checkpoint'],int(r['node'])] and r['pass']=='1' for r in ck)
        assert all(int(r['nwk_custody'])==int(r['nsdp4'])+int(r['nsdp5']) for r in ev)
        for r in ev:
            if r['event'] in ('checkpoint','final'):
                assert int(r['hop_pending'])==int(r['resend_queue'])+int(r['dack_holds'])
            if r['event']=='tx_start':
                assert r['rate_kbps']=='128' and r['power_dbm']=='33'
                if int(r['app_source'])>0:
                    assert (int(r['node']),int(r['peer'])) in ((4,5),(5,1))
        case_results[case]={'admitted':count4+count5,'delivered':count4+count5,'release_callbacks':2*count4+count5,'checks_passed':41,'final_data_owners_and_holds_zero':True}
    assert len(relay['CaseResults'])==4
    for r in relay['CaseResults']:
        expected=case_results[r['Case']]
        assert r['Completed'] is True and r['ErrorIdentifier']==r['ErrorMessage']=='' and r['ErrorStack']==[]
        assert sum(r['Admitted'])==sum(r['Delivered'])==expected['delivered']
        assert sum(r['Released'])==expected['release_callbacks']
        assert all(v==0 for field in ('FinalHopPending','FinalDackHolds','FinalResends') for v in r[field])
        assert r['Drops']==0
        # Bootstrap controls remain queued by design; retain rather than hide.
        assert r['PendingControls']==[2,0,0,2,3]
    tape={(r['case'],r['node'],r['ordinal']):r for r in rows(package['scenarios/relay/draws.csv'])}
    for r in draws:
        assert r['min']=='0' and r['max']=='31' and 0<=int(r['draw'])<=31 and int(r['resolved'])>=0
        supplied=tape[r['case'],r['node'],r['ordinal']]
        assert r['draw']==supplied['draw']
    for r in usage:
        ds=[d for d in draws if d['case']==r['case'] and d['node']==r['node']]
        assert [int(d['ordinal']) for d in ds]==list(range(1,len(ds)+1))
        assert int(r['consumed'])==len(ds) and int(r['supplied'])==256
        assert int(r['unused'])==256-len(ds)
    clock = json.loads(owner['clock/summary.json'])
    clock_events=rows(owner['clock/events.csv'])
    native_clock=rows(package['evidence/tranche-12-clock-reference/events.csv'])
    clock_checks=rows(owner['clock/checks.csv'])
    boundary=rows(owner['clock/boundary.csv'])
    assert len(clock_events)==len(native_clock)==18 and len(clock_checks)==72 and len(boundary)==6
    fields=('local_counter','neighbor_counter','data_queue','transmissions')
    key=lambda r:(r['case'],r['phase'])
    event_map={key(r):r for r in clock_events}
    assert len(event_map)==18
    checked=set()
    for r in clock_checks:
        ck=(r['case'],r['phase'],r['field'])
        assert ck not in checked and r['field'] in fields
        checked.add(ck)
        assert r['actual']==r['expected']==event_map[key(r)][r['field']] and r['pass']=='1'
    differences=[]
    for a,n in zip(clock_events,native_clock):
        assert key(a)==key(n)
        for field in a:
            if a[field]!=n[field]:
                differences.append({'case':a['case'],'phase':a['phase'],'field':field,'matlab':int(a[field]),'native':int(n[field])})
    assert len(differences)==4 and {d['case'] for d in differences}=={'continuous'}
    assert len({d['phase'] for d in differences})==3
    assert all(d['field'] in ('local_counter','neighbor_counter') for d in differences)
    for r in boundary:
        arrival=struct.unpack('>d',bytes.fromhex(r['arrival_seconds_hex']))[0]
        tick=struct.unpack('>d',bytes.fromhex(r['tick_seconds_hex']))[0]
        assert tick==2011501000/1e9
        assert math.isclose(float(r['arrival_minus_tick_seconds']),arrival-tick,rel_tol=1e-14,abs_tol=0)
        case=r['case']
        assert r['transport_quantized']==str(int(case=='quantized')) and r['late_insertion']==str(int(case=='tie_late'))
        assert arrival=={'tie_early':tick,'tie_late':tick,'before':2011500999/1e9,'after':2011501001/1e9,'continuous':math.nextafter(tick,math.inf),'quantized':tick}[case]
        ev=[e for e in clock_events if e['case']==case]
        late=case in ('tie_late','after','continuous')
        pairs=[(15,15),(15,16),(15,16)] if late else [(16,16),(16,16),(15,15)]
        assert [(int(e['local_counter']),int(e['neighbor_counter'])) for e in ev]==pairs
        assert all(e['data_queue']=='1' and e['transmissions']=='0' for e in ev)
    assert all(clock[k] is True for k in ('DiagnosticCompleted','Passed','SharedIntegerMatchesNative','ExpectedContinuousResidual'))
    assert clock['MatchesNative'] is False and clock['GlobalClockChanged'] is False
    assert clock['UnmatchedCount']==3 and clock['FailedCount']==0
    assert clock['InputSHA256']==c['ClockPlanSHA256']
    assert clock['ReferenceSHA256']==sha(package['evidence/tranche-12-clock-reference/events.csv'])
    assert m['Status']=='completed' and m['MATLABExecuted'] is True and m['NativeExecuted'] is False
    assert m['TestsPassed'] is True and m['FocusedGateExecuted'] is True and m['DiagnosticOnly'] is True
    assert m['FullAcceptanceGateExecuted'] is False and m['AcceptanceEstablished'] is False and m['NumericalParityEstablished'] is False
    assert m['RelayCompleted'] is True and m['RelayPassed'] is True and m['RelayMatchesNative'] is False
    assert m['ClockCompleted'] is True and m['ClockPassed'] is True and m['ClockMatchesNative'] is False
    result={'schema':'csr-tranche12-repaired-return-independent-integrity-v1',
            'disposition':'focused_diagnostic_execution_verified; strict_numerical_parity_not_established',
            'owner_archive_sha256':owner_sha,'delivered_base_sha256':package_sha,'delivered_repair_sha256':repair_sha,'candidate_sha256':candidate_sha,
            'source_commit':c['SourceCommit'],'runtime':m['Runtime'],'started_utc':m['StartedUTC'],'completed_utc':m['CompletedUTC'],
            'integrity':{'archive_members':14,'artifact_hashes_verified':13,'delivered_overlay_inventory_files_verified':1598,
                         'source_files_verified':259,'reference_files_verified':132,'source_reference_pre_post_identical':True,
                         'source_reference_sets_closed_against_immutable_delivery':True,'native_reference_artifacts':native_counts,
                         'baselines':baselines,'repair_matlab_files_changed':changed_matlab},
            'tests':{'passed':72,'failed':0,'incomplete':0,'by_class':by_class,'retained_passed':52},
            'relay':{'cases':case_results,'checks_passed':164,'checks_failed':0,'event_count':2344,'draw_count':332,
                     'usage_records':12,'unused_draw_suffix_recorded':True,'bootstrap_pending_controls_per_case':[2,0,0,2,3],
                     'strict_matches_native':False},
            'clock':{'cases':6,'checks_passed':72,'checks_failed':0,'shared_integer_cases_exact':5,
                     'continuous_difference_rows':3,'continuous_difference_fields':4,'differences':differences,'global_clock_changed':False},
            'full_acceptance_gate_executed':False,'numerical_parity_established':False,
            'method':'Independent Python standard-library parsing, SHA256 and closed-set checks against immutable csr12.zip+t12fix.zip. Raw service events cross-checked against reported outcomes. No project acceptance checker imported; no MATLAB/native simulator executed by this audit.',
            'scope':'Actual owner-returned R2025a focused tests and controlled relay/clock fixtures. Prescribed random draws, successful addressed transport, fixed 128 rate key/+33dBm, preconditioned routes and neighbors; bootstrap controls excluded and still queued. No RF/PHY, stochastic population, routing convergence, security admission, full application generator or campus parity claim.'}
    (OUT/'integrity.json').write_text(json.dumps(result,indent=2)+'\n')
    (OUT/'integrity.md').write_text('\n'.join([
        '# Tranche 12 repaired return: independent integrity review','',
        '**Verified: the repaired run completes the focused diagnostic milestone. Strict numerical parity and full-protocol acceptance remain unclaimed.**','',
        f"Owner archive SHA256: `{owner_sha}`.",
        f"Executed repaired candidate SHA256: `{candidate_sha}`.",'',
        'The immutable original package plus delivered repair reconstructs the owner candidate. All 1,598 package payload entries match their manifest and the local repair tree. All 13 returned artifact hashes, 259 source bindings and 132 reference bindings verify with closed inventories and identical pre-run/post-run snapshots. Native manifests close over 41 relay and five clock artifacts.','',
        'All 241 Tranche 11 baseline source files, including all 130 MATLAB files, remain unchanged. The core 225-source/124-MATLAB-file baseline also remains unchanged. The repair changes only the new relay diagnostic MATLAB file.','',
        'MATLAB R2025a (25.1.0.2943329) completed 72/72 selected tests with zero failures or incomplete tests: 12 relay tests, eight clock tests and 52 retained tests. All four relay cases completed and all 164 relay checks pass. Raw events confirm 120 admitted and 120 delivered application identities, 180 release callbacks and zero final HOP pending owners, DACK holds, resends, waiting data, data custody or pair NSDP counts.','',
        'All 332 consumed draws match their prescribed raw tape values and ordinal sequence; all 12 usage records account for supplied, consumed and unused entries. Bootstrap controls are separately retained: node 1 has two, node 4 has two and node 5 has three queued controls per case. Zero remaining data custody must not be described as zero queues of every kind.','',
        'All 72 clock checks pass. The five shared integer-time cases match native exactly. The continuous case retains the expected one-binary64-ULP arrival residual, producing three differing observation rows and four counter-field differences. The global scheduler is unchanged.','',
        'The returned metadata correctly reports completed focused diagnostics with strict native matching false and full acceptance/numerical parity false. Event and draw differences require separate residual analysis; their presence does not imply failed application delivery.','',
        'This independent audit uses Python standard-library ZIP, CSV, JSON and hash parsing, without importing the project acceptance checker. It inspects actual owner-run MATLAB evidence and does not claim a new MATLAB or ns-3 execution.','',
        'The fixture uses prescribed random draws, fixed radio settings, preconditioned routes and neighbors, and controlled successful addressed transport. It does not establish real RF/PHY, security-admission, route-convergence, stochastic-population, full-generator or campus parity.'
    ])+'\n')
    print(json.dumps({'audit':'passed','owner_archive_sha256':owner_sha,'tests':72,'relay_checks':164,'clock_checks':72,'baseline_matlab_unchanged':130,'source_bindings':259,'reference_bindings':132},indent=2))


if __name__=='__main__':
    main()
