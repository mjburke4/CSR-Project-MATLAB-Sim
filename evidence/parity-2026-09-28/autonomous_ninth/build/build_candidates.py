"""Source-bound SNMP session ownership and inline reliable key update."""
from pathlib import Path
import hashlib
import json

base = Path(__file__).resolve().parents[1]
root = base / 'kit/autocase'
previous = base.parent / 'autonomous_eighth/kit/autocase'
proof = json.loads((previous / 'candidate_transform.json').read_text())

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def gen(source, target, edits):
    raw = (root / source).read_bytes()
    text = raw.decode()
    for old, new in edits:
        assert text.count(old) == 1, (source, old[:100], text.count(old))
        text = text.replace(old, new)
    result = text.encode()
    (root / target).write_bytes(result)
    reverse = text
    for old, new in reversed(edits):
        assert reverse.count(new) == 1
        reverse = reverse.replace(new, old)
    assert reverse.encode() == raw
    proof['transforms'].append(dict(
        source=source, source_sha256=sha(raw), target=target, target_sha256=sha(result),
        reverse_recovers_source=True, edits=[dict(old=a, new=b) for a,b in edits]))

old_inline = """            if scheduleWake && strcmp(kind,'KEY_REQUEST') && ~reliable
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
            end"""
new_inline = """            if scheduleWake && ((strcmp(kind,'KEY_REQUEST') && ~reliable) || ...
                    (strcmp(kind,'KEY_UPDATE') && reliable))
                % Native admits fresh key traffic inside the receive callback.
                % Retain each reliable owner's HOP gate and ACK/radio options;
                % never pump unrelated owners or application traffic here.
                canSubmit=~reliable || ~isfield(obj.Callbacks,'CanSendControl') || ...
                    obj.Callbacks.CanSendControl(peers);
                if canSubmit
                    controlId=control.Id;
                    position=obj.controlPosition(controlId);
                    obj.Controls{position}.Submitted=true;
                    options=obj.radioOptions(peers,struct()); options.AckRequired=logical(reliable);
                    submitted=false;
                    if isfield(obj.Callbacks,'SendControl')
                        submitted=obj.Callbacks.SendControl(control,peers,options);
                    end
                    % A synchronous completion may remove or append owners.
                    position=obj.controlPosition(controlId);
                    if ~submitted && position>0, obj.Controls{position}.Submitted=false; end
                    if submitted, return; end
                end
                % Blocked or failed admission retains ordinary deferred retry.
            end"""
gen('+ac/ControlWireNwk.m', '+ac/DiscoveryLifecycleNwk.m', [
    ('classdef ControlWireNwk < handle', 'classdef DiscoveryLifecycleNwk < handle'),
    ('function obj = ControlWireNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)',
     'function obj = DiscoveryLifecycleNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)'),
    ("""                    if ~obj.ScanStarted || obj.ScanComplete
                        obj.startDiscovery(max(0,option(payload,'DelaySeconds',0)));
                    end
                    if ~ismember(source,obj.ScanRequested), obj.ScanRequested(end+1)=source; end""",
     """                    if ~obj.ScanStarted || obj.ScanComplete
                        % Only an idle/new-session initiator is marked done.
                        % An active duplicate still receives DONE and remains
                        % eligible for a later outbound discovery handoff.
                        if ~ismember(source,obj.ScanRequested), obj.ScanRequested(end+1)=source; end
                        obj.startDiscovery(max(0,option(payload,'DelaySeconds',0)));
                    end"""),
    (old_inline, new_inline),
])
gen('+ac/ReceiverTimerSimulation.m', '+ac/DiscoveryLifecycleSimulation.m', [
    ('classdef ReceiverTimerSimulation < handle', 'classdef DiscoveryLifecycleSimulation < handle'),
    ('function obj = ReceiverTimerSimulation(config,linkObserver,transportTiming,autonomousOptions)',
     'function obj = DiscoveryLifecycleSimulation(config,linkObserver,transportTiming,autonomousOptions)'),
    ('obj.Networks{k} = ac.ControlWireNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);',
     'obj.Networks{k} = ac.DiscoveryLifecycleNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);'),
])
proof.pop('new_K_matlab_executed', None)
proof.update(
    schema='csr-isolated-discovery-lifecycle-candidate-v1', matlab_executed=False,
    prior_K_owner_executed=True, new_L_matlab_executed=False, production_model_changed=False,
    natural_path_changed=False,
    scope='L retains K timer/protocol/comparison paths; mark an SNMP requester complete only when it starts a new local discovery session, and admit a fresh reliable KEY_UPDATE inline with existing HOP availability and owner/radio/ACK rules.',
    current_limitation='Blocked/failed key admission retains the portable deferred retry path. Native/MATLAB SNMP DONE wait policy and requester-capacity differences are not changed; neither triggered in the captured prefix. No full-network parity claim.',
)
(root / 'candidate_transform.json').write_text(json.dumps(proof, indent=2) + '\n')
print('Built L: 24 exact reversible transforms; K timer and strict guards unchanged.')
