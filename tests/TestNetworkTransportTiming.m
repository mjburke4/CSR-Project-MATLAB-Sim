classdef TestNetworkTransportTiming < matlab.unittest.TestCase
    % Prepared MATLAB checks for the optional real receive-pipeline seam.
    methods (Test)
        function policyRejectsInvalidModesTimesAndUnsafeIntegerSums(test)
            test.verifyError(@()csr.sim.TransportTiming('rounded'),'csr:sim:TransportMode');
            timing=csr.sim.TransportTiming('nanoseconds');
            test.verifyError(@()timing.plan(NaN,0,0.1,0.01,1,2,uint64(1)),'csr:sim:TransportTime');
            test.verifyError(@()timing.plan(0,0,0.01,0.1,1,2,uint64(1)),'csr:sim:TransportTime');
            test.verifyError(@()timing.plan(flintmax/1e9,1,0.1,0.01,1,2,uint64(1)),'csr:sim:TransportTime');
            test.verifyEqual(timing.Count,0);
        end
        function independentComponentsPreservePhysicalTargetsAndWideIdentity(test)
            timing=csr.sim.TransportTiming('nanoseconds');
            id=bitshift(uint64(1),60)+uint64(37);
            row=timing.plan(1.4e-9,1.4e-9,0.0132600004,0.0066300004,1,2,id);
            test.verifyEqual(row.StartNanoseconds,2);
            test.verifyEqual(row.EndNanoseconds,13260002);
            test.verifyEqual(row.PreambleEndNanoseconds,6630002);
            test.verifyEqual(row.StartSeconds,2e-9);
            test.verifyEqual(num2hex(row.PhysicalStartSeconds),num2hex(1.4e-9+1.4e-9));
            test.verifyNotEqual(row.PhysicalEndSeconds,row.EndSeconds);
            timing.record({row}); report=timing.snapshot();
            test.verifyEqual(report.Records.FrameId,id);
            test.verifyEqual(report.Records.Ordinal,uint64(1));
            test.verifyEqual(report.Omitted,0);
        end
        function continuousModeRetainsSignalEngineOperandOrderExactly(test)
            timing=csr.sim.TransportTiming('continuous');
            tx=2.4446320000000004; propagation=4e-6; duration=0.026519999999999998;
            row=timing.plan(tx,propagation,duration,0.01326,1,2,uint64(1));
            test.verifyEqual(num2hex(row.StartSeconds),num2hex(tx+propagation));
            test.verifyEqual(num2hex(row.EndSeconds),num2hex(tx+propagation+duration));
            test.verifyEqual(num2hex(row.PreambleEndSeconds),num2hex(tx+propagation+0.01326));
            test.verifyEqual([row.StartShiftSeconds row.PreambleEndShiftSeconds row.EndShiftSeconds],[0 0 0]);
        end
        function pastArrivalAndRecordOverflowRejectBeforePhyMutation(test)
            c=engineConfig(2); f=engineFrame(1,1,2,8,'short',64);
            scheduler=csr.sim.EventScheduler(); scheduler.run(1+eps(1));
            timing=csr.sim.TransportTiming('nanoseconds');
            engine=csr.phy.SignalEngine(c,scheduler,csr.sim.RandomStreams(12),@(~,~,~)[],[],[],timing);
            test.verifyError(@()engine.transmit(f),'csr:sim:TransportPast');
            test.verifyEqual(engine.ActiveSignalCount,0); test.verifyEqual(scheduler.PendingCount,0);
            test.verifyEqual(engine.state(1),'Search'); test.verifyEqual(timing.Count,0);
            c=engineConfig(3); scheduler=csr.sim.EventScheduler();
            timing=csr.sim.TransportTiming('continuous',1);
            engine=csr.phy.SignalEngine(c,scheduler,csr.sim.RandomStreams(12),@(~,~,~)[],[],[],timing);
            test.verifyError(@()engine.transmit(f),'csr:sim:TransportLimit');
            test.verifyEqual(engine.ActiveSignalCount,0); test.verifyEqual(scheduler.PendingCount,0);
            test.verifyEqual(engine.state(1),'Search'); test.verifyEqual(timing.Count,0);
        end
        function defaultAndExplicitContinuousRetainInterferenceAndCallbackTrace(test)
            c=engineConfig(3); c.Nodes(2).PositionMeters=[1200 0 0];
            c.Nodes(3).PositionMeters=[-1200 0 0];
            frames={engineFrame(1,1,2,8,'short',64),engineFrame(2,3,2,500,'short',64)};
            [expected,expectedTrace]=exercise(c,frames,[0.1 0.13],1,[]);
            timing=csr.sim.TransportTiming('continuous');
            [actual,actualTrace,engine,scheduler]=exercise(c,frames,[0.1 0.13],1,timing);
            test.verifyTrue(isequaln(actual,expected)); test.verifyTrue(isequaln(actualTrace,expectedTrace));
            test.verifyEqual(engine.ActiveSignalCount,0); test.verifyEqual(scheduler.PendingCount,0);
            test.verifyEqual(timing.Count,4); test.verifyEqual(timing.MaxAbsShiftSeconds,0);
        end
        function nanosecondCallbacksKeepPhysicalIntervalReferenceAndHalfDuplex(test)
            c=engineConfig(3); c.Nodes(2).PositionMeters=[1200.12 0 0];
            c.Nodes(3).PositionMeters=[-1200.12 0 0];
            frames={engineFrame(1,1,2,8,'short',64),engineFrame(2,3,2,8,'short',64)};
            timing=csr.sim.TransportTiming('nanoseconds');
            [records,trace,engine,scheduler]=exercise(c,frames,[0.1 0.13],1,timing);
            report=timing.snapshot();
            test.verifyNumElements(records,4); test.verifyEqual(engine.ActiveSignalCount,0);
            test.verifyEqual(scheduler.PendingCount,0);
            target=records([records.FrameId]==uint64(1) & [records.ReceiverId]==3);
            test.verifyFalse(target.Decision.Success);
            test.verifyEqual(target.Decision.Reason,'half_duplex');
            starts=trace(strcmp({trace.Event},'phy_signal_start'));
            for k=1:numel(starts)
                row=report.Records(report.Records.FrameId==starts(k).FrameId & ...
                    report.Records.ReceiverId==starts(k).ReceiverId,:);
                test.verifyEqual(starts(k).TimeSeconds,row.StartSeconds);
            end
            test.verifyTrue(all(report.Records.EndSeconds>=report.Records.PreambleEndSeconds));
            test.verifyTrue(all(report.Records.PreambleEndSeconds>=report.Records.StartSeconds));
            test.verifyGreaterThan(report.MaxAbsShiftSeconds,0);
        end
        function nanosecondEqualArrivalKeepsFifoAndOccludedCompletion(test)
            c=engineConfig(3); c.Nodes(1).RadioProfile.TxPowerDbm=-20;
            frames={engineFrame(10,1,2,8,'short',64),engineFrame(11,3,2,8,'short',64)};
            timing=csr.sim.TransportTiming('nanoseconds');
            [records,trace]=exercise(c,frames,[0 0],1,timing);
            arrivals=trace(strcmp({trace.Event},'phy_signal_start') & [trace.ReceiverId]==2);
            test.verifyEqual([arrivals.FrameId],uint64([10 11]));
            test.verifyNumElements(records,4);
            c=engineConfig(2); c.Nodes(2).PositionMeters=[1e6 0 0];
            c.Nodes(2).RadioProfile.ClosureMode='EARTH_LINE_OF_SIGHT';
            timing=csr.sim.TransportTiming('nanoseconds');
            [records,~,engine]=exercise(c,frames(1),0,1,timing);
            report=timing.snapshot(); test.verifyNumElements(records,1);
            test.verifyEqual(records.Decision.Reason,'closure');
            test.verifyEqual(records.TimeSeconds,report.Records.EndSeconds);
            test.verifyEqual(engine.ActiveSignalCount,0);
        end
        function optionalTimingIsSingleEngineAndPortableOnly(test)
            c=engineConfig(2); timing=csr.sim.TransportTiming('continuous');
            csr.phy.SignalEngine(c,csr.sim.EventScheduler(),csr.sim.RandomStreams(12),@(~,~,~)[],[],[],timing);
            test.verifyError(@()csr.phy.SignalEngine(c,csr.sim.EventScheduler(),csr.sim.RandomStreams(12), ...
                @(~,~,~)[],[],[],timing),'csr:sim:TransportReuse');
            c=csr.scenario.routedNetwork('autonomous'); c.Backend='wireless-clock';
            test.verifyError(@()csr.sim.NetworkSimulation(c,[],csr.sim.TransportTiming('continuous')), ...
                'csr:sim:TransportBackend');
        end
        function realNetworkDefaultAndExplicitContinuousRetainAllCoreResults(test)
            c=csr.scenario.routedNetwork('autonomous');
            % This small integration check includes actual PHY/discovery and
            % application generation. It does not demand completed routing.
            c.DurationSeconds=20; c.Traffic.StartSeconds=12; c.Traffic.PacketCount=1;
            expectedSimulation=csr.sim.NetworkSimulation(c); expected=expectedSimulation.run();
            timing=csr.sim.TransportTiming('continuous');
            simulation=csr.sim.NetworkSimulation(c,[],timing); actual=simulation.run();
            test.verifyFalse(isfield(expected,'TransportTiming'));
            test.verifyTrue(isequaln(actual.Statistics,expected.Statistics));
            fields={'Trace','PhyTrace','ApplicationAdmissionTrace','NodeMacStatistics', ...
                'NodeHopStatistics','NodeNwkStatistics','Routes','Neighbors','Config'};
            for k=1:numel(fields), test.verifyTrue(isequaln(actual.(fields{k}),expected.(fields{k}))); end
            test.verifyGreaterThan(actual.Statistics.PhysicalTransmissions,0);
            test.verifyEqual(actual.TransportTiming.Count,actual.Statistics.PhysicalAttempts);
            test.verifyEqual(actual.TransportTiming.MaxAbsShiftSeconds,0);
        end
    end
