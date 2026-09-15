function report = run_tranche13_validation(outputRoot)
%RUN_TRANCHE13_VALIDATION Continued-traffic DATA/ACK loss and relay-link recovery tests.
% Uses the unchanged NWK/HOP/MAC with preconditioned neighbors/routes and
% controlled transport. Upload the printed t13.zip even when traces differ.
root=fileparts(mfilename('fullpath')); addpath(root,'-begin');
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t13'); end
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyMMdd_HHmmss'));
[~,token]=fileparts(tempname); token=token(max(1,end-3):end);
directory=fullfile(outputRoot,['r' stamp '_' token]);
if isfolder(directory), error('csr:t13:OutputExists','Output already exists: %s.',directory); end
[ok,message]=mkdir(directory);
if ~ok, error('csr:t13:Output','Cannot create output: %s.',message); end
diary(fullfile(directory,'run.log'));
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-13-validation-v1','Tranche',13, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'NativeExecuted',false,'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'CandidateFile','evidence/tranche-13-candidate.json','CandidateSHA256','', ...
    'SourceSnapshotSHA256','','ReferenceSnapshotSHA256','', ...
    'SourceFilesFinal',struct([]),'ReferenceFilesFinal',struct([]), ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'BaselineSourceFilesVerified',0,'BaselineMatlabFilesVerified',0, ...
    'CoreBaselineSourceFilesVerified',0,'CoreBaselineMatlabFilesVerified',0, ...
    'TestFiles',{{}},'ExpectedTestNames',{{}},'TestsExecuted',false,'TestsPassed',false, ...
    'TestCount',0,'PassedTests',0,'FailedTests',0,'IncompleteTests',0,'TestClassesCompleted',0, ...
    'TestResultsFile','tests.csv','RecoveryDirectory','loss', ...
    'RecoveryCompleted',false,'RecoveryPassed',false,'RecoveryMatchesNative',false, ...
    'RecoveryCaseCount',0,'RecoveryEventCount',0,'RecoveryDrawCount',0, ...
    'RecoveryCheckpointCount',0,'RecoveryUnmatchedCount',0, ...
    'FocusedGateExecuted',false,'FullAcceptanceGateExecuted',false,'DiagnosticOnly',true, ...
    'AcceptanceEstablished',false,'NumericalParityEstablished',false, ...
    'EvidenceArchive','t13.zip','InventoryExcludedPaths',{{'metadata.json'}}, ...
    'Artifacts',struct([]),'LocalArtifacts',struct([]), ...
    'Scope',['Finite offers gated by actual NWK admission state; production NWK/HOP/MAC ' ...
        'queue and relay custody with preconditioned neighbors/routes, prescribed draws and controlled DATA/ACK loss ' ...
        'or relay-link interruption while new application demand continues. No RF, neighbor-authentication, ' ...
        'route-convergence, campus, stochastic-population or full-protocol parity claim.']);
