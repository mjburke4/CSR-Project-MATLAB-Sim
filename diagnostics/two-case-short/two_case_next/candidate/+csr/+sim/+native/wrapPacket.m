function packet = wrapPacket(frame, node, radio, startSeconds)
%WRAPPACKET Put a CSR logical frame in the documented R2026a PHY envelope.
% CSR SourceId/DestinationId remain in Data.CSRFrame. TransmitterID is the
% separately assigned native simulator ID. This adds no protocol behavior.
packet = wirelessPacket;
packet.TechnologyType = wnet.TechnologyType.Custom1;
packet.TransmitterID = node.ID;
packet.TransmitterPosition = node.Position;
packet.TransmitterVelocity = node.Velocity;
packet.NumTransmitAntennas = 1;
packet.StartTime = startSeconds;
packet.Duration = csr.phy.airtime(frame.WirePayloadBytes, ...
    frame.RateKeyKbps, frame.Preamble);
packet.Power = radio.TxPowerDbm;
if isfield(frame, 'TxPowerDbm') && ~isempty(frame.TxPowerDbm)
    packet.Power = frame.TxPowerDbm;
end
packet.CenterFrequency = radio.CenterFrequencyHz;
packet.Bandwidth = radio.BandwidthHz;
packet.Abstraction = true;
packet.SampleRate = radio.BandwidthHz;
packet.DirectToDestination = 0;
packet.Data = struct('CSRFrame', frame);
end
