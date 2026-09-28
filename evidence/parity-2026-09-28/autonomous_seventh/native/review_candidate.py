#!/usr/bin/env python3
"""Static scope review of J. No MATLAB or native network execution."""
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
KIT=ROOT/'autonomous_seventh/kit/autocase'
PRIOR=ROOT/'autonomous_sixth/kit/autocase'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
manifest_path=KIT/'candidate_transform.json'
manifest=json.loads(manifest_path.read_text())
verified=[]
for tr in manifest['transforms']:
    source=KIT/tr['source']; target=KIT/tr['target']
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
assert len(verified)==19
files=sorted(p for p in (PRIOR/'model').rglob('*') if p.is_file())
assert len(files)==99
assert all(sha(p)==sha(KIT/'model'/p.relative_to(PRIOR/'model'))for p in files)
preserved=['TxSignature.m','Streams.m','ControlWireSimulation.m','ControlWireNwk.m','controlWireBytes.m']
for name in preserved:
    assert sha(KIT/'+ac'/name)==sha(PRIOR/'+ac'/name),name
for name in ('random_draws.csv','tx_signatures.csv'):
    assert sha(KIT/'ref/native'/name)==sha(PRIOR/'ref/native'/name),name
stream=(KIT/'+ac/DiscoveryStreams.m').read_text()
restored_stream=stream.replace('classdef DiscoveryStreams < handle','classdef Streams < handle').replace(
    'function obj=DiscoveryStreams(', 'function obj=Streams(').replace(
    'ac.DiscoveryTxSignature.compare(frame,rows)','ac.TxSignature.compare(frame,rows)')
assert restored_stream==(KIT/'+ac/Streams.m').read_text()
simulation=(KIT/'+ac/DiscoveryIdentitySimulation.m').read_text()
restored_sim=simulation.replace('classdef DiscoveryIdentitySimulation < handle','classdef ControlWireSimulation < handle').replace(
    'function obj = DiscoveryIdentitySimulation(', 'function obj = ControlWireSimulation(').replace(
    'obj.Streams = ac.DiscoveryStreams(', 'obj.Streams = ac.Streams(')
assert restored_sim==(KIT/'+ac/ControlWireSimulation.m').read_text()
comparator=(KIT/'+ac/DiscoveryTxSignature.m').read_text()
assert comparator.count("if discoveryTraceIdentity && strcmp(name,'hop_sequence'), continue; end")==1
assert "'actual',item.hop_sequence,'native',double(wanted.hop_sequence)" in comparator
assert "strcmp(char(child.Control.Payload.Subtype),'broadcast')" in comparator
assert "strcmp(char(wanted.discover_subtype),'broadcast')" in comparator
assert 'double(wanted.kind)==4' in comparator
assert 'double(wanted.hop_destination)==16777215' in comparator
assert 'double(child.DestinationId)==16777215' in comparator
assert 'numel(child.DestinationIds)==1' in comparator
assert '~child.AckRequired && ~child.HasAckWindow' in comparator
assert 'double(wanted.ackable)==0 && double(wanted.has_ack_window)==0' in comparator
assert 'bitand(' in comparator and '128' in comparator and 'security_count' in comparator
runner_path=KIT/'run_autonomous_tests.m'; runner=runner_path.read_text()
assert runner.index('if first.completed && first.natural_prefix_passed') < runner.index('ac.discoveryIdentityPreflight') < runner.index("runCase(root,out,config,'J_discovery_identity','native')")
out={
    'scope_review':'pass','matlab_executed':False,'native_run':False,
    'candidate_manifest_sha256':sha(manifest_path),'runner_sha256':sha(runner_path),
    'verified_transforms':verified,'unchanged_baseline_model_files':99,
    'prior_protocol_provider_comparator_files_unchanged':preserved,
    'native_fixtures_unchanged':['random_draws.csv','tx_signatures.csv'],
    'native_contract_checks':[
        'Only eligible broadcast-subtype DISCOVER outer hop_sequence comparison is skipped.',
        'Both sides require DISCOVER kind, broadcast destination, no ACK and no ACK window; actual has one broadcast target.',
        'Expected native frame must retain group-protection flag and valid security-count metadata.',
        'Both raw outer sequence values, policy and reason remain in actual diagnostic context.',
        'Payload discovery-session sequence, active-peer membership and all other ordinary item comparisons remain strict.',
        'No chirp exception, no general nonACK/reliable/control sequence exception.',
        'New provider differs only in class/constructor identity and comparator call.',
        'New simulation differs only in class/constructor identity and provider binding; I NWK/protocol unchanged.',
        'Natural gate and inherited/public comparator preflights precede J continuation.'
    ],
    'limits':[
        'MATLAB public positive/negative comparator preflight execution remains owner-side.',
        'No continuation or behavioral performance improvement measured here.',
        'Actual model has behavioral security rather than a native cryptographic outer header; unchanged CONTROL.DISCOVER is its GroupEstablish counterpart.',
        'Previously documented I model and receive-security limits remain.'
    ]}
(OUT/'candidate_scope_review.json').write_text(json.dumps(out,indent=2)+'\n')
print('PASS: 19 exact transforms, 99 baseline model files unchanged, native fixtures unchanged, DISCOVER-only comparator/wiring scope.')
