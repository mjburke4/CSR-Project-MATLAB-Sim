#!/usr/bin/env python3
"""Static bounded K scope/hash review. Does not execute MATLAB or a network."""
import hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
KIT=ROOT/'autonomous_eighth/kit/autocase';PRIOR=ROOT/'autonomous_seventh/kit/autocase'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest_path=KIT/'candidate_transform.json';manifest=json.loads(manifest_path.read_text())
verified=[]
for tr in manifest['transforms']:
    source=KIT/tr['source'];target=KIT/tr['target']
    assert sha(source)==tr['source_sha256'] and sha(target)==tr['target_sha256']
    text=source.read_text()
    for edit in tr['edits']:
        assert edit['old'] in text
        text=text.replace(edit['old'],edit['new'])
    assert text==target.read_text(),tr['target']
    for edit in reversed(tr['edits']):
        assert edit['new'] in text
        text=text.replace(edit['new'],edit['old'])
    assert text==source.read_text(),tr['target']
    verified.append({'target':tr['target'],'sha256':sha(target),'forward_and_reverse_exact':True})
assert len(verified)==22
files=sorted(p for p in(PRIOR/'model').rglob('*')if p.is_file());assert len(files)==99
assert all(sha(p)==sha(KIT/'model'/p.relative_to(PRIOR/'model'))for p in files)
preserved=['DiscoveryTxSignature.m','DiscoveryStreams.m','DiscoveryIdentitySimulation.m',
           'ControlWireNwk.m','controlWireBytes.m']
assert all(sha(KIT/'+ac'/n)==sha(PRIOR/'+ac'/n)for n in preserved)
assert all(sha(KIT/'ref/native'/n)==sha(PRIOR/'ref/native'/n)for n in ('random_draws.csv','tx_signatures.csv'))
phy=(KIT/'+ac/ReceiverTimerSignalEngine.m').read_text();mac=(KIT/'+ac/ReceiverTimerMac.m').read_text()
helper=(KIT/'+ac/ReceiverTimer.m').read_text();sim=(KIT/'+ac/ReceiverTimerSimulation.m').read_text()
assert "txDeadline=obj.relativeDeadline(txIndex,duration,'phy_tx_finish');" in phy
assert 'obj.Receivers(txIndex).TxUntil=txDeadline;' in phy
assert 'obj.Scheduler.scheduleAt(txDeadline,@()obj.finishTx(txIndex))' in phy
assert "obj.relativeDeadline(index,obj.SyncToTrackSeconds,'acquisition')" in phy
assert "obj.relativeDeadline(index,28e-9,'rejected_return')" in phy
assert phy.count('obj.relativeDeadline(')==3
assert 'nowNs=round(now*1e9); delayNs=round(delay*1e9);' in helper
assert 'targetNs=nowNs+delayNs; deadline=targetNs/1e9;' in helper
assert 'scheduleAt' not in helper and '.get(' not in helper
assert "obj.NodeId,'mac_tx_finish');" in mac
assert 'obj.FinishEvent=obj.Scheduler.scheduleAt(deadline,@()obj.finishTx());' in mac
assert mac.index('obj.Callbacks.Transmit(envelope, duration);')<mac.index("obj.NodeId,'mac_tx_finish');")
# Generic MAC delay scheduling remains byte-identical.
old_mac=(KIT/'model/+csr/+mac/Layer.m').read_text()
segment=lambda s:s[s.index('        function id = after('):s.index('        function cancelTimer(')]
assert segment(mac)==segment(old_mac)
assert 'macRelativeTimer=obj.RelativeTimer;' in sim
assert 'obj.TransportTiming,obj.RelativeTimer);' in sim
assert 'config,macCallbacks,macRelativeTimer);' in sim
runner_path=KIT/'run_autonomous_tests.m';runner=runner_path.read_text()
assert runner.index('if first.completed && first.natural_prefix_passed')<runner.index('ac.receiverTimerPreflight')<runner.index("runCase(root,out,config,'K_receiver_timers','native')")
result={'scope_review':'pass','matlab_executed':False,'native_network_run':False,
 'candidate_manifest_sha256':sha(manifest_path),'runner_sha256':sha(runner_path),
 'helper_sha256':sha(KIT/'+ac/ReceiverTimer.m'),
 'verified_transforms':verified,'unchanged_baseline_model_files':99,
 'prior_protocol_provider_comparator_files_unchanged':preserved,
 'native_fixtures_unchanged':['random_draws.csv','tx_signatures.csv'],
 'native_contract_checks':[
  'Only acquisition, explicit28ns rejected return, and PHY/MAC TX-completion targets change.',
  'Continuous physical start/end/preamble geometry and Model allocation remain source-identical.',
  'Both TX callbacks and TxUntil use one integer-nanosecond relative-target formula.',
  'PHY schedules first inside Transmit callback; MAC completion schedules afterward, preserving existing MATLAB decomposition order.',
  'Native has one MAC FinishTx callback; this review does not assert a native two-event order.',
  'Generic MAC after helper and global EventScheduler unchanged.',
  'Shared recorder does not schedule events or consume randomness; overflow is observational and retained in summary.',
  'Original strict J comparators/providers and raw native random/semantic fixtures unchanged.',
  'Natural gate, inherited regressions and new public timer preflight precede one K continuation.'],
 'limits':[
  'MATLAB preflight and K runtime remain owner-side; static source review only.',
  'ns/1e9 is not universally bitwise equal to native fixed-point GetSeconds; full current fixture count coverage is recorded separately.',
  'Rejected-return28ns has no actual J execution; direct component test does not establish network coverage.',
  'Sibling MAC/NWK/HOP timer quantization outside these explicit boundaries remains unchanged.',
  'All inherited J protocol/security/model limitations remain; no15percent-parity claim.']}
(OUT/'candidate_scope_review.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS:22 exact transforms;99 baseline files unchanged; strict fixtures/comparators unchanged; bounded coherent K relative timer scope.')
