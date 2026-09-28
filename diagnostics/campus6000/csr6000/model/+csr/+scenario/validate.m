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
if ~isfield(config,'ApplicationProfile') || isempty(config.ApplicationProfile)
    config.ApplicationProfile = 'current-send-only';
end
if isstring(config.ApplicationProfile) && isscalar(config.ApplicationProfile)
    config.ApplicationProfile = char(config.ApplicationProfile);
end
applicationProfiles = {'current-send-only','legacy-send-only-no-dscp', ...
    'legacy-send-to-from-no-dscp'};
if ~ischar(config.ApplicationProfile) || ~isrow(config.ApplicationProfile) || ...
        ~any(strcmp(config.ApplicationProfile,applicationProfiles))
    error('csr:scenario:ApplicationProfile', ...
        'ApplicationProfile must be current-send-only or a named legacy no-DSCP profile.');
end
if ~any(strcmp(config.Backend, {'portable','wireless-clock'}))
    error('csr:scenario:Backend', 'Backend must be portable or wireless-clock.');
end
if ~isfield(config,'Stack'), config.Stack = 'phy-only'; end
if ~any(strcmp(config.Stack,{'phy-only','mac-hop','network'}))
    error('csr:scenario:Stack','Stack must be phy-only, mac-hop or network.');
end
if ~isfield(config,'ApplicationGenerator') || isempty(config.ApplicationGenerator)
    config.ApplicationGenerator = 'configured-count';
end
if isstring(config.ApplicationGenerator) && isscalar(config.ApplicationGenerator)
    config.ApplicationGenerator = char(config.ApplicationGenerator);
end
if ~ischar(config.ApplicationGenerator) || ~isrow(config.ApplicationGenerator) || ...
        ~any(strcmp(config.ApplicationGenerator,{'configured-count','historical-opnet-gated'}))
    error('csr:scenario:ApplicationGenerator','Unsupported application generator.');
end
historicalGenerator = strcmp(config.ApplicationGenerator,'historical-opnet-gated');
if historicalGenerator && ~strcmp(config.Stack,'network')
    error('csr:scenario:ApplicationGenerator','Historical application admission requires the network stack.');
end
if ~isfield(config,'ApplicationFlowLimit'), config.ApplicationFlowLimit = 0; end
validateattributes(config.ApplicationFlowLimit,{'numeric'}, ...
    {'scalar','real','finite','integer','nonnegative','<=',flintmax});
config.ApplicationFlowLimit = double(config.ApplicationFlowLimit);
if ~historicalGenerator && config.ApplicationFlowLimit ~= 0
    error('csr:scenario:ApplicationGenerator', ...
        'ApplicationFlowLimit applies only to the historical generator; use Traffic.PacketCount otherwise.');
end
if ~isfield(config.Channel, 'Model'), config.Channel.Model = 'controlled'; end
if ~any(strcmp(config.Channel.Model, {'controlled','csr-phy'}))
    error('csr:scenario:Channel', 'Channel.Model must be controlled or csr-phy.');
end
if ~isfield(config.Channel, 'FixedDropProbability'), config.Channel.FixedDropProbability = 0; end
if ~isfield(config.Trace, 'MaxPhyRecords'), config.Trace.MaxPhyRecords = config.Trace.MaxRecords; end
if ~isfield(config.Trace,'MaxApplicationAdmissionRecords')
    config.Trace.MaxApplicationAdmissionRecords = min(config.Trace.MaxRecords,100000);
end
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
    if ~isfield(config.Traffic(index),'DestinationMode') || isempty(config.Traffic(index).DestinationMode)
        config.Traffic(index).DestinationMode = 'fixed';
    end
    if isstring(config.Traffic(index).DestinationMode) && isscalar(config.Traffic(index).DestinationMode)
        config.Traffic(index).DestinationMode = char(config.Traffic(index).DestinationMode);
    end
    flow = config.Traffic(index);
    if ~ischar(flow.DestinationMode) || ~isrow(flow.DestinationMode) || ...
            ~any(strcmp(flow.DestinationMode,{'fixed','random_route_or_neighbor'})) || ...
            (~historicalGenerator && ~strcmp(flow.DestinationMode,'fixed'))
        error('csr:scenario:ApplicationGenerator', ...
            'Dynamic destinations require the explicit historical application generator.');
    end
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
    if historicalGenerator
        times = [config.DurationSeconds,flow.StartSeconds,flow.IntervalSeconds];
        ticks = times*1e9;
        if any(ticks > flintmax) || any(abs(ticks-round(ticks)) > 1e-5) || round(ticks(3)) == 0
            error('csr:scenario:ApplicationGenerator', ...
                'Historical generator times must be exactly representable nanoseconds.');
        end
        if round(ticks(2)) == round(ticks(1))
            error('csr:scenario:ApplicationGenerator', ...
                'A first generator event at the stop time has ambiguous source ordering.');
        end
    end
end
validateattributes(config.Trace.Enabled, {'logical'}, {'scalar'});
validateattributes(config.Trace.MaxRecords, {'numeric'}, {'scalar','real','finite','integer','nonnegative'});
validateattributes(config.Trace.MaxPhyRecords, {'numeric'}, {'scalar','real','finite','integer','nonnegative'});
validateattributes(config.Trace.MaxApplicationAdmissionRecords, {'numeric'}, ...
    {'scalar','real','finite','integer','nonnegative'});
