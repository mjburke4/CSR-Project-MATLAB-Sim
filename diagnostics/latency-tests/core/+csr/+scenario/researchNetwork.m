function config = researchNetwork(name, options)
%RESEARCHNETWORK Synthetic research layouts using the packet-level CSR PHY.
% config = csr.scenario.researchNetwork(name, options) accepts only Seed,
% DurationSeconds and ApplicationProfile in the optional scalar options struct.
% DurationSeconds may extend a fixture up to 6000 s; long_run_6000 is fixed.
% These are research hypotheses, not imported campus scenarios or certified
% delivery outcomes. Routes and admission form from received control packets.
if nargin < 1, name = 'two_node'; end
if nargin < 2, options = struct(); end
name = textChoice(name, {'two_node','line_4','hidden_node','mesh_6', ...
    'route_recovery','leaf_no_transit','high_rate_500','high_rate_1000', ...
    'long_run_6000'}, 'csr:scenario:UnknownResearchFixture');
if ~isstruct(options) || ~isscalar(options)
    error('csr:scenario:ResearchOptions','Research options must be a scalar struct.');
end
unknown = setdiff(fieldnames(options), {'Seed','DurationSeconds','ApplicationProfile'});
if ~isempty(unknown)
    error('csr:scenario:ResearchOptions','Unknown research option: %s.',unknown{1});
end

