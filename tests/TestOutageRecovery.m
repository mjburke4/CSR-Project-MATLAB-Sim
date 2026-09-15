classdef TestOutageRecovery < matlab.unittest.TestCase
    % Source-contract fixtures use real HOP/NWK with an explicit fake MAC.
    % They test freshness and custody ordering, not RF outage performance.
    methods (Test)
        function passiveRadioDoesNotCreateNwkNeighbor(test)
            h=networkHarness(false);
            h.Layer.observeRadio(2,struct('Success',true,'PathlossDb',90));
            test.verifyEmpty(h.Layer.neighborsSnapshot());
            test.verifyFalse(h.Layer.routeAvailable(application(1,1,2)));
        end
        function dataAndAckDoNotPostponeStrictFreshness(test)
            h=networkHarness(true); h.Receive(discoverFrame(1),0);
            data=csr.hop.Frames.data(application(1,2,1),2,1,uint16(10));
            h.Receive(data,10);
            ack=csr.hop.Frames.acknowledgment(2,1,uint16(300),uint64(1),uint64(0));
            h.Receive(ack,18);
            peer=h.Peer(); test.verifyEqual(peer.LastHeardSeconds,0);
            h.Clock.run(20); test.verifyTrue(h.Peer().Active);
            h.Clock.run(22); peer=h.Peer();
            test.verifyTrue(peer.Stale); test.verifyFalse(peer.Active);
            test.verifyEqual(peer.Failures,0);
            test.verifyEqual(h.Hop.stats().Delivered,1);
        end
        function overheardCheckDoesNotRenewNwkLiveness(test)
            h=networkHarness(true); h.Receive(discoverFrame(1),0);
            frame=controlFrame('NEIGHBOR_CHECK',checkPayload(),1,99);
            h.Receive(frame,19);
            test.verifyEqual(h.Peer().LastHeardSeconds,0);
            test.verifyEqual(h.Hop.stats().ControlReceived,1);
            h.Clock.run(22); test.verifyTrue(h.Peer().Stale);
        end
        function firstControlsRenewButTheirDuplicatesDoNot(test)
            h=networkHarness(false); h.Receive(discoverFrame(1),0);
            check=controlFrame('NEIGHBOR_CHECK',checkPayload(),1,1);
            h.Receive(check,10); test.verifyEqual(h.Peer().LastHeardSeconds,10);
            h.Receive(check,18); test.verifyEqual(h.Peer().LastHeardSeconds,10);
            sections=csr.nwk.RoutingCodec.sections( ...
                csr.nwk.RoutingCodec.encodeRecords({struct('Operation','FLUSH')}),5);
            routing=controlFrame('ROUTING',struct('Bytes',sections{1}),2,1);
            h.Receive(routing,25); test.verifyEqual(h.Peer().LastHeardSeconds,25);
            h.Receive(routing,28); test.verifyEqual(h.Peer().LastHeardSeconds,25);
            test.verifyEqual(h.Hop.stats().ControlDuplicates,2);
        end
        function keyTrafficAndKeyAckDoNotRenewNwkLiveness(test)
            h=networkHarness(false); h.Receive(discoverFrame(1),0);
            h.Receive(controlFrame('KEY_REQUEST',struct(),1,1),7);
            h.Receive(controlFrame('KEY_UPDATE',struct(),2,1),9);
            frames=h.Frames();
            keys=frames(cellfun(@(f)strcmp(f.Kind,'CONTROL') && ...
                strcmp(f.Control.Type,'KEY_UPDATE'),frames));
            test.assertNotEmpty(keys);
            ack=csr.hop.Frames.acknowledgment(2,1,keys{end}.Sequence, ...
                uint64(0),uint64(0),struct('HasAckWindow',false));
            h.Receive(ack,11);
            test.verifyTrue(h.Peer().SentKey);
            test.verifyEqual(h.Peer().LastHeardSeconds,0);
        end
        function everyFirstRoutingSectionRenewsBeforeReassembly(test)
            h=networkHarness(false); h.Receive(discoverFrame(1),0);
            records=cell(1,60);
            for index=1:60, records{index}=routeUpdate(100+index); end
            sections=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords(records),5);
            test.assertNumElements(sections,2);
            first=controlFrame('ROUTING',struct('Bytes',sections{1}),1,1);
            h.Receive(first,10);
            test.verifyEqual(h.Peer().LastHeardSeconds,10);
            test.verifyFalse(h.Layer.routeAvailable(application(1,1,101)));
            h.Receive(first,18); test.verifyEqual(h.Peer().LastHeardSeconds,10);
            h.Receive(controlFrame('ROUTING',struct('Bytes',sections{2}),2,1),20);
            test.verifyEqual(h.Peer().LastHeardSeconds,20);
            test.verifyTrue(h.Layer.routeAvailable(application(1,1,101)));
        end
        function malformedRoutingDoesNotRenewFreshness(test)
            h=networkHarness(true); h.Receive(discoverFrame(1),0);
            bad=controlFrame('ROUTING',struct('Bytes',uint8([0 0 0 12 0 1 255])),1,1);
            h.Receive(bad,19);
            test.verifyEqual(h.Peer().LastHeardSeconds,0);
            h.Clock.run(22); test.verifyTrue(h.Peer().Stale);
        end
        function freshnessPreservesKeyOwnerBackoffsAndCallbackGeneration(test)
            h=neighborHarness(); h.Neighbors.start();
            h.Neighbors.receiveControl('DISCOVER',2,discoverPayload());
            h.Clock.run(10); h.Neighbors.receiveControl('KEY_UPDATE',2,struct());
            before=h.Peer(); test.verifyTrue(before.KeySendActive);
            h.Clock.run(22); after=h.Peer();
            test.verifyTrue(after.Stale); test.verifyTrue(after.KeySendActive);
            for name={'Failures','Generation','RetryEvent','KeyRequestWhen','KeyRequestDelay', ...
                    'KeySendWhen','KeySendDelay','OverheardWhen','OverheardDelay'}
                test.verifyEqual(after.(name{1}),before.(name{1}));
            end
            sent=h.Sent('KEY_UPDATE'); test.assertNumElements(sent,1);
            h.Clock.run(23);
            h.Neighbors.controlCompleted('KEY_UPDATE',2,sent.Payload,true);
            after=h.Peer(); test.verifyTrue(after.SentKey); test.verifyFalse(after.KeySendActive);
            test.verifyTrue(after.Stale); test.verifyEqual(after.LastHeardSeconds,0);
            test.verifyEqual(h.Neighbors.snapshot().Counters.StaleCompletions,0);
        end
        function inFlightCheckProofCanReadmitAfterFreshnessExpiry(test)
            h=neighborHarness(); h.Neighbors.start();
            h.Neighbors.receiveControl('DISCOVER',2,discoverPayload());
            h.Neighbors.receiveControl('KEY_UPDATE',2,struct());
            keys=h.Sent('KEY_UPDATE');
            h.Neighbors.controlCompleted('KEY_UPDATE',2,keys(end).Payload,true);
            checks=h.Sent('NEIGHBOR_CHECK'); test.assertNotEmpty(checks);
            h.Clock.run(22); test.verifyTrue(h.Peer().Stale);
            h.Clock.run(23);
            h.Neighbors.controlCompleted('NEIGHBOR_CHECK',2,checks(end).Payload,true);
            peer=h.Peer(); test.verifyTrue(peer.Active); test.verifyFalse(peer.Stale);
            test.verifyEqual(peer.LastHeardSeconds,23); test.verifyEqual(peer.Failures,0);
            test.verifyEqual(h.Neighbors.snapshot().Counters.StaleCompletions,0);
        end
        function obsoleteDiscoveryVerifyCannotRenewFreshness(test)
            h=neighborHarness(); h.Neighbors.start();
            h.Neighbors.receiveControl('DISCOVER',2,discoverPayload());
            h.Clock.run(19);
            payload=struct('Subtype','verify','Sequence',uint32(99),'Generation',0);
            h.Neighbors.controlCompleted('NEIGHBOR_CHECK',2,payload,true);
            test.verifyEqual(h.Peer().LastHeardSeconds,0);
            h.Clock.run(22); test.verifyTrue(h.Peer().Stale);
            test.verifyEqual(h.Peer().Failures,0);
        end
        function staleInactiveReporterStillChirpsAndReportsExactCause(test)
            h=neighborHarness(); h.Neighbors.start();
            h.Neighbors.receiveControl('DISCOVER',2,discoverPayload());
            test.verifyFalse(h.Peer().Active); h.Clock.run(22);
            sent=h.Sent('DISCOVER'); test.assertNumElements(sent,1);
            test.verifyEqual(sent.Payload.Subtype,'chirp');
            events=h.Events(); inactive=events(strcmp({events.Name},'neighbor_inactive'));
            test.assertNumElements(inactive,1);
            test.verifyEqual(inactive.Details.Reason,'freshness_timeout');
            test.verifyEqual(inactive.Details.LastHeardSeconds,0);
            test.verifyEqual(inactive.Details.AgeSeconds,22);
            test.verifyEqual(inactive.Details.TimeoutSeconds,20);
            test.verifyEqual(h.Peer().Failures,0);
        end
        function expiredRoutingAssemblyCannotCompleteAfterReadmission(test)
            h=networkHarness(true); h.Receive(discoverFrame(1),0);
            records=cell(1,60);
            for index=1:60, records{index}=routeUpdate(100+index); end
            sections=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords(records),5);
            test.assertNumElements(sections,2);
            h.Receive(controlFrame('ROUTING',struct('Bytes',sections{1}),1,1),0);
            h.Clock.run(22); test.verifyTrue(h.Peer().Stale);
            h.Receive(controlFrame('ROUTING',struct('Bytes',sections{2}),2,1),23);
            test.verifyTrue(h.Peer().Active);
            test.verifyFalse(h.Layer.routeAvailable(application(1,1,101)));
            test.verifyEqual(h.Layer.stats().RoutingMessagesReceived,0);
        end
        function dataExhaustionRemainsTerminalWithoutNeighborPenalty(test)
            h=networkHarness(false); h.Receive(discoverFrame(1),0);
            app=application(1,1,2); test.verifyTrue(h.Layer.sendApplication(app));
            h.Clock.run(0); frames=h.DataFrames(); h.Hop.notifySent(frames{end});
            h.Clock.run(2.01); frames=h.DataFrames(); h.Hop.notifySent(frames{end});
            h.Clock.run(4.02); frames=h.DataFrames(); h.Hop.notifySent(frames{end});
            h.Clock.run(8.03);
            test.verifyEqual(h.Hop.stats().Failed,1);
            test.verifyEqual(h.Hop.PendingDataCount,0);
            test.verifyEqual(h.Layer.stats().PendingCustody,0);
            test.verifyNumElements(h.DataFrames(),3);
            drops=h.Drops(); test.assertNumElements(drops,1);
            test.verifyEqual(drops.Reason,'retry_exhausted');
            peer=h.Peer(); test.verifyTrue(peer.Active); test.verifyEqual(peer.Failures,0);
            test.verifyEqual(peer.LastHeardSeconds,0);
            test.verifyTrue(h.Layer.routeAvailable(app));
        end
    end
