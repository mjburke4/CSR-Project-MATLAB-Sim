function report = run_current_policy_adapter(planPath,expectedPlanSHA256)
% Opt-in owned-batch preflight and matched component only. Never a full runner.
% External controller supplies/attests ownership and asynchronously enforces caps.
assert(ispc&&usejava('jvm'),'adapter:Platform','Windows and JVM are required.');
assert(batchStartupOptionUsed()&&~usejava('desktop'),'adapter:FreshBatch', ...
    'Use a newly owned -batch process. Existing GUI sessions are never cleared.');
started=tic;
packageRoot=char(System.IO.Path.GetFullPath(fileparts(fileparts(mfilename('fullpath')))));
assertPlainPath(packageRoot);
assert(ischar(planPath)&&isrow(planPath)&&ischar(expectedPlanSHA256),'adapter:Plan','Explicit plan and SHA-256 required.');
planPath=char(System.IO.Path.GetFullPath(planPath));assertPlainPath(planPath);
assert(strcmp(sha256(planPath),expectedPlanSHA256),'adapter:PlanHash','Plan hash mismatch.');
plan=readJson(planPath,65536); validatePlan(plan);
manifestPath=relativeFile(packageRoot,'PACKAGE_MANIFEST.json');
assert(strcmp(sha256(manifestPath),plan.package_manifest_sha256),'adapter:ManifestHash','Manifest hash mismatch.');
manifest=readJson(manifestPath,1024^2);
assert(strcmp(manifest.schema,'csr-component-package-v1'));
verifyPackage(packageRoot,manifest);
sourcePath=relativeFile(packageRoot,'SOURCE_MANIFEST.json');
assert(strcmp(sha256(sourcePath),plan.source_manifest_sha256),'adapter:SourceHash','Source manifest mismatch.');
sources=readJson(sourcePath,1024^2);
assert(strcmp(sources.schema,'csr-component-sources-v1'));
% Loaded classes/functions are never cleared or swapped. Check before addpath.
[mfiles,mexfiles,classes]=inmem('-completenames');
loaded=[mfiles(:);mexfiles(:);classes(:)];
for k=1:numel(loaded)
    entry=strrep(loaded{k},'\','/');[~,stem]=fileparts(entry);
    packageLoaded=contains(entry,'/+ac/')||contains(entry,'/+csr/')|| ...
        startsWith(entry,'ac.')||startsWith(entry,'csr.');
    namedLoaded=any(strcmp(stem,{sources.effective_symbols.symbol}))|| ...
        any(strcmp(entry,{sources.effective_symbols.symbol}));
    assert(~packageLoaded&&(~namedLoaded||strcmp(stem,'run_current_policy_adapter')), ...
        'adapter:Preloaded','A relevant symbol is already loaded. Start a fresh owned process.');
end
outputRoot=char(System.IO.Path.GetFullPath(plan.output_root));assertPlainPath(outputRoot);
assert(System.IO.Directory.Exists(outputRoot),'adapter:OutputRoot','Output root must exist.');
assert(~isWithin(outputRoot,packageRoot)&&~isWithin(packageRoot,outputRoot), ...
    'adapter:OutputRoot','Output and package directories must be disjoint.');
outputEntries=System.IO.Directory.GetFileSystemEntries(outputRoot);
outputEntryCount=double(outputEntries.Length);
fprintf('adapter:OutputDirectoryCensus MATLAB_numel=%g NET_Length=%g\n',numel(outputEntries),outputEntryCount);
assert(outputEntryCount==0,'adapter:OutputNotEmpty','Preserve prior outputs.');
receiptPath=char(System.IO.Path.GetFullPath(plan.ownership_receipt_path));assertPlainPath(receiptPath);
assert(~isWithin(receiptPath,outputRoot)&&~isWithin(receiptPath,packageRoot),'adapter:ReceiptPath','Receipt must be outside package/output.');
assert(~isWithin(planPath,outputRoot)&&~isWithin(planPath,packageRoot),'adapter:PlanPath','Plan must be outside package/output.');
configPath=char(System.IO.Path.GetFullPath(plan.scientific_configuration_path));assertPlainPath(configPath);
assert(~isWithin(configPath,outputRoot)&&~isWithin(configPath,packageRoot), ...
    'adapter:PrivateConfigurationPath','Configuration must stay outside package/output.');
assert(System.IO.File.Exists(configPath),'adapter:PrivateConfigurationPath','Explicit private configuration file required.');
configInfo=System.IO.FileInfo(configPath);
assert(double(configInfo.Length)<=1024^2,'adapter:ConfigurationSize','Private configuration exceeds 1 MiB.');
assert(strcmp(sha256(configPath),plan.scientific_configuration_sha256), ...
    'adapter:ConfigurationHash','Private configuration mismatch.');
receiptHash=sha256(receiptPath);receipt=readJson(receiptPath,65536);
assert(strcmp(receipt.schema,'csr-owned-component-receipt-v1')&&receipt.job_owned&& ...
    receipt.local_job_binding_verified&&~receipt.engine_creation_independently_verified&& ...
    strcmp(receipt.execution_id,plan.execution_id)&&strcmp(receipt.plan_sha256,expectedPlanSHA256)&& ...
    strcmp(receipt.package_manifest_sha256,plan.package_manifest_sha256)&& ...
    receipt.memory_limit_bytes==plan.memory_limit_bytes&&receipt.max_wall_seconds==plan.max_wall_seconds&& ...
    receipt.output_cap_bytes==plan.output_cap_bytes&&strcmp(receipt.deadline_utc,plan.deadline_utc), ...
    'adapter:Ownership','Existing owned-job route receipt does not bind this plan.');
deadline=datetime(plan.deadline_utc,'InputFormat',"yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",'TimeZone','UTC');
check();
originalPath=path;pathCleanup=onCleanup(@()path(originalPath)); %#ok<NASGU>
addpath(fullfile(packageRoot,'frozen','model'),'-begin');
addpath(fullfile(packageRoot,'frozen'),'-begin');
addpath(fullfile(packageRoot,'frozen','runtime'),'-begin');
addpath(fullfile(packageRoot,'fixture'),'-begin');
addpath(fullfile(packageRoot,'adapter'),'-begin');
addpath(fullfile(packageRoot,'observer'),'-begin');
resolution=verifyResolution(packageRoot,sources);
rawConfig=readJson(configPath,1024^2);
config=csr.scenario.validate(rawConfig,'ac.DiscoveryMembershipNwk');
assert(strcmp(jsonencode(config),jsonencode(rawConfig)),'adapter:ConfigValues', ...
    'Validation changed a JSON-visible scientific field. No fallback is permitted.');
check();
preflightRoot=fullfile(outputRoot,'preflight');System.IO.Directory.CreateDirectory(preflightRoot);
preflight=preflight_current_policy(config,preflightRoot,@check);
check();matched=false;componentSHA='';
if strcmp(plan.mode,'preflight-and-matched')
    % These are the exact accepted scripted harness bytes, not new model logic.
    componentPath=fullfile(outputRoot,'COMPONENT.json');
    run_congestion_candidate(configPath,componentPath);
    check();componentSHA=sha256(componentPath);matched=true;
end
assert(isempty(ac.Trace.holder()),'adapter:TraceSink','Trace sink remains active.');
verifyResolution(packageRoot,sources);verifyPackage(packageRoot,manifest);check();
writeJsonNew(fullfile(outputRoot,'SOURCE_RESOLUTION.json'),resolution,256*1024);
report=struct('schema','csr-component-adapter-result-v1','passed',true, ...
    'mode',plan.mode,'release',version('-release'),'runtime',version, ...
    'package_manifest_sha256',plan.package_manifest_sha256, ...
    'source_manifest_sha256',plan.source_manifest_sha256, ...
    'private_configuration_binding_checked',true,'configuration_contents_exported',false, ...
    'preflight',preflight,'matched_fixture_executed',matched,'component_sha256',componentSHA, ...
    'cross_engine_comparison_performed',false,'full_network_run_performed',false, ...
    'ownership_receipt_binding_checked',true,'engine_creation_independently_verified',false, ...
    'external_job_enforcement_independently_verified_by_adapter',false, ...
    'owned_job_closure_requires_controller_receipt',true,'elapsed_seconds',toc(started), ...
    'scope','Constructor/writers and optional scripted NWK/HOP component only; separate HOP clock edge is not an equality pass.');
writeJsonNew(fullfile(outputRoot,'ADAPTER_RESULT.json'),report,128*1024);check();

    function check()
        assert(toc(started)<=plan.max_wall_seconds&&datetime('now','TimeZone','UTC')<deadline, ...
            'adapter:Deadline','Deadline exceeded. Outer owned watchdog must enforce asynchronous termination.');
        assert(strcmp(sha256(receiptPath),receiptHash)&&strcmp(sha256(planPath),expectedPlanSHA256), ...
            'adapter:BindingChanged','Plan or ownership receipt changed.');
        assertPlainPath(configPath);
        currentConfigInfo=System.IO.FileInfo(configPath);
        assert(currentConfigInfo.Exists&&double(currentConfigInfo.Length)<=1024^2, ...
            'adapter:ConfigurationSize','Private configuration is absent or exceeds 1 MiB.');
        assert(strcmp(sha256(configPath),plan.scientific_configuration_sha256), ...
            'adapter:ConfigurationChanged','Private configuration changed.');
        assertPlainPath(outputRoot);checkOutputs(outputRoot,plan.output_cap_bytes);
    end
end

function validatePlan(p)
required={'schema','mode','execution_id','package_manifest_sha256','source_manifest_sha256', ...
 'scientific_configuration_path','scientific_configuration_sha256','output_root','ownership_receipt_path','deadline_utc', ...
 'max_wall_seconds','memory_limit_bytes','output_cap_bytes'};
assert(isstruct(p)&&isscalar(p)&&isequal(sort(fieldnames(p)),sort(required(:))),'adapter:PlanFields','Exact plan schema required.');
assert(strcmp(p.schema,'csr-component-execution-plan-v1')&&any(strcmp(p.mode,{'preflight-only','preflight-and-matched'})));
assert(ischar(p.execution_id)&&~isempty(regexp(p.execution_id,'^[A-Za-z0-9_-]{1,80}$','once')));
for name={'package_manifest_sha256','source_manifest_sha256','scientific_configuration_sha256'}
 assert(ischar(p.(name{1}))&&~isempty(regexp(p.(name{1}),'^[0-9a-f]{64}$','once')));
end
for name={'output_root','ownership_receipt_path','scientific_configuration_path','deadline_utc'}
 assert(ischar(p.(name{1}))&&isrow(p.(name{1}))&&~isempty(p.(name{1})));
end
validateattributes(p.max_wall_seconds,{'numeric'},{'scalar','finite','integer','>=',1,'<=',300});
validateattributes(p.memory_limit_bytes,{'numeric'},{'scalar','finite','integer','>=',1,'<=',3*1024^3});
validateattributes(p.output_cap_bytes,{'numeric'},{'scalar','finite','integer','>=',20*1024^2,'<=',64*1024^2});
assert(~isempty(regexp(p.deadline_utc,'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$','once')));
assert(System.IO.Path.IsPathRooted(p.output_root)&&System.IO.Path.IsPathRooted(p.ownership_receipt_path)&& ...
    System.IO.Path.IsPathRooted(p.scientific_configuration_path));
end
function value=readJson(p,cap)
info=System.IO.FileInfo(p);assert(info.Exists&&double(info.Length)<=cap,'adapter:ReadCap','Missing or oversized JSON.');
value=jsondecode(native2unicode(reshape(uint8(System.IO.File.ReadAllBytes(p)),1,[]),'UTF-8'));
end
function verifyPackage(root,m)
assert(isstruct(m.files)&&numel(unique({m.files.path}))==numel(m.files));
for k=1:numel(m.files)
 item=m.files(k);p=relativeFile(root,item.path);info=System.IO.FileInfo(p);
 assert(info.Exists&&double(info.Length)==item.bytes&&strcmp(sha256(p),item.sha256),'adapter:SourceBytes','Package bytes mismatch.');
end
actual=listFiles(root,'');expected=[{m.files.path},{'PACKAGE_MANIFEST.json'}];
assert(isequal(sort(actual),sort(expected)),'adapter:PackageCensus','Unexpected or missing package file.');
end
function result=verifyResolution(root,s)
result=struct('schema','csr-component-resolution-v1','symbols',s.effective_symbols);
for k=1:numel(s.effective_symbols)
 item=s.effective_symbols(k);expected=relativeFile(root,item.path);actual=which(item.symbol);
 assert(~isempty(actual)&&strcmpi(char(System.IO.Path.GetFullPath(actual)),expected)&& ...
   strcmp(sha256(actual),item.sha256),'adapter:Resolution','Unexpected source resolution: %s',item.symbol);
end
end
function p=relativeFile(root,rel)
assert(ischar(rel)&&~isempty(regexp(rel,'^[A-Za-z0-9_+./-]+$','once'))&& ...
 ~startsWith(rel,'/')&&~contains(rel,'//')&&~any(ismember(strsplit(rel,'/'),{'.','..',''})), ...
 'adapter:RelativePath','Invalid relative package path.');
p=char(System.IO.Path.GetFullPath(fullfile(root,strrep(rel,'/',filesep))));
assert(isWithin(p,root),'adapter:Containment','Path escaped root.');assertPlainPath(p);
end
function value=isWithin(p,root)
value=strcmpi(p,root)||startsWith(lower(p),[lower(root) filesep]);
end
function assertPlainPath(p)
p=char(System.IO.Path.GetFullPath(p));
while ~isempty(p)
 assert(System.IO.File.Exists(p)||System.IO.Directory.Exists(p),'adapter:PathMissing','Required path is absent.');
 attrs=System.IO.File.GetAttributes(p);
 assert(bitand(uint32(System.Convert.ToInt32(attrs)),uint32(1024))==0,'adapter:ReparsePoint','Reparse paths are not allowed.');
 parent=char(System.IO.Path.GetDirectoryName(p));if strcmp(parent,p),break;end;p=parent;
end
end
function paths=listFiles(root,rel)
paths={};entries=dir(fullfile(root,strrep(rel,'/',filesep)));
for k=1:numel(entries)
 e=entries(k);if any(strcmp(e.name,{'.','..'})),continue;end
 name=e.name;if ~isempty(rel),name=[rel '/' name];end
 p=relativeFile(root,name);
 if e.isdir,paths=[paths listFiles(root,name)];else,paths{end+1}=name;end %#ok<AGROW>
end
end
function checkOutputs(root,cap)
allowed={'preflight/random_requests.digest.json','preflight/synthetic.digest.json', ...
 'preflight/synthetic.jsonl','COMPONENT.json','SOURCE_RESOLUTION.json','ADAPTER_RESULT.json'};
limits=[2048 2048 512 16*1024^2 256*1024 128*1024];
entries=dir(root);dirs=entries([entries.isdir]);names=setdiff({dirs.name},{'.','..'});
assert(all(strcmp(names,'preflight')),'adapter:OutputDirectory','Unexpected output directory.');
if isfolder(fullfile(root,'preflight'))
 entries=dir(fullfile(root,'preflight'));sub=entries([entries.isdir]);
 assert(isempty(setdiff({sub.name},{'.','..'})),'adapter:OutputDirectory','Unexpected nested directory.');
end
files=listFiles(root,'');charged=0;
for k=1:numel(files)
 index=find(strcmp(allowed,files{k}));assert(isscalar(index),'adapter:OutputAllowlist','Unexpected output file.');
 info=System.IO.FileInfo(relativeFile(root,files{k}));n=double(info.Length);
 assert(n<=limits(index),'adapter:FileCap','File exceeds its declared cap.');
 charged=charged+4096*ceil(n/4096);
end
assert(charged<=cap,'adapter:OutputCap','Output reservation estimate exceeds plan.');
end
function writeJsonNew(p,value,cap)
bytes=uint8(unicode2native([jsonencode(value) newline],'UTF-8'));
assert(numel(bytes)<=cap,'adapter:ReportCap','Report cap exceeded.');
f=System.IO.FileStream(p,System.IO.FileMode.CreateNew,System.IO.FileAccess.Write,System.IO.FileShare.Read);
c=onCleanup(@()f.Dispose()); %#ok<NASGU>
f.Write(bytes,0,numel(bytes));f.Flush(true);
end
function value=sha256(p)
fid=fopen(p,'rb');assert(fid>=0,'adapter:Read','Cannot read bound file.');
c=onCleanup(@()fclose(fid)); %#ok<NASGU>
md=java.security.MessageDigest.getInstance('SHA-256');
while true,b=fread(fid,1048576,'*uint8');if isempty(b),break;end;md.update(typecast(b,'int8'));end
value=lower(reshape(dec2hex(typecast(md.digest(),'uint8'),2).',1,[]));
end
