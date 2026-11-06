function [cases,plan] = tranche19Suite()
%TRANCHE19SUITE Two full original campus runs differing only in DATA retry policy.
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
plan=jsondecode(fileread(fullfile(root,'scenarios','t19','plan.json')));
[original,~]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
if numel(original)~=1
    error('csr:t19:Plan','Exactly one original campus benchmark is required.');
end
csr.validation.RetryPolicyCheckpoint.validatePlan(plan,original);
template=original;
template.OriginalCaseId=original.CaseId;
template.Policy=''; template.PlanEntry=struct();
cases=repmat(template,2,1);
for k=1:2
    entry=plan.cases(k);
    cases(k).CaseId=entry.case_id;
    cases(k).Policy=entry.policy;
    cases(k).PlanEntry=entry;
    % Do not change Benchmark metadata, traffic, observation, PHY or timing.
    cases(k).Config.Hop.DataQueuedRetryPolicy=entry.policy;
    cases(k).Config=csr.scenario.validate(cases(k).Config);
    expected=original.Config; expected.Hop.DataQueuedRetryPolicy=entry.policy;
    if ~isequaln(cases(k).Config,expected)
        error('csr:t19:Plan','Validation altered settings outside the declared DATA retry policy.');
    end
end
end
