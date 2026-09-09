function report = run_tranche5_validation(outputRoot,options)
%RUN_TRANCHE5_VALIDATION Multi-seed load/recovery experiments and diagnostics.
% Portable R2025a/R2026a. Defaults to the full Tranche 4 regression followed
% by 18 sweep cases. IncludeLongRun=true explicitly adds 6000-second cases.
% Options: RunTests, IncludeNative, Seeds, Experiments, IncludeLongRun,
% LoadMultipliers and FreshnessTimeoutSeconds. See docs/tranche-5-validation.md.
root = fileparts(mfilename('fullpath')); addpath(root);
if nargin < 1 || isempty(outputRoot), outputRoot = fullfile(root,'results','tranche5_validation'); end
if nargin < 2, options = struct(); end
[options,cases,plan] = validatedOptions(options);
outputRoot = csr.validation.Artifacts.canonicalPath(outputRoot);
stamp = char(datetime('now','TimeZone','UTC','Format','yyyyMMdd_HHmmss_SSS'));
[~,token] = fileparts(tempname);
directory = fullfile(outputRoot,['run_' stamp '_' token]);
[ok,message] = mkdir(directory);
if ~ok, error('csr:validation:Output','Cannot create result directory: %s.',message); end
diary(fullfile(directory,'validation.log'));
diaryCleanup = onCleanup(@() diary('off')); %#ok<NASGU>
regressionRoot = fullfile(directory,'regression');
report = struct('Schema','csr-matlab-tranche-5-validation-v1','Status','running', ...
    'Tranche',5,'StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'Options',options,'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'MatlabBaseCommit','7edaab558f4f00290d11e0681d883364141d547c', ...
    'TestsRequested',options.RunTests,'TestsExecuted',false,'TestsPassed',false, ...
    'TestCount',0,'PassedTests',0,'FailedTests',0,'IncompleteTests',0, ...
    'RegressionStatus','not_run','RegressionEvidenceDirectory','', ...
    'NativeRequested',options.IncludeNative,'NativeAttempted',false, ...
    'NativeExecuted',false,'NativeStatus','not_run', ...
    'SourceFilesStableDuringRun',false,'CrossSimulatorComparisonExecuted',false, ...
    'NumericalParityEstablished',false,'SweepPlan','sweep_plan.json', ...
    'PlannedCaseCount',numel(cases),'CompletedCaseCount',0, ...
    'Cases',repmat(struct('CaseId','','Name','','Experiment','','Parameter','','Value',0,'Seed',0, ...
        'Directory','','DiagnosticsDirectory','','ManifestSHA256',''),0,1), ...
    'EvidenceBoundary',['Completed means requested execution and structural accounting checks finished. ' ...
        'Delivery loss, pending ownership, control-retry exhaustion and recovery latency are measured ' ...
        'outcomes; this run does not establish numerical or full protocol parity.'], ...
    'ArchivePolicy','CSV, JSON and closed logs; MAT objects and nested ZIPs stay on the execution machine.', ...
    'InventoryExcludedPaths',{{'validation_metadata.json'}});
