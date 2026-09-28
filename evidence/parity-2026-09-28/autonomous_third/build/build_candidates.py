"""Build isolated, source-bound diagnostic classes; never edit the model tree."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]/'kit'/'autocase'
def sha(b): return hashlib.sha256(b).hexdigest()
records=[]
def generate(source,target,edits):
    raw=(root/source).read_bytes(); text=raw.decode()
    for old,new in edits:
        assert text.count(old)==1,(source,old[:100],text.count(old))
        text=text.replace(old,new)
    result=text.encode(); (root/target).write_bytes(result)
    reverse=text
    for old,new in reversed(edits):
        assert reverse.count(new)==1
        reverse=reverse.replace(new,old)
    assert reverse.encode()==raw
    records.append(dict(source=source,source_sha256=sha(raw),target=target,target_sha256=sha(result),
      reverse_recovers_source=True,edits=[dict(old=a,new=b) for a,b in edits]))
branch="""            if scheduleWake && strcmp(kind,'KEY_REQUEST') && ~reliable
                % Diagnostic candidate: native NWK admits this newly-created
                % no-ACK request while the receive callback is still Track.
                % Preserve replacement/capacity above; never pump other owners.
                controlId=control.Id;
                position=obj.controlPosition(controlId);
                obj.Controls{position}.Submitted=true;
                options=obj.radioOptions(peers,struct()); options.AckRequired=false;
                submitted=false;
                if isfield(obj.Callbacks,'SendControl')
                    submitted=obj.Callbacks.SendControl(control,peers,options);
                end
                % A synchronous sent/completion callback may remove the owner.
                position=obj.controlPosition(controlId);
                if ~submitted && position>0, obj.Controls{position}.Submitted=false; end
                if submitted, return; end
                % Failed admission retains the original deferred retry path.
            end
"""
needle="            obj.Controls{end+1}=owner;\n            if scheduleWake, obj.wake(); end"
generate('model/+csr/+nwk/Layer.m','+ac/InlineKeyNwk.m',[
 ('classdef Layer < handle','classdef InlineKeyNwk < handle'),
 ('function obj = Layer(nodeId,scheduler,streams,fullScenarioConfig,callbacks)',
  'function obj = InlineKeyNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)'),
 (needle,'            obj.Controls{end+1}=owner;\n'+branch+'            if scheduleWake, obj.wake(); end')])
generate('model/+csr/+sim/NetworkSimulation.m','+ac/InlineKeySimulation.m',[
 ('classdef NetworkSimulation < handle','classdef InlineKeySimulation < handle'),
 ('function obj = NetworkSimulation(config,linkObserver,transportTiming,autonomousOptions)',
  'function obj = InlineKeySimulation(config,linkObserver,transportTiming,autonomousOptions)'),
 ('obj.Networks{k} = csr.nwk.Layer(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);',
  'obj.Networks{k} = ac.InlineKeyNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);')])
proof=dict(schema='csr-isolated-key-request-candidate-v1',matlab_executed=False,
 production_model_changed=False,natural_path_changed=False,scope='D only: submit only a fresh no-ACK KEY_REQUEST owner inline after unchanged replacement/capacity checks; failed admission uses original wake path.',
 unsupported_claims=['No production fix acceptance','No full-network performance parity','No generic control/data pump timing change'],transforms=records)
(root/'candidate_transform.json').write_text(json.dumps(proof,indent=2)+'\n')
print('Generated two isolated classes; inverse edits recover both exact model source files.')
