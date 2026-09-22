function config = macHopNetwork(name)
%MACHOPNETWORK Cohesive MAC/HOP fixtures using the actual CSR signal engine.
% Paths are explicit T2 forwarding inputs; they do not imply discovered routes.
if nargin == 0, name = 'reliable'; end
name = char(name);
config = csr.scenario.phyNetwork('clean');
config.Name = ['mac_hop_' name];
config.Stack = 'mac-hop';
config.DurationSeconds = 90;
config.Trace.MaxRecords = 50000;
config.Trace.MaxPhyRecords = 50000;
config.MaxEvents = 1000000;
config.NetworkQueueLimit = 512;
config.Mac = csr.mac.Layer.defaults();
config.Hop = csr.hop.Layer.defaults();
% The operational duty cycle, access timing and retry defaults remain active.
config.Traffic = config.Traffic(1);
config.Traffic.StartSeconds = 0.1;
config.Traffic.IntervalSeconds = 8;
config.Traffic.PacketCount = 6;
config.Traffic.Path = [2 1];
config.Traffic.Dscp = 0;
config.Traffic.AckRequired = true;
fault = struct('Kind','*','SourceId',-1,'DestinationId',-1, ...
    'First',1,'Count',1,'StartSeconds',0,'EndSeconds',Inf);
config.Faults = repmat(fault,0,1);
switch name
    case 'reliable'
        % Node 3 can overhear; all application delivery is addressed to node 1.
    case 'ack_loss'
        config.Traffic.PacketCount = 1;
        fault.Kind = 'ACK'; fault.SourceId = 1; fault.DestinationId = 2;
        fault.Count = 5; % Drop one complete MAC-owned ACK repetition budget.
        config.Faults = fault;
    case 'data_loss'
        config.Traffic.PacketCount = 1;
        fault.Kind = 'DATA'; fault.SourceId = 2; fault.DestinationId = 1;
        config.Faults = fault;
    case {'relay','dack'}
        config.Traffic.Path = [2 3 1];
        if strcmp(name,'dack')
            config.Traffic.PacketCount = 1;
            % Controlled low-threshold experiment: first relay custody produces
            % DACK. The default source threshold is 16 in ordinary scenarios.
            config.Hop.NsdpLimit = 0;
        end
    case 'collision'
        config.Traffic(2) = config.Traffic(1);
        config.Traffic(2).SourceId = 3;
        config.Traffic(2).Path = [3 1];
        config.Traffic(1).PacketCount = 3;
        config.Traffic(2).PacketCount = 3;
    case 'queue_pressure'
        config.NetworkQueueLimit = 2;
        config.Traffic.IntervalSeconds = 0.001;
        config.Traffic.PacketCount = 20;
    case {'high_rate_500','high_rate_1000'}
        if strcmp(name,'high_rate_500'), config.Radio.RateKeyKbps = 500;
        else, config.Radio.RateKeyKbps = 1000; end
    otherwise
        error('csr:scenario:UnknownMacHopFixture','Unknown MAC/HOP fixture: %s',name);
end
end
