classdef Neighbors < handle
    %NEIGHBORS Behavioral ARL admission, local discovery and peer freshness.
    % A control enqueue is never a key-send ACK or a NeighborCheck proof.
    % SecurityProfile identifies a lifecycle model, not cryptographic security.
    properties (SetAccess = private)
        NodeId
        DiscoveryState = 'idle'
        DiscoverySequence = uint32(0)
    end
    properties (Access = private)
        Scheduler
        Config
        Callbacks
        Peers
        PeerOrder = []
        Started = false
        DiscoveryGeneration = 0
        DiscoveryStopEvent = uint64(0)
        DiscoveryTickEvent = uint64(0)
        ChirpPending = false
        Counters
    end
    methods
        function obj = Neighbors(nodeId,scheduler,options,callbacks)
            validPeer(nodeId);
            if nargin<3, options=struct(); end
            if nargin<4, callbacks=struct(); end
            obj.NodeId=double(nodeId); obj.Scheduler=scheduler;
            obj.Config=neighborConfig(options); obj.Callbacks=callbacks;
            obj.Peers=containers.Map('KeyType','double','ValueType','any');
            obj.Counters=struct('DiscoveryStarts',0,'DiscoveryBroadcasts',0, ...
                'DiscoveryCompletions',0,'Chirps',0,'KeyRequests',0, ...
                'KeyUpdates',0,'Checks',0,'Activations',0,'Deactivations',0, ...
                'ControlRejected',0,'StaleCompletions',0);
        end
        function start(obj)
            % Monitoring is opt-in; gateway startup belongs to the NWK layer.
            if obj.Started, return; end
            obj.Started=true;
            if obj.Config.FreshnessEnabled
                obj.Scheduler.scheduleAt(obj.Scheduler.Now+obj.Config.FreshnessPeriodSeconds, ...
                    @()obj.checkFreshness());
            end
        end
        function accepted = startDiscovery(obj,delay,duration)
            if nargin<2, delay=0; end
            if nargin<3, duration=obj.Config.DiscoveryDurationSeconds; end
            validateattributes(delay,{'numeric'},{'scalar','real','finite','nonnegative'});
            validateattributes(duration,{'numeric'},{'scalar','real','finite','positive'});
            accepted=strcmp(obj.DiscoveryState,'idle');
            if ~accepted, return; end
            obj.DiscoveryState='scheduled';
            obj.DiscoveryGeneration=obj.DiscoveryGeneration+1;
            generation=obj.DiscoveryGeneration;
            obj.Scheduler.scheduleAt(obj.Scheduler.Now+delay,@()obj.beginDiscovery(generation));
            obj.DiscoveryStopEvent=obj.Scheduler.scheduleAt(obj.Scheduler.Now+delay+duration, ...
                @()obj.finishDiscovery(generation));
        end
        function observe(obj,peer,metrics)
            validPeer(peer); peer=double(peer);
            if peer==obj.NodeId, return; end
            if nargin<3, metrics=struct(); end
            entry=obj.ensure(peer); entry.LastHeardSeconds=obj.Scheduler.Now;
            entry.Stale=false; entry.Metrics=metrics;
            if ~obj.Config.AdmissionEnabled && ~entry.Active
                entry.Active=true; obj.Peers(peer)=entry;
                obj.changed(peer,true); return
            end
            obj.Peers(peer)=entry;
        end
        function receiveControl(obj,kind,peer,payload)
            validPeer(peer); peer=double(peer);
            if peer==obj.NodeId, return; end
            if nargin<4, payload=struct(); end
            kind=upper(char(kind));
            if ~any(strcmp(kind,{'DISCOVER','KEY_REQUEST','KEY_UPDATE','NEIGHBOR_CHECK'}))
                return
            end
            before=obj.ensure(peer); wasActive=before.Active && ~before.Stale;
            obj.observe(peer,before.Metrics);
            switch kind
                case 'DISCOVER'
                    entry=obj.Peers(peer);
                    subtype=lower(char(value(payload,'Subtype','broadcast')));
                    if strcmp(subtype,'broadcast')
                        sequence=sequenceValue(value(payload,'Sequence',0));
                        if ~entry.DiscoverySequenceValid || newerSequence(sequence,entry.DiscoverySequence)
                            entry.DiscoverySequenceValid=true; entry.DiscoverySequence=sequence;
                            entry.PendingDiscoveryCheck=obj.Config.DiscoveryResponseEnabled;
                            entry.PendingDiscoverySequence=sequence; obj.Peers(peer)=entry;
                            if (entry.SentKey || ~obj.Config.AdmissionEnabled) && obj.Config.DiscoveryResponseEnabled
                                generation=entry.Generation;
                                obj.Scheduler.scheduleAt(obj.Scheduler.Now+obj.Config.ResponseDelaySeconds, ...
                                    @()obj.pendingDiscoveryCheck(peer,generation));
                            end
                        end
                    elseif strcmp(subtype,'chirp') && wasActive && ...
                            ~any(double(value(payload,'ActivePeers',[]))==obj.NodeId)
                        generation=entry.Generation;
                        obj.Scheduler.scheduleAt(obj.Scheduler.Now+obj.Config.ResponseDelaySeconds, ...
                            @()obj.delayedCheck(peer,'verify',uint32(0),generation));
                    end
                    obj.evaluate(peer,true);
                case 'KEY_REQUEST'
                    obj.sendKeyUpdate(peer);
                case 'KEY_UPDATE'
                    entry=obj.Peers(peer); entry.ReceivedKey=true; obj.Peers(peer)=entry;
                    obj.sendKeyUpdate(peer); obj.evaluate(peer,false);
                case 'NEIGHBOR_CHECK'
                    subtype=lower(char(value(payload,'Subtype','message')));
                    if strcmp(subtype,'overheard')
                        obj.ensureMessage(peer);
                    elseif any(strcmp(subtype,{'discovery','message','verify'}))
                        obj.tryActivate(peer,['received_' subtype]);
                    end
                    if strcmp(subtype,'discovery') && strcmp(obj.DiscoveryState,'active') && ...
                            sequenceValue(value(payload,'Sequence',0))==obj.DiscoverySequence
                        entry=obj.Peers(peer); entry.DiscoveryVerified=true; obj.Peers(peer)=entry;
                    end
                    obj.evaluate(peer,false);
            end
        end
        function controlCompleted(obj,kind,peer,payload,success)
            % The transport invokes this only after ACK or final exhaustion.
            validPeer(peer); peer=double(peer);
            if ~isKey(obj.Peers,peer), return; end
            entry=obj.Peers(peer);
            if value(payload,'Generation',entry.Generation)~=entry.Generation
                obj.Counters.StaleCompletions=obj.Counters.StaleCompletions+1; return
            end
            switch upper(char(kind))
                case 'KEY_UPDATE'
                    entry.KeySendActive=false;
                    if success, entry.SentKey=true; end
                    obj.Peers(peer)=entry; obj.evaluate(peer,false);
                    if ~success && ~entry.Active
                        obj.scheduleRetry(peer,max(0,entry.KeySendWhen+entry.KeySendDelay-obj.Scheduler.Now));
                    end
                case 'NEIGHBOR_CHECK'
                    subtype=lower(char(value(payload,'Subtype','message')));
                    entry.CheckActive=false;
                    if strcmp(subtype,'discovery')
                        entry.DiscoveryCheckActive=false;
                        if ~success
                            entry.PendingDiscoveryCheck=true;
                            entry.PendingDiscoverySequence=sequenceValue(value(payload,'Sequence',0));
                        end
                    end
                    obj.Peers(peer)=entry;
                    if success
                        if strcmp(subtype,'verify') && value(payload,'Sequence',0)~=0 && ...
                                sequenceValue(payload.Sequence)~=obj.DiscoverySequence
                            return
                        end
                        entry=obj.Peers(peer); entry.LastHeardSeconds=obj.Scheduler.Now;
                        entry.Stale=false; entry.Failures=max(0,entry.Failures-1);
                        obj.Peers(peer)=entry; obj.tryActivate(peer,['acked_' subtype]);
                    else
                        obj.scheduleRetry(peer,obj.Config.AdmissionRetrySeconds);
                    end
            end
        end
        function yes = isActive(obj,peer)
            yes=false;
            if isKey(obj.Peers,double(peer))
                entry=obj.Peers(double(peer)); yes=entry.Active && ~entry.Stale;
            end
        end
        function peers = activePeers(obj)
            peers=[];
            for peer=obj.PeerOrder
                if obj.isActive(peer), peers(end+1)=peer; end %#ok<AGROW>
            end
        end
        function data = snapshot(obj)
            entries=repmat(emptyPeer(0,obj.Config),0,1);
            for peer=obj.PeerOrder
                entries(end+1,1)=obj.Peers(peer); %#ok<AGROW>
            end
            data=struct('NodeId',obj.NodeId,'DiscoveryState',obj.DiscoveryState, ...
                'DiscoverySequence',obj.DiscoverySequence,'Peers',entries, ...
                'Counters',obj.Counters,'SecurityProfile','behavioral-admission');
        end
        function failNeighbor(obj,peer)
            validPeer(peer); peer=double(peer);
            if ~isKey(obj.Peers,peer), return; end
            entry=obj.Peers(peer); wasActive=entry.Active;
            entry.Active=false; entry.CheckActive=false; entry.DiscoveryCheckActive=false;
            entry.KeySendActive=false; entry.Failures=entry.Failures+1;
            entry.Generation=entry.Generation+1;
            obj.Scheduler.cancel(entry.RetryEvent); entry.RetryEvent=uint64(0);
            obj.Peers(peer)=entry;
            % Always notify: even an inactive reporter may own cached transit routes.
            obj.changed(peer,false);
            if wasActive, obj.scheduleChirp(); end
        end
        function noteInactiveTraffic(obj,peer)
            obj.ensure(peer);
            if ~obj.isActive(peer)
                obj.ensureMessage(peer); obj.evaluate(peer,false);
            end
        end
        function securityReset(obj,peer)
            % Caller must authenticate a changed security count first.
            obj.ensure(peer); obj.failNeighbor(peer); entry=obj.Peers(double(peer));
            entry.ReceivedKey=false; entry.SentKey=false; entry.KeySendValid=false;
            entry.KeyRequestValid=false; entry.DiscoverySequenceValid=false;
            entry.Failures=0; obj.Peers(double(peer))=entry;
        end
    end
    methods (Static)
        function options = defaults()
            options=neighborConfig(struct());
        end
    end
    methods (Access = private)
        function entry = ensure(obj,peer)
            validPeer(peer); peer=double(peer);
            if ~isKey(obj.Peers,peer)
                obj.Peers(peer)=emptyPeer(peer,obj.Config);
                obj.PeerOrder=[peer obj.PeerOrder];
            end
            entry=obj.Peers(peer);
        end
        function beginDiscovery(obj,generation)
            if generation~=obj.DiscoveryGeneration || ~strcmp(obj.DiscoveryState,'scheduled'), return; end
            obj.DiscoveryState='active';
            obj.DiscoverySequence=uint32(mod(double(obj.DiscoverySequence)+1,4294967296));
            if obj.DiscoverySequence==0, obj.DiscoverySequence=uint32(1); end
            for peer=obj.PeerOrder
                entry=obj.Peers(peer); entry.DiscoveryVerified=false; obj.Peers(peer)=entry;
            end
            obj.Counters.DiscoveryStarts=obj.Counters.DiscoveryStarts+1;
            obj.discoveryTick(generation,obj.Config.DiscoveryBroadcastCount);
        end
        function discoveryTick(obj,generation,remaining)
            if generation~=obj.DiscoveryGeneration || ~strcmp(obj.DiscoveryState,'active'), return; end
            if remaining==0, obj.finishDiscovery(generation); return; end
            payload=struct('Subtype','broadcast','Sequence',obj.DiscoverySequence,'ActivePeers',[]);
            obj.send('DISCOVER',16777215,payload,false);
            obj.Counters.DiscoveryBroadcasts=obj.Counters.DiscoveryBroadcasts+1;
            obj.DiscoveryTickEvent=obj.Scheduler.scheduleAt(obj.Scheduler.Now+obj.Config.DiscoveryIntervalSeconds, ...
                @()obj.discoveryTick(generation,remaining-1));
        end
        function finishDiscovery(obj,generation)
            if generation~=obj.DiscoveryGeneration || ~strcmp(obj.DiscoveryState,'active'), return; end
            obj.Scheduler.cancel(obj.DiscoveryTickEvent); obj.Scheduler.cancel(obj.DiscoveryStopEvent);
            obj.DiscoveryState='idle'; obj.Counters.DiscoveryCompletions=obj.Counters.DiscoveryCompletions+1;
            obj.event('discovery_finished',obj.NodeId,struct('Sequence',obj.DiscoverySequence));
            if isfield(obj.Callbacks,'DiscoveryFinished')
                obj.Callbacks.DiscoveryFinished(obj.activePeers());
            end
        end
        function evaluate(obj,peer,receivedDiscovery)
            if ~obj.Config.AdmissionEnabled, return; end
            entry=obj.Peers(peer);
            if entry.Stale || entry.Active, return; end
            now=obj.Scheduler.Now;
            if ~entry.ReceivedKey
                if receivedDiscovery
                    entry.KeyRequestDelay=obj.Config.AdmissionRetrySeconds;
                    entry.KeySendDelay=obj.Config.AdmissionRetrySeconds;
                elseif ~entry.KeyRequestValid || now-entry.KeyRequestWhen>=entry.KeyRequestDelay
                    entry.KeyRequestDelay=2*entry.KeyRequestDelay;
                else
                    obj.scheduleRetry(peer,entry.KeyRequestWhen+entry.KeyRequestDelay-now); return
                end
                entry.KeyRequestValid=true; entry.KeyRequestWhen=now; obj.Peers(peer)=entry;
                obj.Counters.KeyRequests=obj.Counters.KeyRequests+1;
                obj.send('KEY_REQUEST',peer,obj.keyPayload(entry),false);
                obj.scheduleRetry(peer,entry.KeyRequestDelay); return
            end
            if ~entry.SentKey
                if ~entry.KeySendActive && (~entry.KeySendValid || now-entry.KeySendWhen>=entry.KeySendDelay)
                    if entry.KeySendValid, entry.KeySendDelay=2*entry.KeySendDelay; end
                    obj.Peers(peer)=entry; obj.sendKeyUpdate(peer);
                elseif ~entry.KeySendActive
                    obj.scheduleRetry(peer,entry.KeySendWhen+entry.KeySendDelay-now);
                end
                return
            end
            if entry.PendingDiscoveryCheck
                obj.pendingDiscoveryCheck(peer,entry.Generation); return
            end
            if ~entry.CheckActive && (~entry.OverheardValid || now-entry.OverheardWhen>=entry.OverheardDelay)
                entry.OverheardValid=true; entry.OverheardWhen=now;
                entry.OverheardDelay=2*entry.OverheardDelay; obj.Peers(peer)=entry;
                obj.sendCheck(peer,'overheard',uint32(0));
                obj.scheduleRetry(peer,entry.OverheardDelay);
            elseif ~entry.CheckActive
                obj.scheduleRetry(peer,max(0,entry.OverheardWhen+entry.OverheardDelay-now));
            end
        end
        function sendKeyUpdate(obj,peer)
            entry=obj.Peers(peer);
            if entry.SentKey || entry.KeySendActive, return; end
            entry.KeySendActive=true; entry.KeySendValid=true;
            entry.KeySendWhen=obj.Scheduler.Now; obj.Peers(peer)=entry;
            obj.Counters.KeyUpdates=obj.Counters.KeyUpdates+1;
            accepted=obj.send('KEY_UPDATE',peer,obj.keyPayload(entry),true);
            if ~accepted
                entry=obj.Peers(peer); entry.KeySendActive=false; obj.Peers(peer)=entry;
            end
            obj.scheduleRetry(peer,entry.KeySendDelay);
        end
        function pendingDiscoveryCheck(obj,peer,generation)
            entry=obj.Peers(peer);
            if entry.Generation~=generation || ~entry.PendingDiscoveryCheck || ...
                    entry.DiscoveryCheckActive || ~obj.Config.DiscoveryResponseEnabled || ...
                    (obj.Config.AdmissionEnabled && ~entry.SentKey), return; end
            entry.PendingDiscoveryCheck=false; entry.DiscoveryCheckActive=true;
            obj.Peers(peer)=entry;
            obj.sendCheck(peer,'discovery',entry.PendingDiscoverySequence);
        end
        function delayedCheck(obj,peer,subtype,sequence,generation)
            entry=obj.Peers(peer);
            if entry.Generation==generation, obj.sendCheck(peer,subtype,sequence); end
        end
        function ensureMessage(obj,peer)
            entry=obj.Peers(peer);
            if entry.Active || entry.CheckActive || entry.DiscoveryCheckActive, return; end
            obj.sendCheck(peer,'message',uint32(0));
        end
        function sendCheck(obj,peer,subtype,sequence)
            entry=obj.Peers(peer); entry.CheckActive=true; obj.Peers(peer)=entry;
            payload=struct('Subtype',subtype,'Sequence',sequence,'Active',entry.Active, ...
                'Generation',entry.Generation,'SecurityProfile','behavioral-admission');
            obj.Counters.Checks=obj.Counters.Checks+1;
            if ~obj.send('NEIGHBOR_CHECK',peer,payload,true)
                obj.controlCompleted('NEIGHBOR_CHECK',peer,payload,false);
            end
        end
        function tryActivate(obj,peer,reason)
            entry=obj.Peers(peer);
            if entry.Active || (obj.Config.AdmissionEnabled && (~entry.ReceivedKey || ~entry.SentKey))
                return
            end
            entry.Active=true; entry.Stale=false; entry.CheckActive=false;
            entry.DiscoveryCheckActive=false; entry.OverheardDelay=obj.Config.AdmissionRetrySeconds;
            obj.Scheduler.cancel(entry.RetryEvent); entry.RetryEvent=uint64(0);
            obj.Peers(peer)=entry; obj.changed(peer,true);
            obj.event('neighbor_active',peer,struct('Reason',reason));
        end
        function scheduleRetry(obj,peer,delay)
            entry=obj.Peers(peer);
            if entry.Active || entry.Stale, return; end
            obj.Scheduler.cancel(entry.RetryEvent); generation=entry.Generation;
            entry.RetryEvent=obj.Scheduler.scheduleAt(obj.Scheduler.Now+delay, ...
                @()obj.retry(peer,generation)); obj.Peers(peer)=entry;
        end
        function retry(obj,peer,generation)
            entry=obj.Peers(peer);
            if entry.Generation==generation, obj.evaluate(peer,false); end
        end
        function checkFreshness(obj)
            for peer=obj.PeerOrder
                entry=obj.Peers(peer);
                if ~entry.Stale && entry.LastHeardSeconds>=0 && ...
                        obj.Scheduler.Now-entry.LastHeardSeconds>obj.Config.FreshnessTimeoutSeconds
                    obj.failNeighbor(peer); entry=obj.Peers(peer); entry.Stale=true;
                    obj.Peers(peer)=entry;
                end
            end
            obj.Scheduler.scheduleAt(obj.Scheduler.Now+obj.Config.FreshnessPeriodSeconds, ...
                @()obj.checkFreshness());
        end
        function scheduleChirp(obj)
            if obj.ChirpPending, return; end
            obj.ChirpPending=true; obj.Scheduler.scheduleAt(obj.Scheduler.Now,@()obj.sendChirp());
        end
        function sendChirp(obj)
            obj.ChirpPending=false; obj.Counters.Chirps=obj.Counters.Chirps+1;
            obj.send('DISCOVER',16777215,struct('Subtype','chirp', ...
                'Sequence',obj.DiscoverySequence,'ActivePeers',obj.activePeers()),false);
        end
        function payload = keyPayload(~,entry)
            payload=struct('Generation',entry.Generation,'SecurityProfile','behavioral-admission');
        end
        function accepted = send(obj,kind,peers,payload,reliable)
            accepted=false;
            if isfield(obj.Callbacks,'SendControl')
                accepted=logical(obj.Callbacks.SendControl(kind,peers,payload,reliable));
            end
            if ~accepted, obj.Counters.ControlRejected=obj.Counters.ControlRejected+1; end
            obj.event('neighbor_control_send',peers,struct('Kind',kind, ...
                'Reliable',reliable,'Accepted',accepted,'Payload',payload));
        end
        function changed(obj,peer,active)
            if active, obj.Counters.Activations=obj.Counters.Activations+1;
            else, obj.Counters.Deactivations=obj.Counters.Deactivations+1; end
            if isfield(obj.Callbacks,'NeighborChanged'), obj.Callbacks.NeighborChanged(peer,active); end
        end
        function event(obj,name,peer,details)
            if isfield(obj.Callbacks,'Event'), obj.Callbacks.Event(name,peer,details); end
        end
    end
