function report = run_tranche7_validation(outputRoot,options)
%RUN_TRANCHE7_VALIDATION Campus6000 and focused historical-profile benchmarks.
% Default: full portable regression followed by all three benchmark cases.
% Options: RunTests=true, IncludeNative=false, Cases={} (catalog defaults).
% No Python or OPNET license is required on the MATLAB execution machine.
root=fileparts(mfilename('fullpath')); addpath(root);
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','tranche7_validation'); end
if nargin<2, options=struct(); end
options=validatedOptions(options);
[cases,plan]=csr.scenario.benchmarkSuite(struct('Cases',{options.Cases}));
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyyyMMdd_HHmmss_SSS'));
[~,token]=fileparts(tempname);
directory=fullfile(outputRoot,['run_' stamp '_' token]);
[ok,message]=mkdir(directory);
if ~ok, error('csr:validation:Output','Cannot create output: %s.',message); end
diary(fullfile(directory,'validation.log'));
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-matlab-tranche-7-validation-v1','Tranche',7, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'MatlabBaseCommit','b53653ed822d85db2fd4d351fb4a49bb1dd739ec', ...
    'ValidatedTranche6CodeCommit','21c0a3f024c9efffdbd11c8059f1540a67c19b1a', ...
    'Options',options,'TestsRequested',options.RunTests,'TestsExecuted',false, ...
    'TestsPassed',false,'TestCount',0,'PassedTests',0,'FailedTests',0,'IncompleteTests',0, ...
    'NativeRequested',options.IncludeNative,'NativeExecuted',false, ...
    'RegressionStatus','not_run','RegressionEvidenceDirectory','','RegressionMetadataSHA256','', ...
    'SourceFilesStableDuringRun',false,'ReferenceFilesStableDuringRun',false, ...
    'PlannedCaseCount',numel(cases),'CompletedCaseCount',0, ...
    'Cases',repmat(struct('CaseId','','Directory','','ManifestSHA256',''),0,1), ...
    'BenchmarkPlan','benchmark_plan.json','CatalogSHA256',plan.CatalogSHA256, ...
    'CrossSimulatorComparisonExecuted',false,'NumericalParityEstablished',false, ...
    'EvidenceArchive','tranche7_evidence.zip', ...
    'EvidenceBoundary',['Benchmark execution and structural accounting only. ' ...
        'Compare the returned aggregates with pinned ns-3 and archived OPNET separately. ' ...
        'Finite-stop loss/pending work and bounded admission-trace omissions remain reported.'], ...
    'ArchivePolicy','CSV, JSON and closed logs; MAT objects and nested ZIPs remain on the execution machine.', ...
    'InventoryExcludedPaths',{{'validation_metadata.json'}});
