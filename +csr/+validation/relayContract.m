function report = relayContract(outputDirectory)
%RELAYCONTRACT Real NWK/HOP/MAC relay service with controlled raw draws.
% The finite 4 -> 5 -> 1 fixture preconditions admitted neighbors and routes.
% A finite offer driver consults real NWK NSDP state and the existing
% application limit; real NWK queue/custody,
% HOP DATA/ACK service and MAC contention run through success-only addressed
% transport. It does not validate discovery, RF reception or campus parity.
if nargin<1, outputDirectory = ''; end
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
inputDirectory = fullfile(root,'scenarios','relay');
referenceDirectory = fullfile(root,'evidence','tranche-12-relay-reference');
plan = jsondecode(fileread(fullfile(inputDirectory,'plan.json')));
cases = readtable(fullfile(inputDirectory,'cases.csv'),'TextType','string', ...
    'VariableNamingRule','preserve');
tape = readtable(fullfile(inputDirectory,'draws.csv'),'TextType','string', ...
    'VariableNamingRule','preserve');
if ~strcmp(plan.schema,'csr-tranche12-relay-input-v1') || ...
        ~isequal(string(cases.('case')),string(plan.cases(:)))
    error('csr:validation:RelayPlan','Relay cases differ from the pinned input plan.');
end
events = table(); draws = table(); usage = table(); checks = table();
caseResults = repmat(struct('Case','','Completed',false,'ErrorIdentifier','', ...
    'ErrorMessage','','ErrorStack',struct('file',{},'name',{},'line',{}), ...
    'Admitted',[],'Delivered',[],'Released',[],'RelayCustodyAccepted',0, ...
    'PendingControls',[],'FinalHopPending',[],'FinalDackHolds',[], ...
    'FinalResends',[],'Drops',0),0,1);
for k=1:height(cases)
    [caseEvents,caseDraws,caseUsage,caseChecks,result] = runCase(cases(k,:));
    events = [events;caseEvents]; draws = [draws;caseDraws]; %#ok<AGROW>
    usage = [usage;caseUsage]; checks = [checks;caseChecks]; %#ok<AGROW>
    caseResults(end+1,1) = result; %#ok<AGROW>
end
if ~isequal(events.Properties.VariableNames,cellstr(string(plan.events_schema(:)))') || ...
        ~isequal(draws.Properties.VariableNames,cellstr(string(plan.draws_output_schema(:)))')
    error('csr:validation:RelaySchema','Relay observations differ from the pinned schema.');
end
eventComparison = compareTable(events,fullfile(referenceDirectory,'events.csv'));
drawComparison = compareTable(draws,fullfile(referenceDirectory,'draws.csv'));
usageComparison = compareTable(usage,fullfile(referenceDirectory,'usage.csv'));
unmatched = eventComparison.UnmatchedCount+drawComparison.UnmatchedCount+usageComparison.UnmatchedCount;
completed = all([caseResults.Completed]); failed = sum(~logical(checks.pass));
report = struct('Schema','csr-tranche12-relay-contract-v1', ...
    'DiagnosticCompleted',completed,'MatchesNative',unmatched==0, ...
    'Passed',completed && failed==0,'CaseCount',height(cases), ...
    'EventCount',height(events),'DrawCount',height(draws), ...
    'CheckpointCount',height(checks),'FailedCount',failed,'UnmatchedCount',unmatched, ...
    'EventsCompared',eventComparison.ComparedRows,'DrawsCompared',drawComparison.ComparedRows, ...
    'UsageCompared',usageComparison.ComparedRows,'ComparedEntireTrajectories',true, ...
    'InputBindings',bindings(inputDirectory,{'plan.json','cases.csv','draws.csv'},'scenarios/relay/'), ...
    'ReferenceBindings',bindings(referenceDirectory,{'events.csv','draws.csv','usage.csv'}, ...
        'evidence/tranche-12-relay-reference/'), ...
    'Scope',plan.scope,'Runtime',version,'CaseResults',caseResults, ...
    'EventComparison',eventComparison,'DrawComparison',drawComparison, ...
    'UsageComparison',usageComparison,'TimeToleranceNanoseconds',1);
if ~isempty(outputDirectory)
    if ~isfolder(outputDirectory), mkdir(outputDirectory); end
    writetable(events,fullfile(outputDirectory,'events.csv'));
    writetable(draws,fullfile(outputDirectory,'draws.csv'));
    writetable(usage,fullfile(outputDirectory,'usage.csv'));
    writetable(checks,fullfile(outputDirectory,'check.csv'));
    csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'summary.json'),report);
