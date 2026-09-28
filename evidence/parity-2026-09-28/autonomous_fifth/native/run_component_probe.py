#!/usr/bin/env python3
"""Compile public native component cases; no device, channel or network run."""
import json
import subprocess
from pathlib import Path

out=Path(__file__).resolve().parent
root=out.parents[1]
build=root/'autonomous/native_env/engine/build'
cmd=['g++','-std=c++23','-O0','-g','-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE',
     '-I'+str(build/'include'),str(out/'population_route_probe.cc'),'-L'+str(build/'lib'),
     '-Wl,-rpath,'+str(build/'lib'),'-lns3-dev-csr-debug','-lns3-dev-core-debug','-lns3-dev-network-debug',
     '-lstdc++exp','-o',str(out/'population_route_probe')]
(out/'compile_command.json').write_text(json.dumps(cmd,indent=2)+'\n')
with (out/'compile.log').open('w') as f:
    subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
with (out/'population_route_probe.log').open('w') as f:
    subprocess.run([str(out/'population_route_probe')],stdout=f,stderr=subprocess.STDOUT,check=True)
print('All native population/route component cases passed.')
