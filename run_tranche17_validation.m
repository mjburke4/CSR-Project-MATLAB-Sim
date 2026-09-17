function report = run_tranche17_validation(outputRoot,options)
%RUN_TRANCHE17_VALIDATION Full portable regression and unchanged campus6000.
% Phase: all (default), tests, campus, or finalize. Pass the SAME fixed output
% directory between phases. Only verified completed stages can be reused.
% Interrupted/failed stages remain intact; restart in a new output directory.
root=fileparts(mfilename('fullpath')); addpath(root,'-begin');
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t17'); end
if nargin<2, options=struct(); end
options=csr.validation.ReleaseCheckpoint.options(options);
directory=csr.validation.Artifacts.canonicalPath(outputRoot);
assertOutputPath(root,directory);
assertPackagePath(root);
[identity,candidate]=csr.validation.ReleaseCheckpoint.identity(root);
csr.scenario.tranche17Suite();
preflightExistingOutput(directory,root,identity,candidate);
if ~isfolder(directory)
    [ok,message]=mkdir(directory);
    if ~ok, error('csr:t17:Output','Cannot create output: %s.',message); end
end
lockPath=fullfile(directory,'.active');
lock=javaObject('java.io.File',lockPath);
if ~lock.createNewFile()
    error('csr:t17:ActiveRun','This output has an active or interrupted invocation; preserve it and use a new output directory.');
end
lockCleanup=onCleanup(@()delete(lockPath)); %#ok<NASGU>
[~,token]=fileparts(tempname);
logPath=fullfile(directory,['run_' token '.log']);
diary(logPath);
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-17-validation-v1','Tranche',17, ...
    'Status','running','Phase',options.Phase,'StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'NativeExecuted',false,'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'CandidateFile','evidence/tranche-17-candidate.json','CandidateSHA256','', ...
    'SourceSnapshotSHA256','','ReferenceSnapshotSHA256','', ...
    'SourceFilesFinal',struct([]),'ReferenceFilesFinal',struct([]), ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'BaselineSourceFilesVerified',0,'BaselineMatlabFilesVerified',0, ...
    'AllBaselineSourcesUnchanged',false,'TestFiles',{{}},'ExpectedTestNames',{{}}, ...
    'TestsExecuted',false,'TestsPassed',false,'TestCount',0,'PassedTests',0, ...
    'FailedTests',0,'IncompleteTests',0,'TestResultsFile','tests/results.csv', ...
    'CompletedCaseCount',0,'CampusCompleted',false,'CampusStructuralChecksPassed',false, ...
    'Cases',repmat(struct('CaseId','','Directory','','ManifestSHA256',''),0,1), ...
    'StageReceipts',repmat(struct('Phase','','File','','SHA256',''),0,1), ...
    'FullAcceptanceGateExecuted',false,'AcceptanceEstablished',false, ...
    'NumericalParityEstablished',false,'EvidenceArchive','t17.zip', ...
    'Artifacts',struct([]),'LocalArtifacts',struct([]), ...
    'InventoryExcludedPaths',{{'metadata.json','.active','t17.zip'}}, ...
    'Scope',['Full top-level portable MATLAB regression and one unchanged campus_multihop_6000 run. ' ...
        'Real PHY, autonomous routing, seed 128, default continuous transport. ' ...
        'Finite-stop pending work and bounded admission-trace omissions are reported. ' ...
        'Protocol and PHY traces must be complete. Acceptance and numerical parity require return review.']);
