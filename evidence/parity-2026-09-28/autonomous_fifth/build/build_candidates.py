"""Isolated MAC population publisher candidate; no model file is edited."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]/'kit'/'autocase'
def sha(b):return hashlib.sha256(b).hexdigest()
proof=json.loads((root/'candidate_transform.json').read_text());proof['transforms']=proof['transforms'][:8]
def gen(source,target,edits):
 raw=(root/source).read_bytes();text=raw.decode()
 for old,new in edits:
  assert text.count(old)==1,(source,old[:100],text.count(old));text=text.replace(old,new)
 result=text.encode();(root/target).write_bytes(result)
 reverse=text
 for old,new in reversed(edits):
  assert reverse.count(new)==1,(source,new[:120],reverse.count(new));reverse=reverse.replace(new,old)
 assert reverse.encode()==raw
 proof['transforms'].append(dict(source=source,source_sha256=sha(raw),target=target,target_sha256=sha(result),reverse_recovers_source=True,edits=[dict(old=a,new=b) for a,b in edits]))
old="""            if ~obj.Config.AdmissionEnabled && ~entry.Active
                entry.Active=true; obj.Peers(peer)=entry;
                obj.changed(peer,true); return
            end
            obj.Peers(peer)=entry;
        end
        function receiveControl"""
new="""            if ~obj.Config.AdmissionEnabled && ~entry.Active
                entry.Active=true; obj.Peers(peer)=entry;
                if isfield(obj.Callbacks,'PopulationObserved'), obj.Callbacks.PopulationObserved(); end
                obj.changed(peer,true); return
            end
            obj.Peers(peer)=entry;
            if isfield(obj.Callbacks,'PopulationObserved'), obj.Callbacks.PopulationObserved(); end
        end
        function receiveControl"""
gen('+ac/MessageFlagNeighbors.m','+ac/PopulationNeighbors.m',[
 ('classdef MessageFlagNeighbors < handle','classdef PopulationNeighbors < handle'),
 ('function obj = MessageFlagNeighbors(nodeId,scheduler,options,callbacks)','function obj = PopulationNeighbors(nodeId,scheduler,options,callbacks)'),(old,new)])
helper="""        function publishMacPopulation(obj)
            % Native publishes from qualifying NWK observation boundaries;
            % ACK completion can change this count without publishing it.
            if isfield(obj.Callbacks,'PublishMacPopulation')
                state=obj.applicationState();
                obj.Callbacks.PublishMacPopulation(state.ActiveNodeCount);
            end
        end

"""
gen('+ac/MessageFlagNwk.m','+ac/PopulationNwk.m',[
 ('classdef MessageFlagNwk < handle','classdef PopulationNwk < handle'),
 ('function obj = MessageFlagNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)','function obj = PopulationNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)'),
 ("                'NeighborChanged',@(peer,active)obj.neighborChanged(peer,active),", "                'PopulationObserved',@()obj.publishMacPopulation(), ...\n                'NeighborChanged',@(peer,active)obj.neighborChanged(peer,active),"),
 ('obj.Neighbors=ac.MessageFlagNeighbors(obj.NodeId,scheduler,obj.Config.Neighbor,neighborCallbacks);','obj.Neighbors=ac.PopulationNeighbors(obj.NodeId,scheduler,obj.Config.Neighbor,neighborCallbacks);'),
 ('        function accepted = queueControl(obj,kind,peers,payload,reliable,scheduleWake)',helper+'        function accepted = queueControl(obj,kind,peers,payload,reliable,scheduleWake)')])
bridge="""        function publishMacPopulation(obj,nodeId,count)
            if ~strcmp(obj.Config.ApplicationGenerator,'historical-opnet-gated'), return; end
            index=obj.NodeIndex(nodeId);
            obj.Macs{index}.setActiveNodes(count);
            ac.Trace.record(obj.Scheduler.Now,'mac_population_publish',nodeId, ...
                struct('ActiveNodes',count,'Cause','qualified_nwk_observation'));
        end

