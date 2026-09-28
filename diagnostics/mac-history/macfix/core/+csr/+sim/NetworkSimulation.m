classdef NetworkSimulation < handle
    %NETWORKSIMULATION Integrated autonomous CSR network control and routing.
    % Each node owns independent NWK, HOP and MAC state. The unchanged source
    % signal engine carries all discovery, admission, routing and DATA frames.
    properties (SetAccess = private)
        Config
        Scheduler
        Nodes
        Macs
        Hops
        Networks
    end
    properties (Access = private)
        Streams
        Engine
        NodeIndex
        NodeEnabled
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
        ApplicationGenerators
        AdmissionRows
        AdmissionCount = 0
        LinkObserver = []
        TransportTiming = []
        FeedbackContext = []
        FeedbackQueueEvent = ''
        HasRun = false
    end
    methods
        function obj = NetworkSimulation(config,linkObserver,transportTiming)
            obj.Config = csr.scenario.validate(config);
            config = obj.Config;
            if ~strcmp(config.Stack,'network') || ~strcmp(config.Channel.Model,'csr-phy')
                error('csr:sim:NetworkBackend','NWK requires Stack=network and Channel.Model=csr-phy.');
            end
            % Optional passive instrumentation is external to Config and the
            % packet model. It owns no simulator callback, event or RNG stream.
            if nargin>1 && ~isempty(linkObserver)
                if ~isa(linkObserver,'csr.sim.LinkDiagnostics') || ~isscalar(linkObserver)
                    error('csr:sim:LinkObserver','Expected one csr.sim.LinkDiagnostics observer.');
                end
                linkObserver.attach(config.Mac.AckTransmissions);
                obj.LinkObserver = linkObserver;
            end
            if nargin>2 && ~isempty(transportTiming)
                if ~isa(transportTiming,'csr.sim.TransportTiming') || ~isscalar(transportTiming)
                    error('csr:sim:TransportTiming','Expected one csr.sim.TransportTiming object.');
                end
                if ~strcmp(config.Backend,'portable')
                    error('csr:sim:TransportBackend','Optional transport timing requires the portable backend.');
                end
                obj.TransportTiming=transportTiming;
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
            obj.ApplicationGenerators = cell(1,numel(config.Traffic));
            historical = strcmp(config.ApplicationGenerator,'historical-opnet-gated');
            for k = 1:numel(config.Traffic)
                obj.ApplicationGenerators{k} = csr.sim.ApplicationGenerator(k, ...
                    config.Traffic(k),historical,config.ApplicationFlowLimit);
            end
            obj.AdmissionRows = repmat(csr.sim.ApplicationGenerator.emptyTrace(), ...
                config.Trace.MaxApplicationAdmissionRecords*double(config.Trace.Enabled)*double(historical),1);
            n = numel(config.Nodes);
            obj.Nodes = cell(1,n); obj.Macs = cell(1,n); obj.Hops = cell(1,n);
            obj.Networks = cell(1,n); obj.NodeEnabled = true(1,n);
            for k = 1:n
                obj.Nodes{k} = csr.Node(config.Nodes(k));
                obj.NodeIndex(config.Nodes(k).Id) = k;
            end
            obj.Counters = struct('Generated',0,'Received',0,'Dropped',0, ...
                'ApplicationBytesReceived',0,'LatencySumSeconds',0, ...
                'PhysicalTransmissions',0,'DataTransmissions',0,'ControlTransmissions',0, ...
                'PhysicalAttempts',0,'PhysicalReceived',0,'PhysicalDropped',0, ...
                'Overheard',0,'Collisions',0,'FaultDrops',0,'QueueDrops',0,'QueueAdmissionRejections',0, ...
                'HopFailures',0,'UnconfirmedHopTransfers',0,'UnretainedHopAcks',0,'RelayAccepted',0, ...
                'LateDeliveries',0,'LateCustodyRecoveries',0, ...
                'MaxNetworkQueueDepth',0,'OmittedTraceRecords',0,'OmittedPhyTraceRecords',0, ...
                'OmittedApplicationAdmissionRecords',0);
            obj.FaultMatches = zeros(1,numel(config.Faults));
            trace = struct('TimeSeconds',0,'Event','','NodeId',0,'PeerId',0, ...
                'PacketId',uint64(0),'ApplicationBytes',0,'Reason','', ...
                'FrameKind','','Sequence',0,'Dscp',0,'QueueDepth',0, ...
                'ControlType','','HopCount',0);
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
                @(nodeId,state)obj.receiverChanged(nodeId,state),obj.TransportTiming);
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
                    'CancelMacControl',@(peer,type)obj.Macs{k}.cancelControl(peer,type), ...
                    'Deliver',@(app,peer)obj.receiveData(nodeId,app,peer), ...
                    'ValidateControl',@(control,peer)obj.Networks{k}.validateControl(control,peer), ...
                    'DeliverControl',@(control,peer)obj.Networks{k}.receiveControl(control,peer), ...
                    'ControlResult',@(control,peer,success,complete,remaining) ...
                        obj.Networks{k}.controlResult(control,peer,success,complete,remaining), ...
                    'Terminal',@(app,success,reason)obj.terminal(nodeId,app,success,reason), ...
                    'NsdpRelease',@(app,reason)obj.Networks{k}.releaseFromHop(app,reason), ...
                    'Wake',@()obj.Networks{k}.wake(), ...
                    'NsdpCount',@(app)obj.Networks{k}.nsdpCount(app), ...
                    'RouteAvailable',@(app)obj.Networks{k}.routeAvailable(app), ...
                    'Event',@(event,frame,details)obj.hopEvent(nodeId,event,frame,details));
                if isa(obj.LinkObserver,'csr.sim.AckServiceDiagnostics')
                    hopCallbacks.CancelMac=@(peer,sequence)obj.cancelMacObserved(nodeId,peer,sequence);
                    hopCallbacks.CancelMacControl=@(peer,type)obj.cancelMacControlObserved(nodeId,peer,type);
                end
                obj.Hops{k} = csr.hop.Layer(nodeId,obj.Scheduler,obj.Streams,config,hopCallbacks);
                networkCallbacks = struct('CanSendData',@(peer)obj.Hops{k}.canSend(peer), ...
                    'SendData',@(app,peer,options)obj.Hops{k}.send(app,peer,options), ...
                    'CanSendControl',@(peers)obj.Hops{k}.canSendControl(peers), ...
                    'CancelControl',@(peer,type)obj.Hops{k}.cancelQueuedControl(peer,type), ...
                    'SendControl',@(control,peers,options)obj.Hops{k}.sendControl(control,peers,options), ...
                    'CustodyAccepted',@(app,peer)obj.custodyAccepted(nodeId,app,peer), ...
                    'Delivered',@(app,peer)obj.delivered(nodeId,app,peer), ...
                    'Dropped',@(app,reason)obj.dropApplication(nodeId,app,reason), ...
                    'Event',@(event,frame,details)obj.protocolEvent(nodeId,event,frame,details));
                obj.Networks{k} = csr.nwk.Layer(nodeId,obj.Scheduler,obj.Streams,config,networkCallbacks);
            end
        end

        function result = run(obj)
            if obj.HasRun, error('csr:Simulation:AlreadyRun','Create a fresh simulation for each run.'); end
            obj.HasRun = true;
            runtime = tic;
            % Preserve same-time input order for deterministic RF blackout events.
            for k = 1:numel(obj.Config.LinkEvents)
                event = obj.Config.LinkEvents(k);
                if event.TimeSeconds <= obj.Config.DurationSeconds
                    obj.Scheduler.scheduleAt(event.TimeSeconds,@()obj.linkEvent(event));
                end
            end
            for k = 1:numel(obj.Config.DiscoveryEvents)
                event = obj.Config.DiscoveryEvents(k);
                if event.TimeSeconds <= obj.Config.DurationSeconds
                    obj.Scheduler.scheduleAt(event.TimeSeconds,@()obj.discoveryEvent(event));
                end
            end
            for k = 1:numel(obj.Macs), obj.Macs{k}.start(); end
            for k = 1:numel(obj.Networks), obj.Networks{k}.start(); end
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
            macRows = cell(n,1); hopRows = cell(n,1); nwkRows = cell(n,1);
            routeRows = repmat(struct('NodeId',0,'DestinationId',0,'NextHop',0, ...
                'Capability',0,'HopCount',0,'Cost',0),0,1);
            neighborRows = repmat(struct('NodeId',0,'PeerId',0,'Active',false,'Stale',false),0,1);
            for k = 1:n
                node = obj.Nodes{k}; nwk = obj.Networks{k}.stats();
                nodeRows(k) = struct('Id',node.Id,'Generated',node.Generated, ...
                    'Transmitted',node.Transmitted,'Received',node.Received,'Dropped',node.Dropped, ...
                    'PendingCustody',nwk.PendingCustody,'WaitingForHop',nwk.WaitingForHop);
                macRows{k} = obj.Macs{k}.Counters; macRows{k}.NodeId = node.Id;
                hopRows{k} = obj.Hops{k}.stats(); hopRows{k}.NodeId = node.Id;
                nwkRows{k} = nwk; nwkRows{k}.NodeId = node.Id;
                routes = obj.Networks{k}.routesSnapshot();
                if istable(routes), routes = table2struct(routes); end
                for j = 1:numel(routes)
                    routeRows(end+1,1) = struct('NodeId',node.Id, ...
                        'DestinationId',double(routes(j).DestinationId), ...
                        'NextHop',double(routes(j).NextHop),'Capability',double(routes(j).Capability), ...
                        'HopCount',double(routes(j).HopCount),'Cost',double(routes(j).Cost)); %#ok<AGROW>
                end
                neighbors = obj.Networks{k}.neighborsSnapshot();
                if istable(neighbors), neighbors = table2struct(neighbors); end
                for j = 1:numel(neighbors)
                    neighborRows(end+1,1) = struct('NodeId',node.Id,'PeerId',double(neighbors(j).PeerId), ...
                        'Active',logical(neighbors(j).Active),'Stale',logical(neighbors(j).Stale)); %#ok<AGROW>
                end
            end
            stats = obj.Counters;
            nwkStats = vertcat(nwkRows{:});
            stats.QueueDrops = sum([nwkStats.QueueDrops]);
            stats.QueueAdmissionRejections = sum([nwkStats.QueueAdmissionRejections]);
            stats.MaxNetworkQueueDepth = max([nwkStats.MaxNetworkQueueDepth]);
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
            metadata.ApplicationProfile = obj.Config.ApplicationProfile;
            metadata.ApplicationGenerator = obj.Config.ApplicationGenerator;
            metadata.ApplicationFlowLimit = obj.Config.ApplicationFlowLimit;
            metadata.Backend = obj.Config.Backend;
            metadata.ChannelModel = 'csr-phy';
            metadata.ModelStage = 'tranche-3-autonomous-network-routing';
            metadata.Routing = 'Per-node ARL neighbor admission, autonomous route propagation and forwarding';
            metadata.SecurityProfile = obj.Config.Nwk.SecurityProfile;
            metadata.SecurityAssumption = ['Decoded admission and routing controls are trusted ' ...
                'simulation inputs; no authentication, encryption, keys or replay protection.'];
            metadata.NativePacketTransportIntegrated = false;
            metadata.Rng = struct('Generator','mt19937ar','MappingVersion',obj.Streams.MappingVersion);
            metadata.Seed = obj.Config.Seed;
            metadata.RuntimeSeconds = elapsed;
            metadata.PendingEvents = obj.Scheduler.PendingCount;
            metadata.FaultInjection = 'Optional deterministic post-PHY receive erasures before MAC/HOP/NWK; default none';
            metadata.LinkEvents = 'Post-PHY RF blackout at receive completion; protocol timers keep running';
            metadata.MetricDefinitions = struct('Received','Unique final-destination application deliveries', ...
                'Dropped','Terminal application loss at current custody owner; excludes feedback failure after delivery', ...
                'Transmitted','OTA aggregate transmissions across all nodes, including control', ...
                'PhysicalTransmissions','OTA aggregate transmissions, including control-only frames', ...
                'PhysicalAttempts','OTA transmission at each non-self receiver', ...
                'PhysicalDropped','Failed receiver observations, including optional post-PHY erasures', ...
                'PhyTrace','Raw source PHY decisions plus explicitly named post_phy_drop erasure rows', ...
                'Collisions','Completed receiver-signal observations with overlap, not forced packet losses', ...
                'QueueDrops','New source applications dropped by bounded forwarding custody queue', ...
                'QueueAdmissionRejections','Source or relay queue admission refusals, including retried refusals', ...
                'AcksReceived','HOP DATA transactions acknowledged by ACK feedback, not raw ACK frames', ...
                'DacksReceived','HOP DATA transactions accepted through DACK feedback', ...
                'UnconfirmedHopTransfers','Hop feedback failure after custody moved onward or application delivered', ...
                'UnretainedHopAcks','ACK/DACK completion without onward custody; recorded as loss, recoverable by late reception');
            trace = struct2table(obj.TraceRows(1:obj.TraceCount),'AsArray',true);
            templateGenerator = csr.sim.ApplicationGenerator(0, ...
                struct('SourceId',0,'DestinationId',1),false,0);
            admission = repmat(templateGenerator.Statistics,numel(obj.ApplicationGenerators),1);
            for k = 1:numel(obj.ApplicationGenerators)
                admission(k) = obj.ApplicationGenerators{k}.Statistics;
            end
            result = struct('Config',obj.Config,'Statistics',stats, ...
                'ApplicationAdmissionStatistics',struct2table(admission,'AsArray',true), ...
                'ApplicationAdmissionTrace',struct2table(obj.AdmissionRows(1:obj.AdmissionCount),'AsArray',true), ...
                'NodeStatistics',struct2table(nodeRows,'AsArray',true), ...
                'NodeMacStatistics',struct2table(vertcat(macRows{:}),'AsArray',true), ...
                'NodeHopStatistics',struct2table(hopStats,'AsArray',true), ...
                'NodeNwkStatistics',struct2table(nwkStats,'AsArray',true), ...
                'Routes',struct2table(routeRows,'AsArray',true), ...
                'Neighbors',struct2table(neighborRows,'AsArray',true), ...
                'Trace',trace,'ProtocolTrace',trace, ...
                'PhyTrace',struct2table(obj.PhyRows(1:obj.PhyCount),'AsArray',true), ...
                'Metadata',metadata);
            if ~isempty(obj.TransportTiming)
                result.TransportTiming=obj.TransportTiming.snapshot();
            end
            if ~isempty(obj.LinkObserver)
                observed = obj.LinkObserver.snapshot();
                result.LinkDecisionTrace = observed.LinkDecisionTrace;
                result.ActualFeedbackTrace = observed.ActualFeedbackTrace;
                result.LinkDiagnostics = observed.LinkDiagnostics;
                if isfield(observed,'ServiceTrace')
                    result.ServiceTrace = observed.ServiceTrace;
                    result.ServiceDiagnostics = observed.ServiceDiagnostics;
                end
            end
        end
    end
    methods (Access = private)
        function generate(obj,flowIndex,ordinal)
            flow = obj.Config.Traffic(flowIndex);
            generator = obj.ApplicationGenerators{flowIndex};
            historical = strcmp(obj.Config.ApplicationGenerator,'historical-opnet-gated');
            if ~generator.canAttempt(), return; end
            if historical
                % ns-3 uses integer nanosecond Time and posts the next
                % interrupt before admission. Simulator::Stop runs before
                % recursively posted generator events exactly at the stop.
                next = (round(obj.Scheduler.Now*1e9)+round(flow.IntervalSeconds*1e9))/1e9;
                if ordinal < flow.PacketCount && round(next*1e9) < round(obj.Config.DurationSeconds*1e9)
                    obj.Scheduler.scheduleAt(next,@()obj.generate(flowIndex,ordinal+1));
                end
            end
            index = obj.NodeIndex(flow.SourceId);
            observe = @(destination)obj.Networks{index}.applicationState(destination);
            draw = @()rand(obj.Streams.get(flow.SourceId,'traffic'));
            [accepted,destination,admission] = generator.attempt(obj.Scheduler.Now,observe,draw);
            if ~accepted
                obj.recordAdmission(admission);
                return
            end
            flow.DestinationId = destination;
            app = csr.packet(obj.NextApplicationId,flow,obj.Scheduler.Now,obj.Config.Radio);
            app.FlowIndex = flowIndex; app.FlowOrdinal = ordinal;
            app.HopCount = 0; app.Traversal = app.SourceId; app.Dscp = flow.Dscp;
            app.AckRequired = flow.AckRequired;
            obj.NextApplicationId = obj.NextApplicationId + uint64(1);
            obj.Counters.Generated = obj.Counters.Generated + 1;
            admission.PacketId = app.Id;
            if historical, obj.recordAdmission(admission); end
            obj.Nodes{index}.Generated = obj.Nodes{index}.Generated + 1;
            obj.Records(obj.key(app)) = struct('App',app,'Status','pending', ...
                'CustodyNodeId',app.SourceId,'CustodyHopCount',0,'DropNodeId',0,'DropReason','', ...
                'NoRouteSuppressed',false);
            obj.record('app_generate',app,app.SourceId,app.DestinationId,'',struct());
            obj.Networks{index}.sendApplication(app);
            next = flow.StartSeconds + ordinal*flow.IntervalSeconds;
            if ~historical && ordinal < flow.PacketCount && next <= obj.Config.DurationSeconds
                obj.Scheduler.scheduleAt(next,@()obj.generate(flowIndex,ordinal+1));
            end
        end

        function recordAdmission(obj,row)
            if isa(obj.LinkObserver,'csr.sim.AckServiceDiagnostics')
                obj.LinkObserver.observeAdmission(row);
            end
            if ~obj.Config.Trace.Enabled, return; end
            if obj.AdmissionCount >= numel(obj.AdmissionRows)
                obj.Counters.OmittedApplicationAdmissionRecords = ...
                    obj.Counters.OmittedApplicationAdmissionRecords+1;
                return
            end
            obj.AdmissionCount = obj.AdmissionCount+1;
            obj.AdmissionRows(obj.AdmissionCount) = row;
        end

        function accepted = receiveData(obj,nodeId,app,previousHop)
            [accepted,reason] = obj.Networks{obj.NodeIndex(nodeId)}.receiveData(app,previousHop);
            if ~accepted && any(strcmp(reason,{'inactive_neighbor','transit_disabled'}))
                % Source NWK policy runs after HOP has accepted the DATA and
                % may already have queued the final-destination ACK. Preserve
                % that protocol receipt while recording actual app loss.
                obj.dropApplication(previousHop,app,reason);
                obj.record('network_policy_drop',app,nodeId,previousHop,reason,struct());
                accepted = true;
                return
            end
            if ~accepted && ~app.AckRequired
                % A no-ACK sender has already released HOP ownership and
                % cannot retry a relay's refused custody admission.
                obj.terminal(previousHop,app,false,'no_ack_relay_refused');
            end
        end

        function accepted = delivered(obj,nodeId,app,previousHop)
            key = obj.key(app);
            if ~isKey(obj.Records,key), error('csr:sim:UnknownApplication','Received an unknown application.'); end
            record = obj.Records(key); accepted = true;
            if strcmp(record.Status,'delivered'), return; end
            if nodeId ~= app.DestinationId
                error('csr:sim:DeliveryEndpoint','NWK delivery must be at the final application destination.');
            end
            if strcmp(record.Status,'dropped')
                % A final frame may arrive after its sender's last ACK timer.
                obj.recoverDrop(record);
                obj.Counters.LateDeliveries = obj.Counters.LateDeliveries+1;
            end
            record.Status = 'delivered'; record.CustodyNodeId = nodeId;
            record.CustodyHopCount = max(record.CustodyHopCount,app.HopCount);
            record.App = app;
            obj.Records(key) = record;
            obj.Counters.Received = obj.Counters.Received+1;
            obj.Counters.ApplicationBytesReceived = obj.Counters.ApplicationBytesReceived+app.ApplicationPayloadBytes;
            obj.Counters.LatencySumSeconds = obj.Counters.LatencySumSeconds+obj.Scheduler.Now-app.GeneratedSeconds;
            index = obj.NodeIndex(nodeId); obj.Nodes{index}.Received = obj.Nodes{index}.Received+1;
            obj.record('app_receive',app,nodeId,previousHop,'delivered',struct());
        end

        function custodyAccepted(obj,nodeId,app,previousHop)
            % Called only after NWK retained fresh relay custody and advanced
            % HopCount/Traversal. Feedback loss never transfers custody back.
            key = obj.key(app);
            if ~isKey(obj.Records,key), error('csr:sim:UnknownApplication','Retained an unknown application.'); end
            record = obj.Records(key);
            if strcmp(record.Status,'delivered') || app.HopCount <= record.CustodyHopCount, return; end
            if strcmp(record.Status,'dropped')
                obj.recoverDrop(record);
                obj.Counters.LateCustodyRecoveries = obj.Counters.LateCustodyRecoveries+1;
                record.Status = 'pending';
            end
            record.CustodyNodeId = nodeId; record.CustodyHopCount = app.HopCount;
            record.App = app; record.NoRouteSuppressed = false;
            obj.Records(key) = record;
            obj.Counters.RelayAccepted = obj.Counters.RelayAccepted+1;
            obj.record('relay_accept',app,nodeId,previousHop,'',struct());
        end

        function terminal(obj,nodeId,app,success,reason)
            record = obj.Records(obj.key(app));
            if success && any(strcmp(reason,{'ack','dack_custody'})) && ...
                    strcmp(record.Status,'pending') && record.CustodyNodeId == nodeId
                % Source HOP records a first no-route sequence, so a later
                % duplicate can ACK without ever delivering to NWK. Preserve
                % that wire behavior while accounting the unretained app.
                loss = 'hop_ack_without_custody';
                if record.NoRouteSuppressed, loss = 'hop_no_route_unretained'; end
                obj.Counters.UnretainedHopAcks = obj.Counters.UnretainedHopAcks+1;
                obj.dropApplication(nodeId,app,loss);
            elseif ~success
                obj.Counters.HopFailures = obj.Counters.HopFailures+1;
                if ~strcmp(record.Status,'pending') || record.CustodyNodeId ~= nodeId
                    obj.Counters.UnconfirmedHopTransfers = obj.Counters.UnconfirmedHopTransfers+1;
                    obj.record('hop_delivery_unconfirmed',app,nodeId,app.DestinationId,reason,struct());
                end
            end
            obj.Networks{obj.NodeIndex(nodeId)}.terminal(app,success,reason);
        end

        function dropApplication(obj,nodeId,app,reason)
            key = obj.key(app); record = obj.Records(key);
            % An old sender may exhaust ACK retries after the receiver has
            % accepted custody or delivered. That failure is not app loss.
            if ~strcmp(record.Status,'pending') || record.CustodyNodeId ~= nodeId, return; end
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
            if ~isempty(obj.LinkObserver)
                obj.LinkObserver.observeTransmission(obj.Scheduler.Now,frame);
            end
            obj.Engine.transmit(frame,duration);
        end

        function sent(obj,nodeId,frame)
            obj.Hops{obj.NodeIndex(nodeId)}.notifySent(frame);
            % MAC has dequeued before this callback; other peers can now use
            % the freed queue even while this packet awaits feedback.
            obj.Networks{obj.NodeIndex(nodeId)}.wake();
        end

        function accepted = enqueueMac(obj,nodeId,frame)
            index = obj.NodeIndex(nodeId);
            obj.refreshHistoricalPopulation(index);
            powerDefaulted = isempty(frame.TxPowerDbm);
            if powerDefaulted
                frame.TxPowerDbm = obj.Config.Nodes(index).RadioProfile.TxPowerDbm;
            end
            observe = ~isempty(obj.LinkObserver) && any(strcmp(frame.Kind,{'ACK','DACK'}));
            if observe, obj.FeedbackQueueEvent = ''; end
            accepted = obj.Macs{index}.enqueue(frame);
            if observe
                failures = NaN;
                % This accessor copies existing NWK entries only. It does
                % not call HOP state/admission accessors that create peers.
                peers = obj.Networks{index}.neighborsSnapshot();
                if ~isempty(peers)
                    peerIndex = find([peers.PeerId]==frame.DestinationId,1);
                    if ~isempty(peerIndex), failures = peers(peerIndex).Failures; end
                end
                obj.LinkObserver.observeDecision(obj.Scheduler.Now,frame, ...
                    obj.FeedbackContext,obj.Config.Nodes(index).RadioProfile.TxPowerDbm, ...
                    powerDefaulted,accepted,obj.FeedbackQueueEvent,failures);
                obj.FeedbackQueueEvent = '';
            end
        end

        function receive(obj,frame,nodeId,decision)
            if obj.fieldOr(decision,'CollisionCount',0)>0
                obj.Counters.Collisions = obj.Counters.Collisions+1;
            end
            if decision.Success && (~obj.NodeEnabled(obj.NodeIndex(frame.SourceId)) || ...
                    ~obj.NodeEnabled(obj.NodeIndex(nodeId)))
                decision.Success = false; decision.Reason = 'node_disabled';
                obj.record('link_drop',frame,nodeId,frame.SourceId,decision.Reason,struct());
                obj.recordPhy('post_phy_drop',frame,nodeId,decision);
            elseif decision.Success && obj.forceDrop(frame,nodeId)
                decision.Success = false; decision.Reason = 'scripted_receive_erasure';
                obj.Counters.FaultDrops = obj.Counters.FaultDrops+1;
                obj.record('fault_drop',frame,nodeId,frame.SourceId,decision.Reason,struct());
                obj.recordPhy('post_phy_drop',frame,nodeId,decision);
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
            members = obj.members(frame);
            % Passive HOP radio measurements are distinct from NWK liveness.
            % DATA, ACK and overheard frames update radio metrics without
            % postponing the neighbor freshness deadline. Legacy SNMP skips
            % even this passive observation.
            isSnmp=cellfun(@(member)strcmp(member.Kind,'CONTROL') && ...
                any(strcmp(member.Control.Type,{'SNMP_START','SNMP_DONE'})),members);
            if any(~isSnmp), obj.Networks{index}.observeRadio(frame.SourceId,decision); end
            obj.Macs{index}.receive(frame,decision);
            addressed = false;
            for k = 1:numel(members)
                member = members{k};
                if obj.addressedTo(member,nodeId)
                    addressed = true;
                    if ~isempty(obj.LinkObserver)
                        obj.FeedbackContext = struct('Frame',member, ...
                            'AggregateId',frame.Id,'Decision',decision,'NodeId',nodeId);
                    end
                    obj.Hops{index}.receive(member,decision);
                    if ~isempty(obj.LinkObserver), obj.FeedbackContext = []; end
                    obj.refreshHistoricalPopulation(index);
                end
            end
            if ~addressed, obj.Counters.Overheard = obj.Counters.Overheard+1; end
        end

        function refreshHistoricalPopulation(obj,index)
            if ~strcmp(obj.Config.ApplicationGenerator,'historical-opnet-gated'), return; end
            % Pinned GetActiveNodeCount includes persistent direct NWK peers
            % with a qualifying last-heard marker, including stale peers. It
            % excludes transitive routes and passive DATA/ACK observations.
            state = obj.Networks{index}.applicationState();
            obj.Macs{index}.setActiveNodes(state.ActiveNodeCount);
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
                    member = members{j};
                    memberMatches = obj.addressedTo(member,nodeId) && ...
                        (strcmp(rule.Kind,'*') || strcmp(rule.Kind,member.Kind));
                    controlType = obj.fieldOr(rule,'ControlType','*');
                    if memberMatches && ~isempty(controlType) && ~strcmp(controlType,'*')
                        memberMatches = strcmp(member.Kind,'CONTROL') && ...
                            strcmp(member.Control.Type,controlType);
                    end
                    match = match || memberMatches;
                end
                if ~match, continue; end
                obj.FaultMatches(k) = obj.FaultMatches(k)+1;
                ordinal = obj.FaultMatches(k);
                if ordinal >= rule.First && ordinal < rule.First+rule.Count, dropped = true; end
            end
        end

        function linkEvent(obj,event)
            for nodeId = reshape(double(event.NodeIds),1,[])
                obj.NodeEnabled(obj.NodeIndex(nodeId)) = event.Enabled;
                name = 'link_disable'; if event.Enabled, name = 'link_enable'; end
                obj.record(name,struct(),nodeId,0,'rf_blackout',struct());
            end
        end

        function discoveryEvent(obj,event)
            for nodeId = reshape(double(event.NodeIds),1,[])
                obj.Networks{obj.NodeIndex(nodeId)}.startDiscovery(0,obj.Config.Nwk.DiscoveryDurationSeconds);
                obj.record('discovery_request',struct(),nodeId,0,'scenario_event',struct());
            end
        end

        function receiverChanged(obj,nodeId,state)
            index = obj.NodeIndex(nodeId);
            if ~isempty(obj.Macs{index}), obj.Macs{index}.receiverChanged(state); end
        end

        function hopEvent(obj,nodeId,event,frame,details)
            if strcmp(event,'hop_no_route')
                key = obj.key(frame.App); record = obj.Records(key);
                record.NoRouteSuppressed = true; obj.Records(key) = record;
                if ~frame.AckRequired
                    obj.terminal(frame.SourceId,frame.App,false,'no_ack_no_route');
                end
            end
            obj.protocolEvent(nodeId,event,frame,details);
        end

        function removed = cancelMacObserved(obj,nodeId,peer,sequence)
            mac=obj.Macs{obj.NodeIndex(nodeId)};
            observe=obj.cancellationInWindow();
            if observe
                obj.LinkObserver.observeCancellation(obj.Scheduler.Now,nodeId,'mac_cancel_before', ...
                    peer,sequence,'',NaN,obj.cancellationSnapshot(mac));
            end
            removed=mac.cancel(peer,sequence);
            if observe
                obj.LinkObserver.observeCancellation(obj.Scheduler.Now,nodeId,'mac_cancel_after', ...
                    peer,sequence,'',removed,obj.cancellationSnapshot(mac));
            end
        end

        function removed = cancelMacControlObserved(obj,nodeId,peer,type)
            mac=obj.Macs{obj.NodeIndex(nodeId)};
            observe=obj.cancellationInWindow();
            if observe
                obj.LinkObserver.observeCancellation(obj.Scheduler.Now,nodeId,'mac_control_cancel_before', ...
                    peer,NaN,type,NaN,obj.cancellationSnapshot(mac));
            end
            removed=mac.cancelControl(peer,type);
            if observe
                obj.LinkObserver.observeCancellation(obj.Scheduler.Now,nodeId,'mac_control_cancel_after', ...
                    peer,NaN,type,removed,obj.cancellationSnapshot(mac));
            end
        end

        function inside = cancellationInWindow(obj)
            window=obj.LinkObserver.WindowSeconds;
            inside=obj.Scheduler.Now>=window(1) && obj.Scheduler.Now<window(2);
        end

        function details = cancellationSnapshot(~,mac)
            % These six public scalar reads have no side effects. In
            % particular, the queue-count getters only return numel(queue).
            details=struct('State',mac.State,'PreparationActive',mac.PreparationActive, ...
                'ReservationSlot',mac.ReservationSlot,'ReservationCounter',mac.ReservationCounter, ...
                'DataDepth',mac.DataQueueCount,'AckDepth',mac.AckQueueCount);
        end

        function protocolEvent(obj,nodeId,event,frame,details)
            if isa(obj.LinkObserver,'csr.sim.AckServiceDiagnostics')
                obj.LinkObserver.observeService(obj.Scheduler.Now,nodeId,event,frame,details);
            end
            if ~isempty(obj.LinkObserver) && ...
                    any(strcmp(obj.fieldOr(frame,'Kind',''),{'ACK','DACK'})) && ...
                    any(strcmp(event,{'mac_enqueue','mac_ack_replace','mac_queue_drop'}))
                obj.FeedbackQueueEvent = char(event);
            end
            peer = obj.fieldOr(frame,'DestinationId',0);
            if contains(event,'receive') || any(strcmp(event,{'hop_no_route','hop_custody_refused'}))
                peer = obj.fieldOr(frame,'SourceId',0);
            end
            peer = obj.fieldOr(details,'PeerId',obj.fieldOr(details,'Peer',peer));
            obj.record(event,frame,nodeId,peer,obj.fieldOr(details,'Reason',''),details);
        end

        function record(obj,event,frame,nodeId,peerId,reason,details)
            if ~obj.Config.Trace.Enabled, return; end
            if obj.TraceCount >= numel(obj.TraceRows)
                obj.Counters.OmittedTraceRecords = obj.Counters.OmittedTraceRecords+1; return
            end
            obj.TraceCount = obj.TraceCount+1;
            app = frame;
            kind = obj.fieldOr(frame,'Kind','APP');
            aggregate = strcmp(kind,'AGGREGATE');
            if ~aggregate && isfield(frame,'App') && isstruct(frame.App) && isfield(frame.App,'Id')
                app = frame.App;
            end
            controlType = '';
            if ~aggregate && isfield(frame,'Control')
                controlType = obj.fieldOr(frame.Control,'Type','');
                app = frame.Control;
            elseif isfield(frame,'Type'), controlType = frame.Type; end
            if ~isempty(controlType), kind = 'CONTROL'; end
            obj.TraceRows(obj.TraceCount) = struct('TimeSeconds',obj.Scheduler.Now, ...
                'Event',char(event),'NodeId',nodeId,'PeerId',peerId, ...
                'PacketId',uint64(obj.fieldOr(app,'Id',0)), ...
                'ApplicationBytes',obj.fieldOr(app,'ApplicationPayloadBytes',0), ...
                'Reason',char(reason),'FrameKind',kind, ...
                'Sequence',double(obj.fieldOr(frame,'Sequence',0)), ...
                'Dscp',double(obj.fieldOr(frame,'Dscp',0)), ...
                'QueueDepth',double(obj.fieldOr(details,'QueueDepth',0)), ...
                'ControlType',char(controlType),'HopCount',double(obj.fieldOr(app,'HopCount',0)));
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

    end
    methods (Static, Access = private)
        function addressed = addressedTo(frame,nodeId)
            if strcmp(frame.Kind,'CONTROL')
                peers = double(frame.DestinationIds);
                addressed = any(peers == nodeId) || ...
                    (numel(peers) == 1 && peers(1) == 16777215 && ~frame.AckRequired);
            else
                addressed = frame.DestinationId == nodeId;
            end
        end
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
