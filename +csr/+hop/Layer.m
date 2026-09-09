classdef Layer < handle
    %LAYER CSR DATA/control custody, cumulative feedback and HOP-owned retries.
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
        DataReceiveWindows
        ControlReceiveWindows
        Resends
        ResendOrder = {}
        ControlOwners
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
            obj.DataReceiveWindows=containers.Map('KeyType','double','ValueType','any');
            obj.ControlReceiveWindows=containers.Map('KeyType','double','ValueType','any');
            obj.Resends=containers.Map('KeyType','char','ValueType','any');
            obj.ControlOwners=containers.Map('KeyType','char','ValueType','char');
            obj.DackHolds=containers.Map('KeyType','char','ValueType','any');
            obj.Counters=struct('Admitted',0,'AdmissionBlocked',0, ...
                'MacAdmissionRejected',0,'ResendQueueOverflow',0,'Transmitted',0, ...
                'Retransmissions',0,'Acknowledged',0,'Dacked',0,'Failed',0, ...
                'DataReceived',0,'Duplicates',0,'Delivered',0,'CustodyRefused',0, ...
                'NoRouteSuppressed',0,'AckGenerated',0,'DackGenerated',0, ...
                'FeedbackQueueDrops',0,'FeedbackReceived',0,'UnknownFeedback',0, ...
                'DackExpired',0,'QueueWakes',0,'PeakPendingData',0, ...
                'ControlAdmitted',0,'ControlAdmissionBlocked',0,'ControlTransmitted',0, ...
                'ControlRetransmissions',0,'ControlAcknowledged',0,'ControlCompleted',0, ...
                'ControlFailed',0,'ControlTargetFailures',0,'ControlReceived',0, ...
                'ControlDuplicates',0,'ControlDelivered',0,'ControlUnexpectedDack',0);
        end
        function allowed = canSend(obj,peer)
            s=obj.admission(peer); allowed=s.GlobalAllowed && s.NeighborAllowed ...
                && obj.Resends.Count<obj.Config.ResendQueueLimit;
        end
        function allowed = canSendControl(obj,peerIds)
            validateControlPeers(peerIds,false);
            % A group occupies one shared resend entry and no DATA window.
            allowed=obj.Resends.Count<obj.Config.ResendQueueLimit;
        end
        function removed = cancelQueuedControl(obj,peer,controlType)
            removed=0;
            if isfield(obj.Callbacks,'CancelMacControl')
                removed=double(obj.Callbacks.CancelMacControl(double(peer),char(controlType)));
            end
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
        function [accepted,frame] = sendControl(obj,control,peerIds,options)
            if nargin<4, options=struct(); end
            ackRequired=readOption(options,'AckRequired',true);
            if ~(isnumeric(ackRequired) || islogical(ackRequired)) || ...
                    ~isscalar(ackRequired) || ~isreal(ackRequired) || ~ismember(ackRequired,[0 1])
                error('csr:hop:InvalidField','AckRequired must be scalar logical or 0/1.');
            end
            peerIds=validateControlPeers(peerIds,~logical(ackRequired));
            isSnmp=any(strcmp(control.Type,{'SNMP_START','SNMP_DONE'}));
            if isSnmp && (logical(ackRequired) || numel(peerIds)~=1 || peerIds==16777215)
                error('csr:hop:InvalidControl', ...
                    'SNMP is a single-destination, best-effort legacy control.');
            end
            frame=[];
            if ackRequired && ~obj.canSendControl(peerIds)
                obj.increment('ControlAdmissionBlocked'); obj.increment('ResendQueueOverflow');
                accepted=false; return
            end
            previous=zeros(size(peerIds)); sequences=zeros(size(peerIds),'uint16');
            existed=false(size(peerIds));
            if ~isSnmp
                for n=1:numel(peerIds)
                    peer=peerIds(n); existed(n)=isKey(obj.LastSequences,peer);
                    if existed(n), previous(n)=obj.LastSequences(peer); end
                    sequences(n)=uint16(mod(previous(n)+1,65536));
                end
            end
            if ~isfield(options,'GeneratedSeconds'), options.GeneratedSeconds=obj.Scheduler.Now; end
            frame=csr.hop.Frames.control(control,obj.NodeId,peerIds,sequences,options);
            if ~isSnmp
                for n=1:numel(peerIds), obj.LastSequences(peerIds(n))=double(sequences(n)); end
            end
            if ackRequired
                key=entryKey(peerIds(1),sequences(1));
                e=struct('Frame',frame,'Peer',peerIds(1),'Sequence',sequences(1), ...
                    'ResendCount',0,'LastTxSeconds',Inf,'Confirmed',false, ...
                    'TargetPeers',peerIds,'TargetSequences',sequences,'Acked',false(size(peerIds)));
                obj.Resends(key)=e; obj.ResendOrder{end+1}=key;
                for n=1:numel(peerIds)
                    obj.ControlOwners(entryKey(peerIds(n),sequences(n)))=key;
                end
            end
            accepted=obj.enqueue(frame);
            if ~accepted
                obj.increment('MacAdmissionRejected');
                if ackRequired, obj.removeResend(key); end
                % Failed admission transfers no control ownership or sequence.
                for n=1:numel(peerIds)
                    if isSnmp, continue; end
                    if existed(n), obj.LastSequences(peerIds(n))=previous(n);
                    else, remove(obj.LastSequences,peerIds(n)); end
                end
                return
            end
            obj.increment('ControlAdmitted');
            obj.emit('hop_control_admit',frame,struct('Targets',peerIds));
        end
        function notifySent(obj,frame)
            % HOP never starts an initial ACK clock at MAC queue admission.
            isControl=strcmp(frame.Kind,'CONTROL');
            if ~isControl && ~strcmp(frame.Kind,'DATA'), return; end
            if isControl, obj.increment('ControlTransmitted'); else, obj.increment('Transmitted'); end
            if ~frame.AckRequired
                if isControl
                    for n=1:numel(frame.DestinationIds)
                        obj.controlResult(frame.Control,frame.DestinationIds(n),true, ...
                            n==numel(frame.DestinationIds),[]);
                    end
                    obj.increment('ControlCompleted');
                else, obj.terminal(frame.App,true,'sent_no_ack'); end
                return
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
            if strcmp(frame.Kind,'CONTROL')
                peers=double(frame.DestinationIds); index=find(peers==obj.NodeId,1);
                if isempty(index)
                    if numel(peers)~=1 || peers(1)~=16777215 || frame.AckRequired, return; end
                else
                    frame.DestinationId=obj.NodeId; frame.Sequence=frame.HopSequences(index);
                end
            elseif double(frame.DestinationId)~=obj.NodeId, return; end
            switch upper(frame.Kind)
                case 'DATA'
                    obj.receiveData(frame);
                case 'CONTROL'
                    obj.receiveControl(frame);
                case {'ACK','DACK'}
                    obj.receiveFeedback(frame);
            end
        end
        function s = stats(obj)
            s=obj.Counters;
            s.PendingData=obj.PendingDataCount;
            s.ResendQueueDepth=double(obj.Resends.Count);
            s.DackHoldCount=double(obj.DackHolds.Count);
            s.ControlPending=0; s.ControlPendingTargets=0;
            for n=1:numel(obj.ResendOrder)
                e=obj.Resends(obj.ResendOrder{n});
                if strcmp(e.Frame.Kind,'CONTROL')
                    s.ControlPending=s.ControlPending+1;
                    s.ControlPendingTargets=s.ControlPendingTargets+sum(~e.Acked);
                end
            end
        end
        function s = state(obj,peer)
            s=obj.admission(peer); fc=obj.flow(double(peer));
            s.AckCount=fc.AckCount;
            s.DataReceiveWindow=obj.receiveWindow(double(peer),true);
            s.ControlReceiveWindow=obj.receiveWindow(double(peer),false);
            % Retain the Tranche 2 accessor as a DATA-window alias.
            s.ReceiveWindow=s.DataReceiveWindow;
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
        function frame = makeControlAck(obj,received)
            % Reliable source controls use an exact ACK. They never expose
            % the DATA or control replay bitmap on the wire.
            options=struct('RateKeyKbps',received.RateKeyKbps, ...
                'TxPowerDbm',[],'Preamble','short','HasAckWindow',false);
            if isfield(received,'EnvelopeProfile')
                options.EnvelopeProfile=received.EnvelopeProfile;
            end
            frame=csr.hop.Frames.acknowledgment(obj.NodeId,received.SourceId, ...
                received.Sequence,uint64(0),uint64(0),options);
        end
        function receiveControl(obj,frame)
            obj.increment('ControlReceived'); src=double(frame.SourceId);
            % Discovery broadcasts use an independent sender sequence stream;
            % they cannot advance the per-peer reliable ACK receive window.
            broadcast=double(frame.DestinationId)==16777215;
            first=true;
            isSnmp=any(strcmp(frame.Control.Type,{'SNMP_START','SNMP_DONE'}));
            if ~obj.validateControl(frame.Control,src)
                obj.emit('hop_control_rejected',frame, ...
                    struct('FirstReception',false,'Reason','invalid_control'));
                return
            end
            if ~broadcast && ~isSnmp
                [first,~]=obj.checkSequence(src,frame.Sequence,false);
            end
            feedbackRequired=~broadcast && ~isSnmp && frame.AckRequired;
            % Source KeyUpdate ACKs precede admission/key callbacks, whereas
            % RoutingControl and NeighborCheck deliver to NWK before ACKing.
            ackAfterDelivery=any(strcmp(frame.Control.Type,{'ROUTING','NEIGHBOR_CHECK'}));
            if feedbackRequired && ~ackAfterDelivery
                obj.enqueueFeedback(obj.makeControlAck(frame));
            end
            if first
                if isfield(obj.Callbacks,'DeliverControl'), obj.Callbacks.DeliverControl(frame.Control,src); end
                obj.increment('ControlDelivered');
            else, obj.increment('ControlDuplicates'); end
            if feedbackRequired && ackAfterDelivery
                obj.enqueueFeedback(obj.makeControlAck(frame));
            end
            obj.emit('hop_control_receive',frame,struct('FirstReception',first));
        end
        function receiveData(obj,frame)
            obj.increment('DataReceived');
            src=double(frame.SourceId);
            [first,window]=obj.checkSequence(src,frame.Sequence,true);
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
            cancellations={};
            if frame.HasAckWindow
                ack=frame.AckBitmap; dack=bitand(frame.DackBitmap,bitcmp(ack));
                for bit=1:64
                    if bitget(ack,bit) || bitget(dack,bit)
                        sequence=uint16(mod(double(frame.Sequence)-(bit-1),65536));
                        % Cumulative feedback is DATA-only. Reliable controls
                        % use exact ACKs even though transmit sequences share
                        % the same per-peer allocator.
                        pair=obj.complete(double(frame.SourceId),sequence, ...
                            logical(bitget(dack,bit)),false);
                        if ~isempty(pair), cancellations{end+1}=pair; end %#ok<AGROW>
                    end
                end
            elseif strcmp(frame.Kind,'ACK')
                pair=obj.complete(double(frame.SourceId),frame.Sequence,false,true);
                if ~isempty(pair), cancellations{end+1}=pair; end
            end
            % Finish every custody change before cancellation. A partial
            % group ACK keeps the original MAC frame, including all targets.
            for n=1:numel(cancellations)
                pair=cancellations{n}; obj.cancelMac(pair(1),uint16(pair(2)));
            end
            % Source single-DACK path is disabled. Even unknown/single-DACK
            % feedback requests one coalesced NWK wake at the next TIC.
            obj.scheduleWake();
        end
        function cancellation = complete(obj,peer,sequence,isDack,allowControl)
            cancellation=[];
            key=entryKey(peer,sequence);
            if allowControl && isKey(obj.ControlOwners,key)
                groupKey=obj.ControlOwners(key); e=obj.Resends(groupKey);
                cancellation=[];
                if isDack
                    % Controls never take DATA custody or enter DACK holds.
                    obj.increment('ControlUnexpectedDack'); return
                end
                index=find(e.TargetPeers==peer & e.TargetSequences==sequence,1);
                if e.Acked(index), return; end
                e.Acked(index)=true; finished=all(e.Acked);
                remaining=e.TargetPeers(~e.Acked);
                % Source reports completion while the HOP owner is still
                % present. Store ACK progress first, then erase after callback.
                obj.Resends(groupKey)=e;
                if finished, obj.increment('ControlCompleted'); end
                obj.increment('ControlAcknowledged');
                obj.controlResult(e.Frame.Control,peer,true,finished,remaining);
                if finished
                    obj.removeResend(groupKey);
                    cancellation=[e.Peer double(e.Sequence)];
                end
                obj.emit('hop_control_ack',e.Frame,struct('Peer',peer,'Complete',finished, ...
                    'RemainingPeers',remaining));
                return
            end
            if ~isKey(obj.Resends,key)
                obj.increment('UnknownFeedback'); return
            end
            e=obj.Resends(key);
            if strcmp(e.Frame.Kind,'CONTROL')
                % A cumulative DATA bitmap cannot complete or DACK a control
                % owner that happens to occupy this transmit sequence.
                obj.increment('UnknownFeedback'); return
            end
            cancellation=[double(peer) double(sequence)];
            fc=obj.flow(peer);
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
                if strcmp(e.Frame.Kind,'CONTROL'), obj.increment('ControlRetransmissions');
                else, obj.increment('Retransmissions'); end
                obj.emit('hop_retry',e.Frame,struct('ResendCount',e.ResendCount));
                if ~obj.enqueue(e.Frame)
                    obj.increment('MacAdmissionRejected');
                    obj.failEntry(key,e,'mac_queue_full');
                end
            end
        end
        function failEntry(obj,key,e,reason)
            if strcmp(e.Frame.Kind,'CONTROL')
                remaining=e.TargetPeers(~e.Acked);
                obj.increment('ControlFailed');
                for n=1:numel(remaining)
                    obj.increment('ControlTargetFailures');
                    % Failure metadata names the originally attempted group;
                    % NWK independently owns and prunes its residual set.
                    obj.controlResult(e.Frame.Control,remaining(n),false, ...
                        n==numel(remaining),e.TargetPeers);
                end
                obj.removeResend(key); obj.cancelMac(e.Peer,e.Sequence);
                obj.emit('hop_control_failed',e.Frame,struct('Reason',reason, ...
                    'ResendCount',e.ResendCount,'RemainingPeers',remaining));
                obj.scheduleWake(); return
            end
            obj.releaseNsdp(e.Frame.App,reason); obj.releaseCapacity(e.Peer);
            fc=obj.flow(e.Peer); fc.AckCount=0; fc.Threshold=max(0,fc.Threshold-1);
            obj.Flows(e.Peer)=fc; obj.removeResend(key); obj.cancelMac(e.Peer,e.Sequence);
            obj.increment('Failed'); obj.terminal(e.Frame.App,false,reason);
            obj.emit('hop_failed',e.Frame,struct('Reason',reason,'ResendCount',e.ResendCount));
            obj.scheduleWake();
        end
        function [first,w] = checkSequence(obj,peer,sequence,dataTraffic)
            w=obj.receiveWindow(peer,dataTraffic);
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
            if dataTraffic, obj.DataReceiveWindows(peer)=w;
            else, obj.ControlReceiveWindows(peer)=w; end
        end
        function w = markDack(obj,peer,sequence,w)
            delta=sequenceDifference(w.Highest,sequence);
            if delta<=0 && delta>-64
                w.AckBitmap=bitset(w.AckBitmap,1-delta,0);
                w.DackBitmap=bitset(w.DackBitmap,1-delta,1);
            end
            obj.DataReceiveWindows(peer)=w;
        end
        function unmarkSequence(obj,peer,sequence)
            w=obj.DataReceiveWindows(peer); delta=sequenceDifference(w.Highest,sequence);
            if delta<=0 && delta>-64
                w.AckBitmap=bitset(w.AckBitmap,1-delta,0);
                w.DackBitmap=bitset(w.DackBitmap,1-delta,0);
            end
            obj.DataReceiveWindows(peer)=w;
        end
        function w = receiveWindow(obj,peer,dataTraffic)
            w=emptyWindow();
            if dataTraffic
                if isKey(obj.DataReceiveWindows,peer), w=obj.DataReceiveWindows(peer); end
            elseif isKey(obj.ControlReceiveWindows,peer)
                w=obj.ControlReceiveWindows(peer);
            end
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
            if isKey(obj.Resends,key)
                e=obj.Resends(key);
                if strcmp(e.Frame.Kind,'CONTROL')
                    for n=1:numel(e.TargetPeers)
                        remove(obj.ControlOwners,entryKey(e.TargetPeers(n),e.TargetSequences(n)));
                    end
                end
                remove(obj.Resends,key);
            end
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
        function accepted = validateControl(obj,control,peer)
            accepted=true;
            if ~isfield(obj.Callbacks,'ValidateControl'), return; end
            accepted=obj.Callbacks.ValidateControl(control,double(peer));
            if ~(isnumeric(accepted) || islogical(accepted)) || ~isscalar(accepted) || ...
                    ~isreal(accepted) || ~ismember(accepted,[0 1])
                error('csr:hop:ControlValidationContract', ...
                    'ValidateControl must return scalar logical or 0/1.');
            end
            accepted=logical(accepted);
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
        function controlResult(obj,control,peer,success,complete,remainingPeers)
            if isfield(obj.Callbacks,'ControlResult')
                obj.Callbacks.ControlResult(control,double(peer),logical(success), ...
                    logical(complete),reshape(double(remainingPeers),1,[]));
            end
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
function peers = validateControlPeers(peers,allowBroadcast)
if ~isnumeric(peers) || ~isvector(peers) || isempty(peers) || numel(peers)>10 || ...
        ~isreal(peers) || any(~isfinite(peers(:))) || any(peers(:)<0 | peers(:)>16777215 | ...
        fix(peers(:))~=peers(:)) || numel(unique(peers))~=numel(peers)
    error('csr:hop:InvalidTargets','Controls require 1 to 10 distinct valid peer IDs.');
end
peers=reshape(double(peers),1,[]);
if any(peers==16777215) && (~allowBroadcast || numel(peers)~=1)
    error('csr:hop:InvalidTargets','Broadcast control requires one best-effort destination.');
end
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
