classdef TestPhyMacBridge < matlab.unittest.TestCase
    % PHY/MAC boundary tests; these require execution in actual MATLAB.
    methods (Test)
        function decodedFramePrecedesSearchNotification(test)
            c=bridgeConfig(2); scheduler=csr.sim.EventScheduler();
            streams=csr.sim.RandomStreams(12); events={}; engine=[];
            engine=csr.phy.SignalEngine(c,scheduler,streams,@receive,[],@changed);
            engine.transmit(bridgeFrame(1,1,2,'short'));
            scheduler.run(1);
            test.verifyEqual(events,{'Track','receive','Search'});
            test.verifyEqual(engine.ActiveSignalCount,0);
            function changed(id,state)
                test.verifyEqual(engine.state(id),state);
                if id==2
                    events{end+1}=state;
                    if strcmp(state,'Track'), test.verifyTrue(engine.hasSync(id)); end
                end
            end
            function receive(~,id,decision)
                test.verifyTrue(decision.Success);
                test.verifyEqual(engine.state(id),'Track');
                test.verifyFalse(engine.hasSync(id));
                test.verifyEqual(engine.ActiveSignalCount,0);
                events{end+1}='receive';
            end
        end
        function callbackMayEnterIdleAfterReceive(test)
            c=bridgeConfig(2); scheduler=csr.sim.EventScheduler();
            streams=csr.sim.RandomStreams(12); delivered=false; states={}; engine=[];
            engine=csr.phy.SignalEngine(c,scheduler,streams,@receive,[],@changed);
            engine.transmit(bridgeFrame(1,1,2,'short')); scheduler.run(1);
            test.verifyEqual(states,{'Track','Search','Idle'});
            test.verifyEqual(engine.state(2),'Idle');
            test.verifyEqual(scheduler.PendingCount,0);
            function receive(~,~,decision)
                test.verifyTrue(decision.Success); delivered=true;
            end
            function changed(id,state)
                if id~=2, return; end
                states{end+1}=state;
                if delivered && strcmp(state,'Search')
                    engine.setReceiverState(id,'Idle');
                end
            end
        end
        function successfulReceiveCannotUndoMacSleep(test)
            c=bridgeConfig(2); scheduler=csr.sim.EventScheduler();
            streams=csr.sim.RandomStreams(12); states={}; engine=[];
            engine=csr.phy.SignalEngine(c,scheduler,streams,@receive,[],@changed);
            engine.transmit(bridgeFrame(1,1,2,'short')); scheduler.run(1);
            test.verifyEqual(states,{'Track','Idle'});
            test.verifyEqual(engine.state(2),'Idle');
            test.verifyEqual(engine.ActiveSignalCount,0);
            test.verifyEqual(scheduler.PendingCount,0);
            function changed(id,state)
                if id==2, states{end+1}=state; end
            end
            function receive(~,id,decision)
                test.verifyTrue(decision.Success);
                engine.setReceiverState(id,'Idle');
            end
        end
        function standaloneCallbackOrderIsPreserved(test)
            c=bridgeConfig(2); scheduler=csr.sim.EventScheduler();
            streams=csr.sim.RandomStreams(12); receivedState=''; engine=[];
            engine=csr.phy.SignalEngine(c,scheduler,streams,@receive);
            engine.transmit(bridgeFrame(1,1,2,'short')); scheduler.run(1);
            test.verifyEqual(receivedState,'Search');
            function receive(~,id,~)
                receivedState=engine.state(id);
            end
        end
        function syncPresenceExcludesRejectedAndExpiredPreambles(test)
            c=bridgeConfig(4); c.Nodes(3).RadioProfile.TxBaseFrequencyHz=40e6;
            scheduler=csr.sim.EventScheduler(); streams=csr.sim.RandomStreams(12);
            engine=csr.phy.SignalEngine(c,scheduler,streams,@(~,~,~)[],[],@(~,~)[]);
            engine.setReceiverState(2,'Idle');
            weak=bridgeFrame(1,1,2,'short'); weak.TxPowerDbm=-200;
            offBand=bridgeFrame(2,3,2,'short');
            admitted=bridgeFrame(3,4,2,'long');
            engine.transmit(weak); engine.transmit(offBand);
            scheduler.run(0.02); test.verifyFalse(engine.hasSync(2));
            scheduler.scheduleAt(0.03,@()engine.transmit(admitted));
            scheduler.run(0.031); test.verifyTrue(engine.hasSync(2));
            test.verifyEqual(engine.state(2),'Idle');
            scheduler.run(0.03+7888*0.000510/4+1e-6);
            test.verifyFalse(engine.hasSync(2));
            test.verifyGreaterThan(engine.ActiveSignalCount,0);
        end
        function wakeAcquiresAlreadyAdmittedPreamble(test)
            c=bridgeConfig(2); scheduler=csr.sim.EventScheduler();
            streams=csr.sim.RandomStreams(12); states={}; decisions={};
            engine=csr.phy.SignalEngine(c,scheduler,streams,@receive,[],@changed);
            engine.setReceiverState(2,'Idle'); engine.setReceiverState(2,'Idle');
            engine.transmit(bridgeFrame(1,1,2,'long'));
            test.verifyError(@()engine.setReceiverState(1,'Search'),'csr:phy:ReceiverBusy');
            scheduler.run(0.03); test.verifyTrue(engine.hasSync(2));
            engine.setReceiverState(2,'Search'); scheduler.run(0.04);
            test.verifyEqual(engine.state(2),'Track');
            scheduler.run(2);
            test.verifyEqual(states,{'Idle','Search','Track','Search'});
            test.verifyNumElements(decisions,1); test.verifyTrue(decisions{1}.Success);
            function changed(id,state)
                if id==2, states{end+1}=state; end
            end
            function receive(~,~,decision)
                decisions{end+1}=decision;
            end
        end
        function rejectedTrackedReceiveWaitsOneSourceTic(test)
            c=failureConfig(); scheduler=csr.sim.EventScheduler();
            streams=csr.sim.RandomStreams(12); searchTimes=[]; decisions={};
            engine=csr.phy.SignalEngine(c,scheduler,streams,@receive,[],@changed);
            frame=bridgeFrame(1,1,2,'short');
            duration=csr.phy.airtime(frame.WirePayloadBytes,frame.RateKeyKbps,frame.Preamble);
            engine.transmit(frame); scheduler.run(duration);
            test.verifyNumElements(decisions,1);
            test.verifyFalse(decisions{1}.Success); test.verifyTrue(decisions{1}.EccDropped);
            test.verifyEqual(engine.state(2),'Track'); test.verifyEmpty(searchTimes);
            scheduler.run(duration+28e-9);
            test.verifyEqual(engine.state(2),'Search');
            test.verifyEqual(searchTimes,duration+28e-9,'AbsTol',1e-15);
            function changed(id,state)
                if id==2 && strcmp(state,'Search'), searchTimes(end+1)=scheduler.Now; end
            end
            function receive(~,~,decision)
                decisions{end+1}=decision;
            end
        end
        function rejectedFallbackCannotUndoMacSleep(test)
            c=failureConfig(); scheduler=csr.sim.EventScheduler();
            streams=csr.sim.RandomStreams(12); states={}; engine=[];
            engine=csr.phy.SignalEngine(c,scheduler,streams,@receive,[],@changed);
            engine.transmit(bridgeFrame(1,1,2,'short')); scheduler.run(1);
            test.verifyEqual(states,{'Track','Idle'});
            test.verifyEqual(engine.state(2),'Idle');
            function changed(id,state)
                if id==2, states{end+1}=state; end
            end
            function receive(~,id,decision)
                test.verifyFalse(decision.Success);
                scheduler.scheduleAt(scheduler.Now+14e-9,@()engine.setReceiverState(id,'Idle'));
            end
        end
        function aggregateSegmentsAreOpaqueToPhy(test)
            c=bridgeConfig(2); scheduler=csr.sim.EventScheduler();
            streams=csr.sim.RandomStreams(12); received={};
            engine=csr.phy.SignalEngine(c,scheduler,streams,@receive,[],@(~,~)[]);
            frame=bridgeFrame(1,1,2,'short');
            frame.Segments={struct('Type','DATA','Sequence',7), ...
                struct('Type','ACK','Sequence',5),struct('Type','DACK','Sequence',4)};
            engine.transmit(frame); scheduler.run(1);
            test.verifyNumElements(received,1);
            test.verifyEqual(received{1}.Segments,frame.Segments);
            function receive(value,~,decision)
                test.verifyTrue(decision.Success); received{end+1}=value;
            end
        end
    end
