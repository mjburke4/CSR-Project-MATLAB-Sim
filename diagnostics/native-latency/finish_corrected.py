from pathlib import Path
import sys,json,subprocess,time,hashlib,difflib,csv,shutil
R=Path(__file__).resolve().parent;K=R.parent/'latency-tests';S=R.parent/'ns3-repo';B=R/'engine/build';O=R/'corrected';overlay=O/'overlay'
sys.path.insert(0,str(K/'mac'));import native_build_support as N;import run_native as M
from compare_mac import read,compare
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=N.input_snapshot(S,B);N.check_source(S,B)
records=[]
def run(args,name):
 start=time.monotonic()
 with (O/(name+'.log')).open('w') as f:r=subprocess.run(list(map(str,args)),stdout=f,stderr=subprocess.STDOUT,timeout=300)
 rec={'stage':name,'argv':list(map(str,args)),'exit_code':r.returncode,'seconds':time.monotonic()-start};records.append(rec)
 (O/'isolated-execution.json').write_text(json.dumps(records,indent=2)+'\n');print(name,r.returncode,round(rec['seconds'],2),flush=True)
 if r.returncode:raise RuntimeError(name)
dest=O/'native-mac-isolated';dest.mkdir();cases=read(K/'mac/cases.csv')
fields=list(cases[0]);samples=[];inputs=[]
for case in cases:
 d=dest/case['case_id'];d.mkdir()
 with (d/'case.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow(case)
 run([O/'native-mac/fixture',d/'case.csv',d],'isolated-'+case['case_id'])
 samples+=read(d/'sampled.csv');inputs+=read(d/'inputs.csv')
 shutil.copy2(d/(case['case_id']+'-trace.csv'),dest/(case['case_id']+'-trace.csv'))
for filename,rows in [('sampled.csv',samples),('inputs.csv',inputs)]:
 with (dest/filename).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
M.exact_events(dest,cases)
result=compare(read(R/'matlab-fixtures/mac-events.csv'),read(dest/'events.csv'),cases);(O/'mac-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['discrete_rows_match'] and result['structural_passed']
text=(K/'replay/hop_replay.cc').read_text();anchor='mac.SetReservationSlotOverrideForDifferentialRun(1);';assert text.count(anchor)==1
text=text.replace(anchor,'csr_t11::rawDraw=[](uint32_t node,int lo,int hi){ if(node!=2 || lo!=1 || hi<1)throw std::runtime_error("Unexpected draw domain"); return 1; };')
src=O/'hop_replay.cc';src.write_text(text);(O/'hop_replay.cc.patch').write_text(''.join(difflib.unified_diff((K/'replay/hop_replay.cc').read_text().splitlines(True),text.splitlines(True),fromfile='original/hop_replay.cc',tofile='corrected/hop_replay.cc')))
dest=O/'native-replay';dest.mkdir();binary=dest/'fixture';cmd=N.compile_runner(S,B,binary,'g++');cmd[cmd.index(str(S/'csr-opnet-scenario-runner.cc'))]=str(src);cmd.insert(1,'-I'+str(overlay));run(cmd,'compile-replay')
run([binary,K/'replay/inputs.csv',dest/'hop.csv'],'run-replay')
run([sys.executable,K/'replay/compare_hop_replay.py',R/'matlab-fixtures/hop.csv',dest/'hop.csv','--output',O/'hop-comparison.json'],'compare-hop')
N.check_source(S,B);assert before==N.input_snapshot(S,B)
(O/'provenance.json').write_text(json.dumps({'source_pin':N.PIN,'source_and_libraries_unchanged':True,'source_inputs':before,'base_build_receipt_sha256':sha(R/'build-receipt.json'),'mac_isolated_process_per_case':True,'mac_isolation_reason':'Repeated zero-byte early_257 trace in combined-process runs; original attempts preserved. Each independent process uses same per-case seed/reset and binary.','files':{str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file()}},indent=2)+'\n')
