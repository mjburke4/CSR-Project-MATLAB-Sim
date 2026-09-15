function report = run_tranche10_mesh(outputRoot)
%RUN_TRANCHE10_MESH Focused retry regressions and the unchanged failing mesh.
% This is diagnostic evidence, not the full Tranche 10 acceptance gate.
% Runs one 900-second mesh at seed 128 with the original 2e6 event cap.
root=fileparts(mfilename('fullpath')); addpath(root,'-begin');
if nargin<1 || isempty(outputRoot), outputRoot=fullfile(root,'results','m10'); end
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
stamp=char(datetime('now','TimeZone','UTC','Format','yyMMdd_HHmmss'));
[~,token]=fileparts(tempname); token=token(max(1,end-7):end);
directory=fullfile(outputRoot,['r' stamp '_' token]);
[ok,message]=mkdir(directory);
if ~ok, error('csr:diagnostic:Output','Cannot create output: %s.',message); end
diary(fullfile(directory,'run.log'));
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('Schema','csr-tranche10-mesh-diagnostic-v1','Status','running', ...
    'StartedUTC',csr.validation.Artifacts.utcNow(),'EvidenceDirectory',directory, ...
    'MATLABExecuted',true,'MATLABVersion',version,'MATLABRelease',version('-release'), ...
    'DiagnosticOnly',true,'FullAcceptanceGateExecuted',false, ...
    'NumericalParityEstablished',false,'CaseId','research_mesh_6_seed_128', ...
    'DurationSeconds',900,'Seed',128,'MaxEvents',2000000, ...
    'TestsExecuted',false,'TestsPassed',false,'MeshStarted',false,'MeshCompleted',false, ...
    'SourceFilesStableDuringRun',false,'EvidenceArchive','mesh.zip');
simulation=[]; originalFailure=[]; snapshot=[];
try
    % Detect a different CSR tree ahead of this package on the MATLAB path.
    for name={'csr.nwk.Neighbors','csr.sim.EventScheduler','csr.sim.NetworkSimulation'}
        resolved=csr.validation.Artifacts.canonicalPath(which(name{1}));
        % Class basenames are not package directories.
        parts=strsplit(name{1},'.'); relative='';
        for k=1:numel(parts)-1, relative=fullfile(relative,['+' parts{k}]); end
        expected=csr.validation.Artifacts.canonicalPath(fullfile(root,relative,[parts{end} '.m']));
        if ~strcmp(resolved,expected)
            error('csr:diagnostic:Path','A different CSR tree is loaded: %s.',resolved);
        end
    end
    snapshot=csr.validation.Artifacts.sourceSnapshot(root);
    csr.validation.Artifacts.writeJson(fullfile(directory,'source.json'),snapshot);
    report.SourceSnapshotSHA256=csr.validation.Artifacts.sha256(fullfile(directory,'source.json'));
    config=csr.scenario.researchNetwork('mesh_6',struct('Seed',128));
    if config.DurationSeconds~=900 || config.MaxEvents~=2000000 || ...
            config.Seed~=128 || ~strcmp(config.Backend,'portable')
        error('csr:diagnostic:Config','Expected the original portable mesh, duration, seed and event cap.');
    end
    csr.validation.Artifacts.writeJson(fullfile(directory,'config.json'),config);
    fprintf('Tranche 10 mesh check: testing neighbor retries and scheduler failure reporting.\n');
    results=runtests(fullfile(root,'tests','TestNeighbors.m'));
    schedulerResults=runtests(fullfile(root,'tests','TestEventScheduler.m'));
    results=[results(:); schedulerResults(:)];
    summary=table({results.Name}',[results.Passed]',[results.Failed]', ...
        [results.Incomplete]',[results.Duration]', ...
        'VariableNames',{'Name','Passed','Failed','Incomplete','DurationSeconds'});
    writetable(summary,fullfile(directory,'tests.csv'));
    report.TestsExecuted=true; report.TestCount=numel(results);
    report.PassedTests=sum([results.Passed]); report.FailedTests=sum([results.Failed]);
    report.IncompleteTests=sum([results.Incomplete]);
    report.TestsPassed=~isempty(results) && all([results.Passed]) && ...
        ~any([results.Failed]) && ~any([results.Incomplete]);
    assertSuccess(results);
    fprintf('Mesh 1/1: 6 nodes, 900 simulated seconds, seed 128, original event cap 2000000.\n');
    simulation=csr.sim.NetworkSimulation(config);
    report.MeshStarted=true;
    result=simulation.run();
    report.MeshCompleted=true;
    report.RuntimeSeconds=result.Metadata.RuntimeSeconds;
    report.Statistics=result.Statistics;
    csr.validation.Artifacts.writeJson(fullfile(directory,'state.json'),captureState(simulation));
    csr.validation.exportResearchCase(result,fullfile(directory,'raw'),root,snapshot);
    csr.validation.Artifacts.checkSnapshot(root,snapshot);
    report.SourceFilesStableDuringRun=true; report.Status='completed';
    fprintf('Mesh completed in %.1f wall seconds: %d admitted, %d delivered, %d dropped.\n', ...
        result.Metadata.RuntimeSeconds,result.Statistics.Generated, ...
        result.Statistics.Received,result.Statistics.Dropped);
