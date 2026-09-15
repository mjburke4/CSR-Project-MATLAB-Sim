function report = run_tranche9_validation(outputRoot,options)
%RUN_TRANCHE9_VALIDATION Early ACK service, controlled contracts and six diagnostics.
% Runs portable unit tests, deterministic contracts, six cases and two controls.
% It does not rerun the accepted campus workload or retained scenario sweep.
root=fileparts(mfilename('fullpath')); addpath(root);
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','t9'); end
if nargin<2, options=struct(); end
options=validatedOptions(options);
[cases,plan]=csr.scenario.ackServiceSuite();
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyMMdd_HHmmss'));
[~,token]=fileparts(tempname);
token=token(max(1,end-7):end);
directory=fullfile(outputRoot,['r' stamp '_' token]);
[ok,message]=mkdir(directory);
if ~ok, error('csr:diagnostic:Output','Cannot create output: %s.',message); end
diary(fullfile(directory,'validation.log'));
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-9-validation-v1','Tranche',9, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'SourceCommit',plan.ns3_source_commit,'MatlabBaseCommit',plan.matlab_base_commit, ...
    'ValidatedTranche8CodeCommit',plan.accepted_tranche8_matlab_commit, ...
    'Options',options,'TestsRequested',options.RunTests,'TestsExecuted',false, ...
    'TestsPassed',false,'TestCount',0,'PassedTests',0,'FailedTests',0,'IncompleteTests',0, ...
    'TestResultsFile','tests/test_results.csv','NativeRequested',false,'NativeExecuted',false, ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'PlannedCaseCount',numel(cases),'CompletedCaseCount',0, ...
    'Cases',repmat(struct('CaseId','','Directory','','ManifestSHA256',''),0,1), ...
    'DiagnosticPlan','diagnostic_plan.json','DiagnosticPlanSHA256','', ...
    'NonperturbationFile','nonperturbation.json','NonperturbationPassed',false, ...
    'CrossSimulatorComparisonExecuted',false,'NumericalParityEstablished',false, ...
    'CrossSimulatorComparisonScope','Application benchmark comparison after return; deterministic contracts compare recorded ns-3 checkpoints during this run.', ...
    'EvidenceArchive','tranche9_evidence.zip', ...
    'ServiceWindowSeconds',plan.service_window_s(:)', ...
    'ServiceWindowEndExclusive',true,'ContractDirectory','contracts', ...
    'ContractsExecuted',false,'ContractsPassed',false, ...
    'EvidenceBoundary',['Six unchanged synthetic stimuli, deterministic subsystem contracts and passive observations; ' ...
        'compare with pinned ns-3 and accepted T8 evidence after return. ' ...
        'Finite-stop backlog remains reported.'], ...
    'ArchivePolicy','CSV, JSON and closed logs; MAT objects remain on execution machine.', ...
    'InventoryExcludedPaths',{{'validation_metadata.json'}});
summaryRows=cell(0,1);
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
    references=referenceSnapshot(root,cases,plan);
    report.ReferenceFiles=references;
    planPath=fullfile(root,'scenarios','ack_service','plan.json');
    copyfile(planPath,fullfile(directory,'diagnostic_plan.json'));
    report.DiagnosticPlanSHA256=csr.validation.Artifacts.sha256(planPath);
    writeControls(); writeReport();
    fprintf('Tranche 9: checking deterministic ACK service and capacity contracts.\n');
    contract=csr.validation.ackServiceContract(fullfile(directory,'contracts'));
    report.ContractsExecuted=true; report.ContractsPassed=contract.Passed; writeReport();
    if ~contract.Passed, error('csr:service:Contract','Deterministic service contract failed.'); end
    if options.RunTests
        fprintf('Tranche 9: running portable unit tests.\n');
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
    controls.passed=controls.completed_control_count==2 && all([controls.cases.passed]);
    if ~controls.passed, error('csr:diagnostic:Perturbation','Incomplete observer controls.'); end
    controls.status='completed'; writeControls(); report.NonperturbationPassed=true;
    report.SourceFilesFinal=csr.validation.Artifacts.sourceSnapshot(root);
    report.ReferenceFilesFinal=referenceSnapshot(root,cases,plan);
    if ~isequal(snapshot,report.SourceFilesFinal) || ~isequal(references,report.ReferenceFilesFinal)
        error('csr:diagnostic:InputChanged','Candidate or references changed during execution.');
    end
    report.SourceFilesStableDuringRun=true; report.ReferenceFilesStableDuringRun=true;
    report.Status='completed'; report.CompletedUTC=csr.validation.Artifacts.utcNow();
    diary('off'); finishEvidence();
    fprintf('Tranche 9 completed: %d/%d tests, %d/%d diagnostics, 2/2 tracing controls.\n', ...
        report.PassedTests,report.TestCount,report.CompletedCaseCount,report.PlannedCaseCount);
    fprintf('Upload %s for controlled-contract and early ACK-service comparison.\n',fullfile(directory,report.EvidenceArchive));
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
    fprintf(2,'Tranche 9 failed; partial evidence remains at %s.\n',directory);
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
options=struct('RunTests',true);
if ~isstruct(given) || ~isscalar(given) || ~all(ismember(fieldnames(given),{'RunTests'}))
    error('csr:diagnostic:Options','Only the logical RunTests option is supported.');
end
if isfield(given,'RunTests'), options.RunTests=given.RunTests; end
validateattributes(options.RunTests,{'logical'},{'scalar'});
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

function files=referenceSnapshot(root,cases,plan)
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
