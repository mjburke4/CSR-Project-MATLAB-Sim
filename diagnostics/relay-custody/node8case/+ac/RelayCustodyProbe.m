classdef RelayCustodyProbe < handle
    %RELAYCUSTODYPROBE Public-boundary NWK/HOP driver; no private state injection.
    % Decoded HOP inputs and sent indications are scripted component stimuli.
    % Captured callbacks observe real queue/custody ownership and HOP windows.
    properties (SetAccess=private)
        Network
        Hop
        Clock
        Config
        Folder
        Owned = {}
        Frames = {}
        Feedback = {}
        Releases = {}
        Terminals = {}
        Delivered = {}
        Drops = {}
        Events = struct('time_s',{},'layer',{},'event',{},'app',{},'details',{})
        Checks = struct('label',{},'passed',{},'actual',{},'expected',{})
    end
    properties
        Blocked = true
        ReenterOnSend = false
        ReentryFrame = []
    end
    methods
        function obj=RelayCustodyProbe(config,folder,candidate,nsdpLimit,nodeId,queueLimit)
            if nargin<4, nsdpLimit=16; end
            if nargin<5, nodeId=4; end
            if nargin<6, queueLimit=512; end
            obj.Folder=folder; if ~isfolder(folder), mkdir(folder); end
            config.Nwk.Neighbor.AdmissionEnabled=false;
            config.Nwk.Neighbor.FreshnessEnabled=false;
            config.Nwk.Neighbor.DiscoveryResponseEnabled=false;
            config.Nwk.StartupMode='manual'; config.Nwk.SendOnlyToGateway=false;
            config.Nwk.AdaptiveLinkControl=false; config.Nwk.QueueLimit=queueLimit;
            config.Hop.NsdpLimit=nsdpLimit; config.Hop.TicSeconds=1e-6;
            config.Hop.MaxResends=0; config.Hop.ResendSeconds=1;
            config.Hop.DackHoldSeconds=2;
            config.Hop.DataQueuedRetryPolicy='native-provisional';
            obj.Config=config; obj.Clock=csr.sim.EventScheduler(10000);
            streams=csr.sim.RandomStreams(config.Seed);
            callbacks=struct('SendControl',@(control,peers,options)true, ...
                'CanSendControl',@(peers)true,'CanSendData',@(peer)obj.canSend(peer), ...
                'SendData',@(app,peer,options)obj.send(app,peer,options), ...
                'CustodyAccepted',@(app,peer)obj.accepted(app,peer), ...
                'Delivered',@(app,peer)obj.delivered(app,peer), ...
                'Dropped',@(app,reason)obj.dropped(app,reason), ...
                'Event',@(name,app,details)obj.event('nwk',name,app,details));
            if candidate
                obj.Network=ac.DiscoveryMembershipNwk(nodeId,obj.Clock,streams,config,callbacks);
            else
                obj.Network=csr.nwk.Layer(nodeId,obj.Clock,streams,config,callbacks);
            end
            hopCallbacks=struct('EnqueueMac',@(frame)obj.enqueue(frame), ...
                'Deliver',@(app,peer)obj.Network.receiveData(app,peer), ...
                'RouteAvailable',@(app)obj.Network.routeAvailable(app), ...
                'NsdpCount',@(app)obj.Network.nsdpCount(app), ...
                'NsdpRelease',@(app,reason)obj.release(app,reason), ...
                'Terminal',@(app,success,reason)obj.terminal(app,success,reason), ...
                'Wake',@()obj.Network.wake(), ...
                'Event',@(name,frame,details)obj.event('hop',name,frame,details));
            if candidate
                obj.Hop=ac.TerminalHop(nodeId,obj.Clock,streams,config.Hop,hopCallbacks);
            else
                obj.Hop=csr.hop.Layer(nodeId,obj.Clock,streams,config.Hop,hopCallbacks);
            end
            for peer=[2 4 8]
                if peer~=nodeId, obj.Network.observe(peer,struct()); end
            end
            obj.Clock.run(0);
            ac.writeJson(fullfile(folder,'configuration.json'),config);
            obj.persist();
        end
        function frame=input(obj,source,id,sequence,destination)
            if nargin<5, destination=2; end
            app=struct('Id',uint64(id),'SourceId',source,'DestinationId',destination, ...
                'GeneratedSeconds',0,'ApplicationPayloadBytes',185,'Dscp',0, ...
                'HopCount',1,'Traversal',[source 8]);
            if source==8, app.HopCount=0; app.Traversal=8; end
            frame=csr.hop.Frames.data(app,8,obj.Network.NodeId,uint16(sequence),struct());
        end
        function receive(obj,frame), obj.Hop.receive(frame); end
        function open(obj)
            obj.Blocked=false; obj.Network.wake(); obj.Clock.run(obj.Clock.Now);
        end
        function advance(obj,seconds), obj.Clock.run(obj.Clock.Now+seconds); end
        function feedback(obj,frame,kind)
            ack=uint64(1); dack=uint64(0);
            if strcmp(kind,'dack'), ack=uint64(0); dack=uint64(1); end
            f=csr.hop.Frames.acknowledgment(frame.DestinationId,obj.Network.NodeId, ...
                frame.Sequence,ack,dack,struct('HasAckWindow',true));
            obj.Hop.receive(f);
        end
        function expect(obj,label,condition,actual,expected)
            obj.Checks(end+1)=struct('label',label,'passed',logical(condition), ...
                'actual',actual,'expected',expected);
            obj.persist();
            assert(condition,'relaycase:CustodyPreflight','%s: actual=%s expected=%s', ...
                label,jsonencode(actual),jsonencode(expected));
        end
        function value=snapshot(obj)
            value=struct('time_s',obj.Clock.Now,'network',obj.Network.stats(), ...
                'hop',obj.Hop.stats(),'accepted_copies',numel(obj.Owned), ...
                'outgoing_copies',numel(obj.Frames),'releases',numel(obj.Releases), ...
                'terminals',numel(obj.Terminals),'unique_delivery_callbacks',numel(obj.Delivered), ...
                'drop_callbacks',numel(obj.Drops));
        end
        function persist(obj)
            ac.writeJson(fullfile(obj.Folder,'public_custody_trace.json'),struct( ...
                'schema','csr-relay-custody-public-trace-v1','state',obj.snapshot(), ...
                'checks',obj.Checks,'owned', {obj.Owned},'frames',{obj.Frames}, ...
                'feedback',{obj.Feedback},'release_callbacks',{obj.Releases}, ...
                'terminal_callbacks',{obj.Terminals},'delivery_callbacks',{obj.Delivered}, ...
                'drop_callbacks',{obj.Drops},'events',obj.Events, ...
                'scope','Real NWK/HOP objects; scripted decoded receives/sent inputs, no RF or physical MAC simulation'));
        end
    end
    methods (Access=private)
        function okay=canSend(obj,peer), okay=~obj.Blocked && obj.Hop.canSend(peer); end
        function okay=send(obj,app,peer,options)
            if obj.ReenterOnSend
                obj.ReenterOnSend=false; obj.Blocked=true;
                obj.Network.releaseFromHop(app,'fixture_reentrant_release');
                obj.Hop.receive(obj.ReentryFrame); okay=false; return
            end
            [okay,~]=obj.Hop.send(app,peer,options);
        end
        function okay=enqueue(obj,frame)
            okay=true;
            if strcmp(frame.Kind,'DATA'), obj.Frames{end+1}=frame;
            else, obj.Feedback{end+1}=frame; end
        end
        function accepted(obj,app,peer)
            obj.Owned{end+1}=app;
            obj.event('callback','custody_accepted',app,struct('previous_hop',peer));
        end
        function okay=delivered(obj,app,peer)
            obj.Delivered{end+1}=app; okay=true;
            obj.event('callback','unique_delivered',app,struct('previous_hop',peer));
        end
        function dropped(obj,app,reason)
            obj.Drops{end+1}=struct('app',app,'reason',reason);
        end
        function release(obj,app,reason)
            obj.Releases{end+1}=struct('app',app,'reason',reason);
            obj.Network.releaseFromHop(app,reason);
        end
        function terminal(obj,app,success,reason)
            obj.Terminals{end+1}=struct('app',app,'success',success,'reason',reason);
            obj.Network.terminal(app,success,reason);
        end
        function event(obj,layer,name,app,details)
            obj.Events(end+1)=struct('time_s',obj.Clock.Now,'layer',layer, ...
                'event',name,'app',app,'details',details);
        end
    end
end
