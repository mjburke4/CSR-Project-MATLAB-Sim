classdef SignalEngine < handle
    %SIGNALENGINE Shared CSR network-level receive pipeline, independent of MATLAB APIs.
    % Source: ns-3 main 486d9e0, CsrNetDevice receive/Track/interference pipeline.
    % Every transmission reaches every non-self peer; addressing belongs above
    % PHY. onReceive(frame,receiverId,decision) runs once at physical completion.
    % onTrace(eventName,frame,receiverId,details) is optional and never owns RNG.
    % onState(receiverId,state) is optional. It runs after each actual state
    % transition and its PHY bookkeeping are complete. MAC owns wake/sleep,
    % post-TX wait and access timers; PHY owns acquisition and half-duplex TX.
    %
    % T1 uses source's always-awake Search default. setReceiverState is a
    % controlled Idle/Search hook; MAC duty cycling, post-TX wait and access
    % scheduling belong to T2. Same-rate JSR history intentionally retains
    % ns-3 receiver-global state; high-rate payload jammer state is interval-local.
    properties (Dependent, SetAccess = private)
        ActiveSignalCount
    end
    properties (Access = private)
        Config
        Scheduler
        Streams
        OnReceive
        OnTrace
        OnState
        TransportTiming = []
        Receivers
        NextSignalId = 1
        Outstanding = 0
        MaxActiveSignals = 100000
        MaxIntervalsPerSignal = 10000
        SyncToTrackSeconds = 0.00663
        CaptureMarginDb = 10.5
    end
    methods
        function obj = SignalEngine(config, scheduler, streams, onReceive, onTrace, onState, transportTiming)
            if nargin < 5, onTrace = []; end
            if nargin < 6, onState = []; end
            if ~isa(onReceive,'function_handle') || ...
                    (~isempty(onTrace) && ~isa(onTrace,'function_handle')) || ...
                    (~isempty(onState) && ~isa(onState,'function_handle'))
                error('csr:phy:Callback','Receive and optional trace/state callbacks must be function handles.');
            end
            if nargin>6 && ~isempty(transportTiming)
                if ~isa(transportTiming,'csr.sim.TransportTiming') || ~isscalar(transportTiming)
                    error('csr:phy:TransportTiming','Expected one csr.sim.TransportTiming object.');
                end
                if ~isa(scheduler,'csr.sim.EventScheduler')
                    error('csr:phy:TransportBackend','Optional transport timing is validated only for the portable scheduler.');
                end
                transportTiming.attach(); obj.TransportTiming=transportTiming;
            end
            obj.Config=config; obj.Scheduler=scheduler; obj.Streams=streams;
            obj.OnReceive=onReceive; obj.OnTrace=onTrace; obj.OnState=onState;
            if isfield(config,'Phy')
                options={'MaxActiveSignals','MaxIntervalsPerSignal','SyncToTrackSeconds','CaptureMarginDb'};
                for k=1:numel(options)
                    name=options{k};
                    if isfield(config.Phy,name), obj.(name)=config.Phy.(name); end
                end
            end
            validateattributes(obj.MaxActiveSignals,{'numeric'},{'scalar','integer','positive','finite'});
            validateattributes(obj.MaxIntervalsPerSignal,{'numeric'},{'scalar','integer','positive','finite'});
            validateattributes(obj.SyncToTrackSeconds,{'numeric'},{'scalar','positive','finite'});
            validateattributes(obj.CaptureMarginDb,{'numeric'},{'scalar','real','finite'});
            template=struct('Id',0,'State','Search','Signals',{{}},'TrackedId',0, ...
                'AcquireEvent',uint64(0),'TxEvent',uint64(0),'TxUntil',0, ...
                'SameSpeed',false,'JsrDb',-1000,'TimeOffsetSeconds',0);
            obj.Receivers=repmat(template,1,numel(config.Nodes));
            for k=1:numel(config.Nodes), obj.Receivers(k).Id=config.Nodes(k).Id; end
        end
        function count=get.ActiveSignalCount(obj)
            % Includes scheduled arrivals/completions so the memory limit is
            % enforced before expanding a transmission to all peers.
            count=obj.Outstanding;
        end
        function value=state(obj,nodeId)
            value=obj.Receivers(obj.nodeIndex(nodeId)).State;
        end
        function present=hasSync(obj,nodeId)
            % Match CsrNetDevice::UpdateSyncPresence: presence is the admitted
            % SYNC table, not raw RF energy. Track-rejected admitted preambles
            % remain present; weak/off-band signals never enter this table.
            signals=obj.Receivers(obj.nodeIndex(nodeId)).Signals;
            present=false;
            for k=1:numel(signals)
                if signals{k}.SyncEligible && signals{k}.PreambleActive
                    present=true; return
                end
            end
        end
        function setReceiverState(obj,nodeId,value)
            % MAC's explicit wake/sleep hook; no PHY-owned duty-cycle timer.
            value=char(value); index=obj.nodeIndex(nodeId);
            if ~any(strcmp(value,{'Search','Idle'}))
                error('csr:phy:ReceiverState','Explicit receiver state must be Search or Idle.');
            end
            if strcmp(obj.Receivers(index).State,'Tx')
                error('csr:phy:ReceiverBusy','Cannot override an active half-duplex transmission.');
            end
            previous=obj.Receivers(index).State;
            if strcmp(value,'Idle')
                obj.cancelAcquisition(index);
                for k=1:numel(obj.Receivers(index).Signals)
                    signal=obj.Receivers(index).Signals{k};
                    signal.MissedByState=true;
                    obj.Receivers(index).Signals{k}=signal;
                end
            end
            obj.Receivers(index).State=value;
            if strcmp(value,'Search'), obj.scheduleAcquisition(index); end
            obj.notifyState(index,previous);
        end
        function transmit(obj,frame,duration)
            if nargin<3
                duration=csr.phy.airtime(frame.WirePayloadBytes,frame.RateKeyKbps,frame.Preamble);
            end
            validateattributes(duration,{'numeric'},{'scalar','finite','positive'});
            txIndex=obj.nodeIndex(frame.SourceId); now=obj.Scheduler.Now;
            if strcmp(obj.Receivers(txIndex).State,'Tx') && obj.Receivers(txIndex).TxUntil>now
                error('csr:phy:TransmitterBusy','Node %g is already transmitting.',frame.SourceId);
            end
            peers=numel(obj.Config.Nodes)-1;
            if obj.Outstanding+peers>obj.MaxActiveSignals
                error('csr:phy:ActiveSignalLimit','MaxActiveSignals exceeded before scheduling transmission.');
            end
            if obj.NextSignalId>=flintmax
                error('csr:phy:SignalIdLimit','Signal identifier capacity exhausted.');
            end
            % Preflight every optional receiver target and the observation
            % budget before any PHY state, counter or event is changed.
            timingPlans={}; timingFront=cell(1,numel(obj.Config.Nodes));
            timingByReceiver=cell(1,numel(obj.Config.Nodes));
            if ~isempty(obj.TransportTiming)
                obj.TransportTiming.verifyCapacity(double(peers));
                timingTx=obj.Config.Nodes(txIndex);
                if isfield(frame,'TxPowerDbm') && ~isempty(frame.TxPowerDbm)
                    timingTx.RadioProfile.TxPowerDbm=frame.TxPowerDbm;
                end
                if strcmp(frame.Preamble,'long'), timingBits=7888; else, timingBits=104; end
                for timingIndex=1:numel(obj.Config.Nodes)
                    if timingIndex==txIndex, continue; end
                    timingRx=obj.Config.Nodes(timingIndex);
                    timingFront{timingIndex}=csr.phy.Model.frontEnd(timingTx.RadioProfile, ...
                        timingRx.RadioProfile,timingTx.PositionMeters,timingRx.PositionMeters);
                    timingDelay=timingFront{timingIndex}.DistanceMeters/obj.Config.Channel.PropagationSpeedMps;
                    timingByReceiver{timingIndex}=obj.TransportTiming.plan(now,timingDelay,duration, ...
                        timingBits*0.000510/4,double(frame.SourceId),double(timingRx.Id),frame.Id);
                    timingPlans{end+1}=timingByReceiver{timingIndex}; %#ok<AGROW>
                end
                obj.TransportTiming.record(timingPlans);
            end
            id=obj.NextSignalId; obj.NextSignalId=id+1;
            obj.Outstanding=obj.Outstanding+peers;
            obj.cancelAcquisition(txIndex);
            for k=1:numel(obj.Receivers(txIndex).Signals)
                active=obj.Receivers(txIndex).Signals{k}; active.HalfDuplex=true;
                obj.Receivers(txIndex).Signals{k}=active;
            end
            previous=obj.Receivers(txIndex).State;
            obj.Receivers(txIndex).State='Tx';
            obj.Receivers(txIndex).TxUntil=now+duration;
            if obj.Receivers(txIndex).TxEvent~=0
                obj.Scheduler.cancel(obj.Receivers(txIndex).TxEvent);
            end
            obj.Receivers(txIndex).TxEvent=obj.Scheduler.scheduleAt(now+duration,@()obj.finishTx(txIndex));
            tx=obj.Config.Nodes(txIndex);
            if isfield(frame,'TxPowerDbm') && ~isempty(frame.TxPowerDbm)
                tx.RadioProfile.TxPowerDbm=frame.TxPowerDbm;
            end
            if strcmp(frame.Preamble,'long'), preambleBits=7888; else, preambleBits=104; end
            for index=1:numel(obj.Config.Nodes)
                if index==txIndex, continue; end
                rx=obj.Config.Nodes(index);
                if isempty(obj.TransportTiming)
                    front=csr.phy.Model.frontEnd(tx.RadioProfile,rx.RadioProfile,tx.PositionMeters,rx.PositionMeters);
                else
                    front=timingFront{index};
                end
                delay=front.DistanceMeters/obj.Config.Channel.PropagationSpeedMps;
                signal=struct('Id',id,'Frame',frame,'FrontEnd',front,'StartSec',now+delay, ...
                    'EndSec',now+delay+duration,'PreambleEndSec',now+delay+preambleBits*0.000510/4, ...
                    'PreambleBits',preambleBits,'PacketBits',preambleBits+48+8*frame.WirePayloadBytes+32, ...
                    'IntervalStartSec',now+delay,'IntervalCount',0, ...
                    'DecisionSameRate',false,'DecisionJsrDb',-Inf,'DecisionTimeOffset',0, ...
                    'HasHighRatePayloadJammer',false, ...
                    'Allocation',obj.emptyAllocation(),'NoiseIds',[],'NoiseWatts',[], ...
                    'SyncEligible',false,'PreambleActive',true,'Rejected',false, ...
                    'RejectedDuringTrack',false,'Tracked',false,'Collided',false, ...
                    'MissedByState',false,'HalfDuplex',false,'CollisionCount',0,'CaptureCount',0, ...
                    'SameRateInterference',false,'JsrDb',-Inf,'TimeOffsetSeconds',0);
                startCallback=signal.StartSec; endCallback=signal.EndSec;
                if ~isempty(obj.TransportTiming)
                    timing=timingByReceiver{index};
                    startCallback=timing.StartSeconds; endCallback=timing.EndSeconds;
                    signal.CallbackPreambleEndSec=timing.PreambleEndSeconds;
                    signal.CallbackEndSec=timing.EndSeconds;
                end
                if front.Closure
                    obj.Scheduler.scheduleAt(startCallback,@()obj.beginSignal(index,signal));
                else
                    % Source emits closure immediately; the portable application
                    % accounting callback is intentionally completion-timed.
                    obj.Scheduler.scheduleAt(endCallback,@()obj.finishOccluded(index,signal));
                end
            end
            obj.notifyState(txIndex,previous);
        end
    end
    methods (Access=private)
        function index=nodeIndex(obj,id)
            index=find([obj.Receivers.Id]==id,1);
            if isempty(index), error('csr:phy:Endpoint','Unknown radio node %g.',id); end
        end
        function index=signalIndex(obj,receiver,id)
            signals=obj.Receivers(receiver).Signals; index=[];
            for k=1:numel(signals)
                if signals{k}.Id==id, index=k; return; end
            end
        end
        function finishTx(obj,index)
            previous=obj.Receivers(index).State;
            obj.Receivers(index).TxEvent=uint64(0);
            obj.Receivers(index).State='Search';
            obj.scheduleAcquisition(index);
            obj.notifyState(index,previous);
        end
        function cancelAcquisition(obj,index)
            id=obj.Receivers(index).AcquireEvent;
            if id~=0, obj.Scheduler.cancel(id); end
            obj.Receivers(index).AcquireEvent=uint64(0);
        end
        function scheduleAcquisition(obj,index)
            rx=obj.Receivers(index);
            if ~strcmp(rx.State,'Search') || rx.AcquireEvent~=0, return; end
            eligible=false;
            for k=1:numel(rx.Signals)
                eligible=eligible || (rx.Signals{k}.SyncEligible && rx.Signals{k}.PreambleActive);
            end
            if eligible
                obj.Receivers(index).AcquireEvent=obj.Scheduler.scheduleAt( ...
                    obj.Scheduler.Now+obj.SyncToTrackSeconds,@()obj.acquire(index));
            end
        end
        function beginSignal(obj,index,incoming)
            % Native BeginReceiveSignal starts error intervals at the actual
            % callback time while retaining continuous physical signal times.
            if ~isempty(obj.TransportTiming), incoming.IntervalStartSec=obj.Scheduler.Now; end
            obj.closeIntervals(index,obj.Scheduler.Now);
            % Signals are appended in arrival order; pair overwrite order is
            % deliberately arrival order, independently of transmitter IDs.
            for k=1:numel(obj.Receivers(index).Signals)
                prior=obj.Receivers(index).Signals{k};
                [incoming,prior]=obj.interferencePair(index,incoming,prior);
                obj.Receivers(index).Signals{k}=prior;
            end
            if incoming.FrontEnd.ChannelMatched
                profile=obj.Config.Nodes(index).RadioProfile;
                threshold=profile.SyncSnrThresholdDb;
                if profile.StochasticSyncThreshold && profile.SyncSnrThresholdVarianceDb2>0
                    threshold=threshold+sqrt(profile.SyncSnrThresholdVarianceDb2)* ...
                        randn(obj.Streams.get(obj.Receivers(index).Id,'sync'));
                end
                incoming.SyncEligible=obj.signalSnr(incoming)>=threshold;
                if ~incoming.SyncEligible, incoming.Rejected=true; end
            end
            stateNow=obj.Receivers(index).State;
            if strcmp(stateNow,'Tx')
                incoming.MissedByState=true; incoming.HalfDuplex=true;
            elseif strcmp(stateNow,'Track')
                incoming.Rejected=true; incoming.RejectedDuringTrack=true;
                trackedIndex=obj.signalIndex(index,obj.Receivers(index).TrackedId);
                if ~isempty(trackedIndex)
                    tracked=obj.Receivers(index).Signals{trackedIndex};
                    if incoming.FrontEnd.ChannelMatched && tracked.Frame.RateKeyKbps==incoming.Frame.RateKeyKbps
                        if tracked.FrontEnd.ReceivedPowerDbm-incoming.FrontEnd.ReceivedPowerDbm<obj.CaptureMarginDb
                            tracked.Collided=true;
                        else
                            tracked.CaptureCount=tracked.CaptureCount+1;
                        end
                    end
                    obj.Receivers(index).Signals{trackedIndex}=tracked;
                end
            elseif strcmp(stateNow,'Idle')
                incoming.MissedByState=true;
            end
            % mark_sync rejection never enters the SYNC table and therefore
            % never schedules clear_sync, which could cancel another acquisition.
            preambleCallback=incoming.PreambleEndSec; endCallback=incoming.EndSec;
            if ~isempty(obj.TransportTiming)
                preambleCallback=incoming.CallbackPreambleEndSec; endCallback=incoming.CallbackEndSec;
            end
            if incoming.SyncEligible
                obj.Scheduler.scheduleAt(preambleCallback,@()obj.endPreamble(index,incoming.Id));
            else
                incoming.PreambleActive=false;
            end
            obj.Receivers(index).Signals{end+1}=incoming;
            obj.Scheduler.scheduleAt(endCallback,@()obj.endSignal(index,incoming.Id));
            obj.emit('phy_signal_start',index,incoming,struct('SyncEligible',incoming.SyncEligible, ...
                'SnrDb',obj.signalSnr(incoming),'ReceivedPowerDbm',incoming.FrontEnd.ReceivedPowerDbm));
            obj.scheduleAcquisition(index);
        end
        function [first,second]=interferencePair(obj,index,first,second)
            if ~first.FrontEnd.ChannelMatched || ~second.FrontEnd.ChannelMatched || ...
                    first.EndSec<=obj.Scheduler.Now || second.EndSec<=obj.Scheduler.Now
                return
            end
            first.CollisionCount=first.CollisionCount+1;
            second.CollisionCount=second.CollisionCount+1;
            if first.Frame.RateKeyKbps==second.Frame.RateKeyKbps
                obj.Receivers(index).SameSpeed=true;
                if ~first.Rejected && ~second.Rejected
                    if first.FrontEnd.ReceivedPowerDbm>second.FrontEnd.ReceivedPowerDbm
                        desired=first; jammer=second;
                    else
                        desired=second; jammer=first;
                    end
                elseif ~first.Rejected
                    desired=first; jammer=second;
                elseif ~second.Rejected
                    desired=second; jammer=first;
                else
                    desired=[]; jammer=[];
                end
                if ~isempty(desired)
                    obj.Receivers(index).JsrDb=jammer.FrontEnd.ReceivedPowerDbm-desired.FrontEnd.ReceivedPowerDbm;
                    obj.Receivers(index).TimeOffsetSeconds=jammer.StartSec-desired.StartSec;
                end
                if ~first.Rejected, first=obj.recordJammer(first,second); end
                if ~second.Rejected, second=obj.recordJammer(second,first); end
            else
                obj.Receivers(index).SameSpeed=false;
                if ~first.Rejected
                    first.NoiseIds(end+1)=second.Id;
                    first.NoiseWatts(end+1)=second.FrontEnd.ReceivedPowerWatts;
                end
                if ~second.Rejected
                    second.NoiseIds(end+1)=first.Id;
                    second.NoiseWatts(end+1)=first.FrontEnd.ReceivedPowerWatts;
                end
            end
        end
        function signal=recordJammer(~,signal,jammer)
            if ~signal.FrontEnd.ChannelMatched || ~jammer.FrontEnd.ChannelMatched || ...
                    signal.FrontEnd.ReceivedPowerWatts<=0 || jammer.FrontEnd.ReceivedPowerWatts<=0
                return
            end
            jsr=jammer.FrontEnd.ReceivedPowerDbm-signal.FrontEnd.ReceivedPowerDbm;
            if ~signal.SameRateInterference || jsr>signal.JsrDb
                signal.SameRateInterference=true; signal.JsrDb=jsr;
                signal.TimeOffsetSeconds=jammer.StartSec-signal.StartSec;
            end
        end
        function value=signalSnr(~,signal)
            value=csr.phy.Model.snrDb(signal.FrontEnd.ReceivedPowerWatts, ...
                signal.FrontEnd.BackgroundNoiseWatts+sum(signal.NoiseWatts));
        end
        function endPreamble(obj,index,id)
            k=obj.signalIndex(index,id); if isempty(k), return; end
            signal=obj.Receivers(index).Signals{k}; signal.PreambleActive=false;
            if ~strcmp(obj.Receivers(index).State,'Track'), signal.Rejected=true; end
            obj.Receivers(index).Signals{k}=signal;
            % Source clear_sync cancels even if a different preamble remains.
            obj.cancelAcquisition(index);
        end
        function acquire(obj,index)
            obj.Receivers(index).AcquireEvent=uint64(0);
            if ~strcmp(obj.Receivers(index).State,'Search'), return; end
            candidates=[];
            for k=1:numel(obj.Receivers(index).Signals)
                s=obj.Receivers(index).Signals{k};
                if s.SyncEligible && s.PreambleActive && (~s.Rejected || s.RejectedDuringTrack)
                    candidates(end+1)=k; %#ok<AGROW>
                end
            end
            if isempty(candidates), return; end
            selected=candidates(1);
            for k=candidates(2:end)
                s=obj.Receivers(index).Signals{k}; best=obj.Receivers(index).Signals{selected};
                if obj.Scheduler.Now-s.StartSec>obj.SyncToTrackSeconds && ...
                        s.FrontEnd.ReceivedPowerDbm>best.FrontEnd.ReceivedPowerDbm
                    selected=k;
                end
            end
            obj.closeIntervals(index,obj.Scheduler.Now);
            signal=obj.Receivers(index).Signals{selected};
            signal.Rejected=false; signal.RejectedDuringTrack=false;
            signal.Tracked=true; signal.MissedByState=false; signal.HalfDuplex=false;
            strongest=[]; sameRatePower=-Inf;
            for k=candidates
                if k==selected, continue; end
                other=obj.Receivers(index).Signals{k};
                other.Rejected=true; other.RejectedDuringTrack=true;
                obj.Receivers(index).Signals{k}=other;
                if isempty(strongest) || other.FrontEnd.ReceivedPowerDbm>strongest.FrontEnd.ReceivedPowerDbm
                    strongest=other;
                end
                if other.Frame.RateKeyKbps==signal.Frame.RateKeyKbps && other.FrontEnd.ChannelMatched
                    sameRatePower=max(sameRatePower,other.FrontEnd.ReceivedPowerDbm);
                end
            end
            if ~isempty(strongest)
                obj.Receivers(index).JsrDb=strongest.FrontEnd.ReceivedPowerDbm-signal.FrontEnd.ReceivedPowerDbm;
                obj.Receivers(index).TimeOffsetSeconds=strongest.StartSec-signal.StartSec;
            end
            if isfinite(sameRatePower)
                if signal.FrontEnd.ReceivedPowerDbm-sameRatePower<obj.CaptureMarginDb
                    signal.Collided=true;
                else
                    signal.CaptureCount=signal.CaptureCount+1;
                end
            end
            obj.Receivers(index).Signals{selected}=signal;
            obj.Receivers(index).TrackedId=signal.Id;
            previous=obj.Receivers(index).State;
            obj.Receivers(index).State='Track';
            obj.emit('phy_track',index,signal,struct('Collided',signal.Collided,'JsrDb',obj.Receivers(index).JsrDb));
            obj.notifyState(index,previous);
        end
        function closeIntervals(obj,index,endSec)
            for k=1:numel(obj.Receivers(index).Signals)
                signal=obj.Receivers(index).Signals{k}; stop=min(endSec,signal.EndSec);
                if stop<=signal.IntervalStartSec, continue; end
                if signal.IntervalCount>=obj.MaxIntervalsPerSignal
                    error('csr:phy:IntervalLimit','MaxIntervalsPerSignal exceeded; increase the explicit scenario limit.');
                end
                interval=csr.phy.Model.interval(signal.IntervalStartSec,stop, ...
                    signal.FrontEnd.BackgroundNoiseWatts+sum(signal.NoiseWatts));
                interval.CollisionCount=signal.CollisionCount;
                interval.SameRateInterference=obj.Receivers(index).SameSpeed;
                interval.JsrDb=obj.Receivers(index).JsrDb;
                interval.TimeOffsetSeconds=obj.Receivers(index).TimeOffsetSeconds;
                if signal.Frame.RateKeyKbps>=500
                    interval.HighRatePayloadJammer=signal.SameRateInterference;
                    interval.HighRatePayloadJsrDb=signal.JsrDb;
                end
                allocated=csr.phy.Model.allocateErrors(obj.Config.Nodes(index).RadioProfile, ...
                    signal.FrontEnd,signal.StartSec,signal.PreambleBits,signal.PacketBits, ...
                    signal.Frame.RateKeyKbps,interval,obj.Streams.get(obj.Receivers(index).Id,'phy'));
                a=signal.Allocation;
                for name={'HeaderBits','PayloadBits','HeaderErrors','PayloadErrors','TotalErrors'}
                    a.(name{1})=a.(name{1})+allocated.(name{1});
                end
                for name={'ActualBer','HeaderBer','PayloadBer'}, a.(name{1})=allocated.(name{1}); end
                a.MinimumSnrDb=min(a.MinimumSnrDb,allocated.MinimumSnrDb);
                a.PeakNoisePowerWatts=max(a.PeakNoisePowerWatts,allocated.PeakNoisePowerWatts);
                a.PacketErrorProbability=1-(1-a.PacketErrorProbability)*(1-allocated.PacketErrorProbability);
                signal.Allocation=a; signal.IntervalCount=signal.IntervalCount+1;
                % Fold the source EvaluateAllocatedRx interval diagnostics
                % incrementally, retaining strongest high-rate payload JSR
                % or the last receiver-global same-rate JSR otherwise.
                if interval.HighRatePayloadJammer
                    if ~signal.HasHighRatePayloadJammer || interval.HighRatePayloadJsrDb>signal.DecisionJsrDb
                        signal.DecisionSameRate=true; signal.DecisionJsrDb=interval.HighRatePayloadJsrDb;
                        signal.DecisionTimeOffset=interval.TimeOffsetSeconds;
                    end
                    signal.HasHighRatePayloadJammer=true;
                elseif ~signal.HasHighRatePayloadJammer && interval.SameRateInterference
                    signal.DecisionSameRate=true; signal.DecisionJsrDb=interval.JsrDb;
                    signal.DecisionTimeOffset=interval.TimeOffsetSeconds;
                end
                signal.IntervalStartSec=stop;
                obj.Receivers(index).Signals{k}=signal;
                details=interval; details.HeaderErrors=allocated.HeaderErrors;
                details.PayloadErrors=allocated.PayloadErrors;
                obj.emit('phy_interval',index,signal,details);
            end
        end
        function finishOccluded(obj,index,signal)
            decision=obj.makeDecision(index,signal,false);
            decision.Closure=false; decision.Success=false; decision.Reason='closure';
            obj.Outstanding=obj.Outstanding-1;
            obj.emit('phy_signal_end',index,signal,decision);
            obj.OnReceive(signal.Frame,obj.Receivers(index).Id,decision);
        end
        function endSignal(obj,index,id)
            k=obj.signalIndex(index,id); if isempty(k), return; end
            obj.closeIntervals(index,obj.Scheduler.Now);
            signal=obj.Receivers(index).Signals{k};
            wasTracked=obj.Receivers(index).TrackedId==id;
            decision=obj.makeDecision(index,signal,wasTracked);
            obj.Receivers(index).Signals(k)=[];
            if wasTracked, obj.Receivers(index).TrackedId=0; end
            for j=1:numel(obj.Receivers(index).Signals)
                other=obj.Receivers(index).Signals{j}; keep=other.NoiseIds~=id;
                other.NoiseIds=other.NoiseIds(keep); other.NoiseWatts=other.NoiseWatts(keep);
                obj.Receivers(index).Signals{j}=other;
            end
            obj.refreshHighRateInterference(index);
            obj.Outstanding=obj.Outstanding-1;
            if ~isempty(obj.OnState)
                % ns-3 delivers decoded segments while still Track, allowing
                % HOP to enqueue ACK before MAC's Track -> Search preparation.
                % Retire PHY signal bookkeeping first so callbacks cannot
                % invalidate indices in this completed receive operation.
                obj.emit('phy_signal_end',index,signal,decision);
                obj.OnReceive(signal.Frame,obj.Receivers(index).Id,decision);
            end
            resumeTracked=wasTracked && ~strcmp(obj.Receivers(index).State,'Tx');
            if ~isempty(obj.OnState)
                % The completed frame no longer owns a receiver that MAC
                % synchronously slept or woke during its receive callback.
                resumeTracked=resumeTracked && strcmp(obj.Receivers(index).State,'Track');
            end
            if resumeTracked
                if decision.Success
                    obj.returnToSearch(index);
                else
                    % ns-3 nanosecond resolution quantizes 1/36 MHz to 28 ns.
                    obj.Scheduler.scheduleAt(obj.Scheduler.Now+28e-9,@()obj.returnRejectedToSearch(index));
                end
            end
            if isempty(obj.OnState)
                % Preserve T1's callback-observable ordering for standalone
                % consumers that have not installed the MAC state bridge.
                obj.emit('phy_signal_end',index,signal,decision);
                obj.OnReceive(signal.Frame,obj.Receivers(index).Id,decision);
            end
        end
        function returnRejectedToSearch(obj,index)
            % A MAC-owned wake/sleep change can supersede a rejected packet's
            % fallback. Do not let its old completion wake the receiver again.
            if ~isempty(obj.OnState) && ~strcmp(obj.Receivers(index).State,'Track'), return; end
            obj.returnToSearch(index);
        end
        function returnToSearch(obj,index)
            if strcmp(obj.Receivers(index).State,'Tx'), return; end
            previous=obj.Receivers(index).State;
            obj.Receivers(index).State='Search'; obj.scheduleAcquisition(index);
            obj.notifyState(index,previous);
        end
        function refreshHighRateInterference(obj,index)
            signals=obj.Receivers(index).Signals;
            for k=1:numel(signals)
                s=signals{k}; if s.Frame.RateKeyKbps<500, continue; end
                s.SameRateInterference=false; s.JsrDb=-Inf; s.TimeOffsetSeconds=0;
                if ~s.Rejected
                    for j=1:numel(signals)
                        if j~=k && signals{j}.Frame.RateKeyKbps==s.Frame.RateKeyKbps
                            s=obj.recordJammer(s,signals{j});
                        end
                    end
                end
                obj.Receivers(index).Signals{k}=s;
            end
        end
        function decision=makeDecision(obj,index,signal,wasTracked)
            front=signal.FrontEnd; a=signal.Allocation;
            stateAllows=strcmp(obj.Receivers(index).State,'Track');
            ecc=csr.phy.Model.ecc(obj.Config.Nodes(index).RadioProfile, ...
                signal.PacketBits,signal.PreambleBits,a.TotalErrors, ...
                wasTracked && stateAllows && ~signal.Rejected && front.ChannelMatched,false,false);
            decision=struct('Success',ecc.Accepted,'Reason','prior_stage','Closure',front.Closure, ...
                'ChannelMatched',front.ChannelMatched,'Tracked',wasTracked,'Collided',signal.Collided, ...
                'CollisionCount',signal.CollisionCount,'CaptureCount',signal.CaptureCount, ...
                'Captured',signal.CaptureCount>0,'PathModel',front.PathModel, ...
                'DistanceMeters',front.DistanceMeters,'PathlossDb',front.PathlossDb, ...
                'ReceivedPowerDbm',front.ReceivedPowerDbm,'NoisePowerWatts',a.PeakNoisePowerWatts, ...
                'NoisePowerDbm',csr.phy.Model.wattsToDbm(a.PeakNoisePowerWatts), ...
                'SnrDb',a.MinimumSnrDb,'Per',a.PacketErrorProbability, ...
                'SameRateInterference',signal.DecisionSameRate,'JsrDb',signal.DecisionJsrDb, ...
                'TimeOffsetSeconds',signal.DecisionTimeOffset,'HeaderBer',a.HeaderBer,'PayloadBer',a.PayloadBer, ...
                'ActualBer',a.ActualBer,'HeaderErrors',a.HeaderErrors,'PayloadErrors',a.PayloadErrors, ...
                'TotalErrors',a.TotalErrors,'ProtectedBits',ecc.ProtectedBits, ...
                'CorrectableBits',ecc.CorrectableBits,'EccDropped',ecc.EccDropped, ...
                'IntervalCount',signal.IntervalCount,'SignalId',signal.Id);
            if decision.Success
                decision.Reason='accepted';
            elseif ~front.Closure
                decision.Reason='closure';
            elseif ~front.ChannelMatched
                decision.Reason='channel_mismatch';
            elseif strcmp(obj.Receivers(index).State,'Tx') || signal.HalfDuplex
                decision.Reason='half_duplex';
            elseif ecc.EccDropped
                decision.Reason='ecc';
            elseif ~signal.SyncEligible
                decision.Reason='sync_threshold';
            elseif signal.MissedByState
                decision.Reason='receiver_state';
            elseif ~wasTracked
                decision.Reason='not_acquired';
            elseif signal.Rejected
                decision.Reason='acquisition_rejected';
            end
        end
        function emit(obj,name,index,signal,details)
            if isempty(obj.OnTrace), return; end
            details.TimeSeconds=obj.Scheduler.Now; details.SignalId=signal.Id;
            obj.OnTrace(name,signal.Frame,obj.Receivers(index).Id,details);
        end
        function notifyState(obj,index,previous)
            current=obj.Receivers(index).State;
            if isempty(obj.OnState) || strcmp(previous,current), return; end
            % Call only at the end of a transition. A MAC callback can safely
            % query state/SYNC or schedule work without later PHY assignment
            % overwriting a synchronous Idle/Search decision it makes here.
            obj.OnState(obj.Receivers(index).Id,current);
        end
    end
    methods (Static,Access=private)
        function result=emptyAllocation()
            result=struct('HeaderBits',0,'PayloadBits',0,'HeaderErrors',0,'PayloadErrors',0, ...
                'TotalErrors',0,'ActualBer',0,'HeaderBer',0,'PayloadBer',0, ...
                'MinimumSnrDb',Inf,'PeakNoisePowerWatts',0,'PacketErrorProbability',0);
        end
    end
end
