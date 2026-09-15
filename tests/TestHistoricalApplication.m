classdef TestHistoricalApplication < matlab.unittest.TestCase
    methods (Test)
        function orderedGatesPartitionAttemptsAndCacheBeforeNsdp(test)
            generator = csr.sim.ApplicationGenerator(1,test.flow(),true,0);
            state = test.state(); state.DiscoveryActive = true;
            state.TopologyKnown = false; state.GatewayId = []; state.NsdpCount = 16;
            [accepted,~,row] = generator.attempt(0,@(~)state,@neverDraw);
            test.verifyFalse(accepted); test.verifyEqual(row.Reason,'discovery_active');
            state.DiscoveryActive = false;
            [~,~,row] = generator.attempt(1,@(~)state,@neverDraw);
            test.verifyEqual(row.Reason,'topology_unknown');
            state.TopologyKnown = true;
            [~,~,row] = generator.attempt(2,@(~)state,@neverDraw);
            test.verifyEqual(row.Reason,'gateway_route_unknown');
            state.GatewayId = 7;
            [accepted,destination,row] = generator.attempt(3,@(~)state,@neverDraw);
            test.verifyFalse(accepted); test.verifyEqual(destination,7);
            test.verifyEqual(row.Reason,'nsdp_full'); test.verifyTrue(row.GatewayCached);
            state.GatewayId = []; state.NsdpCount = 15;
            [accepted,destination,row] = generator.attempt(4,@(~)state,@neverDraw);
            test.verifyTrue(accepted); test.verifyEqual(destination,7);
            test.verifyFalse(row.RouteCheckPerformed);
            s = generator.Statistics;
            test.verifyEqual([s.Attempts,s.Admitted,s.BlockedDiscovery,s.BlockedTopology, ...
                s.BlockedGatewayRoute,s.BlockedDestination,s.BlockedNsdp],[5,1,1,1,1,0,1]);
            test.verifyEqual([s.FirstAdmittedSeconds,s.LastAdmittedSeconds],[4,4]);
        end

        function gatewayCacheDoesNotBypassLaterDiscovery(test)
            generator = csr.sim.ApplicationGenerator(1,test.flow(),true,0);
            state = test.state(); state.GatewayId = 7;
            generator.attempt(0,@(~)state,@neverDraw);
            state.DiscoveryActive = true; state.GatewayId = [];
            [accepted,destination,row] = generator.attempt(1,@(~)state,@neverDraw);
            test.verifyFalse(accepted); test.verifyEqual(destination,7);
            test.verifyEqual(row.Reason,'discovery_active'); test.verifyTrue(row.GatewayCached);
        end

        function admittedLimitCountsPacketsRatherThanBlockedInterrupts(test)
            generator = csr.sim.ApplicationGenerator(1,test.flow(),true,1);
            state = test.state(); state.GatewayId = [];
            generator.attempt(0,@(~)state,@neverDraw);
            test.verifyTrue(generator.canAttempt());
            state.GatewayId = 1;
            generator.attempt(1,@(~)state,@neverDraw);
            test.verifyFalse(generator.canAttempt());
            test.verifyError(@()generator.attempt(2,@(~)state,@neverDraw),'csr:sim:ApplicationLimit');
            test.verifyEqual(generator.Statistics.Attempts,2);
        end

        function dynamicGatewaySamplesLivePopulationWithoutCaching(test)
            flow = test.flow(); flow.SourceId = 1; flow.DestinationId = 2;
            flow.DestinationMode = 'random_route_or_neighbor';
            generator = csr.sim.ApplicationGenerator(1,flow,true,0);
            state = test.state(); state.DestinationCandidates = [7,3,5];
            [accepted,destination] = generator.attempt(0,@(~)state,@()0);
            test.verifyTrue(accepted); test.verifyEqual(destination,7);
            [~,destination] = generator.attempt(1,@(~)state,@()0.5);
            test.verifyEqual(destination,3);
            state.DestinationCandidates = 9;
            [~,destination] = generator.attempt(2,@(~)state,@()0.99);
            test.verifyEqual(destination,9); test.verifyFalse(generator.Statistics.GatewayCached);
        end

        function dynamicEmptyPopulationIsDistinctFromUnknownTopology(test)
            flow = test.flow(); flow.DestinationMode = 'random_route_or_neighbor';
            generator = csr.sim.ApplicationGenerator(1,flow,true,0);
            state = test.state(); state.DestinationCandidates = [];
            [accepted,~,row] = generator.attempt(0,@(~)state,@neverDraw);
            test.verifyFalse(accepted); test.verifyEqual(row.Reason,'destination_unavailable');
            test.verifyEqual(generator.Statistics.BlockedDestination,1);
            test.verifyEqual(generator.Statistics.BlockedGatewayRoute,0);
        end

        function nsdpUsesChosenDestinationRatherThanConfiguredPlaceholder(test)
            flow = test.flow(); flow.DestinationMode = 'random_route_or_neighbor';
            generator = csr.sim.ApplicationGenerator(1,flow,true,0);
            [accepted,destination,row] = generator.attempt(0,@destinationState,@()0);
            test.verifyFalse(accepted); test.verifyEqual(destination,7);
            test.verifyEqual(row.NsdpCount,16); test.verifyEqual(row.Reason,'nsdp_full');
            [accepted,destination] = generator.attempt(1,@destinationState,@()0.99);
            test.verifyTrue(accepted); test.verifyEqual(destination,9);
        end

        function configuredGeneratorPreservesUngatedCreation(test)
            config = test.smallScenario();
            config.ApplicationProfile = 'legacy-send-only-no-dscp';
            simulation = csr.sim.NetworkSimulation(config); result = simulation.run();
            test.verifyEqual(result.Config.ApplicationGenerator,'configured-count');
            test.verifyEqual(result.Statistics.Generated,4); % includes the configured event at stop
            test.verifyEqual(result.ApplicationAdmissionStatistics.Attempts,4);
            test.verifyEqual(result.ApplicationAdmissionStatistics.Admitted,4);
            test.verifyEmpty(result.ApplicationAdmissionTrace);
        end

        function historicalInterruptsContinueAfterSuppressionAndExcludeStop(test)
            config = test.smallScenario();
            config.ApplicationGenerator = 'historical-opnet-gated';
            simulation = csr.sim.NetworkSimulation(config); result = simulation.run();
            test.verifyEqual(result.Statistics.Generated,0);
            test.verifyEqual(result.ApplicationAdmissionStatistics.Attempts,3);
            test.verifyEqual(result.ApplicationAdmissionStatistics.BlockedTopology,3);
            test.verifyEqual(result.ApplicationAdmissionTrace.TimeSeconds,[0;0.125;0.25],'AbsTol',1e-15);
            test.verifyEqual(result.ApplicationAdmissionTrace.PacketId,zeros(3,1,'uint64'));
            test.verifyFalse(any(strcmp(result.ProtocolTrace.Event,'app_generate')));
        end

        function boundedAdmissionTraceRetainsCompleteAttemptCounts(test)
            config = test.smallScenario();
            config.ApplicationGenerator = 'historical-opnet-gated';
            config.Trace.MaxApplicationAdmissionRecords = 1;
            simulation = csr.sim.NetworkSimulation(config); result = simulation.run();
            test.verifyEqual(result.ApplicationAdmissionStatistics.Attempts,3);
            test.verifyEqual(height(result.ApplicationAdmissionTrace),1);
            test.verifyEqual(result.Statistics.OmittedApplicationAdmissionRecords,2);
        end

        function explicitGeneratorRejectsAmbiguousTimingAndDynamicDefaults(test)
            config = test.smallScenario(); config.ApplicationGenerator = 'historical-opnet-gated';
            config.Traffic.StartSeconds = config.DurationSeconds;
            test.verifyError(@()csr.scenario.validate(config),'csr:scenario:ApplicationGenerator');
            config.Traffic.StartSeconds = 0; config.Traffic.IntervalSeconds = 1.5e-9;
            test.verifyError(@()csr.scenario.validate(config),'csr:scenario:ApplicationGenerator');
            config = test.smallScenario(); config.Traffic.DestinationMode = 'random_route_or_neighbor';
            test.verifyError(@()csr.scenario.validate(config),'csr:scenario:ApplicationGenerator');
        end
    end
    methods (Static, Access=private)
        function flow = flow()
            flow = struct('SourceId',2,'DestinationId',1,'DestinationMode','fixed');
        end
        function state = state()
            state = struct('DiscoveryActive',false,'TopologyKnown',true,'GatewayId',1, ...
                'DestinationCandidates',[1,3],'NsdpCount',0,'NwkQueueSize',0);
        end
        function config = smallScenario()
            config = csr.scenario.routedNetwork('autonomous');
            config.DurationSeconds = 0.375; config.Nwk.StartupMode = 'manual';
            config.Traffic.StartSeconds = 0; config.Traffic.IntervalSeconds = 0.125;
            config.Traffic.PacketCount = 4; config.Trace.MaxRecords = 1000;
            config.Trace.MaxPhyRecords = 1000;
        end
    end
end

function value = neverDraw()
error('csr:test:UnexpectedRandomDraw','Blocked or fixed flows must not draw a destination.');
value = 0; %#ok<UNRCH>
end

function state = destinationState(destination)
state = struct('DiscoveryActive',false,'TopologyKnown',true,'GatewayId',1, ...
    'DestinationCandidates',[7,9],'NsdpCount',16*double(destination==7),'NwkQueueSize',4);
end
