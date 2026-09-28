function report=discoveryLifecyclePreflight(config,folder)
%DISCOVERYLIFECYCLEPREFLIGHT Two changed public NWK lifecycle boundaries.
% No network, MAC or PHY simulation; no private state, forced tape or RNG.
if ~isfolder(folder), mkdir(folder); end
checks=struct('name',{},'passed',{},'details',{});

% An unacknowledged KEY_REQUEST must still bypass reliable HOP availability.
[layer,clock,probe]=makeLayer(config,true,8); probe.GateOpen=false;
layer.receiveControl(struct('Type','DISCOVER','Payload', ...
    struct('Subtype','broadcast','Sequence',1,'ActivePeers',[])),4);
assert(numel(probe.Calls)==1 && isempty(probe.GateCalls) && ...
    strcmp(probe.Calls{1}.control.Type,'KEY_REQUEST') && ...
    ~probe.Calls{1}.options.AckRequired && clock.Now==0, ...
    'autocase:DiscoveryLifecyclePreflight','No-ACK KEY_REQUEST was gated or deferred.');
checks(end+1)=checked('no_ack_key_request_still_inline_with_reliable_gate_closed', ...
    struct('send_callbacks',1,'reliable_gate_calls',0));

% Fresh reliable KEY_UPDATE is submitted with its owner already present.
[layer,clock,probe]=makeLayer(config,true,8);
layer.receiveControl(keyRequest(),4);
assert(numel(probe.Calls)==1 && numel(probe.GateCalls)==1 && ...
    isequal(probe.GateCalls{1},4) && probe.OwnerCountsAtSend(1)==1 && ...
    strcmp(probe.Calls{1}.control.Type,'KEY_UPDATE') && ...
    probe.Calls{1}.options.AckRequired && clock.Now==0, ...
    'autocase:DiscoveryLifecyclePreflight','Reliable KEY_UPDATE was not admitted inline after its gate.');
call=probe.Calls{1};
frame=csr.hop.Frames.control(call.control,5,4,uint16(0),call.options);
assert(call.control.WirePayloadBytes==62 && frame.WirePayloadBytes==62 && ...
    frame.Dscp==7 && frame.AckRequired,'autocase:DiscoveryLifecyclePreflight', ...
    'Inline admission changed reliable KEY_UPDATE radio/payload semantics.');
clock.run(0);
assert(numel(probe.Calls)==1,'autocase:DiscoveryLifecyclePreflight','Inline accepted owner was sent twice.');
checks(end+1)=checked('reliable_key_update_inline_preserves_owner_ack_and_wire_fields', ...
    struct('wire_bytes',62,'dscp',7,'ack_required',true,'owner_present_at_callback',true));

% A blocked gate and an explicit failed submission both retain the owner.
% Opening the gate or accepting the original wake retry submits it once.
[layer,clock,probe]=makeLayer(config,true,8); probe.GateOpen=false;
layer.receiveControl(keyRequest(),4); state=layer.stats();
assert(isempty(probe.Calls) && state.PendingControlMessages==1, ...
    'autocase:DiscoveryLifecyclePreflight','Closed reliable gate lost or submitted its owner.');
probe.GateOpen=true; clock.run(0);
assert(numel(probe.Calls)==1 && probe.Calls{1}.options.AckRequired, ...
    'autocase:DiscoveryLifecyclePreflight','Blocked reliable owner did not use the normal wake.');
[layer,clock,probe]=makeLayer(config,true,8); probe.Accept=false;
layer.receiveControl(keyRequest(),4); state=layer.stats();
assert(numel(probe.Calls)==1 && state.PendingControlMessages==1, ...
    'autocase:DiscoveryLifecyclePreflight','Failed reliable submission lost its owner.');
id=probe.Calls{1}.control.Id; probe.Accept=true; clock.run(0); clock.run(0);
assert(numel(probe.Calls)==2 && probe.Calls{2}.control.Id==id && ...
    probe.Calls{2}.options.AckRequired,'autocase:DiscoveryLifecyclePreflight', ...
    'Failed reliable admission did not retry exactly its retained owner.');
checks(end+1)=checked('blocked_and_failed_reliable_admissions_keep_normal_retry', ...
    struct('blocked_then_open_callbacks',1,'failed_then_accepted_callbacks',2,'same_owner_retried',true));

