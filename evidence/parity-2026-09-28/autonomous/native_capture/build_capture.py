#!/usr/bin/env python3
"""Rebuild the hash-pinned passive capture in its isolated overlay."""
from pathlib import Path
import subprocess,json,hashlib
from prepare_overlay import prepare

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
RUN=HERE/'run'
def main():
    env=ROOT/'autonomous/native_env'
    for name,expected in [('csr','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'),
                          ('engine','6b5cd24ea80713ce16d88575869aedd6f432bdae')]:
        result=subprocess.check_output(['git','-C',str(env/name),'rev-parse','HEAD'],text=True).strip()
        assert result==expected,(name,result)
        dirty=subprocess.check_output(['git','-C',str(env/name),'status','--porcelain','--untracked-files=no'],text=True)
        assert not dirty.strip(),(name,dirty)
    prepare(env/'csr/model',RUN/'overlay/ns3')
    build=env/'engine/build'
    driver=HERE/'vendor/capture.cc'
    assert hashlib.sha256(driver.read_bytes()).hexdigest()=='b859a78a9e260e87689126569aeb6693861ffb78f28da2d296ff9eaa4287cc4d'
    cmd=['g++','-std=c++23','-O0','-g','-DNS3_ASSERT_ENABLE',
         '-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE',
         '-DSTACKTRACE_LIBRARY_IS_LINKED=1','-D__LINUX__',
         '-I'+str(RUN/'overlay'),'-I'+str(build/'include'),str(driver),
         '-L'+str(build/'lib'),'-Wl,-rpath,'+str(build/'lib'),
         '-Wl,--no-as-needed','-lns3-dev-csr-debug','-Wl,--as-needed']
    cmd += ['-lns3-dev-'+name+'-debug' for name in ['spectrum','buildings',
           'propagation','mobility','antenna','network','stats','core']]
    cmd += ['-lstdc++exp','-o',str(RUN/'autonomous-capture')]
    (HERE/'compile-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
    with (RUN/'compile.log').open('w') as f:
        subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__': main()
