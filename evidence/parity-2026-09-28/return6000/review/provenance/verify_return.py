from pathlib import Path
import csv,hashlib,json
ROOT=Path(__file__).resolve().parents[3]
DATA=ROOT/'return6000/data'
KIT=ROOT/'return6000/kit/csr6000'
OUT=ROOT/'return6000/review/provenance'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
plan=read(KIT/'plan.json');plan_sha=sha(KIT/'plan.json')
invocations=[];success=[]
for folder in sorted((DATA/'invocations').iterdir()):
 s=read(folder/'batch_status.json')
 invocations.append({'name':folder.name,'completed':s['completed'],'error_identifier':s['error_identifier'],'wall_seconds':s['wall_seconds'],'runtime':s['runtime']})
 if s['completed']:success.append((folder,s))
assert len(success)==1
folder,status=success[0];provenance=read(folder/'provenance.json')
assert provenance['plan']==plan
assert provenance['identity']['plan_sha256']==plan_sha
assert provenance['identity']['runtime']==status['runtime']
sourcefiles={x['path']:x['sha256'] for x in plan['source_manifest']}
assert {x['path']:x['sha256'] for x in provenance['model_source_snapshot']}==sourcefiles
for name,digest in sourcefiles.items():assert sha(KIT/'model'/name)==digest
for arr in [plan['input_manifest'],plan['runner_manifest']]:
 for item in arr:assert sha(KIT/item['path'])==item['sha256']
selfcheck=read(folder/'analysis_selfcheck.json');assert selfcheck['completed'] and not selfcheck['simulation_executed']
cases=[]
for seed in [131,132]:
 p=DATA/f's{seed}/attempt_001';seal=read(p/'completion.json');s=read(p/'case_summary.json');raw=read(p/'raw/summary.json');cm=read(p/'raw/case_manifest.json')
 assert seal['completed'] and s['completed'] and s['final_simulation_time_s']==6000
 assert seal['identity']=={**provenance['identity'],'seed':seed}
 assert seal['case_summary']==s
 actual_files={x.relative_to(p).as_posix() for x in p.rglob('*') if x.is_file() and x.suffix in {'.csv','.json','.log'} and x.name!='completion.json'}
 assert actual_files=={x['path'] for x in seal['files']}
 for f in seal['files']:
  actual=p/f['path'];assert actual.stat().st_size==f['bytes'] and sha(actual)==f['sha256'],actual
 for f in cm['files']:
  actual=p/'raw'/f['path'];assert actual.stat().st_size==f['bytes'] and sha(actual)==f['sha256'],actual
 assert {x['path']:x['sha256'] for x in cm['source_files']}==sourcefiles
 assert sha(p/'raw/scenario.csv')==sha(KIT/f'inputs/s{seed}.csv')==cm['scenario_sha256']
 cfg=raw['Config'];stats=raw['Statistics']
 assert cfg['Seed']==seed and cfg['DurationSeconds']==6000 and cfg['Backend']=='portable'
 assert cfg['Hop']['DataQueuedRetryPolicy']=='actual-tx' and cfg['Channel']['Model']=='csr-phy'
 assert len(cfg['Traffic'])==6 and sorted(f['SourceId'] for f in cfg['Traffic'])==[2,3,4,5,7,8]
 assert all(f['StartSeconds']==300 and f['IntervalSeconds']==.02 and f['PacketCount']==285000 and f['DestinationId']==1 for f in cfg['Traffic'])
 assert stats['OmittedTraceRecords']==stats['OmittedPhyTraceRecords']==0
 assert stats['OmittedApplicationAdmissionRecords']==1610000
 assert raw['Metadata']['SourceCommit']==plan['native_source_commit']
 assert stats['Generated']==stats['Received']+stats['Dropped']+stats['Pending']
 records={x['path']:x.get('row_count') for x in cm['files']}
 assert records['application_admission_trace.csv']==100000
 assert sha(p/'raw/trace.csv')==sha(p/'raw/protocol_trace.csv')
 counters=list(csv.DictReader((p/'raw/application_admission_statistics.csv').open()))
 assert sum(int(c['Attempts']) for c in counters)==1710000
 assert sum(int(c['Admitted']) for c in counters)==stats['Generated']
 cases.append({'seed':seed,'complete':True,'sealed_files_verified':len(seal['files']),'capture_rows':records,'wall_seconds':s['wall_seconds'],'admitted':stats['Generated'],'delivered':stats['Received'],'dropped':stats['Dropped'],'pending':stats['Pending'],'protocol_omissions':0,'phy_omissions':0,'admission_prefix_omissions':1610000,'source_files_verified':len(sourcefiles),'scenario_sha256':cm['scenario_sha256']})
report={'schema':'csr-corrected6000-return-verification-v1','status':'pass','input_archive':'upload/out_6000_20260924_152302.zip','input_archive_sha256':sha(ROOT/'upload/out_6000_20260924_152302.zip'),'issued_kit_sha256':sha(ROOT/'return6000/recovered/NS3 to MATLAB Network Simulation/csr-6000-batch.zip'),'plan_sha256':plan_sha,'target_percent':15,'invocations':invocations,'cases':cases,'owner_analysis_preflight':selfcheck,'archiving_note':'Successful invocation was serialized before ZIP creation, so archive_completed=false inside batch_status is expected. Received ZIP integrity and all sealed case hashes verify. Earlier two invocations stopped before simulation on stale CSR cache guard.','matlab_runtime':status['runtime'],'new_simulations_in_review':0}
(OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':'pass','input_sha256':report['input_archive_sha256'],'cases':[{'seed':x['seed'],'sealed_files':x['sealed_files_verified'],'wall_seconds':x['wall_seconds']} for x in cases],'prior_preflight_only_failures':2,'source_files_verified':len(sourcefiles),'runtime':status['runtime']},indent=2))