end
report.Events = events; report.Draws = draws;
report.Usage = usage; report.Checkpoints = checks;

    function [outEvents,outDraws,outUsage,outChecks,result] = runCase(entry)
        name = char(entry.('case'));
        scheduler = csr.sim.EventScheduler(200000);
        owner = csr.validation.ReplayStreams(tape(string(tape.('case'))==name,:), ...
            @()scheduler.Now,name);
        macs = cell(1,max(plan.nodes)); hops = cell(size(macs));
        networks = cell(size(macs));
        admitted = zeros(size(macs)); delivered = zeros(size(macs));
        releases = zeros(size(macs)); blocked = zeros(size(macs));
        releaseFailures = 0; custodyAccepted = 0; drops = 0;
        pendingControls = zeros(size(macs));
        finalPending = zeros(size(macs)); finalHolds = zeros(size(macs));
        finalResends = zeros(size(macs));
        requested = zeros(size(macs));
        requested(4) = entry.apps4; requested(5) = entry.apps5;
        eventRows = repmat(emptyEvent(),0,1);
        checkRows = repmat(struct('case','','checkpoint','','node',0, ...
            'actual',0,'expected',0,'pass',false),0,1);
        complete = false; errorId = ''; errorMessage = '';
        errorStack = struct('file',{},'name',{},'line',{});
        try
            options = csr.mac.Layer.defaults();
            options.DutyCycleEnabled = logical(plan.duty_cycle);
            options.ActiveNodes = plan.active_nodes;
            options.ReportedActiveNodes = plan.reported_active_nodes;
            options.SlotProfile = plan.slot_profile; options.SlotReduction = plan.slot_reduction;
            options.SlotSeconds = plan.slot_seconds; options.HoldoffSeconds = plan.holdoff_seconds;
            config = fixtureConfig(plan);
            for node=reshape(plan.nodes,1,[])
                macs{node} = csr.mac.Layer(node,scheduler,owner,options, ...
                    struct('Transmit',@(f,d)transmit(node,f,d), ...
                    'Sent',@(f)sent(node,f),'Event',@(n,f,d)macEvent(node,n,f,d)));
                hopCallbacks = struct('EnqueueMac',@(f)enqueue(node,f), ...
                    'CancelMac',@(p,s)cancel(node,p,s), ...
                    'Deliver',@(a,p)receiveData(node,a,p), ...
                    'NsdpRelease',@(a,r)release(node,a,r), ...
                    'Wake',@()networkWake(node), ...
                    'NsdpCount',@(a)networkNsdpCount(node,a), ...
                    'RouteAvailable',@(a)networkRouteAvailable(node,a), ...
                    'Terminal',@(a,s,r)terminal(node,a,s,r));
                hops{node} = csr.hop.Layer(node,scheduler,owner,struct(),hopCallbacks);
                networkCallbacks = struct('CanSendData',@(p)canSendData(node,p), ...
                    'SendData',@(a,p,o)sendData(node,a,p,o), ...
                    'CanSendControl',@(~)false, ...
                    'Delivered',@(a,p)deliver(node,a,p), ...
                    'CustodyAccepted',@(a,p)custody(node,a,p), ...
                    'Dropped',@(a,r)dropped(node,a,r));
                networks{node} = csr.nwk.Layer(node,scheduler,owner,config,networkCallbacks);
            end
            % Public receive/observe APIs initialize only the known chain.
            % Admission/discovery and automatic routing traffic are excluded.
            for node=reshape(plan.nodes,1,[])
                macs{node}.start();
                if node==1, peers = 5; elseif node==4, peers = 5; else, peers = [1 4]; end
                for peer=peers
                    heard = struct('SourceId',peer, ...
                        'ReservationSlot',plan.initial_neighbor_reservation);
                    macs{node}.receive(heard,struct('Success',true));
                    macs{node}.receive(heard,struct('Success',true));
                    networks{node}.observe(peer,struct('Success',true,'PathlossDb',plan.pathloss_db));
                end
            end
            update = struct('Operation','UPDATE','NodeId',1,'Capability',2, ...
                'HopCount',1,'Cost',1,'Path',1);
            bytes = csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords({update}),1);
            for section=1:numel(bytes)
                networks{4}.receiveControl(struct('Type','ROUTING', ...
                    'Payload',struct('Bytes',bytes{section})),5);
            end
            % Settle zero-time route bookkeeping before application offers;
            % blocked control traffic consumes neither raw draws nor airtime.
            scheduler.run(0);
            pollStartNs = round(plan.offered_start_seconds*1e9);
            pollPeriodNs = round(plan.offered_poll_seconds*1e9);
            pollStopNs = round(plan.offered_poll_stop_exclusive_seconds*1e9);
            lastPoll = ceil((pollStopNs-pollStartNs)/pollPeriodNs)-1;
            for tick=0:lastPoll
                when = (pollStartNs+tick*pollPeriodNs)/1e9;
                if when<entry.duration_seconds, scheduler.scheduleAt(when,@poll); end
            end
            scheduler.scheduleAt(plan.checkpoint_seconds,@checkpointSnapshot);
            scheduler.run(entry.duration_seconds);
            for node=reshape(plan.nodes,1,[])
                observe('final',node,nextHop(node),struct());
            end
            complete = true;
        catch problem
            errorId = problem.identifier; errorMessage = problem.message;
            errorStack = problem.stack;
        end
        outEvents = struct2table(eventRows); outDraws = owner.draws(); outUsage = owner.usage();
        for source=reshape(plan.sources,1,[])
            checkpoint('admitted',source,admitted(source),requested(source));
            checkpoint('delivered',source,delivered(source),requested(source));
            checkpoint('nsdp_blocked_seen',source,double(blocked(source)>0),double(requested(source)>16));
        end
        for node=reshape(plan.nodes,1,[])
            pending = -1; waiting = -1; custodyCount = -1; pair4 = -1; pair5 = -1;
            holdCount = -1; resendCount = -1;
            if ~isempty(hops{node})
                hopState = hops{node}.stats(); pending = hopState.PendingData;
                holdCount = hopState.DackHoldCount; resendCount = hopState.ResendQueueDepth;
            end
            finalPending(node) = pending; finalHolds(node) = holdCount; finalResends(node) = resendCount;
            if ~isempty(networks{node})
                state = networks{node}.stats(); waiting = state.WaitingForHop;
                custodyCount = state.PendingCustody; pendingControls(node) = state.PendingControlMessages;
                pair4 = networks{node}.nsdpCount(struct('SourceId',4,'DestinationId',1));
                pair5 = networks{node}.nsdpCount(struct('SourceId',5,'DestinationId',1));
            end
            checkpoint('hop_pending',node,pending,0);
            checkpoint('dack_holds',node,holdCount,0);
            checkpoint('resend_queue',node,resendCount,0);
            checkpoint('nwk_waiting',node,waiting,0);
            checkpoint('nwk_custody',node,custodyCount,0);
            checkpoint('nsdp4',node,pair4,0); checkpoint('nsdp5',node,pair5,0);
            targetRelease = 0;
            if node==4, targetRelease = requested(4);
            elseif node==5, targetRelease = requested(4)+requested(5); end
            checkpoint('released',node,releases(node),targetRelease);
        end
        checkpoint('relay_custody',5,custodyAccepted,requested(4));
        checkpoint('drops',0,drops,0);
        checkpoint('release_order_failures',0,releaseFailures,0);
        checkpoint('draw_resolution_failures',0, ...
            sum(string(outDraws.purpose)=="unresolved" | outDraws.resolved<0),0);
        checkpoint('custody_conservation_failures',0, ...
            sum(outEvents.nwk_custody~=outEvents.nsdp4+outEvents.nsdp5),0);
        data = string(outEvents.event)=="tx_start" & outEvents.app_source>0;
        checkpoint('direct_source_gateway_transmissions',4, ...
            sum(data & outEvents.node==4 & outEvents.peer==1),0);
        checkpoint('source4_wrong_next_hop',4, ...
            sum(data & outEvents.node==4 & outEvents.peer~=5),0);
        checkpoint('relay_wrong_next_hop',5, ...
            sum(data & outEvents.node==5 & outEvents.peer~=1),0);
        feedback = string(outEvents.event)=="tx_start" & outEvents.app_source==0;
        checkpoint('relay_ack_seen',5,double(any(feedback & outEvents.node==5 & outEvents.peer==4)), ...
            double(requested(4)>0));
        checkpoint('gateway_ack_seen',1,double(any(feedback & outEvents.node==1 & outEvents.peer==5)), ...
            double(sum(requested)>0));
        checkpoint('case_completed',0,double(complete),1);
        outChecks = struct2table(checkRows);
        result = struct('Case',name,'Completed',complete,'ErrorIdentifier',errorId, ...
            'ErrorMessage',errorMessage,'ErrorStack',errorStack, ...
            'Admitted',admitted,'Delivered',delivered,'Released',releases, ...
            'RelayCustodyAccepted',custodyAccepted,'PendingControls',pendingControls, ...
            'FinalHopPending',finalPending,'FinalDackHolds',finalHolds, ...
            'FinalResends',finalResends,'Drops',drops);

        function peer = nextHop(node)
            if node==4, peer = 5; elseif node==5, peer = 1; else, peer = 0; end
        end
        function checkpointSnapshot()
            for endpoint=reshape(plan.nodes,1,[])
                observe('checkpoint',endpoint,nextHop(endpoint),struct());
            end
        end
        function poll()
            for source=reshape(plan.sources,1,[]), offer(source); end
        end
        function offer(node)
            if admitted(node)>=requested(node), return; end
            app = struct('Id',uint64(admitted(node)+1),'SourceId',node, ...
                'DestinationId',plan.gateway,'GeneratedSeconds',scheduler.Now, ...
                'ApplicationPayloadBytes',plan.application_payload_bytes,'Dscp',plan.dscp);
            metadata = struct('App',app); observe('offer',node,nextHop(node),metadata);
            state = networks{node}.applicationState(plan.gateway);
            if state.NsdpLimit~=plan.application_nsdp_limit
                error('csr:validation:RelayAdmissionLimit','NWK state differs from the pinned NSDP limit.');
            end
            if state.NsdpCount>=state.NsdpLimit
                blocked(node) = blocked(node)+1;
                observe('blocked',node,nextHop(node),metadata); return
            end
            if ~networks{node}.sendApplication(app)
                error('csr:validation:RelayAdmission','The bounded application was rejected by the real NWK queue.');
            end
            admitted(node) = admitted(node)+1;
            observe('admit',node,nextHop(node),metadata);
        end
        % Anonymous functions capture cell-array values when registered.
        % HOP is constructed before NWK, so look up the completed layer in
        % this shared nested workspace when the callback actually runs.
        function count = networkNsdpCount(node,app)
            count = networks{node}.nsdpCount(app);
        end
        function available = networkRouteAvailable(node,app)
            available = networks{node}.routeAvailable(app);
        end
        function accepted = canSendData(node,peer)
            accepted = hops{node}.canSend(peer);
        end
        function accepted = sendData(node,app,peer,options)
            accepted = hops{node}.send(app,peer,options);
        end
        function accepted = enqueue(node,frame)
            % HOP leaves ACK power for the radio adapter; fill only an empty
            % value, preserving any power supplied by the production frame.
            if isempty(frame.TxPowerDbm), frame.TxPowerDbm = plan.power_dbm; end
            accepted = macs{node}.enqueue(frame);
        end
        function cancel(node,peer,sequence), macs{node}.cancel(peer,sequence); end
        function sent(node,frame), hops{node}.notifySent(frame); end
        function networkWake(node), networks{node}.wake(); end
        function terminal(node,app,success,reason), networks{node}.terminal(app,success,reason); end
        function macEvent(node,event,~,details)
            if strcmp(event,'mac_prepare'), owner.resolve(node,'prepare',details.ReservationSlot); end
        end
        function transmit(node,envelope,duration)
            owner.resolve(node,'advertise',envelope.ReservationSlot);
            for segment=1:numel(envelope.Segments)
                frame = envelope.Segments{segment};
                frame.ReservationSlot = envelope.ReservationSlot;
                frame.ActiveNodes = envelope.ActiveNodes;
                observe('tx_start',node,frame.DestinationId,frame);
            end
            scheduler.scheduleAt(scheduler.Now+duration+plan.propagation_seconds, ...
                @()ingress(envelope));
        end
        function ingress(envelope)
            heard = false(size(macs));
            for segment=1:numel(envelope.Segments)
                frame = envelope.Segments{segment};
                frame.ReservationSlot = envelope.ReservationSlot;
                frame.ActiveNodes = envelope.ActiveNodes;
                node = frame.DestinationId; peer = frame.SourceId;
                if ~any((node==1 && peer==5) || (node==4 && peer==5) || ...
                        (node==5 && any(peer==[1 4])))
                    error('csr:validation:RelayTopology','Frame left the controlled 4-5-1 chain.');
                end
                observe('ingress_before',node,peer,frame);
                if ~heard(node)
                    networks{node}.observeRadio(peer,struct('Success',true,'PathlossDb',plan.pathloss_db));
                    macs{node}.receive(frame,struct('Success',true)); heard(node) = true;
                end
                hops{node}.receive(frame,struct('Success',true));
                observe('ingress_after',node,peer,frame);
            end
        end
        function accepted = receiveData(node,app,peer)
            accepted = networks{node}.receiveData(app,peer);
        end
        function accepted = deliver(node,app,peer)
            accepted = node==plan.gateway && app.DestinationId==node;
            if accepted
                delivered(app.SourceId) = delivered(app.SourceId)+1;
                observe('deliver',node,peer,struct('App',app));
            end
        end
        function custody(node,app,previousHop)
            if node~=5 || app.SourceId~=4 || previousHop~=4
                error('csr:validation:RelayCustody','Unexpected relay custody transition.');
            end
            custodyAccepted = custodyAccepted+1;
        end
        function dropped(~,~,~), drops = drops+1; end
        function release(node,app,reason)
            networks{node}.releaseFromHop(app,reason);
            releases(node) = releases(node)+1;
            state = hops{node}.state(nextHop(node));
            if strcmp(reason,'ack') && (state.PendingData~=state.NeighborOutstanding || ...
                    state.ResendQueueDepth<=state.PendingData-state.DackHoldCount)
                releaseFailures = releaseFailures+1;
            end
            metadata = struct('App',struct('SourceId',app.SourceId,'Id',uint64(0)));
            observe('release',node,nextHop(node),metadata);
        end
        function observe(event,node,peer,frame)
            row = emptyEvent(); row.('case') = name; row.order = numel(eventRows)+1;
            row.time_ns = round(scheduler.Now*1e9); row.event = event;
            row.node = node; row.peer = peer;
            if isfield(frame,'App') && isfield(frame.App,'SourceId')
                row.app_source = frame.App.SourceId; row.app_id = frame.App.Id;
            end
            if isfield(frame,'Sequence'), row.hop_seq = double(frame.Sequence); end
            if isfield(frame,'AckBitmap'), row.ack_bits = frame.AckBitmap; end
            if isfield(frame,'DackBitmap'), row.dack_bits = frame.DackBitmap; end
            if isfield(frame,'RateKeyKbps'), row.rate_kbps = frame.RateKeyKbps; end
            if isfield(frame,'TxPowerDbm') && ~isempty(frame.TxPowerDbm), row.power_dbm = frame.TxPowerDbm; end
            mac = macs{node}; row.mac_state = find(strcmp(mac.State,{'Idle','Search','Track','Tx'}))-1;
            row.ack_queue = mac.AckQueueCount; row.data_queue = mac.DataQueueCount;
            row.prep = double(mac.PreparationActive); row.counter = mac.ReservationCounter;
            row.opportunity = mac.LastOpportunitySlot; row.advertised = mac.LastAdvertisedReservation;
            state = hops{node}.state(peer); row.hop_pending = state.PendingData;
            if peer~=0
                row.neighbor_outstanding = state.NeighborOutstanding; row.neighbor_threshold = state.NeighborThreshold;
            end
            row.resend_queue = state.ResendQueueDepth; row.dack_holds = state.DackHoldCount;
            row.admitted = admitted(node);
            network = networks{node}.stats(); row.nwk_waiting = network.WaitingForHop;
            row.nwk_custody = network.PendingCustody;
            row.nsdp4 = networks{node}.nsdpCount(struct('SourceId',4,'DestinationId',1));
            row.nsdp5 = networks{node}.nsdpCount(struct('SourceId',5,'DestinationId',1));
            eventRows(end+1,1) = row;
        end
        function checkpoint(point,node,actual,target)
            checkRows(end+1,1) = struct('case',name,'checkpoint',point, ...
                'node',node,'actual',double(actual),'expected',double(target), ...
                'pass',isfinite(double(actual)) && actual==target);
        end
    end
