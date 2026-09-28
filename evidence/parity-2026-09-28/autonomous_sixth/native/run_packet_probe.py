#!/usr/bin/env python3
"""Regenerate captured-frame inputs and execute only native packet sizing APIs."""
import csv
import json
import subprocess
from pathlib import Path
out=Path(__file__).resolve().parent; root=out.parents[1]
build=root/'autonomous/native_env/engine/build'
include=out/'include/ns3'
include.mkdir(parents=True,exist_ok=True)
# The restored build's CSR wrappers point at an absent contrib symlink.
# Supply equivalent local wrappers without editing the pinned checkout/build.
for name in ['csr-hop-security.h','csr-opnet-envelope.h','csr-phy-model.h']:
    source=root/'autonomous/native_env/csr/model'/name
    (include/name).write_text('#include "'+str(source)+'"\n')
fixture=root/'autonomous/native_capture/fixture/tx_signatures.csv'
rows=[r for r in csv.DictReader(fixture.open()) if r['tx_id']=='4294967314']
assert len(rows)==3
(out/'captured_frames.tsv').write_text(''.join(f"captured_child{r['child_index']}\t{r['wire_bytes']}\t{r['packet_hex']}\n" for r in rows))
cmd=['g++','-std=c++23','-O0','-g','-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE',
     '-I'+str(out/'include'),'-I'+str(build/'include'),str(out/'control_size_probe.cc'),'-L'+str(build/'lib'),'-Wl,-rpath,'+str(build/'lib'),
     '-lns3-dev-csr-debug','-lns3-dev-core-debug','-lns3-dev-network-debug','-lstdc++exp','-o',str(out/'control_size_probe')]
(out/'compile_command.json').write_text(json.dumps(cmd,indent=2)+'\n')
with (out/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
with (out/'control_size_probe.log').open('w') as f:
    subprocess.run([str(out/'control_size_probe'),str(out/'captured_frames.tsv')],stdout=f,stderr=subprocess.STDOUT,check=True)
print('Native packet sizing cases passed; no network simulation.')
