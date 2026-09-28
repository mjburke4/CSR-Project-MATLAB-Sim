"""Source-bound compact REQUEST representation; original model remains untouched."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]/'kit'/'autocase'
def sha(b):return hashlib.sha256(b).hexdigest()
prior=Path(__file__).resolve().parents[2]/'autonomous_fifth/kit/autocase/candidate_transform.json'
proof=json.loads(prior.read_text())
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
edits=[
 ('classdef AdmissionNwk < handle','classdef ControlWireNwk < handle'),
 ('function obj = AdmissionNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)','function obj = ControlWireNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)'),
 ("'WirePayloadBytes',csr.nwk.controlWireBytes(kind,payload,numel(peers),", "'WirePayloadBytes',ac.controlWireBytes(kind,payload,numel(peers),"),
 ("owner.Control.WirePayloadBytes=csr.nwk.controlWireBytes( ...\n                        owner.Control.Type", "owner.Control.WirePayloadBytes=ac.controlWireBytes( ...\n                        owner.Control.Type"),
 ("owner.Control.WirePayloadBytes=csr.nwk.controlWireBytes( ...\n                        'ROUTING'", "owner.Control.WirePayloadBytes=ac.controlWireBytes( ...\n                        'ROUTING'"),
 ("        function accepted = sendRecords(obj,records,peers,mode)\n            if nargin<4, mode='changes'; end", """        function accepted = sendRecords(obj,records,peers,mode,wireRepresentation)
            if nargin<4, mode='changes'; end
            if nargin<5, wireRepresentation='arl_section'; end
            if strcmp(wireRepresentation,'legacy_request_header')
                assert(strcmp(mode,'changes') && numel(peers)==1 && numel(records)==1 && ...
                    isstruct(records{1}) && isscalar(records{1}) && ...
                    isfield(records{1},'Operation') && strcmp(records{1}.Operation,'REQUEST'), ...
                    'autocase:RequestRepresentation','Compact representation requires one generated unicast REQUEST.');
            else
                assert(strcmp(wireRepresentation,'arl_section'), ...
                    'autocase:RequestRepresentation','Unknown routing wire representation.');
            end"""),
 ("'NextSection',nextSection,'NextPeer',nextPeer,'Mode',mode);", "'NextSection',nextSection,'NextPeer',nextPeer,'Mode',mode, ...\n                'WireRepresentation',wireRepresentation);"),
 ("""                    obj.queueControl('ROUTING',group, ...
                        struct('Bytes',message.Sections{message.NextSection}),true,false);""", """                    payload=struct('Bytes',message.Sections{message.NextSection});
                    if strcmp(message.WireRepresentation,'legacy_request_header')
                        % Bytes retain receiver semantics; the native sender
                        % carries this request in its compatibility header.
                        payload.WireRepresentation=message.WireRepresentation;
                    end
                    obj.queueControl('ROUTING',group,payload,true,false);"""),
 ("obj.sendRecords({struct('Operation','REQUEST')},peer,'changes');", "obj.sendRecords({struct('Operation','REQUEST')},peer,'changes','legacy_request_header');")]
gen('+ac/AdmissionNwk.m','+ac/ControlWireNwk.m',edits)
gen('+ac/AdmissionSimulation.m','+ac/ControlWireSimulation.m',[
 ('classdef AdmissionSimulation < handle','classdef ControlWireSimulation < handle'),
 ('function obj = AdmissionSimulation(config,linkObserver,transportTiming,autonomousOptions)','function obj = ControlWireSimulation(config,linkObserver,transportTiming,autonomousOptions)'),
 ('obj.Networks{k} = ac.AdmissionNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);','obj.Networks{k} = ac.ControlWireNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);')])
for obsolete in ['new_G_matlab_executed','new_G_H_matlab_executed']:
 proof.pop(obsolete,None)
proof.update(schema='csr-isolated-control-wire-candidate-v1',matlab_executed=False,
 prior_G_H_owner_executed=True,new_I_matlab_executed=False,production_model_changed=False,natural_path_changed=False,
 scope='I retains H; origin-tagged compact REQUEST excludes semantic-only bytes at all three owner sizing boundaries. The isolated helper also excludes the compatibility-only NoPath target from wire size.',
 current_limitation='Ordinary raw ARL sections remain unchanged; this is not a blanket routing-size correction.')
(root/'candidate_transform.json').write_text(json.dumps(proof,indent=2)+'\n')
print('Built I with 16 total source-bound transforms; all reverse exactly.')
