classdef Layer < handle
    %LAYER CSR DATA custody, cumulative feedback and HOP-owned retries.
    % Protocol state is independent of a PHY or MATLAB release. EnqueueMac
    % admits one logical frame; notifySent must report its actual TX instant.
    % PendingThreshold=16 is a source threshold, permitting pending=17.
    properties (SetAccess = private)
        NodeId
        PendingDataCount = 0
    end
    properties (Access = private)
        Scheduler
        Config
        Callbacks
        Flows
        LastSequences
        ReceiveWindows
        Resends
        ResendOrder = {}
        DackHolds
        DackOrder = {}
        WakePending = false
        Counters
    end
    methods
        function obj = Layer(nodeId,scheduler,streams,config,callbacks) %#ok<INUSD>
            validateattributes(nodeId,{'numeric'},{'scalar','integer','>=',0,'<=',16777214});
            obj.NodeId=double(nodeId); obj.Scheduler=scheduler;
            if nargin<5, callbacks=struct(); end
            obj.Callbacks=callbacks; obj.Config=hopConfig(config);
            obj.Flows=containers.Map('KeyType','double','ValueType','any');
            obj.LastSequences=containers.Map('KeyType','double','ValueType','double');
            obj.ReceiveWindows=containers.Map('KeyType','double','ValueType','any');
            obj.Resends=containers.Map('KeyType','char','ValueType','any');
            obj.DackHolds=containers.Map('KeyType','char','ValueType','any');
            obj.Counters=struct('Admitted',0,'AdmissionBlocked',0, ...
                'MacAdmissionRejected',0,'ResendQueueOverflow',0,'Transmitted',0, ...
                'Retransmissions',0,'Acknowledged',0,'Dacked',0,'Failed',0, ...
                'DataReceived',0,'Duplicates',0,'Delivered',0,'CustodyRefused',0, ...
                'NoRouteSuppressed',0,'AckGenerated',0,'DackGenerated',0, ...
                'FeedbackQueueDrops',0,'FeedbackReceived',0,'UnknownFeedback',0, ...
                'DackExpired',0,'QueueWakes',0,'PeakPendingData',0);
        end
        function allowed = canSend(obj,peer)
            s=obj.admission(peer); allowed=s.GlobalAllowed && s.NeighborAllowed ...
                && obj.Resends.Count<obj.Config.ResendQueueLimit;
        end
        function s = admission(obj,peer)
            fc=obj.flow(double(peer));
            s=struct('PendingData',obj.PendingDataCount, ...
                'PendingThreshold',obj.Config.PendingThreshold, ...
                'GlobalSpare',obj.Config.PendingThreshold-obj.PendingDataCount+1, ...
                'NeighborOutstanding',fc.Outstanding,'NeighborThreshold',fc.Threshold, ...
                'NeighborSpare',fc.Threshold-fc.Outstanding+1, ...
                'GlobalAllowed',obj.PendingDataCount<=obj.Config.PendingThreshold, ...
                'NeighborAllowed',fc.Outstanding<=fc.Threshold);
        end
        function [accepted,frame] = send(obj,app,peer,options)
            if nargin<4, options=struct(); end
            peer=double(peer); frame=[];
            validateattributes(peer,{'numeric'},{'scalar','integer','>=',0,'<=',16777214});
            ackRequired=readOption(options,'AckRequired',true);
            if ackRequired && ~obj.canSend(peer)
                obj.increment('AdmissionBlocked');
                if obj.Resends.Count>=obj.Config.ResendQueueLimit
                    obj.increment('ResendQueueOverflow');
                end
                accepted=false; return
            end
            last=0; if isKey(obj.LastSequences,peer), last=obj.LastSequences(peer); end
            sequence=mod(last+1,65536); obj.LastSequences(peer)=sequence;
            frame=obj.makeData(app,peer,uint16(sequence),options);
            if ackRequired
                key=entryKey(peer,sequence);
                e=struct('Frame',frame,'Peer',peer,'Sequence',uint16(sequence), ...
                    'ResendCount',0,'LastTxSeconds',Inf,'Confirmed',false);
                obj.Resends(key)=e; obj.ResendOrder{end+1}=key;
                fc=obj.flow(peer); fc.Outstanding=fc.Outstanding+1; obj.Flows(peer)=fc;
                obj.PendingDataCount=obj.PendingDataCount+1;
            end
            accepted=obj.enqueue(frame);
            if ~accepted
                obj.increment('MacAdmissionRejected');
                if ackRequired
                    obj.removeResend(key); obj.releaseCapacity(peer);
                end
                return
            end
            obj.increment('Admitted');
            obj.Counters.PeakPendingData=max(obj.Counters.PeakPendingData,obj.PendingDataCount);
            obj.emit('hop_admit',frame,obj.admission(peer));
        end
        function notifySent(obj,frame)
            % HOP never starts an initial ACK clock at MAC queue admission.
            if ~strcmp(frame.Kind,'DATA'), return; end
            obj.increment('Transmitted');
            if ~frame.AckRequired
                obj.terminal(frame.App,true,'sent_no_ack'); return
            end
            key=entryKey(frame.DestinationId,frame.Sequence);
            if ~isKey(obj.Resends,key), return; end
            e=obj.Resends(key); e.LastTxSeconds=obj.Scheduler.Now; e.Confirmed=true;
            obj.Resends(key)=e;
            wait=obj.Config.ResendSeconds;
            if e.ResendCount>=obj.Config.MaxResends, wait=2*wait; end
            obj.Scheduler.scheduleAt(obj.Scheduler.Now+wait+obj.Config.TicSeconds, ...
                @()obj.checkResends());
            obj.emit('hop_sent',frame,struct('ResendCount',e.ResendCount, ...
                'AckWaitSeconds',wait));
        end
        function receive(obj,frame,decision)
            if nargin>=3 && ~isempty(decision) && isfield(decision,'Success') && ~decision.Success
                return
            end
            if double(frame.DestinationId)~=obj.NodeId, return; end
            switch upper(frame.Kind)
                case 'DATA'
                    obj.receiveData(frame);
                case {'ACK','DACK'}
                    obj.receiveFeedback(frame);
            end
        end
        function s = stats(obj)
            s=obj.Counters;
            s.PendingData=obj.PendingDataCount;
            s.ResendQueueDepth=double(obj.Resends.Count);
            s.DackHoldCount=double(obj.DackHolds.Count);
        end
        function s = state(obj,peer)
            s=obj.admission(peer); fc=obj.flow(double(peer));
            s.AckCount=fc.AckCount;
            s.ReceiveWindow=emptyWindow();
            if isKey(obj.ReceiveWindows,double(peer))
                s.ReceiveWindow=obj.ReceiveWindows(double(peer));
            end
            s.ResendQueueDepth=double(obj.Resends.Count);
            s.DackHoldCount=double(obj.DackHolds.Count);
        end
    end
    methods (Static)
        function config = defaults()
            config=hopConfig(struct());
        end
    end
    methods (Access = private)
        function frame = makeData(obj,app,peer,sequence,options)
            % Shared frame construction adds no observation metadata on air.
            for name={'RateKeyKbps','TxPowerDbm','Preamble','EnvelopeProfile'}
                if ~isfield(options,name{1}) && isfield(app,name{1})
                    options.(name{1})=app.(name{1});
                end
            end
            frame=csr.hop.Frames.data(app,obj.NodeId,peer,sequence,options);
        end
        function frame = makeAck(obj,received,window,isDack)
            options=struct('RateKeyKbps',received.RateKeyKbps, ...
                'TxPowerDbm',[],'Preamble','short');
            if isfield(received,'EnvelopeProfile')
                options.EnvelopeProfile=received.EnvelopeProfile;
            end
            frame=csr.hop.Frames.acknowledgment(obj.NodeId,received.SourceId, ...
                uint16(window.Highest),window.AckBitmap,window.DackBitmap,options);
            if isDack, frame.Kind='DACK'; end
        end
        function receiveData(obj,frame)
            obj.increment('DataReceived');
            src=double(frame.SourceId);
            [first,window]=obj.checkSequence(src,frame.Sequence);
            if ~first, obj.increment('Duplicates'); end
            local=double(frame.App.DestinationId)==obj.NodeId;
            before=obj.nsdpCount(frame.App);
            if first && ~local && ~obj.routeAvailable(frame.App)
                % Current ns-3 records the receive sequence before this gate.
                % A retry is consequently ACKed as a duplicate.
                obj.increment('NoRouteSuppressed');
                obj.emit('hop_no_route',frame,struct('FirstReception',true,'NsdpBefore',before));
                return
            end
            dack=frame.AckRequired && first && ~local && before>=obj.Config.NsdpLimit;
            if dack
                window=obj.markDack(src,frame.Sequence,window);
            end
            feedback=[];
            if frame.AckRequired, feedback=obj.makeAck(frame,window,dack); end
            % Receiver final delivery ACK precedes its NWK callback; relay
            % custody precedes feedback admission, matching br_hop ordering.
            if local && ~isempty(feedback), obj.enqueueFeedback(feedback); end
            accepted=true;
            if first
                accepted=obj.deliver(frame.App,src);
                if accepted, obj.increment('Delivered'); end
            end
            if ~accepted
                obj.increment('CustodyRefused');
                if ~local
                    obj.unmarkSequence(src,frame.Sequence);
                    obj.emit('hop_custody_refused',frame,struct('NsdpBefore',before));
                    return
                end
                % Final delivery should not refuse after an ACK. Fail loud
                % rather than silently acknowledging data it did not retain.
                error('csr:hop:LocalCustodyRefused','Local Deliver callback refused an ACKed packet.');
            end
            if ~local && ~isempty(feedback), obj.enqueueFeedback(feedback); end
            obj.emit('hop_receive',frame,struct('FirstReception',first, ...
                'IsDack',dack,'LocalDelivery',local,'NsdpBefore',before, ...
                'NsdpAfter',obj.nsdpCount(frame.App)));
        end
        function enqueueFeedback(obj,frame)
            if strcmp(frame.Kind,'DACK'), obj.increment('DackGenerated');
            else, obj.increment('AckGenerated'); end
            if ~obj.enqueue(frame), obj.increment('FeedbackQueueDrops'); end
        end
        function receiveFeedback(obj,frame)
            obj.increment('FeedbackReceived');
            if frame.HasAckWindow
                ack=frame.AckBitmap; dack=bitand(frame.DackBitmap,bitcmp(ack));
                for bit=1:64
                    if bitget(ack,bit) || bitget(dack,bit)
                        sequence=uint16(mod(double(frame.Sequence)-(bit-1),65536));
                        obj.complete(double(frame.SourceId),sequence,logical(bitget(dack,bit)));
                    end
                end
                % Complete every custody change before cancelling MAC copies.
                for bit=1:64
                    if bitget(ack,bit) || bitget(dack,bit)
                        obj.cancelMac(frame.SourceId,uint16(mod(double(frame.Sequence)-(bit-1),65536)));
                    end
                end
            elseif strcmp(frame.Kind,'ACK')
                obj.complete(double(frame.SourceId),frame.Sequence,false);
                obj.cancelMac(frame.SourceId,frame.Sequence);
            end
            % Source single-DACK path is disabled. Even unknown/single-DACK
            % feedback requests one coalesced NWK wake at the next TIC.
            obj.scheduleWake();
        end
        function complete(obj,peer,sequence,isDack)
            key=entryKey(peer,sequence);
            if ~isKey(obj.Resends,key), obj.increment('UnknownFeedback'); return; end
            e=obj.Resends(key); fc=obj.flow(peer);
            if isDack
                fc.AckCount=0; obj.Flows(peer)=fc;
                hold=obj.Config.DackHoldSeconds;
                if e.ResendCount>=obj.Config.MaxResends, hold=2*hold; end
                e.Expiry=obj.Scheduler.Now+hold;
                obj.DackHolds(key)=e; obj.DackOrder{end+1}=key;
                obj.removeResend(key);
                obj.releaseNsdp(e.Frame.App,'dack');
                obj.increment('Dacked'); obj.terminal(e.Frame.App,true,'dack_custody');
                obj.Scheduler.scheduleAt(e.Expiry+obj.Config.TicSeconds,@()obj.checkDacks());
                obj.emit('hop_dack',e.Frame,struct('HoldSeconds',hold,'CapacityReleased',false));
            else
                obj.releaseCapacity(peer); fc=obj.flow(peer);
                fc.AckCount=fc.AckCount+1;
                if fc.AckCount>=3
                    fc.Threshold=min(obj.Config.FlowThresholdMax,fc.Threshold+1);
                    fc.AckCount=0;
                end
                % PR50: the third ACK can grow the window even after a retry.
                if e.ResendCount>0, fc.AckCount=0; end
                obj.Flows(peer)=fc;
                obj.releaseNsdp(e.Frame.App,'ack'); obj.removeResend(key);
                obj.increment('Acknowledged'); obj.terminal(e.Frame.App,true,'ack');
                obj.emit('hop_ack',e.Frame,obj.admission(peer));
            end
        end
        function checkDacks(obj)
            keys=obj.DackOrder;
            for n=1:numel(keys)
                key=keys{n}; if ~isKey(obj.DackHolds,key), continue; end
                e=obj.DackHolds(key);
                if e.Expiry>obj.Scheduler.Now, continue; end
                obj.releaseCapacity(e.Peer); remove(obj.DackHolds,key);
                obj.DackOrder(strcmp(obj.DackOrder,key))=[];
                obj.increment('DackExpired');
                obj.emit('hop_dack_expired',e.Frame,obj.admission(e.Peer));
                obj.scheduleWake();
            end
        end
        function checkResends(obj)
            keys=obj.ResendOrder;
            % Source final-expiration pass precedes all resend admissions.
            for n=1:numel(keys)
                key=keys{n}; if ~isKey(obj.Resends,key), continue; end
                e=obj.Resends(key);
                if e.Confirmed && e.ResendCount>=obj.Config.MaxResends && ...
                        obj.Scheduler.Now-e.LastTxSeconds>=2*obj.Config.ResendSeconds
                    obj.failEntry(key,e,'retry_exhausted');
                end
            end
            keys=obj.ResendOrder;
            for n=1:numel(keys)
                key=keys{n}; if ~isKey(obj.Resends,key), continue; end
                e=obj.Resends(key);
                if ~e.Confirmed || e.ResendCount>=obj.Config.MaxResends || ...
                        obj.Scheduler.Now-e.LastTxSeconds<obj.Config.ResendSeconds
                    continue
                end
                e.ResendCount=e.ResendCount+1;
                e.Frame.RetryCount=e.ResendCount;
                e.LastTxSeconds=obj.Scheduler.Now; e.Confirmed=false;
                obj.Resends(key)=e;
                obj.increment('Retransmissions'); obj.emit('hop_retry',e.Frame,struct('ResendCount',e.ResendCount));
                if ~obj.enqueue(e.Frame)
                    obj.increment('MacAdmissionRejected');
                    obj.failEntry(key,e,'mac_queue_full');
                end
            end
        end
        function failEntry(obj,key,e,reason)
            obj.releaseNsdp(e.Frame.App,reason); obj.releaseCapacity(e.Peer);
            fc=obj.flow(e.Peer); fc.AckCount=0; fc.Threshold=max(0,fc.Threshold-1);
            obj.Flows(e.Peer)=fc; obj.removeResend(key); obj.cancelMac(e.Peer,e.Sequence);
            obj.increment('Failed'); obj.terminal(e.Frame.App,false,reason);
            obj.emit('hop_failed',e.Frame,struct('Reason',reason,'ResendCount',e.ResendCount));
            obj.scheduleWake();
        end
        function [first,w] = checkSequence(obj,peer,sequence)
            w=emptyWindow(); if isKey(obj.ReceiveWindows,peer), w=obj.ReceiveWindows(peer); end
            if w.Highest<0
                w.Highest=double(sequence); w.AckBitmap=uint64(1); first=true;
            else
                delta=sequenceDifference(w.Highest,sequence);
                if delta>0
                    if delta>=64
                        w.AckBitmap=uint64(1); w.DackBitmap=uint64(0);
                    else
                        w.AckBitmap=bitor(bitshift(w.AckBitmap,delta),uint64(1));
                        w.DackBitmap=bitshift(w.DackBitmap,delta);
                    end
                    w.Highest=double(sequence); first=true;
                elseif -delta>=64
                    first=false;
                else
                    bit=1-delta; first=~logical(bitget(w.AckBitmap,bit));
                    if first, w.AckBitmap=bitset(w.AckBitmap,bit,1); end
                end
            end
            obj.ReceiveWindows(peer)=w;
        end
        function w = markDack(obj,peer,sequence,w)
            delta=sequenceDifference(w.Highest,sequence);
            if delta<=0 && delta>-64
                w.AckBitmap=bitset(w.AckBitmap,1-delta,0);
                w.DackBitmap=bitset(w.DackBitmap,1-delta,1);
            end
            obj.ReceiveWindows(peer)=w;
        end
        function unmarkSequence(obj,peer,sequence)
            w=obj.ReceiveWindows(peer); delta=sequenceDifference(w.Highest,sequence);
            if delta<=0 && delta>-64
                w.AckBitmap=bitset(w.AckBitmap,1-delta,0);
                w.DackBitmap=bitset(w.DackBitmap,1-delta,0);
            end
            obj.ReceiveWindows(peer)=w;
        end
        function fc = flow(obj,peer)
            if isKey(obj.Flows,peer), fc=obj.Flows(peer);
            else, fc=struct('Outstanding',0,'Threshold',0,'AckCount',0); end
        end
        function releaseCapacity(obj,peer)
            fc=obj.flow(peer);
            if fc.Outstanding>0
                fc.Outstanding=fc.Outstanding-1;
                obj.PendingDataCount=obj.PendingDataCount-1;
            end
            obj.Flows(peer)=fc;
        end
        function removeResend(obj,key)
            if isKey(obj.Resends,key), remove(obj.Resends,key); end
            obj.ResendOrder(strcmp(obj.ResendOrder,key))=[];
        end
        function accepted = enqueue(obj,frame)
            if ~isfield(obj.Callbacks,'EnqueueMac')
                error('csr:hop:MissingMac','EnqueueMac callback is required.');
            end
            accepted=logical(obj.Callbacks.EnqueueMac(frame));
        end
        function accepted = deliver(obj,app,peer)
            accepted=true;
            if ~isfield(obj.Callbacks,'Deliver'), return; end
            cb=obj.Callbacks.Deliver;
            if nargout(cb)==0, cb(app,peer); return; end
            result=cb(app,peer);
            if isempty(result), return; end
            if isstruct(result), accepted=logical(result.Accepted);
            else, accepted=logical(result); end
        end
        function available = routeAvailable(obj,app)
            available=true;
            if isfield(obj.Callbacks,'RouteAvailable')
                available=logical(obj.Callbacks.RouteAvailable(app));
            end
        end
        function count = nsdpCount(obj,app)
            count=0;
            if isfield(obj.Callbacks,'NsdpCount'), count=double(obj.Callbacks.NsdpCount(app)); end
        end
        function releaseNsdp(obj,app,reason)
            if isfield(obj.Callbacks,'NsdpRelease'), obj.Callbacks.NsdpRelease(app,reason); end
        end
        function cancelMac(obj,peer,sequence)
            if isfield(obj.Callbacks,'CancelMac'), obj.Callbacks.CancelMac(double(peer),sequence); end
        end
        function terminal(obj,app,success,reason)
            if isfield(obj.Callbacks,'Terminal'), obj.Callbacks.Terminal(app,success,reason); end
        end
        function scheduleWake(obj)
            if obj.WakePending, return; end
            obj.WakePending=true;
            obj.Scheduler.scheduleAt(obj.Scheduler.Now+obj.Config.TicSeconds,@()obj.wake());
        end
        function wake(obj)
            obj.WakePending=false; obj.increment('QueueWakes');
            if isfield(obj.Callbacks,'Wake'), obj.Callbacks.Wake(); end
        end
        function emit(obj,name,frame,details)
            details.TimeSeconds=obj.Scheduler.Now;
            if isfield(obj.Callbacks,'Event'), obj.Callbacks.Event(name,frame,details); end
        end
        function increment(obj,name)
            obj.Counters.(name)=obj.Counters.(name)+1;
        end
    end
