function report = run_tranche27_validation(outputRoot)
%RUN_TRANCHE27_VALIDATION Bounded deterministic discovery-controller diagnostic.
% Overlay T27 on an accepted T25 installation. T26 was an offline review.
% No campus simulation runs. Each invocation preserves a fresh evidence set.
root=fileparts(mfilename('fullpath')); addpath(root,'-begin');
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t27'); end
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
assertOutputPath(root,outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyMMdd_HHmmss'));
[~,token]=fileparts(tempname);
directory=fullfile(outputRoot,['r' stamp '_' token(max(1,end-5):end)]);
if isfolder(directory), error('csr:t27:OutputExists','Use a fresh evidence directory.'); end
[ok,message]=mkdir(directory);
if ~ok, error('csr:t27:Output','Cannot create output: %s.',message); end
logPath=fullfile(directory,'run.log'); diary(logPath);
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
started=tic;
report=struct('Schema','csr-matlab-tranche-27-validation-v1','Tranche',27, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'NativeExecuted',false,'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'CandidateFile','evidence/tranche-27-candidate.json','CandidateSHA256','', ...
    'SourceSnapshotSHA256','','ReferenceSnapshotSHA256','', ...
    'SourceFilesFinal',struct([]),'ReferenceFilesFinal',struct([]), ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'AllBaselineSourcesUnchanged',false,'BaselineSourceFilesVerified',0, ...
    'BaselineMatlabFilesVerified',0,'TestFiles',{{}},'ExpectedTestNames',{{}}, ...
    'TestsExecuted',false,'TestsPassed',false,'TestCount',0,'PassedTests',0, ...
    'FailedTests',0,'IncompleteTests',0,'TestResultsFile','tests.csv', ...
    'ContractCompleted',false,'ContractStructuralPassed',false,'ContractMatchesNative',false, ...
    'ContractCaseCount',0,'ContractCheckpointCount',0,'ContractControlCount',0, ...
    'ContractDifferingCaseCount',0,'ContractDifferingControlRows',0, ...
    'ContractSummaryFile','contract-summary.json','PrivateControllerStateAvailable',false, ...
    'CrossEngineComparisonScope','ordered_logical_SNMP_controls', ...
    'FocusedGateExecuted',false,'FullAcceptanceGateExecuted',false, ...
    'AcceptanceEstablished',false,'NumericalParityEstablished',false, ...
    'WorkingCampusBandPercent',10,'DiagnosticOnly',true,'CampusExecuted',false, ...
    'ProductionChanges',false,'EvidenceArchive','t27.zip', ...
    'InventoryExcludedPaths',{{'metadata.json','t27.zip'}},'Artifacts',struct([]), ...
    'Scope',['Five deterministic executions of four discovery-controller fixtures. ' ...
    'Real MATLAB NWK and scheduler with prescribed usable peers and DONE arrivals. ' ...
    'Logical controls go to a sink; no PHY, stochastic workload or campus run. ' ...
    'Observed cross-engine differences require review and do not fail structural completion.']);
snapshot=struct([]); references=struct([]); candidate=struct(); originalFailure=[];
try
    assertPackagePath(root);
    candidatePath=fullfile(root,report.CandidateFile);
    candidate=jsondecode(fileread(candidatePath));
    if ~strcmp(candidate.Schema,'csr-tranche-27-candidate-v1') || ...
            ~strcmp(candidate.SourceCommit,report.SourceCommit) || ...
            ~isequal(cellstr(string(candidate.SourceFilesExcludedPaths)),{report.CandidateFile})
        error('csr:t27:Candidate','Unexpected candidate identity or excluded paths.');
    end
    report.CandidateSHA256=csr.validation.Artifacts.sha256(candidatePath);
    snapshot=csr.validation.Artifacts.sourceSnapshot(root);
    bound=snapshot(~strcmp({snapshot.path},report.CandidateFile));
    if ~isequal(bound,candidate.SourceFiles)
        error('csr:t27:Candidate','Candidate source membership or hashes changed.');
    end
    verifyBaseline(root,candidate,snapshot);
    report.AllBaselineSourcesUnchanged=true;
    report.BaselineSourceFilesVerified=420; report.BaselineMatlabFilesVerified=186;
    references=referenceSnapshot(root,candidate);
    if ~strcmp(candidate.Plan,'evidence/tranche-27-plan.json') || ...
            ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.Plan)),candidate.PlanSHA256)
        error('csr:t27:Plan','The frozen discovery-controller plan changed.');
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
        error('csr:t27:TestIdentity','Distinct frozen test classes are required.');
    end
    for k=1:numel(report.TestFiles)
        if isempty(regexp(report.TestFiles{k},'^tests/Test[A-Za-z0-9_]+\.m$','once'))
            error('csr:t27:TestIdentity','Only frozen top-level portable tests may run.');
        end
        csr.validation.ReleaseCheckpoint.checkedPath(root,report.TestFiles{k});
    end
    writeMetadata();
    fprintf('Tranche 27: five small deterministic discovery-controller executions.\n');
    fprintf('All 420 accepted T25 sources are unchanged. No campus run.\n');
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
        error('csr:t27:TestIdentity','Executed test membership differs from the frozen candidate.');
    end
    report.TestsPassed=all([results.Passed]) && ~any([results.Failed]) && ~any([results.Incomplete]);
    writeMetadata(); checkStableInputs();
    % Preserve diagnostic outputs even if a focused regression assertion fails.
    fprintf('Running the five controlled executions and exporting public state.\n');
    value=csr.validation.discoveryControllerContract(directory,root);
    attachDiagnostic(value); writeMetadata();
    if ~report.ContractCompleted || ~report.ContractStructuralPassed || ...
            report.ContractCaseCount~=candidate.ExpectedCaseCount || ...
            report.ContractCheckpointCount~=candidate.ExpectedCheckpointCount
        error('csr:t27:Contract','The controlled diagnostic failed its exact structural membership.');
    end
    if ~report.TestsPassed, error('csr:t27:Tests','Focused tests did not all pass.'); end
    checkStableInputs(); report.FocusedGateExecuted=true;
    if report.ContractMatchesNative
        report.Status='completed-review-required';
    else
        report.Status='completed-differences-review-required';
    end
