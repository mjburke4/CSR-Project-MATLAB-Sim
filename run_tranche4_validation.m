function report = run_tranche4_validation(outputRoot,options)
%RUN_TRANCHE4_VALIDATION Research experiments and shared ns-3 input exports.
% R2025a/R2026a portable by default. Each execution gets a new directory.
% Options: RunTests=true, Seeds=128, IncludeLongRun=false, IncludeNative=false,
% ResearchScenarios={'two_node','line_4','hidden_node','mesh_6', ...
% 'route_recovery','leaf_no_transit'}, SharedScenarios={} (all catalog cases).
% ResearchScenarios={} explicitly skips research layouts. Shared inputs keep
% their catalog seed; Seeds applies only to research experiments.
root = fileparts(mfilename('fullpath')); addpath(root);
if nargin < 1 || isempty(outputRoot), outputRoot = fullfile(root,'results','tranche4_validation'); end
if nargin < 2, options = struct(); end
options = validatedOptions(options);
if isstring(outputRoot) && isscalar(outputRoot), outputRoot = char(outputRoot); end
if ~ischar(outputRoot) || ~isrow(outputRoot) || isempty(outputRoot)
    error('csr:validation:Output','Output root must be a path.');
end
outputFile = javaObject('java.io.File',outputRoot);
outputRoot = char(outputFile.getCanonicalPath());
stamp = char(datetime('now','TimeZone','UTC','Format','yyyyMMdd_HHmmss_SSS'));
[~,token] = fileparts(tempname);
directory = fullfile(outputRoot,['run_' stamp '_' token]);
[ok,message] = mkdir(directory);
if ~ok, error('csr:validation:Output','Cannot create result directory: %s.',message); end
diary(fullfile(directory,'validation.log'));
diaryCleanup = onCleanup(@() diary('off')); %#ok<NASGU>
report = struct('Schema','csr-matlab-tranche-4-validation-v1','Status','running', ...
    'Tranche',4,'StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'Options',options,'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'MatlabBaseCommit','c37a39e2d03d0f675271fb37ac2c4c0bcafd9f4b', ...
    'TestsRequested',options.RunTests,'TestsExecuted',false, ...
    'TestCount',0,'PassedTests',0,'FailedTests',0,'IncompleteTests',0, ...
    'NativeRequested',options.IncludeNative,'NativeAttempted',false, ...
    'NativeExecuted',false,'NativeStatus','not_run', ...
    'SourceFilesStableDuringRun',false,'CrossSimulatorComparisonExecuted',false, ...
    'NumericalParityEstablished',false,'Cases',repmat(struct('Kind','','Name','','Directory','','ManifestSHA256',''),0,1), ...
    'EvidenceBoundary',['Completed means requested execution and structural checks finished; ' ...
        'delivery, convergence and cross-simulator numerical differences remain measured outcomes.']);
