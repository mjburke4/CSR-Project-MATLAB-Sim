classdef TestCampusReleaseGate < matlab.unittest.TestCase
    % Small fixtures exercise release evidence trust; no campus simulation.
    methods (Test)
        function phaseOptionsCannotAlterTheWorkload(test)
            options=csr.validation.ReleaseCheckpoint.options();
            test.verifyEqual(options.Phase,'all');
            for phase={'all','tests','campus','finalize'}
                options=csr.validation.ReleaseCheckpoint.options(struct('Phase',string(phase{1})));
                test.verifyEqual(options.Phase,phase{1});
            end
            for given={struct('RunTests',false),struct('DurationSeconds',4), ...
                    struct('Phase','resume'),struct('Phase',["tests","campus"]),[],false}
                test.verifyError(@()csr.validation.ReleaseCheckpoint.options(given{1}),'csr:t17:Options');
            end
        end

        function campusPlanPreservesTheOriginalBenchmark(test)
            [item,plan]=csr.scenario.tranche17Suite();
            [original,benchmarkPlan]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
            test.verifyEqual(item.Config,original.Config);
            test.verifyEqual(item.DurationSeconds,6000); test.verifyEqual(item.Seed,128);
            test.verifyEqual(item.StorageKey,'c');
            test.verifyEqual(item.Config.ApplicationFlowLimit,0);
            csr.validation.ReleaseCheckpoint.validatePlan(plan,item,benchmarkPlan.CatalogSHA256);
        end

        function changedCampusScopeFailsBeforeAnyRun(test)
            [item,plan]=csr.scenario.tranche17Suite();
            changes={'duration_s',4;'seed',129;'timing_policy','nanoseconds'; ...
                'observer_enabled',true;'phy_ecc_changed',true;'post_horizon_drain',true; ...
                'native_tests_included',true;'full_portable_regression',false; ...
                'scenario_sha256',repmat('0',1,64);'storage_key','different'};
            for k=1:size(changes,1)
                altered=plan; altered.(changes{k,1})=changes{k,2};
                test.verifyError(@()csr.validation.ReleaseCheckpoint.validatePlan( ...
                    altered,item,plan.catalog_sha256),'csr:t17:Plan');
            end
            item.Config.ApplicationFlowLimit=1;
            test.verifyError(@()csr.validation.ReleaseCheckpoint.validatePlan( ...
                plan,item,plan.catalog_sha256),'csr:t17:Plan');
        end

        function completedStageIsReusedWithoutWritingIt(test)
            [directory,identity,cleanup]=fixture(); %#ok<ASGLU>
            [~,reused]=csr.validation.ReleaseCheckpoint.begin(directory,'tests',identity);
            test.verifyFalse(reused);
            writeSummary(directory,'tests');
            csr.validation.ReleaseCheckpoint.seal(directory,'tests',identity,struct('Passed',true));
            before=csr.validation.Artifacts.fileInventory(fullfile(directory,'tests'));
            [receipt,reused]=csr.validation.ReleaseCheckpoint.begin(directory,'tests',identity);
            test.verifyTrue(reused); test.verifyEqual(receipt.status,'completed');
            test.verifyEqual(csr.validation.Artifacts.fileInventory(fullfile(directory,'tests')),before);
            test.verifyTrue(receipt.SourceFilesStableDuringRun);
            test.verifyTrue(receipt.ReferenceFilesStableDuringRun);
        end

        function incompleteStageIsPreservedAndCannotResume(test)
            [directory,identity,cleanup]=fixture(); %#ok<ASGLU>
            csr.validation.ReleaseCheckpoint.begin(directory,'campus',identity);
            csr.validation.ReleaseCheckpoint.writeText(fullfile(directory,'campus','partial.csv'),'partial evidence');
            before=csr.validation.Artifacts.fileInventory(fullfile(directory,'campus'));
            test.verifyError(@()csr.validation.ReleaseCheckpoint.begin(directory,'campus',identity), ...
                'csr:t17:IncompleteStage');
            test.verifyEqual(csr.validation.Artifacts.fileInventory(fullfile(directory,'campus')),before);
        end

        function candidateSourceReferenceAndRuntimeChangesRejectReuse(test)
            [directory,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(directory,'tests',identity);
            changed=identity; changed.CandidateSHA256=repmat('b',1,64);
            test.verifyError(@()csr.validation.ReleaseCheckpoint.verify(directory,'tests',changed),'csr:t17:Receipt');
            changed=identity; changed.SourceFiles.sha256=repmat('b',1,64);
            test.verifyError(@()csr.validation.ReleaseCheckpoint.verify(directory,'tests',changed),'csr:t17:Receipt');
            changed=identity; changed.ReferenceFiles.bytes=2;
            test.verifyError(@()csr.validation.ReleaseCheckpoint.verify(directory,'tests',changed),'csr:t17:Receipt');
            changed=identity; changed.Runtime.Release='different';
            test.verifyError(@()csr.validation.ReleaseCheckpoint.verify(directory,'tests',changed),'csr:t17:Receipt');
        end

        function changedReceiptChecksumBlocksReuse(test)
            [directory,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(directory,'tests',identity);
            path=fullfile(directory,'tests','receipt.json');
            value=jsondecode(fileread(path)); value.summary.Passed=false;
            csr.validation.Artifacts.writeJson(path,value);
            test.verifyError(@()csr.validation.ReleaseCheckpoint.verify(directory,'tests',identity),'csr:t17:Receipt');
        end

        function changedMissingOrExtraEvidenceBlocksReuse(test)
            [directory,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(directory,'tests',identity);
            path=fullfile(directory,'tests','summary.json'); original=fileread(path);
            csr.validation.ReleaseCheckpoint.writeText(path,'changed');
            test.verifyError(@()csr.validation.ReleaseCheckpoint.verify(directory,'tests',identity),'csr:t17:Receipt');
            fid=fopen(path,'w'); fprintf(fid,'%s',original); fclose(fid);
            extra=fullfile(directory,'tests','extra.csv');
            csr.validation.ReleaseCheckpoint.writeText(extra,'unexpected');
            test.verifyError(@()csr.validation.ReleaseCheckpoint.verify(directory,'tests',identity),'csr:t17:Receipt');
            delete(extra); delete(path);
            test.verifyError(@()csr.validation.ReleaseCheckpoint.verify(directory,'tests',identity),'csr:t17:Receipt');
        end

        function localSnapshotIsOptionalButCannotChange(test)
            [directory,identity,cleanup]=fixture(); %#ok<ASGLU>
            csr.validation.ReleaseCheckpoint.begin(directory,'campus',identity);
            writeSummary(directory,'campus');
            local=fullfile(directory,'campus','results.mat');
            csr.validation.ReleaseCheckpoint.writeText(local,'fixture snapshot');
            csr.validation.ReleaseCheckpoint.seal(directory,'campus',identity,struct('Passed',true));
            csr.validation.ReleaseCheckpoint.writeText(local,'changed snapshot');
            test.verifyError(@()csr.validation.ReleaseCheckpoint.verify(directory,'campus',identity),'csr:t17:Receipt');
            delete(local);
            receipt=csr.validation.ReleaseCheckpoint.verify(directory,'campus',identity);
            test.verifyEqual(receipt.status,'completed');
        end

        function completedStageCannotBeSealedAgain(test)
            [directory,identity,cleanup]=fixture(); %#ok<ASGLU>
            complete(directory,'tests',identity);
            test.verifyError(@()csr.validation.ReleaseCheckpoint.seal(directory,'tests',identity,struct()), ...
                'csr:t17:Stage');
        end

        function regressionRequiresEveryExactTestName(test)
            rows=table({'TestOne/first';'TestTwo/second'},true(2,1),false(2,1),false(2,1),[0;1], ...
                'VariableNames',{'Name','Passed','Failed','Incomplete','DurationSeconds'});
            expected=rows.Name;
            summary=csr.validation.ReleaseCheckpoint.testResults(rows,expected);
            test.verifyTrue(summary.TestsPassed); test.verifyEqual(summary.TestCount,2);
            test.verifyError(@()csr.validation.ReleaseCheckpoint.testResults(rows(1,:),expected),'csr:t17:TestIdentity');
            changed=rows; changed.Name{2}=changed.Name{1};
            test.verifyError(@()csr.validation.ReleaseCheckpoint.testResults(changed,expected),'csr:t17:TestIdentity');
            changed=rows; changed.Passed(2)=false; changed.Failed(2)=true;
            summary=csr.validation.ReleaseCheckpoint.testResults(changed,expected);
            test.verifyFalse(summary.TestsPassed); test.verifyEqual(summary.FailedTests,1);
            changed=rows; changed.Incomplete(2)=true;
            summary=csr.validation.ReleaseCheckpoint.testResults(changed,expected);
            test.verifyFalse(summary.TestsPassed);
        end

        function artifactPathsCannotEscapeTheirRoot(test)
            [directory,~,cleanup]=fixture(); %#ok<ASGLU>
            for path={'../outside','/absolute','C:/absolute','child/../../outside','child\outside'}
                test.verifyError(@()csr.validation.ReleaseCheckpoint.checkedPath(directory,path{1}),'csr:t17:Path');
            end
            root=fileparts(fileparts(mfilename('fullpath')));
            test.verifyError(@()run_tranche17_validation(root,struct('Phase','finalize')),'csr:t17:Output');
            test.verifyError(@()run_tranche17_validation(fullfile(root,'scenarios','t17'), ...
                struct('Phase','finalize')),'csr:t17:Output');
        end
    end
end

function [directory,identity,cleanup]=fixture()
directory=tempname; mkdir(directory);
cleanup=onCleanup(@()rmdir(directory,'s'));
identity=struct('CandidateSHA256',repmat('a',1,64), ...
    'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'Runtime',struct('Runtime','MATLAB','Release','fixture'), ...
    'SourceFiles',struct('path','source.m','sha256',repmat('c',1,64)), ...
    'ReferenceFiles',struct('path','reference.json','sha256',repmat('d',1,64),'bytes',1));
end

function writeSummary(directory,phase)
csr.validation.Artifacts.writeJson(fullfile(directory,phase,'summary.json'),struct('Passed',true));
end

function complete(directory,phase,identity)
csr.validation.ReleaseCheckpoint.begin(directory,phase,identity);
writeSummary(directory,phase);
csr.validation.ReleaseCheckpoint.seal(directory,phase,identity,struct('Passed',true));
end
