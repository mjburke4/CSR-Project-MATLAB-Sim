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
        function hopCustodyReleaseDoesNotScheduleSameTimePump(test)
            h=nwkHarness(); app=application(1,1,99);
            h.Layer.sendApplication(app); h.Clock.run(0);
            test.verifyEqual(h.Clock.PendingCount,0);
            h.Layer.releaseFromHop(app,'ack');
            test.verifyEqual(h.Layer.stats().PendingCustody,0);
            test.verifyEqual(h.Clock.PendingCount,0);
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
        function packetEnvelopeCannotDowngradeScenarioProfile(test)
            h=nwkHarness(struct(),1,true,'pairwise16-size-only');
            h.Layer.observe(2,struct());
            app=application(1,1,2); test.verifyEqual(app.EnvelopeProfile,'bare');
            test.verifyTrue(h.Layer.sendApplication(app)); h.Clock.run(0);
            sent=h.Data(); test.assertNumElements(sent,1);
            test.verifyEqual(sent.Options.EnvelopeProfile,'pairwise16-size-only');
            frame=csr.hop.Frames.data(sent.App,1,2,uint16(1),sent.Options);
            test.verifyEqual(frame.WirePayloadBytes,app.ApplicationPayloadBytes+37);
            controls=h.Controls(); test.assertNotEmpty(controls);
            test.verifyTrue(all(arrayfun(@(row)strcmp(row.Options.EnvelopeProfile, ...
                'pairwise16-size-only'),controls)));
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
        function routingBacklogPressureRestoresDirtyChanges(test)
            h=nwkHarness(struct('ControlQueueLimit',1));
            h.Layer.observe(2,struct()); h.Clock.run(0);
            controls=h.Controls(); first=controls(1);
            test.verifyEqual(first.Kind,'ROUTING');
            test.verifyEqual(h.Layer.stats().ControlQueueRejections,1);

            h.Layer.controlResult(first.Control,2,true,true,[]); h.Clock.run(0);
            h.Clock.run(8);
            controls=h.Controls(); test.assertGreaterThan(numel(controls),1);
            [~,records]=decodeRoutingRows(controls(end));
            operations=cellfun(@(record)record.Operation,records,'UniformOutput',false);
            test.verifyTrue(any(strcmp(operations,'UPDATE')));
            test.verifyEqual(h.Layer.stats().ControlQueueRejections,1);
        end
        function simultaneousActivationsUseIndependentForwardSnapshots(test)
            h=nwkHarness(); h.Layer.observe(2,struct()); h.Clock.run(0);
            records=cell(1,60);
            for index=1:60
                records{index}=routeUpdate(100+index,1,1,index,100+index);
            end
            h.DeliverRecords(2,50,records); h.Clock.run(0);
            before=numel(h.Controls());

            h.Layer.observe(3,struct()); h.Layer.observe(4,struct()); h.Clock.run(0);
            added=h.Controls(); added=added(before+1:end);
            to3=added(strcmp({added.Kind},'ROUTING') & ...
                arrayfun(@(row)isequal(row.Peers,3),added));
            to4=added(strcmp({added.Kind},'ROUTING') & ...
                arrayfun(@(row)isequal(row.Peers,4),added));
            [sections3,records3]=decodeRoutingRows(to3);
            [sections4,records4]=decodeRoutingRows(to4);

            test.verifyGreaterThan(numel(sections3),1);
            test.verifyEqual([sections3.Section],0:numel(sections3)-1);
            test.verifyEqual([sections4.Section],0:numel(sections4)-1);
            test.verifyEqual(unique([sections3.Sequence]),sections3(1).Sequence);
            test.verifyEqual(unique([sections4.Sequence]),sections4(1).Sequence);
            test.verifyNotEqual(sections3(1).Sequence,sections4(1).Sequence);
            test.verifyEqual(records3{1}.Operation,'INFO');
            test.verifyEqual(records3{end}.Operation,'FLUSH');
            test.verifyEqual(records4,records3);
        end
        function sameTimeRequestUsesProcessedChangesUntilClearEvent(test)
            h=nwkHarness(); h.Layer.observe(2,struct()); h.Clock.run(0);
            acknowledgeRows(h,h.Controls()); h.Clock.run(0);
            before=numel(h.Controls());
            h.DeliverRecords(2,50,{routeUpdate(99,1,1,10,99)});
            h.DeliverRecords(2,51,{struct('Operation','REQUEST')}); h.Clock.run(0);
            added=h.Controls(); added=added(before+1:end);
            snapshot=added(arrayfun(@isSingleSectionSnapshot,added));
            test.assertNumElements(snapshot,1);
            [~,records]=decodeRoutingRows(snapshot);
            test.verifyFalse(any(cellfun(@(record)isfield(record,'NodeId') && record.NodeId==99,records)));

            acknowledgeRows(h,snapshot); h.Clock.run(0); before=numel(h.Controls());
            h.DeliverRecords(2,52,{struct('Operation','REQUEST')}); h.Clock.run(0);
            added=h.Controls(); added=added(before+1:end);
            test.assertNumElements(added,1);
            [~,records]=decodeRoutingRows(added);
            test.verifyTrue(any(cellfun(@(record)isfield(record,'NodeId') && record.NodeId==99,records)));
        end
        function requestBeforeRoutesProcessExcludesPendingChanges(test)
            h=nwkHarness(); h.Layer.observe(2,struct()); h.Clock.run(0);
            acknowledgeRows(h,h.Controls()); h.Clock.run(0); before=numel(h.Controls());
            h.DeliverRecords(2,50,{struct('Operation','REQUEST')});
            h.DeliverRecords(2,51,{routeUpdate(99,1,1,10,99)}); h.Clock.run(0);
            added=h.Controls(); added=added(before+1:end);
            snapshot=added(arrayfun(@isSingleSectionSnapshot,added));
            test.assertNumElements(snapshot,1);
            [~,records]=decodeRoutingRows(snapshot);
            test.verifyFalse(any(cellfun(@(record)isfield(record,'NodeId') && record.NodeId==99,records)));
        end
        function repeatedRequestsWaitForEverySnapshotSectionAck(test)
            h=nwkHarness(); h.Layer.observe(2,struct()); h.Clock.run(0);
            acknowledgeRows(h,h.Controls()); h.Clock.run(0);
            records=cell(1,60);
            for index=1:60
                records{index}=routeUpdate(100+index,1,1,index,100+index);
            end
            h.DeliverRecords(2,50,records); h.Clock.run(0); before=numel(h.Controls());
            h.DeliverRecords(2,51,{struct('Operation','REQUEST')}); h.Clock.run(0);
            snapshot=h.Controls(); snapshot=snapshot(before+1:end);
            test.assertGreaterThan(numel(snapshot),1); count=numel(h.Controls());
            h.DeliverRecords(2,52,{struct('Operation','REQUEST')}); h.Clock.run(0);
            test.verifyNumElements(h.Controls(),count);
            acknowledgeRows(h,snapshot(1:end-1)); h.Clock.run(0);
            % Duplicate callback and a partial final ACK cannot finish a stream.
            acknowledgeRows(h,snapshot(1));
            last=snapshot(end); h.Layer.controlResult(last.Control,2,true,false,[]);
            h.DeliverRecords(2,53,{struct('Operation','REQUEST')}); h.Clock.run(0);
            test.verifyNumElements(h.Controls(),count);
            acknowledgeRows(h,last); h.Clock.run(0);
            h.DeliverRecords(2,54,{struct('Operation','REQUEST')}); h.Clock.run(0);
            test.verifyNumElements(h.Controls(),count+numel(snapshot));
        end
        function outboundWatchdogAllowsRestartAndIgnoresOldSectionAck(test)
            h=nwkHarness(); h.Layer.observe(2,struct()); h.Clock.run(0);
            acknowledgeRows(h,h.Controls()); h.Clock.run(0); h.Clock.run(1);
            before=numel(h.Controls());
            h.DeliverRecords(2,50,{struct('Operation','REQUEST')}); h.Clock.run(1);
            old=h.Controls(); old=old(before+1:end); test.assertNumElements(old,1);
            h.Clock.run(20); count=numel(h.Controls());
            h.DeliverRecords(2,51,{struct('Operation','REQUEST')}); h.Clock.run(20);
            test.verifyNumElements(h.Controls(),count);
            test.verifyEqual(h.Layer.stats().SnapshotTimeouts,0);
            h.Clock.run(21); test.verifyEqual(h.Layer.stats().SnapshotTimeouts,1);
            h.DeliverRecords(2,52,{struct('Operation','REQUEST')}); h.Clock.run(21);
            test.verifyNumElements(h.Controls(),count+1);
            acknowledgeRows(h,old); h.Clock.run(21);
            h.DeliverRecords(2,53,{struct('Operation','REQUEST')}); h.Clock.run(21);
            test.verifyNumElements(h.Controls(),count+1);
        end
        function routeRequestRetryPreservesUnrelatedReassembly(test)
            h=nwkHarness(struct('RouteRequestSeconds',1, ...
                'Neighbor',struct('AdmissionEnabled',true)));
            h.AdmitDiscovery(2,true);
            test.verifyEqual(h.Layer.stats().RouteRequests,1);
            records=cell(1,60);
            for index=1:60
                records{index}=routeUpdate(100+index,1,1,index,100+index);
            end
            sections=csr.nwk.RoutingCodec.sections( ...
                csr.nwk.RoutingCodec.encodeRecords(records),77);
            test.assertNumElements(sections,2);

            h.Layer.receiveControl(struct('Type','ROUTING', ...
                'Payload',struct('Bytes',sections{1})),2);
            h.Clock.run(1);
            test.verifyEqual(h.Layer.stats().RouteRequests,2);
            h.Layer.receiveControl(struct('Type','ROUTING', ...
                'Payload',struct('Bytes',sections{2})),2);

            test.verifyTrue(h.Layer.routeAvailable(application(99,1,160)));
        end
        function discoveryCompletionRefreshesLinksAndRequestsSnapshots(test)
            h=nwkHarness();
            h.Layer.observe(3,struct('PathlossDb',130));
            h.Layer.observe(2,struct('PathlossDb',100)); h.Clock.run(0);
            before=numel(h.Controls());

            test.verifyTrue(h.Layer.startDiscovery(0,0.25)); h.Clock.run(0.25);

            stats=h.Layer.stats(); test.verifyEqual(stats.DiscoveryCompletions,1);
            test.verifyEqual(stats.RouteRequests,2);
            routes=h.Layer.routesSnapshot();
            direct2=routes([routes.DestinationId]==2);
            direct3=routes([routes.DestinationId]==3);
            test.verifyEqual(direct2.Cost,29);
            test.verifyEqual(direct3.Cost,1393);
            added=h.Controls(); added=added(before+1:end);
            requests=added(strcmp({added.Kind},'ROUTING') & ...
                arrayfun(@isRouteRequest,added));
            test.verifyEqual([requests.Peers],[2 3]);
        end
        function remoteActiveDiscoveryCheckAloneStartsRouteRequest(test)
            inactive=nwkHarness(struct('Neighbor',struct('AdmissionEnabled',true)));
            inactive.AdmitDiscovery(2,false);
            test.verifyEqual(inactive.Layer.stats().RouteRequests,0);
            test.verifyFalse(any(arrayfun(@isRouteRequest,inactive.Controls())));

            active=nwkHarness(struct('Neighbor',struct('AdmissionEnabled',true)));
            active.AdmitDiscovery(2,true);
            test.verifyEqual(active.Layer.stats().RouteRequests,1);
            controls=active.Controls(); requests=controls(arrayfun(@isRouteRequest,controls));
            test.assertNumElements(requests,1);
            test.verifyEqual(requests.Peers,2);
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
        function routingPrevalidationIsPureAndRejectsMalformedRecords(test)
            h=nwkHarness();
            bytes=csr.nwk.RoutingCodec.sections( ...
                csr.nwk.RoutingCodec.encodeRecords({struct('Operation','FLUSH')}),12);
            valid=struct('Type','ROUTING','Payload',struct('Bytes',bytes{1}));
            malformed=valid; malformed.Payload.Bytes=uint8([0 0 0 12 0 1 255]);
            truncated=valid; truncated.Payload.Bytes=uint8([0 0 0 12 0]);

            test.verifyTrue(h.Layer.validateControl(valid,2));
            test.verifyFalse(h.Layer.validateControl(malformed,2));
            test.verifyFalse(h.Layer.validateControl(truncated,2));
            test.verifyFalse(h.Layer.validateControl( ...
                struct('Type','UNKNOWN','Payload',struct()),2));
            test.verifyFalse(h.Layer.routeAvailable(application(1,1,99)));
        end
    end
