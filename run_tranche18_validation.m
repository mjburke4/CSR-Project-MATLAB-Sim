function report = run_tranche18_validation(outputRoot)
%RUN_TRANCHE18_VALIDATION Diagnose relay/local service without model changes.
% New suite preflight, eleven real-PHY runs, then the retained focused tests.
% Every invocation uses a fresh directory. Return t18.zip even after failure.
root=fileparts(mfilename('fullpath')); addpath(root,'-begin');
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t18'); end
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
assertOutputPath(root,outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyMMdd_HHmm'));
[~,token]=fileparts(tempname); token=token(max(1,end-3):end);
directory=fullfile(outputRoot,['r' stamp '_' token]);
if isfolder(directory), error('csr:t18:OutputExists','Output exists; choose a fresh directory.'); end
[ok,message]=mkdir(directory);
if ~ok, error('csr:t18:Output','Cannot create output: %s.',message); end
logPath=fullfile(directory,'run.log'); diary(logPath);
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-18-validation-v1','Tranche',18, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'NativeExecuted',false,'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'CandidateFile','evidence/tranche-18-candidate.json','CandidateSHA256','', ...
    'SourceSnapshotSHA256','','ReferenceSnapshotSHA256','', ...
    'SourceFilesFinal',struct([]),'ReferenceFilesFinal',struct([]), ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'BaselineSourceFilesVerified',0,'BaselineMatlabFilesVerified',0, ...
    'AllBaselineSourcesUnchanged',false,'AllowedModifiedSourceFilesVerified',0, ...
    'TestFiles',{{}},'ExpectedTestNames',{{}},'TestsExecuted',false,'TestsPassed',false, ...
    'TestCount',0,'PassedTests',0,'FailedTests',0,'IncompleteTests',0, ...
    'TestClassesCompleted',0,'TestResultsFile','tests.csv','RelayDirectory','network', ...
    'RelayCompleted',false,'RelayPassed',false,'RelayCaseCount',0, ...
    'RelayObservedCaseCount',0,'RelayControlCaseCount',0, ...
    'RelayCheckpointCount',0,'RelayFailedCount',0,'NonperturbationPassed',false, ...
    'FocusedGateExecuted',false,'FullAcceptanceGateExecuted',false,'DiagnosticOnly',true, ...
    'AcceptanceEstablished',false,'NumericalParityEstablished',false, ...
    'EvidenceArchive','t18.zip','InventoryExcludedPaths',{{'metadata.json'}}, ...
    'Artifacts',struct([]),'LocalArtifacts',struct([]), ...
    'Scope',['Passive real-PHY relay/local-service diagnosis over three seeds and a campus prefix. ' ...
        'Default continuous transport, PHY/ECC, queues, routing and admission are unchanged. ' ...
        'Finite-stop backlog/loss and absent DACKs remain measurements. Fresh native references ' ...
        'are compared during return review; no exact RNG alignment or numerical acceptance claim.']);
