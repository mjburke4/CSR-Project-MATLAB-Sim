function config = validate(config)
%VALIDATE Fail explicitly on unsupported scenarios and ambiguous units.
required = {'Schema','Name','DurationSeconds','Seed','Backend','Nodes', ...
    'Radio','Channel','Traffic','Trace','MaxEvents'};
if ~isstruct(config) || ~isscalar(config) || ~all(isfield(config, required))
    error('csr:scenario:Schema', 'A complete scalar scenario configuration is required.');
end
if ~strcmp(config.Schema, 'csr-matlab-scenario-v1')
    error('csr:scenario:Schema', 'Unsupported scenario schema.');
end
if ~any(strcmp(config.Backend, {'portable','wireless-clock'}))
    error('csr:scenario:Backend', 'Backend must be portable or wireless-clock.');
end
if ~isfield(config.Channel, 'Model'), config.Channel.Model = 'controlled'; end
if ~any(strcmp(config.Channel.Model, {'controlled','csr-phy'}))
    error('csr:scenario:Channel', 'Channel.Model must be controlled or csr-phy.');
end
if ~isfield(config.Channel, 'FixedDropProbability'), config.Channel.FixedDropProbability = 0; end
if ~isfield(config.Trace, 'MaxPhyRecords'), config.Trace.MaxPhyRecords = config.Trace.MaxRecords; end
if ~isfield(config, 'Phy'), config.Phy = struct(); end
phyDefaults = struct('MaxActiveSignals',100000,'MaxIntervalsPerSignal',10000, ...
    'SyncToTrackSeconds',0.00663,'CaptureMarginDb',10.5);
unknown = setdiff(fieldnames(config.Phy), fieldnames(phyDefaults));
if ~isempty(unknown), error('csr:scenario:Phy', 'Unknown Phy field: %s', unknown{1}); end
for field = fieldnames(phyDefaults)'
    if ~isfield(config.Phy,field{1}), config.Phy.(field{1}) = phyDefaults.(field{1}); end
end
validateattributes(config.Phy.MaxActiveSignals, {'numeric'}, {'scalar','real','finite','integer','positive'});
validateattributes(config.Phy.MaxIntervalsPerSignal, {'numeric'}, {'scalar','real','finite','integer','positive'});
validateattributes(config.Phy.SyncToTrackSeconds, {'numeric'}, {'scalar','real','finite','positive'});
validateattributes(config.Phy.CaptureMarginDb, {'numeric'}, {'scalar','real','finite','nonnegative'});
validateattributes(config.DurationSeconds, {'numeric'}, {'scalar','real','finite','positive'});
validateattributes(config.Seed, {'numeric'}, {'scalar','real','finite','integer','>=',0,'<=',2^32-1});
validateattributes(config.MaxEvents, {'numeric'}, {'scalar','real','finite','integer','positive'});
if isempty(config.Nodes) || ~isstruct(config.Nodes) || ...
        ~all(isfield(config.Nodes, {'Id','PositionMeters'}))
    error('csr:scenario:Nodes', 'At least one node with Id and PositionMeters is required.');
end
for index = 1:numel(config.Nodes)
    validateattributes(config.Nodes(index).Id, {'numeric'}, ...
        {'scalar','real','finite','integer','>=',0,'<',2^24-1});
    config.Nodes(index).Id = double(config.Nodes(index).Id);
    validateattributes(config.Nodes(index).PositionMeters, {'numeric'}, ...
        {'vector','numel',3,'real','finite'});
    config.Nodes(index).PositionMeters = reshape(config.Nodes(index).PositionMeters, 1, 3);
    if ~isfield(config.Nodes(index),'RadioProfile') || isempty(config.Nodes(index).RadioProfile)
        config.Nodes(index).RadioProfile = csr.phy.RadioProfile.defaults();
    else
        config.Nodes(index).RadioProfile = csr.phy.RadioProfile.validate(config.Nodes(index).RadioProfile);
    end
end
ids = [config.Nodes.Id];
if numel(unique(ids)) ~= numel(ids)
    error('csr:scenario:DuplicateId', 'CSR node IDs must be unique; 0xFFFFFF is reserved for broadcast.');
end
csr.phy.rateDefinition(config.Radio.RateKeyKbps);
if ~any(strcmp(config.Radio.Preamble, {'long','short'})) || ...
        ~any(strcmp(config.Radio.EnvelopeProfile, {'bare','pairwise16-size-only'}))
    error('csr:scenario:Radio', 'Use long/short preamble and bare or pairwise16-size-only envelope.');
