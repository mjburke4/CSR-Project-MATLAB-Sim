function definition = rateDefinition(rateKbps)
%RATEDEFINITION Return the operational CSR rate, not a rounded rate label.
%   RateKeyKbps is the legacy configuration key. BitsPerSecond is derived
%   from the four-bit accounting interval and differs from key * 1000 for
%   keys 8 through 128. This interval is not a waveform symbol duration for
%   either high-rate mode.
%
%   Evidence: CSR-Project-NS3-part2, main 486d9e0,
%   model/csr-phy-model.h: CsrSymbolDurationSeconds, CsrRateKeyToBps,
%   CsrIsDpskRate, and CsrUsesDqpskBer; docs/opnet-phy-ber-ecc.md.
%   'CSR' identifies the source's legacy spread-rate modulation-table
%   family. This helper supplies timing/labels only; it does not model BER.

validateattributes(rateKbps, {'numeric'}, ...
    {'real', 'finite', 'scalar', 'integer', 'positive'}, ...
    mfilename, 'rateKbps');
rateKbps = double(rateKbps);
switch rateKbps
    case 8
        interval = 0.000510;
    case 16
        interval = 0.000254;
    case 32
        interval = 0.000126;
    case 64
        interval = 0.000062;
    case 128
        interval = 0.000030;
    case 500
        interval = 4 / 500000;
    case 1000
        interval = 4 / 1000000;
    otherwise
        error('csr:phy:UnsupportedRate', ...
            'Unsupported CSR rate key %g. Use 8, 16, 32, 64, 128, 500, or 1000.', ...
            rateKbps);
end

modulation = 'CSR';
if rateKbps == 500
    modulation = 'DPSK';
elseif rateKbps == 1000
    modulation = 'DQPSK';
end
definition = struct('RateKeyKbps', rateKbps, ...
    'BitsPerSecond', 4 / interval, ...
    'Modulation', modulation, ...
    'FourBitIntervalSeconds', interval);
end
