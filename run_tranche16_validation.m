function report = run_tranche16_validation(outputRoot)
%RUN_TRANCHE16_VALIDATION Paired network timing across three seeds.
% Uses unchanged six real-network configurations and two explicit receiver
% timing policies. Upload t16.zip even when numerical outcomes differ.
root=fileparts(mfilename('fullpath')); addpath(root,'-begin');
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t16'); end
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyMMdd_HHmm'));
[~,token]=fileparts(tempname); token=token(max(1,end-3):end);
directory=fullfile(outputRoot,['r' stamp '_' token]);
if isfolder(directory), error('csr:t16:OutputExists','Output already exists: %s.',directory); end
[ok,message]=mkdir(directory);
if ~ok, error('csr:t16:Output','Cannot create output: %s.',message); end
diary(fullfile(directory,'run.log'));
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-16-validation-v1','Tranche',16, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'NativeExecuted',false,'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'CandidateFile','evidence/tranche-16-candidate.json','CandidateSHA256','', ...
    'SourceSnapshotSHA256','','ReferenceSnapshotSHA256','', ...
    'SourceFilesFinal',struct([]),'ReferenceFilesFinal',struct([]), ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'BaselineSourceFilesVerified',0,'BaselineMatlabFilesVerified',0, ...
    'UnchangedBaselineSourceFilesVerified',0,'UnchangedBaselineMatlabFilesVerified',0, ...
    'AllowedModifiedSourceFilesVerified',0, ...
    'TestFiles',{{}},'ExpectedTestNames',{{}},'TestsExecuted',false,'TestsPassed',false, ...
    'TestCount',0,'PassedTests',0,'FailedTests',0,'IncompleteTests',0,'TestClassesCompleted',0, ...
    'TestResultsFile','tests.csv','TimingDirectory','network', ...
    'TimingCompleted',false,'TimingPassed',false,'TimingModeCount',0,'TimingCaseCount',0, ...
    'TimingCheckpointCount',0,'TimingFailedCount',0, ...
    'FocusedGateExecuted',false,'FullAcceptanceGateExecuted',false,'DiagnosticOnly',true, ...
    'AcceptanceEstablished',false,'NumericalParityEstablished',false, ...
    'EvidenceArchive','t16.zip','InventoryExcludedPaths',{{'metadata.json'}}, ...
    'Artifacts',struct([]),'LocalArtifacts',struct([]), ...
    'Scope',['Paired continuous and optional nanosecond receiver timing in six unchanged admission/contention ' ...
        'configurations over seeds 128,129,130. Real PHY, autonomous routes, actual admission and ACK service. ' ...
        'Full feedback/admission observations; detailed service callbacks only in [300,320) seconds. ' ...
        'Default timing and physical calculations remain unchanged. Finite-stop loss/backlog is reported; ' ...
        'this is not campus or full-network acceptance or an ns-3/OPNET parity claim.']);