summaryRows = cell(0,1);
performanceRows = cell(0,1);
try
    snapshot = csr.validation.Artifacts.sourceSnapshot(root);
    report.SourceFiles = snapshot;
    csr.validation.Artifacts.writeJson(fullfile(directory,'sweep_plan.json'),plan);
    catalog = rmfield(cases,'Config');
    writetable(struct2table(catalog,'AsArray',true),fullfile(directory,'sweep_cases.csv'));
    writeReport();
    fprintf('Tranche 5: %d planned sweep cases, %g total simulated seconds.\n', ...
        plan.CaseCount,plan.TotalSimulatedSeconds);
    if options.RunTests || options.IncludeNative
        report.RegressionStatus = 'running';
        writeReport();
        regressionOptions = struct('RunTests',options.RunTests,'IncludeNative',options.IncludeNative);
        regression = run_tranche4_validation(regressionRoot,regressionOptions);
        diary(fullfile(directory,'validation.log'));
        report = updateRegression(report,regression,directory);
        if ~strcmp(regression.Status,'completed')
            error('csr:validation:Regression','The requested Tranche 4 regression did not complete.');
        end
        if options.RunTests && ~report.TestsPassed
            error('csr:validation:Regression','Requested regression tests did not all pass.');
        end
        writeReport();
    end
    for k = 1:numel(cases)
        item = cases(k);
        fprintf('Sweep %d/%d: %s (%g simulated seconds).\n', ...
            k,numel(cases),item.CaseId,item.Config.DurationSeconds);
        result = csr.runScenario(item.Config);
        caseDirectory = fullfile(directory,'sweep',item.CaseId);
        [row,~] = csr.validation.exportResearchCase(result,caseDirectory,root,snapshot);
        [performance,applications] = csr.analysis.performanceSummary(result);
        % Diagnostics are siblings of the immutable exportResearchCase output;
        % adding them cannot invalidate that case's original file inventory.
        diagnosticDirectory = fullfile(directory,'diagnostics',item.CaseId);
        [ok,message] = mkdir(diagnosticDirectory);
        if ~ok, error('csr:validation:Output','Cannot create diagnostics: %s.',message); end
        performance = addCaseIdentity(performance,item);
        writetable(struct2table(performance,'AsArray',true), ...
            fullfile(diagnosticDirectory,'performance_summary.csv'));
        writetable(applications,fullfile(diagnosticDirectory,'applications.csv'));
        summaryRows{end+1,1} = addCaseIdentity(row,item); %#ok<AGROW>
        performanceRows{end+1,1} = performance; %#ok<AGROW>
        writetable(struct2table(vertcat(summaryRows{:}),'AsArray',true), ...
            fullfile(directory,'scenario_summary.csv'));
        writetable(struct2table(vertcat(performanceRows{:}),'AsArray',true), ...
            fullfile(directory,'performance_summary.csv'));
        report.Cases(end+1,1) = struct('CaseId',item.CaseId,'Name',item.CaseId,'Experiment',item.Experiment, ...
            'Parameter',item.Parameter,'Value',item.Value,'Seed',item.Seed, ...
            'Directory',relativePath(caseDirectory,directory), ...
            'DiagnosticsDirectory',relativePath(diagnosticDirectory,directory), ...
            'ManifestSHA256',csr.validation.Artifacts.sha256(fullfile(caseDirectory,'case_manifest.json')));
        report.CompletedCaseCount = numel(report.Cases);
        writeReport();
        clear result;
    end
    report.SourceFilesFinal = csr.validation.Artifacts.sourceSnapshot(root);
    if ~isequal(snapshot,report.SourceFilesFinal)
        error('csr:validation:SourceChanged','Source files or candidate changed during validation.');
    end
    report.SourceFilesStableDuringRun = true;
    report.Status = 'completed';
    report.CompletedUTC = csr.validation.Artifacts.utcNow();
    report.EvidenceArchive = 'tranche5_evidence.zip';
    % Close the diary before hashing it. Every archived file except this
    % self-describing metadata document is then covered by an exact hash.
    diary('off');
    writeReport();
    packageEvidence(directory,report);
    fprintf('Tranche 5 structural execution completed on MATLAB %s: %d/%d cases.\n', ...
        version('-release'),report.CompletedCaseCount,report.PlannedCaseCount);
    fprintf('Upload %s for review.\n',fullfile(directory,report.EvidenceArchive));
    fprintf('Measured losses, retry failures and finite-stop pending work are retained in the diagnostics.\n');
catch failure
    report.Status = 'failed';
    report.CompletedUTC = csr.validation.Artifacts.utcNow();
    report.Failure = exceptionRecord(failure);
    if strcmp(report.RegressionStatus,'running')
        report.RegressionStatus = 'failed';
        try
            regression = readPartialRegression(regressionRoot);
            if ~isempty(regression), report = updateRegression(report,regression,directory); end
            if ~strcmp(report.RegressionStatus,'completed'), report.RegressionStatus = 'failed'; end
        catch countFailure
            report.RegressionEvidenceFailure = exceptionRecord(countFailure);
        end
    end
    report.EvidenceArchive = 'tranche5_evidence.zip';
    try
        diary('off');
    catch diaryFailure
        report.DiaryFailure = exceptionRecord(diaryFailure);
    end
    try
        writeReport();
    catch reportFailure
        % A secondary inventory/reporting failure must not hide the original
        % MATLAB test or simulation exception.
        report.EvidenceWriteFailure = exceptionRecord(reportFailure);
        for field = {'Artifacts','LocalArtifacts'}
            if isfield(report,field{1}), report = rmfield(report,field{1}); end
        end
        try
            csr.validation.Artifacts.writeJson(fullfile(directory,'validation_metadata.json'),report);
        catch metadataFailure
            fprintf(2,'Failure metadata could not be written: %s\n',metadataFailure.message);
        end
    end
    try
        packageEvidence(directory,report);
    catch archiveFailure
        fprintf(2,'Evidence ZIP could not be created: %s\n',archiveFailure.message);
    end
    fprintf(2,'Tranche 5 failed; partial evidence remains in %s.\n',directory);
    rethrow(failure);
end

    function writeReport()
        if ~strcmp(report.Status,'running')
            inventory = csr.validation.Artifacts.fileInventory(directory, ...
                {'validation_metadata.json','tranche5_evidence.zip'});
            exported = archiveSelection({inventory.path});
            report.Artifacts = inventory(exported);
            report.LocalArtifacts = inventory(endsWith({inventory.path},'.mat'));
        end
        csr.validation.Artifacts.writeJson(fullfile(directory,'validation_metadata.json'),report);
    end
end

function [options,cases,plan] = validatedOptions(given)
if ~isstruct(given) || ~isscalar(given)
    error('csr:validation:Options','Options must be a scalar struct.');
