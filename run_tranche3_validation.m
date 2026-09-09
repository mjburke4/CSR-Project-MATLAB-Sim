function run_tranche3_validation(outputDirectory)
%RUN_TRANCHE3_VALIDATION Portable regressions and autonomous network evidence.
% Execute on MATLAB R2025a/R2026a. This entry point records the actual release;
% repository linting and source-side ns-3 workflows are separate evidence.
root = fileparts(mfilename('fullpath'));
addpath(root);
if nargin == 0, outputDirectory = fullfile(root,'results','tranche3_validation'); end
if ~exist(outputDirectory,'dir'), mkdir(outputDirectory); end
metadata = initialMetadata();
diary(fullfile(outputDirectory,'validation.log'));
cleanup = onCleanup(@() diary('off')); %#ok<NASGU>
regressionStarted = false;
previousTestHash = '';
try
metadata.MatlabGit = gitFacts(root);
metadata.MatlabSourceFiles = sourceFiles(root);
metadata.CandidateManifest = candidateManifest(root);
previousTestFile = fullfile(outputDirectory,'regression','tests','test_results.csv');
if isfile(previousTestFile), previousTestHash = sha256File(previousTestFile); end
metadata.Status = 'running';
writeMetadata(outputDirectory,metadata);
% This retains the prior portable suite and all nine Tranche 2 scenarios.
% run_validation discovers the new network tests alongside the 145 previous
% tests; assertSuccess stops this run if any regression fails or is incomplete.
regressionStarted = true;
run_tranche2_validation(fullfile(outputDirectory,'regression'));
% run_validation keeps its own detailed test diary. Resume this run's diary
% after that nested entry point closes its log.
diary(fullfile(outputDirectory,'validation.log'));
names = {'autonomous','no_route_custody','control_loss','route_recovery', ...
    'gateway','leaf_no_transit','high_rate_500','high_rate_1000'};
template = struct('Scenario','','Generated',0,'Received',0,'Dropped',0,'Pending',0, ...
    'ApplicationBytesReceived',0,'PhysicalTransmissions',0,'PhysicalAttempts',0, ...
    'PhysicalReceived',0,'PhysicalDropped',0,'PhysicalPending',0, ...
    'DataTransmissions',0,'ControlTransmissions',0,'Retransmissions',0, ...
    'AcksReceived',0,'DacksReceived',0,'FaultDrops',0,'RelayAccepted',0, ...
    'QueueDrops',0,'QueueAdmissionRejections',0,'HopFailures',0, ...
    'UnconfirmedHopTransfers',0,'MaxNetworkQueueDepth',0, ...
    'HopPendingData',0,'ResendQueueDepth',0,'DackHoldCount',0, ...
    'ControlPending',0,'ControlPendingTargets',0,'ControlRetransmissions',0, ...
    'NwkPendingCustody',0,'WaitingForRoute',0,'WaitingForHop',0, ...
    'PendingControlMessages',0,'ControlQueueRejections',0,'RouteChanges',0,'NeighborActivations',0, ...
    'NeighborDeactivations',0,'ControlResidualRetries',0,'DiscoveryStarts',0, ...
    'DiscoveryCompletions',0,'SelectedRoutes',0,'ActiveNeighbors',0, ...
    'RuntimeSeconds',0,'MATLABVersion','','MATLABRelease','');
