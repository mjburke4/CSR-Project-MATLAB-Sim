#!/usr/bin/env python3
"""Bounded M source review. No native/MATLAB execution."""
import hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
KIT=ROOT/'autonomous_tenth/kit/autocase';PRIOR=ROOT/'autonomous_ninth/kit/autocase'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest_path=KIT/'candidate_transform.json';manifest=json.loads(manifest_path.read_text());verified=[]
for tr in manifest['transforms']:
    source=KIT/tr['source'];target=KIT/tr['target']
    assert sha(source)==tr['source_sha256'] and sha(target)==tr['target_sha256']
    text=source.read_text()
    for e in tr['edits']:
        assert e['old'] in text
        text=text.replace(e['old'],e['new'])
    assert text==target.read_text(),tr['target']
    for e in reversed(tr['edits']):
        assert e['new'] in text
        text=text.replace(e['new'],e['old'])
    assert text==source.read_text(),tr['target']
    verified.append({'target':tr['target'],'sha256':sha(target),'forward_and_reverse_exact':True})
assert len(verified)==26
files=sorted(p for p in(PRIOR/'model').rglob('*')if p.is_file());assert len(files)==99
assert all(sha(p)==sha(KIT/'model'/p.relative_to(PRIOR/'model'))for p in files)
preserved=['DiscoveryLifecycleNwk.m','DiscoveryLifecycleSimulation.m','DiscoveryTxSignature.m','DiscoveryStreams.m',
 'ReceiverTimerSimulation.m','ReceiverTimerSignalEngine.m','ReceiverTimerMac.m','ReceiverTimer.m',
 'ControlWireNwk.m','controlWireBytes.m','AdmissionRoutes.m','PopulationNeighbors.m','Scheduler.m']
# Scheduler is in model, not the isolated namespace; model already checked above.
preserved.remove('Scheduler.m')
assert all(sha(KIT/'+ac'/n)==sha(PRIOR/'+ac'/n)for n in preserved)
assert all(sha(KIT/'ref/native'/n)==sha(PRIOR/'ref/native'/n)for n in ('random_draws.csv','tx_signatures.csv'))
nwk=(KIT/'+ac/DiscoveryMembershipNwk.m').read_text();sim=(KIT/'+ac/DiscoveryMembershipSimulation.m').read_text()
old=(KIT/'+ac/DiscoveryLifecycleNwk.m').read_text()
renamed=nwk.replace('classdef DiscoveryMembershipNwk < handle','classdef DiscoveryLifecycleNwk < handle').replace(
 'function obj = DiscoveryMembershipNwk(','function obj = DiscoveryLifecycleNwk(')
new='            % Native advances existing discovery entries. New routing knowledge\n            % enters this table only at discovery completion or received DONE.\n'
assert renamed.replace(new,'            obj.mergeScanKnown(obj.Routes.reachableDestinations());\n')==old
restored=sim.replace('classdef DiscoveryMembershipSimulation < handle','classdef DiscoveryLifecycleSimulation < handle').replace(
 'function obj = DiscoveryMembershipSimulation(','function obj = DiscoveryLifecycleSimulation(').replace(
 'obj.Networks{k} = ac.DiscoveryMembershipNwk(','obj.Networks{k} = ac.DiscoveryLifecycleNwk(')
assert restored==(KIT/'+ac/DiscoveryLifecycleSimulation.m').read_text()
advance=nwk[nwk.index('        function advanceScan('):nwk.index('        function scanWatchdog(')]
assert 'Routes.reachableDestinations' not in advance and 'mergeScanKnown' not in advance
assert advance.index('obj.ScanRequested(end+1)=target;')<advance.index("obj.sendSnmp('SNMP_START'")
assert nwk.count('obj.mergeScanKnown(')==2
assert 'known=known(1:min(10,numel(known))); obj.mergeScanKnown(known);' in nwk
assert 'obj.mergeScanKnown(double(reshape(nodes,1,[])));' in nwk
for method,next_method in [('scanWatchdog','sendSnmp'),('sendSnmp','mergeScanKnown'),('discoveryFinished','sendScanDone'),('queueControl','pumpControls')]:
    assert nwk[nwk.index('        function '+('accepted = 'if method in ('sendSnmp','queueControl')else'')+method+'('):nwk.index('        function '+('accepted = 'if next_method=='sendSnmp'else'')+next_method+'(')]==old[old.index('        function '+('accepted = 'if method in ('sendSnmp','queueControl')else'')+method+'('):old.index('        function '+('accepted = 'if next_method=='sendSnmp'else'')+next_method+'(')]
runner_path=KIT/'run_autonomous_tests.m';runner=runner_path.read_text()
assert runner.index('if first.completed && first.natural_prefix_passed')<runner.index('ac.discoveryMembershipPreflight')<runner.index("runCase(root,out,config,'M_discovery_membership','native')")
assert runner.index('ac.discoveryLifecyclePreflight')<runner.index('ac.discoveryMembershipPreflight')
result={'scope_review':'pass','matlab_executed':False,'native_network_or_component_run':False,
 'candidate_manifest_sha256':sha(manifest_path),'runner_sha256':sha(runner_path),'verified_transforms':verified,
 'unchanged_baseline_model_files':99,'prior_protocol_provider_comparator_files_unchanged':preserved,
 'native_fixtures_unchanged':['random_draws.csv','tx_signatures.csv'],
 'native_contract_checks':[
  'Only executable NWK edit removes current-route merge from advanceScan; class identities are isolated.',
  'Local discovery completion still registers its bounded known-node snapshot; received DONE still registers advertised nodes.',
  'Idle START requester marking and active START completion requester retention remain unchanged from L.',
  'Table insertion order and no-rearm behavior are preserved through existing ScanKnown/ScanRequested.',
  'Advance still marks target requested before SendSnmp, including missing-route failure; watchdog generation and schedule unchanged.',
  'Reliable KEY_UPDATE owned inline submission, control admission/radio/ACK behavior and fallback are byte-identical to L.',
  'Simulation changes only class identity and NWK binding; provider, comparator, timer, route and neighbor classes unchanged.',
  'Natural gate and inherited preflights precede new membership preflight and one M continuation.'],
 'limits':[
  'MATLAB component tests and M trajectory remain owner-side; this is static/source review.',
  'Known-node snapshot truncation is source-aligned; current native capture has at most6 nodes per snapshot and does not reach cap10.',
  'Broader DONE interruption policy and requester cap10 remain unexercised differences outside M.',
  'No watchdog arithmetic or ownership change; canceled-versus-generation-no-op representation remains inherited.',
  'No global callback-order, corrected M trajectory, or15-percent performance claim.']}
(OUT/'candidate_scope_review.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS:26 exact transforms,99 model files unchanged; one executable scan-membership edit; L lifecycle and all providers/guards/timers preserved.')
