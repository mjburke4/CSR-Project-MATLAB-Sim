function report = preflight_current_policy(config,outputRoot,check)
% Constructor/writer qualification only. Caller owns all paths and safeguards.
% check() must throw on deadline, ownership, or output-cap failure. It is
% invoked before/after bounded stages; it is not an asynchronous watchdog.
% A fresh engine must have the verified final overlay installed before entry.
assert(isa(check,'function_handle')&&isscalar(check),'adapter:Check','Required check() callback.');
check();
assert(ispc,'adapter:Platform','Exact DiagnosticByteBudget requires Windows .NET.');
release=version('-release'); runtime=version;
assert(strcmp(release,'2026a')&&~isempty(regexp(runtime,'Update\s*5\>','once')), ...
    'adapter:Release','This candidate requires MATLAB R2026a Update 5.');
assert(ischar(outputRoot)&&isrow(outputRoot),'adapter:Root','Explicit directory required.');
assert(isempty(ac.Trace.holder()),'adapter:TraceSink','Fresh engine must have no active trace sink.');
plan=current_policy_preflight_plan();
pool=DiagnosticByteBudget(outputRoot,plan.CapacityBytes,plan.ExistingChargedBytes,plan.ClusterBytes);
root=pool.Root;
assert(numel(System.IO.Directory.GetFileSystemEntries(root))==0,'adapter:NotEmpty','Preflight root must be empty.');
originalConfig=config; rngBefore=rng;
normalized=csr.scenario.validate(config,'ac.DiscoveryMembershipNwk');
assert(isequaln(config,normalized),'adapter:ConfigurationNormalizationRequired', ...
    'Input is not already normalized. No scientific configuration changes were applied.');
assert(strcmp(config.Backend,'portable'),'adapter:Backend','No native backend is permitted.');
assert(strcmp(config.Nwk.AdmissionPolicy,'opnet-reference'),'adapter:Policy','Current-policy input required.');
policy=policyChecks(config); check();
q=plan.Random;q.Pool=pool;
options=struct('Mode','natural','Fixture','','Folder',root, ...
    'WriterPool',pool,'RandomWriterPlan',q,'RandomLogByteLimit',q.PayloadBytes);
assert(isequal(options.WriterPool,options.RandomWriterPlan.Pool) && ...
    options.RandomLogByteLimit==options.RandomWriterPlan.PayloadBytes,'adapter:PlanMatch','Writer plan mismatch.');
% Exercise the exact early mismatch guard, before any FeedbackStreams writer.
bad=options;bad.RandomLogByteLimit=q.PayloadBytes+1;
expectError(@()ac.TerminalSimulation(config,[],[],bad),'diagnostic2490:SharedBudget');
assert(numel(System.IO.Directory.GetFileSystemEntries(root))==0,'adapter:UnexpectedWrite','Guard created a file.');
observer=CompactObserver(config.DurationSeconds);
timing=csr.sim.TransportTiming(plan.TransportMode,plan.TransportMaxRecords);
check();
simulation=ac.TerminalSimulation(config,observer,timing,options);
cleanupSimulation=onCleanup(@()simulation.autonomousClose()); %#ok<NASGU>
check();
assertQuiet(simulation,observer,timing);
assert(isequaln(simulation.Config,originalConfig),'adapter:ConfigChanged','Constructor changed normalized config.');
before=readObservers(simulation);after=readObservers(simulation);
assert(isequaln(before,after),'adapter:ReadOnly','Observer snapshots changed between reads.');
simulation.autonomousClose();
assertQuiet(simulation,observer,timing);
receiptPath=fullfile(root,'random_requests.digest.json');
receiptInfo=System.IO.FileInfo(receiptPath);
assert(double(receiptInfo.Length)<=plan.Random.PayloadBytes);
receipt=jsondecode(native2unicode(reshape(uint8(System.IO.File.ReadAllBytes(receiptPath)),1,[]),'UTF-8'));
assert(receipt.Closed&&receipt.CompleteRecords&&~receipt.Faulted&&receipt.Records==0&&receipt.RawBytes==0);
random=simulation.autonomousRandomSummary();
assert(random.draw_count==0&&random.native_transmissions_checked==0,'adapter:ModelWork','Unexpected model work.');
check();
% These synthetic records are unrelated to model inputs or distributions.
record=struct('kind','preflight','value',1);
q=plan.SyntheticDigest;
digest=CompactJsonlDigestWriter(fullfile(root,'synthetic.digest.json'),pool, ...
    q.PayloadBytes,q.FooterBytes,q.TemporaryBytes,q.RecordLimits);
cleanupDigest=onCleanup(@()digest.close()); %#ok<NASGU>
encoded=BoundedJsonlWriter.encodeBounded(record,q.RecordLimits);
assert(digest.write(record)==numel(encoded));digest.close();
summary=digest.summary();
assert(summary.Closed&&summary.CompleteRecords&&~summary.Faulted&&summary.Records==1);
q=plan.SyntheticJsonl;
writer=BoundedJsonlWriter(fullfile(root,'synthetic.jsonl'),pool, ...
    q.PayloadBytes,q.FooterBytes,q.TemporaryBytes,q.RecordLimits);
