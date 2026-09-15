classdef TestLinkDiagnosticSuite < matlab.unittest.TestCase
    methods (Test)
        function fixedPlanContainsOnlySmallFiveSeedExperiments(test)
            [cases,plan]=csr.scenario.linkDiagnosticSuite();
            test.verifyEqual(numel(cases),10);
            test.verifyEqual([cases.Seed],repelem(128:132,2));
            test.verifyEqual([cases.DurationSeconds],repmat([1200 360],1,5));
            test.verifyEqual([cases.BucketWidthSeconds],repmat([12 3.6],1,5));
            test.verifyFalse(any([cases.OpnetAvailable]));
            test.verifyEqual(plan.status,'planned-not-executed');
            test.verifyEqual([cases.ObserverMaxRecords],repmat(100000,1,10));
        end

        function stimuliRemainIdenticalToAcceptedDiagnosticParents(test)
            cases=csr.scenario.linkDiagnosticSuite();
            parents=csr.scenario.benchmarkSuite(struct('Cases', ...
                {{'two_node_admission_1200','three_node_contention_360'}}));
            for k=1:numel(cases)
                expected=parents(1+mod(k-1,2)).Config;
                actual=cases(k).Config;
                remove={'Name','Seed','SharedScenario','Benchmark'};
                test.verifyEqual(rmfield(actual,remove),rmfield(expected,remove));
                test.verifyEqual(actual.ApplicationFlowLimit,0);
                test.verifyEqual(actual.Channel.Model,'csr-phy');
            end
        end

        function everyDerivedInputRetainsBoundParentAndRecipe(test)
            root=fileparts(fileparts(mfilename('fullpath')));
            [cases,plan]=csr.scenario.linkDiagnosticSuite();
            entries=plan.cases;
            if iscell(entries), entries=vertcat(entries{:}); end
            for k=1:numel(cases)
                test.verifyEqual(cases(k).ScenarioSHA256, ...
                    csr.validation.Artifacts.sha256(fullfile(root,cases(k).ScenarioFile)));
                test.verifyEqual(cases(k).Config.SharedScenario.SourceSHA256,cases(k).ScenarioSHA256);
                recipe=jsondecode(fileread(fullfile(root,entries(k).recipe_file)));
                test.verifyEqual(recipe.overrides.seed,cases(k).Seed);
                test.verifyEqual(recipe.overrides.scenario,cases(k).Scenario);
                test.verifyEqual(csr.validation.Artifacts.sha256(fullfile(root,recipe.parent_scenario)), ...
                    recipe.parent_scenario_sha256);
            end
        end

        function sourceSnapshotBindsObservationalCppHeaders(test)
            root=tempname; folder=fullfile(root,'scripts','ns3'); mkdir(folder);
            test.addTeardown(@()rmdir(root,'s'));
            header=fullfile(folder,'observer.h');
            csr.validation.Artifacts.writeJson(header,struct('revision',1));
            snapshot=csr.validation.Artifacts.sourceSnapshot(root);
            test.verifyEqual({snapshot.path},{'scripts/ns3/observer.h'});
            csr.validation.Artifacts.writeJson(header,struct('revision',2));
            test.verifyError(@()csr.validation.Artifacts.checkSnapshot(root,snapshot), ...
                'csr:validation:SourceChanged');
        end
    end
end