rows = repmat(template,numel(names),1);
for k = 1:numel(names)
    result = csr.runScenario(csr.scenario.routedNetwork(names{k}));
    csr.analysis.exportResults(result,fullfile(outputDirectory,names{k}));
    row = template;
    row.Scenario = names{k};
    fields = fieldnames(result.Statistics);
    for index = 1:numel(fields)
        field = fields{index};
        if isfield(row,field), row.(field) = result.Statistics.(field); end
    end
    row.HopPendingData = sum(result.NodeHopStatistics.PendingData);
    for field = {'ResendQueueDepth','DackHoldCount','ControlPending', ...
            'ControlPendingTargets','ControlRetransmissions'}
        row.(field{1}) = sum(result.NodeHopStatistics.(field{1}));
    end
    row.NwkPendingCustody = sum(result.NodeNwkStatistics.PendingCustody);
    for field = {'WaitingForRoute','WaitingForHop','PendingControlMessages', ...
            'ControlQueueRejections','RouteChanges','NeighborActivations','NeighborDeactivations', ...
            'ControlResidualRetries','DiscoveryStarts','DiscoveryCompletions'}
        row.(field{1}) = sum(result.NodeNwkStatistics.(field{1}));
    end
    row.SelectedRoutes = height(result.Routes);
    row.ActiveNeighbors = sum(result.Neighbors.Active & ~result.Neighbors.Stale);
    row.RuntimeSeconds = result.Metadata.RuntimeSeconds;
    row.MATLABVersion = result.Metadata.Version;
    row.MATLABRelease = result.Metadata.Release;
    rows(k) = row;
    if row.ControlQueueRejections ~= 0
        error('csr:validation:ControlQueueRejection', ...
            'Scenario %s rejected %d controls/backlog transactions.', ...
            names{k},row.ControlQueueRejections);
    end
end
summary = struct2table(rows,'AsArray',true);
writetable(summary,fullfile(outputDirectory,'scenario_summary.csv'));
metadata = testCounts(metadata,outputDirectory);
metadata.Scenarios = names;
if ~isequal(metadata.MatlabSourceFiles,sourceFiles(root))
    error('csr:validation:SourceChanged','MATLAB source files changed during validation.');
end
if ~isequal(metadata.CandidateManifest,candidateManifest(root))
    error('csr:validation:CandidateChanged','Candidate manifest changed during validation.');
end
metadata.SourceFilesStableDuringRun = true;
metadata.Status = 'completed';
metadata.CompletedUTC = utcNow();
writeMetadata(outputDirectory,metadata);
disp(summary);
fprintf('Portable Tranche 3 validation completed on MATLAB %s (%s): %d/%d tests passed.\n', ...
    version,version('-release'),metadata.PassedTests,metadata.TestCount);
catch failure
    diary(fullfile(outputDirectory,'validation.log'));
    metadata.Status = 'failed';
    metadata.CompletedUTC = utcNow();
    metadata.Failure = struct('Identifier',failure.identifier,'Message',failure.message);
    if regressionStarted
        metadata = testCounts(metadata,outputDirectory,previousTestHash);
    end
    fprintf(2,'Tranche 3 validation failed: %s (%s)\n',failure.message,failure.identifier);
    writeMetadata(outputDirectory,metadata);
    rethrow(failure);
end
end

function metadata = initialMetadata()
metadata = csr.sim.capabilities();
metadata.StartedUTC = utcNow();
metadata.Status = 'initializing';
metadata.SourceCommit = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b';
metadata.ReferenceSourceRepository = 'mjburke4/CSR-Project-NS3-part2';
metadata.MatlabRepository = 'mjburke4/CSR-Project-MATLAB-Sim';
metadata.Tranche = 3;
metadata.Backend = 'portable';
metadata.MATLABExecuted = true;
metadata.SourceFilesStableDuringRun = false;
metadata.SourceHashMethod = 'SHA-256 of raw file bytes using the standard MATLAB JVM';
metadata.TestCount = 0;
metadata.PassedTests = 0;
metadata.FailedTests = 0;
metadata.IncompleteTests = 0;
metadata.TestResultsPresent = false;
metadata.EvidenceBoundary = ['Portable MATLAB execution with controlled line closure, ' ...
    'behavioral admission and selected receive erasures; separate native adapter and ' ...
    'cross-simulator differential gates remain.'];
metadata.RecoveryControlBoundary = ['Freshness monitoring continues at the finite stop time; ' ...
    'DATA custody must drain while bounded health-control owners may remain.'];
end