end

function config = fixtureConfig(plan)
nwk = csr.nwk.defaults(); nwk.StartupMode = 'none';
nwk.Neighbor.AdmissionEnabled = false; nwk.Neighbor.FreshnessEnabled = false;
nwk.AdaptiveLinkControl = false; nwk.ControlRetrySeconds = plan.matlab_control_retry_seconds;
nwk.SnapshotWatchdogSeconds = plan.matlab_snapshot_watchdog_seconds; nwk.RouteRequestSeconds = 1000;
nwk.Routing.LocalInfo.MinSpeedKbps = plan.rate_kbps;
nwk.Routing.LocalInfo.MaxSpeedKbps = plan.rate_kbps;
nwk.Routing.LocalInfo.MinPowerDbmX10 = plan.power_dbm*10;
nwk.Routing.LocalInfo.MaxPowerDbmX10 = plan.power_dbm*10;
node = struct('Id',0,'Capability',1,'TransitForwardingEnabled',true);
nodes = repmat(node,1,numel(plan.nodes));
for k=1:numel(nodes)
    nodes(k).Id = plan.nodes(k);
    if nodes(k).Id==plan.gateway, nodes(k).Capability = 2; end
end
config = struct('Nwk',nwk,'Nodes',nodes,'Radio', ...
    struct('RateKeyKbps',plan.rate_kbps,'TxPowerDbm',plan.power_dbm, ...
    'EnvelopeProfile',plan.wire_profile,'Preamble','long'));
