"""Offline identity/completeness audit of the returned terminal full-run batch."""
from pathlib import Path
import csv, hashlib, json, zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'terminal6000_return'
DATA = OUT / 'data'
KIT = ROOT / 'recovered/issued/csr6000'
ARCHIVE = ROOT / 'upload/out_6000_terminal_20260929_173950.zip'
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()
def read(p): return json.loads(p.read_text())
checks=[]
def check(name, value):
    checks.append({'check':name,'passed':bool(value)})
    assert value, name

with zipfile.ZipFile(ARCHIVE) as z:
    check('ZIP CRC',z.testzip() is None)
    check('unique ZIP members',len(z.namelist())==len(set(z.namelist())))
    member_count=len(z.namelist())
plan=read(KIT/'plan.json')
files=read(KIT/'FILES.json')['files']
for row in files:
    p=KIT/row['path']
    check('issued file '+row['path'],sha(p)==row['sha256'] and p.stat().st_size==row['bytes'])
invocations=list(DATA.glob('invocations/*/provenance.json'))
check('one invocation',len(invocations)==1)
inv=invocations[0].parent; prov=read(inv/'provenance.json'); status=read(inv/'batch_status.json')
check('exact issued plan',prov['plan']==plan)
check('exact plan hash',prov['identity']['plan_sha256']==sha(KIT/'plan.json'))
check('batch completed',status['completed'] and not status['error_identifier'])
check('selected terminal candidate',prov['simulation_class']=='ac.TerminalSimulation')
check('natural streams',prov['random_mode']=='natural')
check('no drain',not prov['drain_interval_added'])
check('nanosecond timing',prov['transport_mode']=='nanoseconds')
check('native provisional policy',prov['retry_policy']=='native-provisional')
expected_sources={r['path']:r['sha256'] for r in plan['source_manifest']}
check('runtime source snapshot',expected_sources=={r['path']:r['sha256'] for r in prov['model_source_snapshot']})
for key in ['source_manifest','candidate_manifest','input_manifest','runner_manifest']:
    base=KIT/'model' if key=='source_manifest' else KIT
    for row in plan[key]: check(key+' '+row['path'],sha(base/row['path'])==row['sha256'])
cases=[]
for seed in [131,132]:
    d=DATA/f's{seed}/attempt_001'; c=read(d/'completion.json'); case=read(d/'case_summary.json')
    check(f'{seed} sealed completed',c['completed'] and case['completed'] and case['final_simulation_time_s']==6000)
    check(f'{seed} completion plan',c['identity']['plan_sha256']==sha(KIT/'plan.json'))
    check(f'{seed} completion runtime',c['identity']['runtime']==status['runtime'])
    for row in c['files']:
        p=d/row['path']
        check(f'{seed} export {row["path"]}',p.is_file() and sha(p)==row['sha256'] and p.stat().st_size==row['bytes'])
    cm=read(d/'raw/case_manifest.json'); sm=read(d/'raw/summary.json'); s=sm['Statistics']
    check(f'{seed} model stable',cm['execution_completed'] and cm['source_files_stable'] and cm['structural_checks_passed'])
    check(f'{seed} model source matches',{r['path']:r['sha256'] for r in cm['source_files']}==expected_sources)
    check(f'{seed} native pin',cm['ns3_source_commit']==plan['native_source_commit'])
    check(f'{seed} original input bytes',sha(d/'raw/scenario.csv')==sha(KIT/f'inputs/s{seed}.csv'))
    check(f'{seed} core trace complete',s['OmittedTraceRecords']==0 and s['OmittedPhyTraceRecords']==0)
    check(f'{seed} expected admission prefix omission',s['OmittedApplicationAdmissionRecords']==1610000)
    random=read(d/'random_summary.json')
    check(f'{seed} autonomous inputs',random['mode']=='natural' and random['native_transmissions_available']==0 and all(r['native_available']==0 for r in random['counts']))
    check(f'{seed} random count closes',sum(r['requested'] for r in random['counts'])==random['draw_count'])
    counters=list(csv.DictReader((d/'raw/application_admission_statistics.csv').open()))
    cases.append({'seed':seed,'completed':True,'wall_seconds':case['wall_seconds'],
        'sealed_files_verified':len(c['files']),'protocol_omissions':s['OmittedTraceRecords'],
        'phy_omissions':s['OmittedPhyTraceRecords'],'admission_prefix_omissions':s['OmittedApplicationAdmissionRecords'],
        'random_draws':random['draw_count'],'generated':s['Generated'],'delivered':s['Received'],
        'unresolved':s['Generated']-s['Received'],'raw_dropped':s['Dropped'],'raw_pending':s['Pending'],
        'late_deliveries':s['LateDeliveries'],'late_custody_recoveries':s['LateCustodyRecoveries']})
receipt={'schema':'csr-terminal6000-return-identity-audit-v1','status':'pass',
    'archive':{'path':str(ARCHIVE.relative_to(ROOT)),'bytes':ARCHIVE.stat().st_size,'sha256':sha(ARCHIVE),'members':member_count},
    'issued_kit_sha256':sha(ROOT/'recovered/csr-6000-terminal-parity-tests.zip'),
    'issued_plan_sha256':sha(KIT/'plan.json'),'bound_issued_files':len(files),
    'runtime':status['runtime'],'wall_seconds':status['wall_seconds'],'cases':cases,
    'checks_passed':len(checks),'checks':checks,
    'archive_status_note':'Embedded archive_completed=false was serialized before ZIP creation. Both sealed cases and all returned member bytes verify; this is not a simulation failure.',
    'scope':'Identity and required evidence completeness. Numerical parity and raw accounting are separate audits.'}
(OUT/'identity_audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='checks'},indent=2))
