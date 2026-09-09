classdef TestNeighbors < matlab.unittest.TestCase
    % Admission proofs and discovery timer behavior, independent of the PHY.
    methods (Test)
        function discoveryCadenceAndImmediateRestart(test)
            h=neighborHarness(); test.verifyTrue(h.Neighbors.startDiscovery());
            test.verifyFalse(h.Neighbors.startDiscovery());
            h.Clock.run(14.99); sent=h.Sent('DISCOVER');
            test.verifyEqual([sent.Time],[0 5 10]);
            test.verifyEqual(h.Neighbors.DiscoveryState,'active');
            test.verifyEqual(h.Done(),0); h.Clock.run(15);
            test.verifyEqual(h.Neighbors.DiscoveryState,'idle'); test.verifyEqual(h.Done(),1);
            test.verifyTrue(h.Neighbors.startDiscovery()); h.Clock.run(15);
            test.verifyEqual(h.Neighbors.DiscoverySequence,uint32(2));
        end
        function shortDurationCancelsRemainingBroadcasts(test)
            h=neighborHarness(); h.Neighbors.startDiscovery(2,6); h.Clock.run(100);
            sent=h.Sent('DISCOVER'); test.verifyEqual([sent.Time],[2 7]);
            test.verifyEqual(h.Done(),1); test.verifyEqual(h.Neighbors.DiscoveryState,'idle');
        end
        function receivedDiscoverDoesNotAdmitOnKeyEnqueue(test)
            h=neighborHarness(); h.Neighbors.receiveControl('DISCOVER',2,discover(7));
            sent=h.Sent('KEY_REQUEST'); test.assertNumElements(sent,1);
            test.verifyFalse(sent.Reliable); test.verifyFalse(h.Neighbors.isActive(2));
            h.Neighbors.receiveControl('KEY_UPDATE',2,struct());
            sent=h.Sent('KEY_UPDATE'); test.assertNumElements(sent,1);
            test.verifyTrue(sent.Reliable); test.verifyFalse(h.Neighbors.isActive(2));
            test.verifyEmpty(h.Sent('NEIGHBOR_CHECK'));
            h.Neighbors.controlCompleted('KEY_UPDATE',2,sent.Payload,true);
            checks=h.Sent('NEIGHBOR_CHECK'); test.assertNumElements(checks,1);
            test.verifyEqual(checks.Payload.Subtype,'discovery');
            test.verifyEqual(checks.Payload.Sequence,uint32(7));
            test.verifyFalse(h.Neighbors.isActive(2));
            h.Neighbors.controlCompleted('NEIGHBOR_CHECK',2,checks.Payload,true);
            test.verifyTrue(h.Neighbors.isActive(2)); test.verifyEqual(h.Neighbors.activePeers(),2);
        end
        function proofWithoutBothKeysCannotAdmit(test)
            h=neighborHarness();
            h.Neighbors.receiveControl('NEIGHBOR_CHECK',2,check('message',0));
            test.verifyFalse(h.Neighbors.isActive(2));
            h.Neighbors.receiveControl('KEY_UPDATE',2,struct());
            test.verifyFalse(h.Neighbors.isActive(2));
            sent=h.Sent('KEY_UPDATE'); h.Neighbors.controlCompleted('KEY_UPDATE',2,sent(end).Payload,true);
            test.verifyFalse(h.Neighbors.isActive(2));
            h.Neighbors.receiveControl('NEIGHBOR_CHECK',2,check('message',0));
            test.verifyTrue(h.Neighbors.isActive(2));
        end
        function keysAloneLeadToOverheardThenMessage(test)
            h=neighborHarness(); h.Neighbors.receiveControl('KEY_UPDATE',2,struct());
            sent=h.Sent('KEY_UPDATE'); h.Neighbors.controlCompleted('KEY_UPDATE',2,sent.Payload,true);
            checks=h.Sent('NEIGHBOR_CHECK'); test.assertNumElements(checks,1);
            test.verifyEqual(checks.Payload.Subtype,'overheard');
            test.verifyFalse(h.Neighbors.isActive(2));
            h.Neighbors.controlCompleted('NEIGHBOR_CHECK',2,checks.Payload,true);
            test.verifyTrue(h.Neighbors.isActive(2));
        end
        function keyRequestBackoffResetsOnNewDiscover(test)
            h=neighborHarness(); h.Neighbors.receiveControl('DISCOVER',2,discover(1));
            h.Clock.run(5); sent=h.Sent('KEY_REQUEST'); test.verifyEqual([sent.Time],[0 5]);
            h.Clock.run(14); test.verifyNumElements(h.Sent('KEY_REQUEST'),2);
            h.Neighbors.receiveControl('DISCOVER',2,discover(1));
            h.Clock.run(19); sent=h.Sent('KEY_REQUEST'); test.verifyEqual([sent.Time],[0 5 14 19]);
            state=h.Neighbors.snapshot(); test.verifyEqual(state.Peers.KeyRequestDelay,10);
        end
        function rejectedKeyUpdateCanRetryWithoutFakeAck(test)
            h=neighborHarness(); h.SetAccept(false);
            h.Neighbors.receiveControl('KEY_REQUEST',2,struct());
            state=h.Neighbors.snapshot(); test.verifyFalse(state.Peers.KeySendActive);
            test.verifyFalse(state.Peers.SentKey); test.verifyFalse(h.Neighbors.isActive(2));
            h.SetAccept(true); h.Neighbors.receiveControl('KEY_UPDATE',2,struct());
            test.verifyNumElements(h.Sent('KEY_UPDATE'),2);
            test.verifyFalse(h.Neighbors.isActive(2));
        end
        function duplicateDiscoveryDoesNotCreateSecondResponse(test)
            h=neighborHarness(struct('AdmissionEnabled',false));
            h.Neighbors.receiveControl('DISCOVER',2,discover(5));
            h.Neighbors.receiveControl('DISCOVER',2,discover(5));
            h.Neighbors.receiveControl('DISCOVER',2,discover(4)); h.Clock.run(0.020);
            checks=h.Sent('NEIGHBOR_CHECK'); test.assertNumElements(checks,1);
            test.verifyEqual(checks.Payload.Sequence,uint32(5));
        end
        function discoverySequenceWrapUsesSerialArithmetic(test)
            h=neighborHarness(struct('AdmissionEnabled',false));
            h.Neighbors.receiveControl('DISCOVER',2,discover(4294967295)); h.Clock.run(0.020);
            first=h.Sent('NEIGHBOR_CHECK'); h.Neighbors.controlCompleted('NEIGHBOR_CHECK',2,first.Payload,true);
            h.Neighbors.receiveControl('DISCOVER',2,discover(1)); h.Clock.run(0.040);
            checks=h.Sent('NEIGHBOR_CHECK'); test.assertNumElements(checks,2);
            test.verifyEqual(checks(2).Payload.Sequence,uint32(1));
        end
        function failedDiscoveryCheckRetriesAfterFiveSeconds(test)
            h=neighborHarness(); admitKeys(h,2,9);
            checks=h.Sent('NEIGHBOR_CHECK');
            h.Neighbors.controlCompleted('NEIGHBOR_CHECK',2,checks(end).Payload,false);
            h.Clock.run(4.99); test.verifyNumElements(h.Sent('NEIGHBOR_CHECK'),1);
            h.Clock.run(5); checks=h.Sent('NEIGHBOR_CHECK'); test.assertNumElements(checks,2);
            test.verifyEqual(checks(2).Payload.Subtype,'discovery');
            test.verifyFalse(h.Neighbors.isActive(2));
        end
        function staleCompletionCannotReactivateFailedNeighbor(test)
            h=neighborHarness(); admitKeys(h,2,1); checks=h.Sent('NEIGHBOR_CHECK');
            h.Neighbors.failNeighbor(2);
            h.Neighbors.controlCompleted('NEIGHBOR_CHECK',2,checks(end).Payload,true);
            test.verifyFalse(h.Neighbors.isActive(2));
            test.verifyEqual(h.Neighbors.snapshot().Counters.StaleCompletions,1);
        end
        function freshnessUsesStrictTimeoutAndCoalescedChirp(test)
            h=neighborHarness(struct('AdmissionEnabled',false,'FreshnessEnabled',true));
            h.Neighbors.start(); h.Neighbors.observe(2); h.Neighbors.observe(3);
            h.Clock.run(20); test.verifyEqual(h.Neighbors.activePeers(),[3 2]);
            h.Clock.run(22); test.verifyEmpty(h.Neighbors.activePeers());
            sent=h.Sent('DISCOVER'); test.assertNumElements(sent,1);
            test.verifyEqual(sent.Payload.Subtype,'chirp'); test.verifyEmpty(sent.Payload.ActivePeers);
            changes=h.Changes(); test.verifyEqual(sum(~[changes.Active]),2);
        end
        function chirpVerifyRequiresPreviouslyActiveOmittedPeer(test)
            h=neighborHarness(struct('AdmissionEnabled',false));
            chirp=struct('Subtype','chirp','Sequence',uint32(0),'ActivePeers',[]);
            h.Neighbors.receiveControl('DISCOVER',2,chirp); h.Clock.run(0.020);
            test.verifyEmpty(h.Sent('NEIGHBOR_CHECK'));
            h.Neighbors.receiveControl('DISCOVER',2,chirp); h.Clock.run(0.040);
            checks=h.Sent('NEIGHBOR_CHECK'); test.assertNumElements(checks,1);
            test.verifyEqual(checks.Payload.Subtype,'verify');
            chirp.ActivePeers=1; h.Neighbors.receiveControl('DISCOVER',2,chirp); h.Clock.run(0.060);
            test.verifyNumElements(h.Sent('NEIGHBOR_CHECK'),1);
        end
        function observedFreshnessIsNotAdmission(test)
            h=neighborHarness(); h.Neighbors.observe(2,struct('PathlossDb',80));
            test.verifyFalse(h.Neighbors.isActive(2)); test.verifyEmpty(h.Sent());
            state=h.Neighbors.snapshot(); test.verifyEqual(state.Peers.LastHeardSeconds,0);
            test.verifyEqual(state.Peers.Metrics.PathlossDb,80);
        end
        function securityResetClearsKeysAndRejectsOldCompletion(test)
            h=neighborHarness(); admitKeys(h,2,1); checks=h.Sent('NEIGHBOR_CHECK');
            h.Neighbors.controlCompleted('NEIGHBOR_CHECK',2,checks(end).Payload,true);
            test.verifyTrue(h.Neighbors.isActive(2)); h.Neighbors.securityReset(2);
            state=h.Neighbors.snapshot(); test.verifyFalse(state.Peers.ReceivedKey);
            test.verifyFalse(state.Peers.SentKey); test.verifyFalse(state.Peers.DiscoverySequenceValid);
            h.Neighbors.controlCompleted('NEIGHBOR_CHECK',2,checks(end).Payload,true);
            test.verifyFalse(h.Neighbors.isActive(2));
        end
        function inactiveFailureStillInvalidatesCachedReporter(test)
            h=neighborHarness(); h.Neighbors.observe(2); h.Neighbors.failNeighbor(2);
            changes=h.Changes(); test.assertNumElements(changes,1); test.verifyFalse(changes.Active);
            h.Clock.run(0); test.verifyEmpty(h.Sent('DISCOVER'));
        end
        function reciprocalAdmissionUsesDeliveredControlsAndAckCallbacks(test)
            % Component transport; this is not a PHY or airtime fixture.
            h=reciprocalHarness(); h.Left.startDiscovery();
            h.Clock.run(2);
            test.verifyTrue(h.Left.isActive(2)); test.verifyTrue(h.Right.isActive(1));
            left=h.Left.snapshot(); right=h.Right.snapshot();
            test.verifyTrue(left.Peers.ReceivedKey && left.Peers.SentKey);
            test.verifyTrue(right.Peers.ReceivedKey && right.Peers.SentKey);
            test.verifyGreaterThan(left.Counters.KeyUpdates+right.Counters.KeyUpdates,1);
        end
    end
