#!/usr/bin/env python3
"""Bounded L source review. No native/MATLAB execution."""
import hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
KIT=ROOT/'autonomous_ninth/kit/autocase';PRIOR=ROOT/'autonomous_eighth/kit/autocase'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest_path=KIT/'candidate_transform.json';manifest=json.loads(manifest_path.read_text())
verified=[]
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
assert len(verified)==24
files=sorted(p for p in(PRIOR/'model').rglob('*')if p.is_file());assert len(files)==99
assert all(sha(p)==sha(KIT/'model'/p.relative_to(PRIOR/'model'))for p in files)
preserved=['DiscoveryTxSignature.m','DiscoveryStreams.m','ReceiverTimerSimulation.m','ReceiverTimerSignalEngine.m',
 'ReceiverTimerMac.m','ReceiverTimer.m','ControlWireNwk.m','controlWireBytes.m']
assert all(sha(KIT/'+ac'/n)==sha(PRIOR/'+ac'/n)for n in preserved)
assert all(sha(KIT/'ref/native'/n)==sha(PRIOR/'ref/native'/n)for n in ('random_draws.csv','tx_signatures.csv'))
nwk=(KIT/'+ac/DiscoveryLifecycleNwk.m').read_text();sim=(KIT/'+ac/DiscoveryLifecycleSimulation.m').read_text()
restored_sim=sim.replace('classdef DiscoveryLifecycleSimulation < handle','classdef ReceiverTimerSimulation < handle').replace(
 'function obj = DiscoveryLifecycleSimulation(','function obj = ReceiverTimerSimulation(').replace(
 'obj.Networks{k} = ac.DiscoveryLifecycleNwk(','obj.Networks{k} = ac.ControlWireNwk(')
assert restored_sim==(KIT/'+ac/ReceiverTimerSimulation.m').read_text()
start=nwk[nwk.index("                case 'SNMP_START'"):nwk.index("                case 'SNMP_DONE'")]
assert start.index('obj.ScanRequesters(end+1)=source;')<start.index('if ~obj.ScanStarted || obj.ScanComplete')
assert start.index('if ~obj.ScanStarted || obj.ScanComplete')<start.index('obj.ScanRequested(end+1)=source;')<start.index('obj.startDiscovery(')
assert start.count('obj.ScanRequested(end+1)=source;')==1
control=nwk[nwk.index('        function accepted = queueControl('):nwk.index('        function pumpControls(')]
assert "if scheduleWake && ((strcmp(kind,'KEY_REQUEST') && ~reliable) || ..." in control
assert "(strcmp(kind,'KEY_UPDATE') && reliable))" in control
assert 'canSubmit=~reliable || ~isfield(obj.Callbacks,\'CanSendControl\') || ...' in control
assert 'obj.Callbacks.CanSendControl(peers);' in control
assert control.index('obj.Controls{end+1}=owner;')<control.index('canSubmit=')<control.index('submitted=obj.Callbacks.SendControl')
assert 'options=obj.radioOptions(peers,struct()); options.AckRequired=logical(reliable);' in control
assert 'if ~submitted && position>0, obj.Controls{position}.Submitted=false; end' in control
assert control.index('position=obj.controlPosition(controlId);',control.index('submitted=obj.Callbacks.SendControl'))>0
assert 'if scheduleWake, obj.wake(); end' in control
old=(KIT/'+ac/ControlWireNwk.m').read_text()
# No generic pump, route/scan selection, sendSnmp or DONE policy edits.
assert nwk[nwk.index('        function pumpControls('):]==old[old.index('        function pumpControls('):]
runner_path=KIT/'run_autonomous_tests.m';runner=runner_path.read_text()
assert runner.index('if first.completed && first.natural_prefix_passed')<runner.index('ac.discoveryLifecyclePreflight')<runner.index("runCase(root,out,config,'L_discovery_lifecycle','native')")
result={'scope_review':'pass','matlab_executed':False,'native_network_or_component_run':False,
 'candidate_manifest_sha256':sha(manifest_path),'runner_sha256':sha(runner_path),
 'verified_transforms':verified,'unchanged_baseline_model_files':99,
 'prior_protocol_provider_comparator_files_unchanged':preserved,
 'native_fixtures_unchanged':['random_draws.csv','tx_signatures.csv'],
 'native_contract_checks':[
  'SNMP requester retention remains before state branch; requested marking only inside idle/new-session branch and before startDiscovery.',
  'Active duplicate requester retains DONE report and later outbound scan eligibility.',
  'New reliable KEY_UPDATE inline submission extends existing fresh KEY_REQUEST owner boundary only.',
  'Owner registration precedes reliable admission gate and sending callback; after callback owner is re-found by ID.',
  'Reliable ACK option and ordinary radioOptions are retained; no SNMP radio override introduced.',
  'Blocked/failed admission retains owner reset and ordinary wake fallback; KEY_REQUEST short-circuits reliable gate.',
  'Generic pump, scan selection, sendSnmp, DONE handling and all later NWK methods remain byte-identical.',
  'Simulation changes only class identity and NWK binding; inherited K timer classes/provider/guards unchanged.',
  'Natural gate, inherited preflights and lifecycle preflight precede one L continuation.'],
 'limits':[
  'MATLAB component tests and L trajectory remain owner-side; this is static/source review.',
  'Native full resend queue may forward untracked control, unlike preserved MATLAB reliable gate; saturation parity not claimed.',
  'Native requester cap10 and broader DONE interruption rules remain unexercised differences outside L.',
  'No global timing-prefix or performance-parity claim; the actual K timing drift precedes its strict SNMP stop.']}
(OUT/'candidate_scope_review.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS:24 exact transforms,99 model files unchanged; idle-only SNMP mark and owned reliable KEY_UPDATE admission; K guards/timers/fixtures preserved.')