catch failure
    originalFailure=failure; report.Status='failed';
    report.Failure=exceptionRecord(failure);
    fprintf(2,'Mesh check FAILED: %s\n',failure.message);
    if ~isempty(simulation)
        try
            state=captureState(simulation);
            csr.validation.Artifacts.writeJson(fullfile(directory,'state.json'),state);
            fprintf(2,'Stopped at %.17g s; next event %.17g s; %d pending events.\n', ...
                state.NowSeconds,state.NextEventSeconds,state.PendingEvents);
        catch captureFailure
            report.StateCaptureFailure=exceptionRecord(captureFailure);
        end
    end
    if ~isempty(snapshot)
        try
            csr.validation.Artifacts.checkSnapshot(root,snapshot);
            report.SourceFilesStableDuringRun=true;
        catch sourceFailure
            report.SourceCheckFailure=exceptionRecord(sourceFailure);
        end
    end
end
report.CompletedUTC=csr.validation.Artifacts.utcNow();
diary('off');
try
    files=csr.validation.Artifacts.fileInventory(directory);
    report.LocalFiles=files(endsWith({files.path},'.mat'));
    report.Files=files(~endsWith({files.path},'.mat'));
    csr.validation.Artifacts.writeJson(fullfile(directory,'report.json'),report);
    paths=[{report.Files.path},{'report.json'}];
    archive=fullfile(directory,report.EvidenceArchive);
    zip(archive,paths,directory);
    fprintf('Upload %s for review. This mesh check is diagnostic-only.\n',archive);
catch packagingFailure
    fprintf(2,'Could not package evidence; partial files remain in %s.\n',directory);
    if isempty(originalFailure), rethrow(packagingFailure); end
end
if ~isempty(originalFailure), rethrow(originalFailure); end
end

function state = captureState(simulation)
scheduler=simulation.Scheduler;
state=struct('NowSeconds',scheduler.Now,'NextEventSeconds',scheduler.nextTime(), ...
    'PendingEvents',scheduler.PendingCount,'MaxEvents',scheduler.MaxEvents, ...
    'Nodes',{{}},'MAC',{{}},'HOP',{{}},'NWK',{{}},'Routes',{{}},'Neighbors',{{}});
for k=1:numel(simulation.Nodes)
    node=simulation.Nodes{k};
    state.Nodes{k}=struct('Id',simulation.Config.Nodes(k).Id, ...
        'Generated',node.Generated,'Transmitted',node.Transmitted, ...
        'Received',node.Received,'Dropped',node.Dropped);
    state.MAC{k}=simulation.Macs{k}.snapshot();
    state.MAC{k}.NodeId=simulation.Macs{k}.NodeId;
    state.MAC{k}.PreparationActive=simulation.Macs{k}.PreparationActive;
    state.MAC{k}.HoldoffOver=simulation.Macs{k}.HoldoffOver;
    state.HOP{k}=simulation.Hops{k}.stats(); state.HOP{k}.NodeId=simulation.Hops{k}.NodeId;
    state.NWK{k}=simulation.Networks{k}.stats(); state.NWK{k}.NodeId=simulation.Networks{k}.NodeId;
    state.Routes{k}=simulation.Networks{k}.routesSnapshot();
    state.Neighbors{k}=simulation.Networks{k}.neighborsSnapshot();
end
end

function output = exceptionRecord(failure)
output=struct('Identifier',failure.identifier,'Message',failure.message,'Stack',failure.stack);
end
