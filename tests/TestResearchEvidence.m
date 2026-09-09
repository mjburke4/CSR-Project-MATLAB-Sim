classdef TestResearchEvidence < matlab.unittest.TestCase
    methods (Test)
        function finiteHorizonReportsCustodyWithoutInventingLoss(test)
            result = pendingResult();
            row = csr.analysis.researchSummary(result);
            test.verifyEqual(row.Generated,1);
            test.verifyEqual(row.Pending,1);
            test.verifyEqual(row.Dropped,0);
            test.verifyTrue(row.StructuralChecksPassed);
            test.verifyFalse(row.DataDrained);
            test.verifyTrue(isnan(row.LatencyP95Seconds));
        end
        function rejectsUnbalancedApplications(test)
            result = pendingResult();
            result.Statistics.Pending = 0;
            test.verifyError(@() csr.analysis.researchSummary(result),'csr:research:Accounting');
        end
        function rejectsUnbalancedReceiverAccounting(test)
            result = pendingResult();
            result.Statistics.PhysicalAttempts = 1;
            test.verifyError(@() csr.analysis.researchSummary(result),'csr:research:Accounting');
        end
        function rejectsTraceTruncation(test)
            result = pendingResult();
            result.Statistics.OmittedTraceRecords = 1;
            test.verifyError(@() csr.analysis.researchSummary(result),'csr:research:TruncatedTrace');
        end
        function rejectsMissingGenerationEvidence(test)
            result = pendingResult();
            result.ProtocolTrace(strcmp(result.ProtocolTrace.Event,'app_generate'),:) = [];
            test.verifyError(@() csr.analysis.researchSummary(result),'csr:research:TraceIdentity');
        end
        function sha256PreservesHighBytesAndWindowsNewlines(test)
            path = tempname;
            cleanup = onCleanup(@() delete(path)); %#ok<NASGU>
            fid = fopen(path,'wb');
            fwrite(fid,uint8([0 127 128 255 13 10]),'uint8'); fclose(fid);
            test.verifyEqual(csr.validation.Artifacts.sha256(path), ...
                '07dea4342ef71489193fa85cbd5390dd56e5308daf50397921d561fd9882e2dd');
        end
        function rejectsAccidentalLongRunAndUnknownRunnerOption(test)
            test.verifyError(@() run_tranche4_validation(tempname, ...
                struct('ResearchScenarios',{{'long_run_6000'}})),'csr:validation:LongRun');
            test.verifyError(@() run_tranche4_validation(tempname, ...
                struct('IncludeLongRuns',true)),'csr:validation:Options');
        end
        function inventoryUsesPathsRelativeToItsDirectory(test)
            previous = pwd; folder = tempname; mkdir(folder);
            cleanup = onCleanup(@() restoreFolder(previous,folder)); %#ok<NASGU>
            cd(folder); mkdir('case');
            csr.validation.Artifacts.writeJson(fullfile('case','summary.json'),struct('value',1));
            files = csr.validation.Artifacts.fileInventory('case');
            test.assertEqual({files.path},{'summary.json'});
            test.verifyEqual(files.sha256,csr.validation.Artifacts.sha256(fullfile('case','summary.json')));
        end
        function compactEvidenceInventoryKeepsMatObjectsLocal(test)
            root = fileparts(fileparts(mfilename('fullpath')));
            directory = tempname;
            cleanup = onCleanup(@() removeDirectory(directory)); %#ok<NASGU>
            snapshot = csr.validation.Artifacts.sourceSnapshot(root);
            [~,manifest] = csr.validation.exportResearchCase(pendingResult(),directory,root,snapshot);
            test.verifyFalse(any(endsWith({manifest.files.path},'.mat')));
            test.verifyTrue(ismember('results.mat',{manifest.local_files.path}));
            test.verifyTrue(ismember('protocol_trace.csv',{manifest.files.path}));
            for k = 1:numel(manifest.files)
                test.verifyTrue(isfile(fullfile(directory,manifest.files(k).path)));
            end
        end
        function sha256HandlesEmptyAndSingleByteFiles(test)
            path = tempname;
            cleanup = onCleanup(@() delete(path)); %#ok<NASGU>
            fid = fopen(path,'wb'); fclose(fid);
            test.verifyEqual(csr.validation.Artifacts.sha256(path), ...
                'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');
            fid = fopen(path,'wb'); fwrite(fid,uint8(128),'uint8'); fclose(fid);
            test.verifyEqual(csr.validation.Artifacts.sha256(path), ...
                '76be8b528d0075f7aae98d6fa57a6d3c83ae480a8469e668d7b0af968995ac71');
        end
        function failedRunPreservesOriginalErrorUnderRelativeOutputRoot(test)
            previous = pwd; folder = tempname; mkdir(folder);
            diaryState = get(0,'Diary');
            diaryFile = csr.validation.Artifacts.canonicalPath(get(0,'DiaryFile'));
            diaryCleanup = onCleanup(@() restoreDiary(diaryState,diaryFile)); %#ok<NASGU>
            cleanup = onCleanup(@() restoreFolder(previous,folder)); %#ok<NASGU>
            cd(folder);
            options = struct('RunTests',false,'ResearchScenarios',{{}}, ...
                'SharedScenarios',{{'unknown_case'}});
            test.verifyError(@() run_tranche4_validation('relative_results',options),'csr:validation:Catalog');
            runs = dir(fullfile(folder,'relative_results','run_*'));
            test.assertNumElements(runs,1);
            directory = fullfile(runs.folder,runs.name);
            metadata = jsondecode(fileread(fullfile(directory,'validation_metadata.json')));
            test.verifyEqual(metadata.Status,'failed');
            test.verifyEqual(metadata.Failure.Identifier,'csr:validation:Catalog');
            test.verifyFalse(metadata.TestsExecuted);
            test.verifyEqual(metadata.EvidenceDirectory,csr.validation.Artifacts.canonicalPath(directory));
            test.verifyTrue(isfile(fullfile(directory,'tranche4_evidence.zip')));
            test.verifyFalse(isfield(metadata,'EvidenceWriteFailure'));
            test.verifyEmpty(metadata.Artifacts);
        end
    end
end

function result = pendingResult()
config = csr.scenario.routedNetwork('autonomous');
config.Nwk.StartupMode = 'manual';
config.DurationSeconds = 0.1;
config.Traffic.StartSeconds = 0.01;
config.Traffic.PacketCount = 1;
result = csr.runScenario(config);
end

function restoreFolder(previous,folder)
cd(previous);
if isfolder(folder), rmdir(folder,'s'); end
end

function removeDirectory(folder)
if isfolder(folder), rmdir(folder,'s'); end
end

function restoreDiary(state,path)
if strcmp(state,'on'), diary(path); else, diary('off'); end
end
