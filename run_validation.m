function run_validation(outputDirectory)
%RUN_VALIDATION Run on MATLAB R2025a or R2026a; preserve actual runtime evidence.
root = fileparts(mfilename('fullpath'));
addpath(root);
if nargin == 0, outputDirectory = fullfile(root, 'results', 'validation'); end
if ~exist(outputDirectory, 'dir'), mkdir(outputDirectory); end
diary(fullfile(outputDirectory, 'validation.log'));
cleanup = onCleanup(@() diary('off'));
disp(csr.sim.capabilities());
% Native-only tests are an explicit validate_native gate and never part of
% the portable suite on installations without R2026a's public classes.
testResults = runtests(fullfile(root, 'tests'), 'IncludeSubfolders', false);
disp(testResults);
save(fullfile(outputDirectory, 'test_results.mat'), 'testResults');
testSummary = table({testResults.Name}', [testResults.Passed]', ...
    [testResults.Failed]', [testResults.Incomplete]', [testResults.Duration]', ...
    'VariableNames', {'Name','Passed','Failed','Incomplete','DurationSeconds'});
writetable(testSummary, fullfile(outputDirectory, 'test_results.csv'));
assertSuccess(testResults);
result = csr.runScenario();
csr.analysis.exportResults(result, outputDirectory);
disp(result.Statistics);
fprintf('MATLAB validation completed successfully on %s (%s).\n', version, version('-release'));
end
