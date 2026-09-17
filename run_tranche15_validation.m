function report = run_tranche15_validation(outputRoot)
%RUN_TRANCHE15_VALIDATION Paired transport timing under continued traffic.
% Uses unchanged production layers and real loss/relay custody with two local
% transport policies. Upload t15.zip even when the numerical traces differ.
root=fileparts(mfilename('fullpath')); addpath(root,'-begin');
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t15'); end
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyMMdd_HHmmss'));
[~,token]=fileparts(tempname); token=token(max(1,end-3):end);
directory=fullfile(outputRoot,['r' stamp '_' token]);
if isfolder(directory), error('csr:t15:OutputExists','Output already exists: %s.',directory); end
[ok,message]=mkdir(directory);
if ~ok, error('csr:t15:Output','Cannot create output: %s.',message); end
diary(fullfile(directory,'run.log'));
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-15-validation-v1','Tranche',15, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'NativeExecuted',false,'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'CandidateFile','evidence/tranche-15-candidate.json','CandidateSHA256','', ...
    'SourceSnapshotSHA256','','ReferenceSnapshotSHA256','', ...
    'SourceFilesFinal',struct([]),'ReferenceFilesFinal',struct([]), ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'BaselineSourceFilesVerified',0,'BaselineMatlabFilesVerified',0, ...
    'CoreBaselineSourceFilesVerified',0,'CoreBaselineMatlabFilesVerified',0, ...
    'TestFiles',{{}},'ExpectedTestNames',{{}},'TestsExecuted',false,'TestsPassed',false, ...
    'TestCount',0,'PassedTests',0,'FailedTests',0,'IncompleteTests',0,'TestClassesCompleted',0, ...
    'TestResultsFile','tests.csv','TimingDirectory','timing', ...
    'TimingCompleted',false,'TimingPassed',false,'TimingModeCount',0,'TimingCaseCount',0, ...
    'TimingCheckpointCount',0,'TimingFailedCount',0, ...
    'FocusedGateExecuted',false,'FullAcceptanceGateExecuted',false,'DiagnosticOnly',true, ...
    'AcceptanceEstablished',false,'NumericalParityEstablished',false, ...
    'EvidenceArchive','t15.zip','InventoryExcludedPaths',{{'metadata.json'}}, ...
    'Artifacts',struct([]),'LocalArtifacts',struct([]), ...
    'Scope',['Paired continuous and local nanosecond transport in the continued-traffic DATA/ACK-loss ' ...
        'and relay-link recovery fixture. Real sender admission, NWK custody, HOP reliability and MAC service; ' ...
        'fixed pre-admitted routes, prescribed draws and controlled addressed-group losses. ' ...
        'No global scheduler, startup phase, PHY/ECC or production policy change; no campus or full-network parity claim.']);
