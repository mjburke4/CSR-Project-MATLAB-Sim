function config = importNs3(path,options)
%IMPORTNS3 Import an audited csr-opnet-scenario-v1 configuration.
% FlowLimit is an explicit positive per-flow cap (default 3). The matching
% ns-3 run must disable application gating and stochastic SYNC thresholds.
% HistoricalBenchmark=true explicitly enables the archived profile tuple,
% source application gates and stochastic SYNC. Its FlowLimit defaults to 0
% (unlimited admitted packets); PacketCount then counts generator interrupts.
% Unsupported behavior is rejected; SharedScenario records the exact input.
if nargin < 2, options = struct(); end
if isstring(path) && isscalar(path), path = char(path); end
if ~ischar(path) || ~isrow(path) || isempty(path) || ~isfile(path)
    error('csr:scenario:ImportPath','An existing canonical CSV path is required.');
end
if ~isstruct(options) || ~isscalar(options) || ...
        ~isempty(setdiff(fieldnames(options),{'FlowLimit','Backend','HistoricalBenchmark'}))
    error('csr:scenario:ImportOptions','Options must contain only FlowLimit, Backend and HistoricalBenchmark.');
end
if ~isfield(options,'HistoricalBenchmark'), options.HistoricalBenchmark = false; end
if ~islogical(options.HistoricalBenchmark) || ~isscalar(options.HistoricalBenchmark)
    error('csr:scenario:ImportOptions','HistoricalBenchmark must be a scalar logical.');
end
historical = options.HistoricalBenchmark;
if ~isfield(options,'FlowLimit'), options.FlowLimit = 3*double(~historical); end
if ~isnumeric(options.FlowLimit) || ~isscalar(options.FlowLimit) || ...
        ~isreal(options.FlowLimit) || ~isfinite(options.FlowLimit) || ...
        options.FlowLimit < double(~historical) || options.FlowLimit > flintmax || ...
        fix(options.FlowLimit) ~= options.FlowLimit
    error('csr:scenario:ImportOptions', ...
        'FlowLimit must be a positive integer, or zero for an explicitly historical benchmark.');
end
if ~isfield(options,'Backend'), options.Backend = 'portable'; end
if isstring(options.Backend) && isscalar(options.Backend)
    options.Backend = char(options.Backend);
end
if ~ischar(options.Backend) || ~isrow(options.Backend) || ...
        ~any(strcmp(options.Backend,{'portable','wireless-clock'}))
    error('csr:scenario:ImportOptions','Backend must be portable or wireless-clock.');
end
options.FlowLimit = double(options.FlowLimit);
[headers,rows,digest] = readCanonical(path);
if ~all(ismember({'schema','record'},headers))
    error('csr:scenario:ImportSchema','CSV requires schema and record columns.');
end
run = {}; nodes = {}; flows = {};
common = {'schema','record'};
runFields = [common,{'scenario','source_sha256','duration_s','seed','tmm', ...
    'coordinate_scale_m_per_unit','application_profile','mac_profile', ...
    'hop_security_profile','ack_envelope_profile','source_executable_sha256', ...
    'reservation_control_start_s'}];
nodeFields = [common,{'node_id','name','node_type','x_m','y_m','height_m', ...
    'min_speed_kbps','max_speed_kbps','min_power_dbm','max_power_dbm', ...
    'link_margin_db','ecc_threshold','rx_frequency_hz','tx_frequency_hz'}];
if historical, nodeFields = [nodeFields,{'interarrival_s','packet_bytes','start_s'}]; end
flowFields = [common,{'flow_src','flow_dst','flow_start_s','flow_interval_s', ...
    'flow_packet_bytes','flow_dscp','flow_destination_mode'}];
