function report = run_6000_batch(outputDirectory)
%RUN_6000_BATCH Run current-candidate 6,000-second seeds 131 and 132.
% Set Current Folder to this extracted csr6000 folder, then run:
%   report = run_6000_batch;
% Completed, sealed cases are reused. Interrupted cases restart in a new
% attempt folder. The returned ZIP excludes local results.mat files.
root = canonical(fileparts(mfilename('fullpath')));
if nargin < 1 || isempty(outputDirectory)
    outputDirectory = fullfile(root,'out_6000');
end
outputDirectory = canonical(char(outputDirectory));
assert(~strcmp(outputDirectory,root) && ~startsWith(root,[outputDirectory filesep]), ...
    'csr6000:OutputPath','The output folder cannot be the kit folder or its parent.');
for protected={'model','inputs','reference','private'}
    folder=fullfile(root,protected{1});
    assert(~strcmp(outputDirectory,folder) && ~startsWith(outputDirectory,[folder filesep]), ...
        'csr6000:OutputPath','Choose an output folder separate from the kit inputs and code.');
end
if ~isfolder(outputDirectory), mkdirChecked(outputDirectory); end
% An operating-system file lock releases automatically if MATLAB exits.
% A remaining batch.lock file is harmless; its existence alone is no lock.
lockFile = javaObject('java.io.RandomAccessFile', ...
    fullfile(outputDirectory,'batch.lock'),'rw');
channel = lockFile.getChannel();
try
    activeLock = channel.tryLock();
catch caught
    channel.close(); lockFile.close();
    error('csr6000:ActiveRun','Cannot acquire the batch lock. Another run may be active: %s',caught.message);
end
if isempty(activeLock)
    channel.close(); lockFile.close();
    error('csr6000:ActiveRun','Another MATLAB process is already using %s.',outputDirectory);
end
releaseLock = onCleanup(@()unlock(activeLock,channel,lockFile)); %#ok<NASGU>
oldPath = path; oldFolder = pwd;
restoreEnvironment = onCleanup(@()restore(oldPath,oldFolder)); %#ok<NASGU>
invocation = newDirectory(fullfile(outputDirectory,'invocations'), ...
    ['run_' datestr(now,'yyyymmdd_HHMMSS')]);
diary(fullfile(invocation,'console.log'));
closeDiary = onCleanup(@()diary('off')); %#ok<NASGU>
started = tic;
report = struct('schema','csr-current6000-owner-run-v1','completed',false, ...
    'completed_definition','Both requested simulations and their required exports completed; numerical gates are separate.', ...
    'numerical_parity_established',false,'target_percent',15, ...
    'started_utc',utcNow(),'finished_utc','','wall_seconds',0, ...
    'runtime',runtimeIdentity(),'output_directory',outputDirectory, ...
    'cases',struct([]),'archive','','archive_completed',false, ...
    'error_identifier','','error_message','');
