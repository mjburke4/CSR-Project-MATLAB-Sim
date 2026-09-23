function [cases,plan] = tranche16Suite()
%TRANCHE16SUITE Six unchanged full-PHY workloads for paired transport timing.
% The caller runs each Config under both declared receiver timing policies.
% Numeric seeds do not align the independent MATLAB and native RNG streams.
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
plan=jsondecode(fileread(fullfile(root,'scenarios','t16','plan.json')));
keys={'a128','c128','a129','c129','a130','c130'};
pin='486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b';
if ~strcmp(plan.schema,'csr-tranche16-network-plan-v1') || ...
        ~strcmp(plan.ns3_source_commit,pin) || plan.case_count~=6 || ...
        plan.paired_run_count~=12 || plan.paired_simulated_seconds~=9360 || ...
        ~isequal(plan.seeds(:)',[128 129 130]) || ...
        ~isequal(plan.case_order(:)',keys) || ...
        ~isequal(plan.policies(:)',{'continuous','nanoseconds'}) || ...
        ~isequal(plan.policy_keys(:)',{'c','n'}) || ...
        plan.stimuli_changed || plan.new_native_execution || plan.opnet_available || ...
        plan.phy_ecc_changed || plan.global_scheduler_quantized || plan.default_policy_changed
    error('csr:t16:Plan','Unexpected Tranche 16 source, workloads or policy scope.');
end
checkBindings(root,plan.source_files);
checkBindings(root,plan.reference_files);
[original,oldPlan]=csr.scenario.linkDiagnosticSuite();
selected=find(ismember([original.Seed],plan.seeds));
cases=original(selected);
entries=plan.cases;
if iscell(entries), entries=vertcat(entries{:}); end
if numel(cases)~=6 || numel(entries)~=6
    error('csr:t16:Plan','Expected the complete two-fixture, three-seed subset.');
end
oldEntries=oldPlan.cases;
if iscell(oldEntries), oldEntries=vertcat(oldEntries{:}); end
referenceRoot=fullfile(root,'evidence','tranche-8-ns3-reference');
suite=jsondecode(fileread(fullfile(referenceRoot,'manifest.json')));
if ~strcmp(suite.schema,'csr-tranche8-link-diagnostic-reference-suite-v1') || ...
        ~strcmp(suite.status,'completed') || ~strcmp(suite.ns3_source_commit,pin) || ...
        ~suite.source_files_stable || ~suite.input_files_stable || ...
        ~suite.all_observer_on_off_checks_passed || numel(suite.cases)~=10
    error('csr:t16:Reference','Archived native suite identity or observer control failed.');
end
for k=1:6
    item=entries(k); source=cases(k);
    expectedSeed=128+floor((k-1)/2);
    expectedBase={'two_node_admission_1200','three_node_contention_360'};
    base=expectedBase{1+mod(k-1,2)};
    if ~strcmp(item.case_id,keys{k}) || ~strcmp(item.storage_key,keys{k}) || ...
            ~strcmp(item.native_case_id,source.CaseId) || ...
            ~strcmp(item.base_case_id,base) || item.seed~=expectedSeed || ...
            item.max_events~=12000000 || source.Config.MaxEvents~=12000000
        error('csr:t16:Plan','The workload order, seed or execution budget changed.');
    end
    retained=rmfield(item,{'native_case_id','storage_key','max_events'});
    retained.case_id=item.native_case_id;
    if ~isequal(orderfields(retained),orderfields(oldEntries(selected(k))))
        error('csr:t16:Stimuli','A retained workload input or trace budget changed.');
    end
    index=find(strcmp({suite.cases.case_id},source.CaseId));
    if numel(index)~=1
        error('csr:t16:Reference','Missing or duplicate archived native workload.');
    end
    entry=suite.cases(index);
    manifestPath=fullfile(referenceRoot,entry.manifest);
    if ~strcmp(csr.validation.Artifacts.sha256(manifestPath),entry.manifest_sha256)
        error('csr:t16:Reference','The archived native case manifest changed.');
    end
    manifest=jsondecode(fileread(manifestPath));
    if ~strcmp(manifest.status,'completed') || ~manifest.tranche8_diagnostics || ...
            ~strcmp(manifest.ns3_source_commit,pin) || ...
            ~isequal(orderfields(manifest.case),orderfields(retained)) || ...
            ~strcmp(manifest.nonperturbation.status,'passed') || ...
            ~manifest.nonperturbation.closed_artifacts_reverified
        error('csr:t16:Reference','Native execution, stimulus or observer identity failed.');
    end
    cases(k).NativeCaseId=source.CaseId;
    cases(k).CaseId=keys{k};
    cases(k).StorageKey=keys{k};
end
if 2*sum([cases.DurationSeconds])~=plan.paired_simulated_seconds
    error('csr:t16:Plan','The original complete simulation horizons changed.');
end
end

function checkBindings(root,files)
if isempty(files) || numel(unique({files.path}))~=numel(files)
    error('csr:t16:Binding','Missing or duplicate source/reference bindings.');
end
canonicalRoot=csr.validation.Artifacts.canonicalPath(root);
for k=1:numel(files)
    item=files(k);
    path=csr.validation.Artifacts.canonicalPath(fullfile(root,item.path));
    if ~startsWith(path,[canonicalRoot filesep]) || ~isfile(path) || ...
            ~strcmp(csr.validation.Artifacts.sha256(path),item.sha256)
        error('csr:t16:Binding','A retained source or reference artifact changed: %s.',item.path);
    end
    info=dir(path);
    if info.bytes~=item.bytes
        error('csr:t16:Binding','A retained artifact size changed: %s.',item.path);
    end
end
end