end

function options = neighborConfig(given)
options=struct('AdmissionEnabled',true,'AdmissionRetrySeconds',5, ...
    'DiscoveryIntervalSeconds',5,'DiscoveryBroadcastCount',3, ...
    'DiscoveryDurationSeconds',30,'DiscoveryResponseEnabled',true, ...
    'ResponseDelaySeconds',0.020,'FreshnessEnabled',false, ...
    'FreshnessTimeoutSeconds',20,'FreshnessPeriodSeconds',2);
if ~isstruct(given) || ~isscalar(given)
    error('csr:nwk:InvalidNeighborConfig','Neighbor options must be a scalar struct.');
end
names=fieldnames(given);
for k=1:numel(names)
    if ~isfield(options,names{k})
        error('csr:nwk:UnknownNeighborOption','Unknown neighbor option: %s',names{k});
    end
    options.(names{k})=given.(names{k});
end
for name={'AdmissionEnabled','DiscoveryResponseEnabled','FreshnessEnabled'}
    item=options.(name{1});
    validateattributes(item,{'logical','numeric'},{'scalar','real','finite','>=',0,'<=',1});
    if item~=0 && item~=1, error('csr:nwk:InvalidNeighborConfig','Boolean option must be 0 or 1.'); end
    options.(name{1})=logical(item);
