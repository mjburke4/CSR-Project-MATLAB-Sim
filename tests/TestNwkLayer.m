classdef TestNwkLayer < matlab.unittest.TestCase
    % Coordinator fixtures use explicit fake transport; no PHY claim is made.
    methods (Test)
        function noRouteRetainsCustodyWithoutStartingDiscovery(test)
            h=nwkHarness(); app=application(1,1,99);
            test.verifyTrue(h.Layer.sendApplication(app)); h.Clock.run(20);
            test.verifyEmpty(h.Data()); test.verifyEmpty(h.Controls());
            stats=h.Layer.stats(); test.verifyEqual(stats.PendingCustody,1);
            test.verifyEqual(stats.WaitingForRoute,1); test.verifyEqual(stats.DiscoveryStarts,0);
            test.verifyEqual(h.Layer.nsdpCount(app),1);
        end
        function noRouteAtQueueHeadDoesNotBlockAnotherDestination(test)
            h=nwkHarness(); h.Layer.observe(2,struct('Success',true));
            blocked=application(1,1,99); blocked.Dscp=7;
            ready=application(2,1,2); ready.Dscp=0;
            h.Layer.sendApplication(blocked); h.Layer.sendApplication(ready); h.Clock.run(0);
            sent=h.Data(); test.assertNumElements(sent,1);
            test.verifyEqual(sent.App.Id,ready.Id); test.verifyEqual(sent.Peer,2);
            test.verifyEqual(h.Layer.stats().PendingCustody,2);
            h.Layer.release(ready,'ack'); h.Clock.run(0);
            test.verifyEqual(h.Layer.nsdpCount(ready),0); test.verifyEqual(h.Layer.nsdpCount(blocked),1);
        end
        function hopBusyPeerDoesNotBlockOtherPeer(test)
            h=nwkHarness(); h.Layer.observe(2,struct()); h.Layer.observe(3,struct());
            h.BlockData(2); h.Layer.sendApplication(application(1,1,2));
            h.Layer.sendApplication(application(2,1,3)); h.Clock.run(0);
            sent=h.Data(); test.assertNumElements(sent,1); test.verifyEqual(sent.Peer,3);
            h.BlockData([]); h.Layer.wake(); h.Clock.run(0);
            sent=h.Data(); test.assertNumElements(sent,2); test.verifyEqual(sent(2).Peer,2);
        end
        function boundedLocalQueueReportsOneDropWithoutTakingCustody(test)
            h=nwkHarness(struct('QueueLimit',1));
            test.verifyTrue(h.Layer.sendApplication(application(1,1,99)));
            test.verifyFalse(h.Layer.sendApplication(application(2,1,99)));
            dropped=h.Drops(); test.assertNumElements(dropped,1);
            test.verifyEqual(dropped.Reason,'network_queue_full');
            test.verifyEqual(h.Layer.stats().PendingCustody,1);
        end
        function localDeliveryAndDuplicateUseSameApplicationIdentity(test)
            h=nwkHarness(); h.Layer.observe(2,struct()); app=application(7,2,1);
            test.verifyTrue(h.Layer.receiveData(app,2));
            test.verifyTrue(h.Layer.receiveData(app,2));
            delivered=h.Deliveries(); test.assertNumElements(delivered,1);
            test.verifyEqual(delivered.App.SourceId,2);
            test.verifyEqual(delivered.App.HopCount,1);
            test.verifyEqual(delivered.App.Traversal,[2 1]);
        end
        function inactivePeerCannotDeliverApplication(test)
            options=struct('Neighbor',struct('AdmissionEnabled',true));
            h=nwkHarness(options); h.Layer.observe(2,struct());
            [accepted,reason]=h.Layer.receiveData(application(1,2,1),2);
            test.verifyFalse(accepted); test.verifyEqual(reason,'inactive_neighbor');
            test.verifyEmpty(h.Deliveries()); h.Clock.run(0);
            controls=h.Controls(); test.verifyTrue(any(strcmp({controls.Kind},'NEIGHBOR_CHECK')));
        end
        function relayCustodyChecksRouteAndRecordsTraversal(test)
            h=nwkHarness(); h.Layer.observe(2,struct()); h.Layer.observe(3,struct());
            test.verifyFalse(h.Layer.receiveData(application(1,2,99),2));
            test.verifyEmpty(h.Custodies());
            app=application(2,2,3); test.verifyTrue(h.Layer.receiveData(app,2));
            custody=h.Custodies(); test.assertNumElements(custody,1);
            test.verifyEqual(custody.App.HopCount,1); test.verifyEqual(custody.App.Traversal,[2 1]);
            h.Clock.run(0); sent=h.Data(); test.assertNumElements(sent,1); test.verifyEqual(sent.Peer,3);
        end
        function configuredLeafAndRevisitedPacketRefuseTransit(test)
            leaf=nwkHarness(struct(),0,false); leaf.Layer.observe(2,struct()); leaf.Layer.observe(3,struct());
            [accepted,reason]=leaf.Layer.receiveData(application(1,2,3),2);
            test.verifyFalse(accepted); test.verifyEqual(reason,'transit_disabled');
            test.verifyEmpty(leaf.Custodies());
            leaf.Clock.run(0); controls=leaf.Controls();
            targeted=controls(arrayfun(@(row)isfield(row.Control.Payload,'Subtype') && ...
                strcmp(row.Control.Payload.Subtype,'no_path'),controls));
            test.assertNumElements(targeted,1);
            test.verifyEqual(targeted.Peers,2);
            test.verifyEqual(targeted.Control.Payload.TargetId,3);
            h=nwkHarness(); h.Layer.observe(2,struct()); h.Layer.observe(3,struct());
            app=application(1,2,3); app.Traversal=[2 1]; app.HopCount=1;
            [accepted,reason]=h.Layer.receiveData(app,2);
            test.verifyFalse(accepted); test.verifyEqual(reason,'routing_loop');
            test.verifyEmpty(h.Custodies());
        end
        function ordinaryCapabilityAloneDoesNotDisableTransit(test)
            h=nwkHarness(struct(),0); h.Layer.observe(2,struct()); h.Layer.observe(3,struct());
            test.verifyTrue(h.Layer.receiveData(application(1,2,3),2));
            custody=h.Custodies(); test.assertNumElements(custody,1);
            h.Clock.run(0); sent=h.Data(); test.assertNumElements(sent,1); test.verifyEqual(sent.Peer,3);
        end
        function positiveDscpPacketsPushFrontWithoutNumericalPrioritySorting(test)
            h=nwkHarness(); h.Layer.observe(2,struct()); h.BlockData(2);
            values=[0 1 7 1];
            for index=1:numel(values)
                app=application(index,1,2); app.Dscp=values(index); h.Layer.sendApplication(app);
            end
            h.Clock.run(0); test.verifyEmpty(h.Data());
            h.BlockData([]); h.Layer.wake(); h.Clock.run(0);
            sent=h.Data(); ids=arrayfun(@(row)double(row.App.Id),sent);
            test.verifyEqual(reshape(ids,1,[]),[4 3 2 1]);
        end
        function gatewayTrafficWaitsForSelfUpdateCapability(test)
            h=nwkHarness(struct('SendOnlyToGateway',true));
            h.Layer.observe(2,struct('Capability',2)); app=application(1,1,2);
            h.Layer.sendApplication(app); h.Clock.run(0); test.verifyEmpty(h.Data());
            h.DeliverRecords(2,1,{routeUpdate(2,2,0,0,[])}); h.Clock.run(0);
            sent=h.Data(); test.assertNumElements(sent,1); test.verifyEqual(sent.Peer,2);
            h.Layer.release(app,'ack'); h.DeliverRecords(2,2,{struct('Operation','DELETE','NodeId',2)});
            h.Layer.sendApplication(application(2,1,2)); h.Clock.run(0);
            test.verifyNumElements(h.Data(),1);
        end
        function submittedDataIsNotRepeatedUntilTransportReleasesIt(test)
            h=nwkHarness(); h.Layer.observe(2,struct()); app=application(1,1,2);
            h.Layer.sendApplication(app); h.Clock.run(0);
            h.Layer.wake(); h.Layer.wake(); h.Clock.run(0);
            test.verifyNumElements(h.Data(),1); test.verifyEqual(h.Layer.nsdpCount(app),1);
            h.Layer.terminal(app,false,'retry_exhausted'); h.Clock.run(0);
            test.verifyEqual(h.Layer.stats().PendingCustody,0);
            dropped=h.Drops(); test.assertNumElements(dropped,1);
            test.verifyEqual(dropped.Reason,'retry_exhausted');
        end
        function routingPartialAckRetryWaitsForLaterEventAndKeepsBytes(test)
            h=nwkHarness(); h.Layer.observe(2,struct()); h.Layer.observe(3,struct()); h.Clock.run(0);
            controls=h.Controls(); pick=find(strcmp({controls.Kind},'ROUTING') & ...
                arrayfun(@(row)numel(row.Peers)==2,controls),1);
            test.assertNotEmpty(pick); original=controls(pick); before=numel(controls);
            h.Layer.controlResult(original.Control,original.Peers(1),true,false,original.Peers(2));
            test.verifyNumElements(h.Controls(),before);
            h.Layer.controlResult(original.Control,original.Peers(2),false,true,original.Peers(2));
            test.verifyNumElements(h.Controls(),before);
            h.Clock.run(0); controls=h.Controls(); test.assertNumElements(controls,before+1);
            retry=controls(end); test.verifyEqual(retry.Peers,original.Peers(2));
            test.verifyEqual(retry.Control.Payload.Bytes,original.Control.Payload.Bytes);
            test.verifyNotEqual(retry.Control.Id,original.Control.Id);
            test.verifyEqual(h.Layer.stats().ControlResidualRetries,1);
        end
        function groupedRoutingAdmissionChecksAllRecipients(test)
            h=nwkHarness(); h.BlockControls(3);
            h.Layer.observe(2,struct()); h.Layer.observe(3,struct()); h.Clock.run(0);
            controls=h.Controls(); test.verifyFalse(any(arrayfun(@(row)ismember(3,row.Peers),controls)));
            h.BlockControls([]); h.Clock.run(8);
            controls=h.Controls(); test.verifyTrue(any(arrayfun(@(row)numel(row.Peers)==2,controls)));
        end
        function gatewayStartupOccursAtTenSeconds(test)
            h=nwkHarness(struct('StartupMode','gateway'),2); h.Layer.start();
            h.Clock.run(9.99); test.verifyEqual(h.Layer.stats().DiscoveryStarts,0);
            h.Clock.run(10); test.verifyEqual(h.Layer.stats().DiscoveryStarts,1);
            controls=h.Controls(); discovery=controls(strcmp({controls.Kind},'DISCOVER'));
            test.assertNumElements(discovery,1); test.verifyEqual(discovery.Time,10);
        end
        function completeDiscoveryAllowsExplicitRecoveryScan(test)
            h=nwkHarness(); test.verifyTrue(h.Layer.startDiscovery()); h.Clock.run(15);
            test.verifyEqual(h.Layer.stats().DiscoveryCompletions,1);
            test.verifyTrue(h.Layer.startDiscovery()); h.Clock.run(15);
            test.verifyEqual(h.Layer.stats().DiscoveryStarts,2);
        end
        function freshMetricObservationCannotReleaseInactiveCachedTransit(test)
            h=nwkHarness(struct('Neighbor',struct('AdmissionEnabled',true)));
            h.Layer.observe(2,struct()); h.DeliverRecords(2,1,{routeUpdate(9,1,1,10,9)});
            app=application(1,1,9); test.verifyFalse(h.Layer.routeAvailable(app));
            h.Admit(2); test.verifyFalse(h.Layer.routeAvailable(app));
            h.Layer.observe(2,struct()); test.verifyFalse(h.Layer.routeAvailable(app));
            h.DeliverRecords(2,2,{routeUpdate(9,1,1,10,9)});
            test.verifyTrue(h.Layer.routeAvailable(app));
        end
        function staleInactiveReporterLosesItsCachedTransit(test)
            h=nwkHarness(struct('Neighbor',struct('AdmissionEnabled',true,'FreshnessEnabled',true)));
            h.Layer.start(); h.Layer.observe(2,struct());
            h.DeliverRecords(2,1,{routeUpdate(9,1,1,10,9)});
            app=application(1,1,9); test.verifyFalse(h.Layer.routeAvailable(app));
            h.Clock.run(22);
            peers=h.Layer.neighborsSnapshot(); test.verifyTrue(peers.Stale);
            h.Layer.observe(2,struct()); h.Admit(2);
            h.Layer.observe(3,struct()); h.Admit(3);
            % A looped update still recomputes its destination. If reporter
            % 2's old candidate survived failure it could become selected.
            h.DeliverRecords(3,1,{routeUpdate(9,1,2,20,[1 9])});
            test.verifyFalse(h.Layer.routeAvailable(app));
            h.DeliverRecords(2,2,{routeUpdate(9,1,1,10,9)});
            test.verifyTrue(h.Layer.routeAvailable(app));
        end
        function incompleteRoutingStreamDoesNotChangeLiveRoutes(test)
            h=nwkHarness(); h.Layer.observe(2,struct()); records=cell(1,60);
            for index=1:60, records{index}=routeUpdate(100+index,1,1,index,100+index); end
            sections=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords(records),5);
            test.assertNumElements(sections,2);
            h.Layer.receiveControl(struct('Type','ROUTING','Payload',struct('Bytes',sections{1})),2);
            test.verifyFalse(h.Layer.routeAvailable(application(1,1,101)));
            h.Layer.receiveControl(struct('Type','ROUTING','Payload',struct('Bytes',sections{2})),2);
            test.verifyTrue(h.Layer.routeAvailable(application(1,1,101)));
            test.verifyTrue(h.Layer.routeAvailable(application(2,1,160)));
        end
    end
