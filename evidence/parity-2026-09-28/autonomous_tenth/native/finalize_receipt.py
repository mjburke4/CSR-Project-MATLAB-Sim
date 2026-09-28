#!/usr/bin/env python3
"""Bind accepted capture, owner L return, source evidence and final M review."""
import hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inputs=[ROOT/'autonomous/native_capture/fixture/tx_signatures.csv',ROOT/'autonomous/native_capture/run/run.log',
 ROOT/'autonomous_tenth/data/L_discovery_lifecycle/first_divergence.json',
 ROOT/'autonomous_tenth/data/L_discovery_lifecycle/random_summary.json',
 ROOT/'autonomous_tenth/data/L_discovery_lifecycle/ordered_events.jsonl']
sources=[ROOT/'autonomous/native_env/csr/model/csr-nwk-layer.h',ROOT/'autonomous/native_env/csr/model/csr-common.h',
 ROOT/'autonomous_ninth/kit/autocase/+ac/DiscoveryLifecycleNwk.m',
 ROOT/'autonomous_tenth/kit/autocase/+ac/DiscoveryMembershipNwk.m',
 ROOT/'autonomous_tenth/kit/autocase/+ac/DiscoveryMembershipSimulation.m']
audit=json.loads((OUT/'membership_audit.json').read_text())
data={'schema':'csr-tenth-discovery-membership-native-evidence-v1','status':'actual_capture_and_source_audit_pass',
 'new_native_network_or_component_run':False,'matlab_executed_here':False,'production_fixture_or_guard_edited':False,
 'full_capture_counts':audit['native_inventory'],
 'input_sha256':{str(p.relative_to(ROOT)):sha(p)for p in inputs},
 'source_sha256':{str(p.relative_to(ROOT)):sha(p)for p in sources},
 'artifact_sha256':{p.name:sha(p)for p in sorted(OUT.iterdir())if p.is_file()and p.name!='evidence_receipt.json'},
 'limits':audit['limits']}
(OUT/'evidence_receipt.json').write_text(json.dumps(data,indent=2)+'\n')
print('Native discovery-membership evidence receipt finalized.')
