function report=run_load_matlab(coreRoot,outputRoot,caseIds)
% Six 600-s real-PHY cases. Optional caseIds, e.g. {'full132'}.
kit=fileparts(mfilename('fullpath')); oldPath=path; cleanup=onCleanup(@()path(oldPath)); %#ok<NASGU>
addpath(coreRoot,'-begin');
assert(strcmp(csr.validation.Artifacts.canonicalPath(which('csr.sim.NetworkSimulation')), ...
 csr.validation.Artifacts.canonicalPath(fullfile(coreRoot,'+csr','+sim','NetworkSimulation.m'))),'Wrong core installation');
assert(~isfolder(outputRoot)&&~isfile(outputRoot),'Use a new output directory'); mkdir(outputRoot);
diary(fullfile(outputRoot,'run.log')); logCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('status','running','matlab_version',version,'release',version('-release'), ...
 'matlab_executed',true,'native_executed',false,'acceptance_established',false,'completed_cases',{{}});
try
 expected=jsondecode(fileread(fullfile(kit,'accepted-core.json')));
 for k=1:numel(expected)
  assert(strcmp(csr.validation.Artifacts.sha256(fullfile(coreRoot,expected(k).path)),expected(k).sha256), ...
   'Accepted core mismatch: %s',expected(k).path);
 end
 snapshot=csr.validation.Artifacts.sourceSnapshot(coreRoot);
 csr.validation.Artifacts.writeJson(fullfile(outputRoot,'source.json'),snapshot);
 plan=jsondecode(fileread(fullfile(kit,'plan.json')));
 if nargin<3||isempty(caseIds), caseIds={plan.cases.id}; end
 assert(numel(unique(string(caseIds)))==numel(caseIds)&&all(ismember(string(caseIds),string({plan.cases.id}))),'Unknown or duplicate case');
 copyfile(fullfile(kit,'plan.json'),outputRoot);
 for k=1:numel(plan.cases)
  item=plan.cases(k); if ~ismember(string(item.id),string(caseIds)), continue; end
  dest=fullfile(outputRoot,item.id); mkdir(dest);
  csr.validation.Artifacts.writeJson(fullfile(dest,'status.json'),struct('status','running'));
  scenario=fullfile(kit,item.scenario);
  assert(strcmp(csr.validation.Artifacts.sha256(scenario),item.sha256),'Scenario changed');
  config=csr.scenario.importNs3(scenario,struct('HistoricalBenchmark',true,'FlowLimit',0,'Backend','portable'));
  config.Trace.MaxRecords=3000000; config.Trace.MaxPhyRecords=3000000;
  config.Trace.MaxApplicationAdmissionRecords=150000; config.MaxEvents=12000000;
  config=csr.scenario.validate(config);
  fprintf('Running %s, 600 seconds; no post-stop drain.\n',item.id);
  simulation=csr.sim.NetworkSimulation(config); result=simulation.run();
  assert(simulation.Scheduler.Now==600,'Incomplete simulation');
  assert(result.Statistics.OmittedTraceRecords==0 && result.Statistics.OmittedPhyTraceRecords==0 && ...
   result.Statistics.OmittedApplicationAdmissionRecords==0,'Truncated evidence');
  [performance,applications]=csr.analysis.performanceSummary(result);
  csr.validation.exportResearchCase(result,fullfile(dest,'raw'),coreRoot,snapshot,scenario);
  writetable(applications,fullfile(dest,'applications.csv'));
  writetable(result.NodeStatistics,fullfile(dest,'node_statistics.csv'));
  csr.validation.Artifacts.writeJson(fullfile(dest,'performance.json'),performance);
  csr.validation.Artifacts.checkSnapshot(coreRoot,snapshot);
  csr.validation.Artifacts.writeJson(fullfile(dest,'status.json'),struct('status','completed','case_id',item.id));
  report.completed_cases{end+1}=item.id;
 end
 report.status='completed-review-required';
catch err
 report.status='failed'; report.failure=struct('identifier',err.identifier,'message',err.message);
 csr.validation.Artifacts.writeJson(fullfile(outputRoot,'status.json'),report); rethrow(err);
end
csr.validation.Artifacts.writeJson(fullfile(outputRoot,'status.json'),report);
diary('off');
diary('off');
csr.validation.Artifacts.writeJson(fullfile(outputRoot,'files.json'),csr.validation.Artifacts.fileInventory(outputRoot,{'files.json'}));
end
