function report = clockBoundaryContract(outputDirectory)
%CLOCKBOUNDARYCONTRACT Observe real MAC counter ordering at one clock boundary.
% A queued DATA frame uses prescribed occupancy leaving one free slot. Actual MAC
% holdoff/ticks decrement its local and neighbor counters. Reservation ingress
% is a prescribed successful MAC input, with no PHY/HOP/NWK execution claim.
% The continuous case intentionally retains the T11 binary64 ordering delta;
% only the separate quantized case applies native time at the test transport.
if nargin < 1, outputDirectory = ''; end
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
planPath = fullfile(root,'scenarios','clock','plan.json');
plan = jsondecode(fileread(planPath));
names = {'tie_early','tie_late','before','after','continuous','quantized'};
validatePlan(plan,names);
rows = repmat(struct('case','','order',0,'phase','','time_ns',0, ...
    'local_counter',0,'neighbor_counter',0,'data_queue',0,'transmissions',0),0,1);
checks = repmat(struct('case','','phase','','field','','actual',0, ...
    'expected',0,'pass',false),0,1);
boundaries = repmat(struct('case','','arrival_seconds_hex','','tick_seconds_hex','', ...
    'arrival_minus_tick_seconds',0,'transport_quantized',false,'late_insertion',false),0,1);
for caseIndex = 1:numel(names), runCase(names{caseIndex}); end
events = struct2table(rows); checkpoints = struct2table(checks);
boundary = struct2table(boundaries);
referencePath = fullfile(root,'evidence','tranche-12-clock-reference','events.csv');
native = readtable(referencePath,'TextType','string','VariableNamingRule','preserve');
matched = false(height(events),1);
if height(native) == height(events) && ...
        isequal(native.Properties.VariableNames,events.Properties.VariableNames)
    matched(:) = true;
    for field = {'case','phase'}
        matched = matched & string(events.(field{1})) == string(native.(field{1}));
    end
    for field = {'order','time_ns','local_counter','neighbor_counter','data_queue','transmissions'}
        actual = double(events.(field{1})); target = double(native.(field{1}));
        matched = matched & isfinite(actual) & isfinite(target) & actual == target;
    end
end
continuous = string(events.case) == "continuous";
referenceComplete = height(native) == height(events);
continuousBoundary = boundary(string(boundary.case)=="continuous",:);
expectedResidual = referenceComplete && all(checkpoints.pass) && all(~matched(continuous)) && ...
    all(matched(~continuous)) && continuousBoundary.arrival_minus_tick_seconds == eps(plan.boundary_ns/1e9);
summary = struct('Schema','csr-tranche12-clock-contract-v1', ...
    'DiagnosticCompleted',height(events)==18 && height(checkpoints)==72 && height(boundary)==6, ...
    'Passed',all(checkpoints.pass),'MatchesNative',referenceComplete && all(matched), ...
    'SharedIntegerMatchesNative',referenceComplete && all(matched(~continuous)), ...
    'ExpectedContinuousResidual',expectedResidual,'CaseCount',6,'EventCount',height(events), ...
    'CheckpointCount',height(checkpoints),'FailedCount',sum(~checkpoints.pass), ...
    'UnmatchedCount',max(height(events),height(native))-sum(matched), ...
    'InputSHA256',csr.validation.Artifacts.sha256(planPath), ...
    'ReferenceSHA256',csr.validation.Artifacts.sha256(referencePath), ...
    'GlobalClockChanged',false,'TransportQuantizationScope','quantized case only', ...
    'Scope',plan.scope);
if ~isempty(outputDirectory)
    if ~isfolder(outputDirectory), mkdir(outputDirectory); end
    writetable(events,fullfile(outputDirectory,'events.csv'));
    writetable(checkpoints,fullfile(outputDirectory,'checks.csv'));
    writetable(boundary,fullfile(outputDirectory,'boundary.csv'));
    csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'summary.json'),summary);