% Capacity is checked before calling HOP. This tests retained MATLAB safety;
% native and MATLAB overflow policies are not asserted to be identical.
[layer,clock,probe]=makeLayer(config,true,1); probe.GateOpen=false;
layer.receiveControl(keyRequest(),2); probe.GateOpen=true;
layer.receiveControl(keyRequest(),4); state=layer.stats();
assert(isempty(probe.Calls) && state.PendingControlMessages==1 && ...
    state.ControlQueueRejections==1,'autocase:DiscoveryLifecyclePreflight', ...
    'Capacity rejection called HOP or removed the existing owner.');
checks(end+1)=checked('capacity_rejection_preserves_existing_owner_before_submission', ...
    struct('pending_controls',1,'rejections',1,'scope','retained MATLAB safety, not native overflow parity'));

% Fresh admission must not become a general pump of other controls or DATA.
[layer,clock,probe]=makeLayer(config,true,8); probe.GateOpen=false;
layer.receiveControl(keyRequest(),2);
accepted=layer.sendApplication(struct('Id',uint64(7701),'SourceId',5,'DestinationId',8,'Dscp',0));
assert(accepted,'autocase:DiscoveryLifecyclePreflight','Unrelated application fixture was not queued.');
probe.GateOpen=true; layer.receiveControl(keyRequest(),4); state=layer.stats();
assert(numel(probe.Calls)==1 && isequal(probe.Calls{1}.peers,4) && ...
    state.PendingControlMessages==2 && state.PendingCustody==1 && probe.DataCalls==0, ...
    'autocase:DiscoveryLifecyclePreflight','Fresh inline KEY_UPDATE pumped another owner.');
checks(end+1)=checked('inline_key_update_does_not_pump_unrelated_owners', ...
    struct('pending_controls',2,'pending_applications',1,'data_callbacks',0));

% An ACK may complete during submission. It may legitimately enqueue a
% NeighborCheck, so assert original-owner identity rather than empty queues.
[layer,clock,probe]=makeLayer(config,true,8); probe.CompleteKeyInline=true;
layer.receiveControl(struct('Type','KEY_UPDATE','Payload',struct('Generation',0)),4);
keyCalls=probe.ofType('KEY_UPDATE'); assert(numel(keyCalls)==1, ...
    'autocase:DiscoveryLifecyclePreflight','Reentrant key fixture did not send one KEY_UPDATE.');
completed=keyCalls{1}.control; before=layer.stats();
layer.controlResult(completed,4,true,true,[]); after=layer.stats();
assert(before.PendingControlMessages==after.PendingControlMessages, ...
    'autocase:DiscoveryLifecyclePreflight','Repeated completion found a resurrected owner.');
clock.run(0); keyCalls=probe.ofType('KEY_UPDATE'); peers=layer.neighborsSnapshot();
peer=peers([peers.Id]==4);
assert(numel(keyCalls)==1 && peer.SentKey && ...
    ~isempty(probe.ofType('NEIGHBOR_CHECK')) && all(probe.OwnerCountsAtSend>=1), ...
    'autocase:DiscoveryLifecyclePreflight','Reentrant completion lost proof work or resubmitted the old owner.');
checks(end+1)=checked('reentrant_key_completion_keeps_followon_owner_without_resurrection', ...
    struct('key_update_callbacks',1,'followon_neighbor_check_present',true,'peer_sent_key',true));

% Public observations establish only component direct routes. Source 3
% starts an idle session; source 1 asks twice during it. Both receive DONE,
% but only the initiating source is already excluded from outbound scans.
[baseline,baseClock,baseProbe]=scanFixture(config,false);
startWithDuplicate(baseline,baseClock); baseClock.run(0.01);
assert(isequal(baseProbe.destinations('SNMP_DONE'),[3 1]) && ...
    isequal(baseProbe.destinations('SNMP_START'),2), ...
    'autocase:DiscoveryLifecyclePreflight','Historical baseline did not reproduce active-requester suppression.');
[layer,clock,probe]=scanFixture(config,true);
startWithDuplicate(layer,clock); clock.run(0.01); state=layer.stats();
assert(isequal(probe.destinations('SNMP_DONE'),[3 1]) && ...
    isequal(probe.destinations('SNMP_START'),1) && state.DiscoveryStarts==1 && ...
    state.DiscoveryCompletions==1,'autocase:DiscoveryLifecyclePreflight', ...
    'Active requester was excluded, duplicated, or caused a second discovery session.');
