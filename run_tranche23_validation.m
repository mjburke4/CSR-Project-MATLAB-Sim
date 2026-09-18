function report = run_tranche23_validation(outputRoot)
%RUN_TRANCHE23_VALIDATION Controlled integrated receiver-pressure and feedback diagnostic.
% Overlay T23 on the accepted T22 installation. No campus simulation runs.
% Each invocation preserves a fresh result directory, including failures.
root=fileparts(mfilename('fullpath')); addpath(root,'-begin');
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t23'); end
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
assertOutputPath(root,outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyMMdd_HHmmss'));
[~,token]=fileparts(tempname);
directory=fullfile(outputRoot,['r' stamp '_' token(max(1,end-5):end)]);
if isfolder(directory), error('csr:t23:OutputExists','Use a fresh output directory.'); end
[ok,message]=mkdir(directory);
if ~ok, error('csr:t23:Output','Cannot create output: %s.',message); end
logPath=fullfile(directory,'run.log'); diary(logPath);
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-23-validation-v1','Tranche',23, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'NativeExecuted',false,'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'CandidateFile','evidence/tranche-23-candidate.json','CandidateSHA256','', ...
    'SourceSnapshotSHA256','','ReferenceSnapshotSHA256','', ...
    'SourceFilesFinal',struct([]),'ReferenceFilesFinal',struct([]), ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'AllBaselineSourcesUnchanged',false,'BaselineSourceFilesVerified',0, ...
    'BaselineMatlabFilesVerified',0,'TestFiles',{{}},'ExpectedTestNames',{{}}, ...
    'TestsExecuted',false,'TestsPassed',false,'TestCount',0,'PassedTests',0, ...
    'FailedTests',0,'IncompleteTests',0,'TestResultsFile','tests.csv', ...
    'ContractCompleted',false,'ContractPassed',false,'ContractCaseCount',0, ...
    'ContractCheckpointCount',0,'ContractFailedCount',0, ...
    'ContractFeedbackCount',0,'ContractFeedbackFailedCount',0, ...
    'FocusedGateExecuted',false,'FullAcceptanceGateExecuted',false, ...
    'AcceptanceEstablished',false,'NumericalParityEstablished',false, ...
    'WorkingCampusBandPercent',10,'DiagnosticOnly',true,'EvidenceArchive','t23.zip', ...
    'InventoryExcludedPaths',{{'metadata.json','t23.zip'}},'Artifacts',struct([]), ...
    'Scope',['Controlled integrated NWK/HOP receiver pressure and emitted feedback. ' ...
    'Identical arrivals and downstream completions; naturally maintained custody. ' ...
    'Differences are preserved for review. No real PHY, campus rerun or parity acceptance.']);
