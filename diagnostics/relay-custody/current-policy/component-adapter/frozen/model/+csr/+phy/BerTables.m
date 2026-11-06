classdef BerTables
    % Exact ns-3 CSR modulation curves, including sparse implicit zero tails.
    % Source: CsrOpnetBerTables, pinned by data/ber_tables.json provenance.
    % All methods use base MATLAB. No toolbox or global RNG is required.

    methods (Static)
        function ber = lookup(name, effectiveSnrDb)
            % Convenience entry point for the three one-dimensional families.
            switch lower(char(name))
                case {'csr', 'standard'}
                    ber = csr.phy.BerTables.standard(effectiveSnrDb);
                case 'dpsk'
                    ber = csr.phy.BerTables.dpsk(effectiveSnrDb);
                case 'dqpsk'
                    ber = csr.phy.BerTables.dqpsk(effectiveSnrDb);
                otherwise
                    error('csr:phy:UnknownBerFamily', 'Unknown BER family: %s.', char(name));
            end
        end

        function ber = standard(effectiveSnrDb)
            data = csr.phy.BerTables.loadData();
            curve = data.Standard;
            ber = csr.phy.BerTables.interpolate(curve.Values, curve.SampleCount, ...
                curve.XStart, curve.XStep, effectiveSnrDb);
        end

        function ber = dpsk(effectiveSnrDb)
            % Exact recovered DPSK_PB law; 500 kbps has no separate table.
            validateattributes(effectiveSnrDb, {'numeric'}, {'real'});
            x = double(effectiveSnrDb);
            ber = 0.5 .* exp(-10 .^ (x ./ 10));
            ber(isnan(x) | x == -Inf) = 0.5;
            ber(x == Inf) = 0;
        end

        function ber = dqpsk(effectiveSnrDb)
            % Preserve supplied low-SNR values above 0.5, exactly as ns-3.
            data = csr.phy.BerTables.loadData();
            curve = data.Dqpsk;
            ber = csr.phy.BerTables.interpolate(curve.Values, curve.SampleCount, ...
                curve.XStart, curve.XStep, effectiveSnrDb);
        end

        function ber = collision(rateKbps, jsrDb, timeOffsetSeconds, effectiveSnrDb)
            % Same-rate spread-spectrum table, with source bucket semantics.
            % High-rate payloads must select dpsk/dqpsk in the PHY dispatcher.
            data = csr.phy.BerTables.loadData();
            layout = csr.phy.BerTables.rateLayout(data, rateKbps);
            bucket = csr.phy.BerTables.quantizeJsrDb(jsrDb);
            jsrIndex = find(data.JsrBuckets == bucket, 1) - 1;
            halfChip = csr.phy.BerTables.halfChipOffset(data, layout, timeOffsetSeconds);
            curve = layout.FirstCurve + jsrIndex * layout.HalfChipOffsetCount + halfChip;
            % Data offsets and curve IDs remain zero based; MATLAB indices do not.
            first = data.Collision.ValueOffsets(curve + 1);
            last = data.Collision.ValueOffsets(curve + 2);
            values = data.Collision.Values(first + 1:last);
            table = data.Collision;
            ber = csr.phy.BerTables.interpolate(values, table.SampleCount, ...
                table.XStart, table.XStep, effectiveSnrDb);
        end

        function bucket = quantizeJsrDb(jsrDb)
            validateattributes(jsrDb, {'numeric'}, {'real', 'scalar'});
            if jsrDb <= -10.5
                bucket = -12;
            elseif jsrDb <= -7.5
                bucket = -9;
            elseif jsrDb <= -4.5
                bucket = -6;
            elseif jsrDb <= -1.5
                bucket = -3;
            else
                % NaN intentionally selects bucket zero, matching C++ comparisons.
                bucket = 0;
            end
        end

        function chips = quantizeChipOffset(rateKbps, timeOffsetSeconds)
            data = csr.phy.BerTables.loadData();
            layout = csr.phy.BerTables.rateLayout(data, rateKbps);
            chips = csr.phy.BerTables.halfChipOffset(data, layout, timeOffsetSeconds) / 2;
        end

        function seconds = symbolDurationSeconds(rateKbps)
            if rateKbps == 500
                seconds = 4 / 500000;
            elseif rateKbps == 1000
                seconds = 4 / 1000000;
            else
                data = csr.phy.BerTables.loadData();
                layout = csr.phy.BerTables.rateLayout(data, rateKbps);
                seconds = layout.SymbolDurationSeconds;
            end
        end
    end

    methods (Static, Access = private)
        function data = loadData()
            persistent cached
            if isempty(cached)
                root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
                path = fullfile(root, 'data', 'ber_tables.json');
                if ~isfile(path)
                    error('csr:phy:MissingBerTables', 'Required BER data file is missing: %s.', path);
                end
                decoded = jsondecode(fileread(path));
                assert(strcmp(decoded.Schema, 'csr-ber-tables-v1'), ...
                    'csr:phy:InvalidBerTables', 'Unsupported BER table schema.');
                % jsondecode uses columns for JSON arrays; canonicalize once.
                decoded.Standard.Values = double(decoded.Standard.Values(:));
                decoded.Dqpsk.Values = double(decoded.Dqpsk.Values(:));
                decoded.Collision.Values = double(decoded.Collision.Values(:));
                decoded.Collision.ValueOffsets = double(decoded.Collision.ValueOffsets(:));
                decoded.JsrBuckets = double(decoded.JsrBuckets(:));
                cached = decoded;
            end
            data = cached;
        end

        function layout = rateLayout(data, rateKbps)
            validateattributes(rateKbps, {'numeric'}, {'real', 'scalar'});
            index = find([data.RateLayout.RateKbps] == rateKbps, 1);
            if isempty(index)
                % Source GetRateLayout falls back to the 8-kbps layout.
                index = 1;
            end
            layout = data.RateLayout(index);
        end

        function offset = halfChipOffset(data, layout, timeOffsetSeconds)
            validateattributes(timeOffsetSeconds, {'numeric'}, {'real', 'scalar'});
            if ~isfinite(timeOffsetSeconds)
                offset = 0;
                return
            end
            % rem has the signed remainder semantics of C++ fmod; mod does not.
            delta = rem(double(timeOffsetSeconds), layout.SymbolDurationSeconds);
            if delta < 0
                delta = delta + layout.SymbolDurationSeconds;
            end
            offset = floor(0.5 + delta / (data.ChipSeconds / 2));
            if offset == layout.HalfChipOffsetCount
                offset = 0;
            end
        end

        function ber = interpolate(values, sampleCount, xStart, xStep, x)
            validateattributes(x, {'numeric'}, {'real'});
            x = double(x);
            ber = zeros(size(x));
            xEnd = xStart + xStep * (sampleCount - 1);
            % This keeps NaN -> first sample, matching !(x > xStart).
            low = ~(x > xStart);
            high = x >= xEnd;
            ber(low) = csr.phy.BerTables.sparseValue(values, 0);
            ber(high) = csr.phy.BerTables.sparseValue(values, sampleCount - 1);
            middle = find(~low & ~high);
            for k = 1:numel(middle)
                index = middle(k);
                position = (x(index) - xStart) / xStep;
                nearest = round(position);
                tolerance = 8 * eps(1) * max(1, abs(position));
                if abs(position - nearest) <= tolerance
                    ber(index) = csr.phy.BerTables.sparseValue(values, nearest);
                else
                    lower = floor(position);
                    fraction = position - lower;
                    lowerValue = csr.phy.BerTables.sparseValue(values, lower);
                    upperValue = csr.phy.BerTables.sparseValue(values, lower + 1);
                    ber(index) = lowerValue + fraction * (upperValue - lowerValue);
                end
            end
        end

        function value = sparseValue(values, zeroBasedIndex)
            if zeroBasedIndex < numel(values)
                value = values(zeroBasedIndex + 1);
            else
                value = 0;
            end
        end
    end
end
