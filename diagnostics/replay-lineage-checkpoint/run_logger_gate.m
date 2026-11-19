function run_logger_gate(runtimeDir, outputParent)
% Logger-only qualification. No simulator or scheduler is constructed.
arguments
    runtimeDir (1,1) string
    outputParent (1,1) string
end
assert(ispc,'loggerGate:Platform','The original writer requires Windows MATLAB.');
assert(isfolder(runtimeDir) && isfolder(outputParent),'loggerGate:Paths','Use existing runtime and test folders.');
here = fileparts(mfilename('fullpath'));
originalPath = path;
restorePath = onCleanup(@() path(originalPath)); %#ok<NASGU>
addpath(runtimeDir, '-begin');
assert(strcmpi(which('ReplayLineageTap'), fullfile(here,'ReplayLineageTap.m')), ...
    'loggerGate:Shadow','The logger does not resolve to this test kit.');
classes = ["Autonomous6000Sink","BoundedJsonlWriter","DiagnosticByteBudget"];
hashes = ["93ba940ecd8596e386d7fd24d1c3b302cf08981068fbfc000185e0cd33896d95", ...
    "8a5e9ea5967693472250f5e248e4ed754c099da49ddbf7691fb9668dae5c3e32", ...
    "cef1e58831448cdb520122fa371cccb2e0b786cb879cc599eab8798d62c09a45"];
for k = 1:numel(classes)
    className = classes(k);
    expected = fullfile(runtimeDir,className + ".m");
    assert(strcmpi(which(char(className)), expected), ...
        'loggerGate:Shadow','Wrong source for %s.',char(className));
    assert(strcmpi(sha256(expected),hashes(k)), ...
        'loggerGate:Hash','Original source hash mismatch for %s.',char(className));
end
preflightPool = DiagnosticByteBudget(char(outputParent),256*1024^2,0,4096); %#ok<NASGU>
root = tempname(outputParent);
assert(~isfolder(root) && ~isfile(root),'loggerGate:Collision','Output exists.');
[ok,msg] = mkdir(root);
assert(ok,'loggerGate:Mkdir','%s',msg);
fprintf('LOGGER_GATE MATLAB=%s platform=%s\nOutput: %s\n',version,computer,root);
limits = struct('MaxNodes',65536,'MaxTextUnits',65536,'MaxDepth',32,'MaxEncodedBytes',262144);
plan = struct('Schema','csr-replay-lineage-plan-v1','ApplicationSources',8:12, ...
    'MaxRows',65536,'PayloadBytes',16777216,'RecordLimits',limits);
identity = struct('case_id','synthetic_three_relay15_i30_v1','seed',10025,'rng_run',1, ...
    'token',repmat('a',1,64),'config_sha256',repmat('b',1,64));
normal = fullfile(root,'normal');
[base,writer,tap] = setup(normal,plan,identity,true,16777216);
cleanNormal = onCleanup(@() closeBestEffort(tap)); %#ok<NASGU>
appId = bitshift(uint64(1),53) + uint64(1);
tap.record(300,'application_attempt',8,struct('SourceId',8,'AppId',appId));
tap.record(301,'protocol',8,struct('event','synthetic_filter', ...
    'frame',struct('Kind','ACK','App',struct())));
baseSummary = base.summary();
assert(strcmp(baseSummary.CallbackCount,'2'),'loggerGate:CallbackCount','Original sink did not see exactly two inputs.');
expectError(@() tap.record(600,'scheduler_fire',0,struct()),'naturalCausal:Endpoint');
tap.close();
tap.close();
receipt = tap.summary();
assert(receipt.complete && receipt.endpoint_observed && receipt.writer_closed && writer.Closed && ...
    receipt.attempted==2 && receipt.emitted==1 && receipt.filtered==1 && receipt.dropped==0, ...
    'loggerGate:Receipt','Normal run receipt does not reconcile.');
