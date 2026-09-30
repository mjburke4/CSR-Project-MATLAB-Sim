function report=discoveryMembershipPreflight(config,folder)
%DISCOVERYMEMBERSHIPPREFLIGHT Public discovery-table population boundaries.
% Component routes arrive through observe/receiveControl. No private state,
% full-network execution, HOP/MAC/PHY transmission or random input is used.
if ~isfolder(folder), mkdir(folder); end
checks=struct('name',{},'passed',{},'details',{});

% Initial session knows direct peers4/5. Initiator5 is already complete;
% target4 remains outstanding. A later ROUTING UPDATE makes7 usable via5.
% The old watchdog incorrectly turns that route into a new discovery entry.
[layer,clock,probe]=lateRouteFixture(config,false);
assert(isequal(probe.destinations('SNMP_START'),4), ...
    'autocase:DiscoveryMembershipPreflight','Baseline initial scan order changed.');
clock.run(0.12); state=layer.stats();
assert(isequal(probe.destinations('SNMP_START'),[4 7]) && state.ScanWatchdogs==1, ...
    'autocase:DiscoveryMembershipPreflight','Baseline did not reproduce extra late-route START.');
checks(end+1)=checked('baseline_watchdog_adds_late_route_to_scan', ...
    struct('start_destinations',[4 7],'late_route_next_hop',5,'watchdogs',1));

% Candidate watchdog advances only existing discovery members. It cannot
% add7, drop its routing candidate or rewrite its route timestamp/sequence.
[layer,clock,probe]=lateRouteFixture(config,true);
before=routeSeven(layer); clock.run(0.12); after=routeSeven(layer); state=layer.stats();
assert(isequal(probe.destinations('SNMP_START'),4) && ...
    isequal(probe.destinations('SNMP_DONE'),5) && state.ScanWatchdogs==1 && ...
    isequal(before,after),'autocase:DiscoveryMembershipPreflight', ...
    'Watchdog changed membership, order, completion addressing or the retained route.');
checks(end+1)=checked('watchdog_preserves_membership_order_and_late_route', ...
    struct('start_destinations',4,'done_destinations',5,'watchdogs',1, ...
    'route_destination',7,'route_next_hop',5,'route_unchanged',true));

% The late route is still usable for ordinary DATA. A transit input avoids
% changing the configured policy for this node's locally generated traffic.
app=struct('Id',uint64(7801),'SourceId',4,'DestinationId',7,'Dscp',0, ...
    'GeneratedSeconds',clock.Now,'ApplicationPayloadBytes',185,'HopCount',0,'Traversal',4);
[accepted,reason]=layer.receiveData(app,4); clock.run(0.12);
assert(accepted && isempty(reason) && numel(probe.Data)==1 && ...
    probe.Data{1}.app.SourceId==4 && probe.Data{1}.app.DestinationId==7 && ...
    probe.Data{1}.peer==5 && probe.Data{1}.app.HopCount==1 && ...
    isequal(probe.Data{1}.app.Traversal,[4 3]) && ...
    isequal(probe.destinations('SNMP_START'),4), ...
    'autocase:DiscoveryMembershipPreflight','Late routing knowledge was unusable for DATA or expanded the scan.');
checks(end+1)=checked('late_route_remains_usable_for_transit_data', ...
    struct('source',4,'receiver',3,'destination',7,'next_hop',5,'send_callbacks',1));

% A received DONE report is an intended membership source, even if a prior
% watchdog has cleared its wait. Adding7 now must cause exactly one handoff.
done=struct('Type','SNMP_DONE','Payload',struct('SourceId',4,'DestinationId',3,'Nodes',7));
layer.receiveControl(done,4); clock.run(0.12);
assert(isequal(probe.destinations('SNMP_START'),[4 7]), ...
    'autocase:DiscoveryMembershipPreflight','Legitimate DONE report did not add late member7.');
starts=probe.ofType('SNMP_START'); last=starts{end};
assert(last.control.Payload.SourceId==3 && last.control.Payload.DestinationId==7 && ...
    isequal(last.peers,5) && last.control.WirePayloadBytes==31 && ~last.options.AckRequired, ...
    'autocase:DiscoveryMembershipPreflight','DONE-triggered handoff changed addressing or wire semantics.');