end

function h = nwkHarness(overrides,capability,transitEnabled,envelopeProfile)
if nargin<1, overrides=struct(); end
if nargin<2, capability=1; end
if nargin<3, transitEnabled=true; end
if nargin<4, envelopeProfile='bare'; end
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
radio=struct('RateKeyKbps',8,'TxPowerDbm',30,'Preamble','long','EnvelopeProfile',envelopeProfile);
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
    'BlockData',@blockData,'BlockControls',@blockControls,'DeliverRecords',@deliverRecords, ...
    'Admit',@admit,'AdmitDiscovery',@admitDiscovery);
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
        completeKeys(peer);
        layer.receiveControl(struct('Type','NEIGHBOR_CHECK', ...
            'Payload',struct('Subtype','message','Sequence',uint32(0),'Active',true)),peer);
        scheduler.run(scheduler.Now);
    end
    function admitDiscovery(peer,remoteActive)
        completeKeys(peer);
        layer.receiveControl(struct('Type','NEIGHBOR_CHECK', ...
            'Payload',struct('Subtype','discovery','Sequence',uint32(1), ...
            'Active',logical(remoteActive))),peer);
        scheduler.run(scheduler.Now);
    end
    function completeKeys(peer)
        layer.receiveControl(struct('Type','KEY_UPDATE','Payload',struct()),peer); scheduler.run(scheduler.Now);
        keys=controls(strcmp({controls.Kind},'KEY_UPDATE')); row=keys(end);
        layer.controlResult(row.Control,peer,true,true,[]); scheduler.run(scheduler.Now);
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
function [sections,records] = decodeRoutingRows(rows)
sections=repmat(struct('Sequence',0,'Section',0,'TotalSections',0,'Body',uint8([])),0,1);
for index=1:numel(rows)
    sections(end+1,1)=csr.nwk.RoutingCodec.decodeSection(rows(index).Control.Payload.Bytes); %#ok<AGROW>
