classdef TestTranche10Suite < matlab.unittest.TestCase
    methods (Test)
        function retainedFactoriesPreserveConfigurations(test)
            [cases,plan]=csr.scenario.retainedSuite();
            test.verifyEqual(numel(cases),29);
            test.verifyEqual(plan.CaseCount,29);
            test.verifyEqual(cases(1).Config,csr.scenario.smallNetwork());
            test.verifyEqual(cases(2).Config,csr.scenario.macHopNetwork('reliable'));
            test.verifyEqual(cases(10).Config,csr.scenario.macHopNetwork('high_rate_1000'));
            test.verifyEqual(cases(11).Config,csr.scenario.routedNetwork('autonomous'));
            test.verifyEqual(cases(29).Config,csr.scenario.researchNetwork('leaf_no_transit',struct('Seed',128)));
            test.verifyEqual(numel(unique({cases.CaseId})),29);
        end

        function retainedPathsDoNotRenameScientificCases(test)
            cases=csr.scenario.retainedSuite();
            test.verifyEqual({cases.StorageKey},arrayfun(@(k)sprintf('%02d',k),1:29,'UniformOutput',false));
            test.verifyEqual(cases(1).Config.Name,'three_node_controlled');
            test.verifyEqual({cases(19:23).Name},{'two_node_8','two_node_128','line_3_8','high_rate_500','high_rate_1000'});
            test.verifyEqual({cases(24:29).Name},{'two_node_seed_128','line_4_seed_128', ...
                'hidden_node_seed_128','mesh_6_seed_128','route_recovery_seed_128','leaf_no_transit_seed_128'});
        end

        function diagnosticsAndSweepsKeepAcceptedStimuli(test)
            [cases,plan,~,sweeps]=csr.scenario.tranche10Suite();
            parents=csr.scenario.ackServiceSuite();
            original=csr.scenario.researchSweep();
            test.verifyEqual(cases,parents);
            test.verifyEqual(rmfield(sweeps,'StorageKey'),original);
            test.verifyEqual([plan.accepted_anchors.tranche],[7 8 9]);
            test.verifyFalse(plan.stimuli_changed);
            test.verifyFalse(plan.phy_ecc_changed);
            test.verifyFalse(plan.radio_policy_changed);
            test.verifyFalse(plan.rng_policy_changed);
        end

        function campusKeepsFullDurationAndBoundedAdmissionEvidence(test)
            [~,~,~,~,campus]=csr.scenario.tranche10Suite();
            original=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
            test.verifyEqual(rmfield(campus,'StorageKey'),original);
            test.verifyEqual(campus.DurationSeconds,6000);
            test.verifyEqual(campus.Seed,128);
            test.verifyEqual(campus.Config.Trace.MaxApplicationAdmissionRecords,100000);
            test.verifyEqual(campus.StorageKey,'campus');
        end
    end
end