for index = 1:size(rows,1)
    row = rows(index,:);
    if ~strcmp(field(headers,row,'schema'),'csr-opnet-scenario-v1')
        error('csr:scenario:ImportSchema','Every row must use csr-opnet-scenario-v1.');
    end
    record = field(headers,row,'record');
    switch record
        case 'run'
            allowed = runFields;
            if ~isempty(run), error('csr:scenario:ImportRows','Exactly one run row is required.'); end
            run = row;
        case 'node'
            allowed = nodeFields; nodes(end+1,:) = row; %#ok<AGROW>
        case 'flow'
            allowed = flowFields; flows(end+1,:) = row; %#ok<AGROW>
        otherwise
            error('csr:scenario:ImportRows','Unsupported row record: %s.',record);
    end
    populated = ~cellfun(@isempty,row);
    unsupported = headers(populated & ~ismember(headers,allowed));
    if ~isempty(unsupported)
        error('csr:scenario:ImportUnsupported', ...
            'Populated field %s is unsupported on a %s row.',unsupported{1},record);
    end
end
if isempty(run) || isempty(nodes)
    error('csr:scenario:ImportRows','One run row and at least one node are required.');
end
name = field(headers,run,'scenario');
if isempty(name), error('csr:scenario:ImportRows','The run must have a scenario name.'); end
[appProfile,macProfile,hopProfile,nwkProfile] = profiles(headers,run,historical);
if ~historical && ~isempty(field(headers,run,'source_executable_sha256'))
    error('csr:scenario:ImportUnsupported','Archived executable profiles require HistoricalBenchmark=true.');
end
if number(headers,run,'tmm',0,1,true) ~= 0
    error('csr:scenario:ImportUnsupported','TMM terrain is unsupported.');
end
if ~isempty(field(headers,run,'reservation_control_start_s')) && ...
        number(headers,run,'reservation_control_start_s',0,flintmax,false) ~= 0
    error('csr:scenario:ImportUnsupported','Forced reservation controls are unsupported.');
end
sourceDigest = field(headers,run,'source_sha256');
sourceLabel = sourceDigest;
if strcmp(sourceDigest,'synthetic-shared-scenario-v1')
    sourceDigest = ''; % This explicit origin label is not an OPNET archive hash.
elseif ~isempty(sourceDigest) && isempty(regexp(sourceDigest,'^[0-9a-f]{64}$','once'))
    error('csr:scenario:ImportRows', ...
        'source_sha256 must be empty, a lowercase SHA-256 digest, or synthetic-shared-scenario-v1.');
end
if historical && isempty(regexp(sourceDigest,'^[0-9a-f]{64}$','once'))
    error('csr:scenario:ImportProfile','Historical profiles require the original source SHA-256 digest.');
end
scale = 1;
if ~isempty(field(headers,run,'coordinate_scale_m_per_unit'))
    scale = number(headers,run,'coordinate_scale_m_per_unit',realmin,flintmax,false);
end
duration = number(headers,run,'duration_s',realmin,flintmax,false);
stopTick = timeTick(duration,'duration_s');
if stopTick == 0, error('csr:scenario:ImportNumber','duration_s must be at least one nanosecond.'); end
seed = number(headers,run,'seed',1,4294944442,true);
config = csr.scenario.routedNetwork('autonomous');
config.Name = name; config.DurationSeconds = duration; config.Seed = seed;
config.Backend = options.Backend;
config.ApplicationProfile = appProfile;
if historical
    config.ApplicationGenerator = 'historical-opnet-gated';
    config.ApplicationFlowLimit = options.FlowLimit;
    config.Mac.SlotProfile = macProfile;
    config.Nwk.SecurityProfile = nwkProfile;
    config.Radio.EnvelopeProfile = 'bare';
end
config.Nodes = repmat(config.Nodes(1),1,size(nodes,1));
nodeNames = cell(1,size(nodes,1));
nodeTraffic = repmat(struct('NodeId',0,'Present',false,'IntervalSeconds',NaN, ...
    'ConfiguredPacketBytes',NaN,'StartSeconds',NaN),1,size(nodes,1));
