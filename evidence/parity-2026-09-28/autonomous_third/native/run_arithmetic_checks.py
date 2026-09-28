#!/usr/bin/env python3
"""Compile/run arithmetic-only probes against restored pinned ns-3 headers."""
from pathlib import Path
import json,subprocess,sys,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
BUILD=ROOT/'autonomous/native_env/engine/build'
cmd=['g++','-std=c++23','-O0','-g','-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE',
     '-I'+str(BUILD/'include'),str(OUT/'arithmetic_probe.cc'),'-L'+str(BUILD/'lib'),
     '-Wl,-rpath,'+str(BUILD/'lib'),'-lns3-dev-csr-debug','-lns3-dev-core-debug',
     '-lns3-dev-network-debug','-lstdc++exp','-o',str(OUT/'arithmetic_probe')]
(OUT/'compile_command.json').write_text(json.dumps(cmd,indent=2)+'\n')
with (OUT/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
with (OUT/'arithmetic_values.csv').open('w') as f:subprocess.run([str(OUT/'arithmetic_probe')],stdout=f,check=True)
subprocess.run([sys.executable,str(OUT/'audit_callback_times.py')],check=True)
paths=[ROOT/'autonomous/native_env/csr/model/csr-phy-model.h',
       ROOT/'autonomous/native_env/csr/model/csr-net-device.h',
       ROOT/'autonomous/native_env/engine/src/core/model/nstime.h',
       ROOT/'autonomous/native_env/engine/src/core/model/int64x64-128.h',
       ROOT/'autonomous/native_env/build.json']
result={'scope':'Arithmetic only; no Simulator::Run and no RNG calls.',
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
(OUT/'arithmetic_provenance.json').write_text(json.dumps(result,indent=2)+'\n')
