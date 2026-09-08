classdef MacHopSimulation < handle
    %MACHOPSIMULATION Integrated CSR PHY, MAC and reliable hop custody.
    % Explicit per-flow paths supply the T2 forwarding boundary. Autonomous
    % route discovery and maintenance belong to the NWK tranche.
    properties (SetAccess = private)
        Config
        Scheduler
        Nodes
        Macs
        Hops
    end
    properties (Access = private)
        Streams
        Engine
        NodeIndex
        Pending
        PumpEvents
        Records
        NextApplicationId = uint64(1)
        NextTransmissionId = uint64(1)
        TraceRows
        TraceCount = 0
        PhyRows
        PhyCount = 0
        FaultMatches
        Counters
        DropReasons
        PhysicalDropReasons
        HasRun = false
    end
    methods
        function obj = MacHopSimulation(config)
            obj.Config = csr.scenario.validate(config);
            config = obj.Config;
            if ~strcmp(config.Stack,'mac-hop') || ~strcmp(config.Channel.Model,'csr-phy')
                error('csr:sim:MacHopBackend','MAC/HOP requires Stack=mac-hop and Channel.Model=csr-phy.');
            end
            if strcmp(config.Backend,'portable')
                obj.Scheduler = csr.sim.EventScheduler(config.MaxEvents);
            else
                obj.Scheduler = csr.sim.NativeScheduler(config.MaxEvents);
            end
            obj.Streams = csr.sim.RandomStreams(config.Seed);
            obj.NodeIndex = containers.Map('KeyType','double','ValueType','double');
            obj.Records = containers.Map('KeyType','char','ValueType','any');
            obj.DropReasons = containers.Map('KeyType','char','ValueType','double');
            obj.PhysicalDropReasons = containers.Map('KeyType','char','ValueType','double');
            n = numel(config.Nodes);
            obj.Nodes = cell(1,n); obj.Macs = cell(1,n); obj.Hops = cell(1,n);
            obj.Pending = cell(1,n); obj.PumpEvents = zeros(1,n,'uint64');
            for k = 1:n
                obj.Nodes{k} = csr.Node(config.Nodes(k));
                obj.NodeIndex(config.Nodes(k).Id) = k;
                obj.Pending{k} = {};
            end
            obj.Counters = struct('Generated',0,'Received',0,'Dropped',0, ...
                'ApplicationBytesReceived',0,'LatencySumSeconds',0, ...
                'PhysicalTransmissions',0,'DataTransmissions',0,'ControlTransmissions',0, ...
                'PhysicalAttempts',0,'PhysicalReceived',0,'PhysicalDropped',0, ...
                'Overheard',0,'Collisions',0,'FaultDrops',0,'QueueDrops',0,'QueueAdmissionRejections',0, ...
                'HopFailures',0,'UnconfirmedHopTransfers',0,'RelayAccepted',0, ...
                'LateDeliveries',0,'LateCustodyRecoveries',0, ...
                'MaxNetworkQueueDepth',0,'OmittedTraceRecords',0,'OmittedPhyTraceRecords',0);
            obj.FaultMatches = zeros(1,numel(config.Faults));
            trace = struct('TimeSeconds',0,'Event','','NodeId',0,'PeerId',0, ...
                'PacketId',uint64(0),'ApplicationBytes',0,'Reason','', ...
                'FrameKind','','Sequence',0,'Dscp',0,'QueueDepth',0);
            obj.TraceRows = repmat(trace,config.Trace.MaxRecords*double(config.Trace.Enabled),1);
            phy = struct('TimeSeconds',0,'Event','','NodeId',0,'SourceId',0, ...
                'DestinationId',0,'PacketId',uint64(0),'RateKeyKbps',0, ...
                'ReceivedPowerDbm',NaN,'PathlossDb',NaN,'SnrDb',NaN, ...
                'NoisePowerWatts',NaN,'JsrDb',NaN,'HeaderBer',NaN,'PayloadBer',NaN, ...
                'HeaderErrors',NaN,'PayloadErrors',NaN,'TotalErrors',NaN, ...
                'CollisionCount',0,'Success',false,'Reason','');
            obj.PhyRows = repmat(phy,config.Trace.MaxPhyRecords*double(config.Trace.Enabled),1);
            obj.Engine = csr.phy.SignalEngine(config,obj.Scheduler,obj.Streams, ...
                @(frame,nodeId,decision)obj.receive(frame,nodeId,decision), ...
                @(event,frame,nodeId,details)obj.recordPhy(event,frame,nodeId,details), ...
                @(nodeId,state)obj.receiverChanged(nodeId,state));
            for k = 1:n
                nodeId = config.Nodes(k).Id;
                macCallbacks = struct('Transmit',@(frame,duration)obj.transmit(frame,duration), ...
                    'Sent',@(frame)obj.sent(nodeId,frame), ...
                    'SetReceiverState',@(state)obj.Engine.setReceiverState(nodeId,state), ...
                    'ReceiverState',@()obj.Engine.state(nodeId), ...
                    'HasSync',@()obj.Engine.hasSync(nodeId), ...
                    'Event',@(event,frame,details)obj.protocolEvent(nodeId,event,frame,details));
                obj.Macs{k} = csr.mac.Layer(nodeId,obj.Scheduler,obj.Streams,config,macCallbacks);
                hopCallbacks = struct('EnqueueMac',@(frame)obj.enqueueMac(nodeId,frame), ...
                    'CancelMac',@(peer,sequence)obj.Macs{k}.cancel(peer,sequence), ...
                    'Deliver',@(app,peer)obj.acceptDelivery(nodeId,app,peer), ...
                    'Terminal',@(app,success,reason)obj.terminal(nodeId,app,success,reason), ...
                    'NsdpRelease',@(app,reason)obj.release(nodeId,app,reason), ...
                    'Wake',@()obj.requestPump(nodeId), ...
                    'NsdpCount',@(app)obj.nsdpCount(nodeId,app), ...
                    'RouteAvailable',@(app)obj.routeAvailable(nodeId,app), ...
                    'Event',@(event,frame,details)obj.protocolEvent(nodeId,event,frame,details));
                obj.Hops{k} = csr.hop.Layer(nodeId,obj.Scheduler,obj.Streams,config,hopCallbacks);
            end
        end

        function result = run(obj)
            if obj.HasRun, error('csr:Simulation:AlreadyRun','Create a fresh simulation for each run.'); end
            obj.HasRun = true;
            runtime = tic;
            for k = 1:numel(obj.Macs), obj.Macs{k}.start(); end
            for k = 1:numel(obj.Config.Traffic)
                flow = obj.Config.Traffic(k);
                if flow.PacketCount > 0 && flow.StartSeconds <= obj.Config.DurationSeconds
                    obj.Scheduler.scheduleAt(flow.StartSeconds,@()obj.generate(k,1));
                end
            end
            obj.Scheduler.run(obj.Config.DurationSeconds);
            elapsed = toc(runtime);
            n = numel(obj.Nodes);
            nodeRows = repmat(struct('Id',0,'Generated',0,'Transmitted',0,'Received',0,'Dropped',0, ...
                'PendingCustody',0,'WaitingForHop',0),n,1);
            macRows = cell(n,1); hopRows = cell(n,1);
            for k = 1:n
                node = obj.Nodes{k}; waiting = 0;
                for j = 1:numel(obj.Pending{k}), waiting = waiting + ~obj.Pending{k}{j}.Submitted; end
                nodeRows(k) = struct('Id',node.Id,'Generated',node.Generated, ...
                    'Transmitted',node.Transmitted,'Received',node.Received,'Dropped',node.Dropped, ...
                    'PendingCustody',numel(obj.Pending{k}),'WaitingForHop',waiting);
                macRows{k} = obj.Macs{k}.Counters;
                macRows{k}.NodeId = node.Id;
                hopRows{k} = obj.Hops{k}.stats();
                hopRows{k}.NodeId = node.Id;
            end
            stats = obj.Counters;
            stats.Transmitted = stats.PhysicalTransmissions;
            stats.Pending = stats.Generated-stats.Received-stats.Dropped;
            stats.PhysicalPending = stats.PhysicalAttempts-stats.PhysicalReceived-stats.PhysicalDropped;
            stats.DeliveryRatio = NaN; stats.MeanLatencySeconds = NaN;
            if stats.Generated > 0, stats.DeliveryRatio = stats.Received/stats.Generated; end
            if stats.Received > 0, stats.MeanLatencySeconds = stats.LatencySumSeconds/stats.Received; end
            stats.GoodputBitsPerSecond = 8*stats.ApplicationBytesReceived/obj.Config.DurationSeconds;
            stats.DropReasons = obj.reasonStruct(obj.DropReasons);
            stats.PhysicalDropReasons = obj.reasonStruct(obj.PhysicalDropReasons);
            hopStats = vertcat(hopRows{:});
            names = {'Retransmissions','AcksReceived','DacksReceived','DuplicateData'};
            sourceNames = {'Retransmissions','Acknowledged','Dacked','Duplicates'};
            for k = 1:numel(names)
                if ~isfield(hopStats,sourceNames{k})
                    error('csr:sim:CounterContract','HOP counter missing: %s',sourceNames{k});
                end
                stats.(names{k}) = sum([hopStats.(sourceNames{k})]);
            end
            metadata = csr.sim.capabilities();
            metadata.SourceCommit = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b';
            metadata.Backend = obj.Config.Backend;
            metadata.ChannelModel = 'csr-phy';
            metadata.ModelStage = 'tranche-2-mac-hop-fixed-path-forwarding';
            metadata.Routing = 'Explicit per-flow paths; autonomous NWK routing not implemented';
            metadata.NativePacketTransportIntegrated = false;
            metadata.Rng = struct('Generator','mt19937ar','MappingVersion',obj.Streams.MappingVersion);
            metadata.Seed = obj.Config.Seed;
            metadata.RuntimeSeconds = elapsed;
            metadata.PendingEvents = obj.Scheduler.PendingCount;
            metadata.FaultInjection = 'Optional deterministic post-PHY receive erasures before MAC/HOP; default none';
            metadata.MetricDefinitions = struct('Received','Unique final-destination application deliveries', ...
                'Dropped','Terminal application loss at current custody owner; excludes feedback failure after delivery', ...
                'Transmitted','OTA aggregate transmissions across all nodes, including control', ...
                'PhysicalTransmissions','OTA aggregate transmissions, including control-only frames', ...
                'PhysicalAttempts','OTA transmission at each non-self receiver', ...
                'Collisions','Completed receiver-signal observations with overlap, not forced packet losses', ...
                'QueueDrops','New source applications dropped by bounded forwarding custody queue', ...
                'QueueAdmissionRejections','Source or relay queue admission refusals, including retried refusals', ...
                'AcksReceived','HOP DATA transactions acknowledged by ACK feedback, not raw ACK frames', ...
                'DacksReceived','HOP DATA transactions accepted through DACK feedback', ...
                'UnconfirmedHopTransfers','Hop feedback failure after custody moved onward or application delivered');
            trace = struct2table(obj.TraceRows(1:obj.TraceCount),'AsArray',true);
            result = struct('Config',obj.Config,'Statistics',stats, ...
                'NodeStatistics',struct2table(nodeRows,'AsArray',true), ...
                'NodeMacStatistics',struct2table(vertcat(macRows{:}),'AsArray',true), ...
                'NodeHopStatistics',struct2table(hopStats,'AsArray',true), ...
                'Trace',trace,'ProtocolTrace',trace, ...
                'PhyTrace',struct2table(obj.PhyRows(1:obj.PhyCount),'AsArray',true), ...
                'Metadata',metadata);
        end
    end
    methods (Access = private)
        function generate(obj,flowIndex,ordinal)
            flow = obj.Config.Traffic(flowIndex);
            app = csr.packet(obj.NextApplicationId,flow,obj.Scheduler.Now,obj.Config.Radio);
            app.FlowIndex = flowIndex; app.FlowOrdinal = ordinal;
            app.Path = flow.Path; app.HopIndex = 1; app.Dscp = flow.Dscp;
            app.AckRequired = flow.AckRequired;
            obj.NextApplicationId = obj.NextApplicationId + uint64(1);
            obj.Counters.Generated = obj.Counters.Generated + 1;
            index = obj.NodeIndex(app.SourceId);
            obj.Nodes{index}.Generated = obj.Nodes{index}.Generated + 1;
            obj.Records(obj.key(app)) = struct('App',app,'Status','pending', ...
                'CustodyNodeId',app.SourceId,'CustodyHopIndex',1,'DropNodeId',0,'DropReason','');
            obj.record('app_generate',app,app.SourceId,app.DestinationId,'',struct());
            if ~obj.enqueue(app.SourceId,app)
                obj.Counters.QueueDrops = obj.Counters.QueueDrops+1;
                obj.dropApplication(app.SourceId,app,'network_queue_full');
            end
            next = flow.StartSeconds + ordinal*flow.IntervalSeconds;
            if ordinal < flow.PacketCount && next <= obj.Config.DurationSeconds
                obj.Scheduler.scheduleAt(next,@()obj.generate(flowIndex,ordinal+1));
            end
        end

        function accepted = enqueue(obj,nodeId,app)
            index = obj.NodeIndex(nodeId);
            accepted = numel(obj.Pending{index}) < obj.Config.NetworkQueueLimit;
            if ~accepted
                obj.Counters.QueueAdmissionRejections = obj.Counters.QueueAdmissionRejections + 1;
                obj.record('network_queue_reject',app,nodeId,app.DestinationId,'network_queue_full',struct());
                return
            end
            peer = app.Path(app.HopIndex+1);
            row = struct('App',app,'PeerId',peer,'Submitted',false);
            position = 1;
            while position <= numel(obj.Pending{index}) && obj.Pending{index}{position}.App.Dscp >= app.Dscp
                position = position+1;
            end
            q = obj.Pending{index}; obj.Pending{index} = [q(1:position-1),{row},q(position:end)];
            obj.Counters.MaxNetworkQueueDepth = max(obj.Counters.MaxNetworkQueueDepth,numel(obj.Pending{index}));
            obj.record('network_enqueue',app,nodeId,peer,'',struct('QueueDepth',numel(obj.Pending{index})));
            obj.requestPump(nodeId);
        end

        function requestPump(obj,nodeId)
            index = obj.NodeIndex(nodeId);
            if obj.PumpEvents(index) ~= 0, return; end
            obj.PumpEvents(index) = obj.Scheduler.scheduleAt(obj.Scheduler.Now,@()obj.pump(nodeId));
        end

        function pump(obj,nodeId)
            index = obj.NodeIndex(nodeId); obj.PumpEvents(index) = uint64(0);
            q = obj.Pending{index};
            % A blocked peer never prevents admission to another eligible peer.
            for k = 1:numel(q)
                if q{k}.Submitted, continue; end
                app = q{k}.App; position = obj.pendingPosition(index,app);
                if position == 0 || obj.Pending{index}{position}.Submitted, continue; end
                if app.AckRequired && ~obj.Hops{index}.canSend(q{k}.PeerId), continue; end
                power = app.TxPowerDbm;
                if isempty(power), power = obj.Config.Nodes(index).RadioProfile.TxPowerDbm; end
                options = struct('Dscp',app.Dscp,'AckRequired',app.AckRequired, ...
                    'RateKeyKbps',app.RateKeyKbps,'TxPowerDbm',power);
                if obj.Hops{index}.send(app,q{k}.PeerId,options)
                    position = obj.pendingPosition(index,app);
                    if position > 0, obj.Pending{index}{position}.Submitted = true; end
                    obj.record('network_submit',app,nodeId,q{k}.PeerId,'',struct());
                end
            end
        end

        function result = acceptDelivery(obj,nodeId,app,previousHop)
            key = obj.key(app);
            if ~isKey(obj.Records,key), error('csr:sim:UnknownApplication','Received an unknown application.'); end
            record = obj.Records(key);
            if strcmp(record.Status,'delivered')
                result = struct('Accepted',true); return
            end
            if nodeId == app.DestinationId
                % Delivery is independent of whether feedback later reaches sender.
                if strcmp(record.Status,'dropped')
                    % A large last-attempt frame can outlast its sender's final
                    % feedback timer. Its actual delivery supersedes that loss.
                    obj.recoverDrop(record);
                    obj.Counters.LateDeliveries = obj.Counters.LateDeliveries+1;
                end
                record.Status = 'delivered'; record.CustodyNodeId = nodeId;
                record.CustodyHopIndex = numel(app.Path);
                obj.Records(key) = record;
                obj.Counters.Received = obj.Counters.Received+1;
                obj.Counters.ApplicationBytesReceived = obj.Counters.ApplicationBytesReceived+app.ApplicationPayloadBytes;
                obj.Counters.LatencySumSeconds = obj.Counters.LatencySumSeconds+obj.Scheduler.Now-app.GeneratedSeconds;
                index = obj.NodeIndex(nodeId); obj.Nodes{index}.Received = obj.Nodes{index}.Received+1;
                obj.record('app_receive',app,nodeId,previousHop,'delivered',struct());
                result = struct('Accepted',true); return
            end
            if record.CustodyHopIndex >= app.HopIndex+1
                % DACK-marked retries reassess feedback but cannot duplicate
                % an accepted application or move onward custody backward.
                result = struct('Accepted',~strcmp(record.Status,'dropped')); return
            end
            onward = app;
            onward.HopIndex = app.HopIndex+1;
            accepted = obj.routeAvailable(nodeId,app) && obj.enqueue(nodeId,onward);
            if accepted
                if strcmp(record.Status,'dropped')
                    % A first late reception at an onward relay can establish
                    % real custody after the prior sender exhausted its timer.
                    obj.recoverDrop(record);
                    obj.Counters.LateCustodyRecoveries = obj.Counters.LateCustodyRecoveries+1;
                    record.Status = 'pending';
                end
                record.CustodyNodeId = nodeId; record.CustodyHopIndex = onward.HopIndex;
                obj.Records(key) = record;
                obj.Counters.RelayAccepted = obj.Counters.RelayAccepted+1;
                obj.record('relay_accept',app,nodeId,previousHop,'',struct());
            elseif ~app.AckRequired
                % Research no-ACK traffic has no remaining resend custodian.
                obj.terminal(previousHop,app,false,'no_ack_relay_refused');
            end
            result = struct('Accepted',accepted);
        end

        function available = routeAvailable(~,nodeId,app)
            next = app.HopIndex+1;
            available = nodeId == app.DestinationId || ...
                (next < numel(app.Path) && app.Path(next) == nodeId);
        end

        function count = nsdpCount(obj,nodeId,app)
            q = obj.Pending{obj.NodeIndex(nodeId)}; count = 0;
            for k = 1:numel(q)
                other = q{k}.App;
                count = count + (other.SourceId == app.SourceId && other.DestinationId == app.DestinationId);
            end
        end

        function release(obj,nodeId,app,reason)
            index = obj.NodeIndex(nodeId); position = obj.pendingPosition(index,app);
            if position > 0
                obj.Pending{index}(position) = [];
                obj.record('network_custody_release',app,nodeId,app.DestinationId,reason,struct());
            end
            obj.requestPump(nodeId);
        end

        function terminal(obj,nodeId,app,success,reason)
            obj.release(nodeId,app,reason);
            if success, return; end
            obj.Counters.HopFailures = obj.Counters.HopFailures+1;
            record = obj.Records(obj.key(app));
            if ~strcmp(record.Status,'pending') || record.CustodyNodeId ~= nodeId
                obj.Counters.UnconfirmedHopTransfers = obj.Counters.UnconfirmedHopTransfers+1;
                obj.record('hop_delivery_unconfirmed',app,nodeId,app.DestinationId,reason,struct());
                return
            end
            obj.dropApplication(nodeId,app,reason);
        end

        function dropApplication(obj,nodeId,app,reason)
            key = obj.key(app); record = obj.Records(key);
            if ~strcmp(record.Status,'pending'), return; end
            record.Status = 'dropped'; record.DropNodeId = nodeId;
            record.DropReason = char(reason); obj.Records(key) = record;
            obj.Counters.Dropped = obj.Counters.Dropped+1;
            index = obj.NodeIndex(nodeId); obj.Nodes{index}.Dropped = obj.Nodes{index}.Dropped+1;
            obj.incrementReason(obj.DropReasons,reason);
            obj.record('app_drop',app,nodeId,app.DestinationId,reason,struct());
        end

        function recoverDrop(obj,record)
            obj.Counters.Dropped = obj.Counters.Dropped-1;
            index = obj.NodeIndex(record.DropNodeId);
            obj.Nodes{index}.Dropped = obj.Nodes{index}.Dropped-1;
            obj.DropReasons(record.DropReason) = obj.DropReasons(record.DropReason)-1;
            if obj.DropReasons(record.DropReason)==0, remove(obj.DropReasons,record.DropReason); end
        end

        function transmit(obj,frame,duration)
            frame.Id = obj.NextTransmissionId;
            obj.NextTransmissionId = obj.NextTransmissionId+uint64(1);
            obj.Counters.PhysicalTransmissions = obj.Counters.PhysicalTransmissions+1;
            obj.Counters.PhysicalAttempts = obj.Counters.PhysicalAttempts+numel(obj.Nodes)-1;
            index = obj.NodeIndex(frame.SourceId);
            obj.Nodes{index}.Transmitted = obj.Nodes{index}.Transmitted+1;
            members = obj.members(frame);
            for k = 1:numel(members)
                if strcmp(members{k}.Kind,'DATA')
                    obj.Counters.DataTransmissions = obj.Counters.DataTransmissions+1;
                else
                    obj.Counters.ControlTransmissions = obj.Counters.ControlTransmissions+1;
                end
            end
            obj.record('tx_start',frame,frame.SourceId,frame.DestinationId,'',struct());
            obj.Engine.transmit(frame,duration);
        end

        function sent(obj,nodeId,frame)
            obj.Hops{obj.NodeIndex(nodeId)}.notifySent(frame);
            % MAC has dequeued before this callback; other peers can now use
            % the freed queue even while this packet awaits feedback.
            obj.requestPump(nodeId);
        end

        function accepted = enqueueMac(obj,nodeId,frame)
            index = obj.NodeIndex(nodeId);
            if isempty(frame.TxPowerDbm)
                frame.TxPowerDbm = obj.Config.Nodes(index).RadioProfile.TxPowerDbm;
            end
            accepted = obj.Macs{index}.enqueue(frame);
        end

        function receive(obj,frame,nodeId,decision)
            if obj.fieldOr(decision,'CollisionCount',0)>0
                obj.Counters.Collisions = obj.Counters.Collisions+1;
            end
            if decision.Success && obj.forceDrop(frame,nodeId)
                decision.Success = false; decision.Reason = 'scripted_receive_erasure';
                obj.Counters.FaultDrops = obj.Counters.FaultDrops+1;
                obj.record('fault_drop',frame,nodeId,frame.SourceId,decision.Reason,struct());
            end
            if decision.Success
                obj.Counters.PhysicalReceived = obj.Counters.PhysicalReceived+1;
            else
                obj.Counters.PhysicalDropped = obj.Counters.PhysicalDropped+1;
                obj.incrementReason(obj.PhysicalDropReasons,decision.Reason);
                members = obj.members(frame);
                for k = 1:numel(members)
                    member = members{k};
                    if member.DestinationId == nodeId && strcmp(member.Kind,'DATA') && ~member.AckRequired
                        obj.terminal(frame.SourceId,member.App,false,'no_ack_receive_loss');
                    end
                end
                return
            end
            index = obj.NodeIndex(nodeId);
            obj.Macs{index}.receive(frame,decision);
            members = obj.members(frame); addressed = false;
            for k = 1:numel(members)
                member = members{k};
                if member.DestinationId == nodeId
                    addressed = true;
                    obj.Hops{index}.receive(member,decision);
                end
            end
            if ~addressed, obj.Counters.Overheard = obj.Counters.Overheard+1; end
        end

        function dropped = forceDrop(obj,frame,nodeId)
            dropped = false; members = obj.members(frame);
            for k = 1:numel(obj.Config.Faults)
                rule = obj.Config.Faults(k);
                if (rule.SourceId >= 0 && rule.SourceId ~= frame.SourceId) || ...
                        (rule.DestinationId >= 0 && rule.DestinationId ~= nodeId) || ...
                        obj.Scheduler.Now < rule.StartSeconds || obj.Scheduler.Now > rule.EndSeconds
                    continue
                end
                match = false;
                for j = 1:numel(members)
                    match = match || (members{j}.DestinationId == nodeId && ...
                        (strcmp(rule.Kind,'*') || strcmp(rule.Kind,members{j}.Kind)));
                end
                if ~match, continue; end
                obj.FaultMatches(k) = obj.FaultMatches(k)+1;
                ordinal = obj.FaultMatches(k);
                if ordinal >= rule.First && ordinal < rule.First+rule.Count
                    dropped = true;
                end
            end
        end

        function receiverChanged(obj,nodeId,state)
            index = obj.NodeIndex(nodeId);
            if ~isempty(obj.Macs{index}), obj.Macs{index}.receiverChanged(state); end
        end

        function protocolEvent(obj,nodeId,event,frame,details)
            peer = obj.fieldOr(frame,'DestinationId',0);
            if any(strcmp(event,{'hop_receive','hop_no_route','hop_custody_refused'}))
                peer = obj.fieldOr(frame,'SourceId',0);
            end
            obj.record(event,frame,nodeId,peer,obj.fieldOr(details,'Reason',''),details);
        end

        function record(obj,event,frame,nodeId,peerId,reason,details)
            if ~obj.Config.Trace.Enabled, return; end
            if obj.TraceCount >= numel(obj.TraceRows)
                obj.Counters.OmittedTraceRecords = obj.Counters.OmittedTraceRecords+1; return
            end
            obj.TraceCount = obj.TraceCount+1;
            app = frame;
            if isfield(frame,'App') && isstruct(frame.App) && ~isempty(frame.App), app = frame.App; end
            obj.TraceRows(obj.TraceCount) = struct('TimeSeconds',obj.Scheduler.Now, ...
                'Event',char(event),'NodeId',nodeId,'PeerId',peerId, ...
                'PacketId',uint64(obj.fieldOr(app,'Id',0)), ...
                'ApplicationBytes',obj.fieldOr(app,'ApplicationPayloadBytes',0), ...
                'Reason',char(reason),'FrameKind',obj.fieldOr(frame,'Kind','APP'), ...
                'Sequence',double(obj.fieldOr(frame,'Sequence',0)), ...
                'Dscp',double(obj.fieldOr(frame,'Dscp',0)), ...
                'QueueDepth',double(obj.fieldOr(details,'QueueDepth',0)));
        end

        function recordPhy(obj,event,frame,nodeId,details)
            if ~obj.Config.Trace.Enabled, return; end
            if obj.PhyCount >= numel(obj.PhyRows)
                obj.Counters.OmittedPhyTraceRecords = obj.Counters.OmittedPhyTraceRecords+1; return
            end
            obj.PhyCount = obj.PhyCount+1; row = obj.PhyRows(obj.PhyCount);
            row.TimeSeconds = obj.Scheduler.Now; row.Event = char(event); row.NodeId = nodeId;
            row.SourceId = frame.SourceId; row.DestinationId = frame.DestinationId;
            row.PacketId = frame.Id; row.RateKeyKbps = frame.RateKeyKbps;
            fields = {'ReceivedPowerDbm','PathlossDb','SnrDb','NoisePowerWatts','JsrDb', ...
                'HeaderBer','PayloadBer','HeaderErrors','PayloadErrors','TotalErrors','CollisionCount'};
            for field = fields, row.(field{1}) = obj.fieldOr(details,field{1},row.(field{1})); end
            row.Success = logical(obj.fieldOr(details,'Success',false));
            row.Reason = char(obj.fieldOr(details,'Reason',''));
            obj.PhyRows(obj.PhyCount) = row;
        end

        function position = pendingPosition(obj,index,app)
            position = 0;
            for k = 1:numel(obj.Pending{index})
                if obj.Pending{index}{k}.App.Id == app.Id, position = k; return; end
            end
        end
    end
    methods (Static, Access = private)
        function key = key(app), key = sprintf('%u',app.Id); end
        function value = fieldOr(item,name,fallback)
            value = fallback;
            if isstruct(item) && isfield(item,name), value = item.(name); end
        end
        function result = members(frame)
            if isfield(frame,'Segments') && ~isempty(frame.Segments), result = frame.Segments;
            else, result = {frame}; end
        end
        function incrementReason(map,reason)
            reason = char(reason);
            if isKey(map,reason), map(reason) = map(reason)+1; else, map(reason) = 1; end
        end
        function result = reasonStruct(map)
            result = struct(); names = sort(keys(map));
            for k = 1:numel(names), result.(matlab.lang.makeValidName(names{k})) = map(names{k}); end
        end
    end
end