end

function c=bridgeConfig(count)
c=csr.scenario.smallNetwork(); profile=csr.phy.RadioProfile.defaults();
profile.ClosureMode='NEVER_OCCLUDED'; profile.StochasticSyncThreshold=false;
node=struct('Id',1,'PositionMeters',[0 0 0],'RadioProfile',profile);
c.Nodes=repmat(node,1,count);
for k=1:count, c.Nodes(k).Id=k; end
c.Phy=struct('MaxActiveSignals',1000,'MaxIntervalsPerSignal',1000, ...
    'SyncToTrackSeconds',0.00663,'CaptureMarginDb',10.5);
end

function c=failureConfig()
c=bridgeConfig(2);
% Admit SYNC explicitly but force approximately half the protected bits to
% fail, with no ECC correction. This isolates post-RX timing from collisions.
c.Nodes(2).RadioProfile.NoiseFloorDbm=100;
c.Nodes(2).RadioProfile.SyncSnrThresholdDb=-200;
c.Nodes(2).RadioProfile.EccThreshold=0;
end

function frame=bridgeFrame(id,source,destination,preamble)
flow=struct('SourceId',source,'DestinationId',destination,'ApplicationPayloadBytes',64);
radio=struct('RateKeyKbps',8,'Preamble',preamble,'EnvelopeProfile','bare');
frame=csr.packet(id,flow,0,radio);
end
