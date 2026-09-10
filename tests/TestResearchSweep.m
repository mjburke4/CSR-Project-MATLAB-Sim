classdef TestResearchSweep < matlab.unittest.TestCase
    % Controlled inputs and honest plan metadata; no delivery assertions.
    methods (Test)
        function defaultsEnumeratePairedCasesAndExecutionBudget(test)
            [cases,plan] = csr.scenario.researchSweep();
            test.verifySize(cases,[18 1]);
            test.verifyEqual(plan.Schema,'csr-matlab-research-sweep-plan-v1');
            test.verifyEqual(plan.Status,'planned-not-executed');
            test.verifyEqual(plan.CaseCount,18);
            test.verifyEqual(plan.TotalSimulatedSeconds,13500);
            test.verifyEqual(plan.TotalApplications,357);
            test.verifyEqual(plan.LongRunCaseCount,0);
            test.verifyEqual(plan.Options.Seeds,[128 129 130]);
            test.verifyFalse(plan.DeliveryCertified);
            test.verifyFalse(plan.NumericalParityCertified);
            test.verifyEqual(plan.Cases,rmfield(cases,'Config'));
            test.verifyEqual(numel(unique({cases.CaseId})),18);
            test.verifyEqual({cases(1:3).CaseId}, ...
                {'offered_load_x1_seed128','offered_load_x1_seed129','offered_load_x1_seed130'});
            decoded = jsondecode(jsonencode(plan));
            test.verifyEqual(decoded.CaseCount,18);
            test.verifyEqual(numel(decoded.Cases),18);
        end

        function offeredLoadPreservesGenerationEndpointsAndDrain(test)
            cases = csr.scenario.researchSweep(struct('Seeds',128, ...
                'Experiments','offered_load','LoadMultipliers',1:8));
            base = csr.scenario.researchNetwork('hidden_node',struct('Seed',128));
            for k = 1:numel(cases)
                config = cases(k).Config;
                test.verifyEqual([config.Traffic.StartSeconds],[base.Traffic.StartSeconds]);
                test.verifyEqual([config.Traffic.PacketCount], ...
                    1+([base.Traffic.PacketCount]-1)*cases(k).Value);
                test.verifyEqual([config.Traffic.IntervalSeconds], ...
                    [base.Traffic.IntervalSeconds]/cases(k).Value);
                test.verifyEqual(TestResearchSweep.trafficEnds(config), ...
                    TestResearchSweep.trafficEnds(base),'AbsTol',1e-10);
                test.verifyEqual(config.Research.WarmupSeconds,240);
                test.verifyEqual(config.Research.TrafficEndSeconds,303,'AbsTol',1e-10);
                test.verifyEqual(config.Research.DrainSeconds,297,'AbsTol',1e-10);
                test.verifyEqual(config.DurationSeconds,600);
            end
        end

        function offeredLoadChangesOnlyTimingCountsAndEvidenceFields(test)
            cases = csr.scenario.researchSweep(struct('Seeds',129, ...
                'Experiments','offered_load','LoadMultipliers',4));
            actual = TestResearchSweep.simulatorInputs(cases.Config);
            expected = TestResearchSweep.simulatorInputs( ...
                csr.scenario.researchNetwork('hidden_node',struct('Seed',129)));
            for k = 1:numel(expected.Traffic)
                expected.Traffic(k).PacketCount = 29;
                expected.Traffic(k).IntervalSeconds = 2.25;
            end
            test.verifyEqual(actual,expected);
            test.verifyEqual([actual.Traffic.SourceId],[2 3]);
            test.verifyEqual([actual.Traffic.ApplicationPayloadBytes],[64 64]);
            test.verifyEqual([actual.Traffic.Dscp],[0 0]);
        end

        function recoveryChangesOnlyTimeoutAndEvidenceFields(test)
            cases = csr.scenario.researchSweep(struct('Seeds',130, ...
                'Experiments','recovery_freshness','FreshnessTimeoutSeconds',[60 180 300]));
            base = csr.scenario.researchNetwork('route_recovery',struct('Seed',130));
            for k = 1:numel(cases)
                config = cases(k).Config;
                expected = TestResearchSweep.simulatorInputs(base);
                expected.Nwk.Neighbor.FreshnessTimeoutSeconds = cases(k).Value;
                test.verifyEqual(TestResearchSweep.simulatorInputs(config),expected);
                test.verifyEqual(config.LinkEvents,base.LinkEvents);
                test.verifyEqual(config.DiscoveryEvents,base.DiscoveryEvents);
                test.verifyEqual(config.Traffic,base.Traffic);
                test.verifyTrue(config.Research.AdministrativeReceiveBlackout);
                test.verifyTrue(config.Nwk.Neighbor.FreshnessEnabled);
                test.verifyEqual(config.Nwk.Neighbor.FreshnessPeriodSeconds,5);
            end
        end

        function everyCaseRetainsPhysicalAndOrdinaryRateBoundaries(test)
            cases = csr.scenario.researchSweep(struct('Seeds',128,'IncludeLongRun',true));
            for k = 1:numel(cases)
                config = cases(k).Config;
                test.verifyEqual(config.Name,cases(k).CaseId);
                test.verifyEqual(config.Seed,cases(k).Seed);
                test.verifyEqual(config.Stack,'network');
                test.verifyEqual(config.Backend,'portable');
                test.verifyEqual(config.Channel.Model,'csr-phy');
                test.verifyEqual(config.Channel.FixedDropProbability,0);
                test.verifyFalse(config.Research.ImportedHistoricalCampus);
                test.verifyFalse(config.Research.HighRateExtension);
                test.verifyFalse(config.Research.ExpectedDeliveryCertified);
                test.verifyFalse(config.Research.Sweep.OutcomeCertified);
                test.verifyFalse(any(strcmp(config.Research.FixtureName, ...
                    {'leaf_no_transit','high_rate_500','high_rate_1000'})));
                test.verifyTrue(all([config.Nodes.TransitForwardingEnabled]));
                test.verifyEmpty(config.Faults);
                test.verifyFalse(isfield(config.Traffic,'Path'));
                test.verifyEqual(csr.scenario.validate(config),config);
            end
        end

        function eachParameterUsesExactlyTheSameSeedSet(test)
            [cases,plan] = csr.scenario.researchSweep(struct('Seeds',[9 0 2^32-1]));
            keys = strcat({cases.Experiment},':',{cases.Parameter},':', ...
                arrayfun(@(row)sprintf('%d',row.Value),cases,'UniformOutput',false)');
            for key = unique(keys)
                selected = cases(strcmp(keys,key{1}));
                test.verifyEqual([selected.Seed],plan.Options.Seeds);
                test.verifyEqual(arrayfun(@(row)row.Config.Seed,selected)',plan.Options.Seeds);
            end
            test.verifyTrue(any(strcmp({cases.CaseId},'offered_load_x1_seed4294967295')));
        end

        function repeatedConstructionPreservesConfigurationAndGlobalRng(test)
            before = rng;
            options = struct('Seeds',uint32([132;131]), ...
                'Experiments',{{"recovery_freshness","offered_load"}}, ...
                'LoadMultipliers',uint8([4;1]), ...
                'FreshnessTimeoutSeconds',uint16([300;60]));
            [first,firstPlan] = csr.scenario.researchSweep(options);
            [second,secondPlan] = csr.scenario.researchSweep(options);
            test.verifyEqual(first,second);
            test.verifyEqual(firstPlan,secondPlan);
            test.verifyEqual(firstPlan.Options.Seeds,[132 131]);
            test.verifyEqual(firstPlan.Options.LoadMultipliers,[4 1]);
            test.verifyEqual(firstPlan.Options.FreshnessTimeoutSeconds,[300 60]);
            test.verifyEqual(first(1).CaseId,'recovery_freshness_s300_seed132');
            test.verifyEqual(first(5).CaseId,'offered_load_x4_seed132');
            test.verifyEqual(rng,before);
        end

        function explicitLongRunPreservesWorkloadAndRaisesEvidenceCaps(test)
            [cases,plan] = csr.scenario.researchSweep(struct('Seeds',[128 129], ...
                'Experiments',{{}},'IncludeLongRun',true));
            test.verifySize(cases,[2 1]);
            test.verifyEqual(plan.LongRunCaseCount,2);
            test.verifyEqual(plan.TotalSimulatedSeconds,12000);
            test.verifyEqual(plan.TotalApplications,320);
            for k = 1:numel(cases)
                config = cases(k).Config;
                base = csr.scenario.researchNetwork('long_run_6000',struct('Seed',cases(k).Seed));
                test.verifyEqual(TestResearchSweep.simulatorInputs(config), ...
                    TestResearchSweep.simulatorInputs(base));
                test.verifyEqual(config.DurationSeconds,6000);
                test.verifyEqual(config.Trace.MaxRecords,1000000);
                test.verifyEqual(config.Trace.MaxPhyRecords,500000);
                test.verifyEqual(config.MaxEvents,5000000);
                test.verifyTrue(config.Research.LongRunOptIn);
                test.verifyEqual(cases(k).Experiment,'long_run');
                test.verifyEqual(cases(k).Parameter,'DurationSeconds');
                test.verifyEqual(cases(k).Value,6000);
            end
        end

        function longRunIsAddedOncePerSeedAfterRequestedExperiments(test)
            [cases,plan] = csr.scenario.researchSweep(struct('IncludeLongRun',true));
            test.verifySize(cases,[21 1]);
            test.verifyEqual(plan.LongRunCaseCount,3);
            test.verifyEqual(plan.TotalSimulatedSeconds,31500);
            test.verifyEqual(plan.TotalApplications,837);
            test.verifyEqual({cases(19:21).Experiment},{'long_run','long_run','long_run'});
            test.verifyEqual([cases(19:21).Seed],[128 129 130]);
        end

        function shortEvidenceLimitsAreUniformAcrossParameterValues(test)
            cases = csr.scenario.researchSweep(struct('Seeds',128));
            for k = 1:numel(cases)
                test.verifyEqual(cases(k).Config.Trace.MaxRecords,250000);
                test.verifyEqual(cases(k).Config.Trace.MaxPhyRecords,250000);
                test.verifyEqual(cases(k).Config.MaxEvents,2000000);
                test.verifyTrue(cases(k).Config.Trace.Enabled);
                test.verifyGreaterThan(cases(k).Config.Research.DrainSeconds,0);
            end
        end

        function malformedOptionsAndUnknownFieldsAreRejected(test)
            values = {[],{1},repmat(struct(),1,2),struct('Seed',128), ...
                struct('DurationSeconds',6000),struct('ApplicationProfile','legacy-send-only-no-dscp'), ...
                struct('IncludeLongRun',1),struct('IncludeLongRun',[true false])};
            for k = 1:numel(values)
                test.verifyError(@()csr.scenario.researchSweep(values{k}),'csr:scenario:SweepOptions');
            end
        end

        function malformedAndDuplicateExperimentsAreRejected(test)
            values = {{},{'offered_load','offered_load'},{'leaf_no_transit'}, ...
                {'long_run'},'campus',42,{'offered_load',42}, ...
                char('offered_load','hidden_node '),{"offered_load",["offered_load" "recovery_freshness"]}};
            for k = 1:numel(values)
                options = struct(); options.Experiments = values{k};
                test.verifyError(@()csr.scenario.researchSweep(options),'csr:scenario:SweepOptions');
            end
        end

        function invalidSeedSetsAreRejectedBeforeConfigurationConstruction(test)
            values = {[],[1 1],-1,2^32,1.5,NaN,Inf,true,'128',1:21, ...
                [1 2;3 4],1+1i,sparse([1 2])};
            for k = 1:numel(values)
                test.verifyError(@()csr.scenario.researchSweep(struct('Seeds',values{k})), ...
                    'csr:scenario:SweepOptions');
            end
        end

        function invalidLoadChoicesAreRejected(test)
            for value = {[],0,9,1.5,[1 1],NaN,Inf,true,'4',[1 2;3 4]}
                test.verifyError(@()csr.scenario.researchSweep(struct('LoadMultipliers',value{1})), ...
                    'csr:scenario:SweepOptions');
            end
        end

        function invalidFreshnessChoicesAreRejected(test)
            for value = {[],29,601,60.5,[60 60],NaN,Inf,true,'60',30:38}
                test.verifyError(@()csr.scenario.researchSweep( ...
                    struct('FreshnessTimeoutSeconds',value{1})),'csr:scenario:SweepOptions');
            end
        end

        function oversizedCasePlansFailBeforeSimulation(test)
            options = struct('Seeds',0:19,'LoadMultipliers',1:8, ...
                'FreshnessTimeoutSeconds',[30 60 90 120 180 240 300 600], ...
                'IncludeLongRun',true);
            test.verifyError(@()csr.scenario.researchSweep(options),'csr:scenario:SweepCaseLimit');
        end
    end

    methods (Static, Access = private)
        function inputs = simulatorInputs(config)
            % Names/provenance and trace capacity do not alter protocol inputs.
            inputs = rmfield(config,{'Name','Research','Trace'});
        end

        function values = trafficEnds(config)
            values = [config.Traffic.StartSeconds]+ ...
                ([config.Traffic.PacketCount]-1).*[config.Traffic.IntervalSeconds];
        end
    end
end
