function [cases,plan] = tranche25Suite()
%TRANCHE25SUITE Two full original campus runs differing only in random seed.
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
plan=jsondecode(fileread(fullfile(root,'scenarios','t25','plan.json')));
[original,~]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
if numel(original)~=1
    error('csr:t25:Plan','Exactly one original campus benchmark is required.');
end
csr.validation.EnsembleCheckpoint.validatePlan(plan,original);
template=original;
template.OriginalCaseId=original.CaseId;
template.Policy=''; template.PlanEntry=struct();
cases=repmat(template,2,1);
for k=1:2
    entry=plan.cases(k);
    cases(k).CaseId=entry.case_id;
    cases(k).Seed=entry.seed;
    cases(k).Policy=entry.policy;
    cases(k).ReferenceDirectory=entry.reference_directory;
    cases(k).PlanEntry=entry;
    % Do not change Benchmark metadata, traffic, observation, PHY or timing.
    cases(k).Config.Seed=entry.seed;
    cases(k).Config=csr.scenario.validate(cases(k).Config);
    expected=original.Config; expected.Seed=entry.seed;
    if ~isequaln(cases(k).Config,expected)
        error('csr:t25:Plan','Validation altered settings outside the declared random seed.');
    end
end
end
