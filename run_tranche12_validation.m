function report = run_tranche12_validation(outputRoot)
%RUN_TRANCHE12_VALIDATION Short relay/local service and clock-boundary tests.
% Uses the unchanged NWK/HOP/MAC with preconditioned neighbors/routes and
% controlled transport. Upload the printed t12.zip even when traces differ.
root=fileparts(mfilename('fullpath')); addpath(root,'-begin');
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t12'); end
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyMMdd_HHmmss'));
[~,token]=fileparts(tempname); token=token(max(1,end-3):end);
directory=fullfile(outputRoot,['r' stamp '_' token]);
if isfolder(directory), error('csr:t12:OutputExists','Output already exists: %s.',directory); end
[ok,message]=mkdir(directory);
if ~ok, error('csr:t12:Output','Cannot create output: %s.',message); end
diary(fullfile(directory,'run.log'));
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-12-validation-v1','Tranche',12, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'NativeExecuted',false,'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'CandidateFile','evidence/tranche-12-candidate.json','CandidateSHA256','', ...
    'SourceSnapshotSHA256','','ReferenceSnapshotSHA256','', ...
    'SourceFilesFinal',struct([]),'ReferenceFilesFinal',struct([]), ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'BaselineSourceFilesVerified',0,'BaselineMatlabFilesVerified',0, ...
    'CoreBaselineSourceFilesVerified',0,'CoreBaselineMatlabFilesVerified',0, ...
    'TestFiles',{{}},'ExpectedTestNames',{{}},'TestsExecuted',false,'TestsPassed',false, ...
    'TestCount',0,'PassedTests',0,'FailedTests',0,'IncompleteTests',0,'TestClassesCompleted',0, ...
    'TestResultsFile','tests.csv','RelayDirectory','relay','ClockDirectory','clock', ...
    'RelayCompleted',false,'RelayPassed',false,'RelayMatchesNative',false, ...
    'RelayCaseCount',0,'RelayEventCount',0,'RelayDrawCount',0,'RelayUnmatchedCount',0, ...
    'ClockCompleted',false,'ClockPassed',false,'ClockMatchesNative',false, ...
    'ClockCaseCount',0,'ClockCheckpointCount',0,'ClockUnmatchedCount',0, ...
    'FocusedGateExecuted',false,'FullAcceptanceGateExecuted',false,'DiagnosticOnly',true, ...
    'AcceptanceEstablished',false,'NumericalParityEstablished',false, ...
    'EvidenceArchive','t12.zip','InventoryExcludedPaths',{{'metadata.json'}}, ...
    'Artifacts',struct([]),'LocalArtifacts',struct([]), ...
    'Scope',['Finite offers gated by actual NWK admission state; production NWK/HOP/MAC ' ...
        'queue and relay custody with preconditioned neighbors/routes, prescribed draws and controlled successful ' ...
        'transport; separate clock-boundary diagnostics. No RF, neighbor-authentication, ' ...
        'route-convergence, campus, stochastic-population or full-protocol parity claim.']);
