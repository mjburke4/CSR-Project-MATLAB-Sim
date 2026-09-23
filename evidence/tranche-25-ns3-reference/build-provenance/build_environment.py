#!/usr/bin/env python3
"""Rebuild the exact archived CSR/engine trees without altering tracked files."""
import hashlib,json,os,platform,subprocess,tarfile,time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'build-provenance'
PIN='486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
ENGINE='6b5cd24ea80713ce16d88575869aedd6f432bdae'
MODULES=('csr','spectrum','buildings','propagation','mobility','antenna','network','stats','core')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):Path(p).write_text(json.dumps(obj,indent=2)+'\n')
def execute(argv,name):
    start=time.monotonic();log=OUT/name
    print('Executing '+name,flush=True)
    with log.open('wb') as f:r=subprocess.run(list(map(str,argv)),stdout=f,stderr=subprocess.STDOUT)
    result={'argv':list(map(str,argv)),'exit_code':r.returncode,'wall_seconds':time.monotonic()-start,'log':name,'log_sha256':sha(log)}
    write(OUT/(name+'.json'),result)
    if r.returncode:raise RuntimeError(f'Failed: {log}')
    return result
def tracked(kind,folder):
    entries={}
    with tarfile.open(ROOT/(kind+'.tar.gz')) as t:
        members=t.getmembers();prefix=members[0].name.split('/')[0]+'/'
        for member in members:
            if not (member.isfile() or member.issym()):continue
            name=member.name.removeprefix(prefix);p=folder/name
            expected=member.linkname.encode() if member.issym() else t.extractfile(member).read()
            actual=str(p.readlink()).encode() if member.issym() else p.read_bytes()
            if actual!=expected:raise ValueError('Tracked file changed: '+str(p))
            entries[name]=hashlib.sha256(actual).hexdigest()
    return {'file_count':len(entries),'file_sha256':entries,'all_archive_bytes_match':True}
def main():
    OUT.mkdir(exist_ok=True);source=ROOT/'csr';engine=ROOT/'engine';build=engine/'build';cache=engine/'cmake-cache'
    before={k:tracked(k,p) for k,p in [('source',source),('engine',engine)]}
    link=engine/'contrib/csr'
    if not link.exists():link.symlink_to(source,target_is_directory=True)
    cmake=ROOT/'tooling/cmake/data/bin/cmake';ninja=ROOT/'tooling/bin/ninja'
    config=[cmake,'-S',engine,'-B',cache,'-G','Ninja','-DCMAKE_MAKE_PROGRAM='+str(ninja),'-DCMAKE_BUILD_TYPE=Debug','-DNS3_ENABLED_MODULES='+';'.join(MODULES),'-DNS3_EXAMPLES=OFF','-DNS3_TESTS=OFF','-DNS3_WARNINGS_AS_ERRORS=OFF','-DNS3_PRECOMPILE_HEADERS=OFF','-DNS3_CCACHE=OFF','-DNS3_GTK3=OFF','-DNS3_GSL=OFF','-DNS3_SQLITE=OFF','-DNS3_EIGEN=OFF','-DNS3_VISUALIZER=OFF','-DNS3_ASSERT=ON','-DNS3_LOG=ON']
    configure=execute(config,'configure.log')
    built=execute([cmake,'--build',cache,'--parallel','2'],'engine-build.log')
    runner=ROOT/'t25-pristine';library=build/'lib'
    compile_cmd=['g++','-std=c++23','-g','-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE','-DSTACKTRACE_LIBRARY_IS_LINKED=1','-D__LINUX__','-I'+str(build/'include'),source/'csr-opnet-scenario-runner.cc','-L'+str(library),'-Wl,-rpath,'+str(library),'-Wl,--no-as-needed','-lns3-dev-csr-debug','-Wl,--as-needed',*[f'-lns3-dev-{n}-debug' for n in MODULES[1:]],'-lstdc++exp','-o',runner]
    compiled=execute(compile_cmd,'pristine-compile.log')
    after={k:tracked(k,p) for k,p in [('source',source),('engine',engine)]}
    assert before==after
    write(OUT/'tracked-source-verification.json',after)
    elf={}
    for name in MODULES:
        p=library/f'libns3-dev-{name}-debug.so'
        assert p.read_bytes()[:4]==b'\x7fELF'
        symbols=subprocess.check_output(['nm','-D','--defined-only',str(p)],text=True)
        assert len(symbols.strip().splitlines())>0
        elf[p.name]={'bytes':p.stat().st_size,'sha256':sha(p),'defined_symbols':len(symbols.strip().splitlines())}
    write(OUT/'elf-verification.json',elf)
    ldd=execute(['ldd',runner],'ldd.log');assert 'not found' not in (OUT/'ldd.log').read_text()
    tools={}
    for name,p in [('compiler',Path('/usr/bin/g++').resolve()),('linker',Path('/usr/bin/ld').resolve()),('cmake',cmake),('ninja',ninja)]:
        tools[name]={'path':str(p),'sha256':sha(p),'version':subprocess.check_output([p,'--version'],text=True).strip()}
    record={'schema':'csr-tranche25-native-build-v1','status':'passed','ns3_source_commit':PIN,'engine_commit':ENGINE,'source_tree':'b611b233fb369569b98f0914ece24d029ccc2f42','engine_tree':'f30343185fb057e3a9cdd54f496cca0cef49ae23','new_compilation':True,'production_source_unchanged':True,'engine_source_unchanged':True,'observer_enabled':False,'runner_sha256':sha(runner),'archives':json.loads((ROOT/'archive-verification.json').read_text()),'toolchain':tools,'platform':platform.platform(),'configure':configure,'engine_build':built,'pristine_compile':compiled,'ldd':ldd,'libraries':elf,'tracked_source_verification':'build-provenance/tracked-source-verification.json','tracked_source_verification_sha256':sha(OUT/'tracked-source-verification.json'),'recorded_utc':datetime.now(timezone.utc).isoformat()}
    write(ROOT/'build.json',record);print(json.dumps({k:record[k] for k in ('status','runner_sha256','new_compilation')},indent=2))
if __name__=='__main__':main()