snapshot=struct([]); references=struct([]); candidate=struct(); originalFailure=[];
try
    assertPackagePath(root);
    candidatePath=fullfile(root,report.CandidateFile);
    candidate=jsondecode(fileread(candidatePath));
    if ~strcmp(candidate.Schema,'csr-tranche-23-candidate-v1') || ...
            ~strcmp(candidate.SourceCommit,report.SourceCommit) || ...
            ~isequal(cellstr(string(candidate.SourceFilesExcludedPaths)),{report.CandidateFile})
        error('csr:t23:Candidate','Unexpected candidate identity or excluded paths.');
    end
    report.CandidateSHA256=csr.validation.Artifacts.sha256(candidatePath);
    snapshot=csr.validation.Artifacts.sourceSnapshot(root);
    bound=snapshot(~strcmp({snapshot.path},report.CandidateFile));
    if ~isequal(bound,candidate.SourceFiles)
        error('csr:t23:Candidate','Candidate source membership or hashes changed.');
    end
    verifyBaseline(root,candidate,snapshot);
    report.AllBaselineSourcesUnchanged=true;
    report.BaselineSourceFilesVerified=390; report.BaselineMatlabFilesVerified=178;
    references=referenceSnapshot(root,candidate);
    if ~strcmp(candidate.Plan,'scenarios/t23/plan.json') || ...
            ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.Plan)),candidate.PlanSHA256)
        error('csr:t23:Plan','The frozen replay plan changed.');
    end
    csr.validation.Artifacts.writeJson(fullfile(directory,'source.json'),snapshot);
    csr.validation.Artifacts.writeJson(fullfile(directory,'references.json'),references);
    copyfile(candidatePath,fullfile(directory,'candidate.json'));
    copyfile(fullfile(root,candidate.Plan),fullfile(directory,'plan.json'));
    report.SourceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'source.json'));
    report.ReferenceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'references.json'));
    report.TestFiles=cellstr(string(candidate.TestFiles));
    report.ExpectedTestNames=cellstr(string(candidate.ExpectedTestNames));
    if isempty(report.TestFiles) || numel(unique(report.TestFiles))~=numel(report.TestFiles)
        error('csr:t23:TestIdentity','Distinct frozen test classes are required.');
    end
    for k=1:numel(report.TestFiles)
        if isempty(regexp(report.TestFiles{k},'^tests/Test[A-Za-z0-9_]+\.m$','once'))
            error('csr:t23:TestIdentity','Only frozen top-level portable tests may run.');
        end
        csr.validation.ReleaseCheckpoint.checkedPath(root,report.TestFiles{k});
    end
    writeMetadata();
    fprintf('Tranche 23: controlled receiver-pressure and ACK/DACK diagnostic.\n');
    fprintf('All 390 accepted T22 sources are unchanged. No campus run.\n');
    fprintf('Running %d focused test methods.\n',numel(report.ExpectedTestNames));
    results=[];
    for k=1:numel(report.TestFiles)
        next=runtests(fullfile(root,report.TestFiles{k})); diary(logPath);
        if isempty(results), results=next(:); else, results=[results;next(:)]; end %#ok<AGROW>
        rows=table({results.Name}',[results.Passed]',[results.Failed]', ...
            [results.Incomplete]',[results.Duration]', ...
            'VariableNames',{'Name','Passed','Failed','Incomplete','DurationSeconds'});
        writetable(rows,fullfile(directory,'tests.csv'));
        report.TestsExecuted=true; report.TestCount=numel(results);
        report.PassedTests=sum([results.Passed]); report.FailedTests=sum([results.Failed]);
        report.IncompleteTests=sum([results.Incomplete]); writeMetadata();
    end
    actual=sort(string({results.Name})); expected=sort(string(report.ExpectedTestNames));
    if isempty(actual) || ~isequal(actual(:),expected(:)) || numel(unique(actual))~=numel(actual)
        error('csr:t23:TestIdentity','Executed test membership differs from the frozen candidate.');
    end
    report.TestsPassed=all([results.Passed]) && ~any([results.Failed]) && ~any([results.Incomplete]);
    writeMetadata();
    % Preserve the main replay checkpoints even when a focused assertion fails.
    % Those observed rows are needed to diagnose a real cross-engine mismatch.
    checkStableInputs();
    fprintf('Replaying the frozen action sequence against native reference states.\n');
    value=csr.validation.receiverFeedbackContract(fullfile(directory,'contract'),root);
    attachDiagnostic(value); writeMetadata();
    if ~report.ContractCompleted || ...
            report.ContractCaseCount~=candidate.ExpectedCaseCount || ...
            report.ContractCheckpointCount~=candidate.ExpectedCheckpointCount
        error('csr:t23:Contract','Controlled diagnostic did not complete its exact planned membership.');
    end
    if ~report.TestsPassed, error('csr:t23:Tests','Focused tests did not all pass.'); end
    checkStableInputs();
    report.FocusedGateExecuted=true;
    if report.ContractPassed
        report.Status='completed-review-required';
    else
        report.Status='completed-differences-review-required';
    end
catch failure
    originalFailure=failure; report.Status='failed'; report.Failure=failureRecord(failure);
    partial=fullfile(directory,'contract','summary.json');
    if isfile(partial)
        try, attachDiagnostic(jsondecode(fileread(partial))); catch, end %#ok<CTCH>
    end
    if ~isempty(snapshot) && ~isempty(references)
        try, checkStableInputs();
        catch inputFailure, report.InputCheckFailure=failureRecord(inputFailure); end
    end
    fprintf(2,'Tranche 23 failed: %s\n',failure.message);
end
report.CompletedUTC=csr.validation.Artifacts.utcNow(); diary('off');
try
    report.Artifacts=csr.validation.Artifacts.fileInventory(directory,{'metadata.json','t23.zip'});
    writeMetadata();
    zip(fullfile(directory,'t23.zip'),[{report.Artifacts.path},{'metadata.json'}],directory);
    fprintf('Upload %s for independent review.\n',fullfile(directory,'t23.zip'));
catch packagingFailure
    report.EvidencePackagingFailure=failureRecord(packagingFailure);
    try, writeMetadata(); catch, end %#ok<CTCH>
    fprintf(2,'Partial evidence remains at %s.\n',directory);
    if isempty(originalFailure), rethrow(packagingFailure); end
end
if ~isempty(originalFailure), rethrow(originalFailure); end
fprintf('Tranche 23 completed: %d tests, %d checkpoints and %d feedback records.\n', ...
    report.PassedTests,report.ContractCheckpointCount,report.ContractFeedbackCount);
fprintf('State differences: %d; feedback differences: %d. Return review required.\n', ...
    report.ContractFailedCount,report.ContractFeedbackFailedCount);

    function writeMetadata()
        csr.validation.Artifacts.writeJson(fullfile(directory,'metadata.json'),report);
    end
    function attachDiagnostic(value)
        report.ContractCompleted=value.DiagnosticCompleted; report.ContractPassed=value.Passed;
        report.ContractCaseCount=value.CaseCount; report.ContractCheckpointCount=value.CheckpointCount;
        report.ContractFailedCount=value.FailedCount;
        report.ContractFeedbackCount=value.FeedbackCount;
        report.ContractFeedbackFailedCount=value.FeedbackFailedCount;
        if logical(report.ContractPassed) ~= ...
                (report.ContractFailedCount==0 && report.ContractFeedbackFailedCount==0)
            error('csr:t23:Comparison','Diagnostic pass flag disagrees with state or feedback differences.');
        end
    end
    function checkStableInputs()
        report.SourceFilesFinal=csr.validation.Artifacts.sourceSnapshot(root);
        report.ReferenceFilesFinal=referenceSnapshot(root,candidate);
        report.SourceFilesStableDuringRun=isequal(snapshot,report.SourceFilesFinal);
        report.ReferenceFilesStableDuringRun=isequal(references,report.ReferenceFilesFinal);
        if ~report.SourceFilesStableDuringRun || ~report.ReferenceFilesStableDuringRun
            error('csr:t23:InputChanged','Source or reference files changed during execution.');
        end
    end
