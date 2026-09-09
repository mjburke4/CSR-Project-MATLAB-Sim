classdef TestResearchScenarios < matlab.unittest.TestCase
    % Fixture contracts and RF hypotheses; these tests do not certify delivery.
    methods (Test)
        function allFixturesUseNativePacketPhyAndSyntheticProvenance(test)
            names = TestResearchScenarios.names();
            for k = 1:numel(names)
                config = csr.scenario.researchNetwork(names{k});
                test.verifyEqual(config.Name,['research_' names{k}]);
                test.verifyEqual(config.Stack,'network');
                test.verifyEqual(config.Channel.Model,'csr-phy');
                test.verifyEqual(config.Channel.FixedDropProbability,0);
                test.verifyEqual(config.Research.LayoutOrigin,'synthetic-research-layout');
                test.verifyFalse(config.Research.ImportedHistoricalCampus);
                test.verifyFalse(config.Research.ExpectedDeliveryCertified);
                test.verifyEmpty(config.Faults);
                test.verifyFalse(isfield(config.Traffic,'Path'));
                for node = config.Nodes
                    test.verifyEqual(node.RadioProfile.PropagationModel,'OPNET_THREE_PATH');
                    test.verifyEqual(node.RadioProfile.ClosureMode,'EARTH_LINE_OF_SIGHT');
                    test.verifyEmpty(node.RadioProfile.ClosureDelegate);
                    test.verifyTrue(node.RadioProfile.StochasticSyncThreshold);
                end
                test.verifyEqual(csr.scenario.validate(config),config);
            end
        end

        function lineGeometryAdmitsOnlyAdjacentGeometricVisibility(test)
            config = csr.scenario.researchNetwork('line_4');
            for source = 1:4
                for destination = 1:4
                    if source == destination, continue; end
                    link = TestResearchScenarios.link(config,source,destination);
                    test.verifyEqual(link.Closure,abs(source-destination)==1);
                    if link.Closure
                        test.verifyGreaterThan(link.SnrDb, ...
                            config.Nodes(destination).RadioProfile.SyncSnrThresholdDb+4);
                    end
                end
            end
        end

        function hiddenSourcesShareReceiverWithoutMutualVisibility(test)
            config = csr.scenario.researchNetwork('hidden_node');
            test.verifyTrue(TestResearchScenarios.link(config,2,1).Closure);
            test.verifyTrue(TestResearchScenarios.link(config,3,1).Closure);
            test.verifyFalse(TestResearchScenarios.link(config,2,3).Closure);
            test.verifyEqual([config.Traffic.SourceId],[2 3]);
            test.verifyEqual([config.Traffic.DestinationId],[1 1]);
            test.verifyEqual(config.Traffic(1).StartSeconds,config.Traffic(2).StartSeconds);
        end

        function meshProvidesMultipleGeometricNextHopOpportunities(test)
            config = csr.scenario.researchNetwork('mesh_6');
            test.verifyEqual(numel(config.Nodes),6);
            test.verifyTrue(TestResearchScenarios.link(config,6,3).Closure);
            test.verifyTrue(TestResearchScenarios.link(config,6,5).Closure);
            test.verifyFalse(TestResearchScenarios.link(config,6,1).Closure);
            test.verifyEqual([config.Traffic.Dscp],[0 8 16]);
        end

        function requestsCoverEveryNodeBeforeFirstApplication(test)
            for name = TestResearchScenarios.names()
                config = csr.scenario.researchNetwork(name{1});
                test.verifyEqual(config.Nwk.StartupMode,'manual');
                nodeCount = numel(config.Nodes);
                startup = config.DiscoveryEvents(1:nodeCount);
                test.verifyEqual([startup.NodeIds],[config.Nodes.Id]);
                test.verifyGreaterThan(diff([startup.TimeSeconds]),0);
                test.verifyLessThan(max([startup.TimeSeconds])+ ...
                    config.Nwk.DiscoveryDurationSeconds,config.Research.WarmupSeconds);
            end
        end

        function recoveryNamesItsAdministrativeBlackoutAndRediscovery(test)
            config = csr.scenario.researchNetwork('route_recovery');
            test.verifyTrue(config.Research.AdministrativeReceiveBlackout);
            test.verifyTrue(config.Nwk.Neighbor.FreshnessEnabled);
            test.verifyEqual([config.LinkEvents.NodeIds],[2 2]);
            test.verifyEqual([config.LinkEvents.Enabled],[false true]);
            test.verifyGreaterThan(config.Traffic.StartSeconds,config.LinkEvents(1).TimeSeconds);
            test.verifyLessThan(config.Traffic.StartSeconds,config.LinkEvents(2).TimeSeconds);
            afterRestore = [config.DiscoveryEvents.TimeSeconds] > config.LinkEvents(2).TimeSeconds;
            test.verifyEqual([config.DiscoveryEvents(afterRestore).NodeIds],[1 2 3]);
            for name = {'two_node','line_4','hidden_node','mesh_6','leaf_no_transit'}
                other = csr.scenario.researchNetwork(name{1});
                test.verifyEmpty(other.LinkEvents);
                test.verifyFalse(other.Research.AdministrativeReceiveBlackout);
            end
        end

        function leafTransitPolicyDoesNotRemoveTheRadio(test)
            config = csr.scenario.researchNetwork('leaf_no_transit');
            test.verifyEqual(config.Nodes(2).Capability,0);
            test.verifyFalse(config.Nodes(2).TransitForwardingEnabled);
            test.verifyTrue(TestResearchScenarios.link(config,3,2).Closure);
            test.verifyTrue(TestResearchScenarios.link(config,2,1).Closure);
            test.verifyFalse(TestResearchScenarios.link(config,3,1).Closure);
            test.verifyTrue(all([config.Traffic.AckRequired]));
        end

        function ordinaryAndHighRateOperatingRangesRemainSeparate(test)
            for name = TestResearchScenarios.names()
                config = csr.scenario.researchNetwork(name{1});
                if config.Research.HighRateExtension
                    test.verifyTrue(ismember(config.Radio.RateKeyKbps,[500 1000]));
                    test.verifyEqual(config.Nwk.Routing.LocalInfo.MinSpeedKbps,config.Radio.RateKeyKbps);
                    test.verifyEqual(config.Nwk.Routing.LocalInfo.MaxSpeedKbps,config.Radio.RateKeyKbps);
                    test.verifyFalse(config.Nwk.AdaptiveLinkControl);
                    test.verifyEqual(numel(config.Nodes),2);
                else
                    test.verifyEqual(config.Research.RateProfile,'ordinary-8-to-128-kbps');
                    test.verifyLessThanOrEqual(config.Radio.RateKeyKbps,128);
                    test.verifyEqual(config.Nwk.Routing.LocalInfo.MaxSpeedKbps,128);
                    test.verifyLessThanOrEqual([config.Traffic.RateKeyKbps],128);
                end
            end
        end

        function legacyProfilesExplicitlyRemoveAllApplicationDscp(test)
            for profile = {'legacy-send-only-no-dscp','legacy-send-to-from-no-dscp'}
                config = csr.scenario.researchNetwork('mesh_6',struct('ApplicationProfile',profile{1}));
                test.verifyEqual(config.ApplicationProfile,profile{1});
                test.verifyEqual([config.Traffic.Dscp],[0 0 0]);
            end
            config = csr.scenario.researchNetwork('mesh_6',struct('ApplicationProfile',"current-send-only"));
            test.verifyEqual([config.Traffic.Dscp],[0 8 16]);
            test.verifyError(@()csr.scenario.researchNetwork('two_node', ...
                struct('ApplicationProfile','legacy-no-dscp')),'csr:scenario:ApplicationProfile');
        end

        function seedAndDurationOverridesPreserveReproducibleInputs(test)
            before = rng;
            options = struct('Seed',uint32(981),'DurationSeconds',uint16(1200));
            first = csr.scenario.researchNetwork('mesh_6',options);
            second = csr.scenario.researchNetwork('mesh_6',options);
            test.verifyEqual(first,second);
            test.verifyEqual(first.Seed,981);
            test.verifyEqual(first.DurationSeconds,1200);
            test.verifyEqual(rng,before);
            defaults = csr.scenario.researchNetwork('mesh_6');
            test.verifyEqual(first.Nodes,defaults.Nodes);
            test.verifyEqual(first.Traffic(1).StartSeconds,480);
        end

        function trafficEndsBeforeStopWithAnExplicitDrainWindow(test)
            for name = TestResearchScenarios.names()
                config = csr.scenario.researchNetwork(name{1});
                last = max([config.Traffic.StartSeconds]+ ...
                    ([config.Traffic.PacketCount]-1).*[config.Traffic.IntervalSeconds]);
                test.verifyEqual(config.Research.TrafficEndSeconds,last);
                test.verifyEqual(config.Research.DrainSeconds,config.DurationSeconds-last);
                test.verifyGreaterThanOrEqual(config.Research.DrainSeconds,90);
                test.verifyGreaterThan(sum([config.Traffic.PacketCount]),0);
            end
        end

        function longWorkloadRetains6000SecondsAndFlagsExtendedRuns(test)
            config = csr.scenario.researchNetwork('long_run_6000');
            test.verifyEqual(config.DurationSeconds,6000);
            test.verifyTrue(config.Research.LongRunOptIn);
            test.verifyEqual(config.Traffic.PacketCount,160);
            test.verifyEqual(config.Research.TrafficEndSeconds,5370);
            test.verifyEqual(config.Research.DrainSeconds,630);
            ordinary = csr.scenario.researchNetwork();
            test.verifyFalse(ordinary.Research.LongRunOptIn);
            test.verifyLessThan(ordinary.DurationSeconds,6000);
            extended = csr.scenario.researchNetwork('two_node',struct('DurationSeconds',6000));
            test.verifyTrue(extended.Research.LongRunOptIn);
            test.verifyEqual(extended.Research.FixtureName,'two_node');
            test.verifyEqual(extended.Traffic.PacketCount,5);
            test.verifyError(@()csr.scenario.researchNetwork('long_run_6000', ...
                struct('DurationSeconds',5999)),'csr:scenario:ResearchDuration');
        end

        function malformedNamesAndOptionsFailBeforeSimulation(test)
            for name = {'campus','two-node',42,["two_node" "line_4"],char('two_node','line_4  ')}
                test.verifyError(@()csr.scenario.researchNetwork(name{1}), ...
                    'csr:scenario:UnknownResearchFixture');
            end
            for options = {[],{1},repmat(struct('Seed',1),1,2),struct('seed',42), ...
                    struct('RateKeyKbps',1000),struct('ClosureMode','DELEGATE')}
                test.verifyError(@()csr.scenario.researchNetwork('two_node',options{1}), ...
                    'csr:scenario:ResearchOptions');
            end
            for value = {299,Inf,NaN,6001,'600',[600 900]}
                test.verifyError(@()csr.scenario.researchNetwork('two_node', ...
                    struct('DurationSeconds',value{1})),'csr:scenario:ResearchDuration');
            end
        end
    end

    methods (Static, Access = private)
        function names = names()
            names = {'two_node','line_4','hidden_node','mesh_6','route_recovery', ...
                'leaf_no_transit','high_rate_500','high_rate_1000','long_run_6000'};
        end

        function result = link(config,source,destination)
            transmitter = config.Nodes(source);
            receiver = config.Nodes(destination);
            result = csr.phy.Model.frontEnd(transmitter.RadioProfile,receiver.RadioProfile, ...
                transmitter.PositionMeters,receiver.PositionMeters);
        end
    end
end