end
for name={'AdmissionRetrySeconds','DiscoveryIntervalSeconds','DiscoveryDurationSeconds', ...
        'FreshnessTimeoutSeconds','FreshnessPeriodSeconds'}
    validateattributes(options.(name{1}),{'numeric'},{'scalar','real','finite','positive'});
end
validateattributes(options.ResponseDelaySeconds,{'numeric'},{'scalar','real','finite','nonnegative'});
validateattributes(options.DiscoveryBroadcastCount,{'numeric'},{'scalar','integer','positive','finite'});
end
function entry = emptyPeer(peer,options)
entry=struct('Id',double(peer),'Active',false,'Stale',false,'LastHeardSeconds',-1, ...
    'Metrics',struct(),'ReceivedKey',false,'SentKey',false,'KeySendActive',false, ...
    'KeyRequestValid',false,'KeyRequestWhen',0,'KeyRequestDelay',options.AdmissionRetrySeconds, ...
    'KeySendValid',false,'KeySendWhen',0,'KeySendDelay',options.AdmissionRetrySeconds, ...
    'OverheardValid',false,'OverheardWhen',0,'OverheardDelay',options.AdmissionRetrySeconds, ...
    'CheckActive',false,'PendingDiscoveryCheck',false,'DiscoveryCheckActive',false, ...
    'PendingDiscoverySequence',uint32(0),'DiscoverySequence',uint32(0), ...
    'DiscoverySequenceValid',false,'DiscoveryVerified',false,'Failures',0, ...
    'Generation',0,'RetryEvent',uint64(0));
end
function result = value(record,name,fallback)
result=fallback;
if isfield(record,name), result=record.(name); end
end
function validPeer(peer)
validateattributes(peer,{'numeric'},{'scalar','real','finite','integer','>=',0,'<=',16777214});
end
function result = sequenceValue(sequence)
validateattributes(sequence,{'numeric'},{'scalar','real','finite','integer','>=',0,'<=',4294967295});
result=uint32(sequence);
end
function yes = newerSequence(incoming,previous)
delta=mod(double(incoming)-double(previous),4294967296);
yes=delta>0 && delta<2147483648;
end