end

function h = nwkHarness(overrides,capability,transitEnabled)
if nargin<1, overrides=struct(); end
if nargin<2, capability=1; end
if nargin<3, transitEnabled=true; end
scheduler=csr.sim.EventScheduler(); options=csr.nwk.defaults();
options.StartupMode='manual'; options.AdaptiveLinkControl=false; options.Neighbor.AdmissionEnabled=false;
names=fieldnames(overrides);
for index=1:numel(names)
    if strcmp(names{index},'Neighbor')
        fields=fieldnames(overrides.Neighbor);
        for item=1:numel(fields), options.Neighbor.(fields{item})=overrides.Neighbor.(fields{item}); end
    else
        options.(names{index})=overrides.(names{index});
    end
end
radio=struct('RateKeyKbps',8,'TxPowerDbm',30,'Preamble','long','EnvelopeProfile','bare');
config=struct('Nwk',options,'Radio',radio,'Nodes',struct('Id',1, ...
    'Capability',capability,'TransitForwardingEnabled',transitEnabled));
data=repmat(struct('Time',0,'App',struct(),'Peer',0,'Options',struct()),0,1);
controls=repmat(struct('Time',0,'Kind','','Control',struct(),'Peers',[],'Options',struct()),0,1);
deliveries=repmat(struct('App',struct(),'Peer',0),0,1);
custodies=repmat(struct('App',struct(),'Peer',0),0,1);
drops=repmat(struct('App',struct(),'Reason',''),0,1); blockedData=[]; blockedControls=[];
callbacks=struct('CanSendData',@canSendData,'SendData',@sendData, ...
    'CanSendControl',@canSendControl,'SendControl',@sendControl, ...
    'CustodyAccepted',@custody,'Delivered',@delivered,'Dropped',@dropped);
