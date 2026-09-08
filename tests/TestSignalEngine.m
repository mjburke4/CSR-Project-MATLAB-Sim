classdef TestSignalEngine < matlab.unittest.TestCase
    % Prepared controlled receive-pipeline tests. Requires actual MATLAB.
    methods (Test)
        function allPeersObservePhysicalSignalOnce(test)
            c=engineConfig(3); f=engineFrame(1,1,2,8,'short',64);
            [records,~,engine,scheduler]=exercise(c,{f},0,1);
            test.verifyEqual(numel(records),2);
            test.verifyEqual(sort([records.ReceiverId]),[2 3]);
            test.verifyTrue(all(arrayfun(@(r)r.Decision.Success,records)));
            test.verifyEqual(engine.ActiveSignalCount,0);
            scheduler.run(2);
            test.verifyEqual(engine.ActiveSignalCount,0);
            test.verifyEqual(scheduler.PendingCount,0);
        end
        function framePowerOverrideReachesFrontEnd(test)
            c=engineConfig(2); f=engineFrame(1,1,2,8,'short',64);
            f.TxPowerDbm=-20;
            records=exercise(c,{f},0,1);
            test.verifyNumElements(records,1);
            test.verifyEqual(records.Decision.ReceivedPowerDbm,-20,'AbsTol',1e-12);
        end
        function horizonLeavesPhysicalCompletionsPending(test)
            c=engineConfig(3); f=engineFrame(1,1,2,8,'long',64);
            [records,~,engine]=exercise(c,{f},0,0.01);
            test.verifyEmpty(records);
            test.verifyEqual(engine.ActiveSignalCount,2);
            test.verifyEqual(engine.state(2),'Track');
        end
        function halfDuplexCannotDeliver(test)
            c=engineConfig(2);
            a=engineFrame(1,1,2,8,'short',64);
            b=engineFrame(2,2,1,8,'short',64);
            records=exercise(c,{a,b},[0 0],1);
            test.verifyEqual(numel(records),2);
            test.verifyFalse(any(arrayfun(@(r)r.Decision.Success,records)));
            test.verifyTrue(all(arrayfun(@(r)strcmp(r.Decision.Reason,'half_duplex'),records)));
            test.verifyFalse(any(arrayfun(@(r)r.Decision.EccDropped,records)));
        end
        function nonDestinationTrackPreventsAnotherAcquisition(test)
            c=engineConfig(4);
            a=engineFrame(1,1,2,8,'long',64);
            b=engineFrame(2,4,3,8,'short',64);
            [records,trace]=exercise(c,{a,b},[0 0.03],2);
            target=records([records.FrameId]==2 & [records.ReceiverId]==3);
            test.verifyNumElements(target,1);
            test.verifyFalse(target.Decision.Success);
            test.verifyFalse(target.Decision.Tracked);
            tracks=trace(strcmp({trace.Event},'phy_track') & [trace.ReceiverId]==3);
            test.verifyTrue(any([tracks.FrameId]==1));
            test.verifyFalse(any([tracks.FrameId]==2));
        end
        function belowThresholdPreambleDoesNotCancelOtherAcquisition(test)
            % Reproduces main's rejected-preamble fix: rejected short SYNC
            % expires at .01326 while valid acquisition is due at .01563.
            c=engineConfig(3); c.Nodes(1).RadioProfile.TxPowerDbm=-200;
            weak=engineFrame(1,1,2,8,'short',64);
            good=engineFrame(2,3,2,8,'short',64);
            [records,trace]=exercise(c,{weak,good},[0 0.009],1);
            target=records([records.FrameId]==2 & [records.ReceiverId]==2);
            test.verifyNumElements(target,1); test.verifyTrue(target.Decision.Success);
            tracks=trace(strcmp({trace.Event},'phy_track') & [trace.ReceiverId]==2 & [trace.FrameId]==2);
            test.verifyNumElements(tracks,1);
            test.verifyEqual(tracks.Details.TimeSeconds,0.01563,'AbsTol',1e-12);
        end
        function strongTrackCapturesLaterWeakSignal(test)
            c=engineConfig(3); c.Nodes(3).RadioProfile.TxPowerDbm=-20;
            a=engineFrame(1,1,2,8,'short',64);
            b=engineFrame(2,3,2,8,'short',64);
            records=exercise(c,{a,b},[0 0.03],1);
            desired=records([records.ReceiverId]==2 & [records.FrameId]==1);
            test.verifyTrue(desired.Decision.Tracked);
            test.verifyTrue(desired.Decision.Captured);
            test.verifyEqual(desired.Decision.CaptureCount,1);
            test.verifyFalse(desired.Decision.Collided);
        end
        function mismatchedSignalDoesNotJamMatchedReceiver(test)
            c=engineConfig(3); c.Nodes(3).RadioProfile.TxBaseFrequencyHz=40e6;
            a=engineFrame(1,1,2,8,'short',64);
            b=engineFrame(2,3,2,8,'short',64);
            records=exercise(c,{a,b},[0 0],1);
            target=records([records.ReceiverId]==2);
            good=target([target.FrameId]==1); bad=target([target.FrameId]==2);
            test.verifyTrue(good.Decision.Success);
            test.verifyEqual(good.Decision.CollisionCount,0);
            test.verifyFalse(bad.Decision.ChannelMatched);
            test.verifyEqual(bad.Decision.Reason,'channel_mismatch');
        end
        function closureExcludedFromInterference(test)
            c=engineConfig(3);
            c.Nodes(3).PositionMeters=[100000 0 0];
            c.Nodes(2).RadioProfile.ClosureMode='EARTH_LINE_OF_SIGHT';
            a=engineFrame(1,1,2,8,'short',64);
            b=engineFrame(2,3,2,8,'short',64);
            records=exercise(c,{a,b},[0 0],1);
            target=records([records.ReceiverId]==2);
            good=target([target.FrameId]==1); bad=target([target.FrameId]==2);
            test.verifyTrue(good.Decision.Success);
            test.verifyEqual(good.Decision.CollisionCount,0);
            test.verifyFalse(bad.Decision.Closure);
            test.verifyEqual(bad.Decision.Reason,'closure');
        end
        function differentRateNoiseRemovedAtJammerEnd(test)
            c=engineConfig(3);
            a=engineFrame(1,1,2,8,'short',64);
            b=engineFrame(2,3,2,500,'short',64);
            [~,trace]=exercise(c,{a,b},[0 0.03],1);
            intervals=trace(strcmp({trace.Event},'phy_interval') & [trace.ReceiverId]==2 & [trace.FrameId]==1);
            noise=arrayfun(@(r)r.Details.NoisePowerWatts,intervals);
            background=csr.phy.Model.dbmToWatts(c.Nodes(2).RadioProfile.NoiseFloorDbm);
            test.verifyGreaterThan(max(noise),1000*background);
            test.verifyEqual(noise(end),background,'RelTol',1e-12);
        end
        function highRateJammerIsSignedAndIntervalLocal(test)
            c=engineConfig(3); c.Nodes(3).RadioProfile.TxPowerDbm=20;
            a=engineFrame(1,1,2,500,'short',8192);
            b=engineFrame(2,3,2,500,'short',64);
            [records,trace]=exercise(c,{a,b},[0 0.03],1);
            intervals=trace(strcmp({trace.Event},'phy_interval') & [trace.ReceiverId]==2 & [trace.FrameId]==1);
            jammed=arrayfun(@(r)r.Details.HighRatePayloadJammer,intervals);
            test.verifyTrue(any(jammed));
            test.verifyFalse(jammed(end));
            jsr=arrayfun(@(r)r.Details.HighRatePayloadJsrDb,intervals(jammed));
            test.verifyEqual(jsr,20*ones(size(jsr)),'AbsTol',1e-10);
            target=records([records.ReceiverId]==2 & [records.FrameId]==1);
            test.verifyEqual(target.Decision.JsrDb,20,'AbsTol',1e-10);
        end
        function activeSignalLimitRejectsBeforeMutation(test)
            c=engineConfig(3); c.Phy.MaxActiveSignals=1;
            scheduler=csr.sim.EventScheduler(); streams=csr.sim.RandomStreams(12);
            engine=csr.phy.SignalEngine(c,scheduler,streams,@(~,~,~)[]);
            f=engineFrame(1,1,2,8,'short',64);
            test.verifyError(@()engine.transmit(f),'csr:phy:ActiveSignalLimit');
            test.verifyEqual(engine.ActiveSignalCount,0);
            test.verifyEqual(scheduler.PendingCount,0);
            test.verifyEqual(engine.state(1),'Search');
        end
        function explicitIdleMustWakeBeforePreambleExpires(test)
            c=engineConfig(2); scheduler=csr.sim.EventScheduler();
            streams=csr.sim.RandomStreams(12); records={};
            engine=csr.phy.SignalEngine(c,scheduler,streams,@receive);
            engine.setReceiverState(2,'Idle');
            f=engineFrame(1,1,2,8,'long',64); engine.transmit(f);
            scheduler.scheduleAt(0.05,@()engine.setReceiverState(2,'Search'));
            scheduler.run(2);
            test.verifyNumElements(records,1);
            test.verifyTrue(records{1}.Success);
            function receive(~,~,decision)
                records{end+1}=decision;
            end
        end
    end
