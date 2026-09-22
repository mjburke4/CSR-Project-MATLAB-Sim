classdef TestTranche25Ensemble < matlab.unittest.TestCase
    % Fixed-workload and evidence-reuse contracts; no full campus simulation.
    methods (Test)
        function casesDifferOnlyInDeclaredSeeds(test)
            [cases,plan]=csr.scenario.tranche25Suite();
            [original,~]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
            test.verifyEqual({cases.CaseId},{'s131','s132'});
            test.verifyEqual([cases.Seed],[131 132]);
            test.verifyEqual({cases.Policy},{'actual-tx','actual-tx'});
            expected=original.Config; expected.Seed=131;
            test.verifyEqual(cases(1).Config,expected);
            expected=original.Config; expected.Seed=132;
            test.verifyEqual(cases(2).Config,expected);
            test.verifyEqual(cases(2).Config.Benchmark,original.Config.Benchmark);
            test.verifyEqual([cases.DurationSeconds],[6000 6000]);
            test.verifyEqual(plan.planned_simulated_seconds,12000);
        end

        function originalTrafficGeometryAndEvidenceBudgetsAreRetained(test)
            [cases,plan]=csr.scenario.tranche25Suite();
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
            [~,plan]=csr.scenario.tranche25Suite();
            [original,~]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
            changes={'observer_enabled',true;'full_portable_regression',false; ...
                'post_horizon_drain',true;'default_policy_changed',true; ...
                'phy_ecc_changed',true;'common_random_numbers_claimed',true; ...
                'planned_simulated_seconds',11999;'comparison_band_percent',5; ...
                'numerical_parity_required',true;'expected_admission_attempts',1710001; ...
                'runtime_must_equal_parent',true;'seed_override_after_import',false; ...
                'fresh_native_reference_seeds',[129 130];'reused_native_reference_seeds',128};
            for k=1:size(changes,1)
                altered=plan; altered.(changes{k,1})=changes{k,2};
                test.verifyError(@()csr.validation.EnsembleCheckpoint.validatePlan(altered,original),'csr:t25:Plan');
            end
            altered=plan; altered.cases(2).seed=128;
            test.verifyError(@()csr.validation.EnsembleCheckpoint.validatePlan(altered,original),'csr:t25:Plan');
            altered=plan; altered.cases(1).policy='native-provisional';
            test.verifyError(@()csr.validation.EnsembleCheckpoint.validatePlan(altered,original),'csr:t25:Plan');
        end

        function acceptedThreeSeedsAreReusedNeverScheduled(test)
            [cases,plan]=csr.scenario.tranche25Suite();
            test.verifyEqual([cases(1).Config.Seed cases(2).Config.Seed],[131 132]);
            test.verifyEqual(plan.reused_seeds(:),[128;129;130]);
            test.verifyEqual(plan.comparison_seeds(:),(128:132)');
            test.verifyEqual(plan.reused_campus_file,'evidence/t25/reused-campus.json');
            [original,~]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
            altered=plan; altered.reused_seeds=[128 129 131];
            test.verifyError(@()csr.validation.EnsembleCheckpoint.validatePlan(altered,original),'csr:t25:Plan');
            altered=plan; altered.cases(1).seed=128;
            test.verifyError(@()csr.validation.EnsembleCheckpoint.validatePlan(altered,original),'csr:t25:Plan');
        end

        function historicalRuntimeDifferencesAreReportedWithoutRelabeling(test)
            expected=struct('Runtime','MATLAB','Version','25.1.0.2943329 (R2025a)', ...
                'Release','2025a','DefaultBackend','portable');
            test.verifyTrue(csr.validation.EnsembleCheckpoint.validateRuntime(expected,expected));
            changed=expected; changed.Version='26.1.0.3346908 (R2026a)'; changed.Release='2026a';
            test.verifyFalse(csr.validation.EnsembleCheckpoint.validateRuntime(changed,expected));
            test.verifyEqual(expected.Release,'2025a');
            changed.DefaultBackend='wireless-clock';
            test.verifyError(@()csr.validation.EnsembleCheckpoint.validateRuntime(changed,expected),'csr:t25:Runtime');
            changed=rmfield(expected,'Version');
            test.verifyError(@()csr.validation.EnsembleCheckpoint.validateRuntime(expected,changed),'csr:t25:Runtime');
        end

        function reusedSourcesMustRemainCompatibleAndKeepHistoricIdentity(test)
            [folder,runtime,sources,references,cleanup]=reuseFixture(); %#ok<ASGLU>
            reused=csr.validation.EnsembleCheckpoint.reusedCases(folder,runtime,sources,references);
            test.verifyEqual([reused.Seed],[128 129 130]);
            test.verifyFalse(any([reused.FreshlyExecuted]));
            test.verifyTrue(all([reused.SourceBindingsUnchanged]));
            test.verifyEqual(reused(1).Runtime.Release,'2025a');
            test.verifyFalse(reused(1).RuntimeMatchesCurrent);
            test.verifyTrue(reused(2).RuntimeMatchesCurrent);
            changed=sources; changed.sha256=repmat('f',1,64);
            test.verifyError(@()csr.validation.EnsembleCheckpoint.reusedCases(folder,runtime,changed,references), ...
                'csr:t25:Reuse');
            changed=references; changed(1).sha256=repmat('f',1,64);
            test.verifyError(@()csr.validation.EnsembleCheckpoint.reusedCases(folder,runtime,sources,changed), ...
                'csr:t25:Reuse');
        end

        function phasesCannotOverrideScenarioParameters(test)
            for phase={'all','tests','s131','s132','finalize'}
                value=csr.validation.EnsembleCheckpoint.options(struct('Phase',string(phase{1})));
                test.verifyEqual(value.Phase,phase{1});
            end
            for value={struct('Phase','campus'),struct('Seed',131),struct('Phase','resume'),struct('Phase','a128'),struct('Phase','p128'),struct('Phase','s129'),struct('Phase','s130'), ...
                    struct('Phase',["s131","s132"]),struct('DurationSeconds',900),[]}
                test.verifyError(@()csr.validation.EnsembleCheckpoint.options(value{1}),'csr:t25:Options');
            end
        end

        function completedCasesReuseExactBytesIndependently(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(folder,'s131',identity);
            complete(folder,'s132',identity);
            before=csr.validation.Artifacts.fileInventory(folder);
            for phase={'s131','s132'}
                [receipt,reused]=csr.validation.EnsembleCheckpoint.begin(folder,phase{1},identity);
                test.verifyTrue(reused); test.verifyEqual(receipt.phase,phase{1});
            end
            test.verifyEqual(csr.validation.Artifacts.fileInventory(folder),before);
        end

        function partialCaseNeverResumesOrDamagesCompletedCase(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(folder,'s131',identity);
            csr.validation.EnsembleCheckpoint.begin(folder,'s132',identity);
            before=csr.validation.Artifacts.fileInventory(folder);
            test.verifyError(@()csr.validation.EnsembleCheckpoint.begin(folder,'s132',identity), ...
                'csr:t25:IncompleteStage');
            [~,reused]=csr.validation.EnsembleCheckpoint.begin(folder,'s131',identity);
            test.verifyTrue(reused);
            test.verifyEqual(csr.validation.Artifacts.fileInventory(folder),before);
        end

        function changedCandidateReferenceSourceOrRuntimeRejectsReuse(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(folder,'s131',identity);
            altered=identity; altered.CandidateSHA256=repmat('f',1,64);
            test.verifyError(@()csr.validation.EnsembleCheckpoint.verify(folder,'s131',altered),'csr:t25:Receipt');
            altered=identity; altered.SourceFiles.sha256=repmat('f',1,64);
            test.verifyError(@()csr.validation.EnsembleCheckpoint.verify(folder,'s131',altered),'csr:t25:Receipt');
            altered=identity; altered.ReferenceFiles.bytes=2;
            test.verifyError(@()csr.validation.EnsembleCheckpoint.verify(folder,'s131',altered),'csr:t25:Receipt');
            altered=identity; altered.Runtime.Release='different';
            test.verifyError(@()csr.validation.EnsembleCheckpoint.verify(folder,'s131',altered),'csr:t25:Receipt');
        end

        function changedOrAddedCaseBytesRejectReuse(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(folder,'s132',identity);
            extra=fullfile(folder,'s132','extra.csv');
            csr.validation.EnsembleCheckpoint.writeText(extra,'unrecorded');
            test.verifyError(@()csr.validation.EnsembleCheckpoint.verify(folder,'s132',identity),'csr:t25:Receipt');
            delete(extra);
            csr.validation.EnsembleCheckpoint.writeText(fullfile(folder,'s132','summary.json'),'changed');
            test.verifyError(@()csr.validation.EnsembleCheckpoint.verify(folder,'s132',identity),'csr:t25:Receipt');
        end

        function receiptChecksumAndPhaseCannotBeSubstituted(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(folder,'s131',identity);
            receiptPath=fullfile(folder,'s131','receipt.json');
            value=jsondecode(fileread(receiptPath)); value.phase='s132';
            csr.validation.Artifacts.writeJson(receiptPath,value);
            test.verifyError(@()csr.validation.EnsembleCheckpoint.verify(folder,'s131',identity),'csr:t25:Receipt');
            csr.validation.EnsembleCheckpoint.writeText(fullfile(folder,'s131','receipt.sha256'), ...
                csr.validation.Artifacts.sha256(receiptPath));
            test.verifyError(@()csr.validation.EnsembleCheckpoint.verify(folder,'s131',identity),'csr:t25:Receipt');
        end

        function unrelatedOutputIsRejectedBeforeWrites(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            csr.validation.EnsembleCheckpoint.writeText(fullfile(folder,'personal.txt'),'preserve');
            before=csr.validation.Artifacts.fileInventory(folder);
            test.verifyError(@()csr.validation.EnsembleCheckpoint.preflight(folder,folder,identity,struct()), ...
                'csr:t25:OutputIdentity');
            test.verifyEqual(csr.validation.Artifacts.fileInventory(folder),before);
        end

        function incompleteRootIdentityIsRejectedBeforeWrites(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            csr.validation.Artifacts.writeJson(fullfile(folder,'source.json'),identity.SourceFiles);
            before=csr.validation.Artifacts.fileInventory(folder);
            test.verifyError(@()csr.validation.EnsembleCheckpoint.preflight(folder,folder,identity,struct()), ...
                'csr:t25:OutputIdentity');
            test.verifyEqual(csr.validation.Artifacts.fileInventory(folder),before);
        end

        function everyExactPortableTestNameIsRequired(test)
            rows=table({'One/a';'Two/b'},true(2,1),false(2,1),false(2,1),[0;1], ...
                'VariableNames',{'Name','Passed','Failed','Incomplete','DurationSeconds'});
            summary=csr.validation.EnsembleCheckpoint.testResults(rows,rows.Name);
            test.verifyTrue(summary.TestsPassed);
            test.verifyEqual(summary.Schema,'csr-tranche25-portable-tests-summary-v1');
            test.verifyError(@()csr.validation.EnsembleCheckpoint.testResults(rows(1,:),rows.Name), ...
                'csr:t25:TestIdentity');
            altered=rows; altered.Name{2}=altered.Name{1};
            test.verifyError(@()csr.validation.EnsembleCheckpoint.testResults(altered,rows.Name), ...
                'csr:t25:TestIdentity');
            altered=rows; altered.Incomplete(2)=true;
            summary=csr.validation.EnsembleCheckpoint.testResults(altered,rows.Name);
            test.verifyFalse(summary.TestsPassed);
        end

        function copiedCompletedStagesSurviveAnInterruptedLaterCase(test)
            [folder,identity,cleanup]=fixture(); %#ok<ASGLU>
            root=fullfile(folder,'installation'); old=fullfile(folder,'old'); fresh=fullfile(folder,'fresh');
            mkdir(fullfile(root,'evidence')); mkdir(fullfile(root,'scenarios','t25'));
            mkdir(old); mkdir(fresh);
            candidate=struct('Plan','scenarios/t25/plan.json');
            csr.validation.Artifacts.writeJson(fullfile(root,'evidence','tranche-25-candidate.json'),candidate);
            csr.validation.Artifacts.writeJson(fullfile(root,candidate.Plan),struct('Scope','fixture'));
            csr.validation.Artifacts.writeJson(fullfile(old,'source.json'),identity.SourceFiles);
            csr.validation.Artifacts.writeJson(fullfile(old,'references.json'),identity.ReferenceFiles);
            csr.validation.Artifacts.writeJson(fullfile(old,'metadata.json'), ...
                struct('Schema','csr-matlab-tranche-25-validation-v1','Runtime',identity.Runtime));
            copyfile(fullfile(root,'evidence','tranche-25-candidate.json'),fullfile(old,'candidate.json'));
            copyfile(fullfile(root,candidate.Plan),fullfile(old,'plan.json'));
            complete(old,'tests',identity); complete(old,'s131',identity);
            csr.validation.EnsembleCheckpoint.begin(old,'s132',identity);
            for name={'source.json','references.json','candidate.json','plan.json','metadata.json'}
                copyfile(fullfile(old,name{1}),fullfile(fresh,name{1}));
            end
            for phase={'tests','s131'}
                copyfile(fullfile(old,phase{1}),fullfile(fresh,phase{1}));
            end
            before=csr.validation.Artifacts.fileInventory(fresh);
            csr.validation.EnsembleCheckpoint.preflight(fresh,root,identity,candidate);
            [~,reused]=csr.validation.EnsembleCheckpoint.begin(fresh,'s131',identity);
            test.verifyTrue(reused);
            test.verifyFalse(isfolder(fullfile(fresh,'s132')));
            test.verifyEqual(csr.validation.Artifacts.fileInventory(fresh),before);
            test.verifyTrue(isfile(fullfile(old,'s132','start.json')));
        end

        function pathsRejectTraversalButPermitMultipartFilenames(test)
            [folder,~,cleanup]=fixture(); %#ok<ASGLU>
            for relative={'../outside','/absolute','C:/absolute','a/../b','a//b','a\b'}
                test.verifyError(@()csr.validation.EnsembleCheckpoint.checkedPath(folder,relative{1}),'csr:t25:Path');
            end
            path=fullfile(folder,'accepted.recipe.json');
            csr.validation.EnsembleCheckpoint.writeText(path,'{}');
            test.verifyEqual(csr.validation.EnsembleCheckpoint.checkedPath(folder,'accepted.recipe.json'), ...
                csr.validation.Artifacts.canonicalPath(path));
            root=fileparts(fileparts(mfilename('fullpath')));
            test.verifyError(@()run_tranche25_validation(root,struct('Phase','finalize')),'csr:t25:Output');
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
csr.validation.EnsembleCheckpoint.begin(folder,phase,identity);
summary=struct('Passed',true);
csr.validation.Artifacts.writeJson(fullfile(folder,phase,'summary.json'),summary);
csr.validation.EnsembleCheckpoint.seal(folder,phase,identity,summary);
end

function [folder,runtime,sources,references,cleanup]=reuseFixture()
folder=tempname; mkdir(folder); cleanup=onCleanup(@()rmdir(folder,'s'));
mkdir(fullfile(folder,'scenarios','t25')); mkdir(fullfile(folder,'evidence','t25'));
runtime=struct('Runtime','MATLAB','Version','26.1 fixture','Release','2026a','DefaultBackend','portable');
sources=struct('path','production.m','sha256',repmat('c',1,64));
csr.validation.Artifacts.writeJson(fullfile(folder,'evidence','source.json'),sources);
for name={'owner.zip','candidate.json','acceptance.json'}
    csr.validation.EnsembleCheckpoint.writeText(fullfile(folder,'evidence',name{1}),'fixture');
end
keys={'a128','s129','s130'};
value=struct('case_id','','seed',0,'policy','actual-tx','fresh_execution',false, ...
    'duration_s',6000,'scenario_sha256',repmat('a',1,64), ...
    'owner_file','evidence/owner.zip','owner_sha256','', ...
    'candidate_file','evidence/candidate.json','candidate_sha256','', ...
    'acceptance_file','evidence/acceptance.json','acceptance_sha256','', ...
    'source_snapshot_file','evidence/source.json','source_snapshot_sha256','','runtime',runtime);
for role={'owner','candidate','acceptance','source_snapshot'}
    value.([role{1} '_sha256'])=csr.validation.Artifacts.sha256(fullfile(folder,value.([role{1} '_file'])));
end
cases=repmat(value,3,1);
for k=1:3, cases(k).case_id=keys{k}; cases(k).seed=127+k; end
cases(1).runtime.Version='25.1 fixture'; cases(1).runtime.Release='2025a';
record=struct('schema','csr-tranche25-reused-campus-v1','seeds',[128 129 130],'cases',cases);
recordPath='evidence/t25/reused-campus.json';
csr.validation.Artifacts.writeJson(fullfile(folder,recordPath),record);
plan=struct('reused_campus_file',recordPath, ...
    'reused_campus_sha256',csr.validation.Artifacts.sha256(fullfile(folder,recordPath)), ...
    'scenario_sha256',value.scenario_sha256);
csr.validation.Artifacts.writeJson(fullfile(folder,'scenarios','t25','plan.json'),plan);
references=csr.validation.Artifacts.fileInventory(folder);
end
