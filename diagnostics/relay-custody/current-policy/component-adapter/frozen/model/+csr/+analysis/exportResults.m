function exportResults(result, outputDirectory)
%EXPORTRESULTS MAT, JSON metadata/counters, and CSV trace/node counters.
if ~exist(outputDirectory, 'dir'), mkdir(outputDirectory); end
save(fullfile(outputDirectory, 'results.mat'), 'result');
writetable(result.Trace, fullfile(outputDirectory, 'trace.csv'));
writetable(result.NodeStatistics, fullfile(outputDirectory, 'nodes.csv'));
if isfield(result,'PhyTrace')
    writetable(result.PhyTrace, fullfile(outputDirectory,'phy_trace.csv'));
end
if isfield(result,'NodeMacStatistics')
    writetable(result.NodeMacStatistics,fullfile(outputDirectory,'mac_nodes.csv'));
    writetable(result.NodeHopStatistics,fullfile(outputDirectory,'hop_nodes.csv'));
    writetable(result.ProtocolTrace,fullfile(outputDirectory,'protocol_trace.csv'));
end
if isfield(result,'NodeNwkStatistics')
    writetable(result.NodeNwkStatistics,fullfile(outputDirectory,'nwk_nodes.csv'));
    writetable(result.Routes,fullfile(outputDirectory,'routes.csv'));
    writetable(result.Neighbors,fullfile(outputDirectory,'neighbors.csv'));
end
if isfield(result,'ApplicationAdmissionStatistics')
    writetable(result.ApplicationAdmissionStatistics, ...
        fullfile(outputDirectory,'application_admission_statistics.csv'));
    writetable(result.ApplicationAdmissionTrace, ...
        fullfile(outputDirectory,'application_admission_trace.csv'));
end
if isfield(result,'LinkDecisionTrace')
    writetable(result.LinkDecisionTrace,fullfile(outputDirectory,'link_decisions.csv'));
    writetable(result.ActualFeedbackTrace,fullfile(outputDirectory,'actual_feedback.csv'));
end
if isfield(result,'ServiceTrace')
    writetable(result.ServiceTrace,fullfile(outputDirectory,'service_trace.csv'));
end
summary = struct('Metadata', result.Metadata, 'Statistics', result.Statistics, 'Config', result.Config);
if isfield(result,'LinkDiagnostics'), summary.LinkDiagnostics = result.LinkDiagnostics; end
if isfield(result,'ServiceDiagnostics'), summary.ServiceDiagnostics = result.ServiceDiagnostics; end
% JSON records named/anonymous callback descriptions; the MAT file above
% retains the actual handle. JSON callback metadata is not executable config.
summary = jsonSafe(summary);
fid = fopen(fullfile(outputDirectory, 'summary.json'), 'w');
if fid < 0, error('csr:export:Open', 'Cannot open summary.json for writing.'); end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, '%s\n', jsonencode(summary, 'PrettyPrint', true));
end

function value = jsonSafe(value)
if isa(value,'function_handle')
    value = struct('Kind','matlab-function-handle','Expression',func2str(value), ...
        'ExecutableFromJson',false,'OriginalStoredIn','results.mat');
elseif isstruct(value)
    names = fieldnames(value);
    for index = 1:numel(value)
        for k = 1:numel(names)
            value(index).(names{k}) = jsonSafe(value(index).(names{k}));
        end
    end
elseif iscell(value)
    for index = 1:numel(value), value{index} = jsonSafe(value{index}); end
end
end
