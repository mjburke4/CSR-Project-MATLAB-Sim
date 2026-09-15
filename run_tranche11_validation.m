function report = run_tranche11_validation(outputRoot)
%RUN_TRANCHE11_VALIDATION Short matched MAC/HOP replay and focused MATLAB tests.
% Runs prescribed contention draws and controlled delivery, not the campus
% benchmark. The accepted simulator, PHY/ECC and routing sources are unchanged.
% Upload the printed t11.zip even when the replay differs from the reference.
root=fileparts(mfilename('fullpath')); addpath(root,'-begin');
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t11'); end
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyMMdd_HHmmss'));
[~,token]=fileparts(tempname); token=token(max(1,end-3):end);
directory=fullfile(outputRoot,['r' stamp '_' token]);
if isfolder(directory), error('csr:replay:OutputExists','Output already exists: %s.',directory); end
[ok,message]=mkdir(directory);
if ~ok, error('csr:replay:Output','Cannot create output: %s.',message); end
diary(fullfile(directory,'run.log'));
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-11-validation-v1','Tranche',11, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'NativeExecuted',false,'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'CandidateFile','evidence/tranche-11-candidate.json','CandidateSHA256','', ...
    'SourceSnapshotSHA256','','ReferenceSnapshotSHA256','', ...
    'SourceFilesFinal',struct([]),'ReferenceFilesFinal',struct([]), ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'BaselineSourceFilesVerified',0,'BaselineMatlabFilesVerified',0, ...
    'TestFiles',{{}},'ExpectedTestNames',{{}},'TestsExecuted',false,'TestsPassed',false, ...
    'TestCount',0,'PassedTests',0,'FailedTests',0,'IncompleteTests',0,'TestClassesCompleted',0, ...
    'TestResultsFile','tests.csv','ReplayDirectory','replay', ...
    'ReplayCompleted',false,'ReplayMatchesNative',false,'ReplayCaseCount',0, ...
    'ReplayEventCount',0,'ReplayDrawCount',0,'ReplayUnmatchedCount',0, ...
    'FocusedGateExecuted',false,'FullAcceptanceGateExecuted',false,'DiagnosticOnly',true, ...
    'AcceptanceEstablished',false,'NumericalParityEstablished',false, ...
    'EvidenceArchive','t11.zip','InventoryExcludedPaths',{{'metadata.json'}}, ...
    'Artifacts',struct([]),'LocalArtifacts',struct([]), ...
    'Scope',['Prescribed raw contention draws through production MAC/HOP; controlled successful ' ...
        'transport and a synthetic HOP-gated application driver. No RF, real NWK admission, ' ...
        'campus, stochastic population or full protocol parity claim.']);
