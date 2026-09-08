function run_tranche2_validation(outputDirectory)
%RUN_TRANCHE2_VALIDATION Run portable tests and integrated MAC/HOP scenarios.
% Native wireless integration is intentionally validated by validate_native.
root = fileparts(mfilename('fullpath'));
addpath(root);
if nargin == 0, outputDirectory = fullfile(root, 'results', 'tranche2_validation'); end
if ~exist(outputDirectory, 'dir'), mkdir(outputDirectory); end
run_validation(fullfile(outputDirectory, 'tests'));
names = {'reliable', 'ack_loss', 'data_loss', 'dack', 'collision', 'relay', ...
    'queue_pressure', 'high_rate_500', 'high_rate_1000'};
template = struct('Scenario', '', 'Generated', 0, 'Received', 0, 'Dropped', 0, ...
    'Pending', 0, 'PhysicalTransmissions', 0, 'Retransmissions', 0, ...
    'AcksReceived', 0, 'DacksReceived', 0, 'DuplicateData', 0, 'QueueDrops', 0, ...
    'HopFailures', 0, 'UnconfirmedHopTransfers', 0, 'FaultDrops', 0, ...
    'RelayAccepted', 0, 'PhysicalReceived', 0, 'Collisions', 0, ...
    'HopPendingData', 0, 'ResendQueueDepth', 0, 'DackHoldCount', 0, 'RuntimeSeconds', 0);
rows = repmat(template, numel(names), 1);
fields = fieldnames(template);
for index = 1:numel(names)
    result = csr.runScenario(csr.scenario.macHopNetwork(names{index}));
    csr.analysis.exportResults(result, fullfile(outputDirectory, names{index}));
    row = template;
    row.Scenario = names{index};
    row.RuntimeSeconds = result.Metadata.RuntimeSeconds;
    for fieldIndex = 2:numel(fields)-1
        name = fields{fieldIndex};
        if any(strcmp(name, {'HopPendingData', 'ResendQueueDepth', 'DackHoldCount'}))
            continue
        end
        row.(name) = result.Statistics.(name);
    end
    row.HopPendingData = sum(result.NodeHopStatistics.PendingData);
    row.ResendQueueDepth = sum(result.NodeHopStatistics.ResendQueueDepth);
    row.DackHoldCount = sum(result.NodeHopStatistics.DackHoldCount);
    rows(index) = row;
end
summary = struct2table(rows, 'AsArray', true);
writetable(summary, fullfile(outputDirectory, 'scenario_summary.csv'));
disp(summary);
fprintf('Portable Tranche 2 validation completed on MATLAB %s (%s).\n', version, version('-release'));
end
