function report = replayContract(outputDirectory)
%REPLAYCONTRACT Controlled, matched-input service of real MATLAB MAC/HOP.
% Raw scalar draws enter production pickSlot before its occupancy probe.
% Actual MAC airtime and actual HOP-generated ACK frames drive an addressed
% success-only transport. No NWK, RF acquisition, collision or adaptive-radio
% equivalence is claimed. Differences from the complete native reference
% remain diagnostic results and never change the supplied tapes.
if nargin<1, outputDirectory = ''; end
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
inputDirectory = fullfile(root,'scenarios','replay');
referenceDirectory = fullfile(root,'evidence','tranche-11-replay-reference');
plan = jsondecode(fileread(fullfile(inputDirectory,'plan.json')));
cases = readtable(fullfile(inputDirectory,'cases.csv'),'TextType','string', ...
    'VariableNamingRule','preserve');
tape = readtable(fullfile(inputDirectory,'draws.csv'),'TextType','string', ...
    'VariableNamingRule','preserve');
if ~strcmp(plan.schema,'csr-tranche11-replay-input-v1') || ...
        ~isequal(string(cases.('case')),string(plan.cases(:)))
    error('csr:validation:ReplayPlan','Replay cases do not match the immutable plan.');
end
events = table(); draws = table(); usage = table(); checks = table();
caseResults = repmat(struct('Case','','Completed',false,'ErrorIdentifier','', ...
    'ErrorMessage','','ErrorStack',struct('file',{},'name',{},'line',{}), ...
    'Admitted',[],'Delivered',[],'Released',[],'WakeCount',[]),0,1);
for k=1:height(cases)
    [caseEvents,caseDraws,caseUsage,caseChecks,result] = runCase(cases(k,:));
    events = [events;caseEvents]; draws = [draws;caseDraws]; %#ok<AGROW>
    usage = [usage;caseUsage]; checks = [checks;caseChecks]; %#ok<AGROW>
    caseResults(end+1,1) = result; %#ok<AGROW>