end
report = summary; report.Events = events; report.Checkpoints = checkpoints;
report.Boundary = boundary;

    function runCase(name)
        scheduler = csr.sim.EventScheduler();
        options = csr.mac.Layer.defaults(); options.DutyCycleEnabled = false;
        options.SlotProfile = plan.slot_profile; options.ActiveNodes = plan.active_nodes;
        mac = csr.mac.Layer(1,scheduler,csr.sim.RandomStreams(129),options, ...
            struct('Transmit',@(~,~)[]));
        mac.start(); mac.receiverChanged('Idle');
        order = 0; tick = plan.boundary_ns/1e9;
        followsTick = any(strcmp(name,{'tie_late','after','continuous'}));
        scheduler.scheduleAt(plan.mac_epoch_ns/1e9,@startMac);
        scheduler.scheduleAt(plan.neighbor_reset_ns/1e9,@resetNeighbor);
        arm = plan.early_arm_ns/1e9;
        if strcmp(name,'tie_late'), arm = plan.late_arm_ns/1e9; end
        scheduler.scheduleAt(arm,@armIngress);
        scheduler.scheduleAt(plan.settled_ns/1e9,@()snapshot('settled'));
        scheduler.run((plan.settled_ns+1)/1e9);

        function startMac()
            mac.receiverChanged('Search');
            mac.receive(struct('SourceId',2),struct('Success',true));
            mac.receive(struct('SourceId',2),struct('Success',true));
            for slot = 0:plan.slot_range
                if slot == plan.free_slot, continue; end
                peer = 100+slot;
                heard = struct('SourceId',peer,'ReservationSlot',slot+1);
                mac.receive(heard,struct('Success',true));
                mac.receive(heard,struct('Success',true));
            end
            application = struct('Id',uint64(1),'SourceId',1,'DestinationId',2, ...
                'GeneratedSeconds',scheduler.Now,'ApplicationPayloadBytes',16,'Dscp',0);
            frame = csr.hop.Frames.data(application,1,2,uint16(1), ...
                struct('EnvelopeProfile','bare','RateKeyKbps',128,'TxPowerDbm',33));
            mac.enqueue(frame);
        end
        function resetNeighbor()
            mac.receive(struct('SourceId',2,'ReservationSlot',plan.neighbor_slot), ...
                struct('Success',true));
        end
        function armIngress()
            arrival = tick;
            if strcmp(name,'before'), arrival = (plan.boundary_ns-1)/1e9; end
            if strcmp(name,'after'), arrival = (plan.boundary_ns+1)/1e9; end
            if any(strcmp(name,{'continuous','quantized'}))
                duration = csr.phy.airtime(plan.wire_payload_bytes,plan.rate_kbps,plan.preamble);
                if strcmp(name,'continuous')
                    arrival = scheduler.Now + duration + plan.propagation_seconds;
                else
                    % Native transport resolves each duration to integer ns.
                    % This local test option does not round EventScheduler.
                    arrival = (round(scheduler.Now*1e9) + round(duration*1e9) + ...
                        round(plan.propagation_seconds*1e9))/1e9;
                end
            end
            boundaries(end+1,1) = struct('case',name,'arrival_seconds_hex',num2hex(arrival), ...
                'tick_seconds_hex',num2hex(tick),'arrival_minus_tick_seconds',arrival-tick, ...
                'transport_quantized',strcmp(name,'quantized'),'late_insertion',strcmp(name,'tie_late'));
            scheduler.scheduleAt(arrival,@ingress);
        end
        function ingress()
            snapshot('ingress_before'); resetNeighbor(); snapshot('ingress_after');
        end
        function snapshot(phase)
            order = order + 1;
            row = struct('case',name,'order',order,'phase',phase, ...
                'time_ns',round(scheduler.Now*1e9),'local_counter',mac.ReservationCounter, ...
                'neighbor_counter',mac.neighborReservation(2),'data_queue',mac.DataQueueCount, ...
                'transmissions',mac.Counters.Transmissions);
            rows(end+1,1) = row;
            expectedLocal = 16;
            if followsTick || strcmp(phase,'settled'), expectedLocal = 15; end
            if strcmp(phase,'ingress_before')
                expectedNeighbor = 16-double(followsTick);
            elseif strcmp(phase,'ingress_after') || followsTick
                expectedNeighbor = 16;
            else
                expectedNeighbor = 15;
            end
            fields = {'local_counter','neighbor_counter','data_queue','transmissions'};
            targets = [expectedLocal expectedNeighbor 1 0];
            for index = 1:numel(fields)
                actual = double(row.(fields{index}));
                checks(end+1,1) = struct('case',name,'phase',phase,'field',fields{index}, ...
                    'actual',actual,'expected',targets(index),'pass',isfinite(actual) && actual==targets(index));
            end
        end
    end
end

function validatePlan(plan,names)
expected = struct('mac_epoch_ns',1699501000,'boundary_ns',2011501000, ...
    'slot_ns',13000000,'free_slot',16,'neighbor_slot',16,'enqueue_ns',1699501000, ...
    'slot_profile','hist-2014-next-tslot-modulo-probe','active_nodes',3,'slot_range',31, ...
    'early_arm_ns',1989000000,'late_arm_ns',2011500998,'neighbor_reset_ns',2011500995, ...
    'settled_ns',2011501002,'reconstructed_tx_seconds',1.989,'wire_payload_bytes',48, ...
    'rate_kbps',128,'propagation_seconds',.000001);
if ~strcmp(plan.schema,'csr-tranche12-clock-input-v1') || ...
        ~strcmp(plan.source_pin,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b') || ...
        ~isequal(string(plan.cases(:)),string(names(:))) || ~strcmp(plan.preamble,'short') || ...
        numel(fieldnames(plan)) ~= numel(fieldnames(expected))+5
    error('csr:validation:ClockPlan','Unsupported fixed-v1 clock plan.');
end
for field = fieldnames(expected)'
    if ~isfield(plan,field{1}) || ~isequal(plan.(field{1}),expected.(field{1}))
        error('csr:validation:ClockPlan','Unsupported clock input %s.',field{1});
    end
end
end