rows = cell(0,1);
try
    snapshot = csr.validation.Artifacts.sourceSnapshot(root);
    report.SourceFiles = snapshot;
    writeReport();
    if options.RunTests
        run_tranche3_validation(fullfile(directory,'regression'));
        diary(fullfile(directory,'validation.log'));
        report = updateTestCounts(report,directory);
        writeReport();
    end
    catalogPath = fullfile(root,'scenarios','shared','catalog.json');
    catalog = jsondecode(fileread(catalogPath));
    if ~strcmp(catalog.schema,'csr-matlab-shared-scenario-catalog-v1')
        error('csr:validation:Catalog','Unsupported shared scenario catalog.');
    end
    entries = catalog.cases;
    names = {entries.name};
    if isempty(entries) || numel(unique(names)) ~= numel(names)
        error('csr:validation:Catalog','Shared catalog must have unique named cases.');
    end
    if ~isempty(options.SharedScenarios) && ~all(ismember(options.SharedScenarios,names))
        error('csr:validation:Catalog','Requested shared scenario is absent from the catalog.');
    end
    for k = 1:numel(entries)
        entry = entries(k);
        if ~isempty(options.SharedScenarios) && ~ismember(entry.name,options.SharedScenarios), continue; end
        if isempty(regexp(entry.name,'^[a-zA-Z0-9_-]+$','once')) || ...
                isempty(regexp(entry.path,'^[a-zA-Z0-9_-]+\.csv$','once'))
            error('csr:validation:Catalog','Shared names and paths must be simple CSV fixture names.');
        end
        input = fullfile(root,'scenarios','shared',entry.path);
        config = csr.scenario.importNs3(input,struct('FlowLimit',entry.flow_limit));
        caseDirectory = fullfile(directory,'shared',entry.name);
        fprintf('Shared scenario %s\n',entry.name);
        result = csr.runScenario(config);
        [row,~] = csr.validation.exportResearchCase(result,caseDirectory,root,snapshot,input);
        recordCase('shared',entry.name,caseDirectory,row);
    end
    researchNames = options.ResearchScenarios;
    if options.IncludeLongRun && ~ismember('long_run_6000',researchNames)
        researchNames{end+1} = 'long_run_6000';
    end
    for k = 1:numel(researchNames)
        for seed = reshape(options.Seeds,1,[])
            name = researchNames{k};
            config = csr.scenario.researchNetwork(name,struct('Seed',seed));
            caseName = sprintf('%s_seed_%u',name,seed);
            caseDirectory = fullfile(directory,'research',caseName);
            fprintf('Research scenario %s (%g simulated seconds)\n',caseName,config.DurationSeconds);
            result = csr.runScenario(config);
            [row,~] = csr.validation.exportResearchCase(result,caseDirectory,root,snapshot);
            recordCase('research',caseName,caseDirectory,row);
        end
    end
    if options.IncludeNative
        report.NativeAttempted = true;
        report.NativeStatus = 'running';
        validate_native(fullfile(directory,'native'));
        diary(fullfile(directory,'validation.log'));
        report.NativeExecuted = true;
        report.NativeStatus = 'passed';
    end
    csr.validation.Artifacts.checkSnapshot(root,snapshot);
    report.SourceFilesStableDuringRun = true;
    report.Status = 'completed';
    report.CompletedUTC = csr.validation.Artifacts.utcNow();
    report.EvidenceArchive = 'tranche4_evidence.zip';
    writeReport();
    diary('off');
    packageEvidence(directory);
    fprintf('Tranche 4 execution completed on MATLAB %s. Evidence: %s\n',version('-release'),directory);
    fprintf('Upload %s for review. MAT result objects remain in the case folders.\n', ...
        fullfile(directory,report.EvidenceArchive));
    fprintf('Compare shared exports with the archived ns-3 references using scripts/compare_matlab_ns3.py.\n');
catch failure
    diary(fullfile(directory,'validation.log'));
    report.Status = 'failed';
    report.CompletedUTC = csr.validation.Artifacts.utcNow();
    report.Failure = struct('Identifier',failure.identifier,'Message',failure.message);
    report = updateTestCounts(report,directory);
    if report.NativeAttempted && ~strcmp(report.NativeStatus,'passed')
        report.NativeStatus = 'failed';
        report.NativeExecuted = isfile(fullfile(directory,'native','native_test_results.csv'));
    end
    writeReport();
    diary('off');
    try
        packageEvidence(directory);
    catch archiveFailure
        fprintf(2,'Evidence ZIP could not be created: %s\n',archiveFailure.message);
    end
    fprintf(2,'Tranche 4 failed. Preserved partial evidence: %s\n',directory);
    rethrow(failure);