end

function h = networkHarness(freshness)
scheduler=csr.sim.EventScheduler(); options=csr.nwk.defaults();
options.StartupMode='manual'; options.AdaptiveLinkControl=false;
options.Neighbor.AdmissionEnabled=false; options.Neighbor.FreshnessEnabled=freshness;
radio=struct('RateKeyKbps',8,'TxPowerDbm',30,'Preamble','long','EnvelopeProfile','bare');
config=struct('Nwk',options,'Radio',radio,'Nodes',struct('Id',1, ...
    'Capability',1,'TransitForwardingEnabled',true));
frames={}; drops=repmat(struct('App',struct(),'Reason',''),0,1);
hop=[];
callbacks=struct('CanSendData',@canSendData,'SendData',@sendData, ...
    'CanSendControl',@canSendControl,'SendControl',@sendControl, ...
    'Dropped',@dropped);
layer=csr.nwk.Layer(1,scheduler,[],config,callbacks);
hopCallbacks=struct('EnqueueMac',@enqueue,'Deliver',@(app,peer)layer.receiveData(app,peer), ...
    'ValidateControl',@(control,peer)layer.validateControl(control,peer), ...
    'DeliverControl',@(control,peer)layer.receiveControl(control,peer), ...
    'ControlResult',@(control,peer,success,complete,remaining) ...
        layer.controlResult(control,peer,success,complete,remaining), ...
    'NsdpRelease',@(app,reason)layer.releaseFromHop(app,reason), ...
    'NsdpCount',@(app)layer.nsdpCount(app),'RouteAvailable',@(app)layer.routeAvailable(app), ...
    'Terminal',@(app,success,reason)layer.terminal(app,success,reason), ...
    'Wake',@()layer.wake());
