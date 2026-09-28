"""Source-bound separation of routing knowledge and discovery membership."""
from pathlib import Path
import hashlib
import json

base = Path(__file__).resolve().parents[1]
root = base / 'kit/autocase'
previous = base.parent / 'autonomous_ninth/kit/autocase'
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

gen('+ac/DiscoveryLifecycleNwk.m', '+ac/DiscoveryMembershipNwk.m', [
    ('classdef DiscoveryLifecycleNwk < handle', 'classdef DiscoveryMembershipNwk < handle'),
    ('function obj = DiscoveryLifecycleNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)',
     'function obj = DiscoveryMembershipNwk(nodeId,scheduler,streams,fullScenarioConfig,callbacks)'),
    ("""        function advanceScan(obj)
            if ~obj.ScanComplete || obj.Capability==0 || ~isempty(obj.ScanWaiting), return; end
            obj.mergeScanKnown(obj.Routes.reachableDestinations());
            pending=obj.ScanKnown(~ismember(obj.ScanKnown,obj.ScanRequested));""",
     """        function advanceScan(obj)
            if ~obj.ScanComplete || obj.Capability==0 || ~isempty(obj.ScanWaiting), return; end
            % Native advances existing discovery entries. New routing knowledge
            % enters this table only at discovery completion or received DONE.
            pending=obj.ScanKnown(~ismember(obj.ScanKnown,obj.ScanRequested));"""),
])
gen('+ac/DiscoveryLifecycleSimulation.m', '+ac/DiscoveryMembershipSimulation.m', [
    ('classdef DiscoveryLifecycleSimulation < handle', 'classdef DiscoveryMembershipSimulation < handle'),
    ('function obj = DiscoveryLifecycleSimulation(config,linkObserver,transportTiming,autonomousOptions)',
     'function obj = DiscoveryMembershipSimulation(config,linkObserver,transportTiming,autonomousOptions)'),
    ('obj.Networks{k} = ac.DiscoveryLifecycleNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);',
     'obj.Networks{k} = ac.DiscoveryMembershipNwk(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);'),
])
proof.pop('new_L_matlab_executed', None)
proof.update(
    schema='csr-isolated-discovery-membership-candidate-v1', matlab_executed=False,
    prior_L_owner_executed=True, new_M_matlab_executed=False, production_model_changed=False,
    natural_path_changed=False,
    scope='M retains L control/timer/comparison paths; advanceScan selects only existing discovery members, populated by local discovery completion or received DONE. Ordinary route learning no longer adds work at advancement/watchdog.',
    current_limitation='Unrelated portable/native SNMP DONE gating, requester capacity and reliable overflow differences remain unchanged. No full-network parity claim.',
)
(root / 'candidate_transform.json').write_text(json.dumps(proof, indent=2) + '\n')
print('Built M: 26 exact reversible transforms; one executable membership line removed.')
