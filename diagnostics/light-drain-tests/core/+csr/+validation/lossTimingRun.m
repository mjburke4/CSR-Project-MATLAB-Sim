function report = lossTimingRun(outputDirectory,mode)
%LOSSTIMINGRUN T13 controlled-loss fixture with an explicit local timing mode.
% Mechanically derived from the accepted lossContract; production classes,
% all inputs, initial conditions, loss decisions and checks remain unchanged.
% The finite 4 -> 5 -> 1 fixture preconditions admitted neighbors and routes.
% A finite offer driver consults real NWK NSDP state and the existing
% application limit; real NWK queue/custody,
% HOP DATA/ACK service and MAC contention run through controlled addressed
% DATA/ACK losses. It does not validate discovery, RF reception or campus parity.
if nargin<1, outputDirectory = ''; end
if nargin<2, mode = 'continuous'; end
csr.validation.transportArrival(0,0,0,mode);
mode = char(mode);
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
inputDirectory = fullfile(root,'scenarios','loss');
referenceDirectory = fullfile(root,'evidence','tranche-13-loss-reference');
plan = jsondecode(fileread(fullfile(inputDirectory,'plan.json')));
cases = readtable(fullfile(inputDirectory,'cases.csv'),'TextType','string', ...
    'VariableNamingRule','preserve');
offers = readtable(fullfile(inputDirectory,'offers.csv'),'TextType','string', ...
    'VariableNamingRule','preserve');
tape = readtable(fullfile(inputDirectory,'draws.csv'),'TextType','string', ...
    'VariableNamingRule','preserve');
if ~strcmp(plan.schema,'csr-tranche13-loss-input-v1') || ...
        ~isequal(string(cases.('case')),string(plan.cases(:)))
    error('csr:validation:LossPlan','Relay cases differ from the pinned input plan.');
end
events = records([],emptyEvent()); draws = records([],emptyDraw());
usage = records([],emptyUsage()); checks = records([],emptyCheck());
transport = records([],emptyTransport()); terminals = records([],emptyTerminal());
timing = records([],emptyTiming()); precision = records([],emptyPrecision());
caseResults = repmat(emptyResult(),0,1);
for k=1:height(cases)
    fprintf('Loss timing %s %d/%d: %s (%g simulated seconds).\n', ...
        mode,k,height(cases),char(cases.('case')(k)),cases.duration_seconds(k));
    [caseEvents,caseDraws,caseUsage,caseChecks,caseTransport,caseTerminals,caseTiming,casePrecision,result] = runCase(cases(k,:));
    if ~isempty(outputDirectory)
        directory = fullfile(outputDirectory,sprintf('c%d',k));
        saveTables(directory,caseEvents,caseDraws,caseUsage,caseChecks, ...
            caseTransport,caseTerminals,caseTiming,casePrecision);
        csr.validation.Artifacts.writeJson(fullfile(directory,'result.json'),result);
    end
    events = [events;caseEvents]; draws = [draws;caseDraws]; %#ok<AGROW>
    usage = [usage;caseUsage]; checks = [checks;caseChecks]; %#ok<AGROW>
    transport = [transport;caseTransport]; terminals = [terminals;caseTerminals]; %#ok<AGROW>
    timing = [timing;caseTiming]; precision = [precision;casePrecision]; %#ok<AGROW>
    caseResults(end+1,1) = result; %#ok<AGROW>