end

    function recordCase(kind,name,path,row)
        rows{end+1,1} = row;
        summary = struct2table(vertcat(rows{:}),'AsArray',true);
        writetable(summary,fullfile(directory,'scenario_summary.csv'));
        relative = strrep(path(numel(directory)+2:end),filesep,'/');
        report.Cases(end+1,1) = struct('Kind',kind,'Name',name,'Directory',relative, ...
            'ManifestSHA256',csr.validation.Artifacts.sha256(fullfile(path,'case_manifest.json')));
        writeReport();
    end

    function writeReport()
        % Hash completed artifacts, including nested regression CSVs, configs
        % and logs; do not hash a live diary whose final bytes can still grow.
        if ~strcmp(report.Status,'running')
            inventory = csr.validation.Artifacts.fileInventory(directory);
            paths = {inventory.path};
            inventory = inventory(~strcmp(paths,'validation_metadata.json') & ...
                ~strcmp(paths,'validation.log') & ~strcmp(paths,'tranche4_evidence.zip'));
            local = endsWith({inventory.path},'.mat');
            report.LocalArtifacts = inventory(local);
            report.Artifacts = inventory(~local);
        end
        csr.validation.Artifacts.writeJson(fullfile(directory,'validation_metadata.json'),report);
    end
end

function options = validatedOptions(given)
options = struct('RunTests',true,'Seeds',128,'IncludeLongRun',false,'IncludeNative',false, ...
    'ResearchScenarios',{{'two_node','line_4','hidden_node','mesh_6','route_recovery','leaf_no_transit'}}, ...
    'SharedScenarios',{{}});
if ~isstruct(given) || ~isscalar(given)
    error('csr:validation:Options','Options must be a scalar struct.');
end
for field = fieldnames(given)'
    if ~isfield(options,field{1}), error('csr:validation:Options','Unknown option %s.',field{1}); end
    options.(field{1}) = given.(field{1});
end
for field = {'RunTests','IncludeLongRun','IncludeNative'}
    validateattributes(options.(field{1}),{'logical'},{'scalar'});
end
validateattributes(options.Seeds,{'numeric'},{'vector','real','finite','integer','nonnegative','<=',2^32-1,'nonempty'});
options.Seeds = reshape(double(options.Seeds),1,[]);
if numel(unique(options.Seeds)) ~= numel(options.Seeds) || numel(options.Seeds)>20
    error('csr:validation:Seeds','Provide up to 20 distinct research seeds.');
end
research = {'two_node','line_4','hidden_node','mesh_6','route_recovery','leaf_no_transit', ...
    'high_rate_500','high_rate_1000','long_run_6000'};
for field = {'ResearchScenarios','SharedScenarios'}
    value = options.(field{1});
    if isstring(value), value = cellstr(value); end
    if ~iscell(value) || ~all(cellfun(@(x)ischar(x) && isrow(x) && ~isempty(x),value)) || ...
            numel(unique(value)) ~= numel(value)
        error('csr:validation:Options','Scenario selections must be distinct names.');
    end
    options.(field{1}) = reshape(value,1,[]);
end
if ~all(ismember(options.ResearchScenarios,research))
    error('csr:validation:Options','Unknown research scenario.');
end
if ismember('long_run_6000',options.ResearchScenarios) && ~options.IncludeLongRun
    error('csr:validation:LongRun','Set IncludeLongRun=true to request a 6000-second experiment.');
end
end

function report = updateTestCounts(report,directory)
path = fullfile(directory,'regression','regression','tests','test_results.csv');
if ~isfile(path), return; end
tests = readtable(path);
report.TestsExecuted = true;
report.TestCount = height(tests);
report.PassedTests = sum(tests.Passed);
report.FailedTests = sum(tests.Failed);
report.IncompleteTests = sum(tests.Incomplete);
report.TestResultsSHA256 = csr.validation.Artifacts.sha256(path);
end

function packageEvidence(directory)
listing = dir(fullfile(directory,'**','*'));
paths = cell(0,1);
for k = 1:numel(listing)
    if listing(k).isdir, continue; end
    [~,~,extension] = fileparts(listing(k).name);
    if ~any(strcmp(extension,{'.csv','.json','.log'})), continue; end
    path = fullfile(listing(k).folder,listing(k).name);
    paths{end+1,1} = path(numel(directory)+2:end); %#ok<AGROW>
end
zip(fullfile(directory,'tranche4_evidence.zip'),paths,directory);
end