cleanupWriter=onCleanup(@()writer.close()); %#ok<NASGU>
assert(writer.write(record)==numel(encoded));writer.close();
assert(writer.Closed&&writer.Bytes==numel(encoded)&&writer.FooterBytes==0&&writer.TemporaryBytes==0);
assert(isequal(reshape(uint8(System.IO.File.ReadAllBytes(fullfile(root,'synthetic.jsonl'))),1,[]),encoded), ...
    'adapter:ExactBytes','Synthetic JSONL bytes differ from exact encoder.');
assert(pool.Charged==plan.CapacityBytes,'adapter:Reservation','Reservation census mismatch.');
files=dir(root);files=files(~ismember({files.name},{'.','..'}));
assert(~any([files.isdir])&&isequal(sort({files.name}),sort(plan.ExpectedCreatedFiles)), ...
    'adapter:UnexpectedFiles','Created files do not match plan.');
for k=1:numel(files)
    claim=find(strcmp({plan.Claims.Path},files(k).name));
    assert(isscalar(claim)&&files(k).bytes<=plan.Claims(claim).PayloadBytes,'adapter:FileCap','File exceeds plan.');
end
rngAfter=rng;
assert(isequaln(rngBefore,rngAfter),'adapter:GlobalRngChanged','Global RNG changed; it was not silently restored.');
assert(isequaln(config,originalConfig),'adapter:ConfigChanged','Input changed.');
check();
report=struct('Schema','csr-current-policy-preflight-v1','Passed',true, ...
    'Release',release,'Runtime',runtime,'Scope','constructor-and-tiny-writers-only', ...
    'SimulationRunCalled',false,'SchedulerRunCalled',false,'DistributionDraws',0, ...
    'GlobalRngUnchanged',true,'ScientificConfigUnchanged',true, ...
    'SchedulerNow',simulation.Scheduler.Now,'PendingCount',simulation.Scheduler.PendingCount, ...
    'PolicyChecks',policy,'WriterPlan',plan,'ReservedBytes',pool.Charged, ...
    'CreatedFiles',{plan.ExpectedCreatedFiles},'ActualBytes',[files.bytes], ...
    'ActualFileOrder',{{files.name}},'RandomSummary',random,'SyntheticDigest',summary);
end

function assertQuiet(s,o,t)
assert(s.Scheduler.Now==0&&s.Scheduler.PendingCount==0,'adapter:SchedulerWork','Constructor/close advanced scheduler.');
r=s.autonomousRandomSummary();assert(r.draw_count==0,'adapter:Draw','Unexpected random draw.');
p=s.autonomousPartial(false);v=struct2cell(p.Statistics);
assert(all(cellfun(@(x)isnumeric(x)&&isscalar(x)&&x==0,v)),'adapter:ModelWork','Nonzero model counter.');
assert(o.Admissions==0&&isempty(o.Pending)&&all(structfun(@(x)x==0,o.Counts))&&t.Count==0, ...
    'adapter:ObserverWork','Unexpected observer callbacks.');
end

function result=readObservers(s)
result=cell(numel(s.Hops),2);
for k=1:numel(s.Hops)
    assert(isscalar(s.Hops{k})&&isscalar(s.Networks{k}));
    result{k,1}=s.Hops{k}.fixtureReadOnly();result{k,2}=s.Networks{k}.fixtureReadOnly();
    assert(isscalar(result{k,1})&&isscalar(result{k,2}));
end
end

function result=policyChecks(config)
defaults=csr.nwk.defaults();assert(strcmp(defaults.AdmissionPolicy,'portable-bounded'));
assert(strcmp(csr.nwk.validateAdmissionPolicy(struct()),'portable-bounded'));
ref=struct('AdmissionPolicy','opnet-reference');
assert(strcmp(csr.nwk.validateAdmissionPolicy(ref,'ac.DiscoveryMembershipNwk'),'opnet-reference'));
expectError(@()csr.nwk.validateAdmissionPolicy(ref),'csr:nwk:UnsupportedAdmissionPolicy');
expectError(@()csr.nwk.validateAdmissionPolicy(ref,'csr.nwk.Layer'),'csr:nwk:UnsupportedAdmissionPolicy');
expectError(@()csr.nwk.validateAdmissionPolicy(struct('AdmissionPolicy','unknown')), 'csr:nwk:InvalidConfig');
expectError(@()csr.scenario.validate(config),'csr:nwk:UnsupportedAdmissionPolicy');
expectError(@()csr.scenario.validate(config,'unknown'),'csr:scenario:NwkImplementation');
result=struct('PortableDefaultRetained',true,'ReferenceRequiresDiscoveryMembership',true, ...
    'UnsupportedImplementationRejected',true,'UnknownPolicyRejected',true);
end

function expectError(callback,identifier)
try
    callback();
catch err
    assert(strcmp(err.identifier,identifier),'adapter:WrongError','Expected %s; received %s.',identifier,err.identifier);
    return
end
error('adapter:MissingError','Expected %s.',identifier);
end