"""
gen('+ac/MessageFlagSimulation.m','+ac/PopulationSimulation.m',[
 ('classdef MessageFlagSimulation < handle','classdef PopulationSimulation < handle'),
 ('function obj = MessageFlagSimulation(config,linkObserver,transportTiming,autonomousOptions)','function obj = PopulationSimulation(config,linkObserver,transportTiming,autonomousOptions)'),
 ("                networkCallbacks = struct('CanSendData',@(peer)obj.Hops{k}.canSend(peer), ...", "                networkCallbacks = struct('PublishMacPopulation',@(count)obj.publishMacPopulation(nodeId,count), ...\n                    'CanSendData',@(peer)obj.Hops{k}.canSend(peer), ..."),
 ('obj.Networks{k} = ac.MessageFlagNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);','obj.Networks{k} = ac.PopulationNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);'),
 ('            index = obj.NodeIndex(nodeId);\n            obj.refreshHistoricalPopulation(index);\n            powerDefaulted', '            index = obj.NodeIndex(nodeId);\n            powerDefaulted'),
 ('                    obj.refreshHistoricalPopulation(index);\n                end\n            end\n            if ~addressed', '                end\n            end\n            if ~addressed'),
 ('        function refreshHistoricalPopulation(obj,index)',bridge+'        function refreshHistoricalPopulation(obj,index)')])
# The route candidate has 25 private/static class self-references. Bind their
# namespace-only rename as one unique whole-text edit for the generic checker.
import runpy
route_builder=runpy.run_path(str(Path(__file__).resolve().parents[1]/'routing'/'build_admission_routes.py'))
route_original=(root/'model/+csr/+nwk/Routes.m').read_text()
route_class_renamed=route_original.replace('classdef Routes < handle','classdef AdmissionRoutes < handle').replace('function obj = Routes(nodeId,capability,options)','function obj = AdmissionRoutes(nodeId,capability,options)')
route_refs_renamed=route_class_renamed.replace('csr.nwk.Routes','ac.AdmissionRoutes')
marker='        function setNeighbor(obj,peer,active,linkCost,now)\n'
expected_route=(root/'+ac/AdmissionRoutes.m').read_bytes()
gen('model/+csr/+nwk/Routes.m','+ac/AdmissionRoutes.m',[
 ('classdef Routes < handle','classdef AdmissionRoutes < handle'),
 ('function obj = Routes(nodeId,capability,options)','function obj = AdmissionRoutes(nodeId,capability,options)'),
 (route_class_renamed,route_refs_renamed),(marker,route_builder['METHOD']+marker)])
assert (root/'+ac/AdmissionRoutes.m').read_bytes()==expected_route
proof['route_namespace_rename_count']=route_original.count('csr.nwk.Routes')
gen('+ac/PopulationNwk.m','+ac/AdmissionNwk.m',[
 ('classdef PopulationNwk < handle','classdef AdmissionNwk < handle'),
 ('function obj = PopulationNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)','function obj = AdmissionNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)'),
 ('obj.Routes=csr.nwk.Routes(obj.NodeId,obj.Capability,obj.Config.Routing);','obj.Routes=ac.AdmissionRoutes(obj.NodeId,obj.Capability,obj.Config.Routing);'),
 ('obj.Routes.setNeighbor(peer,true,obj.peerCost(peer),obj.Scheduler.Now);','obj.Routes.admitNeighbor(peer,obj.peerCost(peer),obj.Scheduler.Now);')])
gen('+ac/PopulationSimulation.m','+ac/AdmissionSimulation.m',[
 ('classdef PopulationSimulation < handle','classdef AdmissionSimulation < handle'),
 ('function obj = PopulationSimulation(config,linkObserver,transportTiming,autonomousOptions)','function obj = AdmissionSimulation(config,linkObserver,transportTiming,autonomousOptions)'),
 ('obj.Networks{k} = ac.PopulationNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);','obj.Networks{k} = ac.AdmissionNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);')])
proof.pop('new_E_F_matlab_executed',None)
proof.update(schema='csr-isolated-population-candidate-v1',matlab_executed=False,
 prior_E_F_owner_executed=True,new_G_H_matlab_executed=False,production_model_changed=False,natural_path_changed=False,
 scope='G retains F and publishes MAC population only at qualifying NWK observation, removing eager addressed-member/enqueue refresh. H also separates route admission from direct-route observation.',
 current_limitation='No portable local ClearRoutes API; no captured native reset. Routing control-header population coverage remains unchanged.')
(root/'candidate_transform.json').write_text(json.dumps(proof,indent=2)+'\n')
print('Built isolated G/H classes; all inverse edits recover exact source bytes.')
