function report=integratedAccountingPreflight(config,folder)
%INTEGRATEDACCOUNTINGPREFLIGHT Run every independent accounting case then fail.
if ~isfolder(folder), mkdir(folder); end
report=struct('schema','csr-integrated-accounting-preflight-v1','completed',false, ...
    'passed',false,'network_parity_claim',false,'matlab_execution_required',true, ...
    'checks',struct('name',{},'passed',{},'details',{}));
for mode={'cutoff','final','relay','siblings'}
    name=mode{1}; fixture=[]; passed=false; details=struct();
    resources=containers.Map('KeyType','char','ValueType','any');
    cleanup=resourceGuard(resources); %#ok<NASGU>
    try
        fixture=ac.AccountingFixture(config,fullfile(folder,name),name);
        resources('fixture')=fixture;
        fixture.execute(); details=fixture.summary(); passed=details.passed;
    catch caught
        if ~isempty(fixture)
            details=fixture.summary();
            try
                fixture.persist();
            catch diagnosticError
                details.diagnostic_error_identifier=diagnosticError.identifier;
                details.diagnostic_error_message=diagnosticError.message;
            end
        end
        details.error_identifier=caught.identifier; details.error_message=caught.message; details.error_stack=caught.stack;
    end
    report.checks(end+1)=struct('name',name,'passed',passed,'details',details); %#ok<AGROW>
    ac.writeJson(fullfile(folder,'integrated_accounting_preflight.json'),report);
    clear cleanup
    fprintf('  Integrated accounting %s: %s\n',name,passLabel(passed));
end
report.completed=numel(report.checks)==4; report.passed=report.completed && all([report.checks.passed]);
report.passed_groups=sum([report.checks.passed]); report.failed_groups=sum(~[report.checks.passed]);
ac.writeJson(fullfile(folder,'integrated_accounting_preflight.json'),report);
assert(report.passed,'batchcase:AccountingFailures', ...
    '%d of 4 integrated accounting groups failed; all groups attempted. Read integrated_accounting_preflight.json.',report.failed_groups);
end
function guard=resourceGuard(resources)
guard=onCleanup(@()closeResources(resources));
end
function closeResources(resources)
% Stable map handle captured by local function, not exiting nested workspace.
items=values(resources);
for k=1:numel(items)
    % Clear only this fixture's sink; never close an unrelated active trace.
    sink=ac.Trace.holder();
    if ~isempty(sink) && isequal(sink,items{k}), ac.Trace.holder('clear',[]); end
    try
        items{k}.close();
    catch cleanupError
        warning('batchcase:AccountingCleanup','Accounting cleanup failed: %s',cleanupError.message);
    end
end
end
function value=passLabel(passed)
value='FAIL'; if passed, value='PASS'; end
end