try
    report.CandidateSHA256=identity.CandidateSHA256;
    report.TestFiles=cellstr(string(candidate.TestFiles));
    report.ExpectedTestNames=cellstr(string(candidate.ExpectedTestNames));
    report.BaselineSourceFilesVerified=304; report.BaselineMatlabFilesVerified=155;
    report.AllBaselineSourcesUnchanged=true;
    writeOnceJson('source.json',identity.SourceFiles);
    writeOnceJson('references.json',identity.ReferenceFiles);
    copyOnce(candidate.Plan,'plan.json');
    copyOnce(report.CandidateFile,'candidate.json');
    report.SourceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'source.json'));
    report.ReferenceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'references.json'));
    writeMetadata();
    fprintf('Tranche 17 release gate, phase %s; %d expected portable tests.\n', ...
        options.Phase,numel(report.ExpectedTestNames));
    fprintf('All 304 prior source files verified unchanged, including 155 MATLAB files.\n');
    if ismember(options.Phase,{'all','tests'})
        [receipt,reused]=csr.validation.ReleaseCheckpoint.begin(directory,'tests',identity);
        if reused
            fprintf('Reusing the verified completed portable regression stage.\n');
        else
            fprintf('Running the full top-level portable test suite (native subfolder excluded).\n');
            results=runtests(fullfile(root,'tests'),'IncludeSubfolders',false);
            diary(logPath);
            rows=table({results.Name}',[results.Passed]',[results.Failed]', ...
                [results.Incomplete]',[results.Duration]', ...
                'VariableNames',{'Name','Passed','Failed','Incomplete','DurationSeconds'});
            writetable(rows,fullfile(directory,'tests','results.csv'));
            summary=csr.validation.ReleaseCheckpoint.testResults(rows,report.ExpectedTestNames,report.TestFiles);
            csr.validation.Artifacts.writeJson(fullfile(directory,'tests','summary.json'),summary);
            attachTestSummary(summary); writeMetadata();
            if ~summary.TestsPassed
                error('csr:t17:Tests','Full portable regression did not pass; failed evidence is preserved.');
            end
            checkStableInputs();
            receipt=csr.validation.ReleaseCheckpoint.seal(directory,'tests',identity,summary);
        end
        attachTests(receipt);
        writeMetadata();
    end
    if ismember(options.Phase,{'all','campus'})
        [receipt,reused]=csr.validation.ReleaseCheckpoint.begin(directory,'campus',identity);
        if reused
            fprintf('Reusing the verified completed 6000-second campus stage.\n');
        else
            summary=csr.validation.campusReleaseContract(fullfile(directory,'campus'), ...
                root,identity.SourceFiles,report.SourceSnapshotSHA256);
            checkStableInputs();
            receipt=csr.validation.ReleaseCheckpoint.seal(directory,'campus',identity,summary);
        end
        attachCampus(receipt);
        writeMetadata();
    end
    if ismember(options.Phase,{'all','finalize'})
        attachTests(csr.validation.ReleaseCheckpoint.verify(directory,'tests',identity));
        attachCampus(csr.validation.ReleaseCheckpoint.verify(directory,'campus',identity));
        report.FullAcceptanceGateExecuted=true;
        report.Status='completed-review-required';
    else
        % Include another already-completed phase without executing it.
        if isfile(fullfile(directory,'tests','receipt.json'))
            attachTests(csr.validation.ReleaseCheckpoint.verify(directory,'tests',identity));
        end
        if isfile(fullfile(directory,'campus','receipt.json'))
            attachCampus(csr.validation.ReleaseCheckpoint.verify(directory,'campus',identity));
        end
        report.Status='phase-completed-review-pending';
    end
    checkStableInputs();
    report.CompletedUTC=csr.validation.Artifacts.utcNow();
    diary('off'); finishEvidence();
    fprintf('Tranche 17 %s: %d/%d passing tests; %d/1 campus cases.\n', ...
        report.Status,report.PassedTests,report.TestCount,report.CompletedCaseCount);
    fprintf('Evidence: %s\n',fullfile(directory,'t17.zip'));
    fprintf('Return review is required; this runner does not establish acceptance or numerical parity.\n');
catch failure
    report.Status='failed'; report.CompletedUTC=csr.validation.Artifacts.utcNow();
    report.Failure=struct('Identifier',failure.identifier,'Message',failure.message,'Stack',failure.stack);
    diary('off');
    try
        finishEvidence();
    catch archiveFailure
        report.EvidencePackagingFailure=struct('Identifier',archiveFailure.identifier,'Message',archiveFailure.message);
        writeMetadata();
    end
    fprintf(2,'Tranche 17 failed: %s\nPartial evidence remains at %s.\n',failure.message,directory);
    rethrow(failure);