end
if ~isequal(events.Properties.VariableNames,cellstr(string(plan.events_schema(:)))') || ...
        ~isequal(draws.Properties.VariableNames,cellstr(string(plan.draws_output_schema(:)))')
    error('csr:validation:ReplaySchema','Observed replay schema differs from the input plan.');
end
eventComparison = compareTable(events,fullfile(referenceDirectory,'events.csv'));
drawComparison = compareTable(draws,fullfile(referenceDirectory,'draws.csv'));
usageComparison = compareTable(usage,fullfile(referenceDirectory,'usage.csv'));
unmatched = eventComparison.UnmatchedCount+drawComparison.UnmatchedCount+usageComparison.UnmatchedCount;
completed = all([caseResults.Completed]);
failed = sum(~logical(checks.pass));
report = struct('Schema','csr-tranche11-replay-contract-v1', ...
    'DiagnosticCompleted',completed,'MatchesNative',unmatched==0, ...
    'Passed',completed && failed==0,'CaseCount',height(cases), ...
    'EventCount',height(events),'DrawCount',height(draws), ...
    'CheckpointCount',height(checks),'FailedCount',failed,'UnmatchedCount',unmatched, ...
    'EventsCompared',eventComparison.ComparedRows,'DrawsCompared',drawComparison.ComparedRows, ...
    'UsageCompared',usageComparison.ComparedRows,'ComparedEntireTrajectories',true, ...
    'InputBindings',bindings(inputDirectory,{'plan.json','cases.csv','draws.csv'},'scenarios/replay/'), ...
    'ReferenceBindings',bindings(referenceDirectory,{'events.csv','draws.csv','usage.csv'}, ...
        'evidence/tranche-11-replay-reference/'), ...
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
        scheduler = csr.sim.EventScheduler(100000);
        owner = csr.validation.ReplayStreams(tape(string(tape.('case'))==name,:), ...
            @()scheduler.Now,name);
        macs = cell(1,max(plan.nodes)); hops = cell(size(macs));
        admitted = zeros(size(macs)); delivered = zeros(size(macs));
        releases = zeros(size(macs)); wakes = zeros(size(macs));
        blocked = zeros(size(macs)); releaseFailures = zeros(size(macs));
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
            for node=reshape(plan.nodes,1,[])
                macs{node} = csr.mac.Layer(node,scheduler,owner,options, ...
                    struct('Transmit',@(f,d)transmit(node,f,d), ...
                    'Sent',@(f)sent(node,f),'Event',@(n,f,d)macEvent(node,n,f,d)));
                hops{node} = csr.hop.Layer(node,scheduler,owner,struct(), ...
                    struct('EnqueueMac',@(f)enqueue(node,f), ...
                    'CancelMac',@(p,s)cancel(node,p,s), ...
                    'Deliver',@(a,p)deliver(node,a,p), ...
                    'NsdpRelease',@(a,r)release(node,a,r),'Wake',@()wake(node)));
            end
            for node=reshape(plan.nodes,1,[])
                macs{node}.start();
                if node==plan.gateway, peers = reshape(plan.sources,1,[]);
                else, peers = plan.gateway; end
                for peer=peers
                    heard = struct('SourceId',peer, ...
                        'ReservationSlot',plan.initial_neighbor_reservation);
                    macs{node}.receive(heard,struct('Success',true));
                    macs{node}.receive(heard,struct('Success',true));
                end
            end
            if entry.track_start_seconds>=0
                scheduler.scheduleAt(entry.track_start_seconds,@()busy('Track'));
                scheduler.scheduleAt(entry.track_stop_seconds,@()busy('Search'));
            end
            pollStartNs = round(plan.offered_start_seconds*1e9);
            pollPeriodNs = round(plan.offered_poll_seconds*1e9);
            pollStopNs = round(plan.offered_poll_stop_exclusive_seconds*1e9);
            lastPoll = ceil((pollStopNs-pollStartNs)/pollPeriodNs)-1;
            for tick=0:lastPoll
                when = (pollStartNs+tick*pollPeriodNs)/1e9;
                if when<entry.duration_seconds
                    scheduler.scheduleAt(when,@poll);
                end
            end
            scheduler.run(entry.duration_seconds);
            for node=reshape(plan.nodes,1,[])
                peer = plan.gateway; if node==plan.gateway, peer = 0; end
                observe('final',node,peer,struct());
            end
            complete = true;
        catch problem
            errorId = problem.identifier; errorMessage = problem.message;
            errorStack = problem.stack;
        end
        outEvents = struct2table(eventRows); outDraws = owner.draws(); outUsage = owner.usage();
        for node=reshape(plan.sources,1,[])
            checkpoint('admitted',node,admitted(node),plan.applications_per_source);
            checkpoint('delivered',node,delivered(node),plan.applications_per_source);
            checkpoint('released',node,releases(node),plan.applications_per_source);
            pending = -1; if ~isempty(hops{node}), pending = hops{node}.PendingDataCount; end
            checkpoint('pending',node,pending,0);
            checkpoint('release_order_failures',node,releaseFailures(node),0);
            checkpoint('blocked_seen',node,double(blocked(node)>0),1);
        end
        ackSeen = any(string(outEvents.event)=="tx_start" & ...
            outEvents.node==plan.gateway & outEvents.app_source==0);
        checkpoint('ack_transmissions_seen',plan.gateway,double(ackSeen),1);
        resolutionFailures = sum(string(outDraws.purpose)=="unresolved" | outDraws.resolved<0);
        checkpoint('draw_resolution_failures',0,resolutionFailures,0);
        outChecks = struct2table(checkRows);
        result = struct('Case',name,'Completed',complete,'ErrorIdentifier',errorId, ...
            'ErrorMessage',errorMessage,'ErrorStack',errorStack, ...
            'Admitted',admitted,'Delivered',delivered, ...
            'Released',releases,'WakeCount',wakes);

        function poll()
            for source=reshape(plan.sources,1,[]), offer(source); end
        end
        function offer(node)
            if admitted(node)>=plan.applications_per_source, return; end
            app = struct('Id',uint64(admitted(node)+1),'SourceId',node, ...
                'DestinationId',plan.gateway,'GeneratedSeconds',scheduler.Now, ...
                'ApplicationPayloadBytes',plan.application_payload_bytes,'Dscp',plan.dscp);
            before = struct('App',app);
            observe('offer',node,plan.gateway,before);
            if ~hops{node}.canSend(plan.gateway)
                blocked(node) = blocked(node)+1;
                observe('blocked',node,plan.gateway,before); return
            end
            radio = struct('EnvelopeProfile',plan.wire_profile, ...
                'RateKeyKbps',plan.rate_kbps,'TxPowerDbm',plan.power_dbm);
            [accepted,frame] = hops{node}.send(app,plan.gateway,radio);
            if ~accepted
                error('csr:validation:ReplayAdmission','HOP allowed admission but MAC rejected the finite fixture frame.');
            end
            admitted(node) = admitted(node)+1;
            observe('admit',node,plan.gateway,frame);
        end
        function accepted = enqueue(node,frame)
            % HOP feedback leaves power empty for the radio adapter to fill,
            % as in MacHopSimulation.enqueueMac. This fixture's node radio
            % power is fixed by the pinned plan; retain supplied frame power.
            if isempty(frame.TxPowerDbm), frame.TxPowerDbm = plan.power_dbm; end
            accepted = macs{node}.enqueue(frame);
        end
        function cancel(node,peer,sequence), macs{node}.cancel(peer,sequence); end
        function sent(node,frame), hops{node}.notifySent(frame); end
        function macEvent(node,event,~,details)
            if strcmp(event,'mac_prepare')
                owner.resolve(node,'prepare',details.ReservationSlot);
            end
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
                observe('ingress_before',node,peer,frame);
                if ~heard(node)
                    macs{node}.receive(frame,struct('Success',true));
                    heard(node) = true;
                end
                hops{node}.receive(frame,struct('Success',true));
                observe('ingress_after',node,peer,frame);
            end
        end
        function accepted = deliver(node,app,~)
            accepted = node==plan.gateway && app.DestinationId==node;
            if accepted, delivered(app.SourceId) = delivered(app.SourceId)+1; end
        end
        function release(node,app,reason)
            if ~strcmp(reason,'ack')
                error('csr:validation:ReplayRelease','Controlled successful delivery unexpectedly released by %s.',reason);
            end
            releases(node) = releases(node)+1;
            state = hops{node}.state(plan.gateway);
            if state.PendingData~=state.NeighborOutstanding || ...
                    state.ResendQueueDepth<=state.PendingData
                releaseFailures(node) = releaseFailures(node)+1;
            end
            % Native's NSDP callback exposes source/destination but no ID.
            metadata = struct('App',struct('SourceId',app.SourceId,'Id',uint64(0)));
            observe('release',node,plan.gateway,metadata);
        end
        function wake(node)
            wakes(node) = wakes(node)+1;
            peer = plan.gateway; if node==plan.gateway, peer = 0; end
            observe('wake',node,peer,struct());
            if any(plan.sources==node), offer(node); end
        end
        function busy(state)
            macs{plan.receiver_track_node}.receiverChanged(state);
            observe('busy',plan.receiver_track_node,0,struct());
        end
        function observe(event,node,peer,frame)
            row = emptyEvent();
            row.('case') = name; row.order = numel(eventRows)+1;
            row.time_ns = round(scheduler.Now*1e9); row.event = event;
            row.node = node; row.peer = peer;
            if isfield(frame,'App') && isfield(frame.App,'SourceId')
                row.app_source = frame.App.SourceId; row.app_id = frame.App.Id;
            end
            if isfield(frame,'Sequence'), row.hop_seq = double(frame.Sequence); end
            if isfield(frame,'AckBitmap'), row.ack_bits = frame.AckBitmap; end
            if isfield(frame,'DackBitmap'), row.dack_bits = frame.DackBitmap; end
            if isfield(frame,'RateKeyKbps'), row.rate_kbps = frame.RateKeyKbps; end
            if isfield(frame,'TxPowerDbm'), row.power_dbm = frame.TxPowerDbm; end
            mac = macs{node};
            row.mac_state = find(strcmp(mac.State,{'Idle','Search','Track','Tx'}))-1;
            row.ack_queue = mac.AckQueueCount; row.data_queue = mac.DataQueueCount;
            row.prep = double(mac.PreparationActive); row.counter = mac.ReservationCounter;
            row.opportunity = mac.LastOpportunitySlot; row.advertised = mac.LastAdvertisedReservation;
            state = hops{node}.state(peer);
            row.hop_pending = state.PendingData;
            if peer~=0
                row.neighbor_outstanding = state.NeighborOutstanding;
                row.neighbor_threshold = state.NeighborThreshold;
            end
            row.resend_queue = state.ResendQueueDepth; row.admitted = admitted(node);
            eventRows(end+1,1) = row;
        end
        function checkpoint(point,node,actual,target)
            checkRows(end+1,1) = struct('case',name,'checkpoint',point, ...
                'node',node,'actual',double(actual),'expected',double(target), ...
                'pass',isfinite(double(actual)) && actual==target);
        end
    end
end

function row = emptyEvent()
row = struct('case','','order',0,'time_ns',0,'event','','node',0,'peer',0, ...
    'app_source',0,'app_id',uint64(0),'hop_seq',0,'ack_bits',uint64(0), ...
    'dack_bits',uint64(0),'mac_state',0,'ack_queue',0,'data_queue',0,'prep',0, ...
    'counter',0,'opportunity',0,'advertised',0,'hop_pending',0, ...
    'neighbor_outstanding',0,'neighbor_threshold',0,'resend_queue',0, ...
    'admitted',0,'rate_kbps',0,'power_dbm',0);
end

function result = compareTable(actual,path)
result = struct('ReferencePresent',isfile(path),'SchemaMatches',false, ...
    'ActualRows',height(actual),'ReferenceRows',0,'ComparedRows',height(actual), ...
    'UnmatchedCount',max(1,height(actual)),'FirstUnmatchedRow',0, ...
    'MaximumTimeDifferenceNanoseconds',0);
if ~isfile(path), return; end
expected = readtable(path,'TextType','string','VariableNamingRule','preserve');
result.ReferenceRows = height(expected);
result.ComparedRows = max(height(actual),height(expected));
result.SchemaMatches = isequal(actual.Properties.VariableNames,expected.Properties.VariableNames);
if ~result.SchemaMatches
    result.UnmatchedCount = max(1,result.ComparedRows); return;
end
overlap = min(height(actual),height(expected)); matched = true(overlap,1);
for k=1:width(actual)
    name = actual.Properties.VariableNames{k};
    left = actual.(name)(1:overlap); right = expected.(name)(1:overlap);
    if strcmp(name,'time_ns')
        delta = abs(double(left)-double(right));
        matched = matched & isfinite(delta) & delta<=1;
        if ~isempty(delta), result.MaximumTimeDifferenceNanoseconds = max(delta); end
    elseif isnumeric(left) || islogical(left)
        % Fixture IDs are 1..4 and cumulative bitmaps cover at most four
        % packets; the comparison remains exact within double integer range.
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
    path = fullfile(directory,names{k});
    hash = ''; if isfile(path), hash = csr.validation.Artifacts.sha256(path); end
    output(end+1,1) = struct('Path',[prefix names{k}],'SHA256',hash); %#ok<AGROW>
end
end
