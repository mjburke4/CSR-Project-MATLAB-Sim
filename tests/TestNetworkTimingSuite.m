classdef TestNetworkTimingSuite < matlab.unittest.TestCase
    properties
        Cases
        Plan
        Parents
    end
    methods (TestClassSetup)
        function loadCanonicalInputs(test)
            [test.Cases,test.Plan]=csr.scenario.tranche16Suite();
            test.Parents=csr.scenario.linkDiagnosticSuite();
        end
    end
    methods (Test)
        function threeSeedsRetainTheTwelveRunBudgetAndShortCaseKeys(test)
            test.verifyEqual({test.Cases.CaseId},{'a128','c128','a129','c129','a130','c130'});
            test.verifyEqual({test.Cases.StorageKey},{test.Cases.CaseId});
            test.verifyEqual([test.Cases.Seed],[128 128 129 129 130 130]);
            test.verifyEqual([test.Cases.DurationSeconds],[1200 360 1200 360 1200 360]);
            test.verifyEqual(test.Plan.case_count,6);
            test.verifyEqual(test.Plan.paired_run_count,12);
            test.verifyEqual(test.Plan.paired_simulated_seconds,9360);
            test.verifyEqual(string(test.Plan.policies(:)),["continuous";"nanoseconds"]);
            test.verifyEqual(string(test.Plan.policy_keys(:)),["c";"n"]);
        end

        function timingInjectionDoesNotAlterAnyCanonicalNetworkSetting(test)
            for k=1:numel(test.Cases)
                item=test.Cases(k);
                index=find(strcmp({test.Parents.CaseId},item.NativeCaseId));
                test.assertEqual(numel(index),1);
                parent=test.Parents(index);
                test.verifyEqual(item.Config,parent.Config);
                test.verifyEqual(item.ScenarioFile,parent.ScenarioFile);
                test.verifyEqual(item.ScenarioSHA256,parent.ScenarioSHA256);
                test.verifyEqual(item.ReferenceDirectory,parent.ReferenceDirectory);
                test.verifyEqual(item.Config.Channel.Model,'csr-phy');
                test.verifyEqual(item.Config.Backend,'portable');
                test.verifyEqual(item.Config.Benchmark.CaseId,item.NativeCaseId);
                test.verifyFalse(item.OpnetAvailable);
            end
        end

        function eachPairedCaseRetainsCanonicalSourceAndRecipeBindings(test)
            root=fileparts(fileparts(mfilename('fullpath')));
            entries=test.Plan.cases;
            if iscell(entries), entries=vertcat(entries{:}); end
            for k=1:numel(test.Cases)
                item=test.Cases(k); entry=entries(k);
                test.verifyEqual(entry.case_id,item.CaseId);
                test.verifyEqual(entry.native_case_id,item.NativeCaseId);
                test.verifyEqual(entry.storage_key,item.StorageKey);
                test.verifyEqual(csr.validation.Artifacts.sha256(fullfile(root,entry.scenario_file)),entry.scenario_sha256);
                test.verifyEqual(csr.validation.Artifacts.sha256(fullfile(root,entry.recipe_file)),entry.recipe_sha256);
                test.verifyEqual(item.Config.Trace.MaxRecords,1500000);
                test.verifyEqual(item.Config.Trace.MaxPhyRecords,1500000);
                test.verifyEqual(item.Config.Trace.MaxApplicationAdmissionRecords,100000);
                test.verifyEqual(item.ObserverMaxRecords,100000);
            end
        end
    end
end