spacing = 3800;
duration = 600;
positions = [0 0 1; spacing 0 1; 2*spacing 0 1];
description = '';
switch name
    case 'two_node'
        positions = [0 0 1; 100 0 1]; duration = 300;
        description = 'Short terrestrial link for admission and application transfer.';
    case {'line_4','long_run_6000'}
        positions = [(0:3)'*spacing zeros(4,1) ones(4,1)];
        description = ['Four-node line with adjacent geometric visibility; ' ...
            'nonadjacent links exceed the modeled Earth horizon.'];
        if strcmp(name,'long_run_6000'), duration = 6000; end
    case 'hidden_node'
        positions = [0 0 1; -spacing 0 1; spacing 0 1];
        description = ['Two sources share a visible receiver while their mutual ' ...
            'link exceeds the modeled Earth horizon; collision frequency is an outcome.'];
    case 'mesh_6'
        positions = [0 0 1; spacing 0 1; 2*spacing 0 1; ...
            0 spacing 1; spacing spacing 1; 2*spacing spacing 1];
        duration = 900;
        description = ['Six-node rectangular layout offers side and diagonal ' ...
            'RF opportunities; actual admitted links and selected paths are measured.'];
    case 'route_recovery'
        duration = 900;
        description = ['Three-node RF line with an explicit administrative receive ' ...
            'blackout at its relay, followed by scheduled rediscovery.'];
    case 'leaf_no_transit'
        description = ['Three-node RF line whose middle node is an admitted leaf ' ...
            'with transit forwarding disabled.'];
    case {'high_rate_500','high_rate_1000'}
        positions = [0 0 1; 100 0 1]; duration = 300;
        description = 'Short-link high-rate radio extension; excluded from ordinary-rate comparisons.';
end
if isfield(options,'DurationSeconds')
    value = options.DurationSeconds;
    if ~isnumeric(value) || ~isscalar(value) || ~isreal(value) || ...
            ~isfinite(value) || value < duration || value > 6000
        error('csr:scenario:ResearchDuration', ...
            'DurationSeconds must be finite and between this fixture minimum (%g) and 6000 s.',duration);
    end
    duration = double(value);
end

config = csr.scenario.smallNetwork();
config.Name = ['research_' name];
config.Stack = 'network';
config.DurationSeconds = duration;
config.Backend = 'portable';
if isfield(options,'Seed'), config.Seed = options.Seed; end
if isfield(options,'ApplicationProfile')
    config.ApplicationProfile = textChoice(options.ApplicationProfile, ...
        {'current-send-only','legacy-send-only-no-dscp','legacy-send-to-from-no-dscp'}, ...
        'csr:scenario:ApplicationProfile');
end
config.Channel = struct('Model','csr-phy','PropagationSpeedMps',3e8, ...
    'FixedDropProbability',0);
config.Radio.EnvelopeProfile = 'pairwise16-size-only';
profile = csr.phy.RadioProfile.defaults();
profile.TxBaseFrequencyHz = 400e6;
profile.RxBaseFrequencyHz = 400e6;
profile.TxPowerDbm = 30;
% Leave the source threshold variance and random sampling enabled. Antenna
% heights explicitly match the geometry; no visibility hook or distance scale.
profile.TxHeightMeters = 1;
profile.RxHeightMeters = 1;
node = struct('Id',1,'PositionMeters',[0 0 1],'RadioProfile',profile, ...
    'Capability',1,'TransitForwardingEnabled',true);
config.Nodes = repmat(node,1,size(positions,1));
for k = 1:numel(config.Nodes)
    config.Nodes(k).Id = k;
    config.Nodes(k).PositionMeters = positions(k,:);
end
config.Nodes(1).Capability = 2;
config.Mac = csr.mac.Layer.defaults();
config.Hop = csr.hop.Layer.defaults();
config.Nwk = csr.nwk.defaults();
% The retained SNMP workflow does not forward a START through multiple hops.
% Staggered administrative requests expose every radio to local discovery;
% no path or neighbor state is installed by these requests.
config.Nwk.StartupMode = 'manual';
config.DiscoveryEvents = repmat(struct('TimeSeconds',0,'NodeIds',1),numel(config.Nodes),1);
for k = 1:numel(config.Nodes)
    config.DiscoveryEvents(k).TimeSeconds = 10+35*(k-1);
    config.DiscoveryEvents(k).NodeIds = k;
end
config.LinkEvents = struct('TimeSeconds',{},'NodeIds',{},'Enabled',{});
config.Faults = struct('Kind',{},'SourceId',{},'DestinationId',{}, ...
    'First',{},'Count',{},'StartSeconds',{},'EndSeconds',{},'ControlType',{});

flow = struct('SourceId',numel(config.Nodes),'DestinationId',1, ...
    'StartSeconds',0.4*duration,'IntervalSeconds',0.04*duration, ...
    'PacketCount',5,'ApplicationPayloadBytes',64,'Dscp',0,'AckRequired',true);
config.Traffic = flow;
if strcmp(name,'hidden_node')
    config.Traffic = repmat(flow,1,2);
    for k = 1:2
        config.Traffic(k).SourceId = k+1;
        config.Traffic(k).PacketCount = 8;
        config.Traffic(k).IntervalSeconds = 0.015*duration;
    end
elseif strcmp(name,'mesh_6')
    config.Traffic = repmat(flow,1,3);
    for k = 1:3
        config.Traffic(k).SourceId = k+3;
        config.Traffic(k).StartSeconds = flow.StartSeconds+6*(k-1);
        config.Traffic(k).Dscp = 8*(k-1);
    end
elseif strcmp(name,'route_recovery')
    config.Nwk.Neighbor.FreshnessEnabled = true;
    config.Nwk.Neighbor.FreshnessTimeoutSeconds = 60;
    config.Nwk.Neighbor.FreshnessPeriodSeconds = 5;
    config.LinkEvents = struct('TimeSeconds',{0.45*duration,0.60*duration}, ...
        'NodeIds',{2,2},'Enabled',{false,true});
    % Both requests are explicit experimental stimuli. A blackout is applied
    % at receive completion; it is not a physical movement or power change.
    for fraction = [0.35 0.64]
        for k = 1:numel(config.Nodes)
            config.DiscoveryEvents(end+1,1) = struct( ...
                'TimeSeconds',fraction*duration+5*(k-1),'NodeIds',k); %#ok<AGROW>
        end
    end
    config.Traffic.StartSeconds = 0.50*duration;
elseif strcmp(name,'leaf_no_transit')
    config.Nodes(2).Capability = 0;
    config.Nodes(2).TransitForwardingEnabled = false;
elseif strcmp(name,'long_run_6000')
    config.Traffic.StartSeconds = 600;
    config.Traffic.IntervalSeconds = 30;
    config.Traffic.PacketCount = 160;
end

isHighRate = any(strcmp(name,{'high_rate_500','high_rate_1000'}));
rateProfile = 'ordinary-8-to-128-kbps';
if isHighRate
    rate = 500;
    if strcmp(name,'high_rate_1000'), rate = 1000; end
    config.Radio.RateKeyKbps = rate;
    config.Nwk.AdaptiveLinkControl = false;
    config.Nwk.Routing.LocalInfo.MinSpeedKbps = rate;
    config.Nwk.Routing.LocalInfo.MaxSpeedKbps = rate;
    rateProfile = sprintf('radio-extension-%d-kbps',rate);
end
if ~strcmp(config.ApplicationProfile,'current-send-only')
    [config.Traffic.Dscp] = deal(0);
end
config.Trace.MaxRecords = 100000;
config.Trace.MaxPhyRecords = 100000;
config.MaxEvents = 2000000;
if strcmp(name,'long_run_6000')
    config.Trace.MaxRecords = 200000;
    config.Trace.MaxPhyRecords = 200000;
    config.MaxEvents = 5000000;
end
lastTraffic = max([config.Traffic.StartSeconds] + ...
    ([config.Traffic.PacketCount]-1).*[config.Traffic.IntervalSeconds]);
config.Research = struct('Schema','csr-matlab-research-fixture-v1', ...
    'FixtureName',name,'LayoutOrigin','synthetic-research-layout', ...
    'ImportedHistoricalCampus',false,'Description',description, ...
    'RateProfile',rateProfile,'HighRateExtension',isHighRate, ...
    'LongRunOptIn',duration >= 6000, ...
    'WarmupSeconds',min([config.Traffic.StartSeconds]), ...
    'TrafficEndSeconds',lastTraffic,'DrainSeconds',duration-lastTraffic, ...
    'DiscoveryPolicy','Explicit staggered per-node requests; routes learned over received packets', ...
    'AdministrativeReceiveBlackout',strcmp(name,'route_recovery'), ...
    'ExpectedDeliveryCertified',false, ...
    'RfHypothesis','Geometric visibility and link budget do not guarantee acquisition, admission or delivery');
config = csr.scenario.validate(config);
end

function value = textChoice(value, choices, identifier)
if isstring(value) && isscalar(value), value = char(value); end
if ~ischar(value) || ~isrow(value) || ~any(strcmp(value,choices))
    error(identifier,'Expected one of: %s.',strjoin(choices,', '));
end
end
