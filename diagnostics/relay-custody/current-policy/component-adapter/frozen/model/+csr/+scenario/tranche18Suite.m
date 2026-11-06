function [cases,plan] = tranche18Suite()
%TRANCHE18SUITE Real-PHY relay/local isolation and an original campus prefix.
% Ten observed workloads; the runner adds one identical observer-off control.
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
planPath=fullfile(root,'scenarios','t18','plan.json');
plan=jsondecode(fileread(planPath));
keys={'r128','l128','m128','r129','l129','m129','r130','l130','m130','p128'};
execution={'r128','l128','m128','m128_off','r129','l129','m129','r130','l130','m130','p128'};
pin='486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b';
if ~strcmp(plan.schema,'csr-tranche18-relay-service-plan-v1') || ...
        ~strcmp(plan.ns3_source_commit,pin) || plan.case_count~=10 || plan.execution_count~=11 || ...
        plan.planned_simulated_seconds~=6900 || ~isequal(plan.seeds(:)',[128 129 130]) || ...
        ~isequal(plan.case_order(:)',keys) || ~isequal(plan.execution_order(:)',execution) || ...
        ~strcmp(plan.timing_policy,'continuous') || plan.phy_ecc_changed || ...
        plan.default_policy_changed || plan.production_source_changed || plan.post_horizon_drain
    error('csr:t18:Plan','Unexpected Tranche 18 workloads, order or protocol scope.');
end
entries=plan.cases;
if iscell(entries), entries=vertcat(entries{:}); end
if numel(entries)~=10 || ~isequal({entries.case_id},keys)
    error('csr:t18:Plan','All ten distinct observed workloads are required in the frozen order.');
end
[parent,~]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
parentConfig=parent.Config;
template=struct('CaseId','','StorageKey','','Condition','','Scenario','', ...
    'ScenarioFile','','ScenarioSHA256','','ProfileId','','DurationSeconds',0,'Seed',0, ...
    'BucketWidthSeconds',0,'SourceKind','','OpnetAvailable',false,'ReferenceDirectory','', ...
    'ObserverEnabled',true,'ObserverMaxRecords',0,'ServiceWindowSeconds',[0 0], ...
    'Config',struct(),'PlanEntry',struct());
cases=repmat(template,10,1);
for k=1:10
    entry=entries(k);
    if k<10
        conditions={'relay_only','local_only','mixed'};
        flowSets={4,5,[4 5]};
        condition=conditions{1+mod(k-1,3)};
        sources=flowSets{1+mod(k-1,3)}; nodes=[1 4 5];
        seed=128+floor((k-1)/3); duration=600; maximum=100000;
        limits=struct('protocol',300000,'phy',500000,'admission',50000);
    else
        condition='campus_prefix'; sources=[2 3 4 5 7 8]; nodes=[1 2 3 4 5 7 8];
        seed=128; duration=900; maximum=400000;
        limits=struct('protocol',1500000,'phy',1500000,'admission',300000);
    end
    if ~strcmp(entry.storage_key,keys{k}) || ~strcmp(entry.condition,condition) || ...
            entry.seed~=seed || entry.duration_s~=duration || entry.flow_limit~=0 || ...
            ~isequal(entry.flow_sources(:)',sources) || ~isequal(entry.node_ids(:)',nodes) || ...
            entry.observer_max_records~=maximum || ~isequal(entry.observer_enabled,true) || ...
            ~isequal(entry.service_window_seconds(:)',[0 duration+1]) || ...
            entry.max_events~=12000000 || entry.opnet_available || ...
            ~isequal(orderfields(entry.trace_limits),orderfields(limits)) || ...
            ~strcmp(entry.profile_id,parent.ProfileId)
        error('csr:t18:Plan','A workload condition, seed, horizon or observation budget changed.');
    end
    % Match the shipped case paths exactly, including the .recipe.json suffix.
    if ~strcmp(entry.scenario_file,['scenarios/t18/inputs/' keys{k} '.csv']) || ...
            ~strcmp(entry.recipe_file,['scenarios/t18/inputs/' keys{k} '.recipe.json']) || ...
            ~strcmp(entry.reference_directory,['evidence/tranche-18-ns3-reference/' keys{k}])
        error('csr:t18:Path','Scenario, recipe and reference paths must be canonical.');
    end
    input=csr.validation.ReleaseCheckpoint.checkedPath(root,entry.scenario_file);
    recipe=csr.validation.ReleaseCheckpoint.checkedPath(root,entry.recipe_file);
    if ~strcmp(csr.validation.Artifacts.sha256(input),entry.scenario_sha256) || ...
            ~strcmp(csr.validation.Artifacts.sha256(recipe),entry.recipe_sha256)
        error('csr:t18:InputChanged','A canonical scenario or derivation recipe changed.');
    end
    config=csr.scenario.importNs3(input, ...
        struct('HistoricalBenchmark',true,'FlowLimit',0,'Backend','portable'));
    if ~strcmp(config.Name,entry.scenario) || config.Seed~=seed || ...
            config.DurationSeconds~=duration || ~strcmp(config.SharedScenario.HopSecurityProfile,parent.ProfileId)
        error('csr:t18:Scenario','Imported configuration differs from the frozen case.');
    end
    % The entire retained radio/protocol configuration is inherited, including
    % geometry, autonomous routing, zero-DSCP historical traffic and real PHY.
    expectedNodes=parentConfig.Nodes(ismember([parentConfig.Nodes.Id],nodes));
    expectedFlows=parentConfig.Traffic(ismember([parentConfig.Traffic.SourceId],sources));
    for j=1:numel(expectedFlows)
        f=expectedFlows(j);
        expectedFlows(j).PacketCount=max(0,floor((round(duration*1e9)-1- ...
            round(f.StartSeconds*1e9))/round(f.IntervalSeconds*1e9))+1);
    end
    if ~isequaln(config.Nodes,expectedNodes) || ~isequaln(config.Traffic,expectedFlows)
        error('csr:t18:Scenario','Node geometry/radio or offered traffic differs from the retained campus inputs.');
    end
    excluded={'Name','DurationSeconds','Seed','Nodes','Traffic','Trace','MaxEvents','SharedScenario','Benchmark'};
    left=rmfield(config,intersect(fieldnames(config),excluded));
    right=rmfield(parentConfig,intersect(fieldnames(parentConfig),excluded));
    if ~isequaln(orderfields(left),orderfields(right))
        error('csr:t18:Scenario','A protocol, PHY or routing configuration changed.');
    end
    config.Trace.MaxRecords=limits.protocol;
    config.Trace.MaxPhyRecords=limits.phy;
    config.Trace.MaxApplicationAdmissionRecords=limits.admission;
    config.MaxEvents=12000000;
    config.Benchmark=struct('Schema','csr-matlab-benchmark-v1', ...
        'CaseId',entry.case_id,'SourceKind',entry.source_kind,'ProfileId',entry.profile_id, ...
        'OpnetAvailable',false,'BucketWidthSeconds',entry.bucket_width_s, ...
        'ReferenceDirectory',entry.reference_directory, ...
        'CatalogSHA256',csr.validation.Artifacts.sha256(planPath), ...
        'HistoricalOutcomeEquivalenceEstablished',false);
    config=csr.scenario.validate(config);
    validateattributes(entry.bucket_width_s,{'numeric'},{'scalar','real','finite','positive'});
    if abs(duration/entry.bucket_width_s-round(duration/entry.bucket_width_s))>1e-10
        error('csr:t18:Plan','Aggregate buckets must partition each complete diagnostic horizon.');
    end
    cases(k)=struct('CaseId',entry.case_id,'StorageKey',entry.storage_key, ...
        'Condition',condition,'Scenario',entry.scenario,'ScenarioFile',entry.scenario_file, ...
        'ScenarioSHA256',entry.scenario_sha256,'ProfileId',entry.profile_id, ...
        'DurationSeconds',duration,'Seed',seed,'BucketWidthSeconds',entry.bucket_width_s, ...
        'SourceKind',entry.source_kind,'OpnetAvailable',false, ...
        'ReferenceDirectory',entry.reference_directory,'ObserverEnabled',true, ...
        'ObserverMaxRecords',maximum,'ServiceWindowSeconds',[0 duration+1], ...
        'Config',config,'PlanEntry',entry);
end
end
