function report = run_tranche10_validation(outputRoot,options)
%RUN_TRANCHE10_VALIDATION Timing contracts, retained regressions and campus6000.
% Default execution includes all portable tests, 29 retained cases, 18 sweeps,
% six unchanged diagnostics, two tracing controls and the full campus case.
% RunTests=false or RunCampus=false produces diagnostic-only evidence.
root=fileparts(mfilename('fullpath')); addpath(root);
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t10'); end
if nargin<2, options=struct(); end
options=validatedOptions(options);
[cases,validationPlan,retained,sweeps,campus,retainedPlan,sweepPlan]=csr.scenario.tranche10Suite();
plan=jsondecode(fileread(fullfile(root,validationPlan.diagnostic_plan)));
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyMMdd_HHmmss'));
[~,token]=fileparts(tempname);
token=token(max(1,end-7):end);
directory=fullfile(outputRoot,['r' stamp '_' token]);
[ok,message]=mkdir(directory);
if ~ok, error('csr:diagnostic:Output','Cannot create output: %s.',message); end
diary(fullfile(directory,'validation.log'));
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-10-validation-v1','Tranche',10, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'SourceCommit',plan.ns3_source_commit,'MatlabBaseCommit',validationPlan.matlab_base_commit, ...
    'ValidatedTranche9CodeCommit',validationPlan.accepted_tranche9_matlab_commit, ...
    'ValidatedTranche8CodeCommit',plan.accepted_tranche8_matlab_commit, ...
    'Options',options,'TestsRequested',options.RunTests,'TestsExecuted',false, ...
    'TestsPassed',false,'TestCount',0,'PassedTests',0,'FailedTests',0,'IncompleteTests',0, ...
    'TestResultsFile','tests/test_results.csv','NativeRequested',false,'NativeExecuted',false, ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'PlannedCaseCount',numel(cases),'CompletedCaseCount',0, ...
    'Cases',repmat(struct('CaseId','','Directory','','ManifestSHA256',''),0,1), ...
    'DiagnosticPlan','diagnostic_plan.json','DiagnosticPlanSHA256','', ...
    'ValidationPlan','validation_plan.json','ValidationPlanSHA256','', ...
    'RetainedPlan','retained_plan.json','RetainedPlannedCount',numel(retained),'RetainedCompletedCount',0, ...
    'RetainedCases',repmat(struct('CaseId','','Kind','','Name','','Directory','','ManifestSHA256',''),0,1), ...
    'SweepPlan','sweep_plan.json','SweepPlannedCount',numel(sweeps),'SweepCompletedCount',0, ...
    'SweepCases',repmat(struct('CaseId','','Kind','','Name','','Experiment','','Parameter','', ...
        'Value',0,'Seed',0,'Directory','','DiagnosticsDirectory','','ManifestSHA256',''),0,1), ...
    'CampusRequested',options.RunCampus,'CampusExecuted',false, ...
    'CampusCase',struct('CaseId','','Directory','','ManifestSHA256',''), ...
    'FullAcceptanceGateExecuted',false,'DiagnosticOnly',~(options.RunTests && options.RunCampus), ...
    'NonperturbationFile','nonperturbation.json','NonperturbationPassed',false, ...
    'CrossSimulatorComparisonExecuted',false,'NumericalParityEstablished',false, ...
    'CrossSimulatorComparisonScope','Application benchmark comparison after return; deterministic contracts compare recorded ns-3 checkpoints during this run.', ...
    'EvidenceArchive','tranche10_evidence.zip', ...
    'ServiceWindowSeconds',plan.service_window_s(:)', ...
    'ServiceWindowEndExclusive',true,'ContractDirectory','k', ...
    'ContractsExecuted',false,'ContractsPassed',false, ...
    'ContractCases',repmat(struct('Kind','','Directory','','Schema','','SummarySHA256','', ...
        'CheckpointCount',0,'Passed',false),0,1), ...
    'EvidenceBoundary',['Default execution covers three contract families, all portable tests, retained scenarios/sweeps, ' ...
        'six unchanged diagnostics, two tracing controls and campus6000; compare with pinned ns-3, ' ...
        'accepted T9 diagnostics and accepted T7 campus after return. Finite-stop backlog and bounded ' ...
        'campus admission-trace omissions remain reported. Skipping tests or campus is diagnostic-only.'], ...
    'ArchivePolicy','CSV, JSON and closed logs; MAT objects remain on execution machine.', ...
    'InventoryExcludedPaths',{{'validation_metadata.json'}});
summaryRows=cell(0,1); retainedRows=cell(0,1); sweepRows=cell(0,1); performanceRows=cell(0,1);
controls=struct('schema','csr-ack-service-nonperturbation-v1', ...
    'status','running','planned_control_count',2,'completed_control_count',0, ...
    'passed',false,'cases',repmat(struct('case_id','','observer_on_directory','', ...
        'observer_off_directory','','statistics_equal',false,'config_equal',false, ...
        'compared_files',struct([]),'passed',false),0,1));