summaryRows=cell(0,1);
try
    snapshot=csr.validation.Artifacts.sourceSnapshot(root);
    report.SourceFiles=snapshot;
    snapshotPath=fullfile(directory,'source_snapshot.json');
    csr.validation.Artifacts.writeJson(snapshotPath,snapshot);
    report.SourceSnapshotSHA256=csr.validation.Artifacts.sha256(snapshotPath);
    references=referenceSnapshot(root,cases);
    report.ReferenceFiles=references;
    csr.validation.Artifacts.writeJson(fullfile(directory,'benchmark_plan.json'),plan);
    copyfile(fullfile(root,'scenarios','benchmarks','catalog.json'),fullfile(directory,'benchmark_catalog.json'));
    writeReport();
    if options.RunTests || options.IncludeNative
        report.RegressionStatus='running'; writeReport();
        regression=run_tranche6_validation(fullfile(directory,'regression'), ...
            struct('RunTests',options.RunTests,'IncludeNative',options.IncludeNative));
        diary(fullfile(directory,'validation.log'));
        report=attachRegression(report,regression,directory);
        if ~strcmp(regression.Status,'completed') || (options.RunTests && ~report.TestsPassed)
            error('csr:benchmark:Regression','Requested portable regression did not pass.');
        end
        writeReport();
    end
    for k=1:numel(cases)
        item=cases(k);
        fprintf('Benchmark %d/%d: %s (%g simulated seconds).\n', ...
            k,numel(cases),item.CaseId,item.DurationSeconds);
        result=csr.runScenario(item.Config);
        caseDirectory=fullfile(directory,'benchmarks',item.CaseId);
        rawDirectory=fullfile(caseDirectory,'raw');
        [row,~]=csr.validation.exportResearchCase(result,rawDirectory,root,snapshot, ...
            fullfile(root,item.ScenarioFile));
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
        aggregateFile=fullfile(analysisDirectory,'aggregates.csv');
        writetable(series,aggregateFile);
        provenance.output=struct('path','analysis/aggregates.csv', ...
            'sha256',csr.validation.Artifacts.sha256(aggregateFile));
        csr.validation.Artifacts.writeJson(fullfile(analysisDirectory,'aggregate_provenance.json'),provenance);
        files=csr.validation.Artifacts.fileInventory(caseDirectory);
        local=endsWith({files.path},'.mat');
        manifest=struct('schema','csr-matlab-benchmark-case-v1','status','completed', ...
            'case_id',item.CaseId,'scenario',item.Scenario,'scenario_sha256',item.ScenarioSHA256, ...
            'profile_id',item.ProfileId,'source_kind',item.SourceKind, ...
            'ns3_source_commit',report.SourceCommit,'matlab_version',version, ...
            'matlab_release',version('-release'),'runtime',report.Runtime, ...
            'duration_s',item.DurationSeconds,'seed',item.Seed, ...
            'bucket_width_s',item.BucketWidthSeconds,'opnet_available',item.OpnetAvailable, ...
            'reference_directory',item.ReferenceDirectory,'source_files',snapshot, ...
            'source_snapshot_sha256',report.SourceSnapshotSHA256, ...
            'structural_checks_passed',true,'numerical_parity_established',false, ...
            'admission_trace_omitted_records',result.Statistics.OmittedApplicationAdmissionRecords, ...
            'admission_counts_complete',true,'files',files(~local),'local_files',files(local));
        manifestPath=fullfile(caseDirectory,'benchmark_manifest.json');
        csr.validation.Artifacts.writeJson(manifestPath,manifest);
        row.CaseId=item.CaseId; row.SourceKind=item.SourceKind;
        row.Attempts=sum(result.ApplicationAdmissionStatistics.Attempts);
        row.AdmissionBlocked=row.Attempts-row.Generated;
        row.OmittedApplicationAdmissionRecords=result.Statistics.OmittedApplicationAdmissionRecords;
        summaryRows{end+1,1}=row; %#ok<AGROW>
        writetable(struct2table(vertcat(summaryRows{:}),'AsArray',true), ...
            fullfile(directory,'benchmark_summary.csv'));
        report.Cases(end+1,1)=struct('CaseId',item.CaseId, ...
            'Directory',['benchmarks/' item.CaseId], ...
            'ManifestSHA256',csr.validation.Artifacts.sha256(manifestPath));
        report.CompletedCaseCount=numel(report.Cases);
        writeReport();
        clear result;
    end
    report.SourceFilesFinal=csr.validation.Artifacts.sourceSnapshot(root);
    report.ReferenceFilesFinal=referenceSnapshot(root,cases);
    if ~isequal(snapshot,report.SourceFilesFinal) || ~isequal(references,report.ReferenceFilesFinal)
        error('csr:benchmark:InputChanged','Candidate or reference artifacts changed during execution.');
    end
    report.SourceFilesStableDuringRun=true; report.ReferenceFilesStableDuringRun=true;
    report.Status='completed'; report.CompletedUTC=csr.validation.Artifacts.utcNow();
    diary('off'); finishEvidence();
    fprintf('Tranche 7 completed: %d/%d tests, %d/%d benchmark cases.\n', ...
        report.PassedTests,report.TestCount,report.CompletedCaseCount,report.PlannedCaseCount);
    fprintf('Upload %s for benchmark comparison.\n',fullfile(directory,report.EvidenceArchive));
