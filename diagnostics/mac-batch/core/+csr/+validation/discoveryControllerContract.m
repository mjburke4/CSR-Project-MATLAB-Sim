function report = discoveryControllerContract(outputDirectory,root)
%DISCOVERYCONTROLLERCONTRACT Run five bounded controller executions.
% Native differences are reported separately from fixture completion. This
% diagnostic neither changes the simulator nor establishes campus causality.
if nargin<1, outputDirectory=''; end
if nargin<2, root=fileparts(fileparts(fileparts(mfilename('fullpath')))); end
planPath=fullfile(root,'evidence','tranche-27-plan.json');
plan=jsondecode(fileread(planPath));
expected={'C0','C1','C2','C3_match','C3_timeout'};
if ~strcmp(plan.schema,'csr-tranche27-controller-plan-v1') || ...
        plan.fixture_count~=4 || plan.execution_count~=5 || ...
        ~isequal(reshape({plan.cases.id},1,[]),expected)
    error('csr:t27:Plan','The frozen plan must contain the five ordered T27 executions.');
end
if ~isempty(outputDirectory) && ~isfolder(outputDirectory), mkdir(outputDirectory); end
cases=repmat(struct('CaseId','','DiagnosticCompleted',false,'StructuralPassed',false, ...
    'ControlCount',0,'CheckpointCount',0),0,1);
comparisons=repmat(struct('CaseId','','MatchesNative',false,'MatlabControlCount',0, ...
    'NativeControlCount',0,'DifferingRows',0),0,1);
report=struct('Schema','csr-tranche27-matlab-controller-contract-v1', ...
    'DiagnosticCompleted',false,'StructuralPassed',false,'CrossEngineMatchesNative',false, ...
    'FixtureCount',4,'CaseCount',0,'ControlCount',0,'CheckpointCount',0, ...
    'DifferingCaseCount',0,'DifferingControlRows',0,'Comparison',comparisons, ...
    'Cases',cases,'PrivateControllerStateAvailable',false, ...
    'PlanSHA256',csr.validation.Artifacts.sha256(planPath), ...
    'CrossEngineComparisonScope','ordered_logical_SNMP_controls', ...
    'ComparisonScope',['Logical SNMP control order, addresses, ACK ownership, send acceptance ' ...
        'and advertised nodes; time tolerance 1e-9 seconds.'], ...
    'Scope','Deterministic controller boundary; no PHY, campus, stochastic parity claim or production change');
for index=1:numel(plan.cases)
    config=plan.cases(index);
    directory='';
    if ~isempty(outputDirectory), directory=fullfile(outputDirectory,'cases',config.id); end
    observed=csr.validation.discoveryControllerCase(config,directory);
    comparison=compareNative(observed.Controls, ...
        fullfile(root,'evidence','tranche-27-native-reference','cases',config.id,'controls.csv'), ...
        config.id);
    cases(end+1,1)=struct('CaseId',config.id,'DiagnosticCompleted',observed.DiagnosticCompleted, ...
        'StructuralPassed',observed.StructuralPassed,'ControlCount',observed.ControlCount, ...
        'CheckpointCount',observed.CheckpointCount); %#ok<AGROW>
    comparisons(end+1,1)=comparison; %#ok<AGROW>
    report.Cases=cases; report.Comparison=comparisons;
    report.CaseCount=numel(cases); report.ControlCount=sum([cases.ControlCount]);
    report.CheckpointCount=sum([cases.CheckpointCount]);
    report.DifferingCaseCount=sum(~[comparisons.MatchesNative]);
    report.DifferingControlRows=sum([comparisons.DifferingRows]);
    report.CrossEngineMatchesNative=all([comparisons.MatchesNative]);
    writeSummary();
end
report.DiagnosticCompleted=numel(cases)==5 && all([cases.DiagnosticCompleted]);
report.StructuralPassed=report.DiagnosticCompleted && all([cases.StructuralPassed]) && ...
    report.CheckpointCount==sum(arrayfun(@(value)numel(value.checkpoints_s),plan.cases));
report.CrossEngineMatchesNative=all([comparisons.MatchesNative]);
writeSummary();

    function writeSummary()
        if ~isempty(outputDirectory)
            csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'contract-summary.json'),report);
        end
    end
end

function comparison=compareNative(observed,path,caseId)
if ~isfile(path), error('csr:t27:Reference','Missing native controls for %s.',caseId); end
native=readtable(path,'TextType','string','VariableNamingRule','preserve');
required={'case_id','order','time_s','command','source','final_destination', ...
    'next_hop','ackable','send_result','advertised_nodes'};
if ~all(ismember(required,native.Properties.VariableNames)) || ...
        any(native.case_id~=string(caseId)) || ...
        ~isequal(reshape(native.order,1,[]),1:height(native))
    error('csr:t27:Reference','Malformed native controls for %s.',caseId);
end
different=abs(numel(observed)-height(native));
numeric={'order','source','final_destination','next_hop','ackable','send_result'};
for index=1:min(numel(observed),height(native))
    row=observed(index); other=native(index,:);
    same=isfinite(other.time_s) && abs(row.time_s-other.time_s)<=1e-9 && ...
        strcmp(row.case_id,char(other.case_id)) && strcmp(row.command,char(other.command));
    for fieldIndex=1:numel(numeric)
        field=numeric{fieldIndex}; same=same && isequal(row.(field),double(other.(field)));
    end
    % Compare node arrays rather than CSV quoting or numeric JSON whitespace.
    left=jsondecode(row.advertised_nodes); right=jsondecode(char(other.advertised_nodes));
    same=same && isequal(reshape(left,1,[]),reshape(right,1,[]));
    different=different+double(~same);
end
comparison=struct('CaseId',char(caseId),'MatchesNative',different==0, ...
    'MatlabControlCount',numel(observed),'NativeControlCount',height(native),'DifferingRows',different);
end
