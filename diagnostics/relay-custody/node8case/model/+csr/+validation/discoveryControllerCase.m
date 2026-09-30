function report = discoveryControllerCase(config,outputDirectory)
%DISCOVERYCONTROLLERCASE Replay prescribed inputs through the real NWK layer.
% The lower-layer callback accepts and records controls, without transmitting
% or acknowledging them. Peer observations and decoded routing self-updates
% supply the fixture boundary. No production object is modified or copied.
if nargin<2, outputDirectory=''; end
validateCase(config);
started=tic;
scheduler=csr.sim.EventScheduler(10000);
options=csr.nwk.defaults();
options.StartupMode='manual';
options.AdaptiveLinkControl=false;
options.Neighbor.AdmissionEnabled=false;
radio=struct('RateKeyKbps',8,'TxPowerDbm',30,'Preamble','long','EnvelopeProfile','bare');
fullConfig=struct('Nwk',options,'Radio',radio, ...
    'Nodes',struct('Id',1,'Capability',2,'TransitForwardingEnabled',true));
controls=repmat(emptyControl(),0,1);
snapshots=repmat(emptySnapshot(),0,1);
allControls=repmat(struct('time_s',0,'kind','','peers',[],'ackable',false),0,1);
logicalBirthOrder=[];
layer=csr.nwk.Layer(1,scheduler,[],fullConfig,struct( ...
    'CanSendControl',@(~)true,'SendControl',@captureControl));
% Do not call start(): autonomous startup and periodic monitoring are outside
% this boundary. Local discovery is explicitly started below.
for peer=reshape(config.initial_peers,1,[]), addUsablePeer(peer); end
if ~layer.startDiscovery(0,config.local_duration_s)
    error('csr:t27:Start','The explicit local discovery was not accepted.');
end
scheduler.run(0);
times=sort(unique([reshape(config.checkpoints_s,1,[]), ...
    reshape(config.done_time_s,1,[]),reshape(config.late_peer_time_s,1,[]),config.stop_s]));
for time=times
    scheduler.run(time);
    if ~isempty(config.done_time_s) && time==config.done_time_s
        layer.receiveControl(struct('Type','SNMP_DONE','Payload', ...
            struct('SourceId',config.done_source,'DestinationId',1,'Nodes',[])), ...
            config.done_source);
    end
    if ~isempty(config.late_peer_time_s) && time==config.late_peer_time_s
        addUsablePeer(config.late_peer);
    end
    scheduler.run(time);
    if any(config.checkpoints_s==time), captureSnapshot(); end
end
finalStats=layer.stats();
structuralPassed=numel(snapshots)==numel(config.checkpoints_s) && ...
    finalStats.DiscoveryStarts==1 && finalStats.DiscoveryCompletions==1 && ...
    finalStats.MalformedControl==0 && finalStats.ControlQueueRejections==0 && ...
    finalStats.ControlFailures==0 && all([controls.send_result]==1) && ...
    all([controls.ackable]==0) && scheduler.Now==config.stop_s;
summary=struct('Schema','csr-tranche27-matlab-controller-case-v1', ...
    'CaseId',char(config.id),'DiagnosticCompleted',true, ...
    'StructuralPassed',structuralPassed,'ControlCount',numel(controls), ...
    'CheckpointCount',numel(snapshots),'StopSeconds',config.stop_s, ...
    'ElapsedSeconds',toc(started),'PrivateControllerStateAvailable',false, ...
    'FinalStatistics',finalStats,'AcceptedLowerLayerControlCount',numel(allControls), ...
    'Transport','Logical NWK controls accepted into a sink; no automatic responses, ACKs or PHY', ...
    'ProductionChanges',false,'RandomnessUsed',false,'CampusExecuted',false);
states=struct('Schema','csr-tranche27-matlab-controller-states-v1', ...
    'CaseId',char(config.id),'PrivateControllerStateAvailable',false, ...
    'UnavailableControllerFields',{{'ScanKnown','ScanRequested','ScanWaiting','ScanGeneration', ...
        'NeighborDiscoveryState','WatchdogDeadline'}}, ...
    'ObservationMethod',['Public Layer.applicationState, stats, routesSnapshot and neighborsSnapshot. ' ...
        'logical_destination_birth_order_fixture records supplied peer creation order; ' ...
        'it is not a read of the private route-order or controller worklist.'], ...
    'Snapshots',snapshots);
if ~isempty(outputDirectory)
    if ~isfolder(outputDirectory), mkdir(outputDirectory); end
    writetable(struct2table(controls),fullfile(outputDirectory,'controls.csv'));
    csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'states.json'),states);
    csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'summary.json'),summary);
    csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'lower-layer-controls.json'),allControls);
