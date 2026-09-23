from pathlib import Path
import sys,hashlib,json,subprocess,time,difflib,shutil
R=Path(__file__).resolve().parent;K=R.parent/'latency-tests';S=R.parent/'ns3-repo';B=R/'engine/build';O=R/'corrected';O.mkdir(exist_ok=False)
sys.path.insert(0,str(R.parent/'matlab-repo/scripts'))
from build_tranche11_overlay import build as overlay_build
sys.path.insert(0,str(K/'mac'))
import native_build_support as N
import run_native as M
from compare_mac import read,compare
sys.path.insert(0,str(K/'replay'))
from compare_hop_replay import inspect
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=N.input_snapshot(S,B);N.check_source(S,B)
overlay=O/'overlay';original_overlay=overlay_build(S,overlay)
header=overlay/'ns3/csr-mac-core.h';text=header.read_text()
old='    int remaining = rng->GetInteger (1, slotRange);'
new='''    // LATENCY TEST SEAM: prescribed raw ordinal; native scan and timer unchanged.
    int remaining = csr_t11::rawDraw
      ? csr_t11::rawDraw (m_nodeId, 1, slotRange)
      : rng->GetInteger (1, slotRange);'''
assert text.count(old)==1;text=text.replace(old,new);header.write_text(text)
patch=[]
for name in ['csr-mac-core.h','csr-net-device.h']:
 patch.extend(difflib.unified_diff((S/'model'/name).read_text().splitlines(True),(overlay/'ns3'/name).read_text().splitlines(True),fromfile='pinned/'+name,tofile='overlay/'+name))
(overlay/'seams.patch').write_text(''.join(patch))
receipt={'schema':'latency-selection-only-overlay-v1','base_t11_recipe_sha256':sha(R.parent/'matlab-repo/scripts/build_tranche11_overlay.py'),'base_overlay_manifest':original_overlay,'scope':'Raw current-profile ordinal replacement only; ordinary native timer phase, countdown, occupancy scan, PHY airtime, ACK/HOP behavior retained. Transport/resolved hooks remain empty.','patched_files':{n:sha(overlay/'ns3'/n) for n in ['csr-mac-core.h','csr-net-device.h']},'patch_sha256':sha(overlay/'seams.patch')}
(overlay/'overlay.json').write_text(json.dumps(receipt,indent=2)+'\n')
records=[]
def run(args,name):
 start=time.monotonic()
 with (O/(name+'.log')).open('w') as f:r=subprocess.run(list(map(str,args)),stdout=f,stderr=subprocess.STDOUT,timeout=300)
 rec={'stage':name,'argv':list(map(str,args)),'exit_code':r.returncode,'seconds':time.monotonic()-start};records.append(rec)
 (O/'execution.json').write_text(json.dumps(records,indent=2)+'\n');print(name,r.returncode,round(rec['seconds'],2),flush=True)
 if r.returncode:raise RuntimeError(name)
def compile(src,target,name):
 cmd=N.compile_runner(S,B,target,'g++');cmd[cmd.index(str(S/'csr-opnet-scenario-runner.cc'))]=str(src);cmd.insert(1,'-I'+str(overlay));run(cmd,name)
control=O/'inert-mac';control.mkdir()
compile(K/'mac/mac_tests.cc',control/'mac-tests','compile-inert-mac')
run([control/'mac-tests',K/'mac/cases.csv',control],'run-inert-mac')
checks=M.exact_events(control,read(K/'mac/cases.csv'))
inert_files=['events.csv','sampled.csv','inputs.csv']+[p.name for p in sorted((R/'native-mac').glob('*-trace.csv'))]
inert={name:sha(control/name)==sha(R/'native-mac'/name) for name in inert_files}
(O/'inert-control.json').write_text(json.dumps({'all_equal':all(inert.values()),'byte_equal_files':inert,'checks':checks},indent=2)+'\n');assert all(inert.values())
for fixture,srcname in [('mac','mac_tests.cc'),('replay','hop_replay.cc')]:
 text=(K/fixture/srcname).read_text();anchor='mac.SetReservationSlotOverrideForDifferentialRun(1);';assert text.count(anchor)==1
 text=text.replace(anchor,'csr_t11::rawDraw=[](uint32_t node,int lo,int hi){ if(node!=2 || lo!=1 || hi<1)throw std::runtime_error("Unexpected draw domain"); return 1; };')
 src=O/srcname;src.write_text(text)
 (O/(srcname+'.patch')).write_text(''.join(difflib.unified_diff((K/fixture/srcname).read_text().splitlines(True),text.splitlines(True),fromfile='original/'+srcname,tofile='corrected/'+srcname)))
 dest=O/('native-'+fixture);dest.mkdir();binary=dest/'fixture';compile(src,binary,'compile-'+fixture)
 if fixture=='mac':
  run([binary,K/'mac/cases.csv',dest],'run-'+fixture);native_checks=M.exact_events(dest,read(K/'mac/cases.csv'));res=compare(read(R/'matlab-fixtures/mac-events.csv'),read(dest/'events.csv'),read(K/'mac/cases.csv'));(O/'mac-comparison.json').write_text(json.dumps(res,indent=2)+'\n')
 else:
  run([binary,K/'replay/inputs.csv',dest/'hop.csv'],'run-'+fixture)
  run([sys.executable,K/'replay/compare_hop_replay.py',R/'matlab-fixtures/hop.csv',dest/'hop.csv','--output',O/'hop-comparison.json'],'compare-hop')
N.check_source(S,B);assert before==N.input_snapshot(S,B)
(O/'provenance.json').write_text(json.dumps({'source_pin':N.PIN,'source_and_libraries_unchanged':True,'source_inputs':before,'base_build_receipt_sha256':sha(R/'build-receipt.json'),'files':{str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file()}},indent=2)+'\n')