layer=csr.nwk.Layer(1,scheduler,[],config,callbacks);
h=struct('Clock',scheduler,'Layer',layer,'Data',@getData,'Controls',@getControls, ...
    'Deliveries',@getDeliveries,'Custodies',@getCustodies,'Drops',@getDrops, ...
    'BlockData',@blockData,'BlockControls',@blockControls,'DeliverRecords',@deliverRecords,'Admit',@admit);
    function okay = canSendData(peer), okay=~ismember(peer,blockedData); end
    function okay = canSendControl(peers), okay=~any(ismember(peers,blockedControls)); end
    function okay = sendData(app,peer,sendOptions)
        data(end+1,1)=struct('Time',scheduler.Now,'App',app,'Peer',peer,'Options',sendOptions);
        okay=true;
    end
    function okay = sendControl(control,peers,sendOptions)
        controls(end+1,1)=struct('Time',scheduler.Now,'Kind',control.Type, ...
            'Control',control,'Peers',peers,'Options',sendOptions); okay=true;
    end
    function okay = delivered(app,peer)
        deliveries(end+1,1)=struct('App',app,'Peer',peer); okay=true;
    end
    function custody(app,peer), custodies(end+1,1)=struct('App',app,'Peer',peer); end
    function dropped(app,reason), drops(end+1,1)=struct('App',app,'Reason',reason); end
    function result = getData(), result=data; end
    function result = getControls(), result=controls; end
    function result = getDeliveries(), result=deliveries; end
    function result = getCustodies(), result=custodies; end
    function result = getDrops(), result=drops; end
    function blockData(peers), blockedData=peers; end
    function blockControls(peers), blockedControls=peers; end
    function deliverRecords(peer,sequence,records)
        sections=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords(records),sequence);
        for part=1:numel(sections)
            layer.receiveControl(struct('Type','ROUTING','Payload',struct('Bytes',sections{part})),peer);
        end
    end
    function admit(peer)
        layer.receiveControl(struct('Type','KEY_UPDATE','Payload',struct()),peer); scheduler.run(scheduler.Now);
        keys=controls(strcmp({controls.Kind},'KEY_UPDATE')); row=keys(end);
        layer.controlResult(row.Control,peer,true,true,[]); scheduler.run(scheduler.Now);
        layer.receiveControl(struct('Type','NEIGHBOR_CHECK', ...
            'Payload',struct('Subtype','message','Sequence',uint32(0),'Active',true)),peer);
        scheduler.run(scheduler.Now);
    end
end
function app = application(id,source,destination)
flow=struct('SourceId',source,'DestinationId',destination,'ApplicationPayloadBytes',64);
radio=struct('RateKeyKbps',8,'Preamble','long','EnvelopeProfile','bare');
app=csr.packet(uint64(id),flow,0,radio); app.Dscp=0; app.AckRequired=true;
end
function record = routeUpdate(destination,capability,hops,cost,path)
record=struct('Operation','UPDATE','NodeId',destination,'Capability',capability, ...
    'HopCount',hops,'Cost',cost,'Path',path);
end