end

function value = readOption(options,name,fallback)
value=fallback; if isfield(options,name), value=options.(name); end
end
function key = entryKey(peer,sequence)
key=sprintf('%.0f:%u',double(peer),uint16(sequence));
end
function w = emptyWindow()
w=struct('Highest',-1,'AckBitmap',uint64(0),'DackBitmap',uint64(0));
end
function difference = sequenceDifference(reference,sequence)
difference=double(sequence)-double(reference);
if difference>32768, difference=difference-65536; end
if difference< -32768, difference=difference+65536; end
end
function c = hopConfig(config)
c=struct('ResendSeconds',2,'MaxResends',2,'DackHoldSeconds',20, ...
    'PendingThreshold',16,'ResendQueueLimit',512,'FlowThresholdMax',16, ...
    'NsdpLimit',16,'TicSeconds',1/36e6);
if isfield(config,'Hop'), overrides=config.Hop; else, overrides=config; end
names=fieldnames(c);
for n=1:numel(names)
    name=names{n}; if isfield(overrides,name), c.(name)=double(overrides.(name)); end
    validateattributes(c.(name),{'numeric'},{'scalar','real','finite','nonnegative'});
end
for name={'PendingThreshold','ResendQueueLimit','FlowThresholdMax','NsdpLimit','MaxResends'}
    validateattributes(c.(name{1}),{'numeric'},{'integer'});
end
if c.ResendSeconds<=0 || c.DackHoldSeconds<=0 || c.TicSeconds<=0 || c.ResendQueueLimit<1
    error('csr:hop:InvalidConfig','Retry, hold and TIC durations and queue limit must be positive.');
end
end