limits = zeros(size(nodes,1),6);
for index = 1:size(nodes,1)
    row = nodes(index,:);
    node = config.Nodes(index);
    node.Id = number(headers,row,'node_id',0,2^24-2,true);
    nodeTraffic(index).NodeId = node.Id;
    if historical
        present = ~cellfun(@isempty,{field(headers,row,'interarrival_s'), ...
            field(headers,row,'packet_bytes'),field(headers,row,'start_s')});
        if any(present) && ~all(present)
            error('csr:scenario:ImportRows','Archived node application metadata must contain all three fields.');
        end
        if all(present)
            nodeTraffic(index).Present = true;
            nodeTraffic(index).IntervalSeconds = number(headers,row,'interarrival_s',realmin,flintmax,false);
            nodeTraffic(index).ConfiguredPacketBytes = number(headers,row,'packet_bytes',15,65550,true);
            nodeTraffic(index).StartSeconds = number(headers,row,'start_s',0,flintmax,false);
        end
    end
    nodeNames{index} = field(headers,row,'name');
    if isempty(nodeNames{index}), error('csr:scenario:ImportNode','Every node needs a name.'); end
    kind = field(headers,row,'node_type');
    choices = {'ordinary','routable','gateway'};
    capability = find(strcmp(kind,choices),1)-1;
    if isempty(capability), error('csr:scenario:ImportNode','Unsupported node_type: %s.',kind); end
    node.Capability = capability; node.TransitForwardingEnabled = capability > 0;
    x = number(headers,row,'x_m',-flintmax,flintmax,false);
    y = number(headers,row,'y_m',-flintmax,flintmax,false);
    height = number(headers,row,'height_m',0,flintmax,false);
    node.PositionMeters = [x,y,height];
    minRate = number(headers,row,'min_speed_kbps',1,1000,true);
    maxRate = number(headers,row,'max_speed_kbps',1,1000,true);
    if minRate > maxRate || ~all(ismember([minRate,maxRate],[8,16,32,64,128,500,1000])) || ...
            (~historical && minRate ~= maxRate)
        error('csr:scenario:ImportUnsupported', ...
            'Rate limits must use supported ordered rates; ranges require HistoricalBenchmark=true.');
    end
    minPower = number(headers,row,'min_power_dbm',-3276.8,3276.7,false);
    maxPower = number(headers,row,'max_power_dbm',-3276.8,3276.7,false);
    margin = number(headers,row,'link_margin_db',0,3276.7,false);
    if minPower > maxPower || (~historical && minPower ~= maxPower) || ...
            abs(10*minPower-round(10*minPower)) > 1e-9 || ...
            abs(10*maxPower-round(10*maxPower)) > 1e-9 || ...
            abs(10*margin-round(10*margin)) > 1e-9
        error('csr:scenario:ImportUnsupported', ...
            'Use ordered power limits and power/margin representable in tenths of a dB.');
    end
    limits(index,:) = [minRate,maxRate,minPower,maxPower,margin,height];
    radio = csr.phy.RadioProfile.defaults();
    radio.TxPowerDbm = maxPower;
    radio.TxBaseFrequencyHz = number(headers,row,'tx_frequency_hz',realmin,flintmax,false);
    radio.RxBaseFrequencyHz = number(headers,row,'rx_frequency_hz',realmin,flintmax,false);
    radio.TxHeightMeters = height; radio.RxHeightMeters = height;
    radio.EccThreshold = number(headers,row,'ecc_threshold',0,1,false);
    radio.StochasticSyncThreshold = historical;
    node.RadioProfile = radio;
    config.Nodes(index) = node;
end
if numel(unique([config.Nodes.Id])) ~= numel(config.Nodes) || ...
        numel(unique(nodeNames)) ~= numel(nodeNames)
    error('csr:scenario:ImportNode','Node IDs and names must be unique.');
end
if any(any(limits ~= limits(1,:)))
    error('csr:scenario:ImportUnsupported', ...
        'Supported scenarios require uniform rate limits, power limits, margin and antenna height.');