end

function verifyBaseline(root,candidate,snapshot)
path=csr.validation.ReleaseCheckpoint.checkedPath(root,candidate.BaselineSourceSnapshot);
if ~strcmp(candidate.BaseSourceSnapshotSHA256, ...
        'c5ca0672545bb213bd262d3d02f1008fd99d6c64e5355b8248ac102257477fd2') || ...
        ~strcmp(csr.validation.Artifacts.sha256(path),candidate.BaseSourceSnapshotSHA256)
    error('csr:t23:Baseline','The accepted T22 source inventory changed.');
end
baseline=jsondecode(fileread(path));
if ~strcmp(candidate.BaselineCandidate,'evidence/tranche-23-parent-candidate.json') || ...
        ~strcmp(candidate.BaselineCandidateSHA256, ...
        '333686e6ee7822baf9f53ad06a0aa1d6475fced46947281596704ff147b5ba06') || ...
        ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.BaselineCandidate)), ...
        candidate.BaselineCandidateSHA256) || ...
        ~strcmp(candidate.BaselineAcceptance,'evidence/t22/accepted/acceptance.json') || ...
        ~strcmp(candidate.BaselineAcceptanceSHA256, ...
        'ba3c50e96e150d6d92073edb20c490c595c2121e01dabbd5c0bcaac1ede08633') || ...
        ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.BaselineAcceptance)), ...
        candidate.BaselineAcceptanceSHA256)
    error('csr:t23:Baseline','The accepted T22 candidate or review identity changed.');
end

if numel(baseline)~=390 || sum(endsWith({baseline.path},'.m'))~=178 || ...
        numel(unique({baseline.path}))~=390
    error('csr:t23:Baseline','Expected 390 unchanged T22 sources, including 178 MATLAB files.');
end
for k=1:numel(baseline)
    match=find(strcmp({snapshot.path},baseline(k).path));
    if numel(match)~=1 || ~strcmp(snapshot(match).sha256,baseline(k).sha256)
        error('csr:t23:Baseline','Accepted source changed: %s.',baseline(k).path);
    end
end
end

function files=referenceSnapshot(root,candidate)
names=cellstr(string(candidate.ReferenceFiles));
if isempty(names) || numel(unique(names))~=numel(names) || ...
        ~isempty(candidate.ReferenceRoots)
    error('csr:t23:Reference','Distinct explicit reference files are required.');
end
files=repmat(struct('path','','sha256','','bytes',0),numel(names),1);
for k=1:numel(names)
    path=csr.validation.ReleaseCheckpoint.checkedPath(root,names{k}); info=dir(path);
    files(k)=struct('path',names{k},'sha256',csr.validation.Artifacts.sha256(path),'bytes',info.bytes);
end
[~,order]=sort({files.path}); files=files(order);
if ~isequal(files,candidate.ReferenceFileInventory)
    error('csr:t23:Reference','Frozen reference membership, hashes or sizes changed.');
end
end

function record=failureRecord(failure)
record=struct('Identifier',failure.identifier,'Message',failure.message,'Stack',failure.stack);
end

function assertOutputPath(root,output)
root=csr.validation.Artifacts.canonicalPath(root);
if strcmp(root,output) || startsWith(root,[output filesep])
    error('csr:t23:Output','Output must not be the installation or an ancestor.');
end
for name={'+csr','tests','examples','scripts','scenarios','data','evidence','docs'}
    protected=fullfile(root,name{1});
    if strcmp(output,protected) || startsWith(output,[protected filesep])
        error('csr:t23:Output','Output must not overwrite source or reference trees.');
    end
end
end

function assertPackagePath(root)
names={'csr.sim.EventScheduler','csr.sim.RandomStreams','csr.hop.Layer','csr.hop.Frames', ...
    'csr.nwk.Layer','csr.sim.ApplicationGenerator', ...
    'csr.validation.receiverFeedbackContract','csr.validation.Artifacts','csr.validation.ReleaseCheckpoint'};
for k=1:numel(names)
    parts=strsplit(names{k},'.'); folders=strcat('+',parts(1:end-1));
    expected=csr.validation.Artifacts.canonicalPath(fullfile(root,folders{:},[parts{end} '.m']));
    actual=which(names{k});
    if isempty(actual) || ~strcmp(expected,csr.validation.Artifacts.canonicalPath(actual))
        error('csr:t23:Path','A different installation is active for %s.',names{k});
    end
end
end
