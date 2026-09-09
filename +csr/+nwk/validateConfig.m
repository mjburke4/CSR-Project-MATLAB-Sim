function config = validateConfig(config)
%VALIDATECONFIG Normalize autonomous routing scenarios before scheduling work.
if ~isfield(config,'Nwk'), config.Nwk = struct(); end
options = merge(config.Nwk,csr.nwk.defaults(),'Nwk');
if ~ischar(options.SecurityProfile) || ...
        ~strcmp(options.SecurityProfile,'behavioral-production-pairwise16-size-only')
    error('csr:nwk:InvalidConfig', ...
        'Tranche 3 supports only behavioral-production-pairwise16-size-only security.');
end
if ~strcmp(config.Radio.EnvelopeProfile,'pairwise16-size-only')
    error('csr:nwk:SecurityProfileMismatch', ...
        'The Tranche 3 production-behavioral profile requires pairwise16-size-only DATA/ACK envelopes.');
end
if ~any(strcmp(options.StartupMode,{'gateway','all','manual'}))
    error('csr:nwk:InvalidConfig','Nwk.StartupMode must be gateway, all or manual.');
end
for name = {'QueueLimit','ControlQueueLimit','MaxControlCycles','MaxHopCount'}
    options.(name{1}) = number(options.(name{1}),1,true);
end
options.MaxRouteRequests = number(options.MaxRouteRequests,0,true);
options.StartupDelaySeconds = number(options.StartupDelaySeconds,0,false);
for name = {'DiscoveryDurationSeconds','ControlRetrySeconds','RouteRequestSeconds', ...
        'SnapshotWatchdogSeconds','GatewayWatchdogSeconds'}
    options.(name{1}) = number(options.(name{1}),realmin,false);
end
for name = {'AdaptiveLinkControl','SendOnlyToGateway'}
    validateattributes(options.(name{1}),{'logical'},{'scalar'});
end
% These objects validate the complete nested contracts without starting timers.
csr.nwk.Neighbors(0,csr.sim.EventScheduler(),options.Neighbor,struct());
csr.nwk.Routes(0,1,options.Routing);
csr.nwk.Reassembly(options.Reassembly);
options.Neighbor = numericStorage(options.Neighbor);
for name = {'AdmissionEnabled','DiscoveryResponseEnabled','FreshnessEnabled'}
    options.Neighbor.(name{1}) = logical(options.Neighbor.(name{1}));
end
options.Routing = numericStorage(options.Routing);
options.Reassembly = numericStorage(options.Reassembly);
info = options.Routing.LocalInfo;
rates = [8 16 32 64 128 500 1000];
if ~ismember(info.MinSpeedKbps,rates) || ~ismember(info.MaxSpeedKbps,rates) || ...
        info.MinSpeedKbps > info.MaxSpeedKbps || ...
        info.MinPowerDbmX10 > info.MaxPowerDbmX10
    error('csr:nwk:InvalidConfig','INFO requires supported ordered rate endpoints and ordered power limits.');
end
config.Nwk = options;
for index = 1:numel(config.Nodes)
    if ~isfield(config.Nodes,'Capability') || isempty(config.Nodes(index).Capability)
        config.Nodes(index).Capability = 1;
    end
    validateattributes(config.Nodes(index).Capability,{'numeric'}, ...
        {'scalar','real','finite','integer','>=',0,'<=',2});
    config.Nodes(index).Capability = double(config.Nodes(index).Capability);
    if ~isfield(config.Nodes,'TransitForwardingEnabled') || isempty(config.Nodes(index).TransitForwardingEnabled)
        config.Nodes(index).TransitForwardingEnabled = true;
    end
    validateattributes(config.Nodes(index).TransitForwardingEnabled,{'logical'},{'scalar'});
end
for index = 1:numel(config.Traffic)
    if isfield(config.Traffic,'Path') && ~isempty(config.Traffic(index).Path)
        error('csr:nwk:ExplicitPath','Network scenarios discover routes; remove Traffic.Path.');
    end
    if ~isfield(config.Traffic,'Dscp') || isempty(config.Traffic(index).Dscp)
        config.Traffic(index).Dscp = 0;
    end
    if ~isfield(config.Traffic,'AckRequired') || isempty(config.Traffic(index).AckRequired)
        config.Traffic(index).AckRequired = true;
    end
    validateattributes(config.Traffic(index).Dscp,{'numeric'}, ...
        {'scalar','real','finite','integer','>=',0,'<=',255});
    validateattributes(config.Traffic(index).AckRequired,{'logical'},{'scalar'});
    config.Traffic(index).Dscp = double(config.Traffic(index).Dscp);
end
ids = [config.Nodes.Id];
config = events(config,'LinkEvents',{'TimeSeconds','NodeIds','Enabled'},ids);
config = events(config,'DiscoveryEvents',{'TimeSeconds','NodeIds'},ids);
end

function out = merge(given,out,label)
if ~isstruct(given) || ~isscalar(given)
    error('csr:nwk:InvalidConfig','%s must be a scalar struct.',label);
end
for item = fieldnames(given)'
    name = item{1};
    if ~isfield(out,name)
        error('csr:nwk:InvalidConfig','Unknown %s option: %s.',label,name);
    end
    if isstruct(out.(name))
        out.(name) = merge(given.(name),out.(name),[label '.' name]);
    else
        out.(name) = given.(name);
    end
end
end

function record = numericStorage(record)
% Accepted integer storage must not quantize fractional seconds or dBm/10.
for item = fieldnames(record)'
    name = item{1};
    if isstruct(record.(name)), record.(name) = numericStorage(record.(name));
    elseif isnumeric(record.(name)), record.(name) = double(record.(name)); end
end
end

function value = number(value,minimum,integer)
validateattributes(value,{'numeric'},{'scalar','real','finite','>=',minimum,'<=',flintmax});
if integer && fix(value) ~= value
    error('csr:nwk:InvalidConfig','NWK count/limit options must be integers.');
end
value = double(value);
end

function config = events(config,name,fields,ids)
if ~isfield(config,name) || isempty(config.(name))
    template = cell2struct(cell(size(fields)),fields,2);
    config.(name) = repmat(template,0,1); return
end
rows = config.(name);
if ~isstruct(rows) || ~all(isfield(rows,fields)) || ~isempty(setdiff(fieldnames(rows),fields))
    error('csr:nwk:InvalidEvents','Invalid %s event fields.',name);
end
for index = 1:numel(rows)
    validateattributes(rows(index).TimeSeconds,{'numeric'}, ...
        {'scalar','real','finite','>=',0,'<=',config.DurationSeconds});
    validateattributes(rows(index).NodeIds,{'numeric'},{'vector','integer','real','finite','nonempty'});
    nodes = reshape(double(rows(index).NodeIds),1,[]);
    if ~all(ismember(nodes,ids)) || numel(unique(nodes)) ~= numel(nodes)
        error('csr:nwk:InvalidEvents','Event node IDs must be distinct existing nodes.');
    end
    rows(index).NodeIds = nodes;
    rows(index).TimeSeconds = double(rows(index).TimeSeconds);
    if strcmp(name,'LinkEvents'), validateattributes(rows(index).Enabled,{'logical'},{'scalar'}); end
end
config.(name) = rows;
end