% Normalize accepted numeric storage types before protocol arithmetic.
config.DurationSeconds = double(config.DurationSeconds);
config.Seed = double(config.Seed);
config.MaxEvents = double(config.MaxEvents);
config.Trace.MaxRecords = double(config.Trace.MaxRecords);
config.Trace.MaxPhyRecords = double(config.Trace.MaxPhyRecords);
config.Trace.MaxApplicationAdmissionRecords = double(config.Trace.MaxApplicationAdmissionRecords);
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
if any(strcmp(config.Stack,{'mac-hop','network'}))
    config = csr.hop.validateConfig(config);
    if ~strcmp(config.Channel.Model,'csr-phy')
        error('csr:scenario:MacHopChannel','The MAC/HOP stack requires the CSR PHY channel.');
    end
    if strcmp(config.Stack,'network')
        config = csr.nwk.validateConfig(config);
    else
    if ~isfield(config,'NetworkQueueLimit'), config.NetworkQueueLimit = 512; end
    validateattributes(config.NetworkQueueLimit,{'numeric'}, {'scalar','integer','positive','finite','real'});
    config.NetworkQueueLimit = double(config.NetworkQueueLimit);
    for k = 1:numel(config.Traffic)
        if ~isfield(config.Traffic(k),'Path') || isempty(config.Traffic(k).Path)
            config.Traffic(k).Path = [config.Traffic(k).SourceId,config.Traffic(k).DestinationId];
        end
        path = config.Traffic(k).Path;
        validateattributes(path,{'numeric'},{'vector','integer','finite','real','nonnegative'});
        path = reshape(double(path),1,[]);
        if numel(path)<2 || numel(unique(path))~=numel(path) || ~all(ismember(path,ids)) || ...
                path(1)~=config.Traffic(k).SourceId || path(end)~=config.Traffic(k).DestinationId
            error('csr:scenario:Path','Each explicit path must connect the flow endpoints through distinct existing nodes.');
        end
        config.Traffic(k).Path = path;
        if ~isfield(config.Traffic(k),'Dscp') || isempty(config.Traffic(k).Dscp), config.Traffic(k).Dscp = 0; end
        if ~isfield(config.Traffic(k),'AckRequired') || isempty(config.Traffic(k).AckRequired), config.Traffic(k).AckRequired = true; end
        validateattributes(config.Traffic(k).Dscp,{'numeric'},{'scalar','integer','finite','real','>=',0,'<=',255});
        validateattributes(config.Traffic(k).AckRequired,{'logical'},{'scalar'});
        config.Traffic(k).Dscp = double(config.Traffic(k).Dscp);
    end
    end
    fault = struct('Kind','*','SourceId',-1,'DestinationId',-1, ...
        'First',1,'Count',1,'StartSeconds',0,'EndSeconds',Inf);
    kinds = {'DATA','ACK','DACK','*'};
    if strcmp(config.Stack,'network')
        fault.ControlType = '*'; kinds{end+1} = 'CONTROL';
        if isfield(config,'Faults') && ~isempty(config.Faults) && ...
                isstruct(config.Faults) && ~isfield(config.Faults,'ControlType')
            [config.Faults.ControlType] = deal('*');
        end
    end
    if ~isfield(config,'Faults') || isempty(config.Faults)
        config.Faults = repmat(fault,0,1);
    else
        if ~isstruct(config.Faults) || ~all(isfield(config.Faults,fieldnames(fault))) || ...
                ~isempty(setdiff(fieldnames(config.Faults),fieldnames(fault)))
            error('csr:scenario:Faults','Faults must use the documented receive-erasure fields.');
        end
        for k = 1:numel(config.Faults)
            rule = config.Faults(k);
            if ~any(strcmp(rule.Kind,kinds))
                error('csr:scenario:Faults','Unsupported fault Kind for this stack.');
            end
            if strcmp(config.Stack,'network') && ...
                    ~any(strcmp(rule.ControlType,{'*','DISCOVER','KEY_REQUEST','KEY_UPDATE', ...
                    'NEIGHBOR_CHECK','ROUTING','SNMP_START','SNMP_DONE'}))
                error('csr:scenario:Faults','Unsupported fault ControlType.');
            end
            for field = {'SourceId','DestinationId'}
                value = rule.(field{1});
                validateattributes(value,{'numeric'},{'scalar','integer','finite','real'});
                if value~=-1 && ~ismember(value,ids), error('csr:scenario:Faults','Fault endpoints must exist or use -1 wildcard.'); end
            end
            validateattributes(rule.First,{'numeric'},{'scalar','integer','finite','positive','real'});
            validateattributes(rule.Count,{'numeric'},{'scalar','nonnegative','real','nonnan'});
            if isfinite(rule.Count) && fix(rule.Count)~=rule.Count, error('csr:scenario:Faults','Fault Count must be integer or Inf.'); end
            validateattributes(rule.StartSeconds,{'numeric'},{'scalar','nonnegative','finite','real'});
            validateattributes(rule.EndSeconds,{'numeric'},{'scalar','real','nonnan','>=',rule.StartSeconds});
            for field = {'SourceId','DestinationId','First','Count','StartSeconds','EndSeconds'}
                config.Faults(k).(field{1}) = double(rule.(field{1}));
            end
        end
    end
end
if any(strcmp(config.ApplicationProfile,applicationProfiles(2:3))) && ...
        isfield(config.Traffic,'Dscp') && any([config.Traffic.Dscp] ~= 0)
    error('csr:scenario:ApplicationProfile', ...
        'Legacy no-DSCP application profiles require every traffic DSCP to be zero.');
end
end