end

function h = neighborHarness(options)
if nargin<1, options=struct(); end
scheduler=csr.sim.EventScheduler();
sent=repmat(struct('Time',0,'Kind','','Peers',[],'Payload',struct(),'Reliable',false),0,1);
changes=repmat(struct('Peer',0,'Active',false),0,1); done=0; accept=true;
callbacks=struct('SendControl',@send,'NeighborChanged',@changed,'DiscoveryFinished',@finished);
neighbors=csr.nwk.Neighbors(1,scheduler,options,callbacks);
h=struct('Clock',scheduler,'Neighbors',neighbors,'Sent',@getSent,'Changes',@getChanges, ...
    'Done',@getDone,'SetAccept',@setAccept);
    function okay = send(kind,peers,payload,reliable)
        sent(end+1,1)=struct('Time',scheduler.Now,'Kind',kind,'Peers',peers, ...
            'Payload',payload,'Reliable',reliable); okay=accept;
    end
    function result = getSent(kind)
        result=sent;
        if nargin>0 && ~isempty(result), result=result(strcmp({result.Kind},kind)); end
    end
    function changed(peer,active)
        changes(end+1,1)=struct('Peer',peer,'Active',active);
    end
    function result = getChanges(), result=changes; end
    function finished(~), done=done+1; end
    function result = getDone(), result=done; end
    function setAccept(item), accept=logical(item); end
