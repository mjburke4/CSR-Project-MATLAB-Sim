function report = run_short_tests(outputDir)
%RUN_SHORT_TESTS Run the bundled short MATLAB checks and package the results.
% Set MATLAB's Current Folder to this extracted folder, then run:
%   report = run_short_tests;
% Return the out_short_*.zip path printed at the end, including on failure.
root=fileparts(mfilename('fullpath'));
candidateRoot=fullfile(root,'candidate');
nativeRoot=fullfile(root,'native');
if nargin<1 || isempty(outputDir)
    stem=fullfile(root,['out_short_' datestr(now,'yyyymmdd_HHMMSS')]);
    outputDir=stem;
    suffix=1;
    while isfolder(outputDir) || isfile(outputDir) || isfile([outputDir '.zip'])
        suffix=suffix+1;
        outputDir=sprintf('%s_%02d',stem,suffix);
    end
else
    outputDir=char(outputDir);
    if isempty(regexp(outputDir,'^([A-Za-z]:[\\/]|[\\/]{2}|/)','once'))
        outputDir=fullfile(pwd,outputDir);
    end
    assert(~isfolder(outputDir) && ~isfile(outputDir) && ~isfile([outputDir '.zip']), ...
        'short_tests:OutputExists','Choose a new output folder to preserve existing results.');
end
[created,message]=mkdir(outputDir);
assert(created,'short_tests:Output','Cannot create result folder: %s',message);
outputDir=char(java.io.File(outputDir).getCanonicalPath());
timer=tic;
oldPath=path;
restorePath=onCleanup(@()path(oldPath)); %#ok<NASGU>
report=struct('schema','csr-two-case-owner-run-v1', ...
    'runtime',version,'release',version('-release'),'computer',computer, ...
    'started_local',datestr(now,'yyyy-mm-ddTHH:MM:SS'), ...
    'completed',false,'full_network_parity_claim',false, ...
    'output_directory',outputDir,'archive',[outputDir '.zip'], ...
    'wall_seconds',0,'replay_summary',struct(), ...
    'error_identifier','','error_message','');
fprintf('\nRunning seed-131 discovery and seed-132 source-5 short checks.\n');
fprintf('Results: %s\n',outputDir);
try
    assert(isfolder(fullfile(candidateRoot,'+csr')), ...
        'short_tests:IncompleteKit', ...
        'The kit is missing candidate/+csr. Extract the complete short-test ZIP again.');
    required={fullfile(nativeRoot,'batch.json'), ...
        fullfile(nativeRoot,'seed131','phy_draws.csv'), ...
        fullfile(nativeRoot,'seed131','phy_draws.provenance.json'), ...
        fullfile(nativeRoot,'seed131','capture.jsonl'), ...
        fullfile(nativeRoot,'bound_node4','manifest.json')};
    for index=1:numel(required)
        assert(isfile(required{index}),'short_tests:IncompleteKit', ...
            ['The kit is missing a bundled native input: %s. ' ...
            'Return this result ZIP so the package can be corrected.'],required{index});
    end
    addpath(root,candidateRoot,'-begin');
    classNames={'csr.hop.Layer','csr.mac.Layer','csr.phy.SignalEngine'};
    classFiles={fullfile(candidateRoot,'+csr','+hop','Layer.m'), ...
        fullfile(candidateRoot,'+csr','+mac','Layer.m'), ...
        fullfile(candidateRoot,'+csr','+phy','SignalEngine.m')};
    for index=1:numel(classNames)
        actual=which(classNames{index});
        assert(strcmp(actual,classFiles{index}),'short_tests:ShadowedCandidate', ...
            'Another CSR copy is active. Restart MATLAB and run this folder again.');
    end
    provenance=struct('schema','csr-two-case-owner-provenance-v1', ...
        'candidate_sources',sourceInventory(candidateRoot), ...
        'kit_matlab_sources',sourceInventory(root), ...
        'native_batch_sha256',sha256(fullfile(nativeRoot,'batch.json')), ...
        'native_batch',jsondecode(fileread(fullfile(nativeRoot,'batch.json'))), ...
        'runner_sha256',sha256(fullfile(root,'run_short_tests.m')), ...
        'replay_wrapper_sha256',sha256(fullfile(root,'run_two_replays.m')));
    writeJson(fullfile(outputDir,'run_provenance.json'),provenance);
    report.replay_summary=run_two_replays(candidateRoot,root,nativeRoot, ...
        fullfile(outputDir,'replays'),fullfile(nativeRoot,'seed131','phy_draws.csv'), ...
        fullfile(nativeRoot,'bound_node4'));
    names={'discovery','node4_receiver','source5_capacity','source5_mac'};
    completed=false(1,numel(names));
    for index=1:numel(names)
        item=report.replay_summary.(names{index});
        completed(index)=logical(item.completed);
        fprintf('%s: completed=%d\n',names{index},completed(index));
        if isfield(item,'error_message') && ~isempty(item.error_message)
            fprintf('  %s\n',item.error_message);
        end
    end
    report.completed=all(completed);
    report.completed_definition=['All four replay procedures completed; ' ...
        'their separate comparison gates remain in replay_summary.'];
catch caught
    report.error_identifier=caught.identifier;
    report.error_message=caught.message;
    report.error_stack=caught.stack;
    fprintf('Short-test run could not complete: %s\n',caught.message);
end
report.wall_seconds=toc(timer);
writeJson(fullfile(outputDir,'suite_summary.json'),report);
listing=dir(outputDir);
names={listing.name};
names=names(~ismember(names,{'.','..'}));
zip(report.archive,names,outputDir);
fprintf('\nShort tests completed=%d (%.1f seconds).\n',report.completed,report.wall_seconds);
fprintf('Return this ZIP, even if a check fails:\n%s\n',report.archive);
end

function files=sourceInventory(folder)
listing=dir(fullfile(folder,'**','*.m'));
files=struct('path',{},'sha256',{});
for index=1:numel(listing)
    file=fullfile(listing(index).folder,listing(index).name);
    relative=strrep(file(numel(folder)+2:end),'\','/');
    files(end+1)=struct('path',relative,'sha256',sha256(file)); %#ok<AGROW>
end
end

function value=sha256(file)
fid=fopen(file,'rb');
assert(fid>=0,'short_tests:Read','Cannot read %s.',file);
closeFile=onCleanup(@()fclose(fid)); %#ok<NASGU>
bytes=fread(fid,Inf,'*uint8');
digest=javaMethod('getInstance','java.security.MessageDigest','SHA-256');
if ~isempty(bytes), digest.update(typecast(bytes,'int8')); end
value=lower(reshape(dec2hex(typecast(digest.digest(),'uint8'),2).',1,[]));
end

function writeJson(file,value)
fid=fopen(file,'w');
assert(fid>=0,'short_tests:Write','Cannot write %s.',file);
closeFile=onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
end
