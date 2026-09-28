function report=run_source5_mac_replay(adapterRoot,captureDir,outputDir,candidateRoot)
%RUN_SOURCE5_MAC_REPLAY Node-5 conditional MAC replay from new native capture.
% Reuse the previously validated 0->665-s MAC replay adapter, bound to the
% current production MAC source. It consumes native queue/state inputs and ordered raw
% integer slot draws from 0, then compares node 5's TX and draw tape through
% 330 s. Fidelity is a mandatory independent native-prefix comparison.
if nargin<1 || isempty(adapterRoot)
    adapterRoot=fullfile(fileparts(mfilename('fullpath')),'mac_adapter');
end
if nargin<2 || isempty(captureDir)
    error('source5:CaptureDir','Supply the new native source-5 capture directory.');
end
if nargin<3 || isempty(outputDir)
    outputDir=fullfile(fileparts(mfilename('fullpath')),'out_mac');
end
if nargin<4 || isempty(candidateRoot)
    error('source5:CandidateRoot','Supply the unchanged grouped-routing candidate root.');
end
if ~isfolder(outputDir), mkdir(outputDir); end
report=struct('schema','source5-mac-conditional-v1','status','capture_pending', ...
    'completed',false,'pass',false,'network_parity_claim',false, ...
    'scope','Node-5 MAC scheduling given observed external queue, receiver and draw inputs', ...
    'error_identifier','','error_message','');
try
    runPath=fullfile(adapterRoot,'matlab','run_mac_history.m');
    adapter=fullfile(adapterRoot,'matlab','+mac_replay','MacLayer.m');
    schedulerPath=fullfile(adapterRoot,'matlab','+mac_replay','Scheduler.m');
    production=fullfile(candidateRoot,'+csr','+mac','Layer.m');
    bindingPath=fullfile(adapterRoot,'binding.json');
    assert(isfile(runPath) && isfile(adapter) && isfile(production), ...
        'source5:MacHarness','Accepted MAC replay implementation is missing.');
    assert(isfile(schedulerPath) && isfile(bindingPath), ...
        'source5:MacBinding','Bundled MAC replay binding is missing.');
    binding=jsondecode(fileread(bindingPath));
    assert(strcmp(sha256(production),binding.production_mac_sha256) && ...
        strcmp(sha256(runPath),binding.run_mac_history_sha256) && ...
        strcmp(sha256(adapter),binding.adapter_mac_layer_sha256) && ...
        strcmp(sha256(schedulerPath),binding.adapter_scheduler_sha256), ...
        'source5:MacSourceBinding','Replay adapter or candidate MAC source differs from accepted binding.');
    profilePath=locate(captureDir,'profile.json','inputs');
    fidelityPath=locate(captureDir,'fidelity.json','reference');
    profile=jsondecode(fileread(profilePath));
    fidelity=jsondecode(fileread(fidelityPath));
    assert(isequal(double(profile.nodes),5) && ...
        double(profile.replay_start_ns)==0 && ...
        double(profile.replay_stop_ns)==330e9 && ...
        double(profile.comparison_start_ns)==300e9 && ...
        double(profile.comparison_stop_ns)==330e9, ...
        'source5:MacProfile','MAC replay must warm from zero and select node 5, 300-330 s.');
    assert(logical(fidelity.all_passed) && ...
        logical(fidelity.source_capture.exact_prefix), ...
        'source5:MacNativeFidelity', ...
        'Native prefix fidelity must be independently established before MAC comparison.');
    for file={'inputs.csv','frames.csv','draws.csv','tx.csv','tx_frames.csv'}
        name=file{1}; path=locate(captureDir,name,'inputs');
        field=matlab.lang.makeValidName(name);
        assert(isfield(fidelity.input_sha256,field) && ...
            strcmp(sha256(path),fidelity.input_sha256.(field)), ...
            'source5:MacTapeBinding','Captured MAC tape changed since native fidelity gate: %s.',name);
    end
    for file={'tx.csv','draws.csv'}
        name=file{1}; path=locate(captureDir,name,'reference');
        field=matlab.lang.makeValidName(name);
        assert(isfield(fidelity.reference_sha256,field) && ...
            strcmp(sha256(path),fidelity.reference_sha256.(field)), ...
            'source5:MacReferenceBinding','Native MAC reference changed: %s.',name);
    end
    staging=fullfile(outputDir,'staging');
    in=fullfile(staging,'inputs'); ref=fullfile(staging,'reference');
    if ~isfolder(in), mkdir(in); end
    if ~isfolder(ref), mkdir(ref); end
    for file={'profile.json','inputs.csv','frames.csv','draws.csv'}
        source=locate(captureDir,file{1},'inputs');
        copyfile(source,fullfile(in,file{1}));
    end
    for file={'fidelity.json','tx.csv','draws.csv'}
        source=locate(captureDir,file{1},'reference');
        copyfile(source,fullfile(ref,file{1}));
    end
    % Aggregate children are bound by fidelity.input_sha256.tx_frames_csv;
    % the accepted MAC adapter compares TX timing/slots from tx.csv only.
    addpath(candidateRoot);
    addpath(fullfile(adapterRoot,'matlab'));
    result=run_mac_history(staging,fullfile(outputDir,'replayed'));
    assert(result.completed && result.behavioral_pass && ...
        numel(result.node_reports)==1 && result.node_reports{1}.node==5 && ...
        result.node_reports{1}.unused_draws==0 && ...
        result.node_reports{1}.raw_draw_pass && result.node_reports{1}.target_tx_pass, ...
        'source5:MacMismatch','Native input/slot/physical-TX comparison failed.');
    report.status='completed'; report.completed=true; report.pass=true;
    report.mac=result; report.inputs_root=staging;
catch caught
    report.status='failed'; report.error_identifier=caught.identifier;
    report.error_message=caught.message; report.error_stack=caught.stack;
end
writeJson(fullfile(outputDir,'report.json'),report);
end

function value=sha256(path)
fid=fopen(path,'rb'); assert(fid>=0,'source5:MacBinding','Cannot read %s.',path);
cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
bytes=fread(fid,Inf,'*uint8');
digest=javaMethod('getInstance','java.security.MessageDigest','SHA-256');
if ~isempty(bytes), digest.update(typecast(bytes,'int8')); end
value=lower(reshape(dec2hex(typecast(digest.digest(),'uint8'),2).',1,[]));
end

function path=locate(root,file,subdir)
path=fullfile(root,subdir,file);
if ~isfile(path), path=fullfile(root,file); end
assert(isfile(path),'source5:CaptureMissing','Required native capture file missing: %s.',file);
end
function writeJson(path,value)
fid=fopen(path,'w'); assert(fid>=0,'source5:Output','Cannot write %s.',path);
cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
end
