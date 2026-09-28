#!/usr/bin/env python3
"""Seal already-executed arithmetic evidence; no simulation or mutation."""
import hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
CSR=ROOT/'autonomous/native_env/csr/model'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,data):(OUT/name).write_text(json.dumps(data,indent=2)+'\n')
spans=[
 ('Native acquisition relative schedule','csr-net-device.h',1198,1213),
 ('Native acquisition closes intervals before Track','csr-net-device.h',1741,1799),
 ('Native interval close bounds by physical end','csr-net-device.h',1284,1340),
 ('PHY component boundaries and truncation','csr-phy-model.h',699,769),
 ('Native duration and time conversion','csr-net-device.h',680,704),
 ('Native TX starts shared MAC completion owner','csr-net-device.h',750,755),
 ('Single native TX completion callback','csr-net-device.h',2634,2690),
 ('Native rejected-return nanosecond delay','csr-net-device.h',2101,2122),
 ('Shared TIC constant quantizes to28ns','csr-common.h',28,38),
]
save('source_path_proof.json',{'source_commit':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b',
 'spans':[{'purpose':purpose,'file':name,'first_line':first,'last_line':last,'file_sha256':sha(CSR/name),
 'source':'\n'.join((CSR/name).read_text().splitlines()[first-1:last])+'\n'}for purpose,name,first,last in spans]})
env=ROOT/'autonomous/native_env/build.json'
inputs=[ROOT/'autonomous/native_capture/run/observations.tsv',ROOT/'autonomous/native_capture/fixture/tx_signatures.csv',
 ROOT/'autonomous_eighth/data/J_discovery_identity/first_divergence.json',
 ROOT/'autonomous_eighth/data/J_discovery_identity/ordered_events.jsonl',env]
model=ROOT/'autonomous_seventh/kit/autocase/model'
mat_sources=[model/'+csr/+phy/SignalEngine.m',model/'+csr/+phy/Model.m',model/'+csr/+mac/Layer.m',model/'+csr/+sim/TransportTiming.m']
native_sources=[CSR/n for n in sorted({x[1]for x in spans})]+[ROOT/'autonomous/native_env/engine/src/core/model/nstime.h',ROOT/'autonomous/native_env/engine/src/core/model/int64x64-128.h']
libraries=ROOT/'autonomous/native_env/engine/build/lib'
save('evidence_receipt.json',{
 'schema':'csr-eighth-receiver-time-arithmetic-v1',
 'status':'native_arithmetic_probe_and_fixed_history_sweep_pass',
 'network_simulation_run':False,'matlab_executed_here':False,'production_fixture_or_guard_edited':False,
 'native_component_scope':'Pinned Time/GetSeconds/PHY rate and explicit-uniform binomial arithmetic only; no Simulator::Run and no RNG consumption.',
 'local_tested_bits':{'native':51,'floating':52},'same_uniform_errors':{'native':0,'floating':0},
 'full_capture_counts':{'observed_components':1542,'reconstructed_intervals':4070,'clock_ticks':10301,'acquisition_schedules':1352},
 'source_pins':json.loads(env.read_text())['sources'],'toolchain':json.loads(env.read_text())['toolchain'],
 'input_sha256':{str(p.relative_to(ROOT)):sha(p)for p in inputs},
 'source_sha256':{str(p.relative_to(ROOT)):sha(p)for p in native_sources+mat_sources},
 'runtime_library_sha256':{p.name:sha(p)for p in sorted(libraries.glob('libns3-dev-*-debug.so'))},
 'artifact_sha256':{p.name:sha(p)for p in sorted(OUT.iterdir())if p.is_file()and p.name not in ('evidence_receipt.json','arithmetic_probe')},
 'compile_argv':json.loads((OUT/'compile_command.json').read_text()),
 'run_argv':[[str(OUT/'arithmetic_probe')],[str(OUT/'arithmetic_probe'),'--clock']],
 'limits':['Local n51/n52 case has identical sampled error count and prior rejected signal; no delivery difference established.',
 'All-interval sweep holds native traffic/event history fixed and is not a K trajectory.',
 'ns/1e9 differs from native fixed-point GetSeconds at two audited ticks; no bit-count impact in this fixed history.',
 'Rejected-return28ns has source/component evidence only, no returned J execution.',
 'Native TX completion is one callback; MATLAB retains its existing two-callback decomposition and order.',
 'K owner execution and network parity remain unmeasured.']})
print('Native arithmetic receipt finalized.')