function metadata = testCounts(metadata,outputDirectory,previousHash)
file = fullfile(outputDirectory,'regression','tests','test_results.csv');
if ~isfile(file), return; end
hash = sha256File(file);
if nargin > 2 && strcmp(hash,previousHash)
    % A failure before run_validation writes its CSV must not reuse counts
    % from an older execution in the same results directory.
    metadata.PriorTestResultsUnchanged = true;
    return
end
tests = readtable(file);
metadata.TestResultsPresent = true;
metadata.TestResultsSHA256 = hash;
metadata.TestCount = height(tests);
metadata.PassedTests = sum(tests.Passed);
metadata.FailedTests = sum(tests.Failed);
metadata.IncompleteTests = sum(tests.Incomplete);
end

function writeMetadata(outputDirectory,metadata)
fid = fopen(fullfile(outputDirectory,'validation_metadata.json'),'w');
if fid < 0, error('csr:validation:Open','Cannot open validation_metadata.json.'); end
fileCleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(metadata,'PrettyPrint',true));
end

function files = sourceFiles(root)
listed = dir(fullfile(root,'**','*.m'));
files = repmat(struct('Path','','SHA256',''),numel(listed),1);
for k = 1:numel(listed)
    path = fullfile(listed(k).folder,listed(k).name);
    files(k).Path = strrep(path(numel(root)+2:end),filesep,'/');
    files(k).SHA256 = sha256File(path);
end
[~,order] = sort({files.Path});
files = files(order);
end

function candidate = candidateManifest(root)
candidate = struct('Present',false,'Path','evidence/tranche-3-candidate.json', ...
    'SHA256','','DeclaredBranch','','DeclaredReferenceSourceCommit','');
path = fullfile(root,'evidence','tranche-3-candidate.json');
if ~isfile(path), return; end
candidate.Present = true;
candidate.SHA256 = sha256File(path);
content = jsondecode(fileread(path));
if isfield(content,'branch'), candidate.DeclaredBranch = content.branch; end
if isfield(content,'ns3_source_commit')
    candidate.DeclaredReferenceSourceCommit = content.ns3_source_commit;
end
end

function digest = sha256File(path)
if ~usejava('jvm')
    error('csr:validation:JVMRequired', ...
        'Source hashing requires the standard MATLAB JVM; restart MATLAB without -nojvm.');
end
fid = fopen(path,'rb');
if fid < 0, error('csr:validation:SourceOpen','Cannot read source file: %s',path); end
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
bytes = fread(fid,Inf,'*uint8');
hasher = javaMethod('getInstance','java.security.MessageDigest','SHA-256');
% typecast preserves byte values above 127; int8(bytes) would saturate them.
hasher.update(typecast(bytes,'int8'));
raw = typecast(hasher.digest(),'uint8');
digest = lower(reshape(dec2hex(raw,2).',1,[]));
end

function facts = gitFacts(root)
facts = struct('Available',false,'Branch','','HeadCommit','', ...
    'Scope','HEAD metadata only; raw MATLAB source hashes identify the files used.');
directory = fullfile(root,'.git');
headFile = fullfile(directory,'HEAD');
if ~isfolder(directory) || ~isfile(headFile), return; end
head = strtrim(fileread(headFile));
facts.Available = true;
if startsWith(head,'ref: ')
    reference = head(6:end);
    if startsWith(reference,'refs/heads/'), facts.Branch = reference(12:end);
    else, facts.Branch = reference; end
    refFile = fullfile(directory,strrep(reference,'/',filesep));
    if isfile(refFile)
        facts.HeadCommit = strtrim(fileread(refFile));
    elseif isfile(fullfile(directory,'packed-refs'))
        pattern = ['(?m)^([0-9a-f]{40}) ' regexptranslate('escape',reference) '$'];
        match = regexp(fileread(fullfile(directory,'packed-refs')),pattern,'tokens','once');
        if ~isempty(match), facts.HeadCommit = match{1}; end
    end
else
    facts.HeadCommit = head;
end
end

function value = utcNow()
value = char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss''Z'''));
end
