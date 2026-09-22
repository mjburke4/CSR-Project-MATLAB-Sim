#!/usr/bin/env python3
"""Execute every input against production native MAC; save MATLAB comparison oracle."""
import concurrent.futures,csv,hashlib,json,pathlib,resource,subprocess,time
P=pathlib.Path(__file__).resolve().parent
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
rows=list(csv.DictReader((P/'vectors.csv').open()))
def one(row):
 args=[str(P/'native-vectors'),row['kind'],row['local'],row['reported'],row['reduction'],row['initial_draw'] or '-1',row['counters']]
 start=time.monotonic();r=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
 result={'case_id':row['case_id'],'status':'unclassified','active_nodes':'','range':'','slot':'','return_code':r.returncode,'diagnostic':''}
 lines=[line for line in r.stdout.splitlines() if line.startswith('RULE_RESULT,')]
 if r.returncode==0 and len(lines)==1:
  _,result['active_nodes'],result['range'],result['slot']=lines[0].split(',')
  result['status']='range' if row['kind']=='range' else 'slot'
 elif r.returncode!=0 and 'historical next_tslot modulo probe exhausted slots 0..R-1' in r.stdout:
  result['status']='probe_exhausted';result['diagnostic']='historical next_tslot modulo probe exhausted slots 0..R-1'
 result['fixture_pass']=str(result['status']==row['expected_class']).lower()
 return result,r.stdout,time.monotonic()-start
start=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(one,rows))
with (P/'native_reference.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(results[0][0]));w.writeheader();w.writerows(x[0] for x in results)
with (P/'native_cases.log').open('w') as f:
 for out,log,secs in results: f.write('\nCASE '+out['case_id']+'\n'+log)
failures=[r for r,_,_ in results if r['fixture_pass']!='true']
summary={'completed':True,'fixture_pass':not failures,'cases':len(rows),'selection_cases':sum(r['kind']=='select' for r in rows),'range_cases':sum(r['kind']=='range' for r in rows),'expected_abort_cases':sum(r['expected_class']=='probe_exhausted' for r in rows),'unexpected_results':failures,'seconds':time.monotonic()-start,'reference_sha256':hashlib.sha256((P/'native_reference.csv').read_bytes()).hexdigest(),'vectors_sha256':hashlib.sha256((P/'vectors.csv').read_bytes()).hexdigest(),'meaning':'Native fixture execution only; MATLAB agreement is evaluated by run_slot_vectors.m.'}
(P/'native_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
raise SystemExit(bool(failures))
