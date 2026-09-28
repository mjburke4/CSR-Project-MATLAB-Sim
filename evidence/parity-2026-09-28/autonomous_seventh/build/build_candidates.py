"""Isolate trace-only broadcast DISCOVER identity comparison from protocol."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]/'kit/autocase'
previous=Path(__file__).resolve().parents[2]/'autonomous_sixth/kit/autocase'
def sha(b):return hashlib.sha256(b).hexdigest()
proof=json.loads((previous/'candidate_transform.json').read_text())
def gen(source,target,edits):
 raw=(root/source).read_bytes();s=raw.decode()
 for old,new in edits:
  assert s.count(old)==1,(source,old[:90],s.count(old));s=s.replace(old,new)
 result=s.encode();(root/target).write_bytes(result)
 reverse=s
 for old,new in reversed(edits):
  assert reverse.count(new)==1,(source,new[:90],reverse.count(new));reverse=reverse.replace(new,old)
 assert reverse.encode()==raw
 proof['transforms'].append(dict(source=source,source_sha256=sha(raw),target=target,target_sha256=sha(result),reverse_recovers_source=True,edits=[dict(old=a,new=b) for a,b in edits]))
eligibility="""                % The native outer broadcast DISCOVER counter is process-
                % scoped; MATLAB's is per sender. Source audit proves that
                % this field is trace-only for this exact observed subtype.
                % Payload discovery-session sequence remains strictly checked.
                discoveryTraceIdentity=strcmp(child.Kind,'CONTROL') && ...
                    strcmp(child.Control.Type,'DISCOVER') && ...
                    double(child.DestinationId)==16777215 && ...
                    numel(child.DestinationIds)==1 && double(child.DestinationIds(1))==16777215 && ...
                    ~child.AckRequired && ~child.HasAckWindow && ...
                    strcmp(char(child.Control.Payload.Subtype),'broadcast') && ...
                    double(wanted.kind)==4 && double(wanted.hop_destination)==16777215 && ...
                    double(wanted.ackable)==0 && double(wanted.has_ack_window)==0 && ...
                    double(wanted.destination_type)==1 && ...
                    bitand(uint16(wanted.flags),uint16(128))~=0 && isfinite(double(wanted.security_count)) && ...
                    strcmp(char(wanted.discover_subtype),'broadcast');
                if discoveryTraceIdentity
                    item.discovery_outer_sequence_identity=struct( ...
                        'actual',item.hop_sequence,'native',double(wanted.hop_sequence), ...
                        'policy','trace_only_broadcast_discover_identifier', ...
                        'reason','Native process counter versus MATLAB per-sender counter; receiver/MAC/PHY do not use this outer field');
                end
"""
gen('+ac/TxSignature.m','+ac/DiscoveryTxSignature.m',[
 ('classdef TxSignature','classdef DiscoveryTxSignature'),
 ("'kind',ac.TxSignature.kind(child)","'kind',ac.DiscoveryTxSignature.kind(child)"),
 ('                fields=fieldnames(item);',eligibility+'                fields=fieldnames(item);'),
 ("                    if endsWith(name,'_ns') || ~isfield(wanted,name), continue; end", "                    if endsWith(name,'_ns') || ~isfield(wanted,name), continue; end\n                    if discoveryTraceIdentity && strcmp(name,'hop_sequence'), continue; end")])
gen('+ac/Streams.m','+ac/DiscoveryStreams.m',[
 ('classdef Streams < handle','classdef DiscoveryStreams < handle'),
 ('function obj=Streams(seed,scheduler,mode,fixture,folder)','function obj=DiscoveryStreams(seed,scheduler,mode,fixture,folder)'),
 ('[actual,mismatches]=ac.TxSignature.compare(frame,rows);','[actual,mismatches]=ac.DiscoveryTxSignature.compare(frame,rows);')])
gen('+ac/ControlWireSimulation.m','+ac/DiscoveryIdentitySimulation.m',[
 ('classdef ControlWireSimulation < handle','classdef DiscoveryIdentitySimulation < handle'),
 ('function obj = ControlWireSimulation(config,linkObserver,transportTiming,autonomousOptions)','function obj = DiscoveryIdentitySimulation(config,linkObserver,transportTiming,autonomousOptions)'),
 ('obj.Streams = ac.Streams(config.Seed,obj.Scheduler, ...','obj.Streams = ac.DiscoveryStreams(config.Seed,obj.Scheduler, ...')])
proof.pop('new_I_matlab_executed',None)
proof.update(schema='csr-isolated-discovery-identity-candidate-v1',matlab_executed=False,
 prior_I_owner_executed=True,new_J_matlab_executed=False,production_model_changed=False,natural_path_changed=False,
 scope='J runs unchanged I protocol with a comparator-only exception for trace-only outer sequence of broadcast, non-ACK DISCOVER subtype broadcast. Both actual/native eligibility is required; raw identities are retained.',
 current_limitation='No exception for chirp, other controls, reliable sequence numbers or payload discovery-session sequence; full wire serialization is not claimed.')
(root/'candidate_transform.json').write_text(json.dumps(proof,indent=2)+'\n')
print('Built J comparator/provider/simulation copies; 19 transformations reverse exactly.')
