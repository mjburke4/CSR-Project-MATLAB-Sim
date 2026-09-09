classdef Layer < handle
    %LAYER Autonomous CSR network control and bounded application custody.
    % Routing/control state is driven by received PHY/HOP traffic. No graph
    % oracle or configured flow path is consulted. Security is behavioral.
    properties (SetAccess = private)
        NodeId
        Capability
        TransitForwardingEnabled
    end
    properties (Access = private)
        Scheduler
        Config
        Radio
        Callbacks
        Routes
        Neighbors
        Reassembly
        Metrics
        Seen
        Pending = {}
        Controls = {}
        RoutingBacklog = {}
        NextControlId = uint64(1)
        RoutingSequence = 0
        WakePending = false
        ControlRetryPending = false
        RouteProcessPending = false
        PendingSnapshots = []
        Requests
        NextRequestGeneration = 0
        Started = false
        ScanStarted = false
        ScanComplete = false
        ScanRequesters = []
        ScanRequested = []
        ScanWaiting = []
        ScanGeneration = 0
        Counters
    end
    methods
        function obj = Layer(nodeId,scheduler,streams,fullScenarioConfig,callbacks) %#ok<INUSD>
            obj.NodeId=double(nodeId); obj.Scheduler=scheduler;
            obj.Config=fullScenarioConfig.Nwk; obj.Callbacks=callbacks;
            index=find([fullScenarioConfig.Nodes.Id]==obj.NodeId,1);
            node=fullScenarioConfig.Nodes(index); obj.Capability=double(node.Capability);
            obj.TransitForwardingEnabled=logical(option(node,'TransitForwardingEnabled',true));
            obj.Radio=fullScenarioConfig.Radio;
            if isfield(node,'RadioProfile')
                obj.Radio.TxPowerDbm=node.RadioProfile.TxPowerDbm;
            end
            obj.Routes=csr.nwk.Routes(obj.NodeId,obj.Capability,obj.Config.Routing);
            obj.Reassembly=csr.nwk.Reassembly(obj.Config.Reassembly);
            obj.Metrics=containers.Map('KeyType','double','ValueType','any');
            obj.Seen=containers.Map('KeyType','char','ValueType','logical');
            obj.Requests=containers.Map('KeyType','double','ValueType','any');
            obj.Counters=struct('QueueAdmissionRejections',0,'QueueDrops',0, ...
                'MaxNetworkQueueDepth',0,'RoutingMessagesSent',0,'RoutingMessagesReceived',0, ...
                'RouteChanges',0,'NeighborActivations',0,'NeighborDeactivations',0, ...
                'ControlQueueRejections',0,'ControlFailures',0,'ControlResidualRetries',0, ...
                'MalformedControl',0,'DuplicateApplications',0,'SnapshotTimeouts',0, ...
                'RouteRequests',0,'ScanStartsSent',0,'ScanDoneSent',0,'ScanWatchdogs',0, ...
                'NoPathSent',0,'NoPathReceived',0);
            neighborCallbacks=struct('SendControl',@(kind,peers,payload,reliable) ...
                obj.queueControl(kind,peers,payload,reliable), ...
                'NeighborChanged',@(peer,active)obj.neighborChanged(peer,active), ...
                'DiscoveryFinished',@(peers)obj.discoveryFinished(peers), ...
                'Event',@(name,peer,details)obj.emit(name,struct('DestinationId',peer),details));
            obj.Neighbors=csr.nwk.Neighbors(obj.NodeId,scheduler,obj.Config.Neighbor,neighborCallbacks);
        end

        function start(obj)
            if obj.Started, return; end
            obj.Started=true; obj.Neighbors.start();
            if strcmp(obj.Config.StartupMode,'all') || ...
                    (strcmp(obj.Config.StartupMode,'gateway') && obj.Capability==2)
                obj.Scheduler.scheduleAt(obj.Scheduler.Now+obj.Config.StartupDelaySeconds, ...
                    @()obj.startDiscovery());
            end
            obj.scheduleRoutes();
        end

        function accepted = startDiscovery(obj,delay,duration)
            if nargin<2, delay=0; end
            if nargin<3, duration=obj.Config.DiscoveryDurationSeconds; end
            accepted=false;
            if obj.ScanStarted && ~obj.ScanComplete, return; end
            newEpoch=obj.ScanStarted && obj.ScanComplete;
            obj.ScanStarted=true; obj.ScanComplete=false;
            if newEpoch, obj.ScanRequested=[]; end
            obj.ScanWaiting=[]; obj.ScanGeneration=obj.ScanGeneration+1;
            accepted=obj.Neighbors.startDiscovery(delay,duration);
        end

        function accepted = acceptFromNeighbor(obj,app,peer) %#ok<INUSD>
            accepted=obj.Neighbors.isActive(peer);
            if ~accepted, obj.Neighbors.noteInactiveTraffic(peer); end
        end

        function accepted = sendApplication(obj,app)
            if ~isfield(app,'HopCount'), app.HopCount=0; end
            if ~isfield(app,'Traversal'), app.Traversal=app.SourceId; end
            if app.DestinationId==obj.NodeId
                accepted=obj.deliverLocal(app,obj.NodeId); return
            end
            accepted=obj.enqueueApplication(app);
            if ~accepted
                obj.Counters.QueueDrops=obj.Counters.QueueDrops+1;
                obj.drop(app,'network_queue_full');
            end
        end

        function [accepted,reason] = receiveData(obj,app,previousHop)
            reason='';
            if ~obj.acceptFromNeighbor(app,previousHop)
                accepted=false; reason='inactive_neighbor'; return
            end
            key=appKey(app);
            if isKey(obj.Seen,key)
                obj.Counters.DuplicateApplications=obj.Counters.DuplicateApplications+1;
                accepted=true; return
            end
            traversal=option(app,'Traversal',app.SourceId);
            hops=option(app,'HopCount',0);
            if any(traversal==obj.NodeId)
                accepted=false; reason='routing_loop'; return
            end
            if hops>=obj.Config.MaxHopCount
                accepted=false; reason='hop_limit'; return
            end
            onward=app; onward.HopCount=hops+1; onward.Traversal=[traversal obj.NodeId];
            obj.Routes.learnReverse(app.SourceId,previousHop,obj.Scheduler.Now);
            if app.DestinationId==obj.NodeId
                accepted=obj.deliverLocal(onward,previousHop);
                if ~accepted, reason='local_delivery_refused'; end
                return
            end
            if ~obj.TransitForwardingEnabled
                obj.sendNoPath(previousHop,app.DestinationId);
                accepted=false; reason='transit_disabled'; return
            end
            if ~obj.routeAvailable(onward)
                accepted=false; reason='no_route'; return
            end
            accepted=obj.enqueueApplication(onward);
            if ~accepted, reason='network_queue_full'; end
            if accepted
                obj.Seen(key)=true;
                if isfield(obj.Callbacks,'CustodyAccepted')
                    obj.Callbacks.CustodyAccepted(onward,previousHop);
                end
            end
        end

        function receiveControl(obj,control,peer)
            if ~isstruct(control) || ~isscalar(control) || ...
                    ~all(isfield(control,{'Type','Payload'}))
                obj.Counters.MalformedControl=obj.Counters.MalformedControl+1; return
            end
            kind=upper(char(control.Type)); payload=control.Payload;
            switch kind
                case {'DISCOVER','KEY_REQUEST','KEY_UPDATE','NEIGHBOR_CHECK'}
                    if strcmp(kind,'NEIGHBOR_CHECK') && strcmpi(option(payload,'Subtype',''),'no_path')
                        target=option(payload,'TargetId',16777215);
                        if ~isnumeric(target) || ~isscalar(target) || ~isreal(target) || ...
                                ~isfinite(target) || target<0 || target>16777215 || fix(target)~=target
                            obj.Counters.MalformedControl=obj.Counters.MalformedControl+1; return
                        end
                        obj.Routes.noteNoPath(peer,target,obj.Scheduler.Now);
                        obj.Counters.NoPathReceived=obj.Counters.NoPathReceived+1; obj.wake();
                    end
                    obj.Neighbors.receiveControl(kind,peer,payload);
                case 'ROUTING'
                    if ~obj.Neighbors.isActive(peer), obj.Neighbors.noteInactiveTraffic(peer); end
                    if ~isfield(payload,'Bytes')
                        obj.Counters.MalformedControl=obj.Counters.MalformedControl+1; return
                    end
                    [complete,records,sequence]=obj.Reassembly.accept(peer,payload.Bytes);
                    if ~complete, return; end
                    obj.Counters.RoutingMessagesReceived=obj.Counters.RoutingMessagesReceived+1;
                    effects=obj.Routes.apply(peer,sequence,records,obj.peerCost(peer),obj.Scheduler.Now);
                    if effects.InfoChanged, obj.refreshLink(peer); end
                    if effects.RequestSnapshot, obj.requestSnapshot(peer); end
                    hasFlush=any(cellfun(@(record)strcmp(record.Operation,'FLUSH'),records));
                    if hasFlush && isKey(obj.Requests,double(peer))
                        request=obj.Requests(double(peer)); request.Complete=true;
                        obj.Requests(double(peer))=request;
                    end
                    obj.scheduleRoutes(); obj.wake();
                case 'SNMP_START'
                    if ~ismember(peer,obj.ScanRequesters), obj.ScanRequesters(end+1)=peer; end
                    if ~ismember(peer,obj.ScanRequested), obj.ScanRequested(end+1)=peer; end
                    if obj.ScanComplete
                        obj.sendScanDone(peer);
                    elseif ~obj.ScanStarted
                        obj.startDiscovery(max(0,option(payload,'DelaySeconds',0)));
                    end
                case 'SNMP_DONE'
                    if ~isempty(obj.ScanWaiting) && obj.ScanWaiting==peer
                        obj.ScanWaiting=[]; obj.ScanGeneration=obj.ScanGeneration+1;
                    end
                    obj.advanceScan();
                otherwise
                    obj.Counters.MalformedControl=obj.Counters.MalformedControl+1;
            end
        end

        function controlResult(obj,control,peer,success,complete,remainingPeers) %#ok<INUSD>
            position=obj.controlPosition(control.Id);
            if position==0, return; end
            owner=obj.Controls{position};
            if success, owner.Remaining(owner.Remaining==peer)=[]; end
            obj.Controls{position}=owner;
            if ~complete, return; end
            if success
                obj.Controls(position)=[];
                if any(strcmp(control.Type,{'KEY_UPDATE','NEIGHBOR_CHECK'}))
                    obj.Neighbors.controlCompleted(control.Type,peer,control.Payload,true);
                end
            elseif strcmp(control.Type,'ROUTING') && owner.Cycles<obj.Config.MaxControlCycles
                owner.Remaining=owner.Remaining(ismember(owner.Remaining,obj.Neighbors.activePeers()));
                if isempty(owner.Remaining)
                    obj.Controls(position)=[];
                else
                    owner.Control.Id=obj.nextControlId(); owner.Peers=owner.Remaining;
                    owner.Control.WirePayloadBytes=obj.controlBytes(owner.Control.Type, ...
                        owner.Control.Payload,numel(owner.Peers));
                    owner.Submitted=false; owner.Cycles=owner.Cycles+1;
                    obj.Controls{position}=owner;
                    obj.Counters.ControlResidualRetries=obj.Counters.ControlResidualRetries+1;
                end
            else
                obj.Controls(position)=[]; obj.Counters.ControlFailures=obj.Counters.ControlFailures+1;
                if any(strcmp(control.Type,{'KEY_UPDATE','NEIGHBOR_CHECK'}))
                    obj.Neighbors.controlCompleted(control.Type,peer,control.Payload,false);
                end
            end
            % HOP removes its resend owner after this callback returns.
            obj.wake();
        end

        function observe(obj,peer,decision)
            if peer==obj.NodeId || peer==16777215, return; end
            if isfield(decision,'Success') && ~decision.Success, return; end
            obj.Metrics(double(peer))=decision;
            obj.Neighbors.observe(peer,decision); obj.refreshLink(peer);
        end

        function available = routeAvailable(obj,app)
            if app.DestinationId==obj.NodeId, available=true; return; end
            if option(app,'HopCount',0)>=obj.Config.MaxHopCount, available=false; return; end
            destination=app.DestinationId;
            if obj.Config.SendOnlyToGateway && app.SourceId==obj.NodeId
                gateway=obj.Routes.applicationGateway();
                if isempty(gateway), available=false; return; end
                destination=gateway;
            end
            route=obj.Routes.relay(destination);
            available=~isempty(route) && obj.Neighbors.isActive(route.NextHop);
            if available
                available=~ismember(route.NextHop,option(app,'Traversal',app.SourceId));
            end
        end

        function count = nsdpCount(obj,app)
            count=0;
            for index=1:numel(obj.Pending)
                other=obj.Pending{index}.App;
                count=count+double(other.SourceId==app.SourceId && other.DestinationId==app.DestinationId);
            end
        end

        function release(obj,app,reason)
            position=obj.pendingPosition(app);
            if position>0
                obj.Pending(position)=[];
                obj.emit('network_custody_release',app,struct('Reason',reason));
            end
            obj.wake();
        end

        function terminal(obj,app,success,reason)
            obj.release(app,reason);
            if ~success, obj.drop(app,reason); end
        end

        function wake(obj)
            if obj.WakePending, return; end
            obj.WakePending=true;
            obj.Scheduler.scheduleAt(obj.Scheduler.Now,@()obj.pump());
        end

        function output = stats(obj)
            output=obj.Counters; output.PendingCustody=numel(obj.Pending);
            output.WaitingForHop=0; output.WaitingForRoute=0;
            for index=1:numel(obj.Pending)
                if ~obj.Pending{index}.Submitted
                    output.WaitingForHop=output.WaitingForHop+1;
                    output.WaitingForRoute=output.WaitingForRoute+double(~obj.routeAvailable(obj.Pending{index}.App));
                end
            end
            output.PendingControlMessages=numel(obj.Controls)+numel(obj.RoutingBacklog);
            neighbors=obj.Neighbors.snapshot();
            output.DiscoveryStarts=neighbors.Counters.DiscoveryStarts;
            output.DiscoveryCompletions=neighbors.Counters.DiscoveryCompletions;
        end

        function routes = routesSnapshot(obj)
            routes=obj.Routes.Candidates;
            for index=1:numel(routes)
                selected=obj.Routes.select(routes(index).DestinationId);
                routes(index).Selected=~isempty(selected) && selected.NextHop==routes(index).NextHop;
                routes(index).NodeId=obj.NodeId;
            end
            if ~isempty(routes), routes=routes([routes.Selected]); end
        end

        function peers = neighborsSnapshot(obj)
            data=obj.Neighbors.snapshot(); peers=data.Peers;
            for index=1:numel(peers)
                peers(index).NodeId=obj.NodeId; peers(index).PeerId=peers(index).Id;
            end
        end
    end
    methods (Access = private)
        function accepted = enqueueApplication(obj,app)
            if obj.pendingPosition(app)>0, accepted=true; return; end
            accepted=numel(obj.Pending)<obj.Config.QueueLimit;
            if ~accepted
                obj.Counters.QueueAdmissionRejections=obj.Counters.QueueAdmissionRejections+1;
                obj.emit('network_queue_reject',app,struct('Reason','network_queue_full')); return
            end
            row=struct('App',app,'Submitted',false,'PeerId',NaN);
            % Source NWK pushes every positive DSCP at head; zero appends.
            position=numel(obj.Pending)+1;
            if option(app,'Dscp',0)>0, position=1; end
            obj.Pending=[obj.Pending(1:position-1) {row} obj.Pending(position:end)];
            obj.Counters.MaxNetworkQueueDepth=max(obj.Counters.MaxNetworkQueueDepth,numel(obj.Pending));
            obj.emit('network_enqueue',app,struct('QueueDepth',numel(obj.Pending))); obj.wake();
        end

        function accepted = deliverLocal(obj,app,peer)
            key=appKey(app);
            if isKey(obj.Seen,key), accepted=true; return; end
            accepted=true;
            if isfield(obj.Callbacks,'Delivered'), accepted=logical(obj.Callbacks.Delivered(app,peer)); end
            if accepted, obj.Seen(key)=true; end
        end

        function pump(obj)
            obj.WakePending=false; obj.pumpControls();
            queue=obj.Pending;
            for index=1:numel(queue)
                app=queue{index}.App; position=obj.pendingPosition(app);
                if position==0 || obj.Pending{position}.Submitted || ~obj.routeAvailable(app), continue; end
                if obj.Config.SendOnlyToGateway && app.SourceId==obj.NodeId
                    if ~isfield(app,'RequestedDestinationId'), app.RequestedDestinationId=app.DestinationId; end
                    app.DestinationId=obj.Routes.applicationGateway();
                    obj.Pending{position}.App=app;
                end
                route=obj.Routes.relay(app.DestinationId); peer=route.NextHop;
                if option(app,'AckRequired',true) && isfield(obj.Callbacks,'CanSendData') && ...
                        ~obj.Callbacks.CanSendData(peer), continue; end
                options=obj.radioOptions(peer,app); options.Dscp=option(app,'Dscp',0);
                options.AckRequired=option(app,'AckRequired',true);
                obj.Pending{position}.Submitted=true; obj.Pending{position}.PeerId=peer;
                accepted=false;
                if isfield(obj.Callbacks,'SendData'), accepted=obj.Callbacks.SendData(app,peer,options); end
                position=obj.pendingPosition(app);
                if position>0 && ~accepted, obj.Pending{position}.Submitted=false; end
                if accepted, obj.emit('network_submit',app,struct('PeerId',peer)); end
            end
        end

        function accepted = queueControl(obj,kind,peers,payload,reliable)
            peers=reshape(double(peers),1,[]);
            if isempty(peers), accepted=false; return; end
            if strcmp(kind,'KEY_REQUEST')
                for index=numel(obj.Controls):-1:1
                    old=obj.Controls{index};
                    if ~old.Submitted && strcmp(old.Control.Type,kind) && isequal(old.Peers,peers)
                        obj.Controls(index)=[];
                    end
                end
            end
            accepted=numel(obj.Controls)<obj.Config.ControlQueueLimit;
            if ~accepted
                obj.Counters.ControlQueueRejections=obj.Counters.ControlQueueRejections+1; return
            end
            control=struct('Id',obj.nextControlId(),'Type',char(kind),'Payload',payload, ...
                'WirePayloadBytes',obj.controlBytes(kind,payload,numel(peers)));
            owner=struct('Control',control,'Peers',peers,'Remaining',peers, ...
                'Reliable',logical(reliable),'Submitted',false,'Cycles',1);
            obj.Controls{end+1}=owner; obj.wake();
        end

        function pumpControls(obj)
            obj.materializeRouting();
            ids=cellfun(@(owner)owner.Control.Id,obj.Controls);
            deferred=false;
            for id=ids
                position=obj.controlPosition(id);
                if position==0, continue; end
                owner=obj.Controls{position};
                if owner.Submitted, continue; end
                if strcmp(owner.Control.Type,'ROUTING')
                    owner.Peers=owner.Peers(ismember(owner.Peers,obj.Neighbors.activePeers()));
                    owner.Remaining=owner.Peers;
                    if isempty(owner.Peers), obj.Controls(position)=[]; continue; end
                    owner.Control.WirePayloadBytes=obj.controlBytes('ROUTING',owner.Control.Payload,numel(owner.Peers));
                end
                if owner.Reliable && isfield(obj.Callbacks,'CanSendControl') && ...
                        ~obj.Callbacks.CanSendControl(owner.Peers)
                    obj.Controls{position}=owner; deferred=true; continue
                end
                options=obj.radioOptions(owner.Peers,struct()); options.AckRequired=owner.Reliable;
                owner.Submitted=true; obj.Controls{position}=owner;
                accepted=false;
                if isfield(obj.Callbacks,'SendControl')
                    accepted=obj.Callbacks.SendControl(owner.Control,owner.Peers,options);
                end
                position=obj.controlPosition(id);
                if ~accepted
                    if position>0, obj.Controls{position}.Submitted=false; end
                    deferred=true;
                elseif strcmp(owner.Control.Type,'ROUTING')
                    obj.Counters.RoutingMessagesSent=obj.Counters.RoutingMessagesSent+1;
                end
            end
            if deferred && ~obj.ControlRetryPending
                obj.ControlRetryPending=true;
                obj.Scheduler.scheduleAt(obj.Scheduler.Now+obj.Config.ControlRetrySeconds,@()obj.retryControls());
            end
        end

        function retryControls(obj)
            obj.ControlRetryPending=false; obj.wake();
        end

        function neighborChanged(obj,peer,active)
            if active
                obj.Routes.setNeighbor(peer,true,obj.peerCost(peer),obj.Scheduler.Now);
                obj.Counters.NeighborActivations=obj.Counters.NeighborActivations+1;
                obj.requestSnapshot(peer); obj.startRequest(peer);
                if obj.ScanComplete, obj.advanceScan(); end
            else
                obj.Routes.invalidateNeighbor(peer,obj.Scheduler.Now);
                obj.Counters.NeighborDeactivations=obj.Counters.NeighborDeactivations+1;
                obj.Reassembly.discardPeer(peer);
                obj.PendingSnapshots(obj.PendingSnapshots==peer)=[];
                if isKey(obj.Requests,double(peer)), remove(obj.Requests,double(peer)); end
            end
            obj.scheduleRoutes(); obj.wake();
        end

        function requestSnapshot(obj,peer)
            if ~ismember(peer,obj.PendingSnapshots), obj.PendingSnapshots(end+1)=peer; end
            obj.scheduleRoutes();
        end

        function scheduleRoutes(obj)
            if obj.RouteProcessPending, return; end
            obj.RouteProcessPending=true;
            obj.Scheduler.scheduleAt(obj.Scheduler.Now,@()obj.processRoutes());
        end

        function processRoutes(obj)
            obj.RouteProcessPending=false;
            [changes,changedIds]=obj.Routes.drainChanges();
            obj.Counters.RouteChanges=obj.Counters.RouteChanges+numel(changedIds);
            peers=obj.PendingSnapshots; obj.PendingSnapshots=[];
            peers=peers(ismember(peers,obj.Neighbors.activePeers()));
            if ~isempty(peers), obj.sendRecords(obj.Routes.snapshot(changedIds),peers); end
            if ~isempty(changes), obj.sendRecords(changes,obj.Neighbors.activePeers()); end
        end

        function sendRecords(obj,records,peers)
            if isempty(peers) || isempty(records), return; end
            if numel(obj.RoutingBacklog)>=obj.Config.ControlQueueLimit
                obj.Counters.ControlQueueRejections=obj.Counters.ControlQueueRejections+1;
                obj.emit('routing_backlog_full',struct(),struct('Sequence',obj.RoutingSequence)); return
            end
            sections=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords(records),obj.RoutingSequence);
            groups=ceil(numel(peers)/10);
            obj.RoutingBacklog{end+1}=struct('Sections',{sections},'Peers',peers, ...
                'NextSection',numel(sections),'NextPeer',10*(groups-1)+1);
            obj.RoutingSequence=mod(obj.RoutingSequence+groups,4294967296);
            obj.wake();
        end

        function materializeRouting(obj)
            % Keep section ownership while the shared HOP/control buffers are
            % full. Source visits reversed recipient groups, and then each
            % group's sections in reverse. All groups share the stream seq.
            while ~isempty(obj.RoutingBacklog) && numel(obj.Controls)<obj.Config.ControlQueueLimit
                message=obj.RoutingBacklog{1};
                group=message.Peers(message.NextPeer:min(message.NextPeer+9,numel(message.Peers)));
                group=group(ismember(group,obj.Neighbors.activePeers()));
                if ~isempty(group)
                    obj.queueControl('ROUTING',group, ...
                        struct('Bytes',message.Sections{message.NextSection}),true);
                end
                message.NextSection=message.NextSection-1;
                if message.NextSection<1
                    message.NextPeer=message.NextPeer-10;
                    message.NextSection=numel(message.Sections);
                end
                if message.NextPeer<1, obj.RoutingBacklog(1)=[];
                else, obj.RoutingBacklog{1}=message; end
            end
        end

        function startRequest(obj,peer)
            obj.NextRequestGeneration=obj.NextRequestGeneration+1;
            generation=obj.NextRequestGeneration;
            request=struct('Generation',generation,'Attempts',0,'Complete',false);
            obj.Requests(double(peer))=request; obj.requestTick(peer,generation);
            obj.Scheduler.scheduleAt(obj.Scheduler.Now+obj.Config.SnapshotWatchdogSeconds, ...
                @()obj.snapshotWatchdog(peer,generation));
        end

        function requestTick(obj,peer,generation)
            if ~isKey(obj.Requests,double(peer)) || ~obj.Neighbors.isActive(peer), return; end
            request=obj.Requests(double(peer));
            if request.Generation~=generation || request.Complete || ...
                    request.Attempts>obj.Config.MaxRouteRequests, return; end
            if request.Attempts>0, obj.Reassembly.discardPeer(peer); end
            request.Attempts=request.Attempts+1; obj.Requests(double(peer))=request;
            obj.Counters.RouteRequests=obj.Counters.RouteRequests+1;
            obj.sendRecords({struct('Operation','REQUEST')},peer);
            if request.Attempts<=obj.Config.MaxRouteRequests
                obj.Scheduler.scheduleAt(obj.Scheduler.Now+obj.Config.RouteRequestSeconds, ...
                    @()obj.requestTick(peer,generation));
            end
        end

        function snapshotWatchdog(obj,peer,generation)
            if ~isKey(obj.Requests,double(peer)), return; end
            request=obj.Requests(double(peer));
            if request.Generation~=generation || request.Complete, return; end
            obj.Counters.SnapshotTimeouts=obj.Counters.SnapshotTimeouts+1;
            obj.emit('routing_snapshot_timeout',struct('DestinationId',peer),struct());
            % A missing complete snapshot is an evidence boundary, not proof
            % that otherwise authenticated bidirectional peer traffic failed.
        end

        function discoveryFinished(obj,peers) %#ok<INUSD>
            obj.ScanComplete=true;
            for requester=obj.ScanRequesters, obj.sendScanDone(requester); end
            obj.ScanRequesters=[]; obj.advanceScan();
        end

        function sendScanDone(obj,peer)
            obj.queueControl('SNMP_DONE',peer,struct('Nodes',obj.Neighbors.activePeers()),false);
            obj.Counters.ScanDoneSent=obj.Counters.ScanDoneSent+1;
        end

        function sendNoPath(obj,peer,destination)
            data=obj.Neighbors.snapshot(); generation=0;
            if ~isempty(data.Peers)
                index=find([data.Peers.Id]==peer,1);
                if ~isempty(index), generation=data.Peers(index).Generation; end
            end
            payload=struct('Subtype','no_path','TargetId',destination, ...
                'Sequence',uint32(0),'Generation',generation);
            if obj.queueControl('NEIGHBOR_CHECK',peer,payload,true)
                obj.Counters.NoPathSent=obj.Counters.NoPathSent+1;
            end
        end

        function advanceScan(obj)
            if ~obj.ScanComplete || obj.Capability==0 || ~isempty(obj.ScanWaiting), return; end
            peers=obj.Neighbors.activePeers(); peers=peers(~ismember(peers,obj.ScanRequested));
            if isempty(peers), return; end
            peer=peers(1); obj.ScanRequested(end+1)=peer; obj.ScanWaiting=peer;
            obj.ScanGeneration=obj.ScanGeneration+1; generation=obj.ScanGeneration;
            obj.queueControl('SNMP_START',peer,struct('DelaySeconds',0),false);
            obj.Counters.ScanStartsSent=obj.Counters.ScanStartsSent+1;
            obj.Scheduler.scheduleAt(obj.Scheduler.Now+obj.Config.GatewayWatchdogSeconds, ...
                @()obj.scanWatchdog(generation));
        end

        function scanWatchdog(obj,generation)
            if generation~=obj.ScanGeneration || isempty(obj.ScanWaiting), return; end
            obj.Counters.ScanWatchdogs=obj.Counters.ScanWatchdogs+1;
            obj.ScanWaiting=[]; obj.advanceScan();
        end

        function refreshLink(obj,peer)
            obj.Routes.setNeighbor(peer,obj.Neighbors.isActive(peer),obj.peerCost(peer),obj.Scheduler.Now);
            obj.scheduleRoutes();
        end

        function cost = peerCost(obj,peer)
            [cost,~]=obj.link(peer);
        end

        function [cost,detail] = link(obj,peer)
            cost=1; detail=[];
            if ~isKey(obj.Metrics,double(peer)), return; end
            metric=obj.Metrics(double(peer)); pathloss=option(metric,'PathlossDb',NaN);
            if ~isfinite(pathloss) || pathloss<0, return; end
            local=obj.Config.Routing.LocalInfo;
            limits=struct('MinSpeedKbps',local.MinSpeedKbps,'MaxSpeedKbps',local.MaxSpeedKbps, ...
                'MinPowerDbm',local.MinPowerDbmX10/10,'MaxPowerDbm',local.MaxPowerDbmX10/10, ...
                'LinkMarginDb',local.LinkMarginDbX10/10,'LowPowerDbm',local.LowPowerDbmX10/10);
            % The source retains remote INFO but computes link cost with its
            % local operating limits. No invented intersection policy here.
            failures=0; neighbors=obj.Neighbors.snapshot();
            if ~isempty(neighbors.Peers)
                index=find([neighbors.Peers.Id]==peer,1);
                if ~isempty(index), failures=neighbors.Peers(index).Failures; end
            end
            [cost,detail]=csr.nwk.linkCost(pathloss,failures,limits);
        end

        function options = radioOptions(obj,peers,app)
            options=struct('RateKeyKbps',option(app,'RateKeyKbps',option(obj.Radio,'RateKeyKbps',8)), ...
                'TxPowerDbm',option(app,'TxPowerDbm',option(obj.Radio,'TxPowerDbm',30)));
            options.Preamble=option(app,'Preamble',option(obj.Radio,'Preamble','long'));
            options.EnvelopeProfile=option(app,'EnvelopeProfile',option(obj.Radio,'EnvelopeProfile','bare'));
            if isempty(options.TxPowerDbm), options.TxPowerDbm=option(obj.Radio,'TxPowerDbm',30); end
            if ~obj.Config.AdaptiveLinkControl, return; end
            chosen=Inf; power=[];
            for peer=reshape(peers,1,[])
                [~,detail]=obj.link(peer);
                if isempty(detail), detail=struct('RateKeyKbps',8,'TxPowerDbm',option(obj.Radio,'TxPowerDbm',30)); end
                if detail.RateKeyKbps<chosen
                    chosen=detail.RateKeyKbps; power=detail.TxPowerDbm;
                elseif detail.RateKeyKbps==chosen, power=max(power,detail.TxPowerDbm); end
            end
            options.RateKeyKbps=chosen; options.TxPowerDbm=power;
        end

        function bytes = controlBytes(~,kind,payload,count)
            switch kind
                case 'DISCOVER', body=12+7;
                case 'KEY_REQUEST', body=7;
                case 'KEY_UPDATE', body=51;
                case 'NEIGHBOR_CHECK'
                    body=11+5;
                    if strcmpi(option(payload,'Subtype',''),'no_path'), body=body+3; end
                case 'ROUTING', body=numel(payload.Bytes)+5;
                case {'SNMP_START','SNMP_DONE'}, body=6+3*numel(option(payload,'Nodes',[]));
                otherwise, error('csr:nwk:InvalidControl','Unknown control kind.');
            end
            bytes=17+8+5*(count-1)+body;
        end

        function id = nextControlId(obj)
            id=obj.NextControlId; obj.NextControlId=obj.NextControlId+uint64(1);
        end
        function position = pendingPosition(obj,app)
            position=0;
            for index=1:numel(obj.Pending)
                if strcmp(appKey(obj.Pending{index}.App),appKey(app)), position=index; return; end
            end
        end
        function position = controlPosition(obj,id)
            position=0;
            for index=1:numel(obj.Controls)
                if obj.Controls{index}.Control.Id==id, position=index; return; end
            end
        end
        function drop(obj,app,reason)
            if isfield(obj.Callbacks,'Dropped'), obj.Callbacks.Dropped(app,reason); end
        end
        function emit(obj,name,packet,details)
            if isfield(obj.Callbacks,'Event'), obj.Callbacks.Event(name,packet,details); end
        end
    end
end

function value = option(record,name,fallback)
value=fallback;
if isstruct(record) && isfield(record,name), value=record.(name); end
end
function key = appKey(app)
key=sprintf('%.0f:%u',double(app.SourceId),uint64(app.Id));
end
