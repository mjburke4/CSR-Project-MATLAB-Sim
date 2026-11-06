function seconds = airtime(wirePayloadBytes, rateKbps, preambleType)
%AIRTIME Compute the source-backed CSR on-air packet duration in seconds.
%   wirePayloadBytes is explicitly the modeled wire payload supplied by the
%   caller, including any modeled protocol/security envelope bytes. It must
%   exclude the preamble, 48-bit S0 header, and 32-bit FCS added here.
%   This helper does not serialize a CSR packet or infer envelope sizes.
%
%   Evidence: CSR-Project-NS3-part2, main 486d9e0,
%   model/csr-net-device.h, SendFramesToPeers payloadBytes/duration calculation.
%   The preamble (7888 long or 104 short bits), SOF, speed, and length use
%   S0: four bits per 510 microseconds. Payload plus FCS uses the exact
%   payload rate. The accounting is the same for all seven rate keys.

validateattributes(wirePayloadBytes, {'numeric'}, ...
    {'real', 'finite', 'scalar', 'integer', 'nonnegative', ...
    '<=', floor((flintmax - 32) / 8)}, mfilename, 'wirePayloadBytes');
if isstring(preambleType) && isscalar(preambleType)
    preambleType = char(preambleType);
end
if ~ischar(preambleType) || ~isrow(preambleType)
    error('csr:phy:InvalidPreamble', 'preambleType must be ''long'' or ''short''.');
end
switch preambleType
    case 'long'
        preambleBits = 7888;
    case 'short'
        preambleBits = 104;
    otherwise
        error('csr:phy:InvalidPreamble', 'preambleType must be ''long'' or ''short''.');
end

rate = csr.phy.rateDefinition(rateKbps);
s0Seconds = (preambleBits + 48) / 4 * 0.000510;
payloadSeconds = (double(wirePayloadBytes) * 8 + 32) / rate.BitsPerSecond;
seconds = s0Seconds + payloadSeconds;
end