snapshot=struct([]); references=struct([]); candidate=struct(); originalFailure=[]; relayFailure=[];
try
    assertPackagePath(root);
    candidatePath=fullfile(root,report.CandidateFile);
    candidate=jsondecode(fileread(candidatePath));
    if ~strcmp(candidate.Schema,'csr-tranche-18-candidate-v1') || ...
            ~strcmp(candidate.SourceCommit,report.SourceCommit) || ...
            ~isequal(cellstr(string(candidate.SourceFilesExcludedPaths)),{report.CandidateFile})
        error('csr:t18:Candidate','Unexpected candidate identity or excluded paths.');
    end
    report.CandidateSHA256=csr.validation.Artifacts.sha256(candidatePath);
    snapshot=csr.validation.Artifacts.sourceSnapshot(root);
    bound=snapshot(~strcmp({snapshot.path},report.CandidateFile));
    if ~isequal(bound,candidate.SourceFiles)
        error('csr:t18:Candidate','Candidate source membership or hashes changed.');
    end
    verifyBaseline(root,candidate,snapshot);
    report.BaselineSourceFilesVerified=313; report.BaselineMatlabFilesVerified=160;
    report.AllBaselineSourcesUnchanged=true;
    references=referenceSnapshot(root,candidate);
    for label={'Plan','BaselineOwnerEvidence','BaselineCandidate'}
        name=label{1};
        path=csr.validation.ReleaseCheckpoint.checkedPath(root,candidate.(name));
        if ~strcmp(csr.validation.Artifacts.sha256(path),candidate.([name 'SHA256']))
            error('csr:t18:Candidate','Frozen %s binding changed.',name);
        end
    end
    csr.scenario.tranche18Suite();
    csr.validation.Artifacts.writeJson(fullfile(directory,'source.json'),snapshot);
    csr.validation.Artifacts.writeJson(fullfile(directory,'references.json'),references);
    copyfile(candidatePath,fullfile(directory,'candidate.json'));
    copyfile(fullfile(root,candidate.Plan),fullfile(directory,'plan.json'));
    report.SourceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'source.json'));
    report.ReferenceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'references.json'));
    report.TestFiles=cellstr(string(candidate.TestFiles));
    report.ExpectedTestNames=cellstr(string(candidate.ExpectedTestNames));
    if isempty(report.TestFiles) || ~strcmp(report.TestFiles{1},'tests/TestRelayServiceSuite.m') || ...
            numel(unique(report.TestFiles))~=numel(report.TestFiles)
        error('csr:t18:TestIdentity','The new scenario/observer preflight must run first.');
    end
    for k=1:numel(report.TestFiles)
        if isempty(regexp(report.TestFiles{k},'^tests/Test[A-Za-z0-9_]+\.m$','once'))
            error('csr:t18:TestIdentity','Only frozen top-level portable test classes may run.');
        end
        csr.validation.ReleaseCheckpoint.checkedPath(root,report.TestFiles{k});
    end
    writeMetadata();
    fprintf('Tranche 18: relay/local service and admission; all 313 prior source files unchanged.\n');
    fprintf('Running new diagnostic preflight before eleven cases (6900 simulated seconds).\n');
    results=runtests(fullfile(root,report.TestFiles{1})); results=results(:); diary(logPath);
    report.TestClassesCompleted=1; writeTests(results); writeMetadata();
    expected=report.ExpectedTestNames(startsWith(report.ExpectedTestNames,'TestRelayServiceSuite/'));
    verifyNames(results,expected); assertSuccess(results);
    checkStableInputs();
    try
        diagnostic=csr.validation.relayServiceContract(fullfile(directory,'network'), ...
            root,snapshot,report.SourceSnapshotSHA256);
        attachDiagnostic(diagnostic);
    catch failure
        relayFailure=failure; report.RelayFailure=failureRecord(failure);
        partial=fullfile(directory,'network','summary.json');
        if isfile(partial), attachDiagnostic(jsondecode(fileread(partial))); end
        fprintf(2,'Relay diagnostic failed: %s\nContinuing the retained focused tests.\n',failure.message);
    end
    diary(logPath); writeMetadata();
    fprintf('Running remaining focused tests; %d total frozen test methods.\n',numel(report.ExpectedTestNames));
    for k=2:numel(report.TestFiles)
        next=runtests(fullfile(root,report.TestFiles{k})); diary(logPath);
        results=[results;next(:)]; %#ok<AGROW>
        report.TestClassesCompleted=k; writeTests(results); writeMetadata();
    end
    verifyNames(results,report.ExpectedTestNames);
    report.TestsPassed=~isempty(results) && all([results.Passed]) && ...
        ~any([results.Failed]) && ~any([results.Incomplete]);
    assertSuccess(results);
    if ~isempty(relayFailure), rethrow(relayFailure); end
    if ~report.RelayCompleted || ~report.RelayPassed || report.RelayCaseCount~=11 || ...
            report.RelayObservedCaseCount~=10 || report.RelayControlCaseCount~=1 || ...
            report.RelayCheckpointCount~=132 || report.RelayFailedCount~=0 || ~report.NonperturbationPassed
        error('csr:t18:Incomplete','Diagnostic cases, structural checks or observer control are incomplete.');
    end
    checkStableInputs();
    report.FocusedGateExecuted=true; report.Status='completed';
catch failure
    originalFailure=failure; report.Status='failed'; report.Failure=failureRecord(failure);
    if ~isempty(snapshot) && ~isempty(references)
        try, checkStableInputs();
        catch inputFailure, report.InputCheckFailure=failureRecord(inputFailure); end
    end
    fprintf(2,'Tranche 18 failed: %s\n',failure.message);
end
report.CompletedUTC=csr.validation.Artifacts.utcNow(); diary('off');
try
    inventory=csr.validation.Artifacts.fileInventory(directory,{'metadata.json','t18.zip'});
    local=endsWith({inventory.path},'.mat') | endsWith({inventory.path},'.zip');
    report.LocalArtifacts=inventory(local); report.Artifacts=inventory(~local);
    writeMetadata();
    zip(fullfile(directory,'t18.zip'),[{report.Artifacts.path},{'metadata.json'}],directory);
    fprintf('Upload %s for independent review.\n',fullfile(directory,'t18.zip'));
catch packagingFailure
    report.EvidencePackagingFailure=failureRecord(packagingFailure);
    try, writeMetadata(); catch, end %#ok<CTCH>
    fprintf(2,'Could not package all evidence; partial files remain at %s.\n',directory);
    if isempty(originalFailure), rethrow(packagingFailure); end
