function config = smallNetwork()
%SMALLNETWORK Three-node, controlled-link Tranche 0 acceptance scenario.
% Bytes are application bytes; this fixture uses the source's bare envelope.
config.Schema = 'csr-matlab-scenario-v1';
config.Name = 'three_node_controlled';
config.ApplicationProfile = 'current-send-only';
config.DurationSeconds = 10;
config.Seed = 128;
config.Backend = 'portable';
config.Nodes = struct('Id', {1, 2, 3}, ...
    'PositionMeters', {[0 0 1], [100 0 1], [0 200 1]});
config.Radio = struct('RateKeyKbps', 8, 'Preamble', 'long', ...
    'EnvelopeProfile', 'bare');
config.Channel = struct('PropagationSpeedMps', 299792458, ...
    'FixedDropProbability', 0);
config.Traffic = struct('SourceId', {2, 3}, 'DestinationId', {1, 1}, ...
    'StartSeconds', {0.1, 1.4}, 'IntervalSeconds', {3, 3}, ...
    'PacketCount', {3, 3}, 'ApplicationPayloadBytes', {64, 64});
config.Trace = struct('Enabled', true, 'MaxRecords', 10000);
config.MaxEvents = 1000000;
end