try
    snapshot=csr.validation.Artifacts.sourceSnapshot(root);
    report.SourceFiles=snapshot;
    sourcePath=fullfile(directory,'source_snapshot.json');
    csr.validation.Artifacts.writeJson(sourcePath,snapshot);
    report.SourceSnapshotSHA256=csr.validation.Artifacts.sha256(sourcePath);
    references=referenceSnapshot(root,cases,plan,validationPlan,campus);
    report.ReferenceFiles=references;
    planPath=fullfile(root,'scenarios','ack_service','plan.json');
    copyfile(planPath,fullfile(directory,'diagnostic_plan.json'));
    report.DiagnosticPlanSHA256=csr.validation.Artifacts.sha256(planPath);
    validationPlanPath=fullfile(root,'scenarios','contention_timing','plan.json');
    copyfile(validationPlanPath,fullfile(directory,'validation_plan.json'));
    report.ValidationPlanSHA256=csr.validation.Artifacts.sha256(validationPlanPath);
    csr.validation.Artifacts.writeJson(fullfile(directory,'retained_plan.json'),retainedPlan);
    csr.validation.Artifacts.writeJson(fullfile(directory,'sweep_plan.json'),sweepPlan);
    writetable(struct2table(rmfield(sweeps,'Config'),'AsArray',true),fullfile(directory,'sweep_cases.csv'));
    writeControls(); writeReport();
    fprintf('Tranche 10: checking MAC contention, receiver timing and retained ACK contracts.\n');
    for contractIndex=1:numel(validationPlan.contract_references)
        reference=validationPlan.contract_references(contractIndex);
        relative=['k/' reference.kind];
        switch reference.kind
            case 'mac', contract=csr.validation.contentionContract(fullfile(directory,relative));
            case 'rx', contract=csr.validation.receiverTimingContract(fullfile(directory,relative));
            case 'ack', contract=csr.validation.ackServiceContract(fullfile(directory,relative));
            otherwise, error('csr:timing:Contract','Unknown contract family.');
        end
        if ~strcmp(contract.Schema,reference.summary_schema) || ~contract.Passed || ...
                contract.CheckpointCount<1 || contract.UnmatchedCount~=0 || contract.FailedCount~=0
            error('csr:timing:Contract','Deterministic %s contract failed.',reference.kind);
        end
        report.ContractCases(end+1,1)=struct('Kind',reference.kind,'Directory',relative, ...
            'Schema',contract.Schema,'SummarySHA256',csr.validation.Artifacts.sha256( ...
                fullfile(directory,relative,'summary.json')), ...
            'CheckpointCount',contract.CheckpointCount,'Passed',contract.Passed);
        fprintf('  %s: %d/%d checkpoints passed.\n',reference.kind,contract.CheckpointCount,contract.CheckpointCount);
        writeReport();
    end
    report.ContractsExecuted=true; report.ContractsPassed=true; writeReport();
    if options.RunTests
        fprintf('Tranche 10: running portable unit tests.\n');
        testDirectory=fullfile(directory,'tests'); mkdir(testDirectory);
        results=runtests(fullfile(root,'tests'),'IncludeSubfolders',false);
        testSummary=table({results.Name}',[results.Passed]',[results.Failed]', ...
            [results.Incomplete]',[results.Duration]', ...
            'VariableNames',{'Name','Passed','Failed','Incomplete','DurationSeconds'});
        writetable(testSummary,fullfile(testDirectory,'test_results.csv'));
        save(fullfile(testDirectory,'test_results.mat'),'results');
        report.TestsExecuted=true; report.TestCount=numel(results);
        report.PassedTests=sum([results.Passed]); report.FailedTests=sum([results.Failed]);
        report.IncompleteTests=sum([results.Incomplete]);
        report.TestsPassed=~isempty(results) && all([results.Passed]) && ...
            ~any([results.Failed]) && ~any([results.Incomplete]);
        writeReport(); assertSuccess(results); clear results;
    end
    fprintf('Tranche 10: running all %d retained scenarios with this candidate.\n',numel(retained));
    for retainedIndex=1:numel(retained)
        item=retained(retainedIndex);
        fprintf('Retained %d/%d: %s (%g simulated seconds).\n', ...
            retainedIndex,numel(retained),item.CaseId,item.Config.DurationSeconds);
        result=csr.runScenario(item.Config);
        relative=['r/' item.StorageKey]; caseDirectory=fullfile(directory,relative);
        gatewayRewrite=strcmp(item.Kind,'routed') && result.Config.Nwk.SendOnlyToGateway;
        if isfield(result,'NodeNwkStatistics') && ~gatewayRewrite
            input=''; if ~isempty(item.ScenarioFile), input=fullfile(root,item.ScenarioFile); end
            csr.validation.exportResearchCase(result,caseDirectory,root,snapshot,input);
        else
            exportRetainedLegacy(result,caseDirectory,root,snapshot,item);
        end
        if strcmp(item.Kind,'routed') && sum(result.NodeNwkStatistics.ControlQueueRejections)~=0
            error('csr:timing:Retained','Retained routed case rejected controls.');
        end
        row=retainedSummary(result,item); retainedRows{end+1,1}=row; %#ok<AGROW>
        writetable(struct2table(vertcat(retainedRows{:}),'AsArray',true),fullfile(directory,'retained_summary.csv'));
        report.RetainedCases(end+1,1)=struct('CaseId',item.CaseId,'Kind',item.Kind, ...
            'Name',item.Name,'Directory',relative,'ManifestSHA256', ...
            csr.validation.Artifacts.sha256(fullfile(caseDirectory,'case_manifest.json')));
        report.RetainedCompletedCount=numel(report.RetainedCases); writeReport();
        fprintf('  Completed in %.1f wall seconds: %d admitted, %d delivered, %d pending.\n', ...
            result.Metadata.RuntimeSeconds,row.Generated,row.Received,row.Pending);
        clear result;
    end
    fprintf('Tranche 10: running the unchanged %d load and recovery sweeps.\n',numel(sweeps));
    for sweepIndex=1:numel(sweeps)
        item=sweeps(sweepIndex);
        fprintf('Sweep %d/%d: %s (%g simulated seconds).\n', ...
            sweepIndex,numel(sweeps),item.CaseId,item.Config.DurationSeconds);
        result=csr.runScenario(item.Config);
        relative=['s/' item.StorageKey '/raw']; rawDirectory=fullfile(directory,relative);
        [row,~]=csr.validation.exportResearchCase(result,rawDirectory,root,snapshot);
        analysisRelative=['s/' item.StorageKey '/analysis'];
        analysisDirectory=fullfile(directory,analysisRelative); mkdir(analysisDirectory);
        [performance,applications]=csr.analysis.performanceSummary(result);
        performance=addSweepIdentity(performance,item);
        writetable(struct2table(performance,'AsArray',true),fullfile(analysisDirectory,'performance_summary.csv'));
        writetable(applications,fullfile(analysisDirectory,'applications.csv'));
        sweepRows{end+1,1}=addSweepIdentity(row,item); %#ok<AGROW>
        performanceRows{end+1,1}=performance; %#ok<AGROW>
        writetable(struct2table(vertcat(sweepRows{:}),'AsArray',true),fullfile(directory,'scenario_summary.csv'));
        writetable(struct2table(vertcat(performanceRows{:}),'AsArray',true),fullfile(directory,'performance_summary.csv'));
        report.SweepCases(end+1,1)=struct('CaseId',item.CaseId,'Kind','sweep','Name',item.CaseId, ...
            'Experiment',item.Experiment,'Parameter',item.Parameter,'Value',item.Value,'Seed',item.Seed, ...
            'Directory',relative,'DiagnosticsDirectory',analysisRelative, ...
            'ManifestSHA256',csr.validation.Artifacts.sha256(fullfile(rawDirectory,'case_manifest.json')));
        report.SweepCompletedCount=numel(report.SweepCases); writeReport();
        fprintf('  Completed in %.1f wall seconds: %d admitted, %d delivered, %d pending.\n', ...
            result.Metadata.RuntimeSeconds,row.Generated,row.Received,row.Pending);
        clear result;
    end
    for k=1:numel(cases)
        item=cases(k);
        fprintf('Diagnostic %d/%d: %s (%g simulated seconds), service window 300 to 320 s, ACK tracing enabled.\n', ...
            k,numel(cases),item.CaseId,item.DurationSeconds);
        observer=csr.sim.AckServiceDiagnostics(plan.service_max_records,plan.service_window_s(:)');
        simulation=csr.sim.NetworkSimulation(item.Config,observer);
        result=simulation.run();
        storageKey=item.StorageKey;
        caseDirectory=fullfile(directory,'b',storageKey);
        rawDirectory=fullfile(caseDirectory,'raw');
        [row,~]=csr.validation.exportResearchCase(result,rawDirectory,root,snapshot, ...
            fullfile(root,item.ScenarioFile));
        % Preserve completed raw observations before a diagnostic cap or
        % correlation failure rejects the case's acceptance manifest.
        observer.assertComplete();
        analysisDirectory=fullfile(caseDirectory,'analysis'); mkdir(analysisDirectory);
        [performance,applications]=csr.analysis.performanceSummary(result);
        writetable(struct2table(performance,'AsArray',true),fullfile(analysisDirectory,'performance_summary.csv'));
        writetable(applications,fullfile(analysisDirectory,'applications.csv'));
        sourceFile=fullfile(rawDirectory,'protocol_trace.csv');
        aggregateOptions=struct('Scenario',item.Scenario,'BucketWidthSeconds',item.BucketWidthSeconds, ...
            'SourceFile','raw/protocol_trace.csv','SourceFileSHA256',csr.validation.Artifacts.sha256(sourceFile), ...
            'ScenarioSHA256',item.ScenarioSHA256,'ProfileID',item.ProfileId, ...
            'SourceSnapshotSHA256',report.SourceSnapshotSHA256);
        [series,provenance]=csr.analysis.benchmarkAggregates(result,aggregateOptions);
        aggregateFile=fullfile(analysisDirectory,'aggregates.csv'); writetable(series,aggregateFile);
        provenance.output=struct('path','analysis/aggregates.csv', ...
            'sha256',csr.validation.Artifacts.sha256(aggregateFile));
        csr.validation.Artifacts.writeJson(fullfile(analysisDirectory,'aggregate_provenance.json'),provenance);
        files=csr.validation.Artifacts.fileInventory(caseDirectory);
        local=endsWith({files.path},'.mat');
        manifest=struct('schema','csr-matlab-benchmark-case-v1','status','completed', ...
            'case_id',item.CaseId,'base_case_id',item.BaseCaseId,'storage_key',storageKey, ...
            'scenario',item.Scenario,'scenario_sha256',item.ScenarioSHA256, ...
            'profile_id',item.ProfileId,'source_kind',item.SourceKind, ...
            'ns3_source_commit',report.SourceCommit,'matlab_version',version, ...
            'matlab_release',version('-release'),'runtime',report.Runtime, ...
            'duration_s',item.DurationSeconds,'seed',item.Seed, ...
            'bucket_width_s',item.BucketWidthSeconds,'opnet_available',false, ...
            'reference_directory',item.ReferenceDirectory,'source_files',snapshot, ...
            'source_snapshot_sha256',report.SourceSnapshotSHA256, ...
            'structural_checks_passed',true,'numerical_parity_established',false, ...
            'admission_trace_omitted_records',result.Statistics.OmittedApplicationAdmissionRecords, ...
            'admission_counts_complete',true,'observer_enabled',true, ...
            'observer_diagnostics',result.LinkDiagnostics, ...
            'service_observer_enabled',true,'service_diagnostics',result.ServiceDiagnostics, ...
            'service_reference_directory',item.ServiceReferenceDirectory, ...
            'files',files(~local),'local_files',files(local));
        manifestPath=fullfile(caseDirectory,'benchmark_manifest.json');
        csr.validation.Artifacts.writeJson(manifestPath,manifest);
        row.CaseId=item.CaseId; row.BaseCaseId=item.BaseCaseId; row.SourceKind=item.SourceKind;
        row.Attempts=sum(result.ApplicationAdmissionStatistics.Attempts);
        row.AdmissionBlocked=row.Attempts-row.Generated;
        row.OmittedApplicationAdmissionRecords=result.Statistics.OmittedApplicationAdmissionRecords;
        summaryRows{end+1,1}=row; %#ok<AGROW>
        writetable(struct2table(vertcat(summaryRows{:}),'AsArray',true),fullfile(directory,'benchmark_summary.csv'));
        report.Cases(end+1,1)=struct('CaseId',item.CaseId,'Directory',['b/' storageKey], ...
            'ManifestSHA256',csr.validation.Artifacts.sha256(manifestPath));
        report.CompletedCaseCount=numel(report.Cases); writeReport();
        fprintf('  Completed in %.1f wall seconds: %d admitted, %d delivered, %d pending.\n', ...
            result.Metadata.RuntimeSeconds,row.Generated,row.Received,row.Pending);
        onStatistics=result.Statistics; onConfig=result.Config;
        clear result simulation observer;
        if ismember(storageKey,plan.control_keys)
            fprintf('  Repeating %s with tracing disabled to check unchanged behavior.\n',item.CaseId);
            disabled=csr.runScenario(item.Config);
            offDirectory=fullfile(directory,'c',storageKey,'raw');
            csr.validation.exportResearchCase(disabled,offDirectory,root,snapshot,fullfile(root,item.ScenarioFile));
            compared=compareUnchangedFiles(rawDirectory,offDirectory);
            equalStats=isequaln(onStatistics,disabled.Statistics);
            equalConfig=isequaln(onConfig,disabled.Config);
            passed=equalStats && equalConfig && all([compared.equal]);
            controls.cases(end+1,1)=struct('case_id',item.CaseId, ...
                'observer_on_directory',['b/' storageKey '/raw'], ...
                'observer_off_directory',['c/' storageKey '/raw'], ...
                'statistics_equal',equalStats,'config_equal',equalConfig, ...
                'compared_files',compared,'passed',passed);
            controls.completed_control_count=numel(controls.cases); writeControls();
            if ~passed, error('csr:diagnostic:Perturbation','Observer changed results for %s.',item.CaseId); end
            fprintf('  Tracing on/off checks passed for %s.\n',item.CaseId);
            clear disabled;
        end
    end
    if options.RunCampus
        fprintf('Tranche 10 campus benchmark: %s (6000 simulated seconds).\n',campus.CaseId);
        fprintf('  This full workload previously took about 72 wall minutes. MATLAB reports completion after the simulation returns.\n');
        result=csr.runScenario(campus.Config);
        report.CampusCase=exportCampus(result,campus,directory,root,snapshot,report);
        report.CampusExecuted=true; writeReport();
        fprintf('  Campus completed in %.1f wall seconds: %d admitted, %d delivered, %d pending.\n', ...
            result.Metadata.RuntimeSeconds,result.Statistics.Generated,result.Statistics.Received,result.Statistics.Pending);
        clear result;
    else
        fprintf('Tranche 10 campus omitted by RunCampus=false; this is diagnostic-only evidence.\n');
    end
    controls.passed=controls.completed_control_count==2 && all([controls.cases.passed]);
    if ~controls.passed, error('csr:diagnostic:Perturbation','Incomplete observer controls.'); end
    controls.status='completed'; writeControls(); report.NonperturbationPassed=true;
    report.SourceFilesFinal=csr.validation.Artifacts.sourceSnapshot(root);
    report.ReferenceFilesFinal=referenceSnapshot(root,cases,plan,validationPlan,campus);
    if ~isequal(snapshot,report.SourceFilesFinal) || ~isequal(references,report.ReferenceFilesFinal)
        error('csr:diagnostic:InputChanged','Candidate or references changed during execution.');
    end
    report.SourceFilesStableDuringRun=true; report.ReferenceFilesStableDuringRun=true;
    report.FullAcceptanceGateExecuted=options.RunTests && report.TestsPassed && options.RunCampus && ...
        report.CampusExecuted && report.ContractsPassed && report.NonperturbationPassed && ...
        report.RetainedCompletedCount==29 && report.SweepCompletedCount==18 && report.CompletedCaseCount==6;
    report.Status='completed'; report.CompletedUTC=csr.validation.Artifacts.utcNow();
    diary('off'); finishEvidence();
    fprintf('Tranche 10 completed: %d/%d tests, %d/%d diagnostics, 2/2 tracing controls.\n', ...
        report.PassedTests,report.TestCount,report.CompletedCaseCount,report.PlannedCaseCount);
    fprintf('Upload %s for timing-contract, regression and campus comparison.\n',fullfile(directory,report.EvidenceArchive));
catch failure
    report.Status='failed'; report.CompletedUTC=csr.validation.Artifacts.utcNow();
    report.Failure=struct('Identifier',failure.identifier,'Message',failure.message);
    diary('off');
    try
        writeControls(); finishEvidence();
    catch archiveFailure
        report.EvidencePackagingFailure=struct('Identifier',archiveFailure.identifier,'Message',archiveFailure.message);
        writeReport();
    end
    fprintf(2,'Tranche 10 failed; partial evidence remains at %s.\n',directory);
    rethrow(failure);
end
    function writeReport()
        csr.validation.Artifacts.writeJson(fullfile(directory,'validation_metadata.json'),report);
    end
    function writeControls()
        csr.validation.Artifacts.writeJson(fullfile(directory,'nonperturbation.json'),controls);
    end
    function finishEvidence()
        inventory=csr.validation.Artifacts.fileInventory(directory,{'validation_metadata.json',report.EvidenceArchive});
        local=endsWith({inventory.path},'.mat');
        report.LocalArtifacts=inventory(local); report.Artifacts=inventory(~local); writeReport();
        paths=[{report.Artifacts.path},{'validation_metadata.json'}];
        zip(fullfile(directory,report.EvidenceArchive),paths,directory);
    end
end

function options=validatedOptions(given)
options=struct('RunTests',true,'RunCampus',true);
if ~isstruct(given) || ~isscalar(given) || ~all(ismember(fieldnames(given),{'RunTests','RunCampus'}))
    error('csr:diagnostic:Options','Only logical RunTests and RunCampus options are supported.');
end
for field=fieldnames(given)', options.(field{1})=given.(field{1}); end
validateattributes(options.RunTests,{'logical'},{'scalar'});
validateattributes(options.RunCampus,{'logical'},{'scalar'});
end

function compared=compareUnchangedFiles(onDirectory,offDirectory)
names={'trace.csv','protocol_trace.csv','phy_trace.csv','nodes.csv','mac_nodes.csv', ...
    'hop_nodes.csv','nwk_nodes.csv','routes.csv','neighbors.csv', ...
    'application_admission_statistics.csv','application_admission_trace.csv','scenario.csv'};
compared=repmat(struct('path','','observer_on_sha256','','observer_off_sha256','','equal',false),numel(names),1);
for k=1:numel(names)
    on=csr.validation.Artifacts.sha256(fullfile(onDirectory,names{k}));
    off=csr.validation.Artifacts.sha256(fullfile(offDirectory,names{k}));
    compared(k)=struct('path',names{k},'observer_on_sha256',on,'observer_off_sha256',off,'equal',strcmp(on,off));
end
end

function row=retainedSummary(result,item)
s=result.Statistics;
row=struct('CaseId',item.CaseId,'Kind',item.Kind,'Name',item.Name, ...
    'Scenario',result.Config.Name,'Seed',result.Config.Seed, ...
    'DurationSeconds',result.Config.DurationSeconds,'Generated',s.Generated, ...
    'Received',s.Received,'Dropped',s.Dropped,'Pending',s.Pending, ...
    'ApplicationBytesReceived',s.ApplicationBytesReceived, ...
    'PhysicalAttempts',s.PhysicalAttempts,'PhysicalReceived',s.PhysicalReceived, ...
    'PhysicalDropped',s.PhysicalDropped,'PhysicalPending',s.PhysicalPending, ...
    'RuntimeSeconds',result.Metadata.RuntimeSeconds,'StructuralChecksPassed',true);
end

function exportRetainedLegacy(result,directory,root,snapshot,item)
% Preserve the schemas of foundation, MAC/HOP and source-gateway fixtures.
% The gateway fixture rewrites the requested destination after app_generate;
% researchSummary intentionally requires an unchanged destination instead.
csr.validation.Artifacts.checkSnapshot(root,snapshot);
if isfolder(directory), error('csr:timing:ExistingCase','Retained case output already exists.'); end
csr.analysis.exportResults(result,directory);
s=result.Statistics;
names={'Generated','Received','Dropped','Pending','PhysicalAttempts', ...
    'PhysicalReceived','PhysicalDropped','PhysicalPending','ApplicationBytesReceived', ...
    'OmittedTraceRecords','OmittedPhyTraceRecords'};
for k=1:numel(names)
    validateattributes(s.(names{k}),{'numeric'},{'scalar','real','finite','integer','nonnegative'});
end
if ~isequaln(result.Config,csr.scenario.validate(item.Config)) || ...
        ~result.Config.Trace.Enabled || s.OmittedTraceRecords~=0 || s.OmittedPhyTraceRecords~=0 || ...
        s.Generated~=s.Received+s.Dropped+s.Pending || ...
        s.PhysicalAttempts~=s.PhysicalReceived+s.PhysicalDropped+s.PhysicalPending
    error('csr:timing:RetainedAccounting','Retained configuration, trace completeness or accounting failed.');
end
expected=0;
for k=1:numel(result.Config.Traffic)
    flow=result.Config.Traffic(k);
    if flow.StartSeconds<=result.Config.DurationSeconds
        expected=expected+min(flow.PacketCount, ...
            floor((result.Config.DurationSeconds-flow.StartSeconds)/flow.IntervalSeconds)+1);
    end
end
if s.Generated~=expected || sum(result.NodeStatistics.Generated)~=s.Generated || ...
        sum(result.NodeStatistics.Received)~=s.Received || sum(result.NodeStatistics.Dropped)~=s.Dropped
    error('csr:timing:RetainedAccounting','Retained generation or node totals disagree.');
end
trace=result.Trace;
sent=trace(strcmp(trace.Event,'app_generate'),:);
received=trace(strcmp(trace.Event,'app_receive'),:);
if any(~isfinite(trace.TimeSeconds)) || any(diff(trace.TimeSeconds)<0) || ...
        any(trace.TimeSeconds<0 | trace.TimeSeconds>result.Config.DurationSeconds) || ...
        height(sent)~=s.Generated || height(received)~=s.Received || ...
        numel(unique(sent.PacketId))~=height(sent) || numel(unique(received.PacketId))~=height(received)
    error('csr:timing:RetainedIdentity','Retained trace order, identities or counts failed.');
end
[known,index]=ismember(received.PacketId,sent.PacketId);
if ~all(known), error('csr:timing:RetainedIdentity','Retained delivery has no generated application.'); end
destination=sent.PeerId(index);
scope='Retained foundation or fixed-path MAC/HOP scenario; no autonomous NWK layer is present.';
if isfield(result,'NodeNwkStatistics')
    if ~strcmp(item.Kind,'routed') || ~result.Config.Nwk.SendOnlyToGateway
        error('csr:timing:RetainedScope','Custom network export requires the retained source-gateway fixture.');
    end
    gateways=[result.Config.Nodes([result.Config.Nodes.Capability]==2).Id];
    if numel(gateways)~=1
        error('csr:timing:RetainedGateway','The retained gateway rewrite requires one configured gateway.');
    end
    % NWK Layer.pump rewrites source applications after app_generate. This
    % fixed fixture has exactly one gateway, so accepted final deliveries
    % target that gateway while the generation trace retains the request.
    destination=repmat(gateways,size(destination));
    hop=result.NodeHopStatistics; nwk=result.NodeNwkStatistics;
    for field={'PendingData','ResendQueueDepth','DackHoldCount','ControlPending','ControlPendingTargets'}
        validateattributes(hop.(field{1}),{'numeric'},{'vector','real','finite','integer','nonnegative'});
    end
    for field={'PendingCustody','WaitingForRoute','WaitingForHop','PendingControlMessages'}
        validateattributes(nwk.(field{1}),{'numeric'},{'vector','real','finite','integer','nonnegative'});
    end
    if any(nwk.PendingCustody>result.Config.Nwk.QueueLimit) || ...
            any(result.NodeMacStatistics.MaxDataQueueDepth>result.Config.Mac.DataQueueLimit)
        error('csr:timing:RetainedOwnership','Retained gateway ownership exceeds a configured queue bound.');
    end
    scope=['Retained source-gateway fixture with full MAC/HOP/NWK tables; unique configured gateway ' ...
        'is the final destination after the source-defined SendOnlyToGateway rewrite.'];
end
if any(received.NodeId~=destination) || ...
        any(received.ApplicationBytes~=sent.ApplicationBytes(index)) || ...
        any(received.TimeSeconds<sent.TimeSeconds(index)) || ...
        sum(received.ApplicationBytes)~=s.ApplicationBytesReceived
    error('csr:timing:RetainedIdentity','Retained delivery endpoint, bytes or timing failed.');
end
row=retainedSummary(result,item);
writetable(struct2table(row,'AsArray',true),fullfile(directory,'retained_summary.csv'));
files=csr.validation.Artifacts.fileInventory(directory); local=endsWith({files.path},'.mat');
manifest=struct('schema','csr-matlab-retained-case-v1','status','completed', ...
    'execution_completed',true,'source_files_stable',true, ...
    'case_id',item.CaseId,'kind',item.Kind,'name',item.Name,'storage_key',item.StorageKey, ...
    'factory',item.Factory,'fixture',item.Fixture,'scenario',result.Config.Name, ...
    'seed',result.Config.Seed,'duration_s',result.Config.DurationSeconds, ...
    'stack',result.Config.Stack,'application_profile',result.Config.ApplicationProfile, ...
    'matlab_version',version,'matlab_release',version('-release'), ...
    'ns3_source_commit',result.Metadata.SourceCommit,'source_files',snapshot, ...
    'completed_utc',csr.validation.Artifacts.utcNow(),'structural_checks_passed',true, ...
    'comparison_scope',scope, ...
    'numerical_parity_established',false,'files',files(~local),'local_files',files(local));
csr.validation.Artifacts.checkSnapshot(root,snapshot);
csr.validation.Artifacts.writeJson(fullfile(directory,'case_manifest.json'),manifest);
end

function row=addSweepIdentity(row,item)
row.CaseId=item.CaseId; row.Experiment=item.Experiment;
row.Parameter=item.Parameter; row.Value=item.Value;
end

function entry=exportCampus(result,item,directory,root,snapshot,report)
caseDirectory=fullfile(directory,'b','campus'); rawDirectory=fullfile(caseDirectory,'raw');
[row,~]=csr.validation.exportResearchCase(result,rawDirectory,root,snapshot, ...
    fullfile(root,item.ScenarioFile));
analysisDirectory=fullfile(caseDirectory,'analysis'); mkdir(analysisDirectory);
[performance,applications]=csr.analysis.performanceSummary(result);
writetable(struct2table(performance,'AsArray',true),fullfile(analysisDirectory,'performance_summary.csv'));
writetable(applications,fullfile(analysisDirectory,'applications.csv'));
sourceFile=fullfile(rawDirectory,'protocol_trace.csv');
options=struct('Scenario',item.Scenario,'BucketWidthSeconds',item.BucketWidthSeconds, ...
    'SourceFile','raw/protocol_trace.csv','SourceFileSHA256',csr.validation.Artifacts.sha256(sourceFile), ...
    'ScenarioSHA256',item.ScenarioSHA256,'ProfileID',item.ProfileId, ...
    'SourceSnapshotSHA256',report.SourceSnapshotSHA256);
[series,provenance]=csr.analysis.benchmarkAggregates(result,options);
aggregateFile=fullfile(analysisDirectory,'aggregates.csv'); writetable(series,aggregateFile);
provenance.output=struct('path','analysis/aggregates.csv','sha256',csr.validation.Artifacts.sha256(aggregateFile));
csr.validation.Artifacts.writeJson(fullfile(analysisDirectory,'aggregate_provenance.json'),provenance);
files=csr.validation.Artifacts.fileInventory(caseDirectory); local=endsWith({files.path},'.mat');
manifest=struct('schema','csr-matlab-benchmark-case-v1','status','completed', ...
    'case_id',item.CaseId,'storage_key','campus','scenario',item.Scenario, ...
    'scenario_sha256',item.ScenarioSHA256,'profile_id',item.ProfileId,'source_kind',item.SourceKind, ...
    'ns3_source_commit',report.SourceCommit,'matlab_version',version, ...
    'matlab_release',version('-release'),'runtime',report.Runtime, ...
    'duration_s',item.DurationSeconds,'seed',item.Seed,'bucket_width_s',item.BucketWidthSeconds, ...
    'opnet_available',item.OpnetAvailable,'reference_directory',item.ReferenceDirectory, ...
    'source_files',snapshot,'source_snapshot_sha256',report.SourceSnapshotSHA256, ...
    'structural_checks_passed',true,'numerical_parity_established',false, ...
    'admission_trace_omitted_records',result.Statistics.OmittedApplicationAdmissionRecords, ...
    'admission_counts_complete',true,'observer_enabled',false,'service_observer_enabled',false, ...
    'files',files(~local),'local_files',files(local));
path=fullfile(caseDirectory,'benchmark_manifest.json');
csr.validation.Artifacts.writeJson(path,manifest);
row.CaseId=item.CaseId; row.SourceKind=item.SourceKind;
row.Attempts=sum(result.ApplicationAdmissionStatistics.Attempts);
row.AdmissionBlocked=row.Attempts-row.Generated;
row.OmittedApplicationAdmissionRecords=result.Statistics.OmittedApplicationAdmissionRecords;
writetable(struct2table(row,'AsArray',true),fullfile(directory,'campus_summary.csv'));
entry=struct('CaseId',item.CaseId,'Directory','b/campus', ...
    'ManifestSHA256',csr.validation.Artifacts.sha256(path));
end

function files=referenceSnapshot(root,cases,diagnosticPlan,plan,campus)
files=serviceReferenceSnapshot(root,cases,diagnosticPlan);
campusFiles=campusReferenceSnapshot(root,campus);
files=[files(:);campusFiles(:)];
for k=1:numel(plan.contract_references)
    reference=plan.contract_references(k);
    if ~strcmp(reference.kind,'ack'), verifyTimingReference(root,reference,plan.ns3_source_commit); end
end
verifyNativeBuild(root,plan.ns3_source_commit);
for k=1:numel(plan.reference_directories)
    relative=plan.reference_directories{k};
    inventory=csr.validation.Artifacts.fileInventory(fullfile(root,relative));
    for j=1:numel(inventory), inventory(j).path=[relative '/' inventory(j).path]; end
    files=[files;inventory(:)]; %#ok<AGROW>
end
for k=1:numel(plan.accepted_anchors)
    item=plan.accepted_anchors(k); checkedReferenceFile(root,item);
    files(end+1,1)=struct('path',item.path,'sha256',item.sha256,'bytes',item.bytes); %#ok<AGROW>
end
for k=1:numel(plan.reference_files)
    item=plan.reference_files(k); checkedReferenceFile(root,item);
    files(end+1,1)=struct('path',item.path,'sha256',item.sha256,'bytes',item.bytes); %#ok<AGROW>
end
[~,order]=sort({files.path}); files=files(order);
keep=true(size(files));
for k=2:numel(files)
    if strcmp(files(k).path,files(k-1).path)
        if ~isequal(files(k),files(k-1))
            error('csr:timing:Reference','Conflicting reference inventory declarations.');
        end
        keep(k)=false;
    end
end
files=files(keep);
end

function verifyNativeBuild(root,pin)
record=jsondecode(fileread(fullfile(root,'evidence','tranche-10-native-build.json')));
if ~strcmp(record.schema,'csr-tranche10-native-engine-rebuild-v1') || ...
        ~strcmp(record.status,'passed') || ~record.engine_rebuilt || ...
        ~strcmp(record.source_commit,pin) || ...
        ~strcmp(record.engine_commit,'6b5cd24ea80713ce16d88575869aedd6f432bdae') || ...
        ~record.engine_tracked_sources_unchanged || ~record.csr_tracked_sources_unchanged || ...
        ~record.copied_csr_module_files_match || record.configure_record.exit_code~=0 || ...
        record.build_record.exit_code~=0 || ~record.build_record.output_captured_after_process_closed || ...
        record.nothing_pending_record.exit_code~=0 || ~record.nothing_pending_record.nothing_pending || ...
        ~record.native_contract_executed || record.smoke_contract.checkpoint_count~=101 || ...
        ~record.smoke_contract.t9_reference_bytes_equal || ~record.smoke_contract.inputs_unchanged || ...
        ~strcmp(record.published_artifact_root,'evidence/tranche-10-native-build') || ...
        ~strcmp(record.original_manifest.path,'evidence/tranche-10-native-build/manifest.json')
    error('csr:timing:NativeBuild','Fresh native build provenance failed.');
end
checkedReferenceFile(root,record.original_manifest);
buildRoot=fullfile(root,record.published_artifact_root);
for k=1:numel(record.artifacts), checkedReferenceFile(buildRoot,record.artifacts(k)); end
inventory=csr.validation.Artifacts.fileInventory(buildRoot);
if numel(inventory)~=numel(record.artifacts)+1 || ...
        numel(unique({record.artifacts.path}))~=numel(record.artifacts)
    error('csr:timing:NativeBuild','Native build artifact membership changed.');
end
recheck=jsondecode(fileread(fullfile(root,'evidence','tranche-10-source-recheck.json')));
if ~strcmp(recheck.schema,'csr-tranche10-source-recheck-v1') || ~strcmp(recheck.status,'passed') || ...
        ~strcmp(recheck.source_commit,pin) || ~recheck.source_tracked_clean || ...
        ~strcmp(recheck.branch,'main') || ~strcmp(recheck.repository,'mjburke4/CSR-Project-NS3-part2')
    error('csr:timing:SourceRecheck','Pinned authoritative source recheck failed.');
end
end

function verifyTimingReference(root,reference,pin)
directory=fullfile(root,reference.directory);
manifest=jsondecode(fileread(fullfile(directory,'manifest.json')));
if ~strcmp(manifest.schema,reference.reference_schema) || ~strcmp(manifest.status,'passed') || ...
        ~strcmp(manifest.source_commit,pin) || ~manifest.source_headers_unchanged || ...
        ~manifest.native_contract_executed || ~manifest.engine_rebuilt || ...
        manifest.compile_returncode~=0 || manifest.run_returncode~=0 || ...
        manifest.checkpoint_count<1 || manifest.case_count<1
    error('csr:timing:Reference','Native timing contract execution or source identity failed.');
end
checkedReferenceFile(root,manifest.contract_source);
checkedReferenceFile(root,manifest.runner_source);
checkedReferenceFile(root,manifest.engine_build_record);
for k=1:numel(manifest.artifacts), checkedReferenceFile(directory,manifest.artifacts(k)); end
inventory=csr.validation.Artifacts.fileInventory(directory);
if numel(inventory)~=numel(manifest.artifacts)+1 || ...
        numel(unique({manifest.artifacts.path}))~=numel(manifest.artifacts)
    error('csr:timing:Reference','Native timing reference membership differs.');
end
summary=jsondecode(fileread(fullfile(directory,'summary.json')));
if ~strcmp(summary.Schema,reference.summary_schema) || ~summary.Passed || ...
        summary.CheckpointCount~=manifest.checkpoint_count || ...
        summary.UnmatchedCount~=0 || summary.FailedCount~=0 || ...
        ~strcmp(summary.ReferenceSHA256,csr.validation.Artifacts.sha256(fullfile(directory,'checkpoints.csv')))
    error('csr:timing:Reference','Native timing checkpoint summary failed.');
end
end

function files=serviceReferenceSnapshot(root,cases,plan)
referenceRoot=fullfile(root,'evidence','tranche-8-ns3-reference');
suite=jsondecode(fileread(fullfile(referenceRoot,'manifest.json')));
if ~strcmp(suite.schema,'csr-tranche8-link-diagnostic-reference-suite-v1') || ...
        ~strcmp(suite.status,'completed') || ~strcmp(suite.ns3_source_commit,plan.ns3_source_commit) || ...
        ~suite.source_files_stable || ~suite.input_files_stable || ...
        ~strcmp(suite.build_manifest_sha256,csr.validation.Artifacts.sha256(fullfile(referenceRoot,'build.json'))) || ...
        numel(suite.cases)~=10
    error('csr:diagnostic:Reference','Reference suite is incomplete or uses another source.');
end
for k=1:numel(suite.files), checkedReferenceFile(referenceRoot,suite.files(k)); end
for k=1:numel(cases)
    item=cases(k); index=find(strcmp({suite.cases.case_id},item.CaseId));
    if numel(index)~=1, error('csr:diagnostic:Reference','Missing or duplicate reference case.'); end
    entry=suite.cases(index);
    checkedReferenceFile(referenceRoot,struct('path',entry.manifest,'sha256',entry.manifest_sha256));
    directory=fullfile(root,item.ReferenceDirectory);
    manifest=jsondecode(fileread(fullfile(directory,'manifest.json')));
    if ~strcmp(manifest.schema,'csr-tranche7-benchmark-reference-case-v1') || ...
            ~strcmp(manifest.status,'completed') || ~manifest.tranche8_diagnostics || ...
            ~strcmp(manifest.case_id,item.CaseId) || ...
            ~strcmp(manifest.ns3_source_commit,plan.ns3_source_commit) || ...
            ~strcmp(manifest.case.scenario_sha256,item.ScenarioSHA256) || ...
            ~strcmp(manifest.case.scenario,item.Scenario) || manifest.case.seed~=item.Seed || ...
            manifest.case.duration_s~=item.DurationSeconds || ...
            ~strcmp(manifest.case.profile_id,item.ProfileId) || ...
            manifest.case.bucket_width_s~=item.BucketWidthSeconds || ...
            ~strcmp(manifest.nonperturbation.status,'passed')
        error('csr:diagnostic:Reference','Reference identity, completion or tracing control failed.');
    end
    if item.Seed==128 && (~manifest.baseline_anchor.app_trace_byte_exact || ...
            ~manifest.baseline_anchor.app_admission_diagnostics_equal_except_labels || ...
            ~manifest.baseline_anchor.ns3_aggregates_equal_except_labels)
        error('csr:diagnostic:Reference','Seed-128 reference differs from accepted T7.');
    end
    inventory=csr.validation.Artifacts.fileInventory(directory);
    if numel(inventory)~=numel(manifest.files)+1 || ...
            numel(unique({manifest.files.path}))~=numel(manifest.files)
        error('csr:diagnostic:Reference','Reference file membership differs from manifest.');
    end
    for j=1:numel(manifest.files), checkedReferenceFile(directory,manifest.files(j)); end
end
anchor=fullfile(root,plan.baseline_anchor.archive);
if ~strcmp(csr.validation.Artifacts.sha256(anchor),plan.baseline_anchor.archive_sha256)
    error('csr:diagnostic:Reference','Accepted MATLAB Tranche 8 evidence archive changed.');
end
verifyServiceReference(root,cases,plan);
verifyContractReference(root);
files=repmat(struct('path','','sha256','','bytes',0),0,1);
for relative={'evidence/tranche-8-ns3-reference','evidence/tranche-7-ns3-reference','evidence/tranche-7-benchmark-inputs','evidence/tranche-9-ns3-reference','evidence/tranche-9-contract-reference'}
    inventory=csr.validation.Artifacts.fileInventory(fullfile(root,relative{1}));
    for j=1:numel(inventory), inventory(j).path=[relative{1} '/' inventory(j).path]; end
    files=[files;inventory(:)]; %#ok<AGROW>
end
info=dir(anchor);
files(end+1,1)=struct('path',plan.baseline_anchor.archive, ...
    'sha256',csr.validation.Artifacts.sha256(anchor),'bytes',info.bytes);
[~,order]=sort({files.path}); files=files(order);
end

function verifyServiceReference(root,cases,plan)
directory=fullfile(root,'evidence','tranche-9-ns3-reference');
suite=jsondecode(fileread(fullfile(directory,'manifest.json')));
if ~strcmp(suite.schema,'csr-tranche9-ack-service-reference-suite-v1') || ...
        ~strcmp(suite.status,'completed') || ~strcmp(suite.ns3_source_commit,plan.ns3_source_commit) || ...
        ~strcmp(suite.plan_sha256,csr.validation.Artifacts.sha256(fullfile(root,'scenarios','ack_service','plan.json'))) || ...
        ~suite.source_files_stable || ~suite.input_files_stable || ...
        ~suite.all_observer_on_off_checks_passed || ~suite.all_accepted_t8_anchors_passed || ...
        ~suite.closed_artifacts_reverified || numel(suite.cases)~=numel(cases) || ...
        ~strcmp(suite.build_manifest_sha256,csr.validation.Artifacts.sha256(fullfile(directory,'build.json')))
    error('csr:service:Reference','Incomplete or changed ns-3 service reference.');
end
build=jsondecode(fileread(fullfile(directory,'build.json')));
if ~strcmp(build.schema,'csr-tranche9-ack-service-reference-build-v1') || ...
        build.observer_compile.exit_code~=0 || ~build.source_headers_match_preserved_build || ...
        ~build.standalone_runner_compiled || ...
        ~strcmp(build.observer_helper_sha256,csr.validation.Artifacts.sha256(fullfile(root,'scripts','ns3','tranche9-service-observer.h'))) || ...
        ~strcmp(build.inherited_feedback_helper_sha256,csr.validation.Artifacts.sha256(fullfile(root,'scripts','ns3','tranche8-link-observer.h')))
    error('csr:service:Reference','ns-3 observer build is not bound to this candidate.');
end
% Absolute input paths become sanitized struct keys after jsondecode. Read
% their unique JSON property/hash pairs directly, independent of checkout root.
buildText=fileread(fullfile(directory,'build.json'));
generators={'run_tranche9_ns3_service.py','run_tranche8_ns3_diagnostics.py', ...
    'run_tranche7_ns3_reference.py','run_tranche4_ns3_reference.py'};
for k=1:numel(generators)
    escaped=regexptranslate('escape',generators{k});
    pattern=['"[^"\r\n]*/scripts/' escaped '"\s*:\s*"([a-f0-9]{64})"'];
    hashes=regexp(buildText,pattern,'tokens');
    if numel(hashes)~=1 || ...
            ~strcmp(hashes{1}{1},csr.validation.Artifacts.sha256(fullfile(root,'scripts',generators{k})))
        error('csr:service:Reference','Observer generator differs from the executed build.');
    end
end
for k=1:numel(suite.files), checkedReferenceFile(directory,suite.files(k)); end
expectedCount=numel(suite.files)+1;
for k=1:numel(cases)
    item=cases(k); index=find(strcmp({suite.cases.storage_key},item.StorageKey));
    if numel(index)~=1, error('csr:service:Reference','Missing or duplicate ns-3 service case.'); end
    row=suite.cases(index);
    expected=[item.StorageKey '/manifest.json'];
    if ~strcmp(row.manifest,expected) || ~strcmp(row.case_id,item.CaseId)
        error('csr:service:Reference','Service case path or identity mismatch.');
    end
    checkedReferenceFile(directory,struct('path',expected,'sha256',row.manifest_sha256));
    caseDirectory=fullfile(directory,item.StorageKey);
    manifest=jsondecode(fileread(fullfile(caseDirectory,'manifest.json')));
    entry=plan.cases(k); if iscell(entry), entry=entry{1}; end
    if ~strcmp(manifest.schema,'csr-tranche9-ack-service-reference-case-v1') || ...
            ~strcmp(manifest.status,'completed') || ~strcmp(manifest.ns3_source_commit,plan.ns3_source_commit) || ...
            ~isequal(orderfields(manifest.case),orderfields(entry)) || ...
            ~strcmp(manifest.nonperturbation.status,'passed') || ...
            ~strcmp(manifest.accepted_t8_anchor.status,'passed') || ...
            ~strcmp(manifest.runner_sha256,build.runner_sha256)
        error('csr:service:Reference','Service reference provenance or controls failed.');
    end
    inventory=csr.validation.Artifacts.fileInventory(caseDirectory);
    if numel(inventory)~=numel(manifest.files)+1 || ...
            numel(unique({manifest.files.path}))~=numel(manifest.files)
        error('csr:service:Reference','Service reference membership mismatch.');
    end
    for j=1:numel(manifest.files), checkedReferenceFile(caseDirectory,manifest.files(j)); end
    expectedCount=expectedCount+numel(manifest.files)+1;
end
if numel(csr.validation.Artifacts.fileInventory(directory))~=expectedCount
    error('csr:service:Reference','Unexpected file in service reference suite.');
end
end

function verifyContractReference(root)
directory=fullfile(root,'evidence','tranche-9-contract-reference');
manifest=jsondecode(fileread(fullfile(directory,'manifest.json')));
if ~strcmp(manifest.schema,'csr-tranche9-ack-contract-reference-v1') || ...
        ~strcmp(manifest.status,'passed') || ...
        ~strcmp(manifest.source_commit,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b') || ...
        ~manifest.source_headers_unchanged || ~manifest.native_contract_executed || ...
        manifest.compile_returncode~=0 || manifest.run_returncode~=0 || ...
        manifest.checkpoint_count~=101 || manifest.case_count~=6 || ...
        ~strcmp(manifest.contract_source.path,'scripts/ns3/tranche9_ack_contract.cc') || ...
        ~strcmp(manifest.runner_source.path,'scripts/run_tranche9_ack_contract.py')
    error('csr:service:Reference','Native contract execution or source identity failed.');
end
checkedReferenceFile(root,manifest.contract_source);
checkedReferenceFile(root,manifest.runner_source);
for k=1:numel(manifest.artifacts), checkedReferenceFile(directory,manifest.artifacts(k)); end
inventory=csr.validation.Artifacts.fileInventory(directory);
if numel(inventory)~=numel(manifest.artifacts)+1 || ...
        numel(unique({manifest.artifacts.path}))~=numel(manifest.artifacts)
    error('csr:service:Reference','Native contract reference membership differs.');
end
summary=jsondecode(fileread(fullfile(directory,'summary.json')));
if ~strcmp(summary.Schema,'csr-tranche9-ack-service-contract-v1') || ~summary.Passed || ...
        summary.CheckpointCount~=101 || summary.UnmatchedCount~=0 || summary.FailedCount~=0 || ...
        ~strcmp(summary.ReferenceSHA256,csr.validation.Artifacts.sha256(fullfile(directory,'checkpoints.csv')))
    error('csr:service:Reference','Native contract checkpoint summary failed.');
end
end

function checkedReferenceFile(directory,entry)
path=csr.validation.Artifacts.canonicalPath(fullfile(directory,entry.path));
directory=csr.validation.Artifacts.canonicalPath(directory);
if ~startsWith(path,[directory filesep]) || ~isfile(path) || ...
        ~strcmp(csr.validation.Artifacts.sha256(path),entry.sha256)
    error('csr:diagnostic:Reference','Missing or changed reference artifact.');
end
if isfield(entry,'bytes')
    info=dir(path);
    if info.bytes~=entry.bytes, error('csr:diagnostic:Reference','Reference size mismatch.'); end
end
end


function files=campusReferenceSnapshot(root,cases)
referenceRoot=fullfile(root,'evidence','tranche-7-ns3-reference');
suite=jsondecode(fileread(fullfile(referenceRoot,'manifest.json')));
if ~strcmp(suite.schema,'csr-tranche7-benchmark-reference-suite-v1') || ...
        ~strcmp(suite.status,'completed') || ~suite.source_files_stable || ~suite.input_files_stable || ...
        ~strcmp(suite.ns3_source_commit,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b') || ...
        ~strcmp(suite.build_manifest_sha256,csr.validation.Artifacts.sha256(fullfile(referenceRoot,'build.json')))
    error('csr:benchmark:Reference','Reference suite or build provenance is incomplete.');
end
for k=1:numel(suite.files)
    checkedReferenceFile(referenceRoot,suite.files(k));
end
for k=1:numel(suite.cases)
    item=suite.cases(k);
    checkedReferenceFile(referenceRoot,struct('path',item.manifest,'sha256',item.manifest_sha256));
end
inputs=jsondecode(fileread(fullfile(root,'evidence','tranche-7-benchmark-inputs','manifest.json')));
if ~strcmp(inputs.schema,'csr-tranche7-benchmark-inputs-v1') || ...
        ~strcmp(inputs.source_archive_sha256,'5ae5a14ba36918e19d274a9f2385eb00dd9b63de518b72b728fc373a29be5b73')
    error('csr:benchmark:Reference','Recovered benchmark input provenance differs from the source archive.');
end
for k=1:numel(inputs.files), checkedReferenceFile(root,inputs.files(k)); end
for k=1:numel(cases)
    relative=cases(k).ReferenceDirectory;
    directory=fullfile(root,relative);
    manifestPath=fullfile(directory,'manifest.json');
    if ~isfile(manifestPath), error('csr:benchmark:Reference','Pinned reference manifest is missing.'); end
    manifest=jsondecode(fileread(manifestPath));
    if ~strcmp(manifest.schema,'csr-tranche7-benchmark-reference-case-v1') || ...
            ~strcmp(manifest.status,'completed') || ...
            ~strcmp(manifest.case_id,cases(k).CaseId) || ...
            ~strcmp(manifest.ns3_source_commit,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b') || ...
            ~strcmp(manifest.case.scenario,cases(k).Scenario) || ...
            ~strcmp(manifest.case.scenario_sha256,cases(k).ScenarioSHA256) || ...
            ~strcmp(manifest.case.profile_id,cases(k).ProfileId) || ...
            ~strcmp(manifest.case.source_kind,cases(k).SourceKind) || ...
            manifest.case.duration_s~=cases(k).DurationSeconds || manifest.case.seed~=cases(k).Seed || ...
            manifest.case.bucket_width_s~=cases(k).BucketWidthSeconds || ...
            manifest.case.opnet_available~=cases(k).OpnetAvailable
        error('csr:benchmark:Reference','Pinned reference identity or completion differs from the case.');
    end
    inventory=csr.validation.Artifacts.fileInventory(directory);
    if isempty(inventory), error('csr:benchmark:Reference','A populated pinned reference is required.'); end
    declared=manifest.files;
    if numel(declared)+1~=numel(inventory) || ...
            numel(unique({declared.path}))~=numel(declared)
        error('csr:benchmark:Reference','Reference inventory has missing, duplicate or extra files.');
    end
    for j=1:numel(declared)
        match=find(strcmp({inventory.path},declared(j).path));
        if numel(match)~=1 || ~strcmp(inventory(match).sha256,declared(j).sha256) || ...
                inventory(match).bytes~=declared(j).bytes
            error('csr:benchmark:Reference','Reference artifact changed: %s.',declared(j).path);
        end
    end
end
% Bind all packaged references and recovered source inputs even for a
% selected diagnostic run, including the suite/build provenance above.
files=repmat(struct('path','','sha256','','bytes',0),0,1);
for relative={'evidence/tranche-7-ns3-reference','evidence/tranche-7-benchmark-inputs'}
    inventory=csr.validation.Artifacts.fileInventory(fullfile(root,relative{1}));
    for j=1:numel(inventory), inventory(j).path=[relative{1} '/' inventory(j).path]; end
    files=[files;inventory(:)]; %#ok<AGROW>
end
[~,index]=sort({files.path}); files=files(index);
end
