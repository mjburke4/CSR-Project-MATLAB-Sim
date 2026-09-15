classdef TestBenchmarkSuite < matlab.unittest.TestCase
    methods (Test)
        function defaultsBindCampusAndFocusedDiagnostics(test)
            [cases,plan]=csr.scenario.benchmarkSuite();
            test.verifyEqual({cases.CaseId}, ...
                {'campus_multihop_6000','two_node_admission_1200','three_node_contention_360'});
            test.verifyEqual([cases.DurationSeconds],[6000 1200 360]);
            test.verifyEqual([cases.BucketWidthSeconds],[60 12 3.6]);
            test.verifyEqual([cases.OpnetAvailable],[true false false]);
            test.verifyEqual({cases.SourceKind},{'archived_opnet','synthetic_diagnostic','synthetic_diagnostic'});
            test.verifyEqual(plan.CaseCount,3);
            test.verifyEqual(plan.TotalSimulatedSeconds,7560);
            test.verifyEqual(plan.Status,'planned-not-executed');
            test.verifyFalse(plan.NumericalParityEstablished);
        end

        function campusIsFullWorkloadOnPhysicalChannel(test)
            cases=csr.scenario.benchmarkSuite(struct('Cases','campus_multihop_6000'));
            test.assertNumElements(cases,1);
            config=cases.Config;
            test.verifyEqual([config.Nodes.Id],[1 2 3 4 5 7 8]);
            test.verifyEqual(config.Channel.Model,'csr-phy');
            test.verifyEqual(config.ApplicationFlowLimit,0);
            test.verifyEqual(sum([config.Traffic.PacketCount]),1710000);
            test.verifyEqual([config.Traffic.StartSeconds],repmat(300,1,6));
            test.verifyEqual([config.Traffic.IntervalSeconds],repmat(0.02,1,6));
            test.verifyEqual(config.Nwk.Routing.LocalInfo.MaxSpeedKbps,128);
            test.verifyEqual(config.Nwk.Routing.LocalInfo.MinPowerDbmX10,-360);
            test.verifyFalse(config.Benchmark.HistoricalOutcomeEquivalenceEstablished);
        end

        function selectionPreservesCanonicalOrderAndInputHashes(test)
            root=fileparts(fileparts(mfilename('fullpath')));
            options=struct('Cases',{{'three_node_contention_360','two_node_admission_1200'}});
            [cases,plan]=csr.scenario.benchmarkSuite(options);
            test.verifyEqual({cases.CaseId},{'two_node_admission_1200','three_node_contention_360'});
            test.verifyEqual(plan.CaseCount,2);
            for k=1:numel(cases)
                test.verifyEqual(cases(k).ScenarioSHA256, ...
                    csr.validation.Artifacts.sha256(fullfile(root,cases(k).ScenarioFile)));
                test.verifyEqual(cases(k).Config.SharedScenario.SourceSHA256,cases(k).ScenarioSHA256);
                test.verifyEqual(cases(k).ProfileId,'hist-adb97c54-bare');
                test.verifyEqual(cases(k).Config.ApplicationGenerator,'historical-opnet-gated');
            end
        end

        function unknownDeferredOrMutatingOptionsFailBeforeExecution(test)
            test.verifyError(@()csr.scenario.benchmarkSuite(struct('Cases','hidden_symmetrical_60000')), ...
                'csr:benchmark:Selection');
            test.verifyError(@()csr.scenario.benchmarkSuite(struct('Cases','two_node_latency_1200')), ...
                'csr:benchmark:Selection');
            test.verifyError(@()csr.scenario.benchmarkSuite(struct('DurationSeconds',60)), ...
                'csr:benchmark:Options');
            test.verifyError(@()csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000','campus_multihop_6000'}})), ...
                'csr:benchmark:Options');
            folder=tempname;
            test.verifyError(@()run_tranche7_validation(folder,struct('IncludeLongRuns',true)), ...
                'csr:benchmark:Options');
            test.verifyFalse(isfolder(folder));
        end

        function historicalObservationBudgetsDoNotCapAdmission(test)
            cases=csr.scenario.benchmarkSuite();
            for k=1:numel(cases)
                config=cases(k).Config;
                test.verifyGreaterThanOrEqual(config.Trace.MaxRecords,1000000);
                test.verifyGreaterThanOrEqual(config.Trace.MaxPhyRecords,1000000);
                test.verifyEqual(config.Trace.MaxApplicationAdmissionRecords,100000);
                test.verifyEqual(config.ApplicationFlowLimit,0);
                test.verifyTrue(config.Trace.Enabled);
            end
        end

        function sourceSnapshotBindsBenchmarkInputsAndRecipes(test)
            folder=tempname;
            directory=fullfile(folder,'scenarios','benchmarks'); mkdir(directory);
            test.addTeardown(@()rmdir(folder,'s'));
            paths={'catalog.json','fixture.recipe.json','fixture.csv'};
            for k=1:numel(paths)
                csr.validation.Artifacts.writeJson(fullfile(directory,paths{k}),struct('revision',1));
            end
            initial=csr.validation.Artifacts.sourceSnapshot(folder);
            test.verifyEqual(sort({initial.path}), ...
                sort(strcat('scenarios/benchmarks/',paths)));
            for k=1:numel(paths)
                before=csr.validation.Artifacts.sourceSnapshot(folder);
                csr.validation.Artifacts.writeJson(fullfile(directory,paths{k}),struct('revision',2));
                test.verifyError(@()csr.validation.Artifacts.checkSnapshot(folder,before), ...
                    'csr:validation:SourceChanged');
            end
        end
    end
end
