function report = run_tranche19_validation(outputRoot,options)
%RUN_TRANCHE19_VALIDATION Full-campus queued DATA retry policy experiment.
% Phase: all (default), tests, a128, p128 or finalize. Completed stages can be
% reused only with the same frozen inputs, MATLAB runtime and artifact bytes.
% An interrupted/failed simulator is never resumed; preserve its evidence.
root=fileparts(mfilename('fullpath')); addpath(root,'-begin');
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t19'); end
if nargin<2, options=struct(); end
options=csr.validation.RetryPolicyCheckpoint.options(options);
directory=csr.validation.Artifacts.canonicalPath(outputRoot);
assertOutputPath(root,directory); assertPackagePath(root);
[identity,candidate]=csr.validation.RetryPolicyCheckpoint.identity(root);
[items,plan]=csr.scenario.tranche19Suite();
csr.validation.RetryPolicyCheckpoint.preflight(directory,root,identity,candidate);
if ~isfolder(directory)
    [ok,message]=mkdir(directory);
    if ~ok, error('csr:t19:Output','Cannot create output: %s.',message); end
end
lockPath=fullfile(directory,'.active'); lock=javaObject('java.io.File',lockPath);
if ~lock.createNewFile()
    error('csr:t19:ActiveRun','Output has an active or interrupted invocation; preserve it and use a new directory.');
end
lockCleanup=onCleanup(@()delete(lockPath)); %#ok<NASGU>
[~,token]=fileparts(tempname); logPath=fullfile(directory,['run_' token '.log']);
diary(logPath); diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-19-validation-v1','Tranche',19, ...
    'Status','running','Phase',options.Phase,'StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'NativeExecuted',false,'SourceCommit',candidate.SourceCommit, ...
    'CandidateFile','evidence/tranche-19-candidate.json','CandidateSHA256',identity.CandidateSHA256, ...
    'SourceSnapshotSHA256','','ReferenceSnapshotSHA256','', ...
    'SourceFilesFinal',struct([]),'ReferenceFilesFinal',struct([]), ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'BaselineSourceFilesVerified',candidate.BaselineSourceFiles, ...
    'BaselineMatlabFilesVerified',candidate.BaselineMatlabFiles, ...
    'AllBaselineSourcesUnchanged',false,'UnmodifiedBaselineSourcesUnchanged',true, ...
    'AllowedBaselineModificationsVerified',true,'AllowedModifiedSourceFiles',candidate.AllowedModifiedSourceFiles, ...
    'TestFiles',{cellstr(string(candidate.TestFiles))}, ...
    'ExpectedTestNames',{cellstr(string(candidate.ExpectedTestNames))}, ...
    'TestsExecuted',false,'TestsPassed',false,'TestCount',0,'PassedTests',0, ...
    'FailedTests',0,'IncompleteTests',0,'TestResultsFile','tests/results.csv', ...
    'CompletedCaseCount',0,'PlannedCaseCount',2,'CampusStructuralChecksPassed',false, ...
    'SimulatedSecondsCompleted',0,'PlannedSimulatedSeconds',12000, ...
    'Cases',repmat(struct('CaseId','','Directory','','ManifestSHA256',''),0,1), ...
    'StageReceipts',repmat(struct('Phase','','File','','SHA256',''),0,1), ...
    'FullAcceptanceGateExecuted',false,'AcceptanceEstablished',false, ...
    'NumericalParityEstablished',false,'ComparisonBandPercent',plan.comparison_band_percent, ...
    'CommonRandomNumbersClaimed',false,'SingleSeedScope',true, ...
    'EvidenceArchive','t19.zip','Artifacts',struct([]),'LocalArtifacts',struct([]), ...
    'InventoryExcludedPaths',{{'metadata.json','.active','t19.zip'}}, ...
    'Scope',['Full portable regression plus two fresh original 6000-second campus runs. ' ...
        'Only DATA queued-retry policy differs: actual-tx versus native-provisional. ' ...
        'Real PHY, autonomous routing, continuous timing, no observer or post-stop drain. ' ...
        'Admission prefix omissions are explicit; total and per-flow counters remain complete. ' ...
        'Single-seed effects and descriptive 5-percent comparison bands require return review.']);