end

function preflightExistingOutput(directory,root,identity,candidate)
% A different candidate/runtime or damaged completed stage must never rewrite
% a previous run's outer metadata, archive or logs.
if ~isfolder(directory), return; end
for binding={'source.json',identity.SourceFiles;'references.json',identity.ReferenceFiles}'
    path=fullfile(directory,binding{1});
    if isfile(path) && ~isequal(jsondecode(fileread(path)),binding{2})
        error('csr:t17:OutputIdentity','Existing evidence has different source/reference inputs; use a new output directory.');
    end
end
for binding={'candidate.json','evidence/tranche-17-candidate.json';'plan.json',candidate.Plan}'
    path=fullfile(directory,binding{1});
    if isfile(path) && ~strcmp(csr.validation.Artifacts.sha256(path), ...
            csr.validation.Artifacts.sha256(fullfile(root,binding{2})))
        error('csr:t17:OutputIdentity','Existing evidence has a different frozen candidate or plan; use a new output directory.');
    end
end
for phase={'tests','campus'}
    if isfile(fullfile(directory,phase{1},'receipt.json'))
        csr.validation.ReleaseCheckpoint.verify(directory,phase{1},identity);
    end
end
end

    function writeMetadata()
        csr.validation.Artifacts.writeJson(fullfile(directory,'metadata.json'),report);
    end
    function writeOnceJson(relative,value)
        path=fullfile(directory,relative);
        if isfile(path)
            if ~isequal(jsondecode(fileread(path)),value)
                error('csr:t17:OutputIdentity','Existing %s belongs to different inputs; use a new output directory.',relative);
            end
        else
            csr.validation.Artifacts.writeJson(path,value);
        end
    end
    function copyOnce(relative,target)
        source=fullfile(root,relative); path=fullfile(directory,target);
        if isfile(path)
            if ~strcmp(csr.validation.Artifacts.sha256(path),csr.validation.Artifacts.sha256(source))
                error('csr:t17:OutputIdentity','Existing %s differs from the candidate.',target);
            end
        else
            [ok,message]=copyfile(source,path);
            if ~ok, error('csr:t17:Output','Cannot copy frozen input: %s.',message); end
        end
    end
    function checkStableInputs()
        current=csr.validation.ReleaseCheckpoint.identity(root);
        report.SourceFilesFinal=current.SourceFiles; report.ReferenceFilesFinal=current.ReferenceFiles;
        report.SourceFilesStableDuringRun=isequal(current.SourceFiles,identity.SourceFiles);
        report.ReferenceFilesStableDuringRun=isequal(current.ReferenceFiles,identity.ReferenceFiles);
        if ~isequal(current,identity)
            error('csr:t17:InputChanged','Candidate, source, reference or MATLAB runtime identity changed during execution.');
        end
    end
    function attachTestSummary(summary)
        for field={'TestsExecuted','TestsPassed','TestCount','PassedTests','FailedTests','IncompleteTests'}
            report.(field{1})=summary.(field{1});
        end
    end
    function attachTests(receipt)
        stored=jsondecode(fileread(fullfile(directory,'tests','summary.json')));
        rows=readtable(fullfile(directory,'tests','results.csv'),'TextType','string');
        computed=csr.validation.ReleaseCheckpoint.testResults(rows,report.ExpectedTestNames,report.TestFiles);
        % JSON normalizes row/column cell shape; compare the serialized shape.
        computed=jsondecode(jsonencode(computed));
        if ~isequal(jsondecode(jsonencode(receipt.summary)),stored) || ...
                ~isequal(stored,computed) || ~computed.TestsPassed
            error('csr:t17:Tests','The completed test receipt does not prove full passing membership.');
        end
        attachTestSummary(computed); addReceipt('tests');
    end
    function attachCampus(receipt)
        stored=jsondecode(fileread(fullfile(directory,'campus','summary.json')));
        if ~isequaln(jsondecode(jsonencode(receipt.summary)),stored) || ...
                ~strcmp(stored.Schema,'csr-tranche17-campus-release-summary-v1') || ...
                ~strcmp(stored.CaseId,'campus_multihop_6000') || ~strcmp(stored.StorageKey,'c') || ...
                stored.CompletedCaseCount~=1 || stored.DurationSeconds~=6000 || stored.SchedulerStopSeconds~=6000 || ...
                stored.Seed~=128 || ~stored.StructuralChecksPassed || ~stored.RealPHY || ...
                ~stored.AutonomousRouting || ~stored.DefaultContinuousTiming || stored.PostHorizonDrain || ...
                stored.ProtocolTraceOmissions~=0 || stored.PhyTraceOmissions~=0 || ...
                ~stored.Admissions.CountsComplete || stored.FiniteStopPendingIsFailure || ...
                stored.AcceptanceEstablished || stored.NumericalParityEstablished || ...
                ~strcmp(stored.Case.ManifestSHA256,csr.validation.Artifacts.sha256( ...
                    fullfile(directory,'campus','c','benchmark_manifest.json')))
            error('csr:t17:CampusCompletion','The completed campus receipt is incomplete or has a different release scope.');
        end
        report.CampusCompleted=true; report.CampusStructuralChecksPassed=true;
        report.CompletedCaseCount=1; report.Cases=stored.Case; addReceipt('campus');
    end
    function addReceipt(phase)
        relative=[phase '/receipt.json'];
        entry=struct('Phase',phase,'File',relative, ...
            'SHA256',csr.validation.Artifacts.sha256(fullfile(directory,relative)));
        selected=find(strcmp({report.StageReceipts.Phase},phase));
        if isempty(selected), report.StageReceipts(end+1,1)=entry;
        else, report.StageReceipts(selected)=entry; end
        [~,order]=sort(strcmp({report.StageReceipts.Phase},'campus'));
        report.StageReceipts=report.StageReceipts(order);
    end
    function finishEvidence()
        files=csr.validation.Artifacts.fileInventory(directory,{'metadata.json','.active','t17.zip'});
        local=endsWith({files.path},'.mat') | endsWith({files.path},'.zip');
        report.Artifacts=files(~local); report.LocalArtifacts=files(local);
        writeMetadata();
        zip(fullfile(directory,'t17.zip'),[{report.Artifacts.path},{'metadata.json'}],directory);
    end