end
validateattributes(config.Channel.PropagationSpeedMps, {'numeric'}, {'scalar','real','finite','positive'});
validateattributes(config.Channel.FixedDropProbability, {'numeric'}, {'scalar','real','finite','>=',0,'<=',1});
if strcmp(config.Channel.Model,'csr-phy') && config.Channel.FixedDropProbability ~= 0
    error('csr:scenario:Channel', 'FixedDropProbability applies only to the controlled test channel.');
end
if ~isstruct(config.Traffic) || ~all(isfield(config.Traffic, ...
        {'SourceId','DestinationId','StartSeconds','IntervalSeconds','PacketCount','ApplicationPayloadBytes'}))
    error('csr:scenario:Traffic', 'Traffic must be a struct array using the defined flow fields.');
end
for index = 1:numel(config.Traffic)
    if ~isfield(config.Traffic(index),'RateKeyKbps') || isempty(config.Traffic(index).RateKeyKbps)
        config.Traffic(index).RateKeyKbps = config.Radio.RateKeyKbps;
    end
    if ~isfield(config.Traffic(index),'Preamble') || isempty(config.Traffic(index).Preamble)
        config.Traffic(index).Preamble = config.Radio.Preamble;
    end
    if ~isfield(config.Traffic(index),'TxPowerDbm'), config.Traffic(index).TxPowerDbm = []; end
    flow = config.Traffic(index);
    csr.phy.rateDefinition(flow.RateKeyKbps);
    if ~any(strcmp(flow.Preamble,{'long','short'}))
        error('csr:scenario:Preamble', 'Flow Preamble must be long or short.');
    end
    if ~isempty(flow.TxPowerDbm)
        validateattributes(flow.TxPowerDbm, {'numeric'}, {'scalar','real','finite'});
    end
    validateattributes(flow.SourceId, {'numeric'}, {'scalar','real','finite','integer'});
    validateattributes(flow.DestinationId, {'numeric'}, {'scalar','real','finite','integer'});
    if ~ismember(flow.SourceId, ids) || ~ismember(flow.DestinationId, ids) || flow.SourceId == flow.DestinationId
        error('csr:scenario:Endpoint', 'Each flow needs distinct existing source and destination nodes.');
    end
    validateattributes(flow.StartSeconds, {'numeric'}, {'scalar','real','finite','nonnegative'});
    validateattributes(flow.IntervalSeconds, {'numeric'}, {'scalar','real','finite','positive'});
    validateattributes(flow.PacketCount, {'numeric'}, {'scalar','real','finite','integer','nonnegative'});
    validateattributes(flow.ApplicationPayloadBytes, {'numeric'}, ...
        {'scalar','real','finite','integer','nonnegative','<=',65535});
end
validateattributes(config.Trace.Enabled, {'logical'}, {'scalar'});
validateattributes(config.Trace.MaxRecords, {'numeric'}, {'scalar','real','finite','integer','nonnegative'});
validateattributes(config.Trace.MaxPhyRecords, {'numeric'}, {'scalar','real','finite','integer','nonnegative'});
% Normalize accepted numeric storage types before protocol arithmetic.
config.DurationSeconds = double(config.DurationSeconds);
config.Seed = double(config.Seed);
config.MaxEvents = double(config.MaxEvents);
config.Trace.MaxRecords = double(config.Trace.MaxRecords);
config.Trace.MaxPhyRecords = double(config.Trace.MaxPhyRecords);
config.Radio.RateKeyKbps = double(config.Radio.RateKeyKbps);
config.Channel.PropagationSpeedMps = double(config.Channel.PropagationSpeedMps);
config.Channel.FixedDropProbability = double(config.Channel.FixedDropProbability);
for index = 1:numel(config.Nodes)
    config.Nodes(index).Id = double(config.Nodes(index).Id);
    config.Nodes(index).PositionMeters = double(config.Nodes(index).PositionMeters);
end
fields = {'SourceId','DestinationId','StartSeconds','IntervalSeconds','PacketCount','ApplicationPayloadBytes','RateKeyKbps','TxPowerDbm'};
for index = 1:numel(config.Traffic)
    for field = fields
        config.Traffic(index).(field{1}) = double(config.Traffic(index).(field{1}));
    end
end
for field = fieldnames(config.Phy)'
    config.Phy.(field{1}) = double(config.Phy.(field{1}));
end
end
