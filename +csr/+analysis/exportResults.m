function exportResults(result, outputDirectory)
%EXPORTRESULTS MAT, JSON metadata/counters, and CSV trace/node counters.
if ~exist(outputDirectory, 'dir'), mkdir(outputDirectory); end
save(fullfile(outputDirectory, 'results.mat'), 'result');
writetable(result.Trace, fullfile(outputDirectory, 'trace.csv'));
writetable(result.NodeStatistics, fullfile(outputDirectory, 'nodes.csv'));
summary = struct('Metadata', result.Metadata, 'Statistics', result.Statistics, 'Config', result.Config);
fid = fopen(fullfile(outputDirectory, 'summary.json'), 'w');
if fid < 0, error('csr:export:Open', 'Cannot open summary.json for writing.'); end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, '%s\n', jsonencode(summary, 'PrettyPrint', true));
end
