#!/usr/bin/env python3
"""Verify isolated G/H changes against untouched baseline and native contract."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
KIT=ROOT/'autonomous_fifth/kit/autocase'
PRIOR=ROOT/'autonomous_fourth/kit/autocase'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((KIT/'candidate_transform.json').read_text())
assert len(manifest['transforms'])==14
verified=[]
for item in manifest['transforms']:
    source,target=KIT/item['source'],KIT/item['target']
    assert sha(source)==item['source_sha256'],item['source']
    assert sha(target)==item['target_sha256'],item['target']
    generated=source.read_bytes()
    for edit in item['edits']:
        old,new=edit['old'].encode(),edit['new'].encode()
        assert generated.count(old)==1,(item['target'],'old uniqueness')
        generated=generated.replace(old,new,1)
    assert generated==target.read_bytes(),item['target']
    recovered=generated
    for edit in reversed(item['edits']):
        old,new=edit['old'].encode(),edit['new'].encode()
        assert recovered.count(new)==1,(item['target'],'new uniqueness')
        recovered=recovered.replace(new,old,1)
    assert recovered==source.read_bytes(),item['target']
    verified.append({'target':item['target'],'sha256':sha(target),'forward_and_reverse_exact':True})

routes=(KIT/'+ac/AdmissionRoutes.m').read_text()
start=routes.index('        function admitNeighbor(')
end=routes.index('        function setNeighbor(',start)
admit=routes[start:end]
assert 'obj.noteDestination(peer);' in admit
assert admit.index('obj.noteDestination(peer);')<admit.index('before = obj.best(peer);')<admit.index('entry.Active = true;')
assert 'route.DestinationId == peer && route.Valid && ...\n                        route.SelectionDeferred && obj.usable(route.NextHop)' in admit
candidate_assignments=[line.strip() for line in admit.splitlines() if 'obj.Candidates' in line and '=' in line and not line.strip().startswith('for ')]
assert candidate_assignments==['route = obj.Candidates(k);','obj.Candidates(k).SelectionDeferred = false;']
without=routes[:start]+routes[end:]
normalized=without.replace('classdef AdmissionRoutes < handle','classdef Routes < handle').replace(
    'function obj = AdmissionRoutes(', 'function obj = Routes(').replace('ac.AdmissionRoutes','csr.nwk.Routes')
assert normalized==(KIT/'model/+csr/+nwk/Routes.m').read_text()

neighbors=(KIT/'+ac/PopulationNeighbors.m').read_text()
observe=neighbors[neighbors.index('        function observe('):neighbors.index('        function receiveControl(')]
assert observe.count('PopulationObserved();')==2
assert observe.index('obj.Callbacks.PopulationObserved();')<observe.index('obj.changed(peer,true);')
assert 'obj.Peers(peer)=entry;\n            if isfield(obj.Callbacks,\'PopulationObserved\')' in observe
nwk=(KIT/'+ac/PopulationNwk.m').read_text()
prior_nwk=(KIT/'+ac/MessageFlagNwk.m').read_text()
for code in [nwk,(KIT/'+ac/AdmissionNwk.m').read_text()]:
    a=code.index('        function state = applicationState(');b=code.index('        function release(',a)
    pa=prior_nwk.index('        function state = applicationState(');pb=prior_nwk.index('        function release(',pa)
    assert code[a:b]==prior_nwk[pa:pb]
    assert 'state=obj.applicationState();\n                obj.Callbacks.PublishMacPopulation(state.ActiveNodeCount);' in code

for name in ['PopulationSimulation','AdmissionSimulation']:
    code=(KIT/f'+ac/{name}.m').read_text()
    assert 'obj.refreshHistoricalPopulation(' not in code
    assert "if ~strcmp(obj.Config.ApplicationGenerator,'historical-opnet-gated'), return; end" in code
    assert "'PublishMacPopulation',@(count)obj.publishMacPopulation(nodeId,count)" in code
    assert "obj.Macs{index}.setActiveNodes(count);" in code
    # A dead baseline helper is retained; all executable bridges use the new publisher.
    assert code.count('function refreshHistoricalPopulation(')==1

admission_nwk=(KIT/'+ac/AdmissionNwk.m').read_text()
assert admission_nwk.count('obj.Routes.admitNeighbor(')==1
assert 'if active\n                obj.Routes.admitNeighbor(peer,obj.peerCost(peer),obj.Scheduler.Now);' in admission_nwk
assert 'obj.Routes.setNeighbor(peer,obj.Neighbors.isActive(peer),obj.peerCost(peer),obj.Scheduler.Now);' in admission_nwk

model_files=[p for p in (KIT/'model').rglob('*') if p.is_file()]
for path in model_files:
    assert sha(path)==sha(PRIOR/path.relative_to(KIT)),path

runner=(KIT/'run_autonomous_tests.m').read_text()
gate=runner.index('if first.completed && first.natural_prefix_passed')
g=runner.index("second=runCase(root,out,config,'G_population','native');")
h=runner.index("third=runCase(root,out,config,'H_admission_route','native');")
assert gate<g<h
between='\n'.join(line for line in runner[g:h].splitlines() if not line.lstrip().startswith('%'))
assert 'if ' not in between
assert 'simulation=ac.PopulationSimulation(config,observer,timing,options)' in runner
assert 'simulation=ac.AdmissionSimulation(config,observer,timing,options)' in runner
assert 'simulation=csr.sim.NetworkSimulation(config,observer,timing,options)' in runner

receipt={'scope_review':'pass','matlab_executed':False,
 'candidate_manifest_sha256':sha(KIT/'candidate_transform.json'),'runner_sha256':sha(KIT/'run_autonomous_tests.m'),
 'verified_transforms':verified,'unchanged_baseline_model_files':len(model_files),
 'native_contract_checks':[
   'Observe commits qualifying peer state before publishing; publishes before admission callback side effects',
   'No executable generic MAC-enqueue or addressed-HOP-member population refresh',
   'Current application/routing population getter byte-preserved independently of MAC latch',
   'Admission retains logical destination insertion and compares selected state before/after activation',
   'Admission allocates no candidate, revalidates/reprices/retimestamps none; only valid deferred destination-peer candidates with usable next hop release',
   'All original route methods preserved exactly after class namespace normalization',
   'Actual observation path retains baseline setNeighbor; only neighborChanged active uses admitNeighbor',
   'Natural A gate required; independent H runs after diagnostic stop in G'],
 'limits':[
   'G/H runtime remains owner-side; no new full network simulation executed here',
   'Native ClearRoutes publisher has no portable local-API counterpart; none occurs in accepted capture',
   'Stale NeighborCheck success recovery and independent repricing precede native admission; component assertions concern fresh admission and do not establish full stale recovery parity',
   'Previously documented not-due retry rescheduling, inline KEY_REQUEST failed-admission fallback and control-header guard limitations remain']}
(OUT/'candidate_scope_review.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(f"G/H static scope passed: {len(verified)} exact transforms, {len(model_files)} unchanged baseline model files.")
