function report=run_autonomous_tests
%RUN_AUTONOMOUS_TESTS Accepted natural gate plus two coupled diagnostic cases.
% Restart MATLAB, set Current Folder to this extracted autocase folder, run:
%   report = run_autonomous_tests;
% Return the printed ZIP even when the common-input case stops at divergence.
root=char(java.io.File(fileparts(mfilename('fullpath'))).getCanonicalPath());
oldPath=path; oldFolder=pwd;
restoreEnvironment=onCleanup(@()restore(oldPath,oldFolder)); %#ok<NASGU>
out=uniqueFolder(root,['out_auto_' datestr(now,'yyyymmdd_HHMMSS')]);
report=struct('schema','csr-autonomous-owner-v1','completed',false, ...
    'matlab_execution_required',true,'numerical_parity_established',false,'target_percent',15, ...
    'runtime',struct('version',version,'release',version('-release'),'computer',computer), ...
    'cases',struct([]),'archive','','archive_completed',false,'error_identifier','','error_message','');
diary(fullfile(out,'console.log')); diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
started=tic;
fprintf('\nSeed 132: natural capture and fully coupled common random inputs, 0–330 s.\n');
fprintf('All seven nodes warm up from time zero. No receiver state or feedback is replayed.\n');
fprintf('C tests receiver callback timing; D adds only synchronous no-ACK KEY_REQUEST admission.\n');
fprintf('The accepted natural capture is reused only when its source, hashes, runtime and configuration match.\n');
try
    model=fullfile(root,'model');
    loaded=inmem('-completenames');
    for k=1:numel(loaded)
        file=strrep(char(loaded{k}),'\','/');
        if contains(file,'/+csr/') || contains(file,'/+ac/')
            file=char(java.io.File(char(loaded{k})).getCanonicalPath());
            assert(startsWith(file,[root filesep]),'autocase:CachedModel', ...
                'Another CSR copy is already loaded. Restart MATLAB and run this autocase folder.');
        end
    end
    cd(root); restoredefaultpath; addpath(root,model,'-begin'); rehash;
    manifest=jsondecode(fileread(fullfile(root,'FILES.json')));
    verifyFiles(root,manifest.files);
    nativeReceipt=jsondecode(fileread(fullfile(root,'ref','native','receipt.json')));
    assert(strcmp(nativeReceipt.status,'verified_exact_native_prefix') && ...
        nativeReceipt.canonical_rows==48919 && numel(nativeReceipt.canonical_fields)==30 && ...
        nativeReceipt.stop_ns_exclusive==330000000000, ...
        'autocase:NativeFidelity','The native fixture has not passed its required canonical prefix gate.');
    resolved=bindSource(root,manifest.files);
    report.case_design=struct('A_natural','Accepted natural run reused if exact gates match; otherwise fresh natural run', ...
        'C_timing','Native random inputs with existing nanosecond receiver callback option', ...
        'D_inline_key','Same timing option plus isolated fresh no-ACK KEY_REQUEST admission candidate');
    report.previous_common_case=jsondecode(fileread(fullfile(root,'ref','history','history.json')));
    ac.writeJson(fullfile(out,'previous_case_history.json'),report.previous_common_case);
    ac.writeJson(fullfile(out,'provenance.json'),struct('runtime',report.runtime, ...
        'manifest',manifest,'resolved_matlab_files',resolved, ...
        'optional_native_namespace','Hashed in full; not resolved or loaded by the portable runtime binding check', ...
        'source_transform',jsondecode(fileread(fullfile(root,'source_transform.json'))), ...
        'candidate_transform',jsondecode(fileread(fullfile(root,'candidate_transform.json')))));
    config=csr.scenario.importNs3(fullfile(root,'inputs','s132.csv'), ...
        struct('HistoricalBenchmark',true,'FlowLimit',0,'Backend','portable'));
    assert(config.Seed==132 && config.DurationSeconds==6000,'autocase:Scenario','Unexpected source scenario.');
    assert(isequal([config.Nodes.Id],[1 2 3 4 5 7 8]),'autocase:Nodes','All seven campus nodes are required.');
    assert(numel(config.Traffic)==6 && all([config.Traffic.StartSeconds]==300) && ...
        all([config.Traffic.IntervalSeconds]==0.02) && all([config.Traffic.DestinationId]==1), ...
        'autocase:Traffic','Fixed source offers must preserve the original scenario.');
    config.DurationSeconds=330;
    config.Trace.Enabled=true; config.Trace.MaxRecords=200000;
    config.Trace.MaxPhyRecords=200000; config.Trace.MaxApplicationAdmissionRecords=20000;
    config.MaxEvents=2000000;
    config=csr.scenario.validate(config);
    ac.writeJson(fullfile(out,'configuration.json'),config);
    fprintf('Checking native CSV import and the original first MAC request before any network simulation.\n');
    report.import_preflight=ac.nativeImportPreflight(root,fullfile(out,'import_preflight'));
    [reused,first,reuse]=reuseNatural(root,out,config,report.runtime);
    report.accepted_natural_reuse=reuse;
    if ~reused, first=runCase(root,out,config,'A_natural','natural'); end
    report.cases=first;
    if first.completed && first.natural_prefix_passed
        fprintf('Checking isolated KEY_REQUEST admission, replacement, capacity and callback ownership.\n');
        report.key_request_preflight=ac.keyRequestPreflight(config,fullfile(out,'key_preflight'));
        second=runCase(root,out,config,'C_timing','native');
        report.cases(end+1)=second;
        % A diagnostic stop in C must not suppress the independent candidate.
        third=runCase(root,out,config,'D_inline_key','native');
        report.cases(end+1)=third;
    else
        fprintf('\nCases C and D skipped: natural source-fidelity gate did not pass. Return this ZIP.\n');
    end
    verifyFiles(root,manifest.files);
    report.completed=numel(report.cases)==3 && all([report.cases.completed]);
catch caught
    report.error_identifier=caught.identifier; report.error_message=caught.message;
    report.error_stack=caught.stack;
    fprintf('\nSetup or final verification failed: %s\n',caught.message);
end
ac.Trace.close(); report.wall_seconds=toc(started);
report.archive=[out '.zip'];
embeddedReport=rmfield(report,'archive_completed');
embeddedReport.archive_status='Archive construction follows this report; successful archive receipt is saved beside the archive.';
ac.writeJson(fullfile(out,'report.json'),embeddedReport);
diary('off');
try
    listing=dir(fullfile(out,'**','*')); listing=listing(~[listing.isdir]);
    names=cell(numel(listing),1);
    for k=1:numel(listing)
        file=fullfile(listing(k).folder,listing(k).name);
        names{k}=file(numel(out)+2:end);
    end
    zip(report.archive,names,out); report.archive_completed=true;
    ac.writeJson(fullfile(out,'archive_receipt.json'), ...
        struct('archive',report.archive,'sha256',hashFile(report.archive),'completed',true));
    fprintf('\nReturn this ZIP, including any divergence or error evidence:\n%s\n',report.archive);
catch caught
    fprintf('\nZIP creation failed: %s\nEvidence is saved in %s\n',caught.message,out);
    report.archive_error=caught.message;
end
fprintf('Simulations completed=%d; ZIP created=%d; elapsed %.1f minutes.\n', ...
    report.completed,report.archive_completed,toc(started)/60);
end

function [reused,item,details]=reuseNatural(root,out,config,runtime)
reused=false; item=[];
folder=fullfile(root,'ref','accepted');
proof=jsondecode(fileread(fullfile(folder,'reuse_proof.json')));
assert(strcmp(proof.schema,'csr-accepted-natural-reuse-v1') && ...
    proof.static_natural_source_identity_proven,'autocase:ReuseProof','Invalid natural source-reuse proof.');
verifyFiles(folder,proof.accepted_files);
verifyFiles(root,proof.unchanged_natural_source_files);
assert(strcmp(hashFile(fullfile(root,'+ac','Streams.m')),proof.current_streams_sha256), ...
    'autocase:ReuseSource','The source proof does not describe this repaired provider.');
runtimeMatches=strcmp(runtime.version,proof.accepted_runtime.version) && ...
    strcmp(runtime.release,proof.accepted_runtime.release) && strcmp(runtime.computer,proof.accepted_runtime.computer);
acceptedConfig=jsondecode(fileread(fullfile(folder,'configuration.json')));
currentConfig=jsondecode(jsonencode(config));
% SourcePath describes where the already-hash-bound CSV was imported; the
% production simulator does not read it. A new extraction path is expected.
acceptedSourcePath=acceptedConfig.SharedScenario.SourcePath;
currentSourcePath=currentConfig.SharedScenario.SourcePath;
acceptedConfig.SharedScenario.SourcePath='hash-bound inputs/s132.csv';
currentConfig.SharedScenario.SourcePath='hash-bound inputs/s132.csv';
configMatches=isequaln(currentConfig,acceptedConfig);
details=struct('reused',false,'runtime_matches',runtimeMatches,'configuration_matches',configMatches, ...
    'accepted_runtime',proof.accepted_runtime,'fresh_natural_simulation_executed',false, ...
    'source_basis','All model and natural producer bytes match; Streams edits are confined to native-only import and matching.', ...
    'prefix_gate_recomputed',false, ...
    'configuration_metadata_path_only',struct('accepted',acceptedSourcePath,'current',currentSourcePath), ...
    'configuration_path_rule','Only SharedScenario.SourcePath is canonicalized; input CSV hash and every behavioral field are checked');
if ~runtimeMatches || ~configMatches
    fprintf('Runtime or configuration differs from the accepted natural capture; running a fresh case A.\n');
    details.fresh_natural_simulation_executed=true; return;
end
accepted=jsondecode(fileread(fullfile(folder,'case_summary.json')));
oldGate=jsondecode(fileread(fullfile(folder,'prefix_gate.json')));
assert(accepted.completed && accepted.natural_prefix_passed && accepted.reached_time_s==330 && ...
    oldGate.passed && all([oldGate.checks.passed]),'autocase:ReuseAcceptance','Packaged natural case was not accepted.');
% This is the same strict CSV comparison as a newly executed natural case.
gate=comparePrefix(folder,fullfile(root,'ref','matlab'));
assert(gate.passed,'autocase:ReusePrefix','Packaged accepted tables no longer pass the original exact prefix gate.');
target=fullfile(out,'A_natural'); mkdir(target);
for name={'protocol_trace.csv','phy_trace.csv','application_admission_trace.csv', ...
        'observer_status.json','random_summary.json'}
    [okay,message]=copyfile(fullfile(folder,name{1}),fullfile(target,name{1}));
    assert(okay,'autocase:ReuseCopy','%s',message);
end
ac.writeJson(fullfile(target,'prefix_gate.json'),gate);
item=struct('name','A_natural','mode','natural','completed',true,'natural_prefix_passed',true, ...
    'reached_time_s',330,'diagnostic_status','accepted_prior_run_reused', ...
    'error_identifier','','error_message','','wall_seconds',0);
ac.writeJson(fullfile(target,'case_summary.json'),item);
details.reused=true; details.prefix_gate_recomputed=true;
details.accepted_previous_wall_seconds=accepted.wall_seconds;
ac.writeJson(fullfile(target,'accepted_reuse.json'),struct('reuse',details,'proof',proof));
reused=true;
fprintf('Case A: accepted prior run reused; all 3 exact prefix gates rechecked. No new natural simulation.\n');
end

function item=runCase(root,out,config,name,mode)
folder=fullfile(out,name); mkdir(folder);
item=struct('name',name,'mode',mode,'completed',false,'natural_prefix_passed',false, ...
    'reached_time_s',NaN,'diagnostic_status','not_started','error_identifier','','error_message','','wall_seconds',0);
started=tic; ac.Trace.open(folder);
observer=csr.sim.AckServiceDiagnostics(200000,[0 330]);
options=struct('Mode',mode,'Fixture',fullfile(root,'ref','native','random_draws.csv'),'Folder',folder);
timing=[];
fprintf('\n%s starting. A semantic divergence is a diagnostic result, not a parity pass.\n',name);
try
    if strcmp(mode,'native'), timing=csr.sim.TransportTiming('nanoseconds',200000); end
    if strcmp(name,'D_inline_key')
        simulation=ac.InlineKeySimulation(config,observer,timing,options);
    else
        simulation=csr.sim.NetworkSimulation(config,observer,timing,options);
    end
    result=simulation.run();
    item.reached_time_s=simulation.Scheduler.Now;
    exportRaw(result,folder);
    assert(item.reached_time_s==330,'autocase:Incomplete','Requested endpoint was not reached.');
    assert(result.Statistics.OmittedTraceRecords==0 && result.Statistics.OmittedPhyTraceRecords==0 && ...
        result.Statistics.OmittedApplicationAdmissionRecords==0, ...
        'autocase:Omitted','A required raw trace was truncated.');
    observer.assertComplete();
    ac.writeJson(fullfile(folder,'statistics.json'),result.Statistics);
    if strcmp(mode,'natural')
        gate=comparePrefix(folder,fullfile(root,'ref','matlab'));
        ac.writeJson(fullfile(folder,'prefix_gate.json'),gate);
        item.natural_prefix_passed=gate.passed;
        assert(gate.passed,'autocase:NaturalPrefixMismatch', ...
            'Natural instrumented capture does not match the existing 6,000-second prefix.');
    end
    if strcmp(mode,'native')
        randomStatus=simulation.autonomousRandomSummary();
        assert(randomStatus.native_tape_exhausted,'autocase:UnusedNativeDraws', ...
            'Simulation reached 330 seconds with unused native random inputs.');
        item.diagnostic_status='completed_context_checks';
    else
        item.diagnostic_status='natural_prefix_passed';
    end
    item.completed=true;
catch caught
    item.error_identifier=caught.identifier; item.error_message=caught.message;
    if any(strcmp(caught.identifier,{'autocase:DrawContextDivergence','autocase:TxContextDivergence','autocase:UnusedNativeDraws'}))
        item.diagnostic_status='context_divergence';
    elseif strcmp(caught.identifier,'autocase:NaturalPrefixMismatch')
        item.diagnostic_status='natural_prefix_failed';
    else
        item.diagnostic_status='unexpected_harness_error';
    end
    ac.writeJson(fullfile(folder,'error.json'),struct('identifier',caught.identifier, ...
        'message',caught.message,'stack',caught.stack));
    fprintf('%s stopped: %s\n',name,caught.message);
    if exist('simulation','var')
        item.reached_time_s=simulation.Scheduler.Now;
        try, exportRaw(simulation.autonomousPartial(),folder); catch exportError
            ac.writeJson(fullfile(folder,'partial_export_error.json'),struct('message',exportError.message));
        end
    end
end
try
    observed=observer.snapshot();
    writetable(observed.ServiceTrace,fullfile(folder,'service_trace.csv'));
    writetable(observed.LinkDecisionTrace,fullfile(folder,'link_decisions.csv'));
    writetable(observed.ActualFeedbackTrace,fullfile(folder,'actual_feedback.csv'));
    ac.writeJson(fullfile(folder,'observer_status.json'),observed.ServiceDiagnostics);
catch caught
    ac.writeJson(fullfile(folder,'observer_export_error.json'),struct('message',caught.message));
    item.completed=false;
end
if exist('simulation','var')
    try
        ac.writeJson(fullfile(folder,'random_summary.json'),simulation.autonomousRandomSummary());
        simulation.autonomousClose();
    catch caught
        item.completed=false; item.diagnostic_status='unexpected_harness_error';
        ac.writeJson(fullfile(folder,'random_export_error.json'),struct('message',caught.message));
    end
end
if ~isempty(timing)
    try
        timingStatus=timing.snapshot();
        writetable(timingStatus.Records,fullfile(folder,'transport_timing.csv'));
        ac.writeJson(fullfile(folder,'transport_timing_summary.json'),rmfield(timingStatus,'Records'));
    catch caught
        item.completed=false; item.diagnostic_status='unexpected_harness_error';
        ac.writeJson(fullfile(folder,'transport_export_error.json'),struct('message',caught.message));
    end
end
ac.Trace.close(); item.wall_seconds=toc(started);
ac.writeJson(fullfile(folder,'case_summary.json'),item);
fprintf('%s endpoint %.9g s, completed=%d, elapsed %.1f min.\n', ...
    name,item.reached_time_s,item.completed,item.wall_seconds/60);
end

function exportRaw(result,folder)
map={'ProtocolTrace','protocol_trace.csv';'PhyTrace','phy_trace.csv'; ...
    'ApplicationAdmissionTrace','application_admission_trace.csv'};
for k=1:size(map,1)
    value=result.(map{k,1}); value=value(value.TimeSeconds<330,:);
    writetable(value,fullfile(folder,map{k,2}));
end
end

function output=comparePrefix(folder,reference)
files={'protocol_trace.csv','phy_trace.csv','application_admission_trace.csv'};
checks=struct('file',{},'actual_rows',{},'reference_rows',{},'passed',{},'first_row',{},'first_column',{});
for k=1:numel(files)
    wantedFile=fullfile(reference,files{k}); actualFile=fullfile(folder,files{k});
    opts=detectImportOptions(wantedFile,'TextType','string');
    expected=readtable(wantedFile,opts); actual=readtable(actualFile,opts);
    item=struct('file',files{k},'actual_rows',height(actual),'reference_rows',height(expected), ...
        'passed',isequaln(actual,expected),'first_row',NaN,'first_column','');
    if ~item.passed
        for row=1:min(height(actual),height(expected))
            for col=1:width(expected)
                if ~isequaln(actual{row,col},expected{row,col})
                    item.first_row=row; item.first_column=expected.Properties.VariableNames{col}; break
                end
            end
            if ~isnan(item.first_row), break; end
        end
    end
    checks(end+1)=item; %#ok<AGROW>
end
output=struct('schema','csr-autonomous-natural-prefix-v1','passed',all([checks.passed]), ...
    'window','0 <= time < 330','comparison','Exact table values after identical CSV import options; no timing tolerance', ...
    'reference','Corrected owner 6,000-second seed-132 return, R2025a', 'checks',checks);
end

function resolved=bindSource(root,files)
resolved=struct('name',{},'path',{},'sha256',{});
for k=1:numel(files)
    relative=char(files(k).path);
    if ~endsWith(relative,'.m'), continue; end
    % Hash verification covers this optional branch, but resolving its
    % class definitions may load an unavailable wnet.Node on R2025a.
    if startsWith(relative,'model/+csr/+sim/+native/'), continue; end
    parts=strsplit(relative,'/');
    if strcmp(parts{1},'model'), parts=parts(2:end); end
    if any(strcmp(parts,'private')), continue; end
    for j=1:numel(parts), parts{j}=erase(parts{j},'+'); end
    parts{end}=parts{end}(1:end-2); name=strjoin(parts,'.');
    found=which(name); expected=fullfile(root,strrep(relative,'/',filesep));
    assert(~isempty(found) && strcmp(char(java.io.File(found).getCanonicalPath()), ...
        char(java.io.File(expected).getCanonicalPath())), ...
        'autocase:SourceBinding','Wrong source resolves for %s. Restart MATLAB in this kit.',name);
    resolved(end+1)=struct('name',name,'path',found,'sha256',hashFile(found)); %#ok<AGROW>
end
end

function verifyFiles(root,files)
for k=1:numel(files)
    p=char(files(k).path);
    assert(isempty(regexp(p,'(^/|^[A-Za-z]:|(^|[\\/])\.\.([\\/]|$))','once')), ...
        'autocase:ManifestPath','Unsafe manifest path.');
    assert(strcmp(hashFile(fullfile(root,strrep(p,'/',filesep))),files(k).sha256), ...
        'autocase:SourceChanged','Missing or changed kit file: %s.',p);
end
end
function value=hashFile(file)
fid=fopen(file,'rb'); assert(fid>=0,'autocase:HashOpen','Cannot read %s.',file);
cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
md=java.security.MessageDigest.getInstance('SHA-256');
while ~feof(fid)
    bytes=fread(fid,1048576,'*uint8');
    if ~isempty(bytes), md.update(typecast(bytes,'int8')); end
end
value=lower(reshape(dec2hex(typecast(md.digest(),'uint8'),2).',1,[]));
end
function folder=uniqueFolder(root,stem)
folder=fullfile(root,stem); n=1;
while isfolder(folder) || isfile(folder) || isfile([folder '.zip']), n=n+1; folder=fullfile(root,sprintf('%s_%02d',stem,n)); end
[ok,message]=mkdir(folder); assert(ok,'autocase:Mkdir','%s',message);
end
function restore(oldPath,oldFolder)
path(oldPath); if isfolder(oldFolder), cd(oldFolder); end
end
