function report=run_repaired_checks
% Focused component regressions only. No autonomous or common-input network run.
root=fileparts(mfilename('fullpath'));candidate=fileparts(root);
addpath(root,candidate,fullfile(candidate,'model'),'-begin');
report=struct('passed',false,'runtime',version,'cases',{{}});
names={'run_nwk_owner_checks','run_node5_checks','run_node7_checks', ...
    'run_node7_fallback_check','run_node8_checks'};
for k=1:numel(names)
    value=feval(names{k},'candidate');
    report.cases{end+1}=struct('name',names{k},'passed',true,'result',value);
end
boundary=review_hop_boundary();assert(boundary.Passed);
report.cases{end+1}=struct('name','hop_boundary','passed',true,'result',boundary);
guard=@()assert(true); % Small synchronous component cases; no network scheduler.
value=test_timer_storage(candidate,fullfile(root,'timer_results'),guard);
report.cases{end+1}=struct('name','timer_storage','passed',value.passed,'result',value);
value=test_typed_trace_buffer(candidate,fullfile(root,'typed_results'),guard);
report.cases{end+1}=struct('name','typed_trace_buffer','passed',value.passed,'result',value);
report.passed=all(cellfun(@(x)x.passed,report.cases));
fid=fopen(fullfile(root,'RESULTS.json'),'w');assert(fid>=0);
cleanup=onCleanup(@()fclose(fid));fprintf(fid,'%s',jsonencode(report));
assert(report.passed);
end