end

function assertOutputPath(root,directory)
root=csr.validation.Artifacts.canonicalPath(root);
if strcmp(directory,root) || startsWith(root,[directory filesep])
    error('csr:t17:Output','Output must be a separate evidence directory, never the installation or its ancestor.');
end
for name={'+csr','tests','examples','scripts','data','scenarios','evidence'}
    protected=csr.validation.Artifacts.canonicalPath(fullfile(root,name{1}));
    if strcmp(directory,protected) || startsWith(directory,[protected filesep])
        error('csr:t17:Output','Output cannot overwrite a source or reference tree.');
    end
end
end

function assertPackagePath(root)
names={'csr.sim.NetworkSimulation','csr.sim.EventScheduler','csr.phy.SignalEngine', ...
    'csr.mac.Layer','csr.hop.Layer','csr.nwk.Layer','csr.analysis.researchSummary', ...
    'csr.analysis.performanceSummary','csr.analysis.benchmarkAggregates', ...
    'csr.validation.Artifacts','csr.validation.ReleaseCheckpoint', ...
    'csr.validation.campusReleaseContract','csr.scenario.benchmarkSuite','csr.scenario.tranche17Suite'};
for k=1:numel(names)
    parts=strsplit(names{k},'.'); packages=strcat('+',parts(1:end-1));
    expected=csr.validation.Artifacts.canonicalPath(fullfile(root,packages{:},[parts{end} '.m']));
    actual=which(names{k});
    if isempty(actual) || ~strcmp(expected,csr.validation.Artifacts.canonicalPath(actual))
        error('csr:t17:Path','A different installation is active for %s.',names{k});
    end
end
end
