function config = phyNetwork(name)
%PHYNETWORK Reusable source-backed PHY fixtures; receivers stay awake in T1.
% Per-flow rate/preamble/power can override the scenario radio setting.
if nargin == 0, name = 'clean'; end
name = char(name);
config = csr.scenario.smallNetwork();
config.Name = ['phy_' name];
config.Channel.Model = 'csr-phy';
% Match the source PHY constant; the T0 controlled fixture retains SI c.
config.Channel.PropagationSpeedMps = 3e8;
config.Trace.MaxPhyRecords = 20000;
profile = csr.phy.RadioProfile.defaults();
profile.TxBaseFrequencyHz = 400e6;
profile.RxBaseFrequencyHz = 400e6;
profile.StochasticSyncThreshold = false;
for index = 1:numel(config.Nodes)
    config.Nodes(index).RadioProfile = profile;
end
switch name
    case {'clean','overhearing'}
        % All six frames are decoded at intended peer and one other peer.
    case {'high_rate_500','high_rate_1000'}
        if strcmp(name,'high_rate_500'), config.Radio.RateKeyKbps = 500;
        else, config.Radio.RateKeyKbps = 1000; end
    case {'collision','mixed_rate'}
        config.Nodes(3).PositionMeters = [-100 0 1];
        for index = 1:numel(config.Traffic)
            config.Traffic(index).StartSeconds = 0.1;
            config.Traffic(index).PacketCount = 1;
        end
        if strcmp(name,'mixed_rate')
            config.Traffic(1).RateKeyKbps = 8;
            config.Traffic(2).RateKeyKbps = 16;
            config.Traffic(2).StartSeconds = 0.12;
        end
    case {'weak','band_mismatch','closure'}
        config.Nodes = config.Nodes(1:2);
        config.Traffic = config.Traffic(1);
        config.Traffic.PacketCount = 1;
        if strcmp(name,'weak')
            config.Nodes(2).RadioProfile.TxPowerDbm = -200;
        elseif strcmp(name,'band_mismatch')
            config.Nodes(1).RadioProfile.RxBaseFrequencyHz = 500e6;
        else
            config.Nodes(2).PositionMeters = [1e6 0 1];
        end
    otherwise
        error('csr:scenario:UnknownPhyFixture','Unknown PHY fixture: %s',name);
end
end