catch failure
    originalFailure=failure; report.Status='failed'; report.Failure=failureRecord(failure);
    partial=fullfile(directory,report.ContractSummaryFile);
    if isfile(partial)
        try, attachDiagnostic(jsondecode(fileread(partial))); catch, end %#ok<CTCH>
    end
    if ~isempty(snapshot) && ~isempty(references)
        try, checkStableInputs();
        catch inputFailure, report.InputCheckFailure=failureRecord(inputFailure); end
    end
    fprintf(2,'Tranche 27 failed: %s\n',failure.message);
end
report.CompletedUTC=csr.validation.Artifacts.utcNow();
report.ElapsedSeconds=toc(started); diary('off');
try
    report.Artifacts=csr.validation.Artifacts.fileInventory(directory,{'metadata.json','t27.zip'});
    writeMetadata();
    zip(fullfile(directory,'t27.zip'),[{report.Artifacts.path},{'metadata.json'}],directory);
    copyfile(fullfile(directory,'t27.zip'),fullfile(outputRoot,'t27.zip'),'f');
    fprintf('Upload %s for independent review.\n',fullfile(outputRoot,'t27.zip'));
    fprintf('This invocation is also preserved in %s.\n',directory);
catch packagingFailure
    report.EvidencePackagingFailure=failureRecord(packagingFailure);
    try, writeMetadata(); catch, end %#ok<CTCH>
    fprintf(2,'Partial evidence remains at %s.\n',directory);
    if isempty(originalFailure), rethrow(packagingFailure); end
end
if ~isempty(originalFailure), rethrow(originalFailure); end
fprintf('Tranche 27 completed: %d tests, %d executions and %d public-state checkpoints.\n', ...
    report.PassedTests,report.ContractCaseCount,report.ContractCheckpointCount);
fprintf('Logical-control differences: %d cases, %d rows. Independent review is required.\n', ...
    report.ContractDifferingCaseCount,report.ContractDifferingControlRows);

    function writeMetadata()
        csr.validation.Artifacts.writeJson(fullfile(directory,'metadata.json'),report);
    end
    function attachDiagnostic(value)
        report.ContractCompleted=value.DiagnosticCompleted;
        report.ContractStructuralPassed=value.StructuralPassed;
        report.ContractMatchesNative=value.CrossEngineMatchesNative;
        report.ContractCaseCount=value.CaseCount;
        report.ContractCheckpointCount=value.CheckpointCount;
        report.ContractControlCount=value.ControlCount;
        report.ContractDifferingCaseCount=value.DifferingCaseCount;
        report.ContractDifferingControlRows=value.DifferingControlRows;
        if logical(report.ContractMatchesNative)~= ...
                (report.ContractDifferingCaseCount==0 && report.ContractDifferingControlRows==0)
            error('csr:t27:Comparison','Logical-control summary disagrees with its difference counts.');
        end
    end
    function checkStableInputs()
        report.SourceFilesFinal=csr.validation.Artifacts.sourceSnapshot(root);
        report.ReferenceFilesFinal=referenceSnapshot(root,candidate);
        report.SourceFilesStableDuringRun=isequal(snapshot,report.SourceFilesFinal);
        report.ReferenceFilesStableDuringRun=isequal(references,report.ReferenceFilesFinal);
        if ~report.SourceFilesStableDuringRun || ~report.ReferenceFilesStableDuringRun
            error('csr:t27:InputChanged','Source or reference files changed during execution.');
        end
    end