end
if ~isequal(events.Properties.VariableNames,cellstr(string(plan.events_schema(:)))') || ...
        ~isequal(draws.Properties.VariableNames,cellstr(string(plan.draws_output_schema(:)))')
    error('csr:validation:LossSchema','Relay observations differ from the pinned schema.');
end
if ~isequal(transport.Properties.VariableNames,cellstr(string(plan.transport_schema(:)))') || ...
        ~isequal(terminals.Properties.VariableNames,cellstr(string(plan.terminal_schema(:)))')
    error('csr:validation:LossSchema','Transport observations differ from pinned schema.');
end
eventComparison = compareTable(events,fullfile(referenceDirectory,'events.csv'));
drawComparison = compareTable(draws,fullfile(referenceDirectory,'draws.csv'));
usageComparison = compareTable(usage,fullfile(referenceDirectory,'usage.csv'));
transportComparison = compareTable(transport,fullfile(referenceDirectory,'transport.csv'));
terminalComparison = compareTable(terminals,fullfile(referenceDirectory,'terminal.csv'));
unmatched = eventComparison.UnmatchedCount+drawComparison.UnmatchedCount+usageComparison.UnmatchedCount+ ...
    transportComparison.UnmatchedCount+terminalComparison.UnmatchedCount;
completed = all([caseResults.Completed]); failed = sum(~logical(checks.pass));
report = struct('Schema','csr-tranche13-loss-contract-v1', ...
    'TimingMode',mode,'TimingCount',height(timing),'PrecisionCount',height(precision), ...
    'TransportPolicy','Only addressed aggregate arrival changes; global clock and startup phase unchanged', ...
    'DiagnosticCompleted',completed,'MatchesNative',unmatched==0, ...
    'Passed',completed && failed==0,'CaseCount',height(cases), ...
    'EventCount',height(events),'DrawCount',height(draws), ...
    'TransportCount',height(transport),'TerminalCount',height(terminals), ...
    'CheckpointCount',height(checks),'FailedCount',failed,'UnmatchedCount',unmatched, ...
    'EventsCompared',eventComparison.ComparedRows,'DrawsCompared',drawComparison.ComparedRows, ...
    'UsageCompared',usageComparison.ComparedRows,'ComparedEntireTrajectories',true, ...
    'InputBindings',bindings(inputDirectory,{'plan.json','cases.csv','offers.csv','draws.csv'},'scenarios/loss/'), ...
    'ReferenceBindings',bindings(referenceDirectory,{'events.csv','draws.csv','usage.csv','transport.csv','terminal.csv'}, ...
        'evidence/tranche-13-loss-reference/'), ...
    'Scope',plan.scope,'Runtime',version,'CaseResults',caseResults, ...
    'EventComparison',eventComparison,'DrawComparison',drawComparison, ...
    'UsageComparison',usageComparison,'TransportComparison',transportComparison, ...
    'TerminalComparison',terminalComparison,'TimeToleranceNanoseconds',1, ...
    'IntegerComparison','app_id/ack_bits/dack_bits compared as exact uint64 decimal text');
if ~isempty(outputDirectory)
    saveTables(outputDirectory,events,draws,usage,checks,transport,terminals,timing,precision);
    csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'summary.json'),report);
end
report.Events = events; report.Draws = draws;
report.Usage = usage; report.Checkpoints = checks;
report.Transport = transport; report.Terminals = terminals;
report.Timing = timing; report.Precision = precision;

    function [outEvents,outDraws,outUsage,outChecks,outTransport,outTerminals,outTiming,outPrecision,result] = runCase(entry)
        name = char(entry.('case'));
        scheduler = csr.sim.EventScheduler(400000);
        owner = csr.validation.ReplayStreams(tape(string(tape.('case'))==name,:), ...
            @()scheduler.Now,name);
        macs = cell(1,max(plan.nodes)); hops = cell(size(macs));
        networks = cell(size(macs));
        admitted = zeros(size(macs)); delivered = zeros(size(macs));
        releases = zeros(size(macs)); blocked = zeros(size(macs));
        generated = zeros(size(macs)); finalDemand = zeros(size(macs));
        demand = cell(size(macs)); dueTimes = cell(size(macs));
        for source=reshape(plan.sources,1,[])
            demand{source} = []; dueTimes{source} = zeros(1,plan.applications_per_active_source);
        end
        transportRows = repmat(emptyTransport(),0,1);
        terminalRows = repmat(emptyTerminal(),0,1);
        timingRows = repmat(emptyTiming(),0,1);
        precisionRows = repmat(emptyPrecision(),0,1);
        txCounter = 0; groupCounter = 0;
        lossSeen = false(numel(macs),numel(macs));
        releaseFailures = 0; custodyAccepted = 0; drops = 0;
        pendingControls = zeros(size(macs));
        finalPending = zeros(size(macs)); finalHolds = zeros(size(macs));
        finalResends = zeros(size(macs));
        finalMacAck = zeros(size(macs)); finalMacData = zeros(size(macs));
        requested = zeros(size(macs));
        requested(4) = entry.apps4; requested(5) = entry.apps5;
        eventRows = repmat(emptyEvent(),0,1);
        checkRows = repmat(emptyCheck(),0,1);
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
            caseOffers = offers(string(offers.('case'))==name,:);
            for generation=1:height(caseOffers)
                item = caseOffers(generation,:);
                scheduler.scheduleAt(double(item.due_ns)/1e9, ...
                    @()generate(item.source,item.app_id,item.due_ns));
            end
            pollStartNs = round(plan.offered_start_seconds*1e9);
            pollPeriodNs = round(plan.offered_poll_seconds*1e9);
            pollStopNs = round(plan.offered_poll_stop_exclusive_seconds*1e9);
            lastPoll = ceil((pollStopNs-pollStartNs)/pollPeriodNs)-1;
            for tick=0:lastPoll
                when = (pollStartNs+tick*pollPeriodNs)/1e9;
                if when<entry.duration_seconds, scheduler.scheduleAt(when,@poll); end
            end
            for when=reshape(plan.checkpoint_seconds,1,[])
                scheduler.scheduleAt(when,@checkpointSnapshot);
            end
            scheduler.run(entry.duration_seconds);
            for node=reshape(plan.nodes,1,[])
                observe('final',node,nextHop(node),struct());
            end
            complete = true;
        catch problem
            errorId = problem.identifier; errorMessage = problem.message;
            errorStack = problem.stack;
            fprintf('Loss timing %s/%s failed: %s (%s).\n',mode,name,errorMessage,errorId);
        end
        outEvents = records(eventRows,emptyEvent());
        outDraws = records(owner.draws(),emptyDraw()); outUsage = records(owner.usage(),emptyUsage());
        outTransport = records(transportRows,emptyTransport());
        outTerminals = records(terminalRows,emptyTerminal());
        outTiming = records(timingRows,emptyTiming()); outPrecision = records(precisionRows,emptyPrecision());
        unexplained = zeros(size(macs));
        eventNames = string(outEvents.event);
        for source=reshape(plan.sources,1,[])
            admittedRows = outEvents(eventNames=="admit" & outEvents.app_source==source,:);
            deliveredRows = outEvents(eventNames=="deliver" & outEvents.app_source==source,:);
            failedRows = outTerminals(outTerminals.app_source==source & outTerminals.success==0,:);
            admissionIds = admittedRows.app_id; deliveryIds = deliveredRows.app_id;
            unexplained(source) = numel(setdiff(admissionIds,union(deliveryIds,failedRows.app_id)));
            terminalRowsForSource = outTerminals(outTerminals.app_source==source,:);
            unknown = sum(~ismember(terminalRowsForSource.app_id,admissionIds));
            dueFailures = 0;
            for a=1:height(admittedRows)
                id = double(admittedRows.app_id(a));
                if id<1 || id>numel(dueTimes{source}) || ...
                        admittedRows.time_ns(a)<round(dueTimes{source}(id)*1e9)
                    dueFailures = dueFailures+1;
                end
            end
            finalDemand(source) = numel(demand{source});
            checkpoint('generated',source,generated(source),requested(source));
            checkpoint('admitted',source,admitted(source),requested(source));
            checkpoint('unexplained_loss',source,unexplained(source),0);
            checkpoint('unknown_terminal',source,unknown,0);
            checkpoint('duplicate_delivery',source,numel(deliveryIds)-numel(unique(deliveryIds)),0);
            checkpoint('admitted_after20_seen',source,double(any(admittedRows.time_ns>20e9)),1);
            checkpoint('final_demand',source,finalDemand(source),0);
            checkpoint('admitted_before_due',source,dueFailures,0);
            checkpoint('duplicate_admission',source,numel(admissionIds)-numel(unique(admissionIds)),0);
            checkpoint('nsdp_blocked_seen',source,double(blocked(source)>0),1);
        end
        for node=reshape(plan.nodes,1,[])
            pending = -1; waiting = -1; custodyCount = -1; pair4 = -1; pair5 = -1;
            holdCount = -1; resendCount = -1;
            if ~isempty(hops{node})
                hopState = hops{node}.stats(); pending = hopState.PendingData;
                holdCount = hopState.DackHoldCount; resendCount = hopState.ResendQueueDepth;
            end
            finalPending(node) = pending; finalHolds(node) = holdCount; finalResends(node) = resendCount;
            finalMacAck(node) = -1; finalMacData(node) = -1;
            if ~isempty(macs{node})
                finalMacAck(node) = macs{node}.AckQueueCount;
                finalMacData(node) = macs{node}.DataQueueCount;
            end
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
            checkpoint('mac_ack_queue',node,finalMacAck(node),0);
            checkpoint('mac_data_queue',node,finalMacData(node),0);
            terminalCount = sum(outTerminals.node==node);
            checkpoint('terminal_release_difference',node,releases(node)-terminalCount,0);
            owned = outEvents(eventNames=="admit" & outEvents.node==node,:);
            if node==5
                received = outEvents(eventNames=="ingress_before" & outEvents.node==5 & ...
                    outEvents.app_source==4,:);
                owned = [owned;received];
            end
            ownedKeys = unique(string(owned.app_source)+":"+string(owned.app_id));
            ended = outTerminals(outTerminals.node==node,:);
            endedKeys = unique(string(ended.app_source)+":"+string(ended.app_id));
            checkpoint('ownership_identity_difference',node,numel(setxor(ownedKeys,endedKeys)),0);
        end
        stable = eventNames=="checkpoint" | eventNames=="final";
        checkpoint('custody_conservation_failures',0, ...
            sum(outEvents.nwk_custody~=outEvents.nsdp4+outEvents.nsdp5),0);
        checkpoint('stable_capacity_failures',0, ...
            sum(outEvents.hop_pending(stable)~=outEvents.resend_queue(stable)+outEvents.dack_holds(stable)),0);
        checkpoint('release_order_failures',0,releaseFailures,0);
        checkpoint('draw_resolution_failures',0, ...
            sum(string(outDraws.purpose)=="unresolved" | outDraws.resolved<0),0);
        checkpoint('drops_terminal_difference',0,drops-sum(outTerminals.success==0),0);
        deliveredRows = outEvents(eventNames=="deliver",:);
        unknownDelivery = sum(~ismember(deliveredRows.app_source,plan.sources) | ...
            deliveredRows.app_id<1 | deliveredRows.app_id>plan.applications_per_active_source | ...
            deliveredRows.node~=plan.gateway | deliveredRows.peer~=5);
        checkpoint('unknown_deliveries',0,unknownDelivery,0);
        terminalKeys = string(outTerminals.node)+":"+string(outTerminals.app_source)+":"+string(outTerminals.app_id);
        checkpoint('terminal_duplicates',0,height(outTerminals)-numel(unique(terminalKeys)),0);
        invalidOwners = sum(~ismember(outTerminals.node,[4 5]) | ...
            (outTerminals.node==4 & outTerminals.app_source~=4));
        checkpoint('invalid_terminal_owner',0,invalidOwners,0);
        checkpoint('loss_policy_failures',0,validateLoss(outTransport,entry,plan),0);
        lost = string(outTransport.decision)=="drop";
        lossGroups = numel(unique(outTransport.group_id(lost)));
        if strcmp(name,'ok'), expectedLoss = 0; actualLoss = lossGroups;
        elseif strcmp(name,'out'), expectedLoss = 1; actualLoss = double(lossGroups>0);
        else, expectedLoss = 2; actualLoss = lossGroups; end
        checkpoint('loss_groups_expected',0,actualLoss,expectedLoss);
        checkpoint('post_loss_delivery_seen',0,double(any(deliveredRows.time_ns>9.5e9)),1);
        controlFailures = 0;
        if strcmp(name,'ok')
            controlFailures = sum(abs(requested-delivered))+sum(outTerminals.success==0);
        end
        checkpoint('control_delivery_failures',0,controlFailures,0);
        checkpoint('case_completed',0,double(complete),1);
        outChecks = records(checkRows,emptyCheck());
        result = emptyResult(); result.Case = name; result.Completed = complete;
        result.ErrorIdentifier = errorId; result.ErrorMessage = errorMessage; result.ErrorStack = errorStack;
        result.Requested = requested; result.Generated = generated;
        result.Admitted = admitted; result.Delivered = delivered; result.Released = releases;
        result.Unexplained = unexplained; result.FinalDemand = finalDemand;
        result.RelayCustodyAccepted = custodyAccepted; result.PendingControls = pendingControls;
        result.FinalHopPending = finalPending; result.FinalDackHolds = finalHolds;
        result.FinalResends = finalResends; result.Drops = drops;
        result.FinalMacAckQueue = finalMacAck; result.FinalMacDataQueue = finalMacData;
        result.FailedTerminals = sum(outTerminals.success==0); result.LossGroups = lossGroups;
        result.MaximumDackHolds = max([0;outEvents.dack_holds]);

        function peer = nextHop(node)
            if node==4, peer = 5; elseif node==5, peer = 1; else, peer = 0; end
        end
        function checkpointSnapshot()
            for endpoint=reshape(plan.nodes,1,[])
                observe('checkpoint',endpoint,nextHop(endpoint),struct());
            end
        end
        function generate(source,id,dueNs)
            id = double(id);
            if id~=generated(source)+1 || id>requested(source)
                error('csr:validation:LossGeneration','Generation identity is not contiguous.');
            end
            generated(source) = generated(source)+1;
            demand{source}(end+1) = id; dueTimes{source}(id) = double(dueNs)/1e9;
            observe('generate',source,nextHop(source), ...
                struct('App',struct('SourceId',source,'Id',uint64(id))));
        end
        function poll()
            for source=reshape(plan.sources,1,[]), offer(source); end
        end
        function offer(node)
            if isempty(demand{node}), return; end
            id = demand{node}(1);
            app = struct('Id',uint64(id),'SourceId',node, ...
                'DestinationId',plan.gateway,'GeneratedSeconds',dueTimes{node}(id), ...
                'ApplicationPayloadBytes',plan.application_payload_bytes,'Dscp',plan.dscp);
            metadata = struct('App',app); observe('offer',node,nextHop(node),metadata);
            state = networks{node}.applicationState(plan.gateway);
            if state.NsdpLimit~=plan.application_nsdp_limit
                error('csr:validation:LossAdmissionLimit','NWK state differs from the pinned NSDP limit.');
            end
            if state.NsdpCount>=state.NsdpLimit
                blocked(node) = blocked(node)+1;
                observe('blocked',node,nextHop(node),metadata); return
            end
            if ~networks{node}.sendApplication(app)
                error('csr:validation:LossAdmission','The bounded application was rejected by the real NWK queue.');
            end
            admitted(node) = admitted(node)+1; demand{node}(1) = [];
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
        function terminal(node,app,success,reason)
            networks{node}.terminal(app,success,reason);
            row = emptyTerminal(); row.('case') = name; row.order = numel(terminalRows)+1;
            row.time_ns = round(scheduler.Now*1e9); row.node = node;
            row.app_source = app.SourceId; row.app_id = uint64(app.Id);
            row.success = double(success); row.reason = reason;
            terminalRows(end+1,1) = row;
        end
        function macEvent(node,event,~,details)
            if strcmp(event,'mac_prepare'), owner.resolve(node,'prepare',details.ReservationSlot); end
        end
        function transmit(node,envelope,duration)
            owner.resolve(node,'advertise',envelope.ReservationSlot);
            txCounter = txCounter+1;
            txNs = round(scheduler.Now*1e9);
            [arrival,arithmetic] = csr.validation.transportArrival( ...
                scheduler.Now,duration,plan.propagation_seconds,mode);
            timingRow = emptyTiming(); timingRow.('case') = name;
            timingRow.tx_id = txCounter; timingRow.sender = node;
            timingRow.wire_payload_bytes = double(envelope.WirePayloadBytes);
            timingRow.segment_count = numel(envelope.Segments);
            timingRow.preamble = char(envelope.Preamble);
            timingRow.rate_kbps = double(envelope.RateKeyKbps);
            timingRow.power_dbm = double(envelope.TxPowerDbm);
            arithmeticFields = fieldnames(arithmetic);
            for field=1:numel(arithmeticFields)
                key = arithmeticFields{field}; timingRow.(key) = arithmetic.(key);
            end
            timingRows(end+1,1) = timingRow;
            receivers = zeros(1,numel(envelope.Segments));
            kinds = strings(size(receivers));
            for segment=1:numel(envelope.Segments)
                receivers(segment) = envelope.Segments{segment}.DestinationId;
                kinds(segment) = string(envelope.Segments{segment}.Kind);
            end
            groupIds = zeros(size(receivers)); decisions = false(size(receivers));
            reasons = repmat("none",size(receivers)); distance = -1;
            if strcmp(entry.loss_policy,'out')
                distance = min(abs(txNs-double(entry.loss_start_ns)),abs(txNs-double(entry.loss_stop_ns)));
                if distance<=plan.loss_boundary_guard_ns
                    error('csr:validation:LossBoundary','TX start lies within the declared outage-boundary guard.');
                end
            end
            for receiver=reshape(unique(receivers,'stable'),1,[])
                if ~((node==1 && receiver==5) || (node==4 && receiver==5) || ...
                        (node==5 && any(receiver==[1 4])))
                    error('csr:validation:LossTopology','Frame left the controlled 4-5-1 chain.');
                end
                selected = receivers==receiver; groupCounter = groupCounter+1;
                groupIds(selected) = groupCounter; reason = "none"; drop = false;
                if strcmp(entry.loss_policy,'data') && ...
                        ((node==4 && receiver==5) || (node==5 && receiver==1)) && ...
                        any(kinds(selected)=="DATA") && ~lossSeen(node,receiver)
                    drop = true; reason = "first_data"; lossSeen(node,receiver) = true;
                elseif strcmp(entry.loss_policy,'ack') && ...
                        ((node==5 && receiver==4) || (node==1 && receiver==5)) && ...
                        any(ismember(kinds(selected),["ACK","DACK"])) && ~lossSeen(node,receiver)
                    drop = true; reason = "first_feedback"; lossSeen(node,receiver) = true;
                elseif strcmp(entry.loss_policy,'out') && txNs>=entry.loss_start_ns && txNs<entry.loss_stop_ns
                    drop = true; reason = "outage";
                end
                decisions(selected) = drop; reasons(selected) = reason;
            end
            for segment=1:numel(envelope.Segments)
                frame = envelope.Segments{segment};
                frame.ReservationSlot = envelope.ReservationSlot;
                frame.ActiveNodes = envelope.ActiveNodes;
                observe('tx_start',node,frame.DestinationId,frame);
                row = emptyTransport(); row.('case') = name;
                row.tx_id = txCounter; row.group_id = groupIds(segment);
                row.segment_index = segment; row.group_segments = sum(receivers==receivers(segment));
                row.tx_time_ns = txNs; row.arrival_ns = round(arrival*1e9);
                row.sender = node; row.receiver = receivers(segment); row.kind = char(kinds(segment));
                if isfield(frame,'App') && isfield(frame.App,'SourceId')
                    row.app_source = frame.App.SourceId; row.app_id = uint64(frame.App.Id);
                end
                row.hop_seq = double(frame.Sequence);
                if isfield(frame,'AckBitmap'), row.ack_bits = uint64(frame.AckBitmap); end
                if isfield(frame,'DackBitmap'), row.dack_bits = uint64(frame.DackBitmap); end
                row.decision = 'pass'; if decisions(segment), row.decision = 'drop'; end
                row.reason = char(reasons(segment)); row.boundary_distance_ns = distance;
                transportRows(end+1,1) = row;
            end
            % Cache the whole receiver-group decision at actual TX start.
            % Arrival does not consult time or mutable first-loss state again.
            scheduler.scheduleAt(arrival,@()ingress(envelope,decisions));
        end
        function ingress(envelope,decisions)
            heard = false(size(macs));
            for segment=1:numel(envelope.Segments)
                frame = envelope.Segments{segment};
                frame.ReservationSlot = envelope.ReservationSlot;
                frame.ActiveNodes = envelope.ActiveNodes;
                node = frame.DestinationId; peer = frame.SourceId;
                if decisions(segment)
                    observe('loss',node,peer,frame); continue
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
            precise = emptyPrecision();
            identities = fieldnames(precise);
            for field=1:numel(identities)-2
                key = identities{field}; precise.(key) = row.(key);
            end
            precise.time_seconds = sprintf('%.17g',scheduler.Now);
            precise.time_hex = num2hex(scheduler.Now);
            precisionRows(end+1,1) = precise;
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
options = detectImportOptions(path,'VariableNamingRule','preserve');
textFields = actual.Properties.VariableNames(varfun(@isstring,actual,'OutputFormat','uniform'));
exact = intersect([{'app_id','ack_bits','dack_bits'},textFields],options.VariableNames,'stable');
if ~isempty(exact), options = setvartype(options,exact,'string'); end
expected = readtable(path,options);
result.ReferenceRows = height(expected); result.ComparedRows = max(height(actual),height(expected));
result.SchemaMatches = isequal(actual.Properties.VariableNames,expected.Properties.VariableNames);
if ~result.SchemaMatches, result.UnmatchedCount = max(1,result.ComparedRows); return; end
overlap = min(height(actual),height(expected)); matched = true(overlap,1);
for k=1:width(actual)
    name = actual.Properties.VariableNames{k}; left = actual.(name)(1:overlap); right = expected.(name)(1:overlap);
    if ismember(name,{'time_ns','tx_time_ns','arrival_ns'})
        delta = abs(double(left)-double(right)); matched = matched & isfinite(delta) & delta<=1;
        if ~isempty(delta), result.MaximumTimeDifferenceNanoseconds = ...
                max(result.MaximumTimeDifferenceNanoseconds,max(delta)); end
    elseif ismember(name,{'app_id','ack_bits','dack_bits'})
        if ~isa(left,'uint64'), error('csr:validation:LossIntegerType','Exact integer columns require uint64.'); end
        matched = matched & string(left)==string(right);
    elseif isnumeric(left) || islogical(left)
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

function result = emptyResult()
result = struct('Case','','Completed',false,'ErrorIdentifier','', ...
    'ErrorMessage','','ErrorStack',struct('file',{},'name',{},'line',{}), ...
    'Requested',[],'Generated',[],'Admitted',[],'Delivered',[],'Released',[], ...
    'Unexplained',[],'FinalDemand',[],'RelayCustodyAccepted',0,'PendingControls',[], ...
    'FinalHopPending',[],'FinalDackHolds',[],'FinalResends',[],'Drops',0, ...
    'FinalMacAckQueue',[],'FinalMacDataQueue',[], ...
    'FailedTerminals',0,'LossGroups',0,'MaximumDackHolds',0);
end

function row = emptyTransport()
row = struct('case','','tx_id',0,'group_id',0,'segment_index',0,'group_segments',0, ...
    'tx_time_ns',0,'arrival_ns',0,'sender',0,'receiver',0,'kind','', ...
    'app_source',0,'app_id',uint64(0),'hop_seq',0,'ack_bits',uint64(0), ...
    'dack_bits',uint64(0),'decision','','reason','','boundary_distance_ns',-1);
end

function row = emptyTerminal()
row = struct('case','','order',0,'time_ns',0,'node',0,'app_source',0, ...
    'app_id',uint64(0),'success',0,'reason','');
end

function failures = validateLoss(rows,entry,plan)
% Recompute each receiver-group policy from emitted frame records. This does
% not alter transport; incomplete/different trajectories stay observable.
failures = 0; seen = false(max(plan.nodes),max(plan.nodes));
for id=reshape(unique(rows.group_id,'stable'),1,[])
    group = rows(rows.group_id==id,:); first = group(1,:);
    sender = first.sender; receiver = first.receiver;
    expected = "pass"; reason = "none"; distance = -1;
    kinds = string(group.kind);
    if strcmp(entry.loss_policy,'data') && ...
            ((sender==4 && receiver==5) || (sender==5 && receiver==1)) && ...
            any(kinds=="DATA") && ~seen(sender,receiver)
        expected = "drop"; reason = "first_data"; seen(sender,receiver) = true;
    elseif strcmp(entry.loss_policy,'ack') && ...
            ((sender==5 && receiver==4) || (sender==1 && receiver==5)) && ...
            any(ismember(kinds,["ACK","DACK"])) && ~seen(sender,receiver)
        expected = "drop"; reason = "first_feedback"; seen(sender,receiver) = true;
    elseif strcmp(entry.loss_policy,'out')
        distance = min(abs(first.tx_time_ns-entry.loss_start_ns),abs(first.tx_time_ns-entry.loss_stop_ns));
        if first.tx_time_ns>=entry.loss_start_ns && first.tx_time_ns<entry.loss_stop_ns
            expected = "drop"; reason = "outage";
        end
        failures = failures+double(distance<=plan.loss_boundary_guard_ns);
    end
    failures = failures+sum(string(group.decision)~=expected | string(group.reason)~=reason | ...
        group.boundary_distance_ns~=distance | group.group_segments~=height(group) | ...
        group.sender~=sender | group.receiver~=receiver | group.tx_id~=first.tx_id | ...
        group.tx_time_ns~=first.tx_time_ns | group.arrival_ns~=first.arrival_ns);
end
end

function output = records(rows,prototype)
if isnumeric(rows) && isempty(rows), rows = repmat(prototype,0,1); end
output = csr.validation.edgeRecordTable(rows,prototype);
end

function saveTables(directory,events,draws,usage,checks,transport,terminals,timing,precision)
if ~isfolder(directory), mkdir(directory); end
names = {'events','draws','usage','check','transport','terminal','timing','precision'};
outputs = {events,draws,usage,checks,transport,terminals,timing,precision};
for k=1:numel(names), writetable(outputs{k},fullfile(directory,[names{k} '.csv'])); end
end

function row = emptyDraw()
row = struct('case','','node',0,'ordinal',0,'time_ns',0, ...
    'min',0,'max',0,'draw',0,'resolved',-1,'purpose','unresolved');
end

function row = emptyUsage()
row = struct('case','','node',0,'supplied',0,'consumed',0,'unused',0);
end

function row = emptyCheck()
row = struct('case','','checkpoint','','node',0,'actual',0,'expected',0,'pass',false);
end

function row = emptyTiming()
row = struct('case','','tx_id',0,'sender',0, ...
    'tx_seconds','','tx_hex','','duration_seconds','','duration_hex','', ...
    'propagation_seconds','','propagation_hex','','continuous_seconds','','continuous_hex','', ...
    'nanoseconds_seconds','','nanoseconds_hex','','arrival_seconds','','arrival_hex','', ...
    'delta_seconds','','delta_hex','','tx_ns',uint64(0),'duration_ns',uint64(0), ...
    'propagation_ns',uint64(0),'sum_ns',uint64(0), ...
    'wire_payload_bytes',0,'segment_count',0,'preamble','','rate_kbps',0,'power_dbm',0);
end

function row = emptyPrecision()
row = struct('case','','order',0,'time_ns',0,'event','','node',0,'peer',0, ...
    'app_source',0,'app_id',uint64(0),'hop_seq',0,'ack_bits',uint64(0), ...
    'dack_bits',uint64(0),'time_seconds','','time_hex','');
end
