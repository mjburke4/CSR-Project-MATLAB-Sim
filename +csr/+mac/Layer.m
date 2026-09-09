classdef Layer < handle
    %LAYER CSR access, reservation, ACK queue and receiver wake state machine.
    %   Protocol time is supplied by a scheduler. PHY acquisition stays in the
    %   signal engine; receiverChanged synchronizes its Search/Track changes.
    %   HOP owns DATA retries. Sent is called only at actual transmission.
    properties (SetAccess = private)
        NodeId
        State = 'Search'
        Counters
        ReservationCounter = -1
        ReservationSlot = -1
        LastAdvertisedReservation = -1
        LastOpportunitySlot = -1
        PreparationActive = false
        HoldoffOver = false
    end
    properties (Dependent, SetAccess = private)
        DataQueueCount
        AckQueueCount
        PendingCount
    end
    properties (Access = private)
        Scheduler
        Stream
        Config
        Callbacks
        DataQueue = {}
        AckQueue = {}
        Neighbors
        Started = false
        SlotEvent = uint64(0)
        HoldoffEvent = uint64(0)
        IdleRtsEvent = uint64(0)
        FinishEvent = uint64(0)
        WakeEvent = uint64(0)
        SleepEvent = uint64(0)
        PostTxEvent = uint64(0)
        PackingRetryEvent = uint64(0)
        PostTxWaitActive = false
        InReceiverUpdate = false
    end
    methods (Static)
        function value = defaults()
            value = struct('DataQueueLimit', 512, 'AckQueueLimit', 256, ...
                'AckTransmissions', 5, 'MaxConcatSegments', 16, ...
                'SlotSeconds', 0.013, 'HoldoffSeconds', 0.3, ...
                'ActiveNodes', 1, 'ReportedActiveNodes', 1, ...
                'SlotReduction', 0, 'ReservationSlotOverride', -1, ...
                'DutyCycleEnabled', true, 'WakeCycleSeconds', 0.988, ...
                'SearchSeconds', 0.0078, 'BootSeconds', 0.0011, ...
                'PostTxBaseSeconds', 15, 'PostTxPerNodeSeconds', 1.5, ...
                'PostTxGuardSeconds', 0.5, 'ConcatenationEnabled', true);
        end

        function range = slotRange(activeNodes, reduction)
            if nargin < 2, reduction = 0; end
            values = [15 18 21 25 31 37 44 52 63 75 89 106 127 151 180 214 255];
            range = values(min(floor(double(activeNodes)), 16) + 1);
            if reduction > 0 && range - reduction > 1
                range = range - reduction;
            end
        end

        function bytes = concatByteLimit(rate)
            rates = [8 16 32 64 128];
            index = find(rates == rate, 1);
            if isempty(index), bytes = 0; else, bytes = 256 * 2^(index - 1); end
        end
    end
    methods
        function obj = Layer(nodeId, scheduler, streams, config, callbacks)
            obj.NodeId = double(nodeId);
            obj.Scheduler = scheduler;
            obj.Stream = streams.get(nodeId, 'mac');
            obj.Config = csr.mac.Layer.defaults();
            if isfield(config, 'Mac'), supplied = config.Mac; else, supplied = config; end
            names = fieldnames(obj.Config);
            for index = 1:numel(names)
                if isfield(supplied, names{index})
                    obj.Config.(names{index}) = supplied.(names{index});
                end
            end
            obj.Callbacks = callbacks;
            if ~isfield(callbacks, 'Transmit') || ~isa(callbacks.Transmit, 'function_handle')
                error('csr:mac:MissingTransmit', 'MAC needs a Transmit callback.');
            end
            obj.Neighbors = containers.Map('KeyType', 'double', 'ValueType', 'any');
            obj.Counters = struct('Enqueued', 0, 'AckEnqueued', 0, ...
                'DataQueueDrops', 0, 'AckQueueDrops', 0, 'AckReplacements', 0, ...
                'Canceled', 0, 'Transmissions', 0, 'SegmentsTransmitted', 0, ...
                'AckTransmissions', 0, 'LongPreambles', 0, 'ShortPreambles', 0, ...
                'MaxDataQueueDepth', 0, 'MaxAckQueueDepth', 0, ...
                'ConcatenatedTransmissions', 0, 'PackingBlocked', 0, ...
                'DataQueueDelaySeconds', 0, 'DataDequeued', 0);
        end

        function count = get.DataQueueCount(obj), count = numel(obj.DataQueue); end
        function count = get.AckQueueCount(obj), count = numel(obj.AckQueue); end
        function count = get.PendingCount(obj)
            count = obj.DataQueueCount + obj.AckQueueCount;
        end

        function start(obj)
            if obj.Started, return; end
            obj.Started = true;
            if obj.Config.DutyCycleEnabled
                obj.setState('Idle');
                cycle = obj.Config.WakeCycleSeconds;
                nextWake = (floor(obj.Scheduler.Now / cycle) + 1) * cycle;
                obj.WakeEvent = obj.Scheduler.scheduleAt(nextWake, @() obj.periodicWake());
            else
                obj.setState('Search');
            end
        end

        function accepted = enqueue(obj, frame)
            obj.start();
            isAck = any(strcmp(frame.Kind, {'ACK', 'DACK'}));
            accepted = true;
            if isAck
                for index = 1:obj.AckQueueCount
                    entry = obj.AckQueue{index};
                    if entry.Frame.DestinationId ~= frame.DestinationId, continue; end
                    if frame.HasAckWindow
                        entry.Frame = frame;
                        entry.Count = 0;
                        obj.AckQueue{index} = entry;
                        obj.Counters.AckReplacements = obj.Counters.AckReplacements + 1;
                        obj.emit('mac_ack_replace', frame, struct('QueueDepth', obj.AckQueueCount));
                        obj.schedulePending();
                        return;
                    elseif entry.Frame.Sequence == frame.Sequence
                        return;
                    end
                end
                if obj.AckQueueCount >= obj.Config.AckQueueLimit
                    obj.Counters.AckQueueDrops = obj.Counters.AckQueueDrops + 1;
                    obj.emit('mac_queue_drop', frame, struct('Queue', 'ack'));
                    accepted = false;
                    return;
                end
                obj.AckQueue{end + 1} = struct('Frame', frame, 'Count', 0);
                obj.Counters.AckEnqueued = obj.Counters.AckEnqueued + 1;
                obj.Counters.MaxAckQueueDepth = max(obj.Counters.MaxAckQueueDepth, obj.AckQueueCount);
            else
                if obj.DataQueueCount >= obj.Config.DataQueueLimit
                    obj.Counters.DataQueueDrops = obj.Counters.DataQueueDrops + 1;
                    obj.emit('mac_queue_drop', frame, struct('Queue', 'data'));
                    accepted = false;
                    return;
                end
                % Full-queue rejection precedes stable priority insertion.
                index = 1;
                while index <= obj.DataQueueCount && obj.DataQueue{index}.Frame.Dscp >= frame.Dscp
                    index = index + 1;
                end
                entry = struct('Frame', frame, 'EnqueuedSeconds', obj.Scheduler.Now);
                obj.DataQueue = [obj.DataQueue(1:index-1), {entry}, obj.DataQueue(index:end)];
                obj.Counters.Enqueued = obj.Counters.Enqueued + 1;
                obj.Counters.MaxDataQueueDepth = max(obj.Counters.MaxDataQueueDepth, obj.DataQueueCount);
            end
            obj.emit('mac_enqueue', frame, struct('DataDepth', obj.DataQueueCount, 'AckDepth', obj.AckQueueCount));
            obj.schedulePending();
        end

        function removed = cancel(obj, peerId, sequence)
            removed = 0;
            keep = true(1, obj.DataQueueCount);
            for index = 1:obj.DataQueueCount
                frame = obj.DataQueue{index}.Frame;
                if frame.AckRequired && frame.DestinationId == peerId && frame.Sequence == sequence
                    keep(index) = false;
                    removed = removed + 1;
                end
            end
            obj.DataQueue = obj.DataQueue(keep);
            obj.Counters.Canceled = obj.Counters.Canceled + removed;
            if obj.PendingCount == 0, obj.PreparationActive = false; end
        end

        function removed = cancelControl(obj,peerId,controlType)
            % KeyRequest immediateTag replacement applies only to unsent MAC
            % entries; reliable control owners remain HOP-managed.
            removed=0; keep=true(1,obj.DataQueueCount);
            for index=1:obj.DataQueueCount
                frame=obj.DataQueue{index}.Frame;
                if ~strcmp(frame.Kind,'CONTROL') || ~strcmp(frame.Control.Type,controlType)
                    continue
                end
                targets=frame.DestinationId;
                if isfield(frame,'DestinationIds'), targets=frame.DestinationIds; end
                if numel(targets)==1 && double(targets)==double(peerId)
                    keep(index)=false; removed=removed+1;
                end
            end
            obj.DataQueue=obj.DataQueue(keep); obj.Counters.Canceled=obj.Counters.Canceled+removed;
            if obj.PendingCount==0, obj.PreparationActive=false; end
        end

        function receive(obj, frame, decision)
            if ~decision.Success, return; end
            peer = double(frame.SourceId);
            known = isKey(obj.Neighbors, peer);
            if known
                entry = obj.Neighbors(peer);
            else
                entry = struct('LastHeardSeconds', -1, 'ReservationCounter', -1);
            end
            % The first successful reception creates the neighbor only after
            % reservation processing. It cannot honor that first reservation.
            if known && isfield(frame, 'ReservationSlot')
                entry.ReservationCounter = double(frame.ReservationSlot);
            end
            entry.LastHeardSeconds = obj.Scheduler.Now;
            obj.Neighbors(peer) = entry;
            if isfield(frame, 'ActiveNodes')
                obj.Config.ReportedActiveNodes = max(obj.Config.ReportedActiveNodes, double(frame.ActiveNodes));
            end
            obj.pollReceiver();
        end

        function receiverChanged(obj, state)
            % Called by the PHY adapter after an actual state transition.
            if strcmp(obj.State, 'Tx'), return; end
            state = char(state);
            if strcmp(state, 'Tx'), return; end
            previous = obj.State;
            obj.State = state;
            if strcmp(previous, state), return; end
            obj.onStateChange(previous, state);
        end

        function counter = neighborReservation(obj, peerId)
            counter = -1;
            if isKey(obj.Neighbors, double(peerId))
                entry = obj.Neighbors(double(peerId));
                counter = entry.ReservationCounter;
            end
        end

        function setActiveNodes(obj, localCount, reportedCount)
            obj.Config.ActiveNodes = double(localCount);
            if nargin > 2
                obj.Config.ReportedActiveNodes = max(obj.Config.ReportedActiveNodes, double(reportedCount));
            end
        end

        function output = snapshot(obj)
            output = obj.Counters;
            output.DataQueueDepth = obj.DataQueueCount;
            output.AckQueueDepth = obj.AckQueueCount;
            output.State = obj.State;
            output.ReservationCounter = obj.ReservationCounter;
            output.ReservationSlot = obj.ReservationSlot;
        end
    end
    methods (Access = private)
        function schedulePending(obj)
            if obj.PendingCount == 0 || strcmp(obj.State, 'Tx'), return; end
            obj.pollReceiver();
            if strcmp(obj.State, 'Idle')
                obj.scheduleIdleRts();
            elseif obj.SlotEvent == 0
                obj.startSearchTiming();
            elseif ~obj.HoldoffOver && obj.HoldoffEvent == 0
                obj.startHoldoff();
            end
        end

        function startSearchTiming(obj)
            if obj.SlotEvent == 0
                obj.SlotEvent = obj.after(obj.Config.SlotSeconds, @() obj.slotTick());
            end
            obj.startHoldoff();
        end

        function startHoldoff(obj)
            obj.cancelTimer('HoldoffEvent');
            obj.HoldoffOver = false;
            obj.HoldoffEvent = obj.after(obj.Config.HoldoffSeconds, @() obj.holdoffExpired());
        end

        function holdoffExpired(obj)
            obj.HoldoffEvent = uint64(0);
            obj.HoldoffOver = true;
            obj.emit('mac_holdoff', struct(), struct('ReservationCounter', obj.ReservationCounter));
        end

        function scheduleIdleRts(obj)
            if obj.IdleRtsEvent ~= 0 || obj.PendingCount == 0, return; end
            now = obj.Scheduler.Now;
            period = obj.Config.SlotSeconds;
            nextSlot = (floor(now / period) + 1) * period;
            if obj.Config.DutyCycleEnabled
                cycle = obj.Config.WakeCycleSeconds;
                nextWake = (floor(now / cycle) + 1) * cycle;
                if abs(nextWake - nextSlot) <= period / 2
                    return; % The already scheduled unconditional wake owns it.
                end
            end
            obj.IdleRtsEvent = obj.Scheduler.scheduleAt(nextSlot, @() obj.idleRts());
        end

        function idleRts(obj)
            obj.IdleRtsEvent = uint64(0);
            if ~strcmp(obj.State, 'Idle') || obj.PendingCount == 0, return; end
            obj.setState('Search');
            obj.prepare(true);
        end

        function periodicWake(obj)
            obj.WakeEvent = obj.after(obj.Config.WakeCycleSeconds, @() obj.periodicWake());
            if ~strcmp(obj.State, 'Idle'), return; end
            obj.setState('Search');
            obj.cancelTimer('SleepEvent');
            obj.SleepEvent = obj.after(obj.Config.BootSeconds + obj.Config.SearchSeconds, @() obj.sleep());
        end

        function sleep(obj)
            obj.SleepEvent = uint64(0);
            obj.pollReceiver();
            if ~obj.Config.DutyCycleEnabled || ~strcmp(obj.State, 'Search') || ...
                    obj.PreparationActive || obj.PostTxWaitActive
                return;
            end
            obj.setState('Idle');
        end

        function slotTick(obj)
            % Re-arm first: a simultaneous transmission end cannot move phase.
            obj.SlotEvent = obj.after(obj.Config.SlotSeconds, @() obj.slotTick());
            obj.pollReceiver();
            if ~strcmp(obj.State, 'Search'), return; end
            if ~obj.hasSync()
                peers = keys(obj.Neighbors);
                for index = 1:numel(peers)
                    entry = obj.Neighbors(peers{index});
                    entry.ReservationCounter = entry.ReservationCounter - 1;
                    obj.Neighbors(peers{index}) = entry;
                end
                if obj.HoldoffOver && obj.ReservationCounter >= 0
                    obj.ReservationCounter = obj.ReservationCounter - 1;
                    if obj.ReservationCounter == -1 && ~obj.PreparationActive
                        obj.ReservationSlot = -1;
                    end
                end
                if obj.PreparationActive && obj.PendingCount > 0 && ...
                        obj.ReservationCounter == -1 && obj.PackingRetryEvent == 0
                    obj.transmit();
                    return;
                end
            end
            % PREP_TX can activate under SYNC, but countdown cannot advance.
            if ~obj.PreparationActive && obj.PendingCount > 0
                obj.cancelPostTxWait();
                obj.prepare(false);
            end
        end

        function prepare(obj, redrawZero)
            if obj.PreparationActive || obj.PendingCount == 0, return; end
            obj.PreparationActive = true;
            obj.cancelTimer('SleepEvent');
            if obj.ReservationCounter < 0 || (redrawZero && obj.ReservationCounter == 0)
                obj.ReservationSlot = obj.pickSlot();
                obj.ReservationCounter = obj.ReservationSlot;
            end
            obj.emit('mac_prepare', struct(), struct('ReservationSlot', obj.ReservationSlot, ...
                'ReservationCounter', obj.ReservationCounter));
        end

        function slot = pickSlot(obj)
            if obj.Config.ReservationSlotOverride > 0
                slot = obj.Config.ReservationSlotOverride;
                return;
            end
            active = max(obj.Config.ActiveNodes, obj.Config.ReportedActiveNodes);
            range = csr.mac.Layer.slotRange(active, obj.Config.SlotReduction);
            occupied = false(1, 256);
            peers = keys(obj.Neighbors);
            for index = 1:numel(peers)
                entry = obj.Neighbors(peers{index});
                counter = entry.ReservationCounter;
                if counter >= 0 && counter < 256, occupied(counter + 1) = true; end
            end
            remaining = randi(obj.Stream, range);
            for candidate = 0:253
                if occupied(candidate + 1), continue; end
                if remaining == 0, slot = candidate; return; end
                remaining = remaining - 1;
            end
            slot = randi(obj.Stream, range); % Source table-exhaustion fallback.
        end

        function transmit(obj)
            if ~obj.HoldoffOver || ~obj.PreparationActive || obj.PendingCount == 0 || ...
                    obj.ReservationCounter ~= -1 || ~strcmp(obj.State, 'Search') || obj.hasSync()
                return;
            end
            [frames, ackCount, dataCount, concatenate] = obj.selectFrames();
            if isempty(frames)
                obj.Counters.PackingBlocked = obj.Counters.PackingBlocked + 1;
                obj.emit('mac_packing_blocked', struct(), struct('QueueDepth', obj.PendingCount));
                obj.PackingRetryEvent = obj.after(1, @() obj.packingRetry());
                return;
            end
            rates = cellfun(@(frame) double(frame.RateKeyKbps), frames);
            rate = min(rates);
            powers = cellfun(@(frame) double(frame.TxPowerDbm), frames);
            power = max(powers(rates == rate));
            preamble = obj.choosePreamble(frames, concatenate);
            for index = 1:numel(frames)
                frames{index}.RateKeyKbps = rate;
                frames{index}.TxPowerDbm = power;
                frames{index}.Preamble = preamble;
            end
            envelope = frames{1};
            envelope.Kind = 'AGGREGATE';
            envelope.Segments = frames;
            envelope.SourceId = obj.NodeId;
            envelope.WirePayloadBytes = sum(cellfun(@(frame) double(frame.WirePayloadBytes), frames));
            envelope.ApplicationPayloadBytes = sum(cellfun(@(frame) double(frame.ApplicationPayloadBytes), frames));
            envelope.Dscp = 0;
            for index = ackCount + 1:numel(frames)
                envelope.Dscp = max(envelope.Dscp, double(frames{index}.Dscp));
            end
            envelope.AckRequired = any(cellfun(@(frame) frame.AckRequired, frames));
            obj.LastOpportunitySlot = obj.ReservationSlot;
            obj.ReservationSlot = obj.pickSlot();
            obj.ReservationCounter = obj.ReservationSlot;
            obj.LastAdvertisedReservation = obj.ReservationSlot;
            envelope.ReservationSlot = obj.ReservationSlot;
            envelope.ActiveNodes = obj.Config.ActiveNodes;
            duration = csr.phy.airtime(envelope.WirePayloadBytes, rate, preamble);
            obj.PreparationActive = false;
            obj.cancelPostTxWait();
            obj.cancelTimer('SleepEvent');
            obj.State = 'Tx';
            obj.emit('mac_state', envelope, struct('State', 'Tx'));
            obj.Callbacks.Transmit(envelope, duration);
            % PHY schedules its TX completion first. Then the MAC can safely
            % request Search and resume the advertised reservation.
            obj.FinishEvent = obj.after(duration, @() obj.finishTx());
            obj.Counters.Transmissions = obj.Counters.Transmissions + 1;
            obj.Counters.SegmentsTransmitted = obj.Counters.SegmentsTransmitted + numel(frames);
            obj.Counters.AckTransmissions = obj.Counters.AckTransmissions + ackCount;
            obj.Counters.ConcatenatedTransmissions = obj.Counters.ConcatenatedTransmissions + (numel(frames) > 1);
            if strcmp(preamble, 'long')
                obj.Counters.LongPreambles = obj.Counters.LongPreambles + 1;
            else
                obj.Counters.ShortPreambles = obj.Counters.ShortPreambles + 1;
            end
            % Mutate selected queues before callbacks that may enqueue new
            % work. Membership and sent instant are otherwise source ordered.
            for index = 1:ackCount
                obj.AckQueue{index}.Count = obj.AckQueue{index}.Count + 1;
            end
            if ackCount > 0
                keep = cellfun(@(entry) entry.Count < obj.Config.AckTransmissions, obj.AckQueue);
                obj.AckQueue = obj.AckQueue(keep);
            end
            for index = 1:dataCount
                obj.Counters.DataQueueDelaySeconds = obj.Counters.DataQueueDelaySeconds + ...
                    obj.Scheduler.Now - obj.DataQueue{index}.EnqueuedSeconds;
            end
            obj.Counters.DataDequeued = obj.Counters.DataDequeued + dataCount;
            obj.DataQueue(1:dataCount) = [];
            obj.emit('mac_transmit', envelope, struct('DurationSeconds', duration, ...
                'Segments', numel(frames), 'ReservationSlot', obj.ReservationSlot));
            if isfield(obj.Callbacks, 'Sent')
                for index = 1:numel(frames)
                    obj.Callbacks.Sent(frames{index});
                end
            end
        end

        function [frames, ackCount, dataCount, concatenate] = selectFrames(obj)
            frames = {};
            ackCount = 0;
            dataCount = 0;
            concatenate = obj.Config.ConcatenationEnabled && obj.PendingCount > 1;
            candidates = [obj.AckQueue, obj.DataQueue];
            totalBytes = 0;
            rate = 1000;
            for index = 1:numel(candidates)
                frame = candidates{index}.Frame;
                nextRate = min(rate, double(frame.RateKeyKbps));
                limit = csr.mac.Layer.concatByteLimit(nextRate);
                if concatenate
                    if limit == 0
                        fits = isempty(frames);
                    else
                        fits = totalBytes + double(frame.WirePayloadBytes) < limit;
                    end
                    if ~fits, break; end
                end
                frames{end + 1} = frame; %#ok<AGROW>
                totalBytes = totalBytes + double(frame.WirePayloadBytes);
                rate = nextRate;
                if index <= obj.AckQueueCount, ackCount = ackCount + 1; else, dataCount = dataCount + 1; end
                if ~concatenate || numel(frames) >= obj.Config.MaxConcatSegments, break; end
            end
        end

        function preamble = choosePreamble(obj, frames, concatenate)
            now = obj.Scheduler.Now;
            oldest = now;
            finalKnown = false;
            for index = 1:numel(frames)
                destinations = double(frames{index}.DestinationId);
                if concatenate && isfield(frames{index}, 'DestinationIds') && ~isempty(frames{index}.DestinationIds)
                    destinations = double(frames{index}.DestinationIds);
                end
                for peer = destinations(:)'
                    finalKnown = isKey(obj.Neighbors, peer);
                    if finalKnown
                        neighbor = obj.Neighbors(peer);
                        oldest = min(oldest, neighbor.LastHeardSeconds);
                    else
                        oldest = now; % Preserve ordered source-variable reuse.
                    end
                end
            end
            if ~finalKnown || oldest < 0 || now - oldest > obj.postTxSeconds()
                preamble = 'long';
            else
                preamble = 'short';
            end
        end

        function packingRetry(obj)
            obj.PackingRetryEvent = uint64(0);
            obj.schedulePending();
        end

        function finishTx(obj)
            obj.FinishEvent = uint64(0);
            obj.setState('Search');
            if obj.PendingCount > 0
                obj.prepare(false);
            else
                obj.PostTxWaitActive = true;
                obj.PostTxEvent = obj.after(obj.postTxSeconds(), @() obj.postTxExpired());
            end
        end

        function postTxExpired(obj)
            obj.PostTxEvent = uint64(0);
            obj.PostTxWaitActive = false;
            obj.pollReceiver();
            if obj.Config.DutyCycleEnabled && strcmp(obj.State, 'Search')
                obj.cancelTimer('SleepEvent');
                obj.setState('Idle');
            end
        end

        function seconds = postTxSeconds(obj)
            seconds = obj.Config.PostTxBaseSeconds + ...
                obj.Config.PostTxPerNodeSeconds * obj.Config.ActiveNodes + obj.Config.PostTxGuardSeconds;
        end

        function cancelPostTxWait(obj)
            obj.cancelTimer('PostTxEvent');
            obj.PostTxWaitActive = false;
        end

        function pollReceiver(obj)
            if ~strcmp(obj.State, 'Tx') && isfield(obj.Callbacks, 'ReceiverState')
                obj.receiverChanged(obj.Callbacks.ReceiverState());
            end
        end

        function present = hasSync(obj)
            present = false;
            if isfield(obj.Callbacks, 'HasSync'), present = obj.Callbacks.HasSync(); end
        end

        function setState(obj, state)
            previous = obj.State;
            obj.State = state;
            if isfield(obj.Callbacks, 'SetReceiverState') && ~obj.InReceiverUpdate
                obj.InReceiverUpdate = true;
                cleanup = onCleanup(@() obj.finishReceiverUpdate()); %#ok<NASGU>
                obj.Callbacks.SetReceiverState(state);
            end
            if ~strcmp(previous, state), obj.onStateChange(previous, state); end
        end

        function finishReceiverUpdate(obj), obj.InReceiverUpdate = false; end

        function onStateChange(obj, previous, state)
            obj.emit('mac_state', struct(), struct('State', state));
            switch state
                case 'Idle'
                    obj.PreparationActive = false;
                    obj.HoldoffOver = false;
                    obj.cancelTimer('SlotEvent');
                    obj.cancelTimer('HoldoffEvent');
                    obj.cancelTimer('IdleRtsEvent');
                    obj.cancelTimer('PackingRetryEvent');
                    if obj.PendingCount > 0, obj.scheduleIdleRts(); end
                case 'Track'
                    obj.cancelTimer('SleepEvent');
                case 'Search'
                    if strcmp(previous, 'Idle')
                        obj.startSearchTiming();
                    elseif strcmp(previous, 'Track')
                        if obj.PendingCount > 0
                            obj.prepare(false);
                        elseif obj.Config.DutyCycleEnabled && ~obj.PostTxWaitActive
                            obj.cancelTimer('SleepEvent');
                            obj.SleepEvent = obj.after(obj.Config.SearchSeconds, @() obj.sleep());
                        end
                    end
            end
        end

        function id = after(obj, delay, callback)
            id = obj.Scheduler.scheduleAt(obj.Scheduler.Now + double(delay), callback);
        end

        function cancelTimer(obj, name)
            id = obj.(name);
            if id ~= 0, obj.Scheduler.cancel(id); end
            obj.(name) = uint64(0);
        end

        function emit(obj, name, frame, details)
            if isfield(obj.Callbacks, 'Event')
                obj.Callbacks.Event(name, frame, details);
            end
        end
    end
end
