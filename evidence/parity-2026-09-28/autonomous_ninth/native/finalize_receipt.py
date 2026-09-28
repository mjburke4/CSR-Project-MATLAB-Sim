#!/usr/bin/env python3
"""Bind read-only lifecycle evidence and final candidate review artifacts."""
import hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inputs=[ROOT/'autonomous/native_capture/fixture/tx_signatures.csv',
 ROOT/'autonomous/native_capture/run/observations.tsv',ROOT/'autonomous/native_capture/run/run.log',
 ROOT/'autonomous_ninth/data/K_receiver_timers/first_divergence.json',
 ROOT/'autonomous_ninth/data/K_receiver_timers/ordered_events.jsonl']
sources=[ROOT/'autonomous/native_env/csr/model/csr-nwk-layer.h',
 ROOT/'autonomous/native_env/csr/model/csr-hop-layer.h',ROOT/'autonomous/native_env/csr/model/csr-net-device.h',
 ROOT/'autonomous_eighth/kit/autocase/+ac/ControlWireNwk.m',
 ROOT/'autonomous_eighth/kit/autocase/+ac/PopulationNeighbors.m',
 ROOT/'autonomous_eighth/kit/autocase/model/+csr/+hop/Layer.m']
data={'schema':'csr-ninth-discovery-lifecycle-native-evidence-v1',
 'status':'actual_capture_and_source_audit_pass',
 'new_native_network_or_component_run':False,'matlab_executed_here':False,
 'production_fixture_or_guard_edited':False,
 'full_capture_counts':{'snmp_tx':36,'snmp_start_tx':28,'snmp_done_tx':8,
     'snmp_start_nwk_receive':8,'active_duplicate_start':1,'snmp_done_nwk_receive':7,
     'key_update_generated':14,'key_update_transmitted':14,'key_update_acknowledged':14},
 'input_sha256':{str(p.relative_to(ROOT)):sha(p)for p in inputs},
 'source_sha256':{str(p.relative_to(ROOT)):sha(p)for p in sources},
 'artifact_sha256':{p.name:sha(p)for p in sorted(OUT.iterdir())if p.is_file()and p.name!='evidence_receipt.json'},
 'limits':['Wrong active-requester marking is observed before the separate key-response callback drift.',
 'Native table order is logged; MATLAB pending list is reconstructed from source and received messages, not privately sampled.',
 'Delivered DONEs all match pending targets; broader DONE interruption/capacity differences remain outside this fix.',
 'Native resend-overflow forwarding differs from retained MATLAB admission gating; saturation parity is not claimed.',
 'No full callback-time prefix equality, corrected L trajectory or15percent-performance claim.']}
(OUT/'evidence_receipt.json').write_text(json.dumps(data,indent=2)+'\n')
print('Native lifecycle evidence receipt finalized.')
