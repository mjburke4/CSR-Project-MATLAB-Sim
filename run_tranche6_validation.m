function report = run_tranche6_validation(outputRoot,options)
%RUN_TRANCHE6_VALIDATION Freshness/recovery candidate gate on portable MATLAB.
% Runs the complete portable tests and the unchanged 18 Tranche 5 load and
% recovery cases using THIS candidate. It does not re-execute the old code.
% Upload the printed tranche6_evidence.zip for comparison with accepted T5
% and the pinned ns-3 outage observations. Options are the T5 runner options.
root = fileparts(mfilename('fullpath')); addpath(root);
if nargin < 1 || isempty(outputRoot)
    outputRoot = fullfile(root,'results','tranche6_validation');
end
if nargin < 2, options = struct(); end
outputRoot = csr.validation.Artifacts.canonicalPath(outputRoot);
stamp = char(datetime('now','TimeZone','UTC','Format','yyyyMMdd_HHmmss_SSS'));
[~,token] = fileparts(tempname);
directory = fullfile(outputRoot,['run_' stamp '_' token]);
[ok,message] = mkdir(directory);
if ~ok, error('csr:validation:Output','Cannot create result directory: %s.',message); end
nestedRoot = fullfile(directory,'regression');
report = struct('Schema','csr-matlab-tranche-6-validation-v1','Tranche',6, ...
    'Status','running','StartedUTC',csr.validation.Artifacts.utcNow(), ...
    'EvidenceDirectory',directory,'MATLABExecuted',true,'Runtime',csr.sim.capabilities(), ...
    'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'MatlabBaseCommit','243ed8610df807e47d3b0be36d4ce2eae0527898', ...
    'AcceptedTranche5CodeCommit','536b288d765a7b18007ff7898eaf3f2e173d9e58', ...
    'Options',options,'SourceFilesStableDuringRun',false, ...
    'RegressionEvidenceDirectory','','RegressionMetadataSHA256','', ...
    'TestsExecuted',false,'TestsPassed',false,'TestCount',0,'PassedTests',0, ...
    'FailedTests',0,'IncompleteTests',0,'CompletedCaseCount',0,'PlannedCaseCount',0, ...
    'CrossSimulatorComparisonExecuted',false,'NumericalParityEstablished',false, ...
    'EvidenceArchive','tranche6_evidence.zip', ...
    'EvidenceBoundary',['Nested T5-format metadata describes the retained regression harness ' ...
        'executed with Tranche 6 source. Its historical base field is not this candidate identity. ' ...
        'Completion requires structural accounting; delivery improvement and comparison with ' ...
        'archived T5/ns-3 evidence require separate review.'], ...
    'ArchivePolicy','CSV, JSON and closed logs; MAT objects and nested ZIPs stay on the execution machine.', ...
    'InventoryExcludedPaths',{{'validation_metadata.json'}});
snapshot = csr.validation.Artifacts.sourceSnapshot(root);
report.SourceFiles = snapshot;
csr.validation.Artifacts.writeJson(fullfile(directory,'validation_metadata.json'),report);
try
    fprintf('Tranche 6: running the portable regression and unchanged load/recovery sweeps.\n');
    regression = run_tranche5_validation(nestedRoot,options);
    report = attachRegression(report,regression,directory);
    if ~strcmp(regression.Status,'completed')
        error('csr:validation:Regression','The requested regression did not complete.');
    end
    report.SourceFilesFinal = csr.validation.Artifacts.sourceSnapshot(root);
    if ~isequal(snapshot,report.SourceFilesFinal)
        error('csr:validation:SourceChanged','Candidate changed during Tranche 6 validation.');
    end
    report.SourceFilesStableDuringRun = true;
    report.Status = 'completed';
    report.CompletedUTC = csr.validation.Artifacts.utcNow();
    report = finishEvidence(report,directory);
    fprintf('Tranche 6 structural execution completed: %d/%d tests, %d/%d sweep cases.\n', ...
        report.PassedTests,report.TestCount,report.CompletedCaseCount,report.PlannedCaseCount);
    fprintf('Upload %s for acceptance and recovery comparison.\n', ...
        fullfile(directory,report.EvidenceArchive));
catch failure
    report.Status = 'failed'; report.CompletedUTC = csr.validation.Artifacts.utcNow();
    report.Failure = struct('Identifier',failure.identifier,'Message',failure.message);
    try
        listing = dir(fullfile(nestedRoot,'run_*','validation_metadata.json'));
        if numel(listing)==1
            regression = jsondecode(fileread(fullfile(listing.folder,listing.name)));
            report = attachRegression(report,regression,directory);
        end
    catch evidenceFailure
        report.RegressionEvidenceFailure = struct('Identifier',evidenceFailure.identifier, ...
            'Message',evidenceFailure.message);
    end
    try
        report = finishEvidence(report,directory);
    catch archiveFailure
        fprintf(2,'Tranche 6 evidence packaging failed: %s\n',archiveFailure.message);
        report.EvidencePackagingFailure = struct('Identifier',archiveFailure.identifier, ...
            'Message',archiveFailure.message);
        try
            csr.validation.Artifacts.writeJson(fullfile(directory,'validation_metadata.json'),report);
        catch writeFailure
            fprintf(2,'Failure metadata could not be written: %s\n',writeFailure.message);
        end
    end
    fprintf(2,'Tranche 6 failed; partial evidence remains in %s.\n',directory);
    rethrow(failure);
end
end

function report = attachRegression(report,regression,directory)
if ~strcmp(regression.Schema,'csr-matlab-tranche-5-validation-v1')
    error('csr:validation:Regression','Unexpected nested regression schema.');
end
path = csr.validation.Artifacts.canonicalPath(regression.EvidenceDirectory);
prefix = [directory filesep];
if ~startsWith(path,prefix)
    error('csr:validation:Path','Nested evidence is outside the Tranche 6 directory.');
end
report.RegressionEvidenceDirectory = strrep(path(numel(prefix)+1:end),filesep,'/');
report.RegressionMetadataSHA256 = csr.validation.Artifacts.sha256( ...
    fullfile(path,'validation_metadata.json'));
for field = {'TestsExecuted','TestsPassed','TestCount','PassedTests','FailedTests', ...
        'IncompleteTests','CompletedCaseCount','PlannedCaseCount','NativeRequested', ...
        'NativeAttempted','NativeExecuted','NativeStatus','Options'}
    if isfield(regression,field{1}), report.(field{1}) = regression.(field{1}); end
end
report.RegressionStatus = regression.Status;
end

function report = finishEvidence(report,directory)
inventory = csr.validation.Artifacts.fileInventory(directory, ...
    {'validation_metadata.json','tranche6_evidence.zip'});
selected = false(numel(inventory),1);
for k = 1:numel(inventory)
    [~,~,extension] = fileparts(inventory(k).path);
    selected(k) = any(strcmp(extension,{'.csv','.json','.log'}));
end
report.Artifacts = inventory(selected);
report.LocalArtifacts = inventory(endsWith({inventory.path},'.mat'));
csr.validation.Artifacts.writeJson(fullfile(directory,'validation_metadata.json'),report);
paths = sort([reshape({report.Artifacts.path},[],1); {'validation_metadata.json'}]);
zip(fullfile(directory,report.EvidenceArchive),paths,directory);
end