end

function c=engineConfig(count)
c=csr.scenario.smallNetwork();
profile=csr.phy.RadioProfile.defaults();
profile.ClosureMode='NEVER_OCCLUDED'; profile.StochasticSyncThreshold=false;
% Co-location invokes unit path gain and removes floating-point propagation
% offsets so same-time ordering tests have exact controlled arrivals.
node=struct('Id',1,'PositionMeters',[0 0 0],'RadioProfile',profile);
c.Nodes=repmat(node,1,count);
for k=1:count, c.Nodes(k).Id=k; end
c.Phy=struct('MaxActiveSignals',1000,'MaxIntervalsPerSignal',1000, ...
    'SyncToTrackSeconds',0.00663,'CaptureMarginDb',10.5);
end

function frame=engineFrame(id,source,destination,rate,preamble,bytes)
flow=struct('SourceId',source,'DestinationId',destination,'ApplicationPayloadBytes',bytes);
radio=struct('RateKeyKbps',rate,'Preamble',preamble,'EnvelopeProfile','bare');
frame=csr.packet(id,flow,0,radio);
end

function [records,trace,engine,scheduler]=exercise(config,frames,times,horizon)
records=struct('FrameId',{},'ReceiverId',{},'Decision',{});
trace=struct('Event',{},'FrameId',{},'ReceiverId',{},'Details',{});
scheduler=csr.sim.EventScheduler(); streams=csr.sim.RandomStreams(12);
engine=csr.phy.SignalEngine(config,scheduler,streams,@receive,@recordTrace);
for k=1:numel(frames)
    frame=frames{k}; scheduler.scheduleAt(times(k),@()engine.transmit(frame));
end
scheduler.run(horizon);
    function receive(frame,receiver,decision)
        records(end+1)=struct('FrameId',frame.Id,'ReceiverId',receiver,'Decision',decision);
    end
    function recordTrace(event,frame,receiver,details)
        trace(end+1)=struct('Event',event,'FrameId',frame.Id,'ReceiverId',receiver,'Details',details);
    end
end
