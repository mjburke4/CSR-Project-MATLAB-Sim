function report = run_light_drain_tests(outputRoot)
%RUN_LIGHT_DRAIN_TESTS Three real-PHY campus seeds with finite traffic and drain.
% Extract this entire kit to a short path, then run report=run_light_drain_tests;
root=fileparts(mfilename('fullpath')); core=fullfile(root,'core');
oldPath=path; pathCleanup=onCleanup(@()path(oldPath)); %#ok<NASGU>
addpath(core,'-begin'); addpath(root,'-begin');
assert(strcmp(csr.validation.Artifacts.canonicalPath(which('csr.sim.NetworkSimulation')), ...
    csr.validation.Artifacts.canonicalPath(fullfile(core,'+csr','+sim','NetworkSimulation.m'))), ...
    'Another CSR core is active. Run this kit in a fresh MATLAB session.');
package=jsondecode(fileread(fullfile(root,'PACKAGE_FILES.json')));
for k=1:numel(package)
    assert(strcmp(csr.validation.Artifacts.sha256(fullfile(root,package(k).path)),package(k).sha256), ...
        'Test package changed: %s',package(k).path);
end
expected=jsondecode(fileread(fullfile(root,'accepted-core.json')));
for k=1:numel(expected)
    assert(strcmp(csr.validation.Artifacts.sha256(fullfile(core,expected(k).path)),expected(k).sha256), ...
        'Accepted core mismatch: %s',expected(k).path);
end
plan=jsondecode(fileread(fullfile(root,'plan.json')));
if nargin<1 || isempty(outputRoot)
    [~,token]=fileparts(tempname); outputRoot=fullfile(root,['out_drain_' token]);
end
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
assert(~isfolder(outputRoot)&&~isfile(outputRoot)&&~isfile([outputRoot '.zip']), ...
    'Use a new output directory.');
mkdir(outputRoot); copyfile(fullfile(root,'plan.json'),fullfile(outputRoot,'plan.json'));
snapshot=csr.validation.Artifacts.sourceSnapshot(core);
csr.validation.Artifacts.writeJson(fullfile(outputRoot,'source.json'),snapshot);
diary(fullfile(outputRoot,'run.log'));
diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('schema','csr-light-drain-matlab-v1','status','running', ...
    'version',version,'release',version('-release'),'matlab_executed',true, ...
    'native_executed_here',false,'production_changes',false,'parity_established',false, ...
    'output',outputRoot,'completed_cases',{{}});
failure=[]; currentCase='';
try
    fprintf('Running %d light-load/drain cases. Core protocol and PHY are unchanged.\n',numel(plan.cases));
    for k=1:numel(plan.cases)
        item=plan.cases(k); currentCase=item.id;
        dest=fullfile(outputRoot,item.id); mkdir(dest);
        csr.validation.Artifacts.writeJson(fullfile(dest,'status.json'),struct('status','running'));
        scenario=fullfile(root,item.scenario);
        assert(strcmp(csr.validation.Artifacts.sha256(scenario),item.sha256),'Scenario changed.');
        config=csr.scenario.importNs3(scenario, ...
            struct('HistoricalBenchmark',true,'FlowLimit',0,'Backend','portable'));
        assert(config.DurationSeconds==item.duration_s,'Scenario duration differs from plan.');
        [config,schedule]=apply_traffic_window(config,item.traffic_stop_s);
        assert(sum([schedule.PlannedAttempts])==item.expected_attempts,'Planned attempt count differs.');
        config.Trace.MaxRecords=3000000; config.Trace.MaxPhyRecords=3000000;
        config.Trace.MaxApplicationAdmissionRecords=150000; config.MaxEvents=30000000;
        config=csr.scenario.validate(config);
        csr.validation.Artifacts.writeJson(fullfile(dest,'traffic-window.json'), ...
            struct('traffic_stop_exclusive_s',item.traffic_stop_s, ...
            'simulation_stop_s',item.duration_s,'schedule',schedule));
        fprintf('%s: traffic stops at %.0f s; simulation ends at %.0f s.\n', ...
            item.id,item.traffic_stop_s,item.duration_s);
        simulation=csr.sim.NetworkSimulation(config); result=simulation.run();
        assert(simulation.Scheduler.Now==item.duration_s,'Incomplete simulation.');
        assert(result.Statistics.OmittedTraceRecords==0 && result.Statistics.OmittedPhyTraceRecords==0 && ...
            result.Statistics.OmittedApplicationAdmissionRecords==0,'Truncated evidence.');
        [performance,applications]=csr.analysis.performanceSummary(result);
        % Export before diagnostic checks so a schedule/accounting failure is inspectable.
        csr.validation.exportResearchCase(result,fullfile(dest,'raw'),core,snapshot,scenario);
        writetable(applications,fullfile(dest,'applications.csv'));
        csr.validation.Artifacts.writeJson(fullfile(dest,'performance.json'),performance);
        sources=summarize_drain_matlab(result,applications,schedule,item.traffic_stop_s);
        writetable(sources,fullfile(dest,'source-summary.csv'));
        disp(sources(:,{'SourceId','Attempts','Admitted','Delivered','Dropped','Pending', ...
            'MedianLatencySeconds','P95LatencySeconds'}));
        % Qualification is diagnostic, not a reason to discard or rerun a seed.
        basic=all(sources.BlockedFraction<=plan.qualification.max_blocked_fraction) && ...
            all(sources.DeliveryFraction>=plan.qualification.min_delivered_fraction) && ...
            all(sources.Pending==0) && all(result.NodeNwkStatistics.WaitingForHop==0);
        caseStatus=struct('status','completed','case_id',item.id, ...
            'source_and_end_waiting_criteria_passed',basic, ...
            'peak_waiting_queue_check','pending Python trace review', ...
            'full_light_load_qualification_established',false);
        csr.validation.Artifacts.writeJson(fullfile(dest,'status.json'),caseStatus);
        csr.validation.Artifacts.checkSnapshot(core,snapshot);
        report.completed_cases{end+1}=item.id;
        fprintf('%s complete: %d delivered, %d dropped, %d pending.\n', ...
            item.id,sum(sources.Delivered),sum(sources.Dropped),sum(sources.Pending));
        clear simulation result applications sources
    end
    report.status='completed-comparison-pending';
catch err
    report.status='failed'; report.failed_case=currentCase;
    report.error=struct('identifier',err.identifier,'message',err.message); failure=err;
    if exist('result','var') && ~isempty(currentCase) && ...
            ~isfile(fullfile(outputRoot,currentCase,'raw','case_manifest.json'))
        % Preserve a completed result even if its structural/omission gate failed.
        try
            csr.analysis.exportResults(result,fullfile(outputRoot,currentCase,'partial-raw'));
            report.partial_result_saved=true;
        catch exportError
            report.partial_export_error=exportError.message;
        end
    end
    if ~isempty(currentCase)
        csr.validation.Artifacts.writeJson(fullfile(outputRoot,currentCase,'status.json'), ...
            struct('status','failed','case_id',currentCase,'error',report.error));
    end
end
diary('off');
csr.validation.Artifacts.writeJson(fullfile(outputRoot,'metadata.json'),report);
csr.validation.Artifacts.writeJson(fullfile(outputRoot,'status.json'),report);
csr.validation.Artifacts.writeJson(fullfile(outputRoot,'files.json'), ...
    csr.validation.Artifacts.fileInventory(outputRoot,{'files.json'}));
zip([outputRoot '.zip'],{'*'},outputRoot);
fprintf('Return this evidence archive: %s.zip\n',outputRoot);
if ~isempty(failure), rethrow(failure); end
end
