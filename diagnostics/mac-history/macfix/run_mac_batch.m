function report = run_mac_batch(outputDir)
%RUN_MAC_BATCH Run independent MAC history and slot-selection comparisons.
% From this folder: report = run_mac_batch;
% Uses the bundled accepted core. No toolbox, Python, or ns-3 is required.
root = fileparts(mfilename('fullpath'));
if nargin < 1 || isempty(outputDir)
    outputDir = fullfile(root,['out_mac_' datestr(now,'yyyymmdd_HHMMSS')]);
    if isfolder(outputDir), outputDir = tempname(root); end
end
if ~isfolder(outputDir), mkdir(outputDir); end
oldPath = path; cleanup = onCleanup(@()path(oldPath)); %#ok<NASGU>
addpath(fullfile(root,'core'),fullfile(root,'matlab'), ...
    fullfile(root,'diagnostics','rules'),fullfile(root,'diagnostics','node4'),fullfile(root,'diagnostics','grouped'),'-begin');
report = struct('suite','common-input MAC batch','runtime',version, ...
    'completed',false,'pass',false,'network_parity_claim',false, ...
    'output_directory',outputDir,'tests',{{}},'wall_seconds',0);
timer = tic;
try
    expected = fullfile(root,'core','+csr','+mac','Layer.m');
    assert(strcmp(which('csr.mac.Layer'),expected), ...
        'mac_batch:ShadowedCore','Another CSR tree shadows the bundled core.');
    binding = verifyBinding(root);
catch caught
    binding = struct('pass',false,'message',caught.message,'error_identifier',caught.identifier);
end
writeJson(fullfile(outputDir,'runtime_binding.json'),binding);
if binding.pass
    tests = {@run_mac_history,@run_slot_vectors,@run_hop_window,@run_grouped_retry};
    names = {'history','slot_rules','hop_window','grouped_retry'};
    for k = 1:numel(tests)
        folder = fullfile(outputDir,names{k});
        if ~isfolder(folder), mkdir(folder); end
        fprintf('\nRunning %s (%d/%d)...\n',names{k},k,numel(tests));
        oneTimer = tic;
        try
            item = tests{k}(root,folder);
            assert(isstruct(item),'mac_batch:Report','Test returned no structured report.');
            if ~isfield(item,'completed'), item.completed = true; end
            if ~isfield(item,'pass'), item.pass = false; end
        catch caught
            item = struct('completed',false,'pass',false, ...
                'error_identifier',caught.identifier,'error_message',caught.message, ...
                'error_stack',caught.stack);
        end
        item.test = names{k}; item.wall_seconds = toc(oneTimer);
        report.tests{end+1} = item;
        writeJson(fullfile(folder,'batch_test_summary.json'),item);
        fprintf('%s: completed=%d, pass=%d (%.2f s)\n', ...
            names{k},item.completed,item.pass,item.wall_seconds);
        if isfield(item,'error_message'), fprintf('%s\n',item.error_message); end
        writeJson(fullfile(outputDir,'suite_summary.json'),report);
    end
    report.completed = all(cellfun(@(r)logical(r.completed),report.tests));
    report.pass = report.completed && all(cellfun(@(r)logical(r.pass),report.tests));
else
    report.error_identifier = 'mac_batch:Binding';
    report.error_message = binding.message;
end
report.wall_seconds = toc(timer);
report.archive = [outputDir '.zip'];
writeJson(fullfile(outputDir,'suite_summary.json'),report);
listing = dir(outputDir); names = {listing.name};
names = names(~ismember(names,{'.','..'}));
zip(report.archive,names,outputDir);
fprintf('\nMAC batch completed=%d; all comparisons pass=%d\n',report.completed,report.pass);
fprintf('Return this ZIP even if a comparison differs: %s\n',report.archive);
end

function binding = verifyBinding(root)
manifest = jsondecode(fileread(fullfile(root,'RUN_FILES.json')));
assert(strcmp(manifest.schema,'csr.mac-batch-run.v1'),'mac_batch:Binding','Unknown run manifest.');
binding = struct('pass',false,'message','','files',struct('path',{},'match',{},'actual_sha256',{}));
for k = 1:numel(manifest.files)
    entry = manifest.files(k); relative = char(entry.path);
    assert(~startsWith(relative,'/') && ~contains(relative,'..'), ...
        'mac_batch:Binding','Unsafe manifest path.');
    value = csr.validation.Artifacts.sha256(fullfile(root,relative));
    binding.files(end+1) = struct('path',relative,'match',strcmpi(value,entry.sha256),'actual_sha256',value);
end
binding.pass = ~isempty(binding.files) && all([binding.files.match]);
if binding.pass, binding.message = 'All issued source, input and reference hashes match.';
else, binding.message = 'File binding differs; see runtime_binding.json.'; end
end

function writeJson(file,value)
fid = fopen(file,'w');
if fid < 0, error('mac_batch:Write','Cannot write %s.',file); end
cleanup = onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
end
