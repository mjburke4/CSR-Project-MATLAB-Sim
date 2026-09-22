#!/usr/bin/env python3
import argparse,pathlib,subprocess,json,os
p=argparse.ArgumentParser();p.add_argument('--engine-build',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path);a=p.parse_args();N=pathlib.Path(__file__).resolve().parent;B=a.engine_build.resolve();out=a.output or N/'receiver-replay'
cmd=['g++','-std=c++23','-O0','-g','-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE','-DSTACKTRACE_LIBRARY_IS_LINKED=1','-D__LINUX__','-I'+str(N/'overlay'),'-I'+str(B/'include'),str(N/'replay.cc'),'-L'+str(B/'lib'),'-Wl,-rpath,'+str(B/'lib'),'-Wl,--no-as-needed','-lns3-dev-csr-debug','-Wl,--as-needed']+['-lns3-dev-'+n+'-debug' for n in ['spectrum','buildings','propagation','mobility','antenna','network','stats','core']]+['-lstdc++exp','-o',str(out)]
r=subprocess.run(cmd);assert r.returncode==0
(N/'build-receipt.json').write_text(json.dumps(dict(command=cmd,exit_code=r.returncode),indent=2)+'\n')
