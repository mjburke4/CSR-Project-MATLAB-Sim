classdef TestNwkScenarios < matlab.unittest.TestCase
    % Autonomous network gates; successful linting is not MATLAB execution.
    methods (Test)
        function autonomousAdmissionBuildsAndUsesTheTwoHopRoute(test)
            config = csr.scenario.routedNetwork('autonomous');
            TestNwkScenarios.verifyNoInstalledPath(test,config);
            result = csr.runScenario(config);
            TestNwkScenarios.verifyDelivered(test,result,true);
            routes = result.Routes;
            selected = routes(routes.NodeId == 3 & routes.DestinationId == 1,:);
            test.assertEqual(height(selected),1);
            test.verifyEqual(selected.NextHop,2);
            test.verifyEqual(selected.HopCount,2);
            test.verifyEqual(selected.Capability,2);
            neighbors = result.Neighbors;
            test.verifyTrue(any(neighbors.NodeId == 3 & neighbors.PeerId == 2 & neighbors.Active));
            test.verifyFalse(any(neighbors.NodeId == 3 & neighbors.PeerId == 1 & neighbors.Active), ...
                'The physical closure must prevent a direct endpoint-to-gateway neighbor.');
            trace = result.ProtocolTrace;
            test.verifyTrue(any(strcmp(trace.Event,'neighbor_active')));
            controls = trace(strcmp(trace.FrameKind,'CONTROL'),:);
            for kind = {'DISCOVER','KEY_REQUEST','KEY_UPDATE','NEIGHBOR_CHECK','ROUTING'}
                test.verifyTrue(any(strcmp(controls.ControlType,kind{1})),kind{1});
            end
            TestNwkScenarios.verifyRelayPath(test,result);
        end

        function earlyApplicationsKeepCustodyUntilDiscoveryConverges(test)
            config = csr.scenario.routedNetwork('no_route_custody');
            TestNwkScenarios.verifyNoInstalledPath(test,config);
            result = csr.runScenario(config);
            TestNwkScenarios.verifyDelivered(test,result,true);
            test.verifyGreaterThan(result.Statistics.MaxNetworkQueueDepth,0);
            trace = result.ProtocolTrace;
            generated = trace(strcmp(trace.Event,'app_generate'),:);
            admitted = trace(strcmp(trace.Event,'neighbor_active'),:);
            received = trace(strcmp(trace.Event,'app_receive'),:);
            test.assertGreaterThan(height(admitted),0);
            test.verifyLessThan(min(generated.TimeSeconds),min(admitted.TimeSeconds));
            test.verifyGreaterThan(min(received.TimeSeconds),min(admitted.TimeSeconds));
            TestNwkScenarios.verifyRelayPath(test,result);
        end

        function queuingDataDoesNotStartDiscoveryOrFabricateARoute(test)
            config = csr.scenario.routedNetwork('no_route_custody');
            config.Traffic.PacketCount = 1;
            config.DurationSeconds = 1;
            result = csr.runScenario(config);
            test.verifyEqual(result.Statistics.Generated,1);
            test.verifyEqual(result.Statistics.Received,0);
            test.verifyEqual(result.Statistics.Dropped,0);
            test.verifyEqual(result.Statistics.Pending,1);
            test.verifyEqual(result.Statistics.DataTransmissions,0);
            test.verifyEqual(sum(result.NodeNwkStatistics.DiscoveryStarts),0);
            test.verifyEqual(sum(result.NodeNwkStatistics.WaitingForRoute),1);
            test.verifyEqual(sum(result.NodeNwkStatistics.PendingCustody),1);
            test.verifyFalse(any(result.Routes.NodeId == 3 & result.Routes.DestinationId == 1));
        end

        function lostRoutingControlRetriesAndReleasesReliableOwners(test)
            config = csr.scenario.routedNetwork('control_loss');
            test.verifyTrue(any(strcmp({config.Faults.ControlType},'ROUTING')));
            result = csr.runScenario(config);
            TestNwkScenarios.verifyDelivered(test,result,true);
            test.verifyGreaterThan(result.Statistics.FaultDrops,0);
            test.verifyGreaterThan(sum(result.NodeHopStatistics.ControlRetransmissions),0);
            trace = result.ProtocolTrace;
            test.verifyTrue(any(strcmp(trace.Event,'fault_drop')));
            test.verifyTrue(any(strcmp(trace.Event,'hop_retry') & strcmp(trace.ControlType,'ROUTING')));
            test.verifyGreaterThan(sum(result.NodeHopStatistics.ControlCompleted),0);
            test.verifyEqual(sum(result.NodeHopStatistics.ControlUnexpectedDack),0);
            TestNwkScenarios.verifyRelayPath(test,result);
        end

        function routeRecoveryRetainsApplicationsAcrossTheRfBlackout(test)
            config = csr.scenario.routedNetwork('route_recovery');
            test.assertGreaterThan(numel(config.LinkEvents),1);
            test.assertGreaterThan(numel(config.DiscoveryEvents),0);
            result = csr.runScenario(config);
            % Monitoring continues through the stop time; a new health-control
            % transaction may be pending after all DATA custody has drained.
            TestNwkScenarios.verifyDelivered(test,result,false);
            trace = result.ProtocolTrace;
            disabled = trace(strcmp(trace.Event,'link_disable') & trace.NodeId == 2,:);
            restored = trace(strcmp(trace.Event,'link_enable') & trace.NodeId == 2,:);
            test.assertEqual(height(disabled),1);
            test.assertEqual(height(restored),1);
            test.verifyLessThan(disabled.TimeSeconds,restored.TimeSeconds);
            test.verifyTrue(any(strcmp(trace.Event,'link_drop')));
            test.verifyGreaterThan(sum(result.NodeNwkStatistics.NeighborDeactivations),0);
            test.verifyGreaterThanOrEqual(result.NodeNwkStatistics.DiscoveryStarts( ...
                result.NodeNwkStatistics.NodeId == 1),2);
            received = trace(strcmp(trace.Event,'app_receive'),:);
            test.verifyTrue(all(received.TimeSeconds > restored.TimeSeconds));
            test.verifyGreaterThan(result.Statistics.MaxNetworkQueueDepth,0);
            TestNwkScenarios.verifyRelayPath(test,result);
        end

        function gatewayPolicyUsesTheAdvertisedGatewayCapability(test)
            config = csr.scenario.routedNetwork('gateway');
            test.verifyTrue(config.Nwk.SendOnlyToGateway);
            test.verifyEqual(config.Traffic.DestinationId,2);
            result = csr.runScenario(config);
            TestNwkScenarios.verifyDelivered(test,result,true);
            received = result.ProtocolTrace(strcmp(result.ProtocolTrace.Event,'app_receive'),:);
            test.verifyTrue(all(received.NodeId == 1));
            test.verifyEqual(result.NodeStatistics.Received(result.NodeStatistics.Id == 2),0);
            TestNwkScenarios.verifyRelayPath(test,result);
        end

        function explicitLeafPolicyDiscardsTransitAfterProtocolReceipt(test)
            config = csr.scenario.routedNetwork('leaf_no_transit');
            test.verifyFalse(config.Nodes([config.Nodes.Id] == 2).TransitForwardingEnabled);
            result = csr.runScenario(config);
            TestNwkScenarios.verifyAccounting(test,result);
            stats = result.Statistics;
            test.verifyEqual(stats.Generated,sum([config.Traffic.PacketCount]));
            test.verifyEqual(stats.Received,0);
            test.verifyGreaterThan(stats.Dropped,0);
            test.verifyEqual(stats.Pending,0);
            test.verifyEqual(sum(result.NodeStatistics.PendingCustody),0);
            test.verifyEqual(sum(result.NodeHopStatistics.PendingData),0);
            test.verifyEqual(sum(result.NodeHopStatistics.DackHoldCount),0);
            test.verifyEqual(sum(result.NodeHopStatistics.ResendQueueDepth- ...
                result.NodeHopStatistics.ControlPending),0);
            test.assertTrue(isfield(stats.DropReasons,'transit_disabled'));
            test.verifyGreaterThan(stats.DropReasons.transit_disabled,0);
            test.verifyTrue(any(result.Neighbors.NodeId == 3 & ...
                result.Neighbors.PeerId == 2 & result.Neighbors.Active), ...
                'The scenario must refuse transit through an admitted leaf, not an absent link.');
            trace = result.ProtocolTrace;
            policyDrops = strcmp(trace.Event,'network_policy_drop') & ...
                trace.NodeId == 2 & strcmp(trace.Reason,'transit_disabled');
            test.verifyTrue(any(policyDrops));
            test.verifyGreaterThan(result.Statistics.AcksReceived,0, ...
                'The receiver acknowledges protocol receipt before its transit-policy discard.');
            data = strcmp(trace.Event,'hop_admit') & strcmp(trace.FrameKind,'DATA');
            test.verifyFalse(any(data & trace.NodeId == 2 & trace.PeerId == 1));
        end

        function highRatePayloadsTraverseTheAutonomousReliabilityStack(test)
            names = {'high_rate_500','high_rate_1000'};
            rates = [500 1000];
            for k = 1:numel(names)
                config = csr.scenario.routedNetwork(names{k});
                result = csr.runScenario(config);
                TestNwkScenarios.verifyDelivered(test,result,true);
                test.verifyEqual(result.Config.Traffic.RateKeyKbps,rates(k));
                phy = result.PhyTrace;
                test.verifyTrue(any(phy.Success & phy.RateKeyKbps == rates(k)),names{k});
                test.verifyGreaterThan(result.Statistics.AcksReceived,0);
                TestNwkScenarios.verifyRelayPath(test,result);
            end
        end

        function fixedSeedReproducesRoutingAndCustodyWithoutGlobalRngChanges(test)
            config = csr.scenario.routedNetwork('autonomous');
            before = rng;
            first = csr.runScenario(config);
            second = csr.runScenario(config);
            test.verifyEqual(first.Statistics,second.Statistics);
            test.verifyEqual(first.ProtocolTrace,second.ProtocolTrace);
            test.verifyEqual(first.PhyTrace,second.PhyTrace);
            test.verifyEqual(first.Routes,second.Routes);
            test.verifyEqual(first.Neighbors,second.Neighbors);
            test.verifyEqual(first.NodeNwkStatistics,second.NodeNwkStatistics);
            test.verifyEqual(first.NodeHopStatistics,second.NodeHopStatistics);
            test.verifyEqual(rng,before);
        end

        function exportsPreserveRuntimeRoutingAndAccountingEvidence(test)
            result = csr.runScenario(csr.scenario.routedNetwork('autonomous'));
            output = tempname;
            mkdir(output);
            cleanup = onCleanup(@() rmdir(output,'s')); %#ok<NASGU>
            csr.analysis.exportResults(result,output);
            for name = {'results.mat','summary.json','trace.csv','protocol_trace.csv', ...
                    'phy_trace.csv','nodes.csv','hop_nodes.csv','mac_nodes.csv', ...
                    'nwk_nodes.csv','routes.csv','neighbors.csv'}
                test.verifyTrue(isfile(fullfile(output,name{1})),name{1});
            end
            summary = jsondecode(fileread(fullfile(output,'summary.json')));
            test.verifyEqual(summary.Metadata.Runtime,'MATLAB');
            test.verifyEqual(summary.Metadata.Version,version);
            test.verifyEqual(summary.Metadata.Release,version('-release'));
            test.verifyEqual(summary.Metadata.SourceCommit, ...
                '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b');
            test.verifyEqual(summary.Metadata.Backend,'portable');
            test.verifyEqual(summary.Metadata.ChannelModel,'csr-phy');
            test.verifyEqual(summary.Statistics.Generated,result.Statistics.Generated);
            test.verifyEqual(summary.Statistics.Received,result.Statistics.Received);
            routes = readtable(fullfile(output,'routes.csv'));
            test.verifyEqual(height(routes),height(result.Routes));
            test.verifyEqual(routes.NextHop,result.Routes.NextHop);
            nodes = readtable(fullfile(output,'nwk_nodes.csv'));
            test.verifyEqual(sum(nodes.PendingCustody),sum(result.NodeNwkStatistics.PendingCustody));
        end
    end

    methods (Static, Access = private)
        function verifyNoInstalledPath(test,config)
            test.verifyEqual(config.Stack,'network');
            if isfield(config.Traffic,'Path')
                test.verifyTrue(all(arrayfun(@(flow) isempty(flow.Path),config.Traffic)), ...
                    'Autonomous fixtures must not install a forwarding path.');
            end
        end

        function verifyDelivered(test,result,quiescentControls)
            TestNwkScenarios.verifyAccounting(test,result);
            stats = result.Statistics;
            test.verifyEqual(stats.Generated,sum([result.Config.Traffic.PacketCount]));
            test.verifyGreaterThan(stats.Generated,0);
            test.verifyEqual(stats.Received,stats.Generated);
            test.verifyEqual(stats.Dropped,0);
            test.verifyEqual(stats.Pending,0);
            test.verifyEqual(stats.ApplicationBytesReceived, ...
                sum([result.Config.Traffic.PacketCount] .* [result.Config.Traffic.ApplicationPayloadBytes]));
            test.verifyEqual(sum(result.NodeStatistics.PendingCustody),0);
            test.verifyEqual(sum(result.NodeStatistics.WaitingForHop),0);
            test.verifyEqual(sum(result.NodeNwkStatistics.WaitingForRoute),0);
            hop = result.NodeHopStatistics;
            test.verifyEqual(sum(hop.PendingData),0);
            test.verifyEqual(sum(hop.DackHoldCount),0);
            test.verifyEqual(sum(hop.ResendQueueDepth-hop.ControlPending),0);
            if quiescentControls
                test.verifyEqual(sum(hop.ControlPending),0);
                test.verifyEqual(sum(hop.ControlPendingTargets),0);
                test.verifyEqual(sum(result.NodeNwkStatistics.PendingControlMessages),0);
                test.verifyEqual(stats.PhysicalPending,0);
            end
            received = result.ProtocolTrace(strcmp(result.ProtocolTrace.Event,'app_receive'),:);
            test.verifyEqual(height(received),stats.Received);
            test.verifyEqual(numel(unique(received.PacketId)),height(received));
        end

        function verifyAccounting(test,result)
            stats = result.Statistics;
            test.verifyEqual(stats.Generated,stats.Received+stats.Dropped+stats.Pending);
            test.verifyGreaterThanOrEqual(stats.Pending,0);
            test.verifyEqual(stats.PhysicalAttempts, ...
                stats.PhysicalReceived+stats.PhysicalDropped+stats.PhysicalPending);
            test.verifyGreaterThanOrEqual(stats.PhysicalPending,0);
            test.verifyEqual(sum(result.NodeStatistics.Generated),stats.Generated);
            test.verifyEqual(sum(result.NodeStatistics.Received),stats.Received);
            test.verifyEqual(sum(result.NodeStatistics.Dropped),stats.Dropped);
            test.verifyGreaterThan(stats.ControlTransmissions,0);
            test.verifyEqual(stats.OmittedTraceRecords,0, ...
                'Scenario traces must retain all structural acceptance evidence.');
            test.verifyEqual(stats.OmittedPhyTraceRecords,0);
            hop = result.NodeHopStatistics;
            test.verifyGreaterThanOrEqual(hop.ControlPendingTargets,hop.ControlPending);
            test.verifyGreaterThanOrEqual(hop.ResendQueueDepth,hop.ControlPending);
            test.verifyLessThanOrEqual(result.NodeNwkStatistics.PendingControlMessages, ...
                repmat(result.Config.Nwk.ControlQueueLimit,height(result.NodeNwkStatistics),1));
            test.verifyEqual(sum(result.NodeNwkStatistics.ControlQueueRejections),0, ...
                'Acceptance fixtures must not depend on control/backlog overflow recovery.');
            TestNwkScenarios.verifyAdmittedDataSubmissions(test,result.ProtocolTrace);
            tx = result.ProtocolTrace(strcmp(result.ProtocolTrace.Event,'tx_start'),:);
            test.verifyEqual(height(tx),stats.PhysicalTransmissions);
            test.verifyEqual(numel(unique(tx.PacketId)),height(tx));
            test.verifyTrue(all(tx.PacketId > 0));
        end

        function verifyAdmittedDataSubmissions(test,trace)
            % Trace row order preserves same-time transitions. A peer that was
            % admitted earlier but has since failed must not accept new DATA.
            active = containers.Map('KeyType','char','ValueType','logical');
            for k = 1:height(trace)
                event = trace.Event{k};
                if ~any(strcmp(event,{'neighbor_active','neighbor_inactive','hop_admit'}))
                    continue
                end
                key = sprintf('%.0f:%.0f',trace.NodeId(k),trace.PeerId(k));
                if strcmp(event,'neighbor_active')
                    active(key) = true;
                elseif strcmp(event,'neighbor_inactive')
                    active(key) = false;
                elseif strcmp(trace.FrameKind{k},'DATA')
                    test.verifyTrue(isKey(active,key) && active(key), ...
                        sprintf('DATA submitted to an inactive peer at trace row %d.',k));
                end
            end
        end

        function verifyRelayPath(test,result)
            trace = result.ProtocolTrace;
            received = trace(strcmp(trace.Event,'app_receive'),:);
            test.assertGreaterThan(height(received),0);
            test.verifyTrue(all(received.NodeId == 1 & received.PeerId == 2));
            test.verifyTrue(all(received.HopCount == 2));
            relay = trace(strcmp(trace.Event,'relay_accept') & trace.NodeId == 2,:);
            test.verifyTrue(all(ismember(received.PacketId,relay.PacketId)));
            test.verifyGreaterThanOrEqual(result.Statistics.RelayAccepted,result.Statistics.Received);
            hops = trace(strcmp(trace.Event,'hop_receive') & strcmp(trace.FrameKind,'DATA'),:);
            test.verifyFalse(any(hops.NodeId == 1 & hops.PeerId == 3), ...
                'Direct overhearing must not substitute for the relay link.');
        end
    end
end