snapshot=struct([]); references=struct([]); candidate=struct(); originalFailure=[];
try
    assertPackagePath(root,{'csr.mac.Layer','csr.hop.Layer','csr.nwk.Layer', ...
        'csr.sim.EventScheduler','csr.sim.NetworkSimulation','csr.phy.SignalEngine', ...
        'csr.sim.TransportTiming','csr.sim.AckServiceDiagnostics', ...
        'csr.validation.edgeRecordTable','csr.validation.networkTimingContract', ...
        'csr.scenario.tranche16Suite'});
    candidatePath=fullfile(root,report.CandidateFile);
    candidate=jsondecode(fileread(candidatePath));
    if ~strcmp(candidate.Schema,'csr-tranche-16-candidate-v1') || ...
            ~strcmp(candidate.SourceCommit,report.SourceCommit)
        error('csr:t16:CandidateIdentity','Unexpected Tranche 16 candidate or native source pin.');
    end
    report.CandidateSHA256=csr.validation.Artifacts.sha256(candidatePath);
    report.TestFiles=cellstr(string(candidate.TestFiles));
    report.ExpectedTestNames=cellstr(string(candidate.ExpectedTestNames));
    snapshot=csr.validation.Artifacts.sourceSnapshot(root);
    % The candidate binds every source except itself; its own hash is
    % separately recorded above and included in the run snapshot below.
    bound=snapshot(~strcmp({snapshot.path},report.CandidateFile));
    if ~isequal(bound,candidate.SourceFiles)
        error('csr:t16:CandidateSource','Candidate source hashes or membership changed.');
    end
    csr.validation.Artifacts.writeJson(fullfile(directory,'source.json'),snapshot);
    report.SourceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'source.json'));
    [report.BaselineSourceFilesVerified,report.BaselineMatlabFilesVerified, ...
        report.UnchangedBaselineSourceFilesVerified,report.UnchangedBaselineMatlabFilesVerified, ...
        report.AllowedModifiedSourceFilesVerified]=verifyBaseline(root,candidate);
    references=referenceSnapshot(root,candidate);
    csr.validation.Artifacts.writeJson(fullfile(directory,'references.json'),references);
    report.ReferenceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'references.json'));
    for label={'Plan','BaselineOwnerEvidence','BaselineCandidate'}
        name=label{1}; expected=candidate.([name 'SHA256']);
        if ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.(name))),expected)
            error('csr:t16:InputChanged','Pinned %s differs from candidate identity.',name);
        end
    end
    writeMetadata();
    fprintf('Tranche 16: receiver timing across three seeds and two real-network fixtures.\n');
    fprintf('Previous source verified: %d MATLAB files unchanged; %d declared integration files.\n', ...
        report.UnchangedBaselineMatlabFilesVerified,report.AllowedModifiedSourceFilesVerified);
    if ~strcmp(report.TestFiles{1},'tests/TestNetworkTransportTiming.m')
        error('csr:t16:TestIdentity','The independent transport-timing preflight must run first.');
    end
    fprintf('Checking transport-timing arithmetic before the simulation cases.\n');
    results=runtests(fullfile(root,report.TestFiles{1})); results=results(:);
    report.TestClassesCompleted=1;
    writeTests(results); writeMetadata();
    preflightNames=sort(string(report.ExpectedTestNames(startsWith(report.ExpectedTestNames,'TestNetworkTransportTiming/'))));
    actualPreflightNames=sort(string({results.Name}));
    if isempty(results) || ~isequal(actualPreflightNames(:),preflightNames(:))
        error('csr:t16:TestIdentity','Transport-time preflight test identities differ from the candidate.');
    end
    assertSuccess(results);
    fprintf('Running 12 paired cases, 9360 simulated seconds total.\n');
    fprintf('Each case prints completion and a rough remaining-time estimate.\n');
    try
        timing=csr.validation.networkTimingContract(fullfile(directory,'network'));
        report.TimingCompleted=logical(timing.DiagnosticCompleted);
        report.TimingPassed=logical(timing.Passed);
        report.TimingModeCount=timing.ModeCount;
        report.TimingCaseCount=timing.CaseCount;
        report.TimingCheckpointCount=timing.CheckpointCount;
        report.TimingFailedCount=timing.FailedCount;
    catch failure
        report.TimingFailure=failureRecord(failure);
        partial=fullfile(directory,'network','summary.json');
        if isfile(partial)
            partialReport=jsondecode(fileread(partial));
            report.TimingCaseCount=partialReport.CaseCount;
            report.TimingCheckpointCount=partialReport.CheckpointCount;
            report.TimingFailedCount=partialReport.FailedCount;
        end
        fprintf(2,'Timing diagnostic error: %s\n',failure.message);
    end
    writeMetadata();
    if report.TimingCompleted
        fprintf('Timing diagnostic: %d cases, %d structural checks, %d failed checks.\n', ...
            report.TimingCaseCount,report.TimingCheckpointCount,report.TimingFailedCount);
        fprintf('The return review will compare delivery, retries, ACK overhead and capacity release.\n');
    else
        fprintf('Timing diagnostic incomplete; preserve the partial evidence.\n');
    end
    fprintf('Continuing the %d-test MATLAB suite in the remaining %d classes.\n', ...
        numel(report.ExpectedTestNames),numel(report.TestFiles)-1);
    for k=2:numel(report.TestFiles)
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
    if ~namesMatch, error('csr:t16:TestIdentity','Executed test identities differ from candidate.'); end
    assertSuccess(results);
    if ~report.TimingCompleted || ~report.TimingPassed || report.TimingModeCount~=2 || ...
            report.TimingCaseCount~=12 || report.TimingCheckpointCount~=candidate.ExpectedStructuralCheckCount || ...
            report.TimingFailedCount~=0
        error('csr:t16:Incomplete','A timing diagnostic failed its structural checks; preserve t16.zip.');
    end
    checkStableInputs();
    report.FocusedGateExecuted=report.TestsPassed && report.TimingCompleted && report.TimingPassed && ...
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
    fprintf(2,'Tranche 16 failed: %s\n',failure.message);
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
fprintf('Tranche 16 focused execution complete: %d/%d MATLAB tests.\n',report.PassedTests,report.TestCount);

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
            error('csr:t16:InputChanged','Source or reference files changed during execution.');
        end
    end