snapshot=struct([]); references=struct([]); candidate=struct(); originalFailure=[];
try
    assertPackagePath(root,{'csr.mac.Layer','csr.hop.Layer','csr.sim.EventScheduler', ...
        'csr.validation.replayContract','csr.validation.ReplayStreams'});
    candidatePath=fullfile(root,report.CandidateFile);
    candidate=jsondecode(fileread(candidatePath));
    report.CandidateSHA256=csr.validation.Artifacts.sha256(candidatePath);
    report.TestFiles=cellstr(string(candidate.TestFiles));
    report.ExpectedTestNames=cellstr(string(candidate.ExpectedTestNames));
    snapshot=csr.validation.Artifacts.sourceSnapshot(root);
    csr.validation.Artifacts.writeJson(fullfile(directory,'source.json'),snapshot);
    report.SourceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'source.json'));
    baseline=jsondecode(fileread(fullfile(root,candidate.BaselineSourceSnapshot)));
    for k=1:numel(baseline)
        path=fullfile(root,baseline(k).path);
        if ~strcmp(csr.validation.Artifacts.sha256(path),baseline(k).sha256)
            error('csr:replay:BaselineChanged','Accepted baseline file differs: %s.',baseline(k).path);
        end
    end
    report.BaselineSourceFilesVerified=numel(baseline);
    report.BaselineMatlabFilesVerified=sum(endsWith({baseline.path},'.m'));
    if report.BaselineSourceFilesVerified~=225 || report.BaselineMatlabFilesVerified~=124
        error('csr:replay:BaselineIdentity','Expected the accepted 225-file / 124-MATLAB-file baseline.');
    end
    references=referenceSnapshot(root,candidate);
    csr.validation.Artifacts.writeJson(fullfile(directory,'references.json'),references);
    report.ReferenceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'references.json'));
    if ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.FixturePlan)),candidate.FixturePlanSHA256)
        error('csr:replay:PlanChanged','The replay plan differs from the candidate identity.');
    end
    writeMetadata();
    fprintf('Tranche 11: short matched contention and ACK-service replay.\n');
    fprintf('Accepted baseline verified: %d MATLAB files unchanged.\n',report.BaselineMatlabFilesVerified);
    fprintf('Running prescribed MAC/HOP cases; controlled transport, no campus run.\n');
    replay=csr.validation.replayContract(fullfile(directory,'replay'));
    report.ReplayCompleted=logical(replay.DiagnosticCompleted);
    report.ReplayMatchesNative=logical(replay.MatchesNative);
    report.ReplayCaseCount=replay.CaseCount;
    report.ReplayEventCount=replay.EventCount;
    report.ReplayDrawCount=replay.DrawCount;
    report.ReplayUnmatchedCount=replay.UnmatchedCount;
    writeMetadata();
    if ~report.ReplayCompleted || report.ReplayCaseCount<1 || report.ReplayEventCount<1 || report.ReplayDrawCount<1
        error('csr:replay:Incomplete','Replay did not complete the prescribed cases.');
    end
    fprintf('Replay completed: %d cases, %d service observations, %d contention draws.\n', ...
        report.ReplayCaseCount,report.ReplayEventCount,report.ReplayDrawCount);
    if report.ReplayMatchesNative
        fprintf('Recorded ns-3 replay comparisons match within the declared timing resolution.\n');
    else
        fprintf('Replay differences recorded: %d. Preserve t11.zip for first-divergence review.\n', ...
            report.ReplayUnmatchedCount);
    end
    fprintf('Running %d focused MATLAB test classes.\n',numel(report.TestFiles));
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
    if ~namesMatch, error('csr:replay:TestIdentity','Executed test identities differ from the candidate.'); end
    assertSuccess(results);
    checkStableInputs();
    report.FocusedGateExecuted=report.TestsPassed && report.ReplayCompleted && ...
        report.SourceFilesStableDuringRun && report.ReferenceFilesStableDuringRun;
    report.Status='completed';
catch failure
    originalFailure=failure; report.Status='failed';
    report.Failure=struct('Identifier',failure.identifier,'Message',failure.message,'Stack',failure.stack);
    if ~isempty(snapshot) && ~isempty(references)
        try
            checkStableInputs();
        catch inputFailure
            report.InputCheckFailure=struct('Identifier',inputFailure.identifier,'Message',inputFailure.message);
        end
    end
    fprintf(2,'Tranche 11 failed: %s\n',failure.message);
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
fprintf('Tranche 11 focused execution complete: %d/%d MATLAB tests.\n', ...
    report.PassedTests,report.TestCount);

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
            error('csr:replay:InputChanged','Source or reference files changed during execution.');
        end
    end
end

function assertPackagePath(root,names)
for k=1:numel(names)
    parts=strsplit(names{k},'.'); relative='';
    for j=1:numel(parts)-1, relative=fullfile(relative,['+' parts{j}]); end
    expected=csr.validation.Artifacts.canonicalPath(fullfile(root,relative,[parts{end} '.m']));
    resolved=csr.validation.Artifacts.canonicalPath(which(names{k}));
    if ~strcmp(expected,resolved)
        error('csr:replay:Path','A different CSR package is active for %s: %s.',names{k},resolved);
    end
end
end

function files=referenceSnapshot(root,candidate)
files=repmat(struct('path','','sha256','','bytes',0),0,1);
roots=cellstr(string(candidate.ReferenceRoots));
for k=1:numel(roots)
    inventory=csr.validation.Artifacts.fileInventory(fullfile(root,roots{k}));
    if isempty(inventory), error('csr:replay:Reference','Empty reference directory: %s.',roots{k}); end
    for j=1:numel(inventory), inventory(j).path=[roots{k} '/' inventory(j).path]; end
    files=[files;inventory(:)]; %#ok<AGROW>
end
individual=cellstr(string(candidate.ReferenceFiles));
for k=1:numel(individual)
    path=fullfile(root,individual{k}); info=dir(path);
    if numel(info)~=1 || info.isdir, error('csr:replay:Reference','Missing reference file: %s.',path); end
    files(end+1,1)=struct('path',individual{k},'sha256',csr.validation.Artifacts.sha256(path),'bytes',info.bytes); %#ok<AGROW>
end
[~,order]=sort({files.path}); files=files(order);
if numel(unique({files.path}))~=numel(files)
    error('csr:replay:Reference','Reference inventory declarations overlap.');
end
end
