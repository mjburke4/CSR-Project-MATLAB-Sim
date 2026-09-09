classdef TestHopControls < matlab.unittest.TestCase
    % Reliable controls share TX allocation and queueing, not DATA RX windows.
    methods (Test)
        function groupsUseIndependentSequencesSharedWithData(test)
            h=controlHarness(); [~,data]=h.Hop.send(appPacket(1,1,2),2);
            [ok,first]=h.Hop.sendControl(controlPacket(2),[2 3]);
            [~,second]=h.Hop.sendControl(controlPacket(3),[3 2]);
            test.verifyTrue(ok); test.verifyEqual(data.Sequence,uint16(1));
            test.verifyEqual(first.HopSequences,uint16([2 1]));
            test.verifyEqual(second.HopSequences,uint16([2 3]));
            test.verifyEqual(first.DestinationIds,[2 3]);
            test.verifyEqual(h.Hop.PendingDataCount,1);
        end
        function controlsBypassSaturatedDataWindows(test)
            h=controlHarness();
            for peer=2:18, test.assertTrue(h.Hop.send(appPacket(peer,1,peer),peer)); end
            test.verifyFalse(h.Hop.canSend(2));
            test.verifyTrue(h.Hop.canSendControl([2 3]));
            test.verifyTrue(h.Hop.sendControl(controlPacket(100),[2 3]));
            test.verifyEqual(h.Hop.PendingDataCount,17);
            test.verifyEqual(h.Hop.state(2).NeighborOutstanding,1);
            test.verifyEqual(h.Hop.state(2).NeighborThreshold,0);
        end
        function tenDestinationsOccupyOneSharedResendSlot(test)
            h=controlHarness(struct('ResendQueueLimit',1));
            test.assertTrue(h.Hop.sendControl(controlPacket(1),2:11));
            s=h.Hop.stats(); test.verifyEqual(s.ResendQueueDepth,1);
            test.verifyEqual(s.ControlPending,1); test.verifyEqual(s.ControlPendingTargets,10);
            test.verifyFalse(h.Hop.sendControl(controlPacket(2),12));
            test.verifyFalse(h.Hop.send(appPacket(3,1,12),12));
            test.verifyEqual(h.Hop.PendingDataCount,0);
            test.verifyEqual(h.Hop.stats().ResendQueueOverflow,2);
        end
        function dataCanFillSharedQueueAndBlockControl(test)
            h=controlHarness(struct('ResendQueueLimit',1));
            test.assertTrue(h.Hop.send(appPacket(1,1,2),2));
            test.verifyFalse(h.Hop.canSendControl(3));
            [ok,frame]=h.Hop.sendControl(controlPacket(2),3);
            test.verifyFalse(ok); test.verifyEmpty(frame);
            test.verifyEqual(h.Hop.stats().ControlAdmissionBlocked,1);
        end
        function macRejectionRollsBackGroupAndSequences(test)
            h=controlHarness(); h.Hop.send(appPacket(1,1,2),2);
            h.SetMac(false);
            test.verifyFalse(h.Hop.sendControl(controlPacket(2),[2 3]));
            test.verifyEqual(h.Hop.stats().ResendQueueDepth,1);
            test.verifyEqual(h.Hop.stats().ControlPending,0);
            test.verifyEmpty(h.Results());
            h.SetMac(true); [ok,frame]=h.Hop.sendControl(controlPacket(3),[2 3]);
            test.verifyTrue(ok); test.verifyEqual(frame.HopSequences,uint16([2 1]));
        end
        function invalidTargetsHaveNoAdmissionSideEffects(test)
            h=controlHarness(); control=controlPacket(1);
            for peers={[],2:12,[2 2],16777215,[2 16777215],-1}
                test.verifyError(@()h.Hop.sendControl(control,peers{1}),'csr:hop:InvalidTargets');
            end
            test.verifyEqual(h.Hop.stats().ResendQueueDepth,0);
            [~,frame]=h.Hop.sendControl(control,2);
            test.verifyEqual(frame.Sequence,uint16(1));
        end
        function frameUsesExplicitEnvelopeAndZeroApplicationBytes(test)
            h=controlHarness(); control=controlPacket(11); control.WirePayloadBytes=133;
            options=struct('RateKeyKbps',32,'Preamble','short','TxPowerDbm',12, ...
                'EnvelopeProfile','pairwise16-size-only');
            [~,frame]=h.Hop.sendControl(control,[2;3],options);
            test.verifyEqual(frame.Control,control); test.verifyEqual(frame.Id,uint64(11));
            test.verifyEqual(frame.Kind,'CONTROL'); test.verifyEqual(frame.Dscp,7);
            test.verifyEqual(frame.ApplicationPayloadBytes,0); test.verifyEqual(frame.WirePayloadBytes,133);
            test.verifyEqual(frame.DestinationIds,[2 3]); test.verifyEqual(frame.DestinationId,2);
            test.verifyEqual(frame.Sequence,frame.HopSequences(1));
            test.verifyEqual(frame.TxPowerDbm,12); test.verifyEqual(frame.RateKeyKbps,32);
            ack=ackFrame(1,2,uint16(0));
            aggregate=csr.hop.Frames.aggregate({ack,frame},'short');
            test.verifyEqual(aggregate.Dscp,7);
            test.verifyEqual(aggregate.ApplicationPayloadBytes,0);
        end
        function timerWaitsForActualControlTransmit(test)
            h=controlHarness(); [~,frame]=h.Hop.sendControl(controlPacket(1),[2 3]);
            h.Clock.run(10); test.verifyEqual(h.Hop.stats().ControlRetransmissions,0);
            h.Hop.notifySent(frame); h.Clock.run(11.99);
            test.verifyEqual(h.Hop.stats().ControlRetransmissions,0);
            h.Clock.run(12.01); test.verifyEqual(h.Hop.stats().ControlRetransmissions,1);
            h.Clock.run(100); test.verifyEqual(h.Hop.stats().ControlRetransmissions,1);
        end
        function partialAckRetainsOriginalRetryDestinations(test)
            h=controlHarness(); [~,frame]=h.Hop.sendControl(controlPacket(1),[2 3]);
            h.Hop.notifySent(frame); h.Hop.receive(ackFrame(2,1,frame.HopSequences(1)));
            test.verifyEmpty(h.Cancelled()); test.verifyEqual(h.Hop.stats().ControlPendingTargets,1);
            h.Clock.run(2.01); frames=h.Frames(); retry=frames{end};
            test.verifyEqual(retry.DestinationIds,frame.DestinationIds);
            test.verifyEqual(retry.HopSequences,frame.HopSequences);
            test.verifyEqual(retry.Control,frame.Control); test.verifyEqual(retry.RetryCount,1);
            test.verifyEqual(retry.Dscp,7); test.verifyEqual(h.Hop.PendingDataCount,0);
            results=h.Results(); test.verifyFalse(results{1}.Complete);
            test.verifyEqual(results{1}.RemainingPeers,3);
        end
        function duplicatePartialAckDoesNotCancelOrRepeatResult(test)
            h=controlHarness(); [~,frame]=h.Hop.sendControl(controlPacket(1),[2 3]);
            ack=ackFrame(2,1,frame.HopSequences(1));
            h.Hop.receive(ack); h.Hop.receive(ack);
            test.verifyEmpty(h.Cancelled()); test.verifyNumElements(h.Results(),1);
            test.verifyEqual(h.Hop.stats().ControlAcknowledged,1);
        end
        function lastSecondaryAckCancelsOriginalPrimaryOnly(test)
            h=controlHarness(); [~,frame]=h.Hop.sendControl(controlPacket(1),[2 3]);
            h.Hop.receive(ackFrame(2,1,frame.HopSequences(1)));
            h.Hop.receive(ackFrame(3,1,frame.HopSequences(2)));
            cancelled=h.Cancelled(); test.assertNumElements(cancelled,1);
            test.verifyEqual(cancelled{1},[2 double(frame.Sequence)]);
            results=h.Results(); test.assertNumElements(results,2);
            test.verifyTrue(results{2}.Success); test.verifyTrue(results{2}.Complete);
            test.verifyEmpty(results{2}.RemainingPeers);
            test.verifyEqual(results{2}.DuringCallback.ControlPending,1);
            test.verifyEqual(results{2}.DuringCallback.ControlPendingTargets,0);
            test.verifyEqual(results{2}.CanceledBeforeCallback,0);
            test.verifyEqual(h.Hop.stats().ResendQueueDepth,0);
            test.verifyEmpty(h.Releases()); test.verifyEmpty(h.Terminals());
            test.verifyEqual(h.Hop.state(2).AckCount,0);
        end
        function cumulativeWindowCompletesDataOnlyAndExactAckCompletesControl(test)
            h=controlHarness(); h.Hop.send(appPacket(1,1,2),2);
            [~,frame]=h.Hop.sendControl(controlPacket(2),2);
            ack=csr.hop.Frames.acknowledgment(2,1,uint16(1), ...
                uint64(1),uint64(0),struct());
            h.Hop.receive(ack);
            test.verifyEqual(h.Hop.PendingDataCount,0);
            test.verifyEqual(h.Hop.stats().ResendQueueDepth,1);
            test.verifyEqual(h.Hop.stats().Acknowledged,1);
            test.verifyEqual(h.Hop.stats().ControlAcknowledged,0);
            h.Hop.receive(ackFrame(2,1,frame.Sequence));
            test.verifyEqual(h.Hop.stats().ResendQueueDepth,0);
            test.verifyEqual(h.Hop.stats().ControlAcknowledged,1);
            test.verifyNumElements(h.Terminals(),1); test.verifyNumElements(h.Results(),1);
            test.verifyEqual(h.Hop.state(2).AckCount,1);
        end
        function groupedReceiverUsesItsOwnSequenceAndDeduplicates(test)
            h=controlHarness(struct(),3);
            frame=csr.hop.Frames.control(controlPacket(1),1,[2 3],uint16([10 27]),struct());
            h.Hop.receive(frame); h.Hop.receive(frame);
            deliveries=h.Controls(); test.assertNumElements(deliveries,1);
            test.verifyEqual(deliveries{1}.Peer,1); test.verifyEqual(deliveries{1}.Control,frame.Control);
            frames=h.Frames(); test.assertNumElements(frames,2);
            test.verifyEqual(frames{1}.Sequence,uint16(27));
            test.verifyFalse(frames{1}.HasAckWindow);
            test.verifyEqual(frames{2}.AckBitmap,uint64(0));
            test.verifyEqual(h.Hop.stats().ControlDuplicates,1);
        end
        function routingAndNeighborDeliveryPrecedeExactAck(test)
            for kind={'ROUTING','NEIGHBOR_CHECK'}
                h=controlHarness(struct(),2); control=controlPacket(1); control.Type=kind{1};
                frame=csr.hop.Frames.control(control,1,2,uint16(17),struct());
                h.Hop.receive(frame); h.Hop.receive(frame);
                test.verifyEqual(h.CallbackOrder(),{'validate','deliver','mac','validate','mac'});
                test.verifyNumElements(h.Controls(),1);
                frames=h.Frames(); test.verifyNumElements(frames,2);
                test.verifyFalse(frames{1}.HasAckWindow);
                test.verifyEqual(frames{1}.Sequence,uint16(17));
            end
        end
        function keyUpdateExactAckPrecedesDelivery(test)
            h=controlHarness(struct(),2); control=controlPacket(1); control.Type='KEY_UPDATE';
            frame=csr.hop.Frames.control(control,1,2,uint16(17),struct());
            h.Hop.receive(frame); h.Hop.receive(frame);
            test.verifyEqual(h.CallbackOrder(),{'validate','mac','deliver','validate','mac'});
            test.verifyNumElements(h.Controls(),1);
        end
        function snmpBypassesTransmitAllocationAndReceiveReplay(test)
            sender=controlHarness(); control=controlPacket(1); control.Type='SNMP_START';
            [~,frame]=sender.Hop.sendControl(control,2,struct('AckRequired',false));
            test.verifyEqual(frame.Sequence,uint16(0)); test.verifyEqual(frame.Dscp,0);
            test.verifyEqual(sender.Hop.stats().ResendQueueDepth,0);
            [~,data]=sender.Hop.send(appPacket(2,1,2),2);
            test.verifyEqual(data.Sequence,uint16(1));
            receiver=controlHarness(struct(),2); receiver.Hop.receive(frame); receiver.Hop.receive(frame);
            test.verifyNumElements(receiver.Controls(),2); test.verifyEmpty(receiver.Frames());
            state=receiver.Hop.state(1);
            test.verifyEqual(state.ControlReceiveWindow.Highest,-1);
            test.verifyEqual(state.DataReceiveWindow.Highest,-1);
        end
        function overheardAndFailedControlsDoNotTouchReceiverState(test)
            h=controlHarness(struct(),4);
            frame=csr.hop.Frames.control(controlPacket(1),1,[2 3],uint16([1 1]),struct());
            h.Hop.receive(frame);
            frame=csr.hop.Frames.control(controlPacket(2),1,4,uint16(1),struct());
            h.Hop.receive(frame,struct('Success',false));
            test.verifyEmpty(h.Controls()); test.verifyEmpty(h.Frames());
            test.verifyEqual(h.Hop.state(1).ReceiveWindow.Highest,-1);
        end
        function dataAndControlUseIndependentReceiveWindows(test)
            h=controlHarness(struct(),2);
            control=csr.hop.Frames.control(controlPacket(1),1,2,uint16(7),struct());
            data=csr.hop.Frames.data(appPacket(2,1,2),1,2,uint16(7),struct());
            h.Hop.receive(control); h.Hop.receive(data);
            h.Hop.receive(control); h.Hop.receive(data);
            test.verifyNumElements(h.Controls(),1); test.verifyNumElements(h.Deliveries(),1);
            state=h.Hop.state(1);
            test.verifyEqual(state.DataReceiveWindow.Highest,7);
            test.verifyEqual(state.ControlReceiveWindow.Highest,7);
            test.verifyEqual(state.DataReceiveWindow.AckBitmap,uint64(1));
            test.verifyEqual(state.ControlReceiveWindow.AckBitmap,uint64(1));
            test.verifyEqual(state.ReceiveWindow,state.DataReceiveWindow);
            frames=h.Frames(); test.verifyFalse(frames{1}.HasAckWindow);
            test.verifyTrue(frames{2}.HasAckWindow);
        end
        function dataAckBitmapLeavesControlSequenceHole(test)
            h=controlHarness(struct(),2);
            h.Hop.receive(csr.hop.Frames.data( ...
                appPacket(1,1,2),1,2,uint16(1),struct()));
            h.Hop.receive(csr.hop.Frames.control( ...
                controlPacket(2),1,2,uint16(2),struct()));
            h.Hop.receive(csr.hop.Frames.data( ...
                appPacket(3,1,2),1,2,uint16(3),struct()));
            frames=h.Frames(); test.assertNumElements(frames,3);
            test.verifyTrue(frames{3}.HasAckWindow);
            test.verifyEqual(frames{3}.Sequence,uint16(3));
            test.verifyEqual(frames{3}.AckBitmap,uint64(5));
            state=h.Hop.state(1);
            test.verifyEqual(state.DataReceiveWindow.AckBitmap,uint64(5));
            test.verifyEqual(state.ControlReceiveWindow.Highest,2);
        end
        function controlsNeverConsultDataRouteOrNsdpGates(test)
            h=controlHarness(struct(),2);
            frame=csr.hop.Frames.control(controlPacket(1),1,2,uint16(1),struct());
            h.Hop.receive(frame);
            test.verifyNumElements(h.Controls(),1);
            frames=h.Frames(); test.verifyEqual(frames{1}.Kind,'ACK');
            test.verifyFalse(frames{1}.HasAckWindow);
            test.verifyEqual(frames{1}.Sequence,uint16(1));
            test.verifyEqual(frames{1}.AckBitmap,uint64(0));
            test.verifyEqual(h.GateCalls(),[0 0]);
            test.verifyEqual(h.Hop.stats().DackHoldCount,0);
        end
        function cumulativeDackCannotMoveControlIntoDataCustody(test)
            h=controlHarness(); [~,frame]=h.Hop.sendControl(controlPacket(1),[2 3]);
            ack=csr.hop.Frames.acknowledgment(2,1,frame.Sequence, ...
                uint64(0),uint64(1),struct('Kind','DACK'));
            h.Hop.receive(ack);
            test.verifyEqual(h.Hop.stats().ControlUnexpectedDack,0);
            test.verifyEqual(h.Hop.stats().UnknownFeedback,1);
            test.verifyEqual(h.Hop.stats().ControlPendingTargets,2);
            test.verifyEqual(h.Hop.stats().DackHoldCount,0);
            test.verifyEqual(h.Hop.PendingDataCount,0);
            test.verifyEmpty(h.Cancelled()); test.verifyEmpty(h.Releases());
        end
        function finalTimeoutReportsOnlyResidualPeersAfterDoubleGrace(test)
            h=controlHarness(); [~,frame]=h.Hop.sendControl(controlPacket(1),[2 3 4]);
            h.Hop.notifySent(frame); h.Hop.receive(ackFrame(2,1,frame.Sequence));
            h.Clock.run(2.01); frames=h.Frames(); h.Hop.notifySent(frames{end});
            h.Clock.run(4.02); frames=h.Frames(); h.Hop.notifySent(frames{end});
            h.Clock.run(8); test.verifyEqual(h.Hop.stats().ControlPending,1);
            h.Clock.run(8.03); results=h.Results(); test.assertNumElements(results,3);
            test.verifyEqual([results{2}.Peer results{3}.Peer],[3 4]);
            test.verifyFalse(results{2}.Success); test.verifyFalse(results{2}.Complete);
            test.verifyFalse(results{3}.Success); test.verifyTrue(results{3}.Complete);
            test.verifyEqual(results{3}.RemainingPeers,[2 3 4]);
            test.verifyEqual(results{2}.DuringCallback.ControlPending,1);
            test.verifyEqual(results{3}.DuringCallback.ControlPending,1);
            test.verifyEqual(results{3}.DuringCallback.ControlPendingTargets,2);
            test.verifyEqual(results{3}.CanceledBeforeCallback,0);
            test.verifyEqual(h.Hop.stats().ControlRetransmissions,2);
            test.verifyEqual(h.Hop.stats().ControlFailed,1);
            test.verifyEqual(h.Hop.stats().ControlTargetFailures,2);
            test.verifyEqual(h.Hop.stats().ControlPending,0);
            test.verifyEqual(h.Hop.state(2).NeighborThreshold,0);
            test.verifyEmpty(h.Terminals()); test.verifyEmpty(h.Releases());
        end
        function retryMacRejectionReleasesWholeControlGroup(test)
            h=controlHarness(); [~,frame]=h.Hop.sendControl(controlPacket(1),[2 3]);
            h.Hop.notifySent(frame); h.SetMac(false); h.Clock.run(2.01);
            test.verifyEqual(h.Hop.stats().ControlPending,0);
            test.verifyEqual(h.Hop.stats().ControlFailed,1);
            results=h.Results(); test.assertNumElements(results,2);
            test.verifyTrue(results{2}.Complete); test.verifyEqual(results{2}.RemainingPeers,[2 3]);
            test.verifyEqual(results{2}.DuringCallback.ControlPending,1);
            test.verifyEqual(results{2}.CanceledBeforeCallback,0);
            test.verifyNumElements(h.Cancelled(),1);
        end
        function bestEffortBroadcastBypassesQueueAndDoesNotPolluteAckWindow(test)
            sender=controlHarness(struct('ResendQueueLimit',1));
            sender.Hop.send(appPacket(1,1,2),2);
            control=controlPacket(2); control.Type='DISCOVER';
            [ok,frame]=sender.Hop.sendControl(control,16777215,struct('AckRequired',false));
            test.verifyTrue(ok); test.verifyEqual(sender.Hop.stats().ResendQueueDepth,1);
            sender.Hop.notifySent(frame); results=sender.Results();
            test.verifyTrue(results{1}.Complete); test.verifyTrue(results{1}.Success);
            receiver=controlHarness(struct(),2); receiver.Hop.receive(frame);
            test.verifyNumElements(receiver.Controls(),1); test.verifyEmpty(receiver.Frames());
            test.verifyEqual(receiver.Hop.state(1).ReceiveWindow.Highest,-1);
        end
        function finalExpirationPassPrecedesOtherControlRetry(test)
            h=controlHarness(struct('MaxResends',1));
            [~,first]=h.Hop.sendControl(controlPacket(1),2); h.Hop.notifySent(first);
            h.Clock.run(2.01); frames=h.Frames(); h.Hop.notifySent(frames{end});
            h.Clock.run(4.01); [~,second]=h.Hop.sendControl(controlPacket(2),3);
            h.Hop.notifySent(second); h.Clock.run(6.02);
            order=h.Events(); failed=find(strcmp(order,'hop_control_failed'),1);
            retries=find(strcmp(order,'hop_retry'));
            test.assertNumElements(retries,2); test.verifyLessThan(failed,retries(2));
        end
        function controlValidationCannotAllocateSequences(test)
            h=controlHarness(); invalid=controlPacket(1); invalid.Id=1;
            test.verifyError(@()h.Hop.sendControl(invalid,2),'csr:hop:InvalidControl');
            invalid=controlPacket(1); invalid.Type='routing';
            test.verifyError(@()h.Hop.sendControl(invalid,2),'csr:hop:InvalidControl');
            [~,frame]=h.Hop.sendControl(controlPacket(2),2);
            test.verifyEqual(frame.Sequence,uint16(1));
        end
        function rejectedControlDoesNotAckOrConsumeReceiveSequence(test)
            h=controlHarness(struct(),2); h.SetControlValidation(false);
            frame=csr.hop.Frames.control(controlPacket(1),1,2,uint16(17),struct());
            h.Hop.receive(frame);
            test.verifyEmpty(h.Controls()); test.verifyEmpty(h.Frames());
            test.verifyEqual(h.CallbackOrder(),{'validate'});
            test.verifyEqual(h.Hop.state(1).ControlReceiveWindow.Highest,-1);
            h.SetControlValidation(true); h.Hop.receive(frame);
            test.verifyNumElements(h.Controls(),1); frames=h.Frames();
            test.verifyNumElements(frames,1); test.verifyFalse(frames{1}.HasAckWindow);
            test.verifyEqual(frames{1}.Sequence,uint16(17));
            test.verifyEqual(h.Hop.state(1).ControlReceiveWindow.Highest,17);
        end
    end