end

function c=engineConfig(count)
c=csr.scenario.smallNetwork(); profile=csr.phy.RadioProfile.defaults();
profile.ClosureMode='NEVER_OCCLUDED'; profile.StochasticSyncThreshold=false;
node=struct('Id',1,'PositionMeters',[0 0 0],'RadioProfile',profile);
c.Nodes=repmat(node,1,count);
for k=1:count, c.Nodes(k).Id=k; end
c.Phy=struct('MaxActiveSignals',1000,'MaxIntervalsPerSignal',1000, ...
    'SyncToTrackSeconds',0.00663,'CaptureMarginDb',10.5);
end
function frame=engineFrame(id,source,destination,rate,preamble,bytes)
flow=struct('SourceId',source,'DestinationId',destination,'ApplicationPayloadBytes',bytes);
radio=struct('RateKeyKbps',rate,'Preamble',preamble,'EnvelopeProfile','bare');
frame=csr.packet(uint64(id),flow,0,radio);
end
function [records,trace,engine,scheduler]=exercise(config,frames,times,horizon,timing)
records=struct('FrameId',{},'ReceiverId',{},'TimeSeconds',{},'Decision',{});
trace=struct('Event',{},'FrameId',{},'ReceiverId',{},'TimeSeconds',{},'Details',{});
scheduler=csr.sim.EventScheduler(); streams=csr.sim.RandomStreams(12);
engine=csr.phy.SignalEngine(config,scheduler,streams,@receive,@recordTrace,[],timing);
for k=1:numel(frames)
    frame=frames{k}; scheduler.scheduleAt(times(k),@()engine.transmit(frame));
end
scheduler.run(horizon);
    function receive(frame,receiver,decision)
        records(end+1)=struct('FrameId',frame.Id,'ReceiverId',receiver,'TimeSeconds',scheduler.Now,'Decision',decision);
    end
    function recordTrace(event,frame,receiver,details)
        trace(end+1)=struct('Event',event,'FrameId',frame.Id,'ReceiverId',receiver,'TimeSeconds',scheduler.Now,'Details',details);
    end
end