end
% The reference sorts nodes by ID before constructing devices and RNG streams.
[~,order] = sort([config.Nodes.Id]);
config.Nodes = config.Nodes(order); nodeNames = nodeNames(order);
nodeTraffic = nodeTraffic(order);
config.Radio.RateKeyKbps = limits(1,1);
config.Nwk.AdaptiveLinkControl = historical;
info = config.Nwk.Routing.LocalInfo;
info.MinSpeedKbps = limits(1,1); info.MaxSpeedKbps = limits(1,2);
info.MinPowerDbmX10 = round(10*limits(1,3)); info.MaxPowerDbmX10 = round(10*limits(1,4));
info.LinkMarginDbX10 = round(10*limits(1,5));
config.Nwk.Routing.LocalInfo = info;
if historical, config.Traffic.DestinationMode = 'fixed'; end
config.Traffic = repmat(config.Traffic,1,size(flows,1));
configuredBytes = zeros(1,size(flows,1));
for index = 1:size(flows,1)
    row = flows(index,:);
    source = number(headers,row,'flow_src',0,2^24-2,true);
    destination = number(headers,row,'flow_dst',0,2^24-2,true);
    if source == destination || ~all(ismember([source,destination],[config.Nodes.Id]))
        error('csr:scenario:ImportFlow','Flows need distinct existing endpoints.');
    end
    mode = field(headers,row,'flow_destination_mode');
    if isempty(mode), mode = 'fixed'; end
    if ~strcmp(mode,'fixed') && ...
            ~(historical && strcmp(mode,'random_route_or_neighbor'))
        error('csr:scenario:ImportUnsupported','Unsupported flow destination mode.');
    end
    start = number(headers,row,'flow_start_s',0,flintmax,false);
    interval = number(headers,row,'flow_interval_s',realmin,flintmax,false);
    startTick = timeTick(start,'flow_start_s'); intervalTick = timeTick(interval,'flow_interval_s');
    if intervalTick == 0
        error('csr:scenario:ImportNumber','flow_interval_s must be at least one nanosecond.');
    end
    if startTick == stopTick
        error('csr:scenario:ImportUnsupported', ...
            'A first send exactly at stop has ambiguous source ordering; use start < stop or start > stop.');
    end
    count = 0;
    if startTick < stopTick
        count = floor((stopTick-1-startTick)/intervalTick)+1;
        if ~historical, count = min(options.FlowLimit,count); end
    end
    bytes = number(headers,row,'flow_packet_bytes',15,65550,true);
    if historical
        sourceTraffic = nodeTraffic([nodeTraffic.NodeId] == source);
        if sourceTraffic.Present && ...
                ~isequal([start,interval,bytes], ...
                [sourceTraffic.StartSeconds,sourceTraffic.IntervalSeconds,sourceTraffic.ConfiguredPacketBytes])
            error('csr:scenario:ImportFlow','Flow settings disagree with their archived source-node application settings.');
        end
    end
    flow = config.Traffic(index);
    flow.SourceId = source; flow.DestinationId = destination;
    flow.StartSeconds = start; flow.IntervalSeconds = interval; flow.PacketCount = count;
    flow.ApplicationPayloadBytes = bytes-15;
    flow.Dscp = number(headers,row,'flow_dscp',0,7,true);
    flow.AckRequired = true;
    if historical, flow.DestinationMode = mode; end
    config.Traffic(index) = flow; configuredBytes(index) = bytes;
end
if historical, validateHistoricalFlows(config); end
runOptions = struct('opnetAppGating',historical,'stochasticSyncThreshold',historical, ...
    'dutyCycling',true,'opnetAlignedDutyCycle',true,'gatewayDiscovery',true);