try
    writeOnceJson('source.json',identity.SourceFiles);
    writeOnceJson('references.json',identity.ReferenceFiles);
    copyOnce(candidate.Plan,'plan.json'); copyOnce(report.CandidateFile,'candidate.json');
    report.SourceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'source.json'));
    report.ReferenceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'references.json'));
    writeMetadata();
    fprintf('Tranche 19, phase %s: %d expected portable tests, two 6000-second campus cases.\n', ...
        options.Phase,numel(report.ExpectedTestNames));
    fprintf('Verified %d T18 sources; only the two declared HOP policy files changed.\n', ...
        report.BaselineSourceFilesVerified);
    if ismember(options.Phase,{'all','tests'})
        [receipt,reused]=csr.validation.RetryPolicyCheckpoint.begin(directory,'tests',identity);
        if reused
            fprintf('Reusing the verified completed portable regression stage.\n');
        else
            fprintf('Running all top-level portable tests; native subfolder excluded.\n');
            results=runtests(fullfile(root,'tests'),'IncludeSubfolders',false);
            diary(logPath);
            rows=table({results.Name}',[results.Passed]',[results.Failed]', ...
                [results.Incomplete]',[results.Duration]', ...
                'VariableNames',{'Name','Passed','Failed','Incomplete','DurationSeconds'});
            writetable(rows,fullfile(directory,'tests','results.csv'));
            summary=csr.validation.RetryPolicyCheckpoint.testResults(rows,report.ExpectedTestNames,report.TestFiles);
            csr.validation.Artifacts.writeJson(fullfile(directory,'tests','summary.json'),summary);
            attachTestSummary(summary); writeMetadata();
            if ~summary.TestsPassed
                error('csr:t19:Tests','Portable regression did not pass; failed evidence is preserved.');
            end
            checkStableInputs();
            receipt=csr.validation.RetryPolicyCheckpoint.seal(directory,'tests',identity,summary);
        end
        attachTests(receipt); writeMetadata();
    end
    for k=1:numel(items)
        key=items(k).CaseId;
        if ~ismember(options.Phase,{'all',key}), continue; end
        [receipt,reused]=csr.validation.RetryPolicyCheckpoint.begin(directory,key,identity);
        if reused
            fprintf('Reusing the verified completed %s campus stage.\n',key);
        else
            summary=csr.validation.retryPolicyContract(fullfile(directory,key),key,root, ...
                identity.SourceFiles,report.SourceSnapshotSHA256);
            checkStableInputs();
            receipt=csr.validation.RetryPolicyCheckpoint.seal(directory,key,identity,summary);
        end
        attachCase(receipt,key); writeMetadata();
    end
    % Attach all completed stages, including phases executed previously.
    for phase={'tests','a128','p128'}
        key=phase{1};
        required=ismember(options.Phase,{'all','finalize'});
        if required || isfile(fullfile(directory,key,'receipt.json'))
            receipt=csr.validation.RetryPolicyCheckpoint.verify(directory,key,identity);
            if strcmp(key,'tests'), attachTests(receipt); else, attachCase(receipt,key); end
        end
    end
    if report.TestsPassed && report.CompletedCaseCount==2
        report.FullAcceptanceGateExecuted=true; report.Status='completed-review-required';
    else
        report.Status='phase-completed-review-pending';
    end
    checkStableInputs(); report.CompletedUTC=csr.validation.Artifacts.utcNow();
    diary('off'); finishEvidence();
    fprintf('Tranche 19 %s: %d/%d passing tests; %d/2 campus cases.\n', ...
        report.Status,report.PassedTests,report.TestCount,report.CompletedCaseCount);
    fprintf('Upload %s for independent review.\n',fullfile(directory,'t19.zip'));
