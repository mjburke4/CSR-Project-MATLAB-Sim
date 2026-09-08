% Run from repository root: run('examples/run_small_network.m')
root = fileparts(fileparts(mfilename('fullpath')));
addpath(root);
result = csr.runScenario(csr.scenario.smallNetwork());
disp(result.Statistics);
csr.analysis.exportResults(result, fullfile(root, 'results', 'small_network'));
