classdef TestMultiSeedSuite < matlab.unittest.TestCase
    % Fixed-workload and evidence-reuse contracts; no full campus simulation.
    methods (Test)
        function casesDifferOnlyInDeclaredSeeds(test)
            [cases,plan]=csr.scenario.tranche20Suite();
            [original,~]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
            test.verifyEqual({cases.CaseId},{'s129','s130'});
            test.verifyEqual([cases.Seed],[129 130]);
            test.verifyEqual({cases.Policy},{'actual-tx','actual-tx'});
            expected=original.Config; expected.Seed=129;
            test.verifyEqual(cases(1).Config,expected);
            expected=original.Config; expected.Seed=130;
            test.verifyEqual(cases(2).Config,expected);
            test.verifyEqual(cases(2).Config.Benchmark,original.Config.Benchmark);
            test.verifyEqual([cases.DurationSeconds],[6000 6000]);
            test.verifyEqual(plan.planned_simulated_seconds,12000);
        end

        function originalTrafficGeometryAndEvidenceBudgetsAreRetained(test)
            [cases,plan]=csr.scenario.tranche20Suite();
            for k=1:2
                c=cases(k).Config;
                test.verifyEqual([c.Nodes.Id],[1 2 3 4 5 7 8]);
                test.verifyEqual([c.Traffic.SourceId],[2 3 4 5 7 8]);
                test.verifyEqual(sum([c.Traffic.PacketCount]),1710000);
                test.verifyEqual(c.Trace.MaxApplicationAdmissionRecords,100000);
                test.verifyEqual(c.Trace.MaxRecords,1500000);
                test.verifyEqual(c.Trace.MaxPhyRecords,1500000);
                test.verifyEqual(c.MaxEvents,12000000);
            end
            test.verifyFalse(plan.observer_enabled);
            test.verifyFalse(plan.post_horizon_drain);
            test.verifyFalse(plan.common_random_numbers_claimed);
            test.verifyFalse(plan.numerical_parity_required);
        end

        function changedScopeFailsBeforeSimulation(test)
            [~,plan]=csr.scenario.tranche20Suite();
            [original,~]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
            changes={'observer_enabled',true;'full_portable_regression',false; ...
                'post_horizon_drain',true;'default_policy_changed',true; ...
                'phy_ecc_changed',true;'common_random_numbers_claimed',true; ...
                'planned_simulated_seconds',11999;'comparison_band_percent',10; ...
                'numerical_parity_required',true;'expected_admission_attempts',1710001; ...
                'runtime_must_equal_parent',false;'seed_override_after_import',false};
            for k=1:size(changes,1)
                altered=plan; altered.(changes{k,1})=changes{k,2};
                test.verifyError(@()csr.validation.MultiSeedCheckpoint.validatePlan(altered,original),'csr:t20:Plan');
            end
            altered=plan; altered.cases(2).seed=128;
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.validatePlan(altered,original),'csr:t20:Plan');
            altered=plan; altered.cases(1).policy='native-provisional';
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.validatePlan(altered,original),'csr:t20:Plan');
        end

        function seed128IsReusedNeverScheduled(test)
            [cases,plan]=csr.scenario.tranche20Suite();
            test.verifyEqual([cases(1).Config.Seed cases(2).Config.Seed],[129 130]);
            test.verifyEqual(plan.reused_baseline.case_id,'a128');
            test.verifyEqual(plan.reused_baseline.seed,128);
            test.verifyFalse(plan.reused_baseline.fresh_execution);
            [original,~]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
            altered=plan; altered.reused_baseline.case_id='p128';
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.validatePlan(altered,original),'csr:t20:Plan');
            altered=plan; altered.cases(1).seed=128;
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.validatePlan(altered,original),'csr:t20:Plan');
        end

        function parentRuntimeMustMatchExactly(test)
            expected=struct('Runtime','MATLAB','Version','25.1.0.2943329 (R2025a)','Release','2025a');
            csr.validation.MultiSeedCheckpoint.validateRuntime(expected,expected);
            changed=expected; changed.Version='another update';
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.validateRuntime(changed,expected),'csr:t20:Runtime');
            changed=expected; changed.Release='2026a';
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.validateRuntime(changed,expected),'csr:t20:Runtime');
        end

        function phasesCannotOverrideScenarioParameters(test)
            for phase={'all','tests','s129','s130','finalize'}
                value=csr.validation.MultiSeedCheckpoint.options(struct('Phase',string(phase{1})));
                test.verifyEqual(value.Phase,phase{1});
            end
            for value={struct('Phase','campus'),struct('Seed',129),struct('Phase','resume'),struct('Phase','a128'),struct('Phase','p128'), ...
                    struct('Phase',["s129","s130"]),struct('DurationSeconds',900),[]}
                test.verifyError(@()csr.validation.MultiSeedCheckpoint.options(value{1}),'csr:t20:Options');
            end
        end

        function completedCasesReuseExactBytesIndependently(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(folder,'s129',identity);
            complete(folder,'s130',identity);
            before=csr.validation.Artifacts.fileInventory(folder);
            for phase={'s129','s130'}
                [receipt,reused]=csr.validation.MultiSeedCheckpoint.begin(folder,phase{1},identity);
                test.verifyTrue(reused); test.verifyEqual(receipt.phase,phase{1});
            end
            test.verifyEqual(csr.validation.Artifacts.fileInventory(folder),before);
        end

        function partialCaseNeverResumesOrDamagesCompletedCase(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(folder,'s129',identity);
            csr.validation.MultiSeedCheckpoint.begin(folder,'s130',identity);
            before=csr.validation.Artifacts.fileInventory(folder);
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.begin(folder,'s130',identity), ...
                'csr:t20:IncompleteStage');
            [~,reused]=csr.validation.MultiSeedCheckpoint.begin(folder,'s129',identity);
            test.verifyTrue(reused);
            test.verifyEqual(csr.validation.Artifacts.fileInventory(folder),before);
        end

        function changedCandidateReferenceSourceOrRuntimeRejectsReuse(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(folder,'s129',identity);
            altered=identity; altered.CandidateSHA256=repmat('f',1,64);
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.verify(folder,'s129',altered),'csr:t20:Receipt');
            altered=identity; altered.SourceFiles.sha256=repmat('f',1,64);
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.verify(folder,'s129',altered),'csr:t20:Receipt');
            altered=identity; altered.ReferenceFiles.bytes=2;
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.verify(folder,'s129',altered),'csr:t20:Receipt');
            altered=identity; altered.Runtime.Release='different';
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.verify(folder,'s129',altered),'csr:t20:Receipt');
        end

        function changedOrAddedCaseBytesRejectReuse(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(folder,'s130',identity);
            extra=fullfile(folder,'s130','extra.csv');
            csr.validation.MultiSeedCheckpoint.writeText(extra,'unrecorded');
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.verify(folder,'s130',identity),'csr:t20:Receipt');
            delete(extra);
            csr.validation.MultiSeedCheckpoint.writeText(fullfile(folder,'s130','summary.json'),'changed');
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.verify(folder,'s130',identity),'csr:t20:Receipt');
        end

        function receiptChecksumAndPhaseCannotBeSubstituted(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(folder,'s129',identity);
            receiptPath=fullfile(folder,'s129','receipt.json');
            value=jsondecode(fileread(receiptPath)); value.phase='s130';
            csr.validation.Artifacts.writeJson(receiptPath,value);
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.verify(folder,'s129',identity),'csr:t20:Receipt');
            csr.validation.MultiSeedCheckpoint.writeText(fullfile(folder,'s129','receipt.sha256'), ...
                csr.validation.Artifacts.sha256(receiptPath));
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.verify(folder,'s129',identity),'csr:t20:Receipt');
        end

        function unrelatedOutputIsRejectedBeforeWrites(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            csr.validation.MultiSeedCheckpoint.writeText(fullfile(folder,'personal.txt'),'preserve');
            before=csr.validation.Artifacts.fileInventory(folder);
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.preflight(folder,folder,identity,struct()), ...
                'csr:t20:OutputIdentity');
            test.verifyEqual(csr.validation.Artifacts.fileInventory(folder),before);
        end

        function incompleteRootIdentityIsRejectedBeforeWrites(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            csr.validation.Artifacts.writeJson(fullfile(folder,'source.json'),identity.SourceFiles);
            before=csr.validation.Artifacts.fileInventory(folder);
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.preflight(folder,folder,identity,struct()), ...
                'csr:t20:OutputIdentity');
            test.verifyEqual(csr.validation.Artifacts.fileInventory(folder),before);
        end

        function everyExactPortableTestNameIsRequired(test)
            rows=table({'One/a';'Two/b'},true(2,1),false(2,1),false(2,1),[0;1], ...
                'VariableNames',{'Name','Passed','Failed','Incomplete','DurationSeconds'});
            summary=csr.validation.MultiSeedCheckpoint.testResults(rows,rows.Name);
            test.verifyTrue(summary.TestsPassed);
            test.verifyEqual(summary.Schema,'csr-tranche20-portable-tests-summary-v1');
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.testResults(rows(1,:),rows.Name), ...
                'csr:t20:TestIdentity');
            altered=rows; altered.Name{2}=altered.Name{1};
            test.verifyError(@()csr.validation.MultiSeedCheckpoint.testResults(altered,rows.Name), ...
                'csr:t20:TestIdentity');
            altered=rows; altered.Incomplete(2)=true;
            summary=csr.validation.MultiSeedCheckpoint.testResults(altered,rows.Name);
            test.verifyFalse(summary.TestsPassed);
        end

        function copiedCompletedStagesSurviveAnInterruptedLaterCase(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            root=fullfile(folder,'installation'); old=fullfile(folder,'old'); fresh=fullfile(folder,'fresh');
            mkdir(fullfile(root,'evidence')); mkdir(fullfile(root,'scenarios','t20'));
            mkdir(old); mkdir(fresh);
            candidate=struct('Plan','scenarios/t20/plan.json');
            csr.validation.Artifacts.writeJson(fullfile(root,'evidence','tranche-20-candidate.json'),candidate);
            csr.validation.Artifacts.writeJson(fullfile(root,candidate.Plan),struct('Scope','fixture'));
            csr.validation.Artifacts.writeJson(fullfile(old,'source.json'),identity.SourceFiles);
            csr.validation.Artifacts.writeJson(fullfile(old,'references.json'),identity.ReferenceFiles);
            csr.validation.Artifacts.writeJson(fullfile(old,'metadata.json'), ...
                struct('Schema','csr-matlab-tranche-20-validation-v1','Runtime',identity.Runtime));
            copyfile(fullfile(root,'evidence','tranche-20-candidate.json'),fullfile(old,'candidate.json'));
            copyfile(fullfile(root,candidate.Plan),fullfile(old,'plan.json'));
            complete(old,'tests',identity); complete(old,'s129',identity);
            csr.validation.MultiSeedCheckpoint.begin(old,'s130',identity);
            for name={'source.json','references.json','candidate.json','plan.json','metadata.json'}
                copyfile(fullfile(old,name{1}),fullfile(fresh,name{1}));
            end
            for phase={'tests','s129'}
                copyfile(fullfile(old,phase{1}),fullfile(fresh,phase{1}));
            end
            before=csr.validation.Artifacts.fileInventory(fresh);
            csr.validation.MultiSeedCheckpoint.preflight(fresh,root,identity,candidate);
            [~,reused]=csr.validation.MultiSeedCheckpoint.begin(fresh,'s129',identity);
            test.verifyTrue(reused);
            test.verifyFalse(isfolder(fullfile(fresh,'s130')));
            test.verifyEqual(csr.validation.Artifacts.fileInventory(fresh),before);
            test.verifyTrue(isfile(fullfile(old,'s130','start.json')));
        end

        function pathsRejectTraversalButPermitMultipartFilenames(test)
            [folder,~,cleanup]=fixture(); %#ok<ASGLU>
            for relative={'../outside','/absolute','C:/absolute','a/../b','a//b','a\b'}
                test.verifyError(@()csr.validation.MultiSeedCheckpoint.checkedPath(folder,relative{1}),'csr:t20:Path');
            end
            path=fullfile(folder,'accepted.recipe.json');
            csr.validation.MultiSeedCheckpoint.writeText(path,'{}');
            test.verifyEqual(csr.validation.MultiSeedCheckpoint.checkedPath(folder,'accepted.recipe.json'), ...
                csr.validation.Artifacts.canonicalPath(path));
            root=fileparts(fileparts(mfilename('fullpath')));
            test.verifyError(@()run_tranche20_validation(root,struct('Phase','finalize')),'csr:t20:Output');
        end
    end
end

function [folder,identity,cleanup]=fixture()
folder=tempname; mkdir(folder); cleanup=onCleanup(@()rmdir(folder,'s'));
identity=struct('CandidateSHA256',repmat('a',1,64), ...
    'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'Runtime',struct('Runtime','MATLAB','Release','fixture'), ...
    'SourceFiles',struct('path','source.m','sha256',repmat('c',1,64)), ...
    'ReferenceFiles',struct('path','reference.json','sha256',repmat('d',1,64),'bytes',1));
end

function complete(folder,phase,identity)
csr.validation.MultiSeedCheckpoint.begin(folder,phase,identity);
summary=struct('Passed',true);
csr.validation.Artifacts.writeJson(fullfile(folder,phase,'summary.json'),summary);
csr.validation.MultiSeedCheckpoint.seal(folder,phase,identity,summary);
end
