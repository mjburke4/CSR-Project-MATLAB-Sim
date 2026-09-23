function [cases,plan] = ackServiceSuite()
%ACKSERVICESUITE Six accepted stimuli with focused service observations.
% Reuse the accepted CSVs and complete configurations without another derivation.
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
path=fullfile(root,'scenarios','ack_service','plan.json');
plan=jsondecode(fileread(path));
keys={'c129','c128','c130','c131','c132','a129'};
if ~strcmp(plan.schema,'csr-ack-service-plan-v1') || ...
        ~strcmp(plan.matlab_base_commit,'d0f3c5657f9f2dcf678f32900020caf3696bf90a') || ...
        ~strcmp(plan.accepted_tranche8_matlab_commit,'89b62e729e588f396bb919afdff522f7e9419268') || ...
        ~strcmp(plan.ns3_source_commit,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b') || ...
        plan.case_count~=6 || ~isequal(plan.case_order(:)',keys) || ...
        ~isequal(plan.control_keys(:)',{'c129','a129'}) || ...
        ~isequal(plan.service_window_s(:)',[300 320]) || ...
        ~plan.service_window_end_exclusive || plan.service_max_records~=100000 || ...
        plan.feedback_max_records~=100000 || plan.stimuli_changed || plan.opnet_available
    error('csr:service:Plan','Unexpected source, case membership or observation scope.');
end
if ~strcmp(plan.parent_plan,'scenarios/link_diagnostics/plan.json') || ...
        ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,plan.parent_plan)),plan.parent_plan_sha256)
    error('csr:service:Parent','Accepted diagnostic plan changed.');
end
[parents,parentPlan]=csr.scenario.linkDiagnosticSuite();
entries=plan.cases; if iscell(entries), entries=vertcat(entries{:}); end
parentEntries=parentPlan.cases;
if iscell(parentEntries), parentEntries=vertcat(parentEntries{:}); end
if numel(entries)~=6, error('csr:service:Plan','Expected six diagnostic cases.'); end
selected=zeros(1,6);
for k=1:6
    item=entries(k);
    base='three_node_contention_360';
    if keys{k}(1)=='a', base='two_node_admission_1200'; end
    expectedId=sprintf('%s_s%s',base,keys{k}(2:end));
    if ~strcmp(item.storage_key,keys{k}) || ~strcmp(item.case_id,expectedId) || ...
            ~strcmp(item.service_reference_directory,['evidence/tranche-9-ns3-reference/' keys{k}])
        error('csr:service:Plan','Case storage mapping differs from fixed short paths.');
    end
    index=find(strcmp({parents.CaseId},item.case_id));
    if numel(index)~=1, error('csr:service:Plan','Missing or duplicate accepted stimulus.'); end
    original=rmfield(item,{'storage_key','service_reference_directory'});
    if ~isequal(orderfields(original),orderfields(parentEntries(index)))
        error('csr:service:Parent','Service case changed an accepted stimulus or reference.');
    end
    selected(k)=index;
end
if numel(unique(selected))~=6, error('csr:service:Plan','Duplicate stimulus.'); end
cases=parents(selected);
for k=1:6
    cases(k).StorageKey=keys{k};
    cases(k).ServiceReferenceDirectory=entries(k).service_reference_directory;
end
anchor=plan.baseline_anchor;
if ~strcmp(anchor.archive,'evidence/tranche-8-r2025a-accepted/tranche8_evidence.zip') || ...
        ~strcmp(anchor.archive_sha256,'bfc4f7f05f0800316b371df3ec316f309f14e3482ef259c3f9c7bd7eea025d77') || ...
        ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,anchor.archive)),anchor.archive_sha256)
    error('csr:service:Anchor','Accepted Tranche 8 return archive changed.');
end
end
