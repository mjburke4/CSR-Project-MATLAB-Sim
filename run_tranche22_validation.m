function report = run_tranche22_validation(outputRoot)
%RUN_TRANCHE22_VALIDATION Controlled adaptive HOP window contract replay.
% Overlay T22 on the accepted T20 installation. No campus simulation runs.
% Each invocation preserves a fresh result directory, including failures.
root=fileparts(mfilename('fullpath')); addpath(root,'-begin');
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t22'); end
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
assertOutputPath(root,outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyMMdd_HHmmss'));
[~,token]=fileparts(tempname);
directory=fullfile(outputRoot,['r' stamp '_' token(max(1,end-5):end)]);
if isfolder(directory), error('csr:t22:OutputExists','Use a fresh output directory.'); end
[ok,message]=mkdir(directory);
if ~ok, error('csr:t22:Output','Cannot create output: %s.',message); end
logPath=fullfile(directory,'run.log'); diary(logPath);
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-22-validation-v1','Tranche',22, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'NativeExecuted',false,'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'CandidateFile','evidence/tranche-22-candidate.json','CandidateSHA256','', ...
    'SourceSnapshotSHA256','','ReferenceSnapshotSHA256','', ...
    'SourceFilesFinal',struct([]),'ReferenceFilesFinal',struct([]), ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'AllBaselineSourcesUnchanged',false,'BaselineSourceFilesVerified',0, ...
    'BaselineMatlabFilesVerified',0,'TestFiles',{{}},'ExpectedTestNames',{{}}, ...
    'TestsExecuted',false,'TestsPassed',false,'TestCount',0,'PassedTests',0, ...
    'FailedTests',0,'IncompleteTests',0,'TestResultsFile','tests.csv', ...
    'ContractCompleted',false,'ContractPassed',false,'ContractCaseCount',0, ...
    'ContractCheckpointCount',0,'ContractFailedCount',0, ...
    'FocusedGateExecuted',false,'FullAcceptanceGateExecuted',false, ...
    'AcceptanceEstablished',false,'NumericalParityEstablished',false, ...
    'WorkingCampusBandPercent',10,'DiagnosticOnly',true,'EvidenceArchive','t22.zip', ...
    'InventoryExcludedPaths',{{'metadata.json','t22.zip'}},'Artifacts',struct([]), ...
    'Scope',['Controlled sends, actual transmit notifications and feedback through the ' ...
    'unchanged HOP layer. Exact discrete contract states, with declared clock tolerance. ' ...
    'No real PHY, network workload, campus rerun or new numerical-parity claim.']);
snapshot=struct([]); references=struct([]); candidate=struct(); originalFailure=[];
try
    assertPackagePath(root);
    candidatePath=fullfile(root,report.CandidateFile);
    candidate=jsondecode(fileread(candidatePath));
    if ~strcmp(candidate.Schema,'csr-tranche-22-candidate-v1') || ...
            ~strcmp(candidate.SourceCommit,report.SourceCommit) || ...
            ~isequal(cellstr(string(candidate.SourceFilesExcludedPaths)),{report.CandidateFile})
        error('csr:t22:Candidate','Unexpected candidate identity or excluded paths.');
    end
    report.CandidateSHA256=csr.validation.Artifacts.sha256(candidatePath);
    snapshot=csr.validation.Artifacts.sourceSnapshot(root);
    bound=snapshot(~strcmp({snapshot.path},report.CandidateFile));
    if ~isequal(bound,candidate.SourceFiles)
        error('csr:t22:Candidate','Candidate source membership or hashes changed.');
    end
    verifyBaseline(root,candidate,snapshot);
    report.AllBaselineSourcesUnchanged=true;
    report.BaselineSourceFilesVerified=376; report.BaselineMatlabFilesVerified=175;
    references=referenceSnapshot(root,candidate);
    if ~strcmp(candidate.Plan,'scenarios/t22/plan.json') || ...
            ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.Plan)),candidate.PlanSHA256)
        error('csr:t22:Plan','The frozen replay plan changed.');
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
        error('csr:t22:TestIdentity','Distinct frozen test classes are required.');
    end
    for k=1:numel(report.TestFiles)
        if isempty(regexp(report.TestFiles{k},'^tests/Test[A-Za-z0-9_]+\.m$','once'))
            error('csr:t22:TestIdentity','Only frozen top-level portable tests may run.');
        end
        csr.validation.ReleaseCheckpoint.checkedPath(root,report.TestFiles{k});
    end
    writeMetadata();
    fprintf('Tranche 22: controlled HOP adaptive-window replay.\n');
    fprintf('All 376 accepted T20 sources are unchanged. No campus run.\n');
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
        error('csr:t22:TestIdentity','Executed test membership differs from the frozen candidate.');
    end
    report.TestsPassed=all([results.Passed]) && ~any([results.Failed]) && ~any([results.Incomplete]);
    writeMetadata();
    % Preserve the main replay checkpoints even when a focused assertion fails.
    % Those observed rows are needed to diagnose a real cross-engine mismatch.
    checkStableInputs();
    fprintf('Replaying the frozen action sequence against native reference states.\n');
    value=csr.validation.adaptiveWindowContract(fullfile(directory,'contract'),root);
    attachDiagnostic(value); writeMetadata();
    if ~report.ContractCompleted || ~report.ContractPassed || report.ContractFailedCount~=0 || ...
            report.ContractCaseCount~=candidate.ExpectedCaseCount || ...
            report.ContractCheckpointCount~=candidate.ExpectedCheckpointCount
        error('csr:t22:Contract','Controlled replay or exact-state comparison did not pass.');
    end
    if ~report.TestsPassed, error('csr:t22:Tests','Focused tests did not all pass.'); end
    checkStableInputs();
    report.FocusedGateExecuted=true; report.Status='completed-review-required';
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
    fprintf(2,'Tranche 22 failed: %s\n',failure.message);