catch failure
    report.Status='failed'; report.CompletedUTC=csr.validation.Artifacts.utcNow();
    report.Failure=struct('Identifier',failure.identifier,'Message',failure.message,'Stack',failure.stack);
    diary('off');
    try
        finishEvidence();
    catch archiveFailure
        report.EvidencePackagingFailure=struct('Identifier',archiveFailure.identifier,'Message',archiveFailure.message);
        try, writeMetadata(); catch, end
    end
    fprintf(2,'Tranche 19 failed: %s\nPartial evidence remains at %s.\n',failure.message,directory);
    rethrow(failure);
end

    function writeMetadata()
        csr.validation.Artifacts.writeJson(fullfile(directory,'metadata.json'),report);
    end
    function writeOnceJson(relative,value)
        path=fullfile(directory,relative);
        if isfile(path)
            if ~isequal(jsondecode(fileread(path)),value)
                error('csr:t19:OutputIdentity','Existing %s has different inputs.',relative);
            end
        else
            csr.validation.Artifacts.writeJson(path,value);
        end
    end
    function copyOnce(relative,target)
        source=fullfile(root,relative); path=fullfile(directory,target);
        if isfile(path)
            if ~strcmp(csr.validation.Artifacts.sha256(path),csr.validation.Artifacts.sha256(source))
                error('csr:t19:OutputIdentity','Existing %s differs from the candidate.',target);
            end
        else
            [ok,message]=copyfile(source,path);
            if ~ok, error('csr:t19:Output','Cannot copy frozen input: %s.',message); end
        end
    end
    function checkStableInputs()
        current=csr.validation.RetryPolicyCheckpoint.identity(root);
        report.SourceFilesFinal=current.SourceFiles; report.ReferenceFilesFinal=current.ReferenceFiles;
        report.SourceFilesStableDuringRun=isequal(current.SourceFiles,identity.SourceFiles);
        report.ReferenceFilesStableDuringRun=isequal(current.ReferenceFiles,identity.ReferenceFiles);
        if ~isequal(current,identity)
            error('csr:t19:InputChanged','Candidate, source, reference or MATLAB runtime changed during execution.');
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
        computed=csr.validation.RetryPolicyCheckpoint.testResults(rows,report.ExpectedTestNames,report.TestFiles);
        computed=jsondecode(jsonencode(computed));
        if ~isequal(jsondecode(jsonencode(receipt.summary)),stored) || ...
                ~isequal(stored,computed) || ~computed.TestsPassed
            error('csr:t19:Tests','Completed regression does not prove exact passing test membership.');
        end
        attachTestSummary(computed); addReceipt('tests');
    end
    function attachCase(receipt,key)
        stored=jsondecode(fileread(fullfile(directory,key,'summary.json')));
        item=items(strcmp({items.CaseId},key));
        if ~isequaln(jsondecode(jsonencode(receipt.summary)),stored) || ...
                ~strcmp(stored.Schema,'csr-tranche19-queued-retry-summary-v1') || ...
                ~strcmp(stored.CaseId,key) || ~strcmp(stored.Policy,item.Policy) || ...
                ~strcmp(stored.OriginalBenchmarkCaseId,'campus_multihop_6000') || ...
                stored.CompletedCaseCount~=1 || stored.DurationSeconds~=6000 || ...
                stored.SchedulerStopSeconds~=6000 || stored.Seed~=128 || ...
                ~stored.StructuralChecksPassed || ~stored.RealPHY || ~stored.AutonomousRouting || ...
                ~stored.DefaultContinuousTiming || stored.ObserverEnabled || stored.PostHorizonDrain || ...
                ~stored.OriginalAdmissionTracePrefix || ~stored.Admissions.CountsComplete || ...
                stored.Admissions.Attempts~=1710000 || stored.Admissions.TraceRecords~=100000 || ...
                stored.Admissions.OmittedTraceRecords~=1610000 || ...
                stored.ProtocolTraceOmissions~=0 || stored.PhyTraceOmissions~=0 || ...
                stored.FiniteStopPendingIsFailure || stored.AcceptanceEstablished || ...
                stored.NumericalParityEstablished || ~strcmp(stored.Case.CaseId,key) || ...
                ~strcmp(stored.Case.Directory,key) || ...
                ~strcmp(stored.Case.ManifestSHA256, ...
                    csr.validation.Artifacts.sha256(fullfile(directory,key,'case.json')))
            error('csr:t19:CampusCompletion','Completed %s receipt has different or incomplete experiment scope.',key);
        end
        found=find(strcmp({report.Cases.CaseId},key));
        if isempty(found), report.Cases(end+1,1)=stored.Case; else, report.Cases(found)=stored.Case; end
        [~,order]=sort({report.Cases.CaseId}); report.Cases=report.Cases(order);
        report.CompletedCaseCount=numel(report.Cases);
        report.SimulatedSecondsCompleted=6000*report.CompletedCaseCount;
        report.CampusStructuralChecksPassed=report.CompletedCaseCount==2;
        addReceipt(key);
    end
    function addReceipt(phase)
        relative=[phase '/receipt.json'];
        entry=struct('Phase',phase,'File',relative, ...
            'SHA256',csr.validation.Artifacts.sha256(fullfile(directory,relative)));
        found=find(strcmp({report.StageReceipts.Phase},phase));
        if isempty(found), report.StageReceipts(end+1,1)=entry; else, report.StageReceipts(found)=entry; end
        [~,indices]=ismember({report.StageReceipts.Phase},{'tests','a128','p128'});
        [~,order]=sort(indices); report.StageReceipts=report.StageReceipts(order);
    end
    function finishEvidence()
        files=csr.validation.Artifacts.fileInventory(directory,{'metadata.json','.active','t19.zip'});
        local=endsWith({files.path},'.mat') | endsWith({files.path},'.zip');
        report.Artifacts=files(~local); report.LocalArtifacts=files(local);
        writeMetadata();
        zip(fullfile(directory,'t19.zip'),[{report.Artifacts.path},{'metadata.json'}],directory);
    end