snapshot=struct([]); references=struct([]); candidate=struct(); originalFailure=[];
try
    assertPackagePath(root,{'csr.mac.Layer','csr.hop.Layer','csr.nwk.Layer', ...
        'csr.sim.EventScheduler','csr.validation.lossContract', ...
        'csr.validation.ReplayStreams'});
    candidatePath=fullfile(root,report.CandidateFile);
    candidate=jsondecode(fileread(candidatePath));
    if ~strcmp(candidate.Schema,'csr-tranche-13-candidate-v1') || ...
            ~strcmp(candidate.SourceCommit,report.SourceCommit)
        error('csr:t13:CandidateIdentity','Unexpected Tranche 13 candidate or native source pin.');
    end
    report.CandidateSHA256=csr.validation.Artifacts.sha256(candidatePath);
    report.TestFiles=cellstr(string(candidate.TestFiles));
    report.ExpectedTestNames=cellstr(string(candidate.ExpectedTestNames));
    snapshot=csr.validation.Artifacts.sourceSnapshot(root);
    csr.validation.Artifacts.writeJson(fullfile(directory,'source.json'),snapshot);
    report.SourceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'source.json'));
    [report.BaselineSourceFilesVerified,report.BaselineMatlabFilesVerified]= ...
        verifyBaseline(root,candidate.BaselineSourceSnapshot,candidate.BaseSourceSnapshotSHA256,259,135);
    [report.CoreBaselineSourceFilesVerified,report.CoreBaselineMatlabFilesVerified]= ...
        verifyBaseline(root,candidate.CoreBaselineSourceSnapshot,candidate.CoreBaselineSourceSnapshotSHA256,225,124);
    references=referenceSnapshot(root,candidate);
    csr.validation.Artifacts.writeJson(fullfile(directory,'references.json'),references);
    report.ReferenceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'references.json'));
    for label={'LossPlan','LossReferenceManifest'}
        name=label{1}; expected=candidate.([name 'SHA256']);
        if ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.(name))),expected)
            error('csr:t13:InputChanged','Pinned %s differs from candidate identity.',name);
        end
    end
    writeMetadata();
    fprintf('Tranche 13: controlled DATA/ACK loss and relay-link recovery on 4 -> 5 -> 1.\n');
    fprintf('Previous source verified: %d MATLAB files unchanged.\n',report.BaselineMatlabFilesVerified);
    fprintf('Running four 64-second cases with continued application demand.\n');
    try
        recovery=csr.validation.lossContract(fullfile(directory,'loss'));
        report.RecoveryCompleted=logical(recovery.DiagnosticCompleted);
        report.RecoveryPassed=logical(recovery.Passed);
        report.RecoveryMatchesNative=logical(recovery.MatchesNative);
        report.RecoveryCaseCount=recovery.CaseCount;
        report.RecoveryEventCount=recovery.EventCount;
        report.RecoveryDrawCount=recovery.DrawCount;
        report.RecoveryCheckpointCount=recovery.CheckpointCount;
        report.RecoveryUnmatchedCount=recovery.UnmatchedCount;
    catch failure
        report.RecoveryFailure=failureRecord(failure);
        fprintf(2,'Recovery diagnostic error: %s\n',failure.message);
    end
    writeMetadata();
    fprintf('Recovery diagnostic: %d cases, %d observations, %d draws; native differences %d.\n', ...
        report.RecoveryCaseCount,report.RecoveryEventCount,report.RecoveryDrawCount,report.RecoveryUnmatchedCount);
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
    if ~namesMatch, error('csr:t13:TestIdentity','Executed test identities differ from candidate.'); end
    assertSuccess(results);
    if ~report.RecoveryCompleted || ~report.RecoveryPassed || report.RecoveryCaseCount~=4 || ...
            report.RecoveryEventCount<1 || report.RecoveryDrawCount<1 || report.RecoveryCheckpointCount<1
        error('csr:t13:Incomplete','A recovery diagnostic failed its structural checks; preserve t13.zip.');
    end
    checkStableInputs();
    report.FocusedGateExecuted=report.TestsPassed && report.RecoveryCompleted && report.RecoveryPassed && ...
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
    fprintf(2,'Tranche 13 failed: %s\n',failure.message);
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
fprintf('Tranche 13 focused execution complete: %d/%d MATLAB tests.\n',report.PassedTests,report.TestCount);

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
            error('csr:t13:InputChanged','Source or reference files changed during execution.');
        end
    end
end

function record=failureRecord(problem)
record=struct('Identifier',problem.identifier,'Message',problem.message,'Stack',problem.stack);
end

function [sourceCount,matlabCount]=verifyBaseline(root,name,expectedHash,wantedSource,wantedMatlab)
path=fullfile(root,name);
if ~strcmp(csr.validation.Artifacts.sha256(path),expectedHash)
    error('csr:t13:BaselineIdentity','Baseline snapshot differs: %s.',name);
end
baseline=jsondecode(fileread(path));
for k=1:numel(baseline)
    if ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,baseline(k).path)),baseline(k).sha256)
        error('csr:t13:BaselineChanged','Previous source file differs: %s.',baseline(k).path);
    end
end
sourceCount=numel(baseline); matlabCount=sum(endsWith({baseline.path},'.m'));
if sourceCount~=wantedSource || matlabCount~=wantedMatlab
    error('csr:t13:BaselineIdentity','Unexpected source/MATLAB counts in %s.',name);
end
end

function assertPackagePath(root,names)
for k=1:numel(names)
    parts=strsplit(names{k},'.'); relative='';
    for j=1:numel(parts)-1, relative=fullfile(relative,['+' parts{j}]); end
    expected=csr.validation.Artifacts.canonicalPath(fullfile(root,relative,[parts{end} '.m']));
    resolved=csr.validation.Artifacts.canonicalPath(which(names{k}));
    if ~strcmp(expected,resolved)
        error('csr:t13:Path','A different CSR package is active for %s: %s.',names{k},resolved);
    end
end
end

function files=referenceSnapshot(root,candidate)
files=repmat(struct('path','','sha256','','bytes',0),0,1);
roots=cellstr(string(candidate.ReferenceRoots));
for k=1:numel(roots)
    inventory=csr.validation.Artifacts.fileInventory(fullfile(root,roots{k}));
    if isempty(inventory), error('csr:t13:Reference','Empty reference directory: %s.',roots{k}); end
    for j=1:numel(inventory), inventory(j).path=[roots{k} '/' inventory(j).path]; end
    files=[files;inventory(:)]; %#ok<AGROW>
end
individual=cellstr(string(candidate.ReferenceFiles));
for k=1:numel(individual)
    path=fullfile(root,individual{k}); info=dir(path);
    if numel(info)~=1 || info.isdir, error('csr:t13:Reference','Missing reference file: %s.',path); end
    files(end+1,1)=struct('path',individual{k},'sha256',csr.validation.Artifacts.sha256(path),'bytes',info.bytes); %#ok<AGROW>
end
[~,order]=sort({files.path}); files=files(order);
if numel(unique({files.path}))~=numel(files)
    error('csr:t13:Reference','Reference inventory declarations overlap.');
end
end