end

function verifyBaseline(root,candidate,snapshot)
path=csr.validation.ReleaseCheckpoint.checkedPath(root,candidate.BaselineSourceSnapshot);
if ~strcmp(candidate.BaselineSourceSnapshot,'evidence/tranche-27-baseline.json') || ...
        ~strcmp(candidate.BaseSourceSnapshotSHA256, ...
        'a18437d84b4557a9b52c96ef6fb065b7904ec7a011c55debf2cc637541aa7376') || ...
        ~strcmp(csr.validation.Artifacts.sha256(path),candidate.BaseSourceSnapshotSHA256)
    error('csr:t27:Baseline','The accepted T25 source inventory changed.');
end
baseline=jsondecode(fileread(path));
if ~strcmp(candidate.BaselineCandidate,'evidence/tranche-27-parent-candidate.json') || ...
        ~strcmp(candidate.BaselineCandidateSHA256, ...
        '3859ff6eaecd504b9c84f0030a97069a364a054063022c903cfdeabd47b02741') || ...
        ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.BaselineCandidate)), ...
        candidate.BaselineCandidateSHA256) || ...
        ~strcmp(candidate.BaselineAcceptance,'evidence/t27/baseline/t25-acceptance.json') || ...
        ~strcmp(candidate.BaselineAcceptanceSHA256, ...
        '4c0937d5a6387e5bed3e23920ca9889e32c6eca04f44c61a6cd96e59b068c80d') || ...
        ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.BaselineAcceptance)), ...
        candidate.BaselineAcceptanceSHA256)
    error('csr:t27:Baseline','The accepted T25 candidate or review identity changed.');
end
if numel(baseline)~=420 || sum(endsWith({baseline.path},'.m'))~=186 || ...
        numel(unique({baseline.path}))~=420
    error('csr:t27:Baseline','Expected 420 unchanged T25 sources, including 186 MATLAB files.');
end
for k=1:numel(baseline)
    match=find(strcmp({snapshot.path},baseline(k).path));
    if numel(match)~=1 || ~strcmp(snapshot(match).sha256,baseline(k).sha256)
        error('csr:t27:Baseline','Accepted source changed: %s.',baseline(k).path);
    end
end
end

function files=referenceSnapshot(root,candidate)
names=cellstr(string(candidate.ReferenceFiles));
if isempty(names) || numel(unique(names))~=numel(names) || ~isempty(candidate.ReferenceRoots)
    error('csr:t27:Reference','Distinct explicit reference files are required.');
end
files=repmat(struct('path','','sha256','','bytes',0),numel(names),1);
for k=1:numel(names)
    path=csr.validation.ReleaseCheckpoint.checkedPath(root,names{k}); info=dir(path);
    files(k)=struct('path',names{k},'sha256',csr.validation.Artifacts.sha256(path),'bytes',info.bytes);
end
[~,order]=sort({files.path}); files=files(order);
if ~isequal(files,candidate.ReferenceFileInventory)
    error('csr:t27:Reference','Frozen reference membership, hashes or sizes changed.');
end
end

function record=failureRecord(failure)
record=struct('Identifier',failure.identifier,'Message',failure.message,'Stack',failure.stack);
end

function assertOutputPath(root,output)
root=csr.validation.Artifacts.canonicalPath(root);
if strcmp(root,output) || startsWith(root,[output filesep])
    error('csr:t27:Output','Output must not be the installation or an ancestor.');
end
for name={'+csr','tests','examples','scripts','scenarios','data','evidence','docs'}
    protected=fullfile(root,name{1});
    if strcmp(output,protected) || startsWith(output,[protected filesep])
        error('csr:t27:Output','Output must not overwrite source or reference trees.');
    end
end
end

function assertPackagePath(root)
names={'csr.sim.EventScheduler','csr.nwk.Layer','csr.nwk.Neighbors','csr.nwk.Routes', ...
    'csr.nwk.RoutingCodec','csr.validation.discoveryControllerCase', ...
    'csr.validation.discoveryControllerContract','csr.validation.Artifacts','csr.validation.ReleaseCheckpoint'};
for k=1:numel(names)
    parts=strsplit(names{k},'.'); folders=strcat('+',parts(1:end-1));
    expected=csr.validation.Artifacts.canonicalPath(fullfile(root,folders{:},[parts{end} '.m']));
    actual=which(names{k});
    if isempty(actual) || ~strcmp(expected,csr.validation.Artifacts.canonicalPath(actual))
        error('csr:t27:Path','A different installation is active for %s.',names{k});
    end
end
end