hop=csr.hop.Layer(1,scheduler,[],struct(),hopCallbacks);
layer.start();
h=struct('Clock',scheduler,'Layer',layer,'Hop',hop,'Receive',@receive, ...
    'Peer',@peer,'Frames',@getFrames,'DataFrames',@dataFrames,'Drops',@getDrops);
    function accepted = enqueue(frame), frames{end+1}=frame; accepted=true; end
    % Nested callbacks share the initialized HOP handle. Anonymous functions
    % created before its assignment would capture the initial empty value.
    function allowed = canSendData(peer), allowed=hop.canSend(peer); end
    function accepted = sendData(app,peer,settings), accepted=hop.send(app,peer,settings); end
    function allowed = canSendControl(peers), allowed=hop.canSendControl(peers); end
    function accepted = sendControl(control,peers,settings)
        accepted=hop.sendControl(control,peers,settings);
    end
    function receive(frame,when)
        scheduler.run(when);
        layer.observeRadio(frame.SourceId,struct('Success',true,'PathlossDb',90));
        if any(frame.DestinationId==[1 16777215]), hop.receive(frame); end
    end
    function entry = peer()
        peers=layer.neighborsSnapshot(); entry=peers([peers.PeerId]==2);
    end
    function result = getFrames(), result=frames; end
    function result = dataFrames()
        result=frames(cellfun(@(frame)strcmp(frame.Kind,'DATA'),frames));
    end
    function dropped(app,reason)
        drops(end+1,1)=struct('App',app,'Reason',reason);
    end
    function result = getDrops(), result=drops; end
