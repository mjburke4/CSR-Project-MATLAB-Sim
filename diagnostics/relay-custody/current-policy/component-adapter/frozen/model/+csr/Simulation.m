classdef Simulation < handle
    %SIMULATION Configured traffic through controlled or CSR PHY transport.
    % T1 sends physical signals to all non-self nodes and records intended
    % application delivery separately from overhearing. Same-node TX uses
    % FIFO serialization until MAC/HOP access/reliability is integrated in T2.
    properties (SetAccess = private)
        Config
        Nodes
        Scheduler
    end
    properties (Access = private)
        Streams
        Channel
        SignalEngine
        NodeIndex
        NextPacketId = uint64(1)
        TraceRows
        TraceCount = 0
        OmittedTraceRecords = 0
        PhyTraceRows
        PhyTraceCount = 0
        OmittedPhyTraceRecords = 0
        PhysicalAttempts = 0
        PhysicalReceived = 0
        PhysicalDropped = 0
        Overheard = 0
        Collisions = 0
        DropReasons
        PhysicalDropReasons
        ReceivedBytes = 0
        LatencySumSeconds = 0
        HasRun = false
    end
    methods
        function obj = Simulation(config)
            obj.Config = csr.scenario.validate(config);
            config = obj.Config;
            if strcmp(config.Backend,'portable')
                obj.Scheduler = csr.sim.EventScheduler(config.MaxEvents);
            else
                obj.Scheduler = csr.sim.NativeScheduler(config.MaxEvents);
            end
            obj.Streams = csr.sim.RandomStreams(config.Seed);
            obj.DropReasons = containers.Map('KeyType','char','ValueType','double');
            obj.PhysicalDropReasons = containers.Map('KeyType','char','ValueType','double');
            obj.NodeIndex = containers.Map('KeyType','double','ValueType','double');
            obj.Nodes = cell(1, numel(config.Nodes));
            for index = 1:numel(config.Nodes)
                obj.Nodes{index} = csr.Node(obj.Config.Nodes(index));
                obj.NodeIndex(config.Nodes(index).Id) = index;
            end
            template = struct('TimeSeconds', 0, 'Event', '', 'NodeId', 0, ...
                'PeerId', 0, 'PacketId', uint64(0), 'ApplicationBytes', 0, 'Reason', '');
            count = config.Trace.MaxRecords * double(config.Trace.Enabled);
            obj.TraceRows = repmat(template, count, 1);
            phyTemplate = struct('TimeSeconds',0,'Event','','NodeId',0, ...
                'SourceId',0,'DestinationId',0,'PacketId',uint64(0), ...
                'RateKeyKbps',0,'ReceivedPowerDbm',NaN,'PathlossDb',NaN, ...
                'SnrDb',NaN,'NoisePowerWatts',NaN,'JsrDb',NaN, ...
                'HeaderBer',NaN,'PayloadBer',NaN,'HeaderErrors',NaN, ...
                'PayloadErrors',NaN,'TotalErrors',NaN,'CollisionCount',0, ...
                'Success',false,'Reason','');
            phyCount = config.Trace.MaxPhyRecords * double(config.Trace.Enabled);
            obj.PhyTraceRows = repmat(phyTemplate,phyCount,1);
            if strcmp(config.Channel.Model,'csr-phy')
                obj.SignalEngine = csr.phy.SignalEngine(config,obj.Scheduler,obj.Streams, ...
                    @(frame,rxId,decision) obj.receive(frame,rxId,decision), ...
                    @(event,frame,rxId,details) obj.recordPhy(event,frame,rxId,details));
            else
                obj.Channel = csr.phy.ControlledChannel(struct( ...
                    'PropagationSpeedMps',config.Channel.PropagationSpeedMps, ...
                    'FixedDropProbability',config.Channel.FixedDropProbability));
            end
        end
        function result = run(obj)
            if obj.HasRun
                error('csr:Simulation:AlreadyRun', 'Create a new simulation for each experiment.');
            end
            obj.HasRun = true;
            for index = 1:numel(obj.Config.Traffic)
                flow = obj.Config.Traffic(index);
                if flow.PacketCount > 0 && flow.StartSeconds <= obj.Config.DurationSeconds
                    obj.Scheduler.scheduleAt(flow.StartSeconds, @() obj.generate(index, 1));
                end
            end
            runtime = tic;
            obj.Scheduler.run(obj.Config.DurationSeconds);
            elapsed = toc(runtime);
            nodeRows = repmat(struct('Id',0,'Generated',0,'Transmitted',0,'Received',0,'Dropped',0), numel(obj.Nodes), 1);
            for index = 1:numel(obj.Nodes)
                node = obj.Nodes{index};
                nodeRows(index) = struct('Id',node.Id,'Generated',node.Generated, ...
                    'Transmitted',node.Transmitted,'Received',node.Received,'Dropped',node.Dropped);
            end
            generated = sum([nodeRows.Generated]);
            received = sum([nodeRows.Received]);
            dropped = sum([nodeRows.Dropped]);
            pdr = NaN;
            meanLatency = NaN;
            if generated > 0, pdr = received / generated; end
            if received > 0, meanLatency = obj.LatencySumSeconds / received; end
            stats = struct('Generated', generated, 'Transmitted', sum([nodeRows.Transmitted]), ...
                'Received', received, 'Dropped', dropped, ...
                'Pending', generated-received-dropped, ...
                'ApplicationBytesReceived', obj.ReceivedBytes, ...
                'DeliveryRatio', pdr, 'MeanLatencySeconds', meanLatency, ...
                'GoodputBitsPerSecond', 8*obj.ReceivedBytes/obj.Config.DurationSeconds, ...
                'OmittedTraceRecords', obj.OmittedTraceRecords, ...
                'PhysicalAttempts',obj.PhysicalAttempts, ...
                'PhysicalReceived',obj.PhysicalReceived,'PhysicalDropped',obj.PhysicalDropped, ...
                'PhysicalPending',obj.PhysicalAttempts-obj.PhysicalReceived-obj.PhysicalDropped, ...
                'Overheard',obj.Overheard,'Collisions',obj.Collisions, ...
                'DropReasons',obj.reasonStruct(obj.DropReasons), ...
                'PhysicalDropReasons',obj.reasonStruct(obj.PhysicalDropReasons), ...
                'OmittedPhyTraceRecords',obj.OmittedPhyTraceRecords);
            metadata = csr.sim.capabilities();
            metadata.SourceCommit = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b';
            metadata.ApplicationProfile = obj.Config.ApplicationProfile;
            metadata.Backend = obj.Config.Backend;
            metadata.ChannelModel = obj.Config.Channel.Model;
            if strcmp(obj.Config.Channel.Model,'csr-phy')
                metadata.ModelStage = 'tranche-1-csr-phy-always-awake';
            else
                metadata.ModelStage = 'tranche-0-controlled-transport';
            end
            metadata.NativePacketTransportIntegrated = false;
            metadata.CoreTransport = 'CSR signal engine; native backend uses framework clock only';
            metadata.Rng = struct('Generator','mt19937ar','MappingVersion',obj.Streams.MappingVersion);
            metadata.MetricDefinitions = struct('Collisions', ...
                'Completed receiver-signal observations with overlap count above zero; not unique collision pairs', ...
                'PhysicalAttempts','One transmitted packet at one non-self receiver; controlled backend uses destination only', ...
                'DropReasons','Intended application destination failures only', ...
                'GoodputBitsPerSecond','Application bytes delivered times eight divided by full configured duration');
            metadata.RuntimeSeconds = elapsed;
            metadata.Seed = obj.Config.Seed;
            metadata.PendingEvents = obj.Scheduler.PendingCount;
            result = struct('Config', obj.Config, 'Statistics', stats, ...
                'NodeStatistics', struct2table(nodeRows, 'AsArray', true), ...
                'Trace', struct2table(obj.TraceRows(1:obj.TraceCount), 'AsArray', true), ...
                'PhyTrace',struct2table(obj.PhyTraceRows(1:obj.PhyTraceCount),'AsArray',true), ...
                'Metadata', metadata);
        end
    end
    methods (Access = private)
        function node = findNode(obj, id)
            node = obj.Nodes{obj.NodeIndex(double(id))};
        end
        function generate(obj, flowIndex, ordinal)
            flow = obj.Config.Traffic(flowIndex);
            node = obj.findNode(flow.SourceId);
            frame = csr.packet(obj.NextPacketId, flow, obj.Scheduler.Now, obj.Config.Radio);
            frame.FlowIndex = flowIndex;
            frame.FlowOrdinal = ordinal;
            obj.NextPacketId = obj.NextPacketId + uint64(1);
            node.Generated = node.Generated + 1;
            obj.record('app_generate', frame, node.Id, flow.DestinationId, '');
            duration = csr.phy.airtime(frame.WirePayloadBytes, frame.RateKeyKbps, frame.Preamble);
            txStart = max(obj.Scheduler.Now, node.TxAvailableSeconds);
            node.TxAvailableSeconds = txStart + duration;
            obj.Scheduler.scheduleAt(txStart, @() obj.transmit(frame, duration));
            nextTime = flow.StartSeconds + ordinal * flow.IntervalSeconds;
            if ordinal < flow.PacketCount && nextTime <= obj.Config.DurationSeconds
                obj.Scheduler.scheduleAt(nextTime, @() obj.generate(flowIndex, ordinal+1));
            end
        end
        function transmit(obj, frame, duration)
            tx = obj.findNode(frame.SourceId);
            rx = obj.findNode(frame.DestinationId);
            if isempty(frame.TxPowerDbm)
                frame.TxPowerDbm = obj.Config.Nodes(obj.NodeIndex(double(tx.Id))).RadioProfile.TxPowerDbm;
            end
            tx.Transmitted = tx.Transmitted + 1;
            obj.record('tx_start', frame, tx.Id, rx.Id, '');
            if strcmp(obj.Config.Channel.Model,'csr-phy')
                obj.PhysicalAttempts = obj.PhysicalAttempts + numel(obj.Nodes)-1;
                obj.SignalEngine.transmit(frame,duration);
            else
                obj.PhysicalAttempts = obj.PhysicalAttempts + 1;
                decision = obj.Channel.evaluate(tx.PositionMeters, rx.PositionMeters, obj.Streams.get(rx.Id, 'phy'));
                obj.Scheduler.scheduleAt(obj.Scheduler.Now + duration + decision.DelaySeconds, ...
                    @() obj.receive(frame, rx.Id, decision));
            end
        end
        function receive(obj, frame, rxId, decision)
            rx = obj.findNode(rxId);
            if obj.fieldOr(decision,'CollisionCount',0) > 0
                obj.Collisions = obj.Collisions + 1;
            end
            if decision.Success
                obj.PhysicalReceived = obj.PhysicalReceived + 1;
            else
                obj.PhysicalDropped = obj.PhysicalDropped + 1;
                obj.incrementReason(obj.PhysicalDropReasons,decision.Reason);
            end
            if rxId ~= frame.DestinationId
                if decision.Success, obj.Overheard = obj.Overheard + 1; end
                return;
            end
            if decision.Success
                rx.Received = rx.Received + 1;
                obj.ReceivedBytes = obj.ReceivedBytes + frame.ApplicationPayloadBytes;
                obj.LatencySumSeconds = obj.LatencySumSeconds + obj.Scheduler.Now - frame.GeneratedSeconds;
                obj.record('app_receive', frame, rx.Id, frame.SourceId, decision.Reason);
            else
                rx.Dropped = rx.Dropped + 1;
                obj.incrementReason(obj.DropReasons,decision.Reason);
                obj.record('rx_drop', frame, rx.Id, frame.SourceId, decision.Reason);
            end
        end
        function record(obj, event, frame, nodeId, peerId, reason)
            if ~obj.Config.Trace.Enabled, return; end
            if obj.TraceCount >= numel(obj.TraceRows)
                obj.OmittedTraceRecords = obj.OmittedTraceRecords + 1;
                return;
            end
            obj.TraceCount = obj.TraceCount + 1;
            obj.TraceRows(obj.TraceCount) = struct('TimeSeconds', obj.Scheduler.Now, ...
                'Event', event, 'NodeId', nodeId, 'PeerId', peerId, ...
                'PacketId', frame.Id, 'ApplicationBytes', frame.ApplicationPayloadBytes, 'Reason', reason);
        end
        function recordPhy(obj,event,frame,rxId,details)
            if ~obj.Config.Trace.Enabled, return; end
            if obj.PhyTraceCount >= numel(obj.PhyTraceRows)
                obj.OmittedPhyTraceRecords = obj.OmittedPhyTraceRecords + 1;
                return;
            end
            obj.PhyTraceCount = obj.PhyTraceCount + 1;
            row = obj.PhyTraceRows(obj.PhyTraceCount);
            row.TimeSeconds = obj.Scheduler.Now;
            row.Event = char(event);
            row.NodeId = rxId;
            row.SourceId = frame.SourceId;
            row.DestinationId = frame.DestinationId;
            row.PacketId = frame.Id;
            row.RateKeyKbps = frame.RateKeyKbps;
            fields = {'ReceivedPowerDbm','PathlossDb','SnrDb','NoisePowerWatts', ...
                'JsrDb','HeaderBer','PayloadBer','HeaderErrors','PayloadErrors','TotalErrors','CollisionCount'};
            for field = fields
                row.(field{1}) = obj.fieldOr(details,field{1},row.(field{1}));
            end
            row.Success = logical(obj.fieldOr(details,'Success',false));
            row.Reason = char(obj.fieldOr(details,'Reason',''));
            obj.PhyTraceRows(obj.PhyTraceCount) = row;
        end
        function incrementReason(~,map,reason)
            reason = char(reason);
            if isKey(map,reason), map(reason) = map(reason) + 1;
            else, map(reason) = 1; end
        end
        function result = reasonStruct(~,map)
            result = struct();
            names = sort(keys(map));
            for index = 1:numel(names)
                result.(matlab.lang.makeValidName(names{index})) = map(names{index});
            end
        end
        function value = fieldOr(~,item,name,default)
            value = default;
            if isfield(item,name), value = item.(name); end
        end
    end
end
