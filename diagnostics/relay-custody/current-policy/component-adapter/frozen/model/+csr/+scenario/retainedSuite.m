function [cases,plan] = retainedSuite()
%RETAINEDSUITE The earlier 28 portable scenarios and default foundation case.
% Reuse the original factories, catalog order and complete configurations.
% Short storage keys describe evidence paths only, never scenario identity.
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
fixed=jsondecode(fileread(fullfile(root,'scenarios','contention_timing','plan.json')));
if ~strcmp(fixed.schema,'csr-contention-timing-plan-v1') || fixed.retained_case_count~=29
    error('csr:timing:RetainedPlan','Expected the fixed 29-case retained plan.');
end
template=struct('CaseId','','Kind','','Name','','StorageKey','','Factory','', ...
    'Fixture','','ScenarioFile','','ScenarioSHA256','','Config',struct());
cases=repmat(template,0,1);
append('foundation','default','csr.scenario.smallNetwork','',csr.scenario.smallNetwork(),'');
names={'reliable','ack_loss','data_loss','dack','collision','relay', ...
    'queue_pressure','high_rate_500','high_rate_1000'};
for k=1:numel(names)
    append('mac_hop',names{k},'csr.scenario.macHopNetwork',names{k}, ...
        csr.scenario.macHopNetwork(names{k}),'');
end
names={'autonomous','no_route_custody','control_loss','route_recovery', ...
    'gateway','leaf_no_transit','high_rate_500','high_rate_1000'};
for k=1:numel(names)
    append('routed',names{k},'csr.scenario.routedNetwork',names{k}, ...
        csr.scenario.routedNetwork(names{k}),'');
end
catalogPath=fullfile(root,'scenarios','shared','catalog.json');
catalog=jsondecode(fileread(catalogPath));
if ~strcmp(catalog.schema,'csr-matlab-shared-scenario-catalog-v1') || numel(catalog.cases)~=5
    error('csr:timing:RetainedPlan','Expected the retained five-case shared catalog.');
end
for k=1:numel(catalog.cases)
    entry=catalog.cases(k); input=['scenarios/shared/' entry.path];
    config=csr.scenario.importNs3(fullfile(root,input),struct('FlowLimit',entry.flow_limit));
    append('shared',entry.name,'csr.scenario.importNs3',entry.name,config,input);
end
names={'two_node','line_4','hidden_node','mesh_6','route_recovery','leaf_no_transit'};
for k=1:numel(names)
    append('research',[names{k} '_seed_128'],'csr.scenario.researchNetwork',names{k}, ...
        csr.scenario.researchNetwork(names{k},struct('Seed',128)),'');
end
if numel(cases)~=29 || numel(fixed.retained_cases)~=29
    error('csr:timing:RetainedPlan','Retained case membership changed.');
end
for k=1:numel(cases)
    item=cases(k); declared=fixed.retained_cases(k);
    actual=struct('case_id',item.CaseId,'kind',item.Kind,'name',item.Name, ...
        'storage_key',item.StorageKey,'factory',item.Factory, ...
        'fixture',item.Fixture,'scenario_file',item.ScenarioFile);
    if ~isequal(orderfields(actual),orderfields(declared))
        error('csr:timing:RetainedPlan','Retained identity, factory or storage mapping changed.');
    end
end
plan=struct('Schema','csr-matlab-retained-plan-v1','Status','planned-not-executed', ...
    'CaseCount',numel(cases),'SourceCommit',fixed.ns3_source_commit, ...
    'TotalSimulatedSeconds',sum(arrayfun(@(x)x.Config.DurationSeconds,cases)), ...
    'Cases',rmfield(cases,'Config'), ...
    'Scope','The default foundation case, nine MAC/HOP, eight routed, five shared and six research cases; original factories and settings.', ...
    'ConfigurationsChanged',false,'NumericalParityEstablished',false);

    function append(kind,name,factory,fixture,config,input)
        key=sprintf('%02d',numel(cases)+1); digest='';
        if ~isempty(input), digest=csr.validation.Artifacts.sha256(fullfile(root,input)); end
        cases(end+1,1)=struct('CaseId',[kind '_' name],'Kind',kind,'Name',name, ...
            'StorageKey',key,'Factory',factory,'Fixture',fixture, ...
            'ScenarioFile',input,'ScenarioSHA256',digest,'Config',config);
    end
end