end

function h = neighborHarness()
scheduler=csr.sim.EventScheduler();
sent=repmat(struct('Kind','','Payload',struct()),0,1);
events=repmat(struct('Name','','Details',struct()),0,1);
options=struct('FreshnessEnabled',true,'AdmissionRetrySeconds',30);
neighbors=csr.nwk.Neighbors(1,scheduler,options,struct('SendControl',@send,'Event',@event));
h=struct('Clock',scheduler,'Neighbors',neighbors,'Sent',@getSent,'Peer',@peer,'Events',@getEvents);
    function accepted = send(kind,~,payload,~)
        sent(end+1,1)=struct('Kind',kind,'Payload',payload); accepted=true;
    end
    function result = getSent(kind), result=sent(strcmp({sent.Kind},kind)); end
    function entry = peer(), state=neighbors.snapshot(); entry=state.Peers; end
    function event(name,~,details)
        events(end+1,1)=struct('Name',name,'Details',details);
    end
    function result = getEvents(), result=events; end
end

function frame = discoverFrame(sequence)
frame=controlFrame('DISCOVER',discoverPayload(),sequence,16777215);
end
function payload = discoverPayload()
payload=struct('Subtype','broadcast','Sequence',uint32(1),'ActivePeers',[]);
end
function payload = checkPayload()
payload=struct('Subtype','message','Sequence',uint32(0),'Active',true);
end
function frame = controlFrame(kind,payload,sequence,destination)
control=struct('Id',uint64(sequence),'Type',kind,'Payload',payload,'WirePayloadBytes',64);
frame=csr.hop.Frames.control(control,2,destination,uint16(sequence), ...
    struct('AckRequired',destination~=16777215));
end
function app = application(id,source,destination)
flow=struct('SourceId',source,'DestinationId',destination,'ApplicationPayloadBytes',64);
radio=struct('RateKeyKbps',8,'Preamble','long','EnvelopeProfile','bare');
app=csr.packet(uint64(id),flow,0,radio); app.Dscp=0; app.AckRequired=true;
end
function record = routeUpdate(destination)
record=struct('Operation','UPDATE','NodeId',destination,'Capability',1, ...
    'HopCount',1,'Cost',10,'Path',destination);
end