snapshot=struct([]); references=struct([]); candidate=struct(); originalFailure=[];
try
    assertPackagePath(root,{'csr.mac.Layer','csr.hop.Layer','csr.nwk.Layer', ...
        'csr.sim.EventScheduler','csr.validation.relayContract', ...
        'csr.validation.clockBoundaryContract','csr.validation.ReplayStreams'});
    candidatePath=fullfile(root,report.CandidateFile);
    candidate=jsondecode(fileread(candidatePath));
    report.CandidateSHA256=csr.validation.Artifacts.sha256(candidatePath);
    report.TestFiles=cellstr(string(candidate.TestFiles));
    report.ExpectedTestNames=cellstr(string(candidate.ExpectedTestNames));
    snapshot=csr.validation.Artifacts.sourceSnapshot(root);
    csr.validation.Artifacts.writeJson(fullfile(directory,'source.json'),snapshot);
    report.SourceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'source.json'));
    [report.BaselineSourceFilesVerified,report.BaselineMatlabFilesVerified]= ...
        verifyBaseline(root,candidate.BaselineSourceSnapshot,candidate.BaseSourceSnapshotSHA256,241,130);
    [report.CoreBaselineSourceFilesVerified,report.CoreBaselineMatlabFilesVerified]= ...
        verifyBaseline(root,candidate.CoreBaselineSourceSnapshot,candidate.CoreBaselineSourceSnapshotSHA256,225,124);
    references=referenceSnapshot(root,candidate);
    csr.validation.Artifacts.writeJson(fullfile(directory,'references.json'),references);
    report.ReferenceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'references.json'));
    for label={'RelayPlan','ClockPlan','RelayReferenceManifest','ClockReferenceManifest'}
        name=label{1}; expected=candidate.([name 'SHA256']);
        if ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.(name))),expected)
            error('csr:t12:InputChanged','Pinned %s differs from candidate identity.',name);
        end
    end
    writeMetadata();
    fprintf('Tranche 12: short 4 -> 5 -> 1 relay/local service and clock-boundary diagnostics.\n');
    fprintf('Previous source verified: %d MATLAB files unchanged.\n',report.BaselineMatlabFilesVerified);
    fprintf('Running relay-only, local-only and shared-service cases.\n');
    try
        relay=csr.validation.relayContract(fullfile(directory,'relay'));
        report.RelayCompleted=logical(relay.DiagnosticCompleted);
        report.RelayPassed=logical(relay.Passed);
        report.RelayMatchesNative=logical(relay.MatchesNative);
        report.RelayCaseCount=relay.CaseCount;
        report.RelayEventCount=relay.EventCount;
        report.RelayDrawCount=relay.DrawCount;
        report.RelayUnmatchedCount=relay.UnmatchedCount;
    catch failure
        report.RelayFailure=failureRecord(failure);
        fprintf(2,'Relay diagnostic error: %s\n',failure.message);
    end
    writeMetadata();
    fprintf('Relay diagnostic: %d cases, %d observations, %d draws; native differences %d.\n', ...
        report.RelayCaseCount,report.RelayEventCount,report.RelayDrawCount,report.RelayUnmatchedCount);
    fprintf('Running clock-boundary diagnostics.\n');
    try
        clockReport=csr.validation.clockBoundaryContract(fullfile(directory,'clock'));
        report.ClockCompleted=logical(clockReport.DiagnosticCompleted);
        report.ClockPassed=logical(clockReport.Passed);
        report.ClockMatchesNative=logical(clockReport.MatchesNative);
        report.ClockCaseCount=clockReport.CaseCount;
        report.ClockCheckpointCount=clockReport.CheckpointCount;
        report.ClockUnmatchedCount=clockReport.UnmatchedCount;
    catch failure
        report.ClockFailure=failureRecord(failure);
        fprintf(2,'Clock diagnostic error: %s\n',failure.message);
    end
    writeMetadata();
    fprintf('Clock diagnostic: %d cases, %d checks; native differences %d.\n', ...
        report.ClockCaseCount,report.ClockCheckpointCount,report.ClockUnmatchedCount);
    fprintf('Running %d focused MATLAB tests in %d classes.\n', ...
        numel(report.ExpectedTestNames),numel(report.TestFiles));
    results=[];
    for k=1:numel(report.TestFiles)
        next=runtests(fullfile(root,report.TestFiles{k}));
        if isempty(results), results=next(:); else, results=[results;next(:)]; end %#ok<AGROW>
        report.TestClassesCompleted=k;
        writeTests(results);
        writeMetadata();
    end
    actualNames=sort(string({results.Name}));
    expectedNames=sort(string(report.ExpectedTestNames));
    namesMatch=isequal(actualNames(:),expectedNames(:)) && ...
        numel(unique(actualNames))==numel(actualNames);
    report.TestsPassed=~isempty(results) && namesMatch && all([results.Passed]) && ...
        ~any([results.Failed]) && ~any([results.Incomplete]);
    if ~namesMatch, error('csr:t12:TestIdentity','Executed test identities differ from candidate.'); end
    assertSuccess(results);
    if ~report.RelayCompleted || ~report.RelayPassed || report.RelayCaseCount<1 || ...
            report.RelayEventCount<1 || report.RelayDrawCount<1 || ...
            ~report.ClockCompleted || ~report.ClockPassed || report.ClockCaseCount<1
        error('csr:t12:Incomplete','A diagnostic failed its structural checks; preserve t12.zip.');
    end
    checkStableInputs();
    report.FocusedGateExecuted=report.TestsPassed && report.RelayCompleted && report.RelayPassed && ...
        report.ClockCompleted && report.ClockPassed && ...
        report.SourceFilesStableDuringRun && report.ReferenceFilesStableDuringRun;
    report.Status='completed';
catch failure
    originalFailure=failure; report.Status='failed'; report.Failure=failureRecord(failure);
    if ~isempty(snapshot) && ~isempty(references)
        try
            checkStableInputs();
        catch inputFailure
            report.InputCheckFailure=failureRecord(inputFailure);
        end
    end
    fprintf(2,'Tranche 12 failed: %s\n',failure.message);