end

function row = emptyEvent()
row = struct('case','','order',0,'time_ns',0,'event','','node',0,'peer',0, ...
    'app_source',0,'app_id',uint64(0),'hop_seq',0,'ack_bits',uint64(0), ...
    'dack_bits',uint64(0),'mac_state',0,'ack_queue',0,'data_queue',0,'prep',0, ...
    'counter',0,'opportunity',0,'advertised',0,'hop_pending',0, ...
    'neighbor_outstanding',0,'neighbor_threshold',0,'resend_queue',0, ...
    'admitted',0,'rate_kbps',0,'power_dbm',0,'nwk_waiting',0,'nwk_custody',0, ...
    'nsdp4',0,'nsdp5',0,'dack_holds',0);
end

function result = compareTable(actual,path)
result = struct('ReferencePresent',isfile(path),'SchemaMatches',false, ...
    'ActualRows',height(actual),'ReferenceRows',0,'ComparedRows',height(actual), ...
    'UnmatchedCount',max(1,height(actual)),'FirstUnmatchedRow',0, ...
    'MaximumTimeDifferenceNanoseconds',0);
if ~isfile(path), return; end
expected = readtable(path,'TextType','string','VariableNamingRule','preserve');
result.ReferenceRows = height(expected); result.ComparedRows = max(height(actual),height(expected));
result.SchemaMatches = isequal(actual.Properties.VariableNames,expected.Properties.VariableNames);
if ~result.SchemaMatches, result.UnmatchedCount = max(1,result.ComparedRows); return; end
overlap = min(height(actual),height(expected)); matched = true(overlap,1);
for k=1:width(actual)
    name = actual.Properties.VariableNames{k}; left = actual.(name)(1:overlap); right = expected.(name)(1:overlap);
    if strcmp(name,'time_ns')
        delta = abs(double(left)-double(right)); matched = matched & isfinite(delta) & delta<=1;
        if ~isempty(delta), result.MaximumTimeDifferenceNanoseconds = max(delta); end
    elseif isnumeric(left) || islogical(left)
        % A mixed next-hop pair sends at most 40 DATA applications. Its
        % IDs and 40-bit cumulative maps are exactly representable as
        % doubles. Only time receives a one-nanosecond tolerance.
        matched = matched & double(left)==double(right);
    else
        matched = matched & string(left)==string(right);
    end
end
result.UnmatchedCount = sum(~matched)+abs(height(actual)-height(expected));
first = find(~matched,1);
if isempty(first) && height(actual)~=height(expected), first = overlap+1; end
if ~isempty(first), result.FirstUnmatchedRow = first; end
end

function output = bindings(directory,names,prefix)
output = repmat(struct('Path','','SHA256',''),0,1);
for k=1:numel(names)
    path = fullfile(directory,names{k}); hash = '';
    if isfile(path), hash = csr.validation.Artifacts.sha256(path); end
    output(end+1,1) = struct('Path',[prefix names{k}],'SHA256',hash); %#ok<AGROW>
end
end