fprintf('\nCSR current-candidate batch: seeds 131 and 132, 6,000 seconds each.\n');
fprintf('Earlier runs took about 1 h 47 min and 3 h 3 min; this batch may take several hours.\n');
fprintf('Runtime varies. Long quiet periods while MATLAB is working are expected.\n');
fprintf('Results are saved separately after each case. Output: %s\n',outputDirectory);
try
    model = fullfile(root,'model');
    rejectCachedOtherCsr(model);
    % Keep only MATLAB defaults and the packaged runner/model for this call.
    cd(root); restoredefaultpath; addpath(root,model,'-begin'); rehash;
    planPath = fullfile(root,'plan.json');
    plan = jsondecode(fileread(planPath));
    assert(strcmp(plan.schema,'csr-current6000-batch-plan-v1') && ...
        isequal(double(plan.seeds(:))',[131 132]) && plan.duration_s == 6000 && ...
        plan.comparison_tolerance_percent == 15, ...
        'csr6000:Plan','The packaged plan does not describe this two-case batch.');
    verifyPlan(root,model,plan);
    resolved=verifyEntryPoints(model);
    snapshot = csr.validation.Artifacts.sourceSnapshot(model);
    identity = struct('schema','csr-current6000-resume-identity-v1', ...
        'plan_sha256',hashFile(planPath),'runtime',runtimeIdentity());
    provenance = struct('schema','csr-current6000-provenance-v1', ...
        'identity',identity,'plan',plan,'model_source_snapshot',snapshot, ...
        'runner_path',fullfile(root,'run_6000_batch.m'), ...
        'model_path',model,'resolved_entry_points',resolved, ...
        'simulation_observer_used',false, ...
        'transport_override_used',false,'progress_events_added',false, ...
        'drain_interval_added',false);
    writeJson(fullfile(invocation,'provenance.json'),provenance);
    fprintf('Checking the analysis/export helper and bundled native references (no simulation).\n');
    selfcheck = batch_analysis_selfcheck(fullfile(root,'reference'));
    writeJson(fullfile(invocation,'analysis_selfcheck.json'),selfcheck);
    % Import and validate both small configurations before allocating a model.
    configurations = cell(1,2);
    for index = 1:2
        seed = plan.seeds(index);
        input = fullfile(root,'inputs',sprintf('s%d.csv',seed));
        config = csr.scenario.importNs3(input,struct( ...
            'HistoricalBenchmark',true,'FlowLimit',0,'Backend','portable'));
        assert(config.Seed == seed && config.DurationSeconds == 6000, ...
            'csr6000:Scenario','The seed or duration differs from the canonical scenario.');
        assert(strcmp(config.Hop.DataQueuedRetryPolicy,'actual-tx'), ...
            'csr6000:RetryPolicy','Expected the unchanged actual-tx retry policy.');
        config.Trace.Enabled = true;
        config.Trace.MaxRecords = 1500000;
        config.Trace.MaxPhyRecords = 1500000;
        config.Trace.MaxApplicationAdmissionRecords = 100000;
        config.MaxEvents = 12000000;
        configurations{index} = csr.scenario.validate(config);
    end
    writeJson(fullfile(invocation,'validated_configurations.json'), ...
        struct('s131',configurations{1},'s132',configurations{2}));
    for index = 1:2
        seed = plan.seeds(index);
        caseIdentity = identity; caseIdentity.seed = seed;
        caseRoot = fullfile(outputDirectory,sprintf('s%d',seed));
        if ~isfolder(caseRoot), mkdirChecked(caseRoot); end
        [reused,item] = completedCase(caseRoot,caseIdentity);
        if reused
            fprintf('\nSeed %d: reusing completed, hash-verified export %s\n',seed,item.attempt_directory);
        else
            attempt = newAttempt(caseRoot);
            % Function scope releases the large result before the next seed.
            item = runCase(root,model,plan,snapshot,configurations{index}, ...
                attempt,caseIdentity);
        end
        if isempty(report.cases), report.cases=item; else, report.cases(end+1)=item; end %#ok<AGROW>
        report.wall_seconds=toc(started);
        writeJson(fullfile(invocation,'batch_status.json'),report);
    end
    verifyPlan(root,model,plan);
    assert(strcmp(identity.plan_sha256,hashFile(planPath)), ...
        'csr6000:PlanChanged','The plan changed during this batch.');
    csr.validation.Artifacts.checkSnapshot(model,snapshot);
    report.completed = numel(report.cases)==2 && all([report.cases.completed]);
catch caught
    report.error_identifier=caught.identifier; report.error_message=caught.message;
    report.error_stack=caught.stack;
    fprintf('\nBatch could not finish: %s\n',caught.message);
end
report.finished_utc=utcNow(); report.wall_seconds=toc(started);
archiveBase=[outputDirectory '_' datestr(now,'yyyymmdd_HHMMSS')];
report.archive=uniqueZipPath(archiveBase);
writeJson(fullfile(invocation,'batch_status.json'),report);
fprintf('\nSimulation/export batch completed=%d. Creating the return ZIP now.\n',report.completed);
fprintf('Large trace files may make ZIP creation take several minutes.\n');
diary('off');
try
    names=returnFileNames(outputDirectory);
    assert(~isempty(names),'csr6000:EmptyArchive','No completed or partial evidence is available.');
    zip(report.archive,names,outputDirectory);
    report.archive_completed=true;
    % This receipt is outside the ZIP. Inside batch_status, false means the
    % archive had not yet been created, not that simulations must be rerun.
    writeJson(fullfile(invocation,'archive_receipt.json'), ...
        struct('archive',report.archive,'sha256',hashFile(report.archive), ...
        'bytes',fileBytes(report.archive),'finished_utc',utcNow()));
    fprintf('\nReturn this ZIP, even if a case or comparison failed:\n%s\n',report.archive);
catch caught
    report.archive_error_identifier=caught.identifier;
    report.archive_error_message=caught.message;
    writeJson(fullfile(invocation,'archive_error.json'), ...
        struct('identifier',caught.identifier,'message',caught.message));
    fprintf('\nZIP creation failed: %s\n',caught.message);
    fprintf('The saved cases are intact. Run run_6000_batch again to reuse sealed cases and retry the ZIP.\n');
end
fprintf('Cases completed=%d; archive created=%d; elapsed %.1f minutes.\n', ...
    report.completed,report.archive_completed,toc(started)/60);
end

function item=runCase(root,model,plan,snapshot,config,attempt,identity)
seed=config.Seed; timer=tic;
item=struct('seed',seed,'completed',false,'resumed',false, ...
    'attempt_directory',attempt,'wall_seconds',0,'final_simulation_time_s',NaN, ...
    'comparison',struct(), ...
    'error_identifier','','error_message','');
writeJson(fullfile(attempt,'start.json'),struct('identity',identity, ...
    'started_utc',utcNow(),'config',config,'status','running'));
fprintf('\nSeed %d: starting 0–6,000 s. No intermediate progress messages are expected.\n',seed);
fprintf('Attempt folder: %s\n',attempt);
try
    verifyPlan(root,model,plan);
    csr.validation.Artifacts.checkSnapshot(model,snapshot);
    assert(strcmp(identity.plan_sha256,hashFile(fullfile(root,'plan.json'))), ...
        'csr6000:PlanChanged','Plan changed before this case.');
    simulation=csr.sim.NetworkSimulation(config);
    result=simulation.run();
    finalSimulationTime=simulation.Scheduler.Now;
    item.final_simulation_time_s=finalSimulationTime;
    clear simulation
    assert(finalSimulationTime==config.DurationSeconds,'csr6000:IncompleteRun', ...
        'Simulation did not reach the requested 6,000-second cutoff.');
    fprintf('Seed %d: simulation returned; saving its local result before analysis.\n',seed);
    checkpoint=fullfile(attempt,'result_checkpoint.mat');
    save(checkpoint,'result','-v7.3');
    fprintf('Seed %d: exporting complete traces and application accounting.\n',seed);
    verifyPlan(root,model,plan);
    assert(strcmp(identity.plan_sha256,hashFile(fullfile(root,'plan.json'))), ...
        'csr6000:PlanChanged','Plan changed during the case.');
    raw=fullfile(attempt,'raw');
    csr.validation.exportResearchCase(result,raw,model,snapshot, ...
        fullfile(root,'inputs',sprintf('s%d.csv',seed)));
    % The canonical export now retains its own MAT result. Remove only the
    % temporary duplicate checkpoint created by this invocation.
    if isfile(fullfile(raw,'results.mat'))
        retained=whos('-file',fullfile(raw,'results.mat'));
        if any(strcmp({retained.name},'result')), delete(checkpoint); end
    end
    [performance,applications]=csr.analysis.performanceSummary(result);
    analysis=fullfile(attempt,'analysis'); mkdirChecked(analysis);
    writetable(applications,fullfile(analysis,'applications.csv'));
    writetable(struct2table(performance,'AsArray',true), ...
        fullfile(analysis,'performance_summary.csv'));
    item.comparison=batch_case_analysis(result,applications,attempt, ...
        fullfile(root,'reference',sprintf('s%d',seed)),15);
    clear result applications
    verifyPlan(root,model,plan);
    csr.validation.Artifacts.checkSnapshot(model,snapshot);
    assert(strcmp(identity.plan_sha256,hashFile(fullfile(root,'plan.json'))), ...
        'csr6000:PlanChanged','Plan changed during export.');
    item.completed=true; item.wall_seconds=toc(timer);
    writeJson(fullfile(attempt,'case_summary.json'),item);
    seal=struct('schema','csr-current6000-completion-v1','identity',identity, ...
        'completed',true,'completed_utc',utcNow(), ...
        'files',evidenceInventory(attempt),'case_summary',item, ...
        'local_mat_files_excluded',true);
    % Only this final receipt permits a future invocation to reuse the case.
    writeJson(fullfile(attempt,'completion.json'),seal);
    fprintf('Seed %d: completed and sealed (%.1f minutes). Numerical gates are in its analysis.\n',seed,toc(timer)/60);
catch caught
    item.completed=false; item.wall_seconds=toc(timer);
    item.error_identifier=caught.identifier; item.error_message=caught.message;
    failure=item; failure.error_stack=caught.stack;
    % A completed simulation must survive a reporting/structural failure.
    % Preserve any computed result and export partial raw evidence if the
    % canonical export did not finish. It remains explicitly unaccepted.
    if exist('result','var') && ~isfile(fullfile(attempt,'raw','case_manifest.json'))
        try
            if ~isfile(fullfile(attempt,'result_checkpoint.mat'))
                save(fullfile(attempt,'result_checkpoint.mat'),'result','-v7.3');
            end
            csr.analysis.exportResults(result,fullfile(attempt,'partial_raw'));
            failure.partial_raw_exported=true;
        catch exportError
            failure.partial_export_error=exportError.message;
        end
    end
    writeJson(fullfile(attempt,'case_summary.json'),failure);
    fprintf('Seed %d failed: %s\nIts partial files are preserved; the other seed will still be attempted.\n',seed,caught.message);
end
end

function [found,item]=completedCase(caseRoot,identity)
found=false; item=struct();
listing=dir(fullfile(caseRoot,'attempt_*')); listing=listing([listing.isdir]);
[~,order]=sort({listing.name}); listing=listing(order);
for index=numel(listing):-1:1
    folder=fullfile(caseRoot,listing(index).name); receipt=fullfile(folder,'completion.json');
    if ~isfile(receipt), continue; end
    try
        seal=jsondecode(fileread(receipt));
        if ~strcmp(seal.schema,'csr-current6000-completion-v1') || ...
                ~seal.completed || ~isequaln(seal.identity,identity)
            continue
        end
        actual=evidenceInventory(folder);
        if ~sameInventory(seal.files,actual), continue; end
        item=seal.case_summary; item.resumed=true; item.attempt_directory=folder;
        assert(item.completed && item.seed==identity.seed,'csr6000:Receipt','Invalid completed case identity.');
        found=true; return
    catch caught
        fprintf('Preserving an unusable completion receipt in %s: %s\n',folder,caught.message);
    end
end
end

function verifyPlan(root,model,plan)
required={'source_manifest','input_manifest','runner_manifest'};
assert(all(isfield(plan,required)),'csr6000:Plan','The plan is missing a file manifest.');
verifyManifest(model,plan.source_manifest); verifyManifest(root,plan.input_manifest);
verifyManifest(root,plan.runner_manifest);
actual=allFiles(model); expected=sort({plan.source_manifest.path}');
assert(isequal(sort(actual),expected),'csr6000:ModelInventory', ...
    'The model files differ from this kit. Extract a fresh copy into a new folder.');
end

function verifyManifest(base,manifest)
assert(isstruct(manifest) && ~isempty(manifest),'csr6000:Manifest','Empty file manifest.');
for index=1:numel(manifest)
    relative=char(manifest(index).path);
    assert(~isempty(relative) && isempty(regexp(relative,'(^/|^[A-Za-z]:|(^|[\\/])\.\.([\\/]|$))','once')), ...
        'csr6000:ManifestPath','Invalid relative path in manifest.');
    file=fullfile(base,strrep(relative,'/',filesep));
    assert(isfile(file) && strcmp(hashFile(file),manifest(index).sha256), ...
        'csr6000:FileChanged','Missing or changed kit file: %s. Extract a fresh kit.',relative);
end
end

function resolved=verifyEntryPoints(model)
names={'csr.runScenario','csr.sim.NetworkSimulation','csr.sim.EventScheduler', ...
    'csr.nwk.Layer','csr.hop.Layer','csr.mac.Layer','csr.phy.SignalEngine', ...
    'csr.scenario.importNs3','csr.scenario.validate', ...
    'csr.validation.exportResearchCase','csr.validation.Artifacts', ...
    'csr.analysis.performanceSummary'};
paths={'+csr/runScenario.m','+csr/+sim/NetworkSimulation.m','+csr/+sim/EventScheduler.m', ...
    '+csr/+nwk/Layer.m','+csr/+hop/Layer.m','+csr/+mac/Layer.m', ...
    '+csr/+phy/SignalEngine.m','+csr/+scenario/importNs3.m', ...
    '+csr/+scenario/validate.m','+csr/+validation/exportResearchCase.m', ...
    '+csr/+validation/Artifacts.m','+csr/+analysis/performanceSummary.m'};
resolved=repmat(struct('name','','path',''),numel(names),1);
for index=1:numel(names)
    found=which(names{index});
    assert(~isempty(found) && strcmp(canonical(found), ...
        canonical(fullfile(model,strrep(paths{index},'/',filesep)))), ...
        'csr6000:ShadowedModel','Another CSR copy is active. Restart MATLAB and run this extracted folder.');
    resolved(index)=struct('name',names{index},'path',canonical(found));
end
end

function rejectCachedOtherCsr(model)
loaded=inmem('-completenames');
for index=1:numel(loaded)
    file=char(loaded{index});
    if contains(strrep(file,'\','/'),'/+csr/')
        file=canonical(file);
        assert(startsWith(file,[model filesep]),'csr6000:CachedModel', ...
            'MATLAB has already loaded another CSR copy. Restart MATLAB, set Current Folder to this kit, and run run_6000_batch.');
    end
end
end

function files=evidenceInventory(folder)
names=returnFileNames(folder); names=names(~strcmp(names,'completion.json'));
files=repmat(struct('path','','sha256','','bytes',0),numel(names),1);
for index=1:numel(names)
    file=fullfile(folder,strrep(names{index},'/',filesep));
    files(index)=struct('path',names{index},'sha256',hashFile(file),'bytes',fileBytes(file));
end
end

function equal=sameInventory(left,right)
equal=numel(left)==numel(right); if ~equal, return; end
for index=1:numel(left)
    if ~strcmp(left(index).path,right(index).path) || ...
            ~strcmp(left(index).sha256,right(index).sha256) || left(index).bytes~=right(index).bytes
        equal=false; return
    end
end
end

function names=returnFileNames(folder)
names=allFiles(folder);
keep=endsWith(lower(string(names)),{'.csv','.json','.log'});
names=names(keep);
end

function names=allFiles(folder)
listing=dir(fullfile(folder,'**','*')); listing=listing(~[listing.isdir]);
names=cell(numel(listing),1);
for index=1:numel(listing)
    file=fullfile(listing(index).folder,listing(index).name);
    names{index}=strrep(file(numel(folder)+2:end),'\','/');
end
names=sort(names);
end

function path=newAttempt(folder)
number=1;
while isfolder(fullfile(folder,sprintf('attempt_%03d',number))) || ...
        isfile(fullfile(folder,sprintf('attempt_%03d',number)))
    number=number+1;
end
path=fullfile(folder,sprintf('attempt_%03d',number)); mkdirChecked(path);
end

function path=newDirectory(parent,stem)
if ~isfolder(parent), mkdirChecked(parent); end
path=fullfile(parent,stem); number=1;
while isfolder(path) || isfile(path)
    number=number+1; path=fullfile(parent,sprintf('%s_%02d',stem,number));
end
mkdirChecked(path);
end

function path=uniqueZipPath(stem)
path=[stem '.zip']; number=1;
while isfile(path) || isfolder(path)
    number=number+1; path=sprintf('%s_%02d.zip',stem,number);
end
end

function value=runtimeIdentity()
value=struct('version',version,'release',version('-release'),'computer',computer);
end

function value=utcNow()
value=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSS''Z'''));
end

function digest=hashFile(file)
fid=fopen(file,'rb'); assert(fid>=0,'csr6000:Read','Cannot read %s.',file);
closer=onCleanup(@()fclose(fid)); %#ok<NASGU>
hasher=javaMethod('getInstance','java.security.MessageDigest','SHA-256');
while true
    bytes=fread(fid,1048576,'*uint8'); if isempty(bytes), break; end
    hasher.update(typecast(bytes,'int8'));
end
digest=lower(reshape(dec2hex(typecast(hasher.digest(),'uint8'),2).',1,[]));
end

function value=fileBytes(file)
listing=dir(file); value=listing.bytes;
end

function writeJson(file,value)
fid=fopen(file,'w'); assert(fid>=0,'csr6000:Write','Cannot write %s.',file);
closer=onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
end

function value=canonical(value)
file=javaObject('java.io.File',value);
if ~file.isAbsolute(), file=javaObject('java.io.File',pwd,value); end
value=char(file.getCanonicalPath());
end

function mkdirChecked(folder)
[ok,message]=mkdir(folder); assert(ok,'csr6000:Directory','Cannot create %s: %s',folder,message);
end

function restore(oldPath,oldFolder)
path(oldPath); if isfolder(oldFolder), cd(oldFolder); end
end

function unlock(activeLock,channel,file)
try activeLock.release(); catch, end
try channel.close(); catch, end
try file.close(); catch, end
end