end
records=csr.nwk.RoutingCodec.decodeRecords([sections.Body]);
end
function acknowledgeRows(h,rows)
for index=1:numel(rows)
    row=rows(index);
    for peer=row.Peers
        h.Layer.controlResult(row.Control,peer,true,peer==row.Peers(end),[]);
    end
end
end
function yes = isSingleSectionSnapshot(row)
yes=false;
if ~strcmp(row.Kind,'ROUTING'), return; end
section=csr.nwk.RoutingCodec.decodeSection(row.Control.Payload.Bytes);
if section.TotalSections~=1, return; end
records=csr.nwk.RoutingCodec.decodeRecords(section.Body);
yes=any(cellfun(@(record)strcmp(record.Operation,'FLUSH'),records));
end
function yes = isRouteRequest(row)
yes=false;
if ~strcmp(row.Kind,'ROUTING'), return; end
try
    section=csr.nwk.RoutingCodec.decodeSection(row.Control.Payload.Bytes);
    if section.Section~=0 || section.TotalSections~=1, return; end
    records=csr.nwk.RoutingCodec.decodeRecords(section.Body);
    yes=numel(records)==1 && strcmp(records{1}.Operation,'REQUEST');
catch exception
    if ~strcmp(exception.identifier,'csr:nwk:MalformedRouting'), rethrow(exception); end
end
end
