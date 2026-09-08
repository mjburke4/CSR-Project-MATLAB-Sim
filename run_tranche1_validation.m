function run_tranche1_validation(outputDirectory)
%RUN_TRANCHE1_VALIDATION Run all portable tests and the integrated PHY cases.
% Native wireless-clock and packet probe have a separate validate_native gate.
root = fileparts(mfilename('fullpath'));
addpath(root);
if nargin == 0, outputDirectory = fullfile(root,'results','tranche1_validation'); end
if ~exist(outputDirectory,'dir'), mkdir(outputDirectory); end
% This runs the original 24 tests plus the new tests; asserts before scenarios.
run_validation(fullfile(outputDirectory,'tests'));
names = {'clean','overhearing','collision','mixed_rate','weak','band_mismatch', ...
    'closure','high_rate_500','high_rate_1000'};
rows = repmat(struct('Scenario','','Generated',0,'Received',0,'Dropped',0, ...
    'Pending',0,'PhysicalReceived',0,'Overheard',0,'Collisions',0,'RuntimeSeconds',0),numel(names),1);
for index = 1:numel(names)
    result = csr.runScenario(csr.scenario.phyNetwork(names{index}));
    csr.analysis.exportResults(result,fullfile(outputDirectory,names{index}));
    stats = result.Statistics;
    rows(index) = struct('Scenario',names{index},'Generated',stats.Generated, ...
        'Received',stats.Received,'Dropped',stats.Dropped,'Pending',stats.Pending, ...
        'PhysicalReceived',stats.PhysicalReceived,'Overheard',stats.Overheard, ...
        'Collisions',stats.Collisions,'RuntimeSeconds',result.Metadata.RuntimeSeconds);
end
summary = struct2table(rows,'AsArray',true);
writetable(summary,fullfile(outputDirectory,'scenario_summary.csv'));
disp(summary);
fprintf('Portable Tranche 1 validation completed on MATLAB %s (%s).\n',version,version('-release'));
end