catch failure
    report.Status='failed'; report.CompletedUTC=csr.validation.Artifacts.utcNow();
    report.Failure=struct('Identifier',failure.identifier,'Message',failure.message);
    try
        listing=dir(fullfile(directory,'regression','run_*','validation_metadata.json'));
        if numel(listing)==1
            partial=jsondecode(fileread(fullfile(listing.folder,listing.name)));
            report=attachRegression(report,partial,directory);
        end
    catch evidenceFailure
        report.RegressionEvidenceFailure=struct('Identifier',evidenceFailure.identifier,'Message',evidenceFailure.message);
    end
    diary('off');
    try
        finishEvidence();
    catch archiveFailure
        report.EvidencePackagingFailure=struct('Identifier',archiveFailure.identifier,'Message',archiveFailure.message);
        writeReport();
    end
    fprintf(2,'Tranche 7 failed; partial evidence remains at %s.\n',directory);
    rethrow(failure);
end

    function writeReport()
        csr.validation.Artifacts.writeJson(fullfile(directory,'validation_metadata.json'),report);
    end

    function finishEvidence()
        inventory=csr.validation.Artifacts.fileInventory(directory, ...
            {'validation_metadata.json',report.EvidenceArchive});
        local=endsWith({inventory.path},'.mat') | endsWith({inventory.path},'.zip');
        report.LocalArtifacts=inventory(local); report.Artifacts=inventory(~local);
        writeReport();
        paths=[{report.Artifacts.path},{'validation_metadata.json'}];
        zip(fullfile(directory,report.EvidenceArchive),paths,directory);
    end
end

function options=validatedOptions(given)
options=struct('RunTests',true,'IncludeNative',false,'Cases',{{}});
if ~isstruct(given) || ~isscalar(given)
    error('csr:benchmark:Options','Options must be a scalar struct.');
end
for field=fieldnames(given)'
    if ~isfield(options,field{1}), error('csr:benchmark:Options','Unknown option %s.',field{1}); end
    options.(field{1})=given.(field{1});
end
validateattributes(options.RunTests,{'logical'},{'scalar'});
validateattributes(options.IncludeNative,{'logical'},{'scalar'});
if ischar(options.Cases), options.Cases={options.Cases}; end
if isstring(options.Cases), options.Cases=cellstr(options.Cases); end
end

function report=attachRegression(report,nested,directory)
if ~strcmp(nested.Schema,'csr-matlab-tranche-6-validation-v1') || ...
        ~strcmp(nested.SourceCommit,report.SourceCommit)
    error('csr:benchmark:Regression','Unexpected nested regression identity.');
end
path=csr.validation.Artifacts.canonicalPath(nested.EvidenceDirectory);
prefix=[directory filesep];
if ~startsWith(path,prefix), error('csr:benchmark:Path','Regression evidence is outside the run.'); end
report.RegressionEvidenceDirectory=strrep(path(numel(prefix)+1:end),filesep,'/');
report.RegressionMetadataSHA256=csr.validation.Artifacts.sha256(fullfile(path,'validation_metadata.json'));
report.RegressionStatus=nested.Status;
for field={'TestsExecuted','TestsPassed','TestCount','PassedTests','FailedTests','IncompleteTests','NativeExecuted'}
    if isfield(nested,field{1}), report.(field{1})=nested.(field{1}); end
end
end

function files=referenceSnapshot(root,cases)
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

function checkedReferenceFile(directory,entry)
path=csr.validation.Artifacts.canonicalPath(fullfile(directory,entry.path));
if ~startsWith(path,[directory filesep]) || ~isfile(path) || ...
        ~strcmp(csr.validation.Artifacts.sha256(path),entry.sha256)
    error('csr:benchmark:Reference','Reference provenance artifact is missing or changed.');
end
if isfield(entry,'bytes')
    details=dir(path);
    if details.bytes~=entry.bytes, error('csr:benchmark:Reference','Reference artifact size changed.'); end
end
end