end
function payload = discover(sequence)
payload=struct('Subtype','broadcast','Sequence',uint32(sequence),'ActivePeers',[]);
end
function payload = check(subtype,sequence)
payload=struct('Subtype',subtype,'Sequence',uint32(sequence),'Active',false);
end
function admitKeys(h,peer,sequence)
h.Neighbors.receiveControl('DISCOVER',peer,discover(sequence));
h.Neighbors.receiveControl('KEY_UPDATE',peer,struct());
sent=h.Sent('KEY_UPDATE'); h.Neighbors.controlCompleted('KEY_UPDATE',peer,sent(end).Payload,true);
end
function h = reciprocalHarness()
scheduler=csr.sim.EventScheduler();
left=csr.nwk.Neighbors(1,scheduler,struct(),struct('SendControl',@sendLeft));
right=csr.nwk.Neighbors(2,scheduler,struct(),struct('SendControl',@sendRight));
h=struct('Clock',scheduler,'Left',left,'Right',right);
    function accepted = sendLeft(kind,~,payload,reliable)
        scheduler.scheduleAt(scheduler.Now+0.01,@()receive(right,left,kind,1,2,payload,reliable));
        accepted=true;
    end
    function accepted = sendRight(kind,~,payload,reliable)
        scheduler.scheduleAt(scheduler.Now+0.01,@()receive(left,right,kind,2,1,payload,reliable));
        accepted=true;
    end
    function receive(receiver,sender,kind,source,destination,payload,reliable)
        receiver.receiveControl(kind,source,payload);
        if reliable
            scheduler.scheduleAt(scheduler.Now+0.01, ...
                @()sender.controlCompleted(kind,destination,payload,true));
        end
    end
end