end
report.CompletedUTC=csr.validation.Artifacts.utcNow(); diary('off');
try
    report.Artifacts=csr.validation.Artifacts.fileInventory(directory,{'metadata.json','t22.zip'});
    writeMetadata();
    zip(fullfile(directory,'t22.zip'),[{report.Artifacts.path},{'metadata.json'}],directory);
    fprintf('Upload %s for independent review.\n',fullfile(directory,'t22.zip'));
catch packagingFailure
    report.EvidencePackagingFailure=failureRecord(packagingFailure);
    try, writeMetadata(); catch, end %#ok<CTCH>
    fprintf(2,'Partial evidence remains at %s.\n',directory);
    if isempty(originalFailure), rethrow(packagingFailure); end
end
if ~isempty(originalFailure), rethrow(originalFailure); end
fprintf('Tranche 22 completed: %d tests and %d replay checkpoints. Return review required.\n', ...
    report.PassedTests,report.ContractCheckpointCount);

    function writeMetadata()
        csr.validation.Artifacts.writeJson(fullfile(directory,'metadata.json'),report);
    end
    function attachDiagnostic(value)
        report.ContractCompleted=value.DiagnosticCompleted; report.ContractPassed=value.Passed;
        report.ContractCaseCount=value.CaseCount; report.ContractCheckpointCount=value.CheckpointCount;
        report.ContractFailedCount=value.FailedCount;
    end
    function checkStableInputs()
        report.SourceFilesFinal=csr.validation.Artifacts.sourceSnapshot(root);
        report.ReferenceFilesFinal=referenceSnapshot(root,candidate);
        report.SourceFilesStableDuringRun=isequal(snapshot,report.SourceFilesFinal);
        report.ReferenceFilesStableDuringRun=isequal(references,report.ReferenceFilesFinal);
        if ~report.SourceFilesStableDuringRun || ~report.ReferenceFilesStableDuringRun
            error('csr:t22:InputChanged','Source or reference files changed during execution.');
        end
    end
end

function verifyBaseline(root,candidate,snapshot)
path=csr.validation.ReleaseCheckpoint.checkedPath(root,candidate.BaselineSourceSnapshot);
if ~strcmp(csr.validation.Artifacts.sha256(path),candidate.BaseSourceSnapshotSHA256)
    error('csr:t22:Baseline','The accepted T20 source inventory changed.');
end
baseline=jsondecode(fileread(path));
if numel(baseline)~=376 || sum(endsWith({baseline.path},'.m'))~=175 || ...
        numel(unique({baseline.path}))~=376
    error('csr:t22:Baseline','Expected 376 unchanged T20 sources, including 175 MATLAB files.');
end
for k=1:numel(baseline)
    match=find(strcmp({snapshot.path},baseline(k).path));
    if numel(match)~=1 || ~strcmp(snapshot(match).sha256,baseline(k).sha256)
        error('csr:t22:Baseline','Accepted source changed: %s.',baseline(k).path);
    end
end
end

function files=referenceSnapshot(root,candidate)
names=cellstr(string(candidate.ReferenceFiles));
if isempty(names) || numel(unique(names))~=numel(names) || ...
        ~isempty(candidate.ReferenceRoots)
    error('csr:t22:Reference','Distinct explicit reference files are required.');
end
files=repmat(struct('path','','sha256','','bytes',0),numel(names),1);
for k=1:numel(names)
    path=csr.validation.ReleaseCheckpoint.checkedPath(root,names{k}); info=dir(path);
    files(k)=struct('path',names{k},'sha256',csr.validation.Artifacts.sha256(path),'bytes',info.bytes);
end
[~,order]=sort({files.path}); files=files(order);
if ~isequal(files,candidate.ReferenceFileInventory)
    error('csr:t22:Reference','Frozen reference membership, hashes or sizes changed.');
end
end

function record=failureRecord(failure)
record=struct('Identifier',failure.identifier,'Message',failure.message,'Stack',failure.stack);
end

function assertOutputPath(root,output)
root=csr.validation.Artifacts.canonicalPath(root);
if strcmp(root,output) || startsWith(root,[output filesep])
    error('csr:t22:Output','Output must not be the installation or an ancestor.');
end
for name={'+csr','tests','examples','scripts','scenarios','data','evidence','docs'}
    protected=fullfile(root,name{1});
    if strcmp(output,protected) || startsWith(output,[protected filesep])
        error('csr:t22:Output','Output must not overwrite source or reference trees.');
    end
end
end

function assertPackagePath(root)
names={'csr.sim.EventScheduler','csr.sim.RandomStreams','csr.hop.Layer','csr.hop.Frames', ...
    'csr.validation.adaptiveWindowContract','csr.validation.Artifacts','csr.validation.ReleaseCheckpoint'};
for k=1:numel(names)
    parts=strsplit(names{k},'.'); folders=strcat('+',parts(1:end-1));
    expected=csr.validation.Artifacts.canonicalPath(fullfile(root,folders{:},[parts{end} '.m']));
    actual=which(names{k});
    if isempty(actual) || ~strcmp(expected,csr.validation.Artifacts.canonicalPath(actual))
        error('csr:t22:Path','A different installation is active for %s.',names{k});
    end
end
end