canonicalPath = csr.validation.Artifacts.canonicalPath(path);
config.SharedScenario = struct('Schema','csr-opnet-scenario-v1', ...
    'SourcePath',canonicalPath,'SourceSHA256',digest, ...
    'SourceCommit','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b', ...
    'FlowLimit',options.FlowLimit,'ApplicationProfile',appProfile, ...
    'MacProfile',macProfile,'HopSecurityProfile',hopProfile, ...
    'RunOptions',runOptions,'OriginalSourceSHA256',sourceDigest,'OriginalSourceLabel',sourceLabel, ...
    'CoordinateScaleMetersPerUnit',scale,'CoordinatesAlreadyMeters',true, ...
    'NodeNames',{nodeNames},'ConfiguredFlowPacketBytes',configuredBytes, ...
    'ApplicationPayloadExclusionBytes',15,'BrAppExclusionBytes',8,'NwkHeaderBytes',7, ...
    'HighRateExtension',limits(1,1) >= 500,'TimeResolutionNanoseconds',1, ...
    'Scope','Fixed-flow current-profile comparison input; no full network parity claim.');
if historical
    config.SharedScenario.HistoricalBenchmark = true;
    config.SharedScenario.SourceExecutableSHA256 = field(headers,run,'source_executable_sha256');
    config.SharedScenario.OriginalNodeApplicationSettings = nodeTraffic;
    config.SharedScenario.Scope = ['Archived source-bound application/MAC/envelope configuration; ' ...
        'gated generation and adaptive link control; no numerical or cryptographic parity claim.'];
end
config = csr.scenario.validate(config);
end

function [application,mac,hop,nwk] = profiles(headers,run,historical)
application = field(headers,run,'application_profile');
mac = field(headers,run,'mac_profile'); hop = field(headers,run,'hop_security_profile');
nwk = 'behavioral-production-pairwise16-size-only';
if ~historical
    profile(headers,run,'application_profile','current-send-only',false);
    profile(headers,run,'mac_profile','current-fine-free-slot',false);
    profile(headers,run,'hop_security_profile','production-pairwise16',false);
    profile(headers,run,'ack_envelope_profile','production-pairwise16',true);
    return
end
tuples = {
    'legacy-send-only-no-dscp','hist-2014-next-tslot-modulo-probe','hist-adb97c54-bare', ...
    'adb97c54f7566439f1404e972d3d777a3bca613e2a965bf12f03353fb009d9af';
    'legacy-send-to-from-no-dscp','hist-2015-fine-one-based-table-no-avoid','hist-dd3f38e8-bare', ...
    'dd3f38e8d33700b61f9e360a737ba34e56cb75b2570eb2960a02de381ed0fff0'};
matched = find(strcmp(application,tuples(:,1)) & strcmp(mac,tuples(:,2)) & strcmp(hop,tuples(:,3)),1);
if isempty(matched)
    error('csr:scenario:ImportProfile','Historical application, MAC and HOP profiles must select an audited atomic tuple.');
end
profile(headers,run,'ack_envelope_profile',hop,true);
profile(headers,run,'source_executable_sha256',tuples{matched,4},false);
nwk = ['behavioral-' hop '-size-only'];
end

function validateHistoricalFlows(config)
gateways = [config.Nodes([config.Nodes.Capability] == 2).Id];
if numel(gateways) ~= 1
    error('csr:scenario:ImportProfile','Historical application profiles require exactly one gateway.');
end
dynamic = 0;
for flow = config.Traffic
    if flow.Dscp ~= 0
        error('csr:scenario:ImportProfile','Historical application profiles require zero DSCP.');
    end
    if strcmp(flow.DestinationMode,'random_route_or_neighbor')
        dynamic = dynamic+1;
        if flow.SourceId ~= gateways
            error('csr:scenario:ImportProfile','A dynamic historical flow must originate at the gateway.');
        end
    elseif flow.SourceId == gateways || flow.DestinationId ~= gateways
        error('csr:scenario:ImportProfile','Fixed historical flows must originate outside and terminate at the gateway.');
    end
end
expected = double(strcmp(config.ApplicationProfile,'legacy-send-to-from-no-dscp'));
if dynamic ~= expected
    error('csr:scenario:ImportProfile','Historical profile has the wrong gateway-origin dynamic flow count.');
end
end

function value = field(headers,row,name)
index = find(strcmp(headers,name),1);
if isempty(index), value = ''; else, value = row{index}; end
end