checks(end+1)=checked('received_done_populates_late_member', ...
    struct('start_destinations',[4 7],'final_destination',7,'next_hop',5,'wire_bytes',31));

% A later local discovery completion is the other intended route-population
% boundary. Reuse the same public setup independently, without a DONE input.
[layer,clock,probe]=lateRouteFixture(config,true); clock.run(0.12);
assert(isequal(probe.destinations('SNMP_START'),4), ...
    'autocase:DiscoveryMembershipPreflight','Late member was present before the new local session.');
accepted=layer.startDiscovery(0,0.01); assert(accepted, ...
    'autocase:DiscoveryMembershipPreflight','Second local session was not accepted.');
clock.run(0.14); state=layer.stats();
assert(state.DiscoveryStarts==2 && state.DiscoveryCompletions==2 && ...
    isequal(probe.destinations('SNMP_START'),[4 7]), ...
    'autocase:DiscoveryMembershipPreflight','Local completion failed to populate the late route.');
checks(end+1)=checked('new_local_completion_populates_late_route', ...
    struct('discovery_sessions',2,'start_destinations',[4 7]));

report=struct('schema','csr-discovery-membership-preflight-v1','passed',all([checks.passed]), ...
    'checks',checks,'network_simulation_executed',false,'random_variates_requested',0, ...
    'scope','Public NWK discovery membership and ordinary transit DATA callback boundaries', ...
    'fixture_scope','Admission-disabled observe establishes two direct component peers; a public ROUTING UPDATE learns7 via5', ...
    'limitations','No full-network/PHY/MAC parity claim. Existing completion snapshot cap and population ordering are not changed.');
ac.writeJson(fullfile(folder,'discovery_membership_preflight.json'),report);
end

function [layer,clock,probe]=lateRouteFixture(config,candidate)
config.Nwk.ControlQueueLimit=512;
config.Nwk.Neighbor.AdmissionEnabled=false;
config.Nwk.Neighbor.DiscoveryResponseEnabled=false;
config.Nwk.DiscoveryDurationSeconds=0.01;
config.Nwk.Neighbor.DiscoveryIntervalSeconds=1;
config.Nwk.Neighbor.DiscoveryBroadcastCount=1;
config.Nwk.GatewayWatchdogSeconds=0.1;
clock=csr.sim.EventScheduler(10000); probe=ac.DiscoveryMembershipProbe(); probe.Scheduler=clock;
callbacks=struct('SendControl',@(control,peers,options)probe.sendControl(control,peers,options), ...
    'CanSendControl',@(peers)true,'CanSendData',@(peer)true, ...
    'SendData',@(app,peer,options)probe.sendData(app,peer,options));
streams=csr.sim.RandomStreams(config.Seed);
if candidate, layer=ac.DiscoveryMembershipNwk(3,clock,streams,config,callbacks);
else, layer=ac.DiscoveryLifecycleNwk(3,clock,streams,config,callbacks); end
for peer=[5 4], layer.observe(peer,struct()); end
clock.run(0);
layer.receiveControl(struct('Type','SNMP_START','Payload', ...
    struct('SourceId',5,'DestinationId',3,'DelaySeconds',0)),5);
clock.run(0.02);
record=struct('Operation','UPDATE','NodeId',7,'Capability',1,'HopCount',1,'Cost',10,'Path',7);
sections=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords({record}),uint32(17));
assert(numel(sections)==1,'autocase:DiscoveryMembershipPreflight','Expected one late-route section.');
layer.receiveControl(struct('Type','ROUTING','Payload',struct('Bytes',sections{1})),5);
clock.run(0.02);
route=routeSeven(layer);
assert(route.NextHop==5 && route.Valid && route.Capability==1 && route.LastUpdatedSeconds==0.02, ...
    'autocase:DiscoveryMembershipPreflight','Public ROUTING UPDATE did not establish the late route.');
end
function selected=routeSeven(layer)
routes=layer.routesSnapshot(); selected=routes([routes.DestinationId]==7);
assert(isscalar(selected),'autocase:DiscoveryMembershipPreflight','Expected one selected route to7.');
end
function value=checked(name,details)
value=struct('name',name,'passed',true,'details',details);
end