end
runTests = true; includeNative = false;
if isfield(given,'RunTests'), runTests = given.RunTests; given = rmfield(given,'RunTests'); end
if isfield(given,'IncludeNative'), includeNative = given.IncludeNative; given = rmfield(given,'IncludeNative'); end
validateattributes(runTests,{'logical'},{'scalar'});
validateattributes(includeNative,{'logical'},{'scalar'});
[cases,plan] = csr.scenario.researchSweep(given);
options = plan.Options;
options.RunTests = runTests;
options.IncludeNative = includeNative;
end

function row = addCaseIdentity(row,item)
row.CaseId = item.CaseId;
row.Experiment = item.Experiment;
row.Parameter = item.Parameter;
row.Value = item.Value;
end

function report = updateRegression(report,regression,directory)
if ~strcmp(regression.Schema,'csr-matlab-tranche-4-validation-v1')
    error('csr:validation:Regression','Unexpected nested regression metadata schema.');
end
regressionDirectory = csr.validation.Artifacts.canonicalPath(regression.EvidenceDirectory);
report.RegressionEvidenceDirectory = relativePath(regressionDirectory,directory);
report.RegressionStatus = regression.Status;
for field = {'NativeAttempted','NativeExecuted','NativeStatus'}
    if isfield(regression,field{1}), report.(field{1}) = regression.(field{1}); end
end
% Resolve the actual returned run directory. No assumed nested run name or
% fixed regression/tests depth is used for test evidence.
listing = dir(fullfile(regressionDirectory,'**','test_results.csv'));
if isempty(listing), return; end
if numel(listing) ~= 1
    error('csr:validation:Regression','Expected exactly one portable test-results CSV in the fresh regression run.');
end
path = fullfile(listing.folder,listing.name);
tests = readtable(path);
if ~all(ismember({'Name','Passed','Failed','Incomplete'},tests.Properties.VariableNames))
    error('csr:validation:Regression','Portable test evidence is missing required columns.');
end
passed = flagColumn(tests.Passed); failed = flagColumn(tests.Failed);
incomplete = flagColumn(tests.Incomplete);
if any(passed & (failed | incomplete)) || any(~(passed | failed | incomplete)) || ...
        numel(unique(tests.Name)) ~= height(tests)
    error('csr:validation:Regression','Portable test evidence has inconsistent outcomes or duplicate names.');
end
report.TestsExecuted = true;
report.TestCount = height(tests);
report.PassedTests = sum(passed);
report.FailedTests = sum(failed);
report.IncompleteTests = sum(incomplete);
report.TestsPassed = height(tests)>0 && all(passed) && ~any(failed | incomplete);
report.TestResultsFile = relativePath(path,directory);
report.TestResultsSHA256 = csr.validation.Artifacts.sha256(path);
end

function values = flagColumn(values)
if ~(isnumeric(values) || islogical(values)) || ~isvector(values) || ...
        any(~isfinite(values) | ~ismember(values,[0 1]))
    error('csr:validation:Regression','Test outcome columns must contain binary flags.');
end
values = logical(values);
end

function regression = readPartialRegression(regressionRoot)
regression = [];
listing = dir(fullfile(regressionRoot,'run_*','validation_metadata.json'));
if isempty(listing), return; end
if numel(listing) ~= 1
    error('csr:validation:Regression','Fresh regression root contains ambiguous run metadata.');
end
regression = jsondecode(fileread(fullfile(listing.folder,listing.name)));
end

function value = relativePath(path,directory)
path = csr.validation.Artifacts.canonicalPath(path);
directory = csr.validation.Artifacts.canonicalPath(directory);
prefix = [directory filesep];
if ~startsWith(path,prefix)
    error('csr:validation:Path','Evidence path is outside this validation run.');
end
value = strrep(path(numel(prefix)+1:end),filesep,'/');
end

function value = exceptionRecord(failure)
value = struct('Identifier',failure.identifier,'Message',failure.message);
end

function selected = archiveSelection(paths)
selected = false(size(paths));
for k = 1:numel(paths)
    [~,~,extension] = fileparts(paths{k});
    selected(k) = any(strcmp(extension,{'.csv','.json','.log'}));
end
end

function packageEvidence(directory,report)
listing = dir(fullfile(directory,'**','*'));
listing = listing(~[listing.isdir]);
paths = cell(numel(listing),1);
for k = 1:numel(listing)
    path = fullfile(listing(k).folder,listing(k).name);
    paths{k} = strrep(path(numel(directory)+2:end),filesep,'/');
end
paths = sort(paths(archiveSelection(paths)));
if isfield(report,'Artifacts')
    expected = sort([reshape({report.Artifacts.path},[],1); {'validation_metadata.json'}]);
    if ~isequal(paths,expected)
        error('csr:validation:ArchiveInventory','Archive membership differs from the completed artifact inventory.');
    end
end
zip(fullfile(directory,'tranche5_evidence.zip'),paths,directory);
end
