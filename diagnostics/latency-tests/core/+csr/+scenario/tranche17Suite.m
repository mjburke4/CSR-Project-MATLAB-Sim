function [item,plan] = tranche17Suite()
%TRANCHE17SUITE One unchanged 6000-second campus benchmark at seed 128.
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
plan=jsondecode(fileread(fullfile(root,'scenarios','t17','plan.json')));
[item,benchmarkPlan]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
if numel(item)~=1
    error('csr:t17:Plan','Exactly one original campus benchmark is required.');
end
csr.validation.ReleaseCheckpoint.validatePlan(plan,item,benchmarkPlan.CatalogSHA256);
item.StorageKey='c';
end
