classdef TestApplicationObservations < matlab.unittest.TestCase
    % Read-only br_app and MAC population projections from 486d9e01 NWK state.
    % Fake transport isolates observation contracts; this is not a PHY run.
    methods (Test)
        function emptyStateAndPassiveRadioDoNotInventTopology(test)
            h=harness(); before=h.Layer.applicationState(9);
            test.verifyFalse(before.DiscoveryActive);
            test.verifyFalse(before.TopologyKnown);
            test.verifyEmpty(before.GatewayId);
            test.verifyEmpty(before.DestinationCandidates);
            test.verifyEqual(before.ActiveNodeCount,1);
            test.verifyEqual(before.NsdpCount,0);
            test.verifyEqual(before.NsdpLimit,16);
            h.Layer.observeRadio(2,struct('Success',true));
            test.verifyEqual(h.Layer.applicationState(9),before);
        end

        function unqualifiedPersistentPeersAreSortedAndDoNotCountAsHeard(test)
            h=harness(); app=application(1,2);
            test.verifyFalse(h.Layer.acceptFromNeighbor(app,9));
            test.verifyFalse(h.Layer.acceptFromNeighbor(app,3));
            state=h.Layer.applicationState(9);
            test.verifyTrue(state.TopologyKnown);
            test.verifyEqual(state.DestinationCandidates,[3 9]);
            test.verifyEqual(state.ActiveNodeCount,1);
            test.verifyEmpty(state.GatewayId);
        end

        function inactiveQualifiedPeerCountsWithoutAdmittingIt(test)
            h=harness(); h.Layer.observe(9,struct());
            state=h.Layer.applicationState(9);
            test.verifyTrue(state.TopologyKnown);
            test.verifyEqual(state.DestinationCandidates,9);
            test.verifyEqual(state.ActiveNodeCount,2);
            test.verifyEmpty(h.Layer.routesSnapshot());
            test.verifyFalse(h.Layer.acceptFromNeighbor(application(1,9),9));
        end

        function rawRoutePopulationKeepsInsertionOrderAndInvalidCandidates(test)
            routes=csr.nwk.Routes(1,1);
            routes.setNeighbor(9,false,1,0);
            routes.setNeighbor(3,false,1,0);
            routes.apply(9,1,{update(7,1,1,7,7)},1,0);
            routes.apply(3,1,{update(7,1,1,7,7)},1,0);
            routes.apply(9,2,{struct('Operation','DELETE','NodeId',8)},1,1);
            test.verifyEmpty(routes.select(7));
            before=routes.Candidates;
            test.verifyEqual(routes.applicationDestinationCandidates(),[9 3 7 8]);
            test.verifyEqual(routes.Candidates,before);
            test.verifyEmpty(routes.select(7));
        end

        function gatewayObservationIsSelectedAndDoesNotCacheForTheCaller(test)
            routes=csr.nwk.Routes(1,1);
            routes.setNeighbor(9,true,1,0);
            routes.apply(9,1,{update(9,2,0,0,[])},1,0);
            test.verifyEqual(routes.applicationGateway(),9);
            routes.setNeighbor(9,false,1,1);
            test.verifyEmpty(routes.applicationGateway());
            test.verifyEqual(routes.applicationDestinationCandidates(),9);
        end

        function onlyActiveDiscoveryBlocksApplicationGeneration(test)
            h=harness(); test.verifyTrue(h.Layer.startDiscovery(2,5));
            test.verifyFalse(h.Layer.applicationState().DiscoveryActive);
            h.Clock.run(2);
            test.verifyTrue(h.Layer.applicationState().DiscoveryActive);
            h.Clock.run(7);
            test.verifyFalse(h.Layer.applicationState().DiscoveryActive);
        end

        function nsdpIncludesHopCustodyWhileNwkQueueExcludesIt(test)
            h=harness(false); h.Layer.observe(2,struct());
            a=application(1,2); b=application(2,99);
            test.verifyTrue(h.Layer.sendApplication(a));
            test.verifyTrue(h.Layer.sendApplication(b));
            before=h.Layer.applicationState(2);
            test.verifyEqual(before.NsdpCount,1);
            test.verifyEqual(before.NwkQueueSize,2);
            h.Clock.run(0);
            after=h.Layer.applicationState(2);
            test.verifyEqual(after.NsdpCount,1);
            test.verifyEqual(after.NwkQueueSize,1);
            test.verifyEqual(after.PendingCustody,2);
            test.verifyEqual(h.Layer.applicationState(99).NsdpCount,1);
            h.Layer.releaseFromHop(a,'ack');
            test.verifyEqual(h.Layer.applicationState(2).NsdpCount,0);
            test.verifyEqual(h.Layer.applicationState(99).NsdpCount,1);
        end

        function populationSurvivesFreshnessExpiryWithoutUsingActiveFlag(test)
            h=harness(false,true); h.Layer.start();
            h.Layer.observe(2,struct());
            test.verifyEqual(h.Layer.applicationState().ActiveNodeCount,2);
            h.Clock.run(3);
            peers=h.Layer.neighborsSnapshot();
            test.verifyTrue(peers.Stale); test.verifyFalse(peers.Active);
            state=h.Layer.applicationState();
            test.verifyEqual(state.ActiveNodeCount,2);
            test.verifyTrue(state.TopologyKnown);
            test.verifyEqual(state.DestinationCandidates,2);
        end
    end
end

function h = harness(admission,freshness)
if nargin<1, admission=true; end
if nargin<2, freshness=false; end
config=csr.scenario.routedNetwork('autonomous');
config.Nwk.StartupMode='manual'; config.Nwk.AdaptiveLinkControl=false;
config.Nwk.Neighbor.AdmissionEnabled=admission;
config.Nwk.Neighbor.FreshnessEnabled=freshness;
config.Nwk.Neighbor.FreshnessTimeoutSeconds=2;
config.Nwk.Neighbor.FreshnessPeriodSeconds=1;
scheduler=csr.sim.EventScheduler();
callbacks=struct('CanSendData',@(~)true,'SendData',@(~,~,~)true, ...
    'CanSendControl',@(~)true,'SendControl',@(~,~,~)true);
layer=csr.nwk.Layer(1,scheduler,[],config,callbacks);
h=struct('Clock',scheduler,'Layer',layer);
end

function app = application(id,destination)
app=struct('Id',uint64(id),'SourceId',1,'DestinationId',destination, ...
    'GeneratedSeconds',0,'ApplicationPayloadBytes',185,'Dscp',0);
end

function record = update(node,capability,hops,cost,path)
record=struct('Operation','UPDATE','NodeId',node,'Capability',capability, ...
    'HopCount',hops,'Cost',cost,'Path',path);
end
