function received = fixedProbeChannel(receiverInfo, transmitted, lossDb, speedMps)
%FIXEDPROBECHANNEL Controlled attenuation/delay for native API validation.
% This channel is solely an interface fixture; it does not replace CSR PHY.
received = transmitted;
for index = 1:numel(transmitted)
    packet = transmitted(index);
    distance = norm(packet.TransmitterPosition - receiverInfo.Position);
    delay = distance / speedMps;
    received(index).Power = packet.Power - lossDb;
    received(index).StartTime = packet.StartTime + delay;
    received(index).Metadata.Channel.PathGains = ...
        repmat(10^(-lossDb/20), [1 1 packet.NumTransmitAntennas ...
        receiverInfo.NumReceiveAntennas]);
    received(index).Metadata.Channel.PathDelays = delay;
    received(index).Metadata.Channel.PathFilters = 1;
    received(index).Metadata.Channel.SampleTimes = packet.StartTime;
end
end
