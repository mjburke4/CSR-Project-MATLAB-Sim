#!/usr/bin/env python3
from pathlib import Path
import subprocess,json,sys
R=Path(__file__).resolve().parents[2];N=R/'mac_replay/native';B=R/'startup131/environment/engine/build'
cmd=['g++','-std=c++23','-O0','-g','-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE','-DSTACKTRACE_LIBRARY_IS_LINKED=1','-D__LINUX__','-I'+str(N/'overlay'),'-I'+str(B/'include'),str(N/'replay.cc'),'-L'+str(B/'lib'),'-Wl,-rpath,'+str(B/'lib'),'-Wl,--no-as-needed','-lns3-dev-csr-debug','-Wl,--as-needed']+['-lns3-dev-'+n+'-debug' for n in ['spectrum','buildings','propagation','mobility','antenna','network','stats','core']]+['-lstdc++exp','-o',str(N/'mac-replay')]
with (N/'compile-replay.log').open('w') as f:p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
assert p.returncode==0,(N/'compile-replay.log').read_text()[-10000:]
print('Replay compiled')
for node in [2,4,8]:
 D=N/f'replay{node}';D.mkdir(exist_ok=True)
 cmd=[str(N/'mac-replay'),str(R/'mac_replay/inputs'),str(D/'replay.log'),str(D/'ns3-trace.csv'),str(node)]
 with (D/'run.log').open('w') as f:p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 print(node,p.returncode,flush=True)
 (D/'receipt.json').write_text(json.dumps(dict(command=cmd,exit_code=p.returncode),indent=2)+'\n')