end

function record=failureRecord(problem)
record=struct('Identifier',problem.identifier,'Message',problem.message,'Stack',problem.stack);
end

function [sourceCount,matlabCount,unchangedSource,unchangedMatlab,modifiedCount]=verifyBaseline(root,candidate)
path=fullfile(root,candidate.BaselineSourceSnapshot);
if ~strcmp(csr.validation.Artifacts.sha256(path),candidate.BaseSourceSnapshotSHA256)
    error('csr:t16:BaselineIdentity','Baseline snapshot differs from the issued candidate.');
end
baseline=jsondecode(fileread(path));
allowed=candidate.AllowedModifiedSourceFiles;
expected={'+csr/+phy/SignalEngine.m','+csr/+sim/NetworkSimulation.m'};
if numel(allowed)~=2 || ~isequal(sort({allowed.path}),sort(expected))
    error('csr:t16:BaselineIdentity','Only the two declared timing integration files may differ.');
end
sourceCount=numel(baseline); matlabCount=sum(endsWith({baseline.path},'.m'));
if sourceCount~=294 || matlabCount~=149 || numel(unique({baseline.path}))~=sourceCount
    error('csr:t16:BaselineIdentity','Unexpected Tranche 15 source inventory.');
end
unchangedSource=0; unchangedMatlab=0; modifiedCount=0;
for k=1:numel(baseline)
    entry=baseline(k); selected=find(strcmp({allowed.path},entry.path));
    if isempty(selected)
        expectedHash=entry.sha256; expectedBytes=[];
        unchangedSource=unchangedSource+1;
        unchangedMatlab=unchangedMatlab+endsWith(entry.path,'.m');
    else
        expectedHash=allowed(selected).sha256; expectedBytes=allowed(selected).bytes;
        modifiedCount=modifiedCount+1;
    end
    actual=fullfile(root,entry.path); info=dir(actual);
    if numel(info)~=1 || info.isdir || (~isempty(expectedBytes) && info.bytes~=expectedBytes) || ...
            ~strcmp(csr.validation.Artifacts.sha256(actual),expectedHash)
        error('csr:t16:BaselineChanged','Baseline or declared integration file differs: %s.',entry.path);
    end
end
if unchangedSource~=292 || unchangedMatlab~=147 || modifiedCount~=2
    error('csr:t16:BaselineIdentity','Incomplete baseline or integration allowlist coverage.');
end
end

function assertPackagePath(root,names)
for k=1:numel(names)
    parts=strsplit(names{k},'.'); relative='';
    for j=1:numel(parts)-1, relative=fullfile(relative,['+' parts{j}]); end
    expected=csr.validation.Artifacts.canonicalPath(fullfile(root,relative,[parts{end} '.m']));
    resolved=csr.validation.Artifacts.canonicalPath(which(names{k}));
    if ~strcmp(expected,resolved)
        error('csr:t16:Path','A different CSR package is active for %s: %s.',names{k},resolved);
    end
end
end

function files=referenceSnapshot(root,candidate)
files=repmat(struct('path','','sha256','','bytes',0),0,1);
roots=cellstr(string(candidate.ReferenceRoots));
for k=1:numel(roots)
    inventory=csr.validation.Artifacts.fileInventory(fullfile(root,roots{k}));
    if isempty(inventory), error('csr:t16:Reference','Empty reference directory: %s.',roots{k}); end
    for j=1:numel(inventory), inventory(j).path=[roots{k} '/' inventory(j).path]; end
    files=[files;inventory(:)]; %#ok<AGROW>
end
individual=cellstr(string(candidate.ReferenceFiles));
for k=1:numel(individual)
    path=fullfile(root,individual{k}); info=dir(path);
    if numel(info)~=1 || info.isdir, error('csr:t16:Reference','Missing reference file: %s.',path); end
    files(end+1,1)=struct('path',individual{k},'sha256',csr.validation.Artifacts.sha256(path),'bytes',info.bytes); %#ok<AGROW>
end
[~,order]=sort({files.path}); files=files(order);
if numel(unique({files.path}))~=numel(files)
    error('csr:t16:Reference','Reference inventory declarations overlap.');
end
end