data = fileread(fullfile(normal,'sidecar.jsonl'));
lines = splitlines(strtrim(string(data)));
assert(numel(lines)==1,'loggerGate:Rows','Expected one sidecar row.');
row = jsondecode(char(lines(1)));
assert(ischar(row.details.AppId) && strcmp(row.details.AppId,'9007199254740993'), ...
    'loggerGate:ExactId','Packet ID did not round-trip as exact decimal text.');
fprintf('PASS: sink callback count, filter, exact ID, exclusive endpoint, close.\n');
disabled = fullfile(root,'disabled');
[base,~,tap] = setup(disabled,plan,identity,false,0);
cleanDisabled = onCleanup(@() closeBestEffort(tap)); %#ok<NASGU>
tap.record(300,'application_attempt',8,struct('SourceId',8,'AppId',appId));
tap.close();
receipt = tap.summary();
baseSummary = base.summary();
assert(strcmp(baseSummary.CallbackCount,'1') && ~receipt.enabled && ...
    ~receipt.complete && receipt.emitted==0 && ~isfile(fullfile(disabled,'sidecar.jsonl')), ...
    'loggerGate:Disable','Disabled mode must not open a sidecar.');
fprintf('PASS: disabled capture preserves original callback.\n');

limited = fullfile(root,'limited');
[base,limitedWriter,tap] = setup(limited,plan,identity,true,128);
cleanLimited = onCleanup(@() closeBestEffort(tap)); %#ok<NASGU>
failedRecord = @() tap.record(300,'application_attempt',8,struct('SourceId',8,'AppId',appId));
expectError(failedRecord,'diag2490:PayloadCap');
expectError(failedRecord,'replayTap:Stopped');
tap.close();
receipt = tap.summary();
baseSummary = base.summary();
sidecarInfo = dir(fullfile(limited,'sidecar.jsonl'));
assert(strcmp(baseSummary.CallbackCount,'1') && receipt.faulted && ...
    ~receipt.complete && receipt.emitted==0 && receipt.dropped==1 && ...
    limitedWriter.Closed && isscalar(sidecarInfo) && sidecarInfo.bytes==0, ...
    'loggerGate:Cap','Over-cap record did not fail before writing.');
fprintf('PASS: byte cap rejects before writing and prevents further callbacks.\n');
fprintf('LOGGER_GATE PASS: 3 checks passed; no model run.\n');
end

function [base,sidecar,tap] = setup(p,plan,identity,enabled,payload)
[ok,msg] = mkdir(p);
assert(ok,'loggerGate:Mkdir','%s',msg);
pool = DiagnosticByteBudget(char(p),256*1024^2,0,4096);
original = BoundedJsonlWriter(char(fullfile(p,'original.jsonl')),pool,4096,0,0,plan.RecordLimits);
base = Autonomous6000Sink(original,@noModelCallback,false,[300 600],1:15,1000000,[],600);
sidecar = [];
try
    if enabled
        sidecar = BoundedJsonlWriter(char(fullfile(p,'sidecar.jsonl')),pool,payload,0,0,plan.RecordLimits);
    end
    tap = ReplayLineageTap(base,sidecar,identity,plan,enabled);
catch exception
    if ~isempty(sidecar),closeBestEffort(sidecar);end
    closeBestEffort(base);
    rethrow(exception);
end
end

function expectError(f,id)
try
    f();
catch e
    assert(strcmp(e.identifier,id),'loggerGate:UnexpectedError','Expected %s, got %s.',id,e.identifier);
    return;
end
error('loggerGate:MissingError','Expected %s.',id);
end

function closeBestEffort(x)
try
    x.close();
catch
    % A test assertion keeps its original error on cleanup.
end
end

function hex = sha256(file)
fid = fopen(file,'rb');
assert(fid~=-1,'loggerGate:Read','Cannot read %s.',char(file));
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
bytes = fread(fid,256*1024+1,'*uint8');
assert(numel(bytes)<=256*1024,'loggerGate:Read','Unexpected source size.');
md = java.security.MessageDigest.getInstance('SHA-256');
md.update(typecast(bytes(:),'int8'));
digest = typecast(md.digest(),'uint8');
hex = lower(reshape(dec2hex(digest,2).',1,[]));
end

function noModelCallback(varargin) %#ok<INUSD>
end