end

function h=controlHarness(config,node)
if nargin<1, config=struct(); end
if nargin<2, node=1; end
frames={}; controls={}; deliveries={}; results={}; cancelled={}; releases={}; terminals={};
events={}; callbackOrder={}; macAccepted=true; controlValid=true; nsdpCalls=0; routeCalls=0;
scheduler=csr.sim.EventScheduler();
callbacks=struct('EnqueueMac',@enqueue,'DeliverControl',@deliverControl, ...
    'ValidateControl',@validateControl, ...
    'ControlResult',@controlResult,'CancelMac',@cancel,'NsdpRelease',@release, ...
    'Terminal',@terminal,'Deliver',@deliver,'NsdpCount',@nsdp,'RouteAvailable',@route,'Event',@event);
hop=csr.hop.Layer(node,scheduler,csr.sim.RandomStreams(73),config,callbacks);
% Named readers observe the mutable nested callback workspace in MATLAB.
h=struct('Hop',hop,'Clock',scheduler,'Frames',@getFrames,'Controls',@getControls, ...
    'Deliveries',@getDeliveries,'Results',@getResults,'Cancelled',@getCancelled, ...
    'Releases',@getReleases,'Terminals',@getTerminals,'Events',@getEvents, ...
    'GateCalls',@getGateCalls,'SetMac',@setMac,'CallbackOrder',@getCallbackOrder);
    h.SetControlValidation=@setControlValidation;
    function accepted=enqueue(frame)
        callbackOrder{end+1}='mac';
        accepted=macAccepted; if accepted, frames{end+1}=frame; end
    end
    function deliverControl(control,peer)
        callbackOrder{end+1}='deliver';
        controls{end+1}=struct('Control',control,'Peer',peer);
    end
    function controlResult(control,peer,success,complete,remainingPeers)
        results{end+1}=struct('Control',control,'Peer',peer,'Success',success, ...
            'Complete',complete,'RemainingPeers',remainingPeers, ...
            'DuringCallback',hop.stats(),'CanceledBeforeCallback',numel(cancelled));
    end
    function cancel(peer,sequence), cancelled{end+1}=[double(peer) double(sequence)]; end
    function release(app,reason), releases{end+1}=struct('App',app,'Reason',reason); end
    function terminal(app,success,reason)
        terminals{end+1}=struct('App',app,'Success',success,'Reason',reason);
    end
    function accepted=deliver(app,peer)
        deliveries{end+1}=struct('App',app,'Peer',peer); accepted=true;
    end
    function value=nsdp(~), nsdpCalls=nsdpCalls+1; value=99; end
    function value=route(~), routeCalls=routeCalls+1; value=false; end
    function value=validateControl(~,~)
        callbackOrder{end+1}='validate'; value=controlValid;
    end
    function event(name,~,~), events{end+1}=name; end
    function value=getFrames(), value=frames; end
    function value=getControls(), value=controls; end
    function value=getDeliveries(), value=deliveries; end
    function value=getResults(), value=results; end
    function value=getCancelled(), value=cancelled; end
    function value=getReleases(), value=releases; end
    function value=getTerminals(), value=terminals; end
    function value=getEvents(), value=events; end
    function value=getCallbackOrder(), value=callbackOrder; end
    function value=getGateCalls(), value=[nsdpCalls routeCalls]; end
    function setMac(value), macAccepted=value; end
    function setControlValidation(value), controlValid=logical(value); end
end
function control=controlPacket(id)
control=struct('Id',uint64(id),'Type','ROUTING','Payload',struct('Bytes',uint8([1 2 3])), ...
    'WirePayloadBytes',64);
end
function app=appPacket(id,source,destination)
flow=struct('SourceId',source,'DestinationId',destination,'ApplicationPayloadBytes',64);
app=csr.packet(id,flow,0,struct('RateKeyKbps',8,'Preamble','long','EnvelopeProfile','bare'));
end
function frame=ackFrame(source,destination,sequence)
frame=csr.hop.Frames.acknowledgment(source,destination,sequence, ...
    uint64(0),uint64(0),struct('HasAckWindow',false));
end