end
if ~isempty(originalFailure), rethrow(originalFailure); end
fprintf('Tranche 18 completed: %d/%d focused tests, 11/11 runs. Return review remains required.\n', ...
    report.PassedTests,report.TestCount);

    function writeMetadata()
        csr.validation.Artifacts.writeJson(fullfile(directory,'metadata.json'),report);
    end
    function writeTests(value)
        rows=table({value.Name}',[value.Passed]',[value.Failed]',[value.Incomplete]',[value.Duration]', ...
            'VariableNames',{'Name','Passed','Failed','Incomplete','DurationSeconds'});
        writetable(rows,fullfile(directory,'tests.csv'));
        report.TestsExecuted=~isempty(value); report.TestCount=numel(value);
        report.PassedTests=sum([value.Passed]); report.FailedTests=sum([value.Failed]);
        report.IncompleteTests=sum([value.Incomplete]);
    end
    function attachDiagnostic(value)
        report.RelayCompleted=value.DiagnosticCompleted; report.RelayPassed=value.Passed;
        report.RelayCaseCount=value.CaseCount; report.RelayObservedCaseCount=value.ObservedCaseCount;
        report.RelayControlCaseCount=value.ControlCaseCount; report.RelayCheckpointCount=value.CheckpointCount;
        report.RelayFailedCount=value.FailedCount; report.NonperturbationPassed=value.NonperturbationPassed;
    end
    function checkStableInputs()
        report.SourceFilesFinal=csr.validation.Artifacts.sourceSnapshot(root);
        report.ReferenceFilesFinal=referenceSnapshot(root,candidate);
        report.SourceFilesStableDuringRun=isequal(snapshot,report.SourceFilesFinal);
        report.ReferenceFilesStableDuringRun=isequal(references,report.ReferenceFilesFinal);
        if ~report.SourceFilesStableDuringRun || ~report.ReferenceFilesStableDuringRun
            error('csr:t18:InputChanged','Source or reference artifacts changed during execution.');
        end
    end
end

function verifyBaseline(root,candidate,snapshot)
path=csr.validation.ReleaseCheckpoint.checkedPath(root,candidate.BaselineSourceSnapshot);
if ~strcmp(csr.validation.Artifacts.sha256(path),candidate.BaseSourceSnapshotSHA256)
    error('csr:t18:Baseline','The frozen Tranche 17 source inventory changed.');
end
baseline=jsondecode(fileread(path));
if numel(baseline)~=313 || sum(endsWith({baseline.path},'.m'))~=160 || ...
        numel(unique({baseline.path}))~=313
    error('csr:t18:Baseline','Expected 313 unchanged baseline sources, including 160 MATLAB files.');
end
for k=1:numel(baseline)
    match=find(strcmp({snapshot.path},baseline(k).path));
    if numel(match)~=1 || ~strcmp(snapshot(match).sha256,baseline(k).sha256)
        error('csr:t18:Baseline','Previous source changed: %s.',baseline(k).path);
    end
end
end

function files=referenceSnapshot(root,candidate)
names=cellstr(string(candidate.ReferenceFiles));
if isempty(names) || numel(unique(names))~=numel(names) || ...
        (isfield(candidate,'ReferenceRoots') && ~isempty(candidate.ReferenceRoots))
    error('csr:t18:Reference','Distinct explicit reference files are required.');
end
files=repmat(struct('path','','sha256','','bytes',0),numel(names),1);
for k=1:numel(names)
    path=csr.validation.ReleaseCheckpoint.checkedPath(root,names{k}); info=dir(path);
    files(k)=struct('path',names{k},'sha256',csr.validation.Artifacts.sha256(path),'bytes',info.bytes);
end
[~,order]=sort({files.path}); files=files(order);
if ~isequal(files,candidate.ReferenceFileInventory)
    error('csr:t18:Reference','Frozen reference membership, hashes or byte counts changed.');
end
end

function verifyNames(results,expected)
actual=sort(string({results.Name})); expected=sort(string(expected));
if isempty(actual) || ~isequal(actual(:),expected(:)) || numel(unique(actual))~=numel(actual)
    error('csr:t18:TestIdentity','Executed test membership differs from the frozen candidate.');
end
end

function record=failureRecord(failure)
record=struct('Identifier',failure.identifier,'Message',failure.message,'Stack',failure.stack);
end

function assertOutputPath(root,output)
root=csr.validation.Artifacts.canonicalPath(root);
if strcmp(root,output) || startsWith(root,[output filesep])
    error('csr:t18:Output','Output must not be the installation or an ancestor.');
end
for name={'+csr','tests','examples','scripts','scenarios','data','evidence'}
    protected=fullfile(root,name{1});
    if strcmp(output,protected) || startsWith(output,[protected filesep])
        error('csr:t18:Output','Output must not overwrite source or reference trees.');
    end
end
end

function assertPackagePath(root)
names={'csr.sim.NetworkSimulation','csr.sim.EventScheduler','csr.sim.AckServiceDiagnostics', ...
    'csr.sim.LinkDiagnostics','csr.phy.SignalEngine','csr.mac.Layer','csr.hop.Layer','csr.nwk.Layer', ...
    'csr.scenario.tranche18Suite','csr.validation.relayServiceContract','csr.validation.Artifacts', ...
    'csr.validation.ReleaseCheckpoint','csr.analysis.researchSummary','csr.analysis.performanceSummary'};
for k=1:numel(names)
    parts=strsplit(names{k},'.'); folders=strcat('+',parts(1:end-1));
    expected=csr.validation.Artifacts.canonicalPath(fullfile(root,folders{:},[parts{end} '.m']));
    actual=which(names{k});
    if isempty(actual) || ~strcmp(expected,csr.validation.Artifacts.canonicalPath(actual))
        error('csr:t18:Path','A different installation is active for %s.',names{k});
    end
end
end