snapshot=struct([]); references=struct([]); candidate=struct(); originalFailure=[];
try
    assertPackagePath(root,{'csr.mac.Layer','csr.hop.Layer','csr.nwk.Layer', ...
        'csr.sim.EventScheduler','csr.validation.TraceScheduler','csr.validation.edgeRecordTable', ...
        'csr.validation.lossTimingContract','csr.validation.lossTimingRun', ...
        'csr.validation.transportArrival', ...
        'csr.validation.ReplayStreams'});
    candidatePath=fullfile(root,report.CandidateFile);
    candidate=jsondecode(fileread(candidatePath));
    if ~strcmp(candidate.Schema,'csr-tranche-15-candidate-v1') || ...
            ~strcmp(candidate.SourceCommit,report.SourceCommit)
        error('csr:t15:CandidateIdentity','Unexpected Tranche 15 candidate or native source pin.');
    end
    report.CandidateSHA256=csr.validation.Artifacts.sha256(candidatePath);
    report.TestFiles=cellstr(string(candidate.TestFiles));
    report.ExpectedTestNames=cellstr(string(candidate.ExpectedTestNames));
    snapshot=csr.validation.Artifacts.sourceSnapshot(root);
    csr.validation.Artifacts.writeJson(fullfile(directory,'source.json'),snapshot);
    report.SourceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'source.json'));
    [report.BaselineSourceFilesVerified,report.BaselineMatlabFilesVerified]= ...
        verifyBaseline(root,candidate.BaselineSourceSnapshot,candidate.BaseSourceSnapshotSHA256,285,144);
    [report.CoreBaselineSourceFilesVerified,report.CoreBaselineMatlabFilesVerified]= ...
        verifyBaseline(root,candidate.CoreBaselineSourceSnapshot,candidate.CoreBaselineSourceSnapshotSHA256,225,124);
    references=referenceSnapshot(root,candidate);
    csr.validation.Artifacts.writeJson(fullfile(directory,'references.json'),references);
    report.ReferenceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'references.json'));
    for label={'TimingPlan','LossPlan','LossReferenceManifest','BaselineOwnerEvidence','BaselineCandidate'}
        name=label{1}; expected=candidate.([name 'SHA256']);
        if ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.(name))),expected)
            error('csr:t15:InputChanged','Pinned %s differs from candidate identity.',name);
        end
    end
    writeMetadata();
    fprintf('Tranche 15: paired transport timing under continued DATA/ACK loss and relay recovery.\n');
    fprintf('Previous source verified: %d MATLAB files unchanged.\n',report.BaselineMatlabFilesVerified);
    if ~strcmp(report.TestFiles{1},'tests/TestTransportArrival.m')
        error('csr:t15:TestIdentity','The independent transport-time preflight must run first.');
    end
    fprintf('Checking transport-time arithmetic before the simulation cases.\n');
    results=runtests(fullfile(root,report.TestFiles{1})); results=results(:);
    report.TestClassesCompleted=1;
    writeTests(results); writeMetadata();
    preflightNames=sort(string(report.ExpectedTestNames(startsWith(report.ExpectedTestNames,'TestTransportArrival/'))));
    actualPreflightNames=sort(string({results.Name}));
    if isempty(results) || ~isequal(actualPreflightNames(:),preflightNames(:))
        error('csr:t15:TestIdentity','Transport-time preflight test identities differ from the candidate.');
    end
    assertSuccess(results);
    fprintf('Running two timing policies across four 64-second loss/recovery cases.\n');
    try
        timing=csr.validation.lossTimingContract(fullfile(directory,'timing'));
        report.TimingCompleted=logical(timing.DiagnosticCompleted);
        report.TimingPassed=logical(timing.Passed);
        report.TimingModeCount=timing.ModeCount;
        report.TimingCaseCount=timing.CaseCount;
        report.TimingCheckpointCount=timing.CheckpointCount;
        report.TimingFailedCount=timing.FailedCount;
    catch failure
        report.TimingFailure=failureRecord(failure);
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
    if ~namesMatch, error('csr:t15:TestIdentity','Executed test identities differ from candidate.'); end
    assertSuccess(results);
    if ~report.TimingCompleted || ~report.TimingPassed || report.TimingModeCount~=2 || ...
            report.TimingCaseCount~=8 || report.TimingCheckpointCount~=candidate.ExpectedStructuralCheckCount || ...
            report.TimingFailedCount~=0
        error('csr:t15:Incomplete','A timing diagnostic failed its structural checks; preserve t15.zip.');
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
    fprintf(2,'Tranche 15 failed: %s\n',failure.message);
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
fprintf('Tranche 15 focused execution complete: %d/%d MATLAB tests.\n',report.PassedTests,report.TestCount);

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
            error('csr:t15:InputChanged','Source or reference files changed during execution.');
        end
    end
end

function record=failureRecord(problem)
record=struct('Identifier',problem.identifier,'Message',problem.message,'Stack',problem.stack);
end

function [sourceCount,matlabCount]=verifyBaseline(root,name,expectedHash,wantedSource,wantedMatlab)
path=fullfile(root,name);
if ~strcmp(csr.validation.Artifacts.sha256(path),expectedHash)
    error('csr:t15:BaselineIdentity','Baseline snapshot differs: %s.',name);
end
baseline=jsondecode(fileread(path));
for k=1:numel(baseline)
    if ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,baseline(k).path)),baseline(k).sha256)
        error('csr:t15:BaselineChanged','Previous source file differs: %s.',baseline(k).path);
    end
end
sourceCount=numel(baseline); matlabCount=sum(endsWith({baseline.path},'.m'));
if sourceCount~=wantedSource || matlabCount~=wantedMatlab
    error('csr:t15:BaselineIdentity','Unexpected source/MATLAB counts in %s.',name);
end
end

function assertPackagePath(root,names)
for k=1:numel(names)
    parts=strsplit(names{k},'.'); relative='';
    for j=1:numel(parts)-1, relative=fullfile(relative,['+' parts{j}]); end
    expected=csr.validation.Artifacts.canonicalPath(fullfile(root,relative,[parts{end} '.m']));
    resolved=csr.validation.Artifacts.canonicalPath(which(names{k}));
    if ~strcmp(expected,resolved)
        error('csr:t15:Path','A different CSR package is active for %s: %s.',names{k},resolved);
    end
end
end

function files=referenceSnapshot(root,candidate)
files=repmat(struct('path','','sha256','','bytes',0),0,1);
roots=cellstr(string(candidate.ReferenceRoots));
for k=1:numel(roots)
    inventory=csr.validation.Artifacts.fileInventory(fullfile(root,roots{k}));
    if isempty(inventory), error('csr:t15:Reference','Empty reference directory: %s.',roots{k}); end
    for j=1:numel(inventory), inventory(j).path=[roots{k} '/' inventory(j).path]; end
    files=[files;inventory(:)]; %#ok<AGROW>
end
individual=cellstr(string(candidate.ReferenceFiles));
for k=1:numel(individual)
    path=fullfile(root,individual{k}); info=dir(path);
    if numel(info)~=1 || info.isdir, error('csr:t15:Reference','Missing reference file: %s.',path); end
    files(end+1,1)=struct('path',individual{k},'sha256',csr.validation.Artifacts.sha256(path),'bytes',info.bytes); %#ok<AGROW>
end
[~,order]=sort({files.path}); files=files(order);
if numel(unique({files.path}))~=numel(files)
    error('csr:t15:Reference','Reference inventory declarations overlap.');
end
end
