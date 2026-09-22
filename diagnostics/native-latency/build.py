from pathlib import Path
import subprocess,json,time,hashlib,sys
R=Path(__file__).resolve().parent
S=R.parent/'ns3-repo';E=R/'engine';B=E/'build';O=R/'build-provenance';O.mkdir(exist_ok=True)
sys.path.insert(0,str(R.parent/'latency-tests/mac'))
import native_build_support as N
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args,name):
 start=time.monotonic()
 with (O/name).open('w') as f: p=subprocess.run(list(map(str,args)),stdout=f,stderr=subprocess.STDOUT)
 record={'argv':list(map(str,args)),'exit_code':p.returncode,'wall_seconds':time.monotonic()-start,'log_sha256':digest(O/name)}
 (O/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
 print(name,p.returncode,round(record['wall_seconds'],2),flush=True)
 if p.returncode: raise RuntimeError(name)
 return record
C=R/'tooling/cmake/data/bin/cmake'; J=R/'tooling/bin/ninja'
cfg=run([C,'-S',E,'-B',E/'cmake-cache','-G','Ninja','-DCMAKE_MAKE_PROGRAM='+str(J),'-DCMAKE_BUILD_TYPE=Debug','-DNS3_ENABLED_MODULES='+';'.join(N.MODULES),'-DNS3_EXAMPLES=OFF','-DNS3_TESTS=OFF','-DNS3_WARNINGS_AS_ERRORS=OFF','-DNS3_PRECOMPILE_HEADERS=OFF','-DNS3_CCACHE=OFF','-DNS3_GTK3=OFF','-DNS3_GSL=OFF','-DNS3_SQLITE=OFF','-DNS3_EIGEN=OFF','-DNS3_VISUALIZER=OFF','-DNS3_ASSERT=ON','-DNS3_LOG=ON'],'configure.log')
built=run([C,'--build',E/'cmake-cache','--parallel','2'],'build.log')
N.check_source(S,B)
runner=R/'csr-opnet-scenario-runner'
compiled=run(N.compile_runner(S,B,runner,'g++'),'runner-compile.log')
linked=run(['ldd','-r',runner],'ldd.log')
assert 'not found' not in (O/'ldd.log').read_text()
assert 'undefined symbol' not in (O/'ldd.log').read_text()
record={'source_commit':N.PIN,'engine_commit':'6b5cd24ea80713ce16d88575869aedd6f432bdae','engine_archive_sha256':digest(R/'engine.tar.gz'),'engine_tracked_bytes_matched_prior_t25_before_build':True,'configure':cfg,'build':built,'runner_compile':compiled,'linking':linked,'runner_sha256':digest(runner),'inputs':N.input_snapshot(S,B),'production_source_unchanged':True,'status':'built-not-yet-regression-checked'}
(R/'build-receipt.json').write_text(json.dumps(record,indent=2)+'\n')
