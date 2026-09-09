function config = routedNetwork(name)
%ROUTEDNETWORK Autonomous ARL/admission fixtures using CSR MAC/HOP and PHY.
% The 150 m closure delegate creates a line topology without injecting paths
% or route tables. LinkEvents are deliberate diagnostic receive erasures.
if nargin == 0, name = 'autonomous'; end
name = char(name);
config = csr.scenario.phyNetwork('clean');
config.Name = ['network_' name];
config.Stack = 'network';
config.DurationSeconds = 300;
config.MaxEvents = 2000000;
config.Trace.MaxRecords = 100000;
config.Trace.MaxPhyRecords = 100000;
config.Mac = csr.mac.Layer.defaults();
config.Hop = csr.hop.Layer.defaults();
config.Nwk = csr.nwk.defaults();
% Tranche 3 is one atomic production-behavioral profile: DATA/ACK and the
% modeled control records all include their source-backed security byte count.
% Cryptographic processing remains deliberately outside this portable tranche.
config.Radio.EnvelopeProfile = 'pairwise16-size-only';
for index = 1:numel(config.Nodes)
    config.Nodes(index).PositionMeters = [(index-1)*100 0 1];
    config.Nodes(index).Capability = 1;
    config.Nodes(index).TransitForwardingEnabled = true;
    config.Nodes(index).RadioProfile.ClosureMode = 'DELEGATE';
    config.Nodes(index).RadioProfile.ClosureDelegate = @lineClosure;
end
config.Nodes(1).Capability = 2;
config.Traffic = struct('SourceId',3,'DestinationId',1, ...
    'StartSeconds',120,'IntervalSeconds',15,'PacketCount',3, ...
    'ApplicationPayloadBytes',64,'Dscp',0,'AckRequired',true);
fault = struct('Kind','*','SourceId',-1,'DestinationId',-1, ...
    'First',1,'Count',1,'StartSeconds',0,'EndSeconds',Inf,'ControlType','*');
config.Faults = repmat(fault,0,1);
config.LinkEvents = struct('TimeSeconds',{},'NodeIds',{},'Enabled',{});
config.DiscoveryEvents = struct('TimeSeconds',{},'NodeIds',{});
switch name
    case 'autonomous'
        % Gateway starts the source's sequential discovery workflow at 10 s.
    case 'no_route_custody'
        config.Traffic.StartSeconds = 0.1;
    case 'control_loss'
        fault.Kind = 'CONTROL'; fault.ControlType = 'ROUTING';
        config.Faults = fault;
    case 'route_recovery'
        config.DurationSeconds = 360;
        config.Nwk.Neighbor.FreshnessEnabled = true;
        config.LinkEvents = struct('TimeSeconds',{120,170}, ...
            'NodeIds',{2,2},'Enabled',{false,true});
        % An explicit administrative discovery request restarts the source
        % workflow after restoration; queueing DATA never starts discovery.
        config.DiscoveryEvents = struct('TimeSeconds',{110,180},'NodeIds',{1,1});
        config.Traffic.StartSeconds = 145;
        config.Traffic.IntervalSeconds = 30;
    case 'gateway'
        config.Nwk.SendOnlyToGateway = true;
        config.Traffic.DestinationId = 2;
    case 'leaf_no_transit'
        config.Nodes(2).Capability = 0;
        config.Nodes(2).TransitForwardingEnabled = false;
    case {'high_rate_500','high_rate_1000'}
        if strcmp(name,'high_rate_500'), rate = 500; else, rate = 1000; end
        config.Radio.RateKeyKbps = rate;
        config.Nwk.AdaptiveLinkControl = false;
        config.Nwk.Routing.LocalInfo.MinSpeedKbps = rate;
        config.Nwk.Routing.LocalInfo.MaxSpeedKbps = rate;
    otherwise
        error('csr:scenario:UnknownNetworkFixture','Unknown routed network fixture: %s.',name);
end
end

function visible = lineClosure(distanceMeters,~,~)
visible = distanceMeters <= 150;
end
