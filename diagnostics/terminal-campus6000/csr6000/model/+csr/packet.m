function frame = packet(id, flow, generatedSeconds, radio)
%PACKET Logical DATA frame; observation IDs never add on-air bytes.
% Source bare DATA payload: 17 MAC + 8 HOP + 7 NWK bytes (app + 32).
% This does not copy ns-3's compact CsrHeader storage envelope.
overhead = 32;
if strcmp(radio.EnvelopeProfile,'pairwise16-size-only'), overhead = overhead + 5; end
rate = radio.RateKeyKbps;
preamble = radio.Preamble;
power = [];
if isfield(flow,'RateKeyKbps') && ~isempty(flow.RateKeyKbps), rate = flow.RateKeyKbps; end
if isfield(flow,'Preamble') && ~isempty(flow.Preamble), preamble = flow.Preamble; end
if isfield(flow,'TxPowerDbm'), power = flow.TxPowerDbm; end
frame = struct('Id', id, 'SourceId', flow.SourceId, ...
    'DestinationId', flow.DestinationId, 'GeneratedSeconds', generatedSeconds, ...
    'ApplicationPayloadBytes', flow.ApplicationPayloadBytes, ...
    'WirePayloadBytes', double(flow.ApplicationPayloadBytes) + overhead, ...
    'RateKeyKbps', rate, 'Preamble', preamble, 'TxPowerDbm', power, ...
    'EnvelopeProfile', radio.EnvelopeProfile);
end