management=[probe.ofType('SNMP_DONE') probe.ofType('SNMP_START')];
for k=1:numel(management)
    call=management{k}; payload=call.control.Payload;
    assert(payload.SourceId==5 && isequal(call.peers,payload.DestinationId) && ...
        ~call.options.AckRequired,'autocase:DiscoveryLifecyclePreflight', ...
        'SNMP completion or handoff changed final/next-hop addressing or reliability.');
end
checks(end+1)=checked('active_duplicate_kept_for_done_and_outbound_scan_idle_initiator_skipped', ...
    struct('done_destinations',[3 1],'baseline_next_target',2,'candidate_next_target',1, ...
    'discovery_sessions',1,'duplicate_start_requests_from_1',2));

% Completing target 1 advances to the next target, and duplicate DONE does
% not create another outstanding START. All checks use public controls.
layer.receiveControl(snmp('SNMP_DONE',1,struct('Nodes',[])),1); clock.run(0.01);
assert(isequal(probe.destinations('SNMP_START'),[1 2]), ...
    'autocase:DiscoveryLifecyclePreflight','DONE did not advance from retained requester1 to target2.');
layer.receiveControl(snmp('SNMP_DONE',1,struct('Nodes',[])),1); clock.run(0.01);
assert(isequal(probe.destinations('SNMP_START'),[1 2]) && ...
    isequal(probe.destinations('SNMP_DONE'),[3 1]), ...
    'autocase:DiscoveryLifecyclePreflight','Duplicate DONE or retained requester generated duplicate controls.');
checks(end+1)=checked('completion_progression_retains_single_outstanding_handoff', ...
    struct('start_destinations',[1 2],'done_destinations',[3 1]));

report=struct('schema','csr-discovery-lifecycle-preflight-v1','passed',all([checks.passed]), ...
    'checks',checks,'network_simulation_executed',false,'random_variates_requested',0, ...
    'scope','Public NWK callback boundary and isolated discovery requester lifecycle; no PHY/MAC timing parity claim', ...
    'capacity_limitation','Retained MATLAB queue/retry safety only; native overflow policy is not claimed identical', ...
    'scan_fixture','Admission-disabled public observations create three direct routes; no private state is injected');
ac.writeJson(fullfile(folder,'discovery_lifecycle_preflight.json'),report);
end

function [layer,clock,probe]=makeLayer(config,candidate,limit)
config.Nwk.ControlQueueLimit=limit;
clock=csr.sim.EventScheduler(10000); probe=ac.DiscoveryLifecycleProbe(); probe.Scheduler=clock;
callbacks=struct('SendControl',@(control,peers,options)probe.sendControl(control,peers,options), ...
    'CanSendControl',@(peers)probe.canSend(peers), ...
    'SendData',@(app,peer,options)probe.sendData(app,peer,options),'CanSendData',@(peer)true);
streams=csr.sim.RandomStreams(config.Seed);
if candidate, layer=ac.DiscoveryLifecycleNwk(5,clock,streams,config,callbacks);
else, layer=ac.ControlWireNwk(5,clock,streams,config,callbacks); end
probe.Layer=layer;
end
function [layer,clock,probe]=scanFixture(config,candidate)
config.Nwk.Neighbor.AdmissionEnabled=false;
config.Nwk.Neighbor.DiscoveryResponseEnabled=false;
config.Nwk.DiscoveryDurationSeconds=0.01;
config.Nwk.Neighbor.DiscoveryIntervalSeconds=1;
config.Nwk.Neighbor.DiscoveryBroadcastCount=1;
[layer,clock,probe]=makeLayer(config,candidate,512);
for peer=[2 1 3], layer.observe(peer,struct()); end
clock.run(0);
end
function startWithDuplicate(layer,clock)
layer.receiveControl(snmp('SNMP_START',3,struct('DelaySeconds',0)),3); clock.run(0);
layer.receiveControl(snmp('SNMP_START',1,struct('DelaySeconds',0)),1);
layer.receiveControl(snmp('SNMP_START',1,struct('DelaySeconds',0)),1);
end
function control=snmp(kind,source,payload)
payload.SourceId=source; payload.DestinationId=5;
control=struct('Type',kind,'Payload',payload);
end
function control=keyRequest()
control=struct('Type','KEY_REQUEST','Payload',struct('Generation',0));
end
function value=checked(name,details)
value=struct('name',name,'passed',true,'details',details);
end