end
report.CompletedUTC=csr.validation.Artifacts.utcNow();
diary('off');
try
    files=csr.validation.Artifacts.fileInventory(directory,{'metadata.json',report.EvidenceArchive});
    local=endsWith({files.path},'.mat');
    report.LocalArtifacts=files(local); report.Artifacts=files(~local);
    writeMetadata();
    zip(fullfile(directory,report.EvidenceArchive),[{report.Artifacts.path},{'metadata.json'}],directory);
    fprintf('Upload %s for review.\n',fullfile(directory,report.EvidenceArchive));
catch packagingFailure
    fprintf(2,'Could not package evidence; partial files remain in %s.\n',directory);
    if isempty(originalFailure), rethrow(packagingFailure); end
end
if ~isempty(originalFailure), rethrow(originalFailure); end
fprintf('Tranche 12 focused execution complete: %d/%d MATLAB tests.\n',report.PassedTests,report.TestCount);

    function writeMetadata()
        csr.validation.Artifacts.writeJson(fullfile(directory,'metadata.json'),report);
    end
    function writeTests(results)
        summary=table({results.Name}',[results.Passed]',[results.Failed]', ...
            [results.Incomplete]',[results.Duration]', ...
            'VariableNames',{'Name','Passed','Failed','Incomplete','DurationSeconds'});
        writetable(summary,fullfile(directory,'tests.csv'));
        report.TestsExecuted=~isempty(results); report.TestCount=numel(results);
        report.PassedTests=sum([results.Passed]); report.FailedTests=sum([results.Failed]);
        report.IncompleteTests=sum([results.Incomplete]);
    end
    function checkStableInputs()
        report.SourceFilesFinal=csr.validation.Artifacts.sourceSnapshot(root);
        report.ReferenceFilesFinal=referenceSnapshot(root,candidate);
        report.SourceFilesStableDuringRun=isequal(snapshot,report.SourceFilesFinal);
        report.ReferenceFilesStableDuringRun=isequal(references,report.ReferenceFilesFinal);
        if ~report.SourceFilesStableDuringRun || ~report.ReferenceFilesStableDuringRun
            error('csr:t12:InputChanged','Source or reference files changed during execution.');
        end
    end
end

function record=failureRecord(problem)
record=struct('Identifier',problem.identifier,'Message',problem.message,'Stack',problem.stack);
end

function [sourceCount,matlabCount]=verifyBaseline(root,name,expectedHash,wantedSource,wantedMatlab)
path=fullfile(root,name);
if ~strcmp(csr.validation.Artifacts.sha256(path),expectedHash)
    error('csr:t12:BaselineIdentity','Baseline snapshot differs: %s.',name);
end
baseline=jsondecode(fileread(path));
for k=1:numel(baseline)
    if ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,baseline(k).path)),baseline(k).sha256)
        error('csr:t12:BaselineChanged','Previous source file differs: %s.',baseline(k).path);
    end
end
sourceCount=numel(baseline); matlabCount=sum(endsWith({baseline.path},'.m'));
if sourceCount~=wantedSource || matlabCount~=wantedMatlab
    error('csr:t12:BaselineIdentity','Unexpected source/MATLAB counts in %s.',name);
end
end

function assertPackagePath(root,names)
for k=1:numel(names)
    parts=strsplit(names{k},'.'); relative='';
    for j=1:numel(parts)-1, relative=fullfile(relative,['+' parts{j}]); end
    expected=csr.validation.Artifacts.canonicalPath(fullfile(root,relative,[parts{end} '.m']));
    resolved=csr.validation.Artifacts.canonicalPath(which(names{k}));
    if ~strcmp(expected,resolved)
        error('csr:t12:Path','A different CSR package is active for %s: %s.',names{k},resolved);
    end
end
end

function files=referenceSnapshot(root,candidate)
files=repmat(struct('path','','sha256','','bytes',0),0,1);
roots=cellstr(string(candidate.ReferenceRoots));
for k=1:numel(roots)
    inventory=csr.validation.Artifacts.fileInventory(fullfile(root,roots{k}));
    if isempty(inventory), error('csr:t12:Reference','Empty reference directory: %s.',roots{k}); end
    for j=1:numel(inventory), inventory(j).path=[roots{k} '/' inventory(j).path]; end
    files=[files;inventory(:)]; %#ok<AGROW>
end
individual=cellstr(string(candidate.ReferenceFiles));
for k=1:numel(individual)
    path=fullfile(root,individual{k}); info=dir(path);
    if numel(info)~=1 || info.isdir, error('csr:t12:Reference','Missing reference file: %s.',path); end
    files(end+1,1)=struct('path',individual{k},'sha256',csr.validation.Artifacts.sha256(path),'bytes',info.bytes); %#ok<AGROW>
end
[~,order]=sort({files.path}); files=files(order);
if numel(unique({files.path}))~=numel(files)
    error('csr:t12:Reference','Reference inventory declarations overlap.');
end
end