end
report=summary;
report.Controls=controls;
report.States=states;

    function addUsablePeer(peer)
        % The two public calls establish one logical peer at the same time.
        % observe activates it with admission disabled. The self UPDATE then
        % gives its direct route capability 1. For a late peer, observe may
        % queue START before that UPDATE: discoveryRelay permits its sole
        % direct route even while capability is 0. The UPDATE precedes the
        % same-time sink callback. No atomic private-state match is claimed.
        if ismember(peer,logicalBirthOrder)
            error('csr:t27:Peer','The fixture attempted to create a peer twice.');
        end
        logicalBirthOrder=[peer logicalBirthOrder];
        layer.observe(peer,struct());
        record=struct('Operation','UPDATE','NodeId',peer,'Capability',1, ...
            'HopCount',0,'Cost',0,'Path',[]);
        sections=csr.nwk.RoutingCodec.sections( ...
            csr.nwk.RoutingCodec.encodeRecords({record}),1);
        for sectionIndex=1:numel(sections)
            layer.receiveControl(struct('Type','ROUTING', ...
                'Payload',struct('Bytes',sections{sectionIndex})),peer);
        end
        routes=layer.routesSnapshot();
        selected=routes([routes.DestinationId]==peer & [routes.NextHop]==peer);
        if numel(selected)~=1 || selected.Capability~=1 || ...
                ~layer.routeAvailable(struct('SourceId',1,'DestinationId',peer,'Traversal',1))
            error('csr:t27:Peer','A prescribed capable direct peer was not usable.');
        end
    end

    function accepted=captureControl(control,peers,sendOptions)
        accepted=true;
        allControls(end+1,1)=struct('time_s',scheduler.Now,'kind',control.Type, ...
            'peers',reshape(peers,1,[]),'ackable',logical(sendOptions.AckRequired));
        if ~any(strcmp(control.Type,{'SNMP_START','SNMP_DONE'})), return; end
        if numel(peers)~=1
            error('csr:t27:Control','A discovery management command must have one next hop.');
        end
        row=emptyControl();
        row.case_id=char(config.id); row.order=numel(controls)+1;
        row.time_s=scheduler.Now; row.command=erase(control.Type,'SNMP_');
        row.source=control.Payload.SourceId;
        row.final_destination=control.Payload.DestinationId;
        row.next_hop=peers(1); row.ackable=double(sendOptions.AckRequired);
        row.send_result=double(accepted);
        if isfield(control.Payload,'Nodes')
            row.advertised_nodes=jsonencode(reshape(control.Payload.Nodes,1,[]));
        end
        controls(end+1,1)=row;
    end

    function captureSnapshot()
        state=layer.applicationState(1);
        stats=layer.stats();
        routes=layer.routesSnapshot();
        neighbors=layer.neighborsSnapshot();
        row=emptySnapshot();
        row.event_order=numel(snapshots)+1; row.time_s=scheduler.Now;
        row.local_discovery_active=logical(state.DiscoveryActive);
        row.topology_known=logical(state.TopologyKnown);
        row.gateway_available=~isempty(state.GatewayId);
        row.local_is_gateway=layer.Capability==2;
        if ~isempty(neighbors)
            active=[neighbors.Active] & ~[neighbors.Stale];
            row.active_peers=reshape([neighbors(active).Id],1,[]);
        end
        row.route_storage_order=reshape([routes.DestinationId],1,[]);
        row.logical_destination_birth_order_fixture=logicalBirthOrder;
        row.application_state=state; row.stats=stats;
        row.routes=routes; row.neighbors=neighbors;
        snapshots(end+1,1)=row;
    end
end

function row=emptyControl()
row=struct('case_id','','order',0,'time_s',0,'command','', ...
    'source',0,'final_destination',0,'next_hop',0, ...
    'ackable',0,'send_result',0,'advertised_nodes','[]');
end

function row=emptySnapshot()
row=struct('event_order',0,'time_s',0,'event','checkpoint', ...
    'local_discovery_active',false,'topology_known',false, ...
    'gateway_available',false,'local_is_gateway',true, ...
    'active_peers',[],'route_storage_order',[], ...
    'logical_destination_birth_order_fixture',[], ...
    'application_state',struct(),'stats',struct(),'routes',struct([]),'neighbors',struct([]));
end

function validateCase(config)
required={'id','initial_peers','done_time_s','done_source','late_peer_time_s', ...
    'late_peer','local_duration_s','stop_s','checkpoints_s'};
if ~isstruct(config) || ~isscalar(config) || ~all(isfield(config,required)) || ...
        ~any(strcmp(config.id,{'C0','C1','C2','C3_match','C3_timeout'}))
    error('csr:t27:Case','A named frozen T27 case is required.');
end
peers=reshape(config.initial_peers,1,[]);
if isempty(peers) || any(~ismember(peers,[3 4 5])) || numel(unique(peers))~=numel(peers)
    error('csr:t27:Case','Initial peers must be distinct members of the bounded fixture.');
end
validateattributes(config.local_duration_s,{'numeric'},{'scalar','positive','finite'});
validateattributes(config.stop_s,{'numeric'},{'scalar','positive','finite'});
validateattributes(config.checkpoints_s,{'numeric'}, ...
    {'vector','nonempty','positive','finite','<=',config.stop_s});
if any(diff(reshape(config.checkpoints_s,1,[]))<=0) || ...
        config.local_duration_s>=config.stop_s || config.stop_s>62 || ...
        config.checkpoints_s(end)~=config.stop_s || ...
        xor(isempty(config.done_time_s),isempty(config.done_source)) || ...
        xor(isempty(config.late_peer_time_s),isempty(config.late_peer))
    error('csr:t27:Case','The bounded schedule or paired input fields are invalid.');
end
if ~isempty(config.done_time_s)
    validateattributes(config.done_time_s,{'numeric'}, ...
        {'scalar','finite','>',config.local_duration_s,'<',config.stop_s});
    if ~ismember(config.done_source,peers)
        error('csr:t27:Case','DONE must come from a prescribed initial peer.');
    end
end
if ~isempty(config.late_peer_time_s)
    validateattributes(config.late_peer_time_s,{'numeric'}, ...
        {'scalar','finite','>',config.local_duration_s,'<',config.stop_s});
    if ~isscalar(config.late_peer) || ~ismember(config.late_peer,[3 4 5]) || ...
            ismember(config.late_peer,peers)
        error('csr:t27:Case','The late peer must be new and within the bounded fixture.');
    end
end
end
