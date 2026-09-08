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
if ~strcmp(config.Backend, 'portable')
    error('csr:scenario:Backend', 'Only the portable backend is implemented in Tranche 0.');
end
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
    validateattributes(config.Nodes(index).PositionMeters, {'numeric'}, ...
        {'vector','numel',3,'real','finite'});
    config.Nodes(index).PositionMeters = reshape(config.Nodes(index).PositionMeters, 1, 3);
end
ids = [config.Nodes.Id];
if numel(unique(ids)) ~= numel(ids)
    error('csr:scenario:DuplicateId', 'CSR node IDs must be unique; 0xFFFFFF is reserved for broadcast.');
end
csr.phy.rateDefinition(config.Radio.RateKeyKbps);
if ~any(strcmp(config.Radio.Preamble, {'long','short'})) || ...
        ~strcmp(config.Radio.EnvelopeProfile, 'bare')
    error('csr:scenario:Radio', 'Tranche 0 requires long/short preamble and bare envelope.');
end
validateattributes(config.Channel.PropagationSpeedMps, {'numeric'}, {'scalar','real','finite','positive'});
validateattributes(config.Channel.FixedDropProbability, {'numeric'}, {'scalar','real','finite','>=',0,'<=',1});
if ~isstruct(config.Traffic) || ~all(isfield(config.Traffic, ...
        {'SourceId','DestinationId','StartSeconds','IntervalSeconds','PacketCount','ApplicationPayloadBytes'}))
    error('csr:scenario:Traffic', 'Traffic must be a struct array using the defined flow fields.');
end
for index = 1:numel(config.Traffic)
    flow = config.Traffic(index);
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
% Normalize accepted numeric storage types before protocol arithmetic.
config.DurationSeconds = double(config.DurationSeconds);
config.Seed = double(config.Seed);
config.MaxEvents = double(config.MaxEvents);
config.Trace.MaxRecords = double(config.Trace.MaxRecords);
config.Radio.RateKeyKbps = double(config.Radio.RateKeyKbps);
config.Channel.PropagationSpeedMps = double(config.Channel.PropagationSpeedMps);
config.Channel.FixedDropProbability = double(config.Channel.FixedDropProbability);
for index = 1:numel(config.Nodes)
    config.Nodes(index).Id = double(config.Nodes(index).Id);
    config.Nodes(index).PositionMeters = double(config.Nodes(index).PositionMeters);
end
fields = {'SourceId','DestinationId','StartSeconds','IntervalSeconds','PacketCount','ApplicationPayloadBytes'};
for index = 1:numel(config.Traffic)
    for field = fields
        config.Traffic(index).(field{1}) = double(config.Traffic(index).(field{1}));
    end
end
end
