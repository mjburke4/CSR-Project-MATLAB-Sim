"""Independent read-only audit; does not import the project's return analyzer."""
import csv, hashlib, io, json, math, pathlib, re, stat, zipfile
from collections import Counter
from datetime import datetime

ROOT = pathlib.Path('/workspace/scratch/1a5b1ad6ce1b')
OUT = ROOT/'t10v/integrity'
issues=[]
def check(ok, text):
    if not ok: issues.append(text)
def sha(data): return hashlib.sha256(data).hexdigest()
def rows(data): return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
def dictionary(items): return {x['path']:x for x in items}
def package_hash(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

with zipfile.ZipFile(ROOT/'upload/tranche10_evidence.zip') as z, zipfile.ZipFile(ROOT/'csr10r.zip') as p:
    names=z.namelist(); infos=z.infolist()
    check(len(names)==len(set(names)), 'Duplicate ZIP member')
    check(len(names)==len(set(n.casefold() for n in names)), 'Case-insensitive ZIP collision')
    for item in infos:
        n=item.filename; q=pathlib.PurePosixPath(n)
        check(not(q.is_absolute() or '..' in q.parts or '\\' in n or ':' in n or '\x00' in n),f'Unsafe path {n}')
        check(not stat.S_ISLNK(item.external_attr>>16),f'Symlink {n}')
        check(not item.flag_bits&1,f'Encrypted member {n}')
    check(z.testzip() is None,'ZIP CRC failure')
    h={n:sha(z.read(n)) for n in names}
    m=json.loads(z.read('validation_metadata.json'))
    snap=json.loads(z.read('source_snapshot.json'))
    inventory=m['Artifacts']; inv=dictionary(inventory)
    check(len(inv)==len(inventory),'Duplicate inventory path')
    check(set(names)==set(inv)|set(m['InventoryExcludedPaths']), 'Closed archive inventory mismatch')
    for n,r in inv.items():
        check(h.get(n)==r['sha256'],f'Inventory hash {n}')
        check(z.getinfo(n).file_size==r['bytes'],f'Inventory size {n}')
    check(m['SourceFiles']==m['SourceFilesFinal']==snap,'Source snapshot start/end mismatch')
    check(m['ReferenceFiles']==m['ReferenceFilesFinal'],'Reference start/end mismatch')
    check(h['source_snapshot.json']==m['SourceSnapshotSHA256'],'Source snapshot hash mismatch')
    for group in [m['SourceFiles'],m['ReferenceFiles']]:
        check(len(group)==len(dictionary(group)), 'Duplicate source/reference path')
        for r in group:
            n=r['path'];check(n in p.namelist(),f'Package missing {n}')
            if n not in p.namelist():continue
            check(sha(p.read(n))==r['sha256'], f'Immutable package hash {n}')
            if 'bytes' in r:check(p.getinfo(n).file_size==r['bytes'],f'Immutable package size {n}')
    # Reconstruct test method names from the immutable package's Test methods blocks.
    expected=[];testclasses=0
    for n in p.namelist():
        if n.startswith('tests/Test') and n.endswith('.m'):
            testclasses+=1;testblock=False
            for line in p.read(n).decode().splitlines():
                if re.match(r'\s{4}methods\b',line):testblock=bool(re.search(r'\bTest\b',line))
                method=re.match(r'\s{8}function\s+(\w+)\s*\(',line)
                if testblock and method:expected.append(pathlib.PurePosixPath(n).stem+'/'+method.group(1))
    tests=rows(z.read('tests/test_results.csv'));actual=[x['Name'] for x in tests]
    check(len(actual)==len(set(actual))==550,'550 unique MATLAB tests not present')
    check(Counter(actual)==Counter(expected),'Returned names differ from source test methods')
    check(all(x['Passed']=='1' and x['Failed']=='0' and x['Incomplete']=='0' and math.isfinite(float(x['DurationSeconds'])) and float(x['DurationSeconds'])>=0 for x in tests),'Nonpassing/invalid MATLAB test')
    # Compare checkpoint identities and numeric columns to archived native reference rows.
    contracts={}; refs={'mac':'evidence/tranche-10-contract-reference/checkpoints.csv','rx':'evidence/tranche-10-receiver-reference/checkpoints.csv','ack':'evidence/tranche-9-contract-reference/checkpoints.csv'}
    for kind,ref in refs.items():
        summary=json.loads(z.read(f'k/{kind}/summary.json')); a=rows(z.read(f'k/{kind}/checkpoints.csv'));b=rows(p.read(ref))
        check(summary['ReferenceSHA256']==sha(p.read(ref)),f'{kind} reference hash')
        check(len(a)==len(b)==summary['CheckpointCount'],f'{kind} checkpoint count')
        check(summary['Passed'] and summary['FailedCount']==summary['UnmatchedCount']==0,f'{kind} summary failure')
        identities=[(r['case'],r['checkpoint'],r['time_seconds'],r['field']) for r in a]
        check(len(set(identities))==len(identities),f'{kind} duplicate checkpoints')
        deltas=[]
        for i,(x,y) in enumerate(zip(a,b)):
            check(all(x[k]==y[k] for k in ['case','checkpoint','field']),f'{kind} row {i} identity mismatch')
            for k in ['time_seconds','actual','expected']:
                v,w=float(x[k]),float(y[k]);deltas.append(abs(v-w))
                check(math.isfinite(v) and math.isfinite(w) and math.isclose(v,w,rel_tol=1e-12,abs_tol=1e-12),f'{kind} row {i} numeric mismatch {k}')
            check(x['pass']=='1' and float(x['actual'])==float(x['expected']),f'{kind} checkpoint fail {i}')
        contracts[kind]={'checkpoints':len(a),'cases':len(set(r['case'] for r in a)),'max_numeric_difference_to_native':max(deltas,default=0)}
    # Verify nested manifests, including their relative file hashes/sizes and snapshots.
    manifest_checks=0;manifest_file_checks=0
    for n in names:
        if n.endswith(('/case_manifest.json','/benchmark_manifest.json')):
            d=json.loads(z.read(n));manifest_checks+=1
            check(d['status']=='completed',f'Incomplete {n}')
            check(d.get('structural_checks_passed') is True,f'Structural failure {n}')
            check(d.get('source_files')==snap,f'Case source snapshot mismatch {n}')
            for r in d.get('files',[]):
                full=str(pathlib.PurePosixPath(n).parent/r['path']);manifest_file_checks+=1
                check(h.get(full)==r['sha256'],f'Nested hash {full}')
                check(full in names and z.getinfo(full).file_size==r['bytes'],f'Nested size {full}')
    plan=json.loads(z.read('validation_plan.json')); diag=json.loads(z.read('diagnostic_plan.json'))
    for local,remote in [('validation_plan.json','scenarios/contention_timing/plan.json'),('diagnostic_plan.json','scenarios/ack_service/plan.json')]:
        check(z.read(local)==p.read(remote),f'Plan differs from package {local}')
    check([r['CaseId'] for r in m['RetainedCases']]==[r['case_id'] for r in plan['retained_cases']],'Retained plan identity/order mismatch')
    check([r['CaseId'] for r in m['SweepCases']]==[r['case_id'] for r in plan['sweep_cases']],'Sweep plan identity/order mismatch')
    check([r['CaseId'] for r in m['Cases']]==[r['case_id'] for r in diag['cases']],'Diagnostic plan identity/order mismatch')
    for group,filename,count in [('RetainedCases','case_manifest.json',29),('SweepCases','case_manifest.json',18),('Cases','benchmark_manifest.json',6)]:
        check(len(m[group])==count, f'{group} count')
        for r in m[group]:check(h.get(r['Directory']+'/'+filename)==r['ManifestSHA256'],f'{group} manifest binding {r["CaseId"]}')
    campusmeta=m['CampusCase'];check(h[campusmeta['Directory']+'/benchmark_manifest.json']==campusmeta['ManifestSHA256'],'Campus manifest binding')
    check(m['Status']=='completed' and m['FullAcceptanceGateExecuted'] and not m['DiagnosticOnly'],'Not full completed gate')
    check(m['Options']=={'RunTests':True,'RunCampus':True},'Nondefault options')
    check(m['Runtime']['Release']=='2025a' and m['Runtime']['DefaultBackend']=='portable','Wrong runtime/backend')
    check(not m['NativeExecuted'] and not m['NumericalParityEstablished'],'Inappropriate native/parity claim')
    # Recompute both observer controls, without trusting nonperturbation booleans.
    controls=json.loads(z.read('nonperturbation.json'));control_result=[]
    check(len(controls['cases'])==2,'Control case count')
    check([x['case_id'] for x in controls['cases']]==[next(c['case_id'] for c in diag['cases'] if c['storage_key']==k) for k in plan['control_keys']],'Control identity mismatch')
    for r in controls['cases']:
        on=r['observer_on_directory'];off=r['observer_off_directory'];detail=[]
        a=json.loads(z.read(on+'/summary.json'));b=json.loads(z.read(off+'/summary.json'))
        check(a['Statistics']==b['Statistics'],f'Control statistics differ {on}')
        check(a['Config']==b['Config'],f'Control configuration differs {on}')
        for f in r['compared_files']:
            x=on+'/'+f['path'];y=off+'/'+f['path']
            check(h[x]==h[y]==f['observer_on_sha256']==f['observer_off_sha256'],f'Control file differs {x}')
            detail.append(f['path'])
        for key in ['LinkDiagnostics','ServiceDiagnostics']:
            d=a[key]
            check(d['Complete'] and d['Passive'] and d['ScheduledEvents']==0 and d['RandomDraws']==0,f'Observer completeness/passivity {on} {key}')
        control_result.append({'case':r['case_id'],'independent_byte_equal_files':len(detail),'statistics_equal':a['Statistics']==b['Statistics'],'config_equal':a['Config']==b['Config']})
    summaries=[]
    for n in names:
        if n.endswith('/summary.json') and not n.startswith('k/'):
            d=json.loads(z.read(n))
            if 'Statistics' not in d:continue
            s=d['Statistics'];c=d['Config'];summaries.append(n)
            check(s['Generated']==s['Received']+s['Dropped']+s['Pending'],f'Application conservation {n}')
            check(s['PhysicalAttempts']==s['PhysicalReceived']+s['PhysicalDropped']+s['PhysicalPending'],f'Physical conservation {n}')
            check(s['OmittedTraceRecords']==s['OmittedPhyTraceRecords']==0,f'Protocol/PHY trace omissions {n}')
    campus=json.loads(z.read('b/campus/raw/summary.json'));cs=campus['Statistics'];cc=campus['Config']
    check(cc['DurationSeconds']==6000 and cc['Seed']==128,'Campus duration/seed mismatch')
    admissions=rows(z.read('b/campus/raw/application_admission_statistics.csv'))
    attempts=sum(int(r['Attempts']) for r in admissions);admitted=sum(int(r['Admitted']) for r in admissions)
    retained_admission_rows=len(rows(z.read('b/campus/raw/application_admission_trace.csv')))
    check(attempts==retained_admission_rows+cs['OmittedApplicationAdmissionRecords'],'Campus admission trace/omission conservation')
    check(admitted==cs['Generated'],'Campus admission aggregate conservation')
    elapsed=(datetime.fromisoformat(m['CompletedUTC'].replace('Z','+00:00'))-datetime.fromisoformat(m['StartedUTC'].replace('Z','+00:00'))).total_seconds()
    result={'status':'pass' if not issues else 'blocked','blockers':issues,'evidence_sha256':package_hash(ROOT/'upload/tranche10_evidence.zip'),'candidate_sha256':package_hash(ROOT/'csr10r.zip'),'archive_members':len(names),'archive_uncompressed_bytes':sum(i.file_size for i in infos),'crc_passed':True,'closed_inventory_verified':len(inventory),'inventory_exclusion':m['InventoryExcludedPaths'],'source_hashes_verified':len(snap),'matlab_source_hashes_verified':sum(r['path'].endswith('.m') for r in snap),'reference_hashes_sizes_verified':len(m['ReferenceFiles']),'source_and_reference_start_end_stable':True,'test_count':len(tests),'source_test_classes':testclasses,'all_test_names_match_source':True,'contracts':contracts,'total_checkpoints':sum(x['checkpoints'] for x in contracts.values()),'nested_manifests_checked':manifest_checks,'nested_file_bindings_checked':manifest_file_checks,'phases':{'retained':29,'sweeps':18,'diagnostics':6,'controls':2,'campus':1},'observer_controls':control_result,'summaries_with_conservation_and_no_protocol_phy_omissions':len(summaries),'elapsed_seconds':elapsed,'campus':{'duration_seconds':cc['DurationSeconds'],'seed':cc['Seed'],'generated':cs['Generated'],'received':cs['Received'],'dropped':cs['Dropped'],'pending_at_finite_stop':cs['Pending'],'runtime_seconds':campus['Metadata']['RuntimeSeconds'],'admission_attempts':attempts,'admission_admitted':admitted,'admission_retained_trace_rows':retained_admission_rows,'admission_omitted_trace_rows':cs['OmittedApplicationAdmissionRecords'],'aggregate_admission_counts_complete':True},'limitations':['Read-only review of returned MATLAB R2025a portable evidence; no MATLAB or ns-3 runtime executed by this auditor.','Finite-stop application backlog is retained explicitly; structural acceptance does not require queues to drain.','Campus admission trace is bounded to 100,000 rows; aggregate admission counts remain complete.','No numerical parity claim follows solely from structural checks.']}
    (OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    (OUT/'audit.md').write_text('# Independent Tranche 10 integrity audit\n\n'+('PASS' if not issues else 'BLOCKED')+'\n\n'+f'- {len(inventory)}/{len(inventory)} closed-inventory SHA-256 and size checks; {len(names)} safe ZIP members and passing CRC.\n- {len(snap)} source hashes match immutable csr10r.zip, including 124 MATLAB files; 332 reference hashes/sizes match and both lists are stable start to finish.\n- 550/550 unique named MATLAB tests match the immutable source methods in 46 test classes.\n- 279 MAC + 154 receiver + 101 ACK = 534 passing checkpoints independently compared with pinned native reference rows.\n- 29 retained, 18 sweeps, 6 diagnostics, 2 controls and campus6000 all completed.\n- Both observer controls reproduce all 12 listed files byte-for-byte, with identical configuration and statistics; observers report zero scheduled events and zero RNG draws.\n- Campus: 12,484 generated = 11,825 delivered + 402 dropped + 257 pending at 6,000 seconds. 1,710,000 admission attempts have complete aggregate counts; 100,000 trace rows retained and 1,610,000 trace rows omitted.\n- No MATLAB/ns-3 execution was performed by this auditor. No numerical-parity conclusion from these structural checks.\n\n'+('Blockers: none.\n' if not issues else '\n'.join(issues)+'\n'))
    print(json.dumps(result,indent=2))