end

function assertOutputPath(root,directory)
root=csr.validation.Artifacts.canonicalPath(root);
if strcmp(directory,root) || startsWith(root,[directory filesep])
    error('csr:t19:Output','Output must be separate from the installation and its ancestors.');
end
for name={'+csr','tests','examples','scripts','data','scenarios','evidence'}
    protected=csr.validation.Artifacts.canonicalPath(fullfile(root,name{1}));
    if strcmp(directory,protected) || startsWith(directory,[protected filesep])
        error('csr:t19:Output','Output cannot overwrite source or reference files.');
    end
end
end

function assertPackagePath(root)
names={'csr.sim.NetworkSimulation','csr.sim.EventScheduler','csr.phy.SignalEngine', ...
    'csr.mac.Layer','csr.hop.Layer','csr.hop.validateConfig','csr.nwk.Layer', ...
    'csr.analysis.researchSummary','csr.analysis.performanceSummary','csr.analysis.benchmarkAggregates', ...
    'csr.validation.Artifacts','csr.validation.RetryPolicyCheckpoint', ...
    'csr.validation.retryPolicyContract','csr.scenario.benchmarkSuite','csr.scenario.tranche19Suite'};
for k=1:numel(names)
    parts=strsplit(names{k},'.'); packages=strcat('+',parts(1:end-1));
    expected=csr.validation.Artifacts.canonicalPath(fullfile(root,packages{:},[parts{end} '.m']));
    actual=which(names{k});
    if isempty(actual) || ~strcmp(expected,csr.validation.Artifacts.canonicalPath(actual))
        error('csr:t19:Path','A different installation is active for %s.',names{k});
    end
end
end
