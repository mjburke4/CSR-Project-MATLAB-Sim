"""Generate source-bound neighbor eligibility experiment; model stays untouched."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]/'kit'/'autocase'
def sha(b):return hashlib.sha256(b).hexdigest()
proof=json.loads((root/'candidate_transform.json').read_text())
# Preserve the accepted D candidate's two original transforms.
proof['transforms']=proof['transforms'][:2]
def gen(source,target,edits):
 raw=(root/source).read_bytes();text=raw.decode()
 for old,new in edits:
  assert text.count(old)==1,(source,old[:80],text.count(old))
  text=text.replace(old,new)
 targetraw=text.encode();(root/target).write_bytes(targetraw)
 reverse=text
 for old,new in reversed(edits):
  assert reverse.count(new)==1
  reverse=reverse.replace(new,old)
 assert reverse.encode()==raw
 proof['transforms'].append(dict(source=source,source_sha256=sha(raw),target=target,target_sha256=sha(targetraw),
  reverse_recovers_source=True,edits=[dict(old=a,new=b) for a,b in edits]))
gen('model/+csr/+nwk/Neighbors.m','+ac/CheckGateNeighbors.m',[
 ('classdef Neighbors < handle','classdef CheckGateNeighbors < handle'),
 ('function obj = Neighbors(nodeId,scheduler,options,callbacks)','function obj = CheckGateNeighbors(nodeId,scheduler,options,callbacks)'),
 ('if ~entry.CheckActive && (~entry.OverheardValid || now>=deadline)','if ~entry.OverheardValid || now>=deadline')])
gen('+ac/InlineKeyNwk.m','+ac/CheckGateNwk.m',[
 ('classdef InlineKeyNwk < handle','classdef CheckGateNwk < handle'),
 ('function obj = InlineKeyNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)',
  'function obj = CheckGateNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)'),
 ('obj.Neighbors=csr.nwk.Neighbors(obj.NodeId,scheduler,obj.Config.Neighbor,neighborCallbacks);',
  'obj.Neighbors=ac.CheckGateNeighbors(obj.NodeId,scheduler,obj.Config.Neighbor,neighborCallbacks);')])
gen('+ac/InlineKeySimulation.m','+ac/CheckGateSimulation.m',[
 ('classdef InlineKeySimulation < handle','classdef CheckGateSimulation < handle'),
 ('function obj = InlineKeySimulation(config,linkObserver,transportTiming,autonomousOptions)',
  'function obj = CheckGateSimulation(config,linkObserver,transportTiming,autonomousOptions)'),
 ('obj.Networks{k} = ac.InlineKeyNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);',
  'obj.Networks{k} = ac.CheckGateNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);')])
gen('+ac/CheckGateNeighbors.m','+ac/MessageFlagNeighbors.m',[
 ('classdef CheckGateNeighbors < handle','classdef MessageFlagNeighbors < handle'),
 ('function obj = CheckGateNeighbors(nodeId,scheduler,options,callbacks)',
  'function obj = MessageFlagNeighbors(nodeId,scheduler,options,callbacks)'),
 ("entry=obj.Peers(peer); entry.CheckActive=true; obj.Peers(peer)=entry;",
  "entry=obj.Peers(peer);\n            if strcmp(subtype,'message')\n                entry.CheckActive=true; obj.Peers(peer)=entry;\n            end")])
gen('+ac/CheckGateNwk.m','+ac/MessageFlagNwk.m',[
 ('classdef CheckGateNwk < handle','classdef MessageFlagNwk < handle'),
 ('function obj = CheckGateNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)',
  'function obj = MessageFlagNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)'),
 ('obj.Neighbors=ac.CheckGateNeighbors(obj.NodeId,scheduler,obj.Config.Neighbor,neighborCallbacks);',
  'obj.Neighbors=ac.MessageFlagNeighbors(obj.NodeId,scheduler,obj.Config.Neighbor,neighborCallbacks);')])
gen('+ac/CheckGateSimulation.m','+ac/MessageFlagSimulation.m',[
 ('classdef CheckGateSimulation < handle','classdef MessageFlagSimulation < handle'),
 ('function obj = CheckGateSimulation(config,linkObserver,transportTiming,autonomousOptions)',
  'function obj = MessageFlagSimulation(config,linkObserver,transportTiming,autonomousOptions)'),
 ('obj.Networks{k} = ac.CheckGateNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);',
  'obj.Networks{k} = ac.MessageFlagNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);')])
proof.update(schema='csr-isolated-neighbor-candidate-v1',matlab_executed=False,prior_D_owner_executed=True,new_E_F_matlab_executed=False,production_model_changed=False,
 natural_path_changed=False,scope='E retains D and removes only the CheckActive exclusion from Overheard send eligibility; the original not-yet-due rescheduling branch remains unchanged. F retains E and sets CheckActive only for Message subtype.',
 current_limitation='E retains generic CheckActive ownership; F narrows setting it to Message. Existing completion/reset paths remain unchanged; this is not full neighbor lifecycle equivalence.')
(root/'candidate_transform.json').write_text(json.dumps(proof,indent=2)+'\n')
print('Built E/F source-bound classes; all inverse edits recover exact source bytes.')
