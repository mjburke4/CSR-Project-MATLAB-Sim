classdef Simulation < handle
    %SIMULATION Portable direct-link foundation, before CSR MAC/HOP/routing.
    % Transmissions from one node serialize FIFO. Receivers have independent
    % controlled links: overlap, acquisition, interference, and half-duplex
    % behavior are deliberately deferred. This is not MAC or PHY parity.
    properties (SetAccess = private)
        Config
        Nodes
        Scheduler
    end
    properties (Access = private)
        Streams
        Channel
        NextPacketId = uint64(1)
        TraceRows
        TraceCount = 0
        OmittedTraceRecords = 0
        ReceivedBytes = 0
        LatencySumSeconds = 0
        HasRun = false
    end
    methods
        function obj = Simulation(config)
            obj.Config = csr.scenario.validate(config);
            config = obj.Config;
            obj.Scheduler = csr.sim.EventScheduler(config.MaxEvents);
            obj.Streams = csr.sim.RandomStreams(config.Seed);
            obj.Channel = csr.phy.ControlledChannel(config.Channel);
            obj.Nodes = cell(1, numel(config.Nodes));
            for index = 1:numel(config.Nodes)
                obj.Nodes{index} = csr.Node(obj.Config.Nodes(index));
            end
            template = struct('TimeSeconds', 0, 'Event', '', 'NodeId', 0, ...
                'PeerId', 0, 'PacketId', uint64(0), 'ApplicationBytes', 0, 'Reason', '');
            count = config.Trace.MaxRecords * double(config.Trace.Enabled);
            obj.TraceRows = repmat(template, count, 1);
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
                'OmittedTraceRecords', obj.OmittedTraceRecords);
            metadata = csr.sim.capabilities();
            metadata.SourceCommit = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b';
            metadata.Backend = 'portable';
            metadata.ModelStage = 'tranche-0-controlled-transport';
            metadata.RuntimeSeconds = elapsed;
            metadata.Seed = obj.Config.Seed;
            metadata.PendingEvents = obj.Scheduler.PendingCount;
            result = struct('Config', obj.Config, 'Statistics', stats, ...
                'NodeStatistics', struct2table(nodeRows, 'AsArray', true), ...
                'Trace', struct2table(obj.TraceRows(1:obj.TraceCount), 'AsArray', true), 'Metadata', metadata);
        end
    end
    methods (Access = private)
        function node = findNode(obj, id)
            ids = [obj.Config.Nodes.Id];
            node = obj.Nodes{find(ids == id, 1)};
        end
        function generate(obj, flowIndex, ordinal)
            flow = obj.Config.Traffic(flowIndex);
            node = obj.findNode(flow.SourceId);
            frame = csr.packet(obj.NextPacketId, flow, obj.Scheduler.Now, obj.Config.Radio);
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
            tx.Transmitted = tx.Transmitted + 1;
            obj.record('tx_start', frame, tx.Id, rx.Id, '');
            decision = obj.Channel.evaluate(tx.PositionMeters, rx.PositionMeters, obj.Streams.get(rx.Id, 'phy'));
            obj.Scheduler.scheduleAt(obj.Scheduler.Now + duration + decision.DelaySeconds, ...
                @() obj.receive(frame, decision));
        end
        function receive(obj, frame, decision)
            rx = obj.findNode(frame.DestinationId);
            if decision.Success
                rx.Received = rx.Received + 1;
                obj.ReceivedBytes = obj.ReceivedBytes + frame.ApplicationPayloadBytes;
                obj.LatencySumSeconds = obj.LatencySumSeconds + obj.Scheduler.Now - frame.GeneratedSeconds;
                obj.record('app_receive', frame, rx.Id, frame.SourceId, decision.Reason);
            else
                rx.Dropped = rx.Dropped + 1;
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
    end
end
