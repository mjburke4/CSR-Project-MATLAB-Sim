classdef TestHopLayer < matlab.unittest.TestCase
    % Behavioral tests against current ns-3 HOP custody/reliability rules.
    methods (Test)
        function timerStartsAtActualTransmit(test)
            h=hopHarness(); [accepted,f]=h.Hop.send(appPacket(1,1,2),2);
            test.verifyTrue(accepted); h.Clock.run(20);
            test.verifyEqual(h.Hop.stats().Retransmissions,0);
            test.verifyEqual(h.Hop.PendingDataCount,1);
            h.Hop.notifySent(f); h.Clock.run(21.99);
            test.verifyEqual(h.Hop.stats().Retransmissions,0);
            h.Clock.run(22.01);
            test.verifyEqual(h.Hop.stats().Retransmissions,1);
        end
        function retryKeepsSequenceAndDscpAndWaitsForSent(test)
            h=hopHarness(); [~,f]=h.Hop.send(appPacket(1,1,2),2,struct('Dscp',5));
            test.assertNumElements(h.Frames(),1);
            h.Hop.notifySent(f); h.Clock.run(2.01);
            frames=h.Frames(); test.assertNumElements(frames,2); retry=frames{end};
            test.verifyEqual(retry.Sequence,f.Sequence);
            test.verifyEqual(retry.Dscp,5); test.verifyEqual(retry.RetryCount,1);
            h.Clock.run(100);
            test.verifyEqual(h.Hop.stats().Retransmissions,1);
            test.verifyEqual(h.Hop.PendingDataCount,1);
        end
        function finalTimeoutHasDoubleGrace(test)
            h=hopHarness(); [~,f]=h.Hop.send(appPacket(1,1,2),2);
            h.Hop.notifySent(f); h.Clock.run(2.01);
            frames=h.Frames(); h.Hop.notifySent(frames{end}); h.Clock.run(4.02);
            frames=h.Frames(); h.Hop.notifySent(frames{end});
            h.Clock.run(8); test.verifyEqual(h.Hop.PendingDataCount,1);
            h.Clock.run(8.03); test.verifyEqual(h.Hop.PendingDataCount,0);
            s=h.Hop.stats(); test.verifyEqual(s.Retransmissions,2); test.verifyEqual(s.Failed,1);
            done=h.Terminals(); test.verifyEqual(done{1}.Reason,'retry_exhausted');
            test.verifyFalse(done{1}.Success);
        end
        function ackReleasesCustodyAndCancelsQueuedCopy(test)
            h=hopHarness(); [~,f]=h.Hop.send(appPacket(1,1,2),2);
            h.Hop.receive(feedback(2,1,f.Sequence,uint64(1),uint64(0)),struct('Success',true));
            test.verifyTrue(h.Hop.canSend(2)); test.verifyEqual(h.Hop.PendingDataCount,0);
            test.verifyEqual(h.Hop.stats().Acknowledged,1);
            cancelled=h.Cancelled(); test.verifyEqual(cancelled{1},[2 double(f.Sequence)]);
            releases=h.Releases(); test.verifyEqual(releases{1}.Reason,'ack');
        end
        function thirdAckGrowsBeforeRetryStreakReset(test)
            h=hopHarness();
            for n=1:3
                [~,f]=h.Hop.send(appPacket(n,1,2),2);
                if n==3
                    h.Hop.notifySent(f); h.Clock.run(2.01);
                end
                h.Hop.receive(feedback(2,1,f.Sequence,uint64(1),uint64(0)));
            end
            state=h.Hop.state(2);
            test.verifyEqual(state.NeighborThreshold,1); test.verifyEqual(state.AckCount,0);
            test.verifyTrue(h.Hop.send(appPacket(4,1,2),2));
            test.verifyTrue(h.Hop.send(appPacket(5,1,2),2));
            test.verifyFalse(h.Hop.send(appPacket(6,1,2),2));
        end
        function globalThresholdSixteenAdmitsSeventeenth(test)
            h=hopHarness();
            for peer=2:18
                test.verifyTrue(h.Hop.send(appPacket(peer,1,peer),peer));
            end
            test.verifyEqual(h.Hop.PendingDataCount,17);
            test.verifyFalse(h.Hop.send(appPacket(19,1,19),19));
            test.verifyEqual(h.Hop.admission(19).GlobalSpare,0);
        end
        function dackReleasesNsdpAndHoldsCapacity(test)
            h=hopHarness(); [~,f]=h.Hop.send(appPacket(1,1,3),2);
            h.Hop.receive(feedback(2,1,f.Sequence,uint64(0),uint64(1)));
            test.verifyEqual(h.Hop.PendingDataCount,1);
            test.verifyEqual(h.Hop.stats().ResendQueueDepth,0);
            test.verifyEqual(h.Hop.stats().DackHoldCount,1);
            releases=h.Releases(); test.verifyEqual(releases{1}.Reason,'dack');
            test.verifyFalse(h.Hop.canSend(2)); h.Clock.run(20);
            test.verifyEqual(h.Hop.PendingDataCount,1);
            h.Clock.run(20+2/36e6); test.verifyEqual(h.Hop.PendingDataCount,0);
            test.verifyTrue(h.Hop.canSend(2)); test.verifyEqual(h.Hop.stats().DackExpired,1);
        end
        function lastRetryDackDoublesHold(test)
            h=hopHarness(struct('MaxResends',0)); [~,f]=h.Hop.send(appPacket(1,1,3),2);
            h.Hop.receive(feedback(2,1,f.Sequence,uint64(0),uint64(1)));
            h.Clock.run(39.99); test.verifyEqual(h.Hop.PendingDataCount,1);
            h.Clock.run(40.01); test.verifyEqual(h.Hop.PendingDataCount,0);
        end
        function unknownFeedbackAndSingleDackStillCoalesceWake(test)
            h=hopHarness(); f=feedback(2,1,uint16(1),uint64(0),uint64(1));
            f.HasAckWindow=false;
            h.Hop.receive(f); h.Hop.receive(f); h.Clock.run(1/36e6);
            test.verifyEqual(h.Hop.stats().QueueWakes,1);
            test.verifyEqual(h.Wakes(),1); test.verifyEmpty(h.Terminals());
        end
        function duplicateIsAckedWithoutRedelivery(test)
            h=hopHarness(struct(),2); f=dataFrame(appPacket(1,1,2),1,2,1);
            h.Hop.receive(f); h.Hop.receive(f);
            test.verifyNumElements(h.Deliveries(),1); test.verifyNumElements(h.Frames(),2);
            test.verifyEqual(h.Hop.stats().Duplicates,1);
            frames=h.Frames(); test.verifyEqual(frames{2}.AckBitmap,uint64(1));
        end
        function sequenceWindowWrapAndOutOfOrder(test)
            h=hopHarness(struct(),2); seq=[65535 0 65534 65535];
            for n=1:numel(seq)
                h.Hop.receive(dataFrame(appPacket(n,1,2),1,2,seq(n)));
            end
            test.verifyNumElements(h.Deliveries(),3);
            state=h.Hop.state(1); test.verifyEqual(state.ReceiveWindow.Highest,0);
            test.verifyEqual(state.ReceiveWindow.AckBitmap,uint64(7));
        end
        function relayCountFifteenStillAcksTheSixteenth(test)
            h=hopHarness(struct(),2); h.SetNsdp(15);
            h.Hop.receive(dataFrame(appPacket(1,1,3),1,2,1));
            frames=h.Frames(); test.verifyEqual(frames{end}.Kind,'ACK');
            h.Hop.receive(dataFrame(appPacket(2,1,3),1,2,2));
            frames=h.Frames(); test.verifyEqual(frames{end}.Kind,'DACK');
        end
        function relayDackUsesPreenqueueCountAndCanBeReassessed(test)
            h=hopHarness(struct(),2); h.SetNsdp(16);
            f=dataFrame(appPacket(1,1,3),1,2,1); h.Hop.receive(f);
            frames=h.Frames(); test.verifyEqual(frames{end}.Kind,'DACK');
            test.verifyEqual(frames{end}.DackBitmap,uint64(1));
            h.SetNsdp(0); h.Hop.receive(f);
            frames=h.Frames(); test.verifyEqual(frames{end}.Kind,'ACK');
            test.verifyEqual(frames{end}.AckBitmap,uint64(1));
            test.verifyEqual(frames{end}.DackBitmap,uint64(1));
            test.verifyNumElements(h.Deliveries(),2);
        end
        function ackBitmapWinsOverlappingDack(test)
            h=hopHarness(); [~,f]=h.Hop.send(appPacket(1,1,2),2);
            h.Hop.receive(feedback(2,1,f.Sequence,uint64(1),uint64(1)));
            test.verifyEqual(h.Hop.stats().Acknowledged,1);
            test.verifyEqual(h.Hop.stats().Dacked,0);
            test.verifyEqual(h.Hop.PendingDataCount,0);
        end
        function localDeliveryNeverDacks(test)
            h=hopHarness(struct(),2); h.SetNsdp(99);
            h.Hop.receive(dataFrame(appPacket(1,1,2),1,2,1));
            frames=h.Frames(); test.verifyEqual(frames{1}.Kind,'ACK');
            order=h.Order(); test.verifyEqual(order,{'mac','deliver'});
        end
        function relayDeliveryPrecedesFeedback(test)
            h=hopHarness(struct(),2);
            h.Hop.receive(dataFrame(appPacket(1,1,3),1,2,1));
            test.verifyEqual(h.Order(),{'deliver','mac'});
        end
        function noRouteFirstReceptionSuppressedAndRetryAcked(test)
            h=hopHarness(struct(),2); h.SetRoute(false);
            f=dataFrame(appPacket(1,1,3),1,2,1); h.Hop.receive(f);
            test.verifyEmpty(h.Frames()); test.verifyEmpty(h.Deliveries());
            h.Hop.receive(f);
            frames=h.Frames(); test.verifyEqual(frames{1}.Kind,'ACK');
            test.verifyEmpty(h.Deliveries());
        end
        function custodyRefusalAllowsFreshRetry(test)
            h=hopHarness(struct(),2); h.SetDelivery(false);
            f=dataFrame(appPacket(1,1,3),1,2,1); h.Hop.receive(f);
            test.verifyEmpty(h.Frames()); h.SetDelivery(true); h.Hop.receive(f);
            test.verifyNumElements(h.Frames(),1); test.verifyEqual(h.Hop.stats().Delivered,1);
        end
        function macRejectionRollsBackAdmission(test)
            h=hopHarness(); h.SetMac(false);
            test.verifyFalse(h.Hop.send(appPacket(1,1,2),2));
            test.verifyEqual(h.Hop.PendingDataCount,0);
            test.verifyEqual(h.Hop.stats().ResendQueueDepth,0);
            test.verifyTrue(h.Hop.canSend(2)); test.verifyEmpty(h.Terminals());
        end
        function queueBoundRefusesBeforeLosingCustody(test)
            h=hopHarness(struct('ResendQueueLimit',1));
            test.verifyTrue(h.Hop.send(appPacket(1,1,2),2));
            test.verifyFalse(h.Hop.send(appPacket(2,1,3),3));
            test.verifyEqual(h.Hop.PendingDataCount,1);
            test.verifyEqual(h.Hop.stats().ResendQueueOverflow,1);
        end
    end