function value = number(headers,row,name,minimum,maximum,integer)
token = field(headers,row,name);
if isempty(regexp(token,'^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$','once'))
    error('csr:scenario:ImportNumber','%s must be an unambiguous decimal number.',name);
end
value = str2double(token);
if ~isfinite(value) || value < minimum || value > maximum || ...
        (integer && (fix(value) ~= value || ~isempty(regexp(token,'[.eE]','once'))))
    error('csr:scenario:ImportNumber','Invalid numeric value for %s.',name);
end
% Decimal leading zeroes are rejected for integers because std::stoull(base0)
% in the reference interprets such tokens as octal.
digits = regexprep(token,'^[+-]','');
if integer && numel(digits)>1 && digits(1)=='0'
    error('csr:scenario:ImportNumber','Use decimal integers without leading zeroes for %s.',name);
end
end

function tick = timeTick(seconds,name)
scaled = seconds*1e9;
tick = round(scaled);
if ~isfinite(scaled) || scaled > flintmax || abs(scaled-tick) > 1e-6
    error('csr:scenario:ImportUnsupported', ...
        '%s must be representable as exact nanoseconds within the portable integer range.',name);
end
end

function profile(headers,row,name,expected,optional)
value = field(headers,row,name);
if ~(optional && isempty(value)) && ~strcmp(value,expected)
    error('csr:scenario:ImportProfile','%s must explicitly select %s.',name,expected);
end
end

function [headers,rows,digest] = readCanonical(path)
if ~usejava('jvm')
    error('csr:scenario:ImportJVM','Exact source hashing requires the standard MATLAB JVM.');
end
fid = fopen(path,'rb');
if fid < 0, error('csr:scenario:ImportPath','Cannot read canonical CSV: %s.',path); end
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
bytes = fread(fid,Inf,'*uint8');
hasher = javaMethod('getInstance','java.security.MessageDigest','SHA-256');
if ~isempty(bytes), hasher.update(typecast(bytes,'int8')); end
digest = lower(reshape(dec2hex(typecast(hasher.digest(),'uint8'),2).',1,[]));
text = native2unicode(reshape(bytes,1,[]),'UTF-8');
lines = regexp(text,'\r\n|\n|\r','split');
if isempty(lines) || isempty(lines{1})
    error('csr:scenario:ImportCsv','Canonical CSV must have a nonempty header.');
end
headers = parseLine(lines{1});
if any(cellfun(@isempty,headers)) || numel(unique(headers)) ~= numel(headers)
    error('csr:scenario:ImportCsv','CSV column names must be nonempty and unique.');
end
rows = cell(0,numel(headers));
for index = 2:numel(lines)
    if isempty(lines{index}), continue; end
    row = parseLine(lines{index});
    if numel(row) ~= numel(headers)
        error('csr:scenario:ImportCsv','CSV line %d has the wrong number of columns.',index);
    end
    rows(end+1,:) = row; %#ok<AGROW>
end
end

function fields = parseLine(line)
% Keep all cells as row char vectors; no readtable type/shape inference.
fields = {}; token = ''; state = 0; index = 1;
while index <= numel(line)
    c = line(index);
    if state == 1
        if c == '"'
            if index < numel(line) && line(index+1) == '"'
                token(end+1) = '"'; index = index+1; %#ok<AGROW>
            else
                state = 2;
            end
        else
            token(end+1) = c; %#ok<AGROW>
        end
    elseif c == ','
        fields{end+1} = token; token = ''; state = 0; %#ok<AGROW>
    elseif c == '"' && state == 0 && isempty(token)
        state = 1;
    elseif state == 2 || c == '"'
        error('csr:scenario:ImportCsv','Malformed CSV quoting.');
    else
        token(end+1) = c; %#ok<AGROW>
    end
    index = index+1;
end
if state == 1, error('csr:scenario:ImportCsv','Unterminated CSV quote.'); end
fields{end+1} = token;
end
