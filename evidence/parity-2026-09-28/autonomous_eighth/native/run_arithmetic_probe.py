#!/usr/bin/env python3
"""Compile and run only native time/bit arithmetic; no network execution."""
import csv,json,subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
BUILD=ROOT/'autonomous/native_env/engine/build'
include=OUT/'include/ns3';include.mkdir(parents=True,exist_ok=True)
(include/'csr-phy-model.h').write_text('#include "'+str(ROOT/'autonomous/native_env/csr/model/csr-phy-model.h')+'"\n')
cmd=['g++','-std=c++23','-O0','-g','-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE',
     '-I'+str(OUT/'include'),'-I'+str(BUILD/'include'),str(OUT/'arithmetic_probe.cc'),
     '-L'+str(BUILD/'lib'),'-Wl,-rpath,'+str(BUILD/'lib'),'-lns3-dev-csr-debug','-lns3-dev-core-debug','-lns3-dev-network-debug','-lstdc++exp','-o',str(OUT/'arithmetic_probe')]
(OUT/'compile_command.json').write_text(json.dumps(cmd,indent=2)+'\n')
with (OUT/'compile.log').open('w') as f: subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
with (OUT/'arithmetic_values.csv').open('w') as f: subprocess.run([str(OUT/'arithmetic_probe')],stdout=f,stderr=subprocess.STDOUT,check=True)
ticks=set()
for r in csv.DictReader((ROOT/'autonomous/native_capture/run/observations.tsv').open(),delimiter='\t'):
    ticks.add(int(r['time_ns']))
    d=json.loads(r['detail_json'])
    if 'deadline_ns' in d: ticks.add(int(d['deadline_ns']))
    for k in ('interval_start_ns','interval_end_ns'): 
        if k in d:ticks.add(int(d[k]))
(OUT/'clock_ticks.txt').write_text(''.join(str(n)+'\n'for n in sorted(ticks)))
with (OUT/'clock_ticks.txt').open() as src,(OUT/'clock_values.csv').open('w') as dest:
    subprocess.run([str(OUT/'arithmetic_probe'),'--clock'],stdin=src,stdout=dest,check=True)
print('Native time/arithmetic probe passed; no simulator run or RNG draw.')