end

function h=hopHarness(config,node)
if nargin<1, config=struct(); end
if nargin<2, node=1; end
frames={}; delivered={}; terminals={}; cancelled={}; releases={}; order={};
nsdp=0; available=true; deliverAccepted=true; macAccepted=true; wakes=0;
scheduler=csr.sim.EventScheduler();
callbacks=struct('EnqueueMac',@enqueue,'Deliver',@deliver, ...
    'Terminal',@terminal,'CancelMac',@cancel,'NsdpCount',@getNsdp, ...
    'RouteAvailable',@getRoute,'NsdpRelease',@release,'Wake',@wake);
hop=csr.hop.Layer(node,scheduler,csr.sim.RandomStreams(128),config,callbacks);
% Named nested readers share the callbacks' mutable workspace. Anonymous
% readers would retain only the values present when the harness was created.
h=struct('Hop',hop,'Clock',scheduler,'Frames',@getFrames,'Deliveries',@getDeliveries, ...
    'Terminals',@getTerminals,'Cancelled',@getCancelled,'Releases',@getReleases, ...
    'Order',@getOrder,'Wakes',@getWakes,'SetNsdp',@setNsdp,'SetRoute',@setRoute, ...
    'SetDelivery',@setDelivery,'SetMac',@setMac);
    function accepted=enqueue(frame)
        accepted=macAccepted;
        if accepted, frames{end+1}=frame; order{end+1}='mac'; end
    end
    function accepted=deliver(app,peer)
        accepted=deliverAccepted; order{end+1}='deliver';
        if accepted, delivered{end+1}=struct('App',app,'Peer',peer); nsdp=nsdp+1; end
    end
    function terminal(app,success,reason)
        terminals{end+1}=struct('App',app,'Success',success,'Reason',reason);
    end
    function cancel(peer,sequence)
        cancelled{end+1}=[double(peer) double(sequence)];
    end
    function release(app,reason)
        releases{end+1}=struct('App',app,'Reason',reason);
    end
    function wake(), wakes=wakes+1; end
    function value=getFrames(), value=frames; end
    function value=getDeliveries(), value=delivered; end
    function value=getTerminals(), value=terminals; end
    function value=getCancelled(), value=cancelled; end
    function value=getReleases(), value=releases; end
    function value=getOrder(), value=order; end
    function value=getWakes(), value=wakes; end
    function value=getNsdp(~), value=nsdp; end
    function value=getRoute(~), value=available; end
    function setNsdp(value), nsdp=value; end
    function setRoute(value), available=value; end
    function setDelivery(value), deliverAccepted=value; end
    function setMac(value), macAccepted=value; end
end
function app=appPacket(id,source,destination)
flow=struct('SourceId',source,'DestinationId',destination,'ApplicationPayloadBytes',64);
radio=struct('RateKeyKbps',8,'Preamble','long','EnvelopeProfile','bare');
app=csr.packet(id,flow,0,radio);
end
function f=dataFrame(app,source,destination,sequence)
f=csr.hop.Frames.data(app,source,destination,uint16(sequence),struct());
end
function f=feedback(source,destination,sequence,ack,dack)
options=struct(); if ack==0 && dack~=0, options.Kind='DACK'; end
f=csr.hop.Frames.acknowledgment(source,destination,sequence,ack,dack,options);
end
