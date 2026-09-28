classdef Model
    %MODEL Source-backed network-level CSR propagation and receive errors.
    %   Behavioral reference: ns-3 model/csr-phy-model.h at 486d9e0.
    %   No Communications Toolbox or waveform simulation is required.
    %   Counter outputs are doubles containing integers, not MATLAB uints.
    %
    %   Interval allocation deliberately retains the current ns-3 behavior:
    %   truncate each header/payload interval independently, and retain the
    %   final interval's realized BER. This is not the reverted cumulative
    %   bit-boundary / header-rejection experiment. PacketErrorProbability
    %   is the probability of ANY protected-bit error, not post-ECC loss.

    properties (Constant)
        SpeedOfLightMetersPerSecond = 3e8
    end

    methods (Static)
        function result = frontEnd(txProfile, rxProfile, txPosition, rxPosition)
            % Power diagnostics and the separate pre-channel closure gate.
            tx = csr.phy.RadioProfile.validate(txProfile);
            rx = csr.phy.RadioProfile.validate(rxProfile);
            validateattributes(txPosition, {'numeric'}, ...
                {'real', 'finite', 'vector', 'numel', 3}, mfilename, 'txPosition');
            validateattributes(rxPosition, {'numeric'}, ...
                {'real', 'finite', 'vector', 'numel', 3}, mfilename, 'rxPosition');
            distance = norm(double(txPosition(:)) - double(rxPosition(:))) * ...
                rx.DistanceScale;
            csr.phy.Model.nonnegative(distance, 'distanceMeters');
            overlap = max(0, min(rx.RxBaseFrequencyHz + rx.RxBwHz, ...
                tx.TxBaseFrequencyHz + tx.TxBwHz) - ...
                max(rx.RxBaseFrequencyHz, tx.TxBaseFrequencyHz));
            noise = csr.phy.Model.dbmToWatts(rx.NoiseFloorDbm);
            if rx.ScaleNoiseWithBandwidth
                noise = noise * rx.RxBwHz / rx.NoiseReferenceBwHz;
            end
            [gain, pathloss, pathModel] = csr.phy.Model.pathGain(tx, rx, distance);
            inBand = csr.phy.Model.dbmToWatts(tx.TxPowerDbm) * overlap / tx.TxBwHz;
            power = 0;
            if overlap > 0 && gain > 0
                power = inBand * 10^(tx.TxAntennaGainDb / 10) * ...
                    gain * 10^(rx.RxAntennaGainDb / 10);
            end
            csr.phy.Model.nonnegative(power, 'receivedPowerWatts');
            csr.phy.Model.nonnegative(noise, 'backgroundNoiseWatts');
            result = struct('Closure', csr.phy.Model.hasClosure(tx, rx, distance), ...
                'ChannelMatched', overlap > 0, 'PathModel', pathModel, ...
                'DistanceMeters', distance, 'BandOverlapHz', overlap, ...
                'PathGainLinear', gain, 'PathlossDb', pathloss, ...
                'InBandTxPowerWatts', inBand, 'ReceivedPowerWatts', power, ...
                'ReceivedPowerDbm', csr.phy.Model.wattsToDbm(power), ...
                'BackgroundNoiseWatts', noise, 'NoisePowerWatts', noise, ...
                'NoisePowerDbm', csr.phy.Model.wattsToDbm(noise), ...
                'SnrDb', csr.phy.Model.snrDb(power, noise));
        end

        function interval = interval(startSec, endSec, noisePowerWatts)
            csr.phy.Model.nonnegative(startSec, 'startSec');
            csr.phy.Model.nonnegative(endSec, 'endSec');
            csr.phy.Model.nonnegative(noisePowerWatts, 'noisePowerWatts');
            if endSec < startSec
                error('csr:phy:InvalidInterval', 'Interval end precedes its start.');
            end
            interval = struct('StartSec', double(startSec), ...
                'EndSec', double(endSec), 'NoisePowerWatts', double(noisePowerWatts), ...
                'CollisionCount', 0, 'SameRateInterference', false, ...
                'JsrDb', -1000, 'TimeOffsetSeconds', 0, ...
                'HighRatePayloadJammer', false, 'HighRatePayloadJsrDb', -Inf);
        end

        function result = ber(rxProfile, frontEnd, rateKbps, interval)
            rx = csr.phy.RadioProfile.validate(rxProfile);
            csr.phy.Model.validateInterval(interval);
            headerDefinition = csr.phy.rateDefinition(8);
            payloadDefinition = csr.phy.rateDefinition(rateKbps);
            headerRate = headerDefinition.BitsPerSecond;
            payloadRate = payloadDefinition.BitsPerSecond;
            snr = csr.phy.Model.snrDb(frontEnd.ReceivedPowerWatts, ...
                interval.NoisePowerWatts);
            headerSnr = snr + 10 * log10(rx.RxBwHz / (2 * headerRate));
            payloadSnr = snr + 10 * log10(rx.RxBwHz / (2 * payloadRate));
            highRate = rateKbps == 500 || rateKbps == 1000;
            if highRate && interval.HighRatePayloadJammer
                jammer = frontEnd.ReceivedPowerWatts * ...
                    10^(interval.HighRatePayloadJsrDb / 10);
                payloadSnr = csr.phy.Model.snrDb(frontEnd.ReceivedPowerWatts, ...
                    interval.NoisePowerWatts + jammer) + ...
                    10 * log10(rx.RxBwHz / (2 * payloadRate));
            end
            if interval.CollisionCount == 0
                headerBer = csr.phy.BerTables.standard(headerSnr);
            else
                headerBer = csr.phy.BerTables.collision(8, interval.JsrDb, ...
                    interval.TimeOffsetSeconds, headerSnr);
            end
            if rateKbps == 500
                payloadBer = csr.phy.BerTables.dpsk(payloadSnr);
            elseif rateKbps == 1000
                payloadBer = csr.phy.BerTables.dqpsk(payloadSnr);
            elseif interval.CollisionCount > 0 && interval.SameRateInterference
                payloadBer = csr.phy.BerTables.collision(rateKbps, interval.JsrDb, ...
                    interval.TimeOffsetSeconds, payloadSnr);
            else
                payloadBer = csr.phy.BerTables.standard(payloadSnr);
            end
            result = struct('SnrDb', snr, 'HeaderEffectiveSnrDb', headerSnr, ...
                'PayloadEffectiveSnrDb', payloadSnr, ...
                'HeaderBer', headerBer, 'PayloadBer', payloadBer);
        end

        function result = allocateErrors(rxProfile, frontEnd, signalStartSec, ...
                preambleBits, packetBits, rateKbps, intervals, stream)
            % RandStream ownership belongs to the receiver. A scalar uniform
            % supplier function may be used for controlled differential tests.
            rx = csr.phy.RadioProfile.validate(rxProfile);
            csr.phy.Model.nonnegative(signalStartSec, 'signalStartSec');
            signalStartSec = double(signalStartSec);
            csr.phy.Model.bitCount(preambleBits, 'preambleBits');
            csr.phy.Model.bitCount(packetBits, 'packetBits');
            if ~isa(stream, 'RandStream') && ~isa(stream, 'function_handle')
                error('csr:phy:InvalidRandomStream', ...
                    'Supply an owned RandStream or scalar uniform supplier.');
            end
            result = struct('HeaderBits', 0, 'PayloadBits', 0, ...
                'HeaderErrors', 0, 'PayloadErrors', 0, 'TotalErrors', 0, ...
                'ActualBer', 0, 'HeaderBer', 0, 'PayloadBer', 0, ...
                'MinimumSnrDb', Inf, 'PeakNoisePowerWatts', 0, ...
                'PacketErrorProbability', 0);
            headerDefinition = csr.phy.rateDefinition(8);
            payloadDefinition = csr.phy.rateDefinition(rateKbps);
            headerRate = headerDefinition.BitsPerSecond;
            payloadRate = payloadDefinition.BitsPerSecond;
            headerStart = signalStartSec + double(preambleBits) / headerRate;
            payloadStart = signalStartSec + (double(preambleBits) + 48) / headerRate;
            packetEnd = payloadStart + ...
                max(0, double(packetBits) - double(preambleBits) - 48) / payloadRate;
            if isempty(intervals)
                result.MinimumSnrDb = -Inf;
                return
            end
            if ~isstruct(intervals)
                error('csr:phy:InvalidInterval', 'Intervals must be a struct array.');
            end
            for k = 1:numel(intervals)
                csr.phy.Model.validateInterval(intervals(k));
            end
            % MATLAB sort is stable; index ties are retained explicitly.
            [~, order] = sortrows([[intervals.StartSec].', (1:numel(intervals)).'], [1, 2]);
            noErrorProbability = 1;
            for index = order.'
                current = intervals(index);
                intervalEnd = min(current.EndSec, packetEnd);
                if intervalEnd < current.StartSec || current.StartSec >= packetEnd
                    continue
                end
                values = csr.phy.Model.ber(rx, frontEnd, rateKbps, current);
                result.HeaderBer = values.HeaderBer;
                result.PayloadBer = values.PayloadBer;
                result.MinimumSnrDb = min(result.MinimumSnrDb, values.SnrDb);
                result.PeakNoisePowerWatts = max(result.PeakNoisePowerWatts, ...
                    current.NoisePowerWatts);
                if intervalEnd < headerStart
                    result.ActualBer = values.HeaderBer;
                    continue
                end
                headerBegin = max(current.StartSec, headerStart);
                headerEnd = min(intervalEnd, payloadStart);
                % Do not add epsilon or round here: current ns-3 casts the
                % positive interval product directly to uint32_t (truncates).
                headerCount = floor(max(0, headerEnd - headerBegin) * headerRate);
                payloadBegin = max(current.StartSec, payloadStart);
                payloadCount = floor(max(0, intervalEnd - payloadBegin) * payloadRate);
                headerErrors = csr.phy.Model.drawBinomial( ...
                    headerCount, values.HeaderBer, stream);
                payloadErrors = csr.phy.Model.drawBinomial( ...
                    payloadCount, values.PayloadBer, stream);
                result.HeaderBits = result.HeaderBits + headerCount;
                result.PayloadBits = result.PayloadBits + payloadCount;
                result.HeaderErrors = result.HeaderErrors + headerErrors;
                result.PayloadErrors = result.PayloadErrors + payloadErrors;
                result.TotalErrors = result.TotalErrors + headerErrors + payloadErrors;
                noErrorProbability = noErrorProbability * ...
                    (1 - values.HeaderBer)^headerCount * ...
                    (1 - values.PayloadBer)^payloadCount;
                tested = headerCount + payloadCount;
                if tested > 0
                    result.ActualBer = (headerErrors + payloadErrors) / tested;
                elseif intervalEnd < payloadStart
                    result.ActualBer = values.HeaderBer;
                else
                    result.ActualBer = values.PayloadBer;
                end
            end
            if ~isfinite(result.MinimumSnrDb)
                result.MinimumSnrDb = -Inf;
            end
            result.PacketErrorProbability = min(1, max(0, 1 - noErrorProbability));
        end

        function errors = sampleSourceBinomial(bits, probability, uniform)
            % Inverse CDF with source complement behavior when p > 0.5.
            % No Statistics Toolbox, normal approximation, or Bernoulli loop.
            csr.phy.Model.bitCount(bits, 'bits');
            validateattributes(probability, {'numeric'}, ...
                {'scalar', 'real', 'finite', '>=', 0, '<=', 1});
            validateattributes(uniform, {'numeric'}, ...
                {'scalar', 'real', 'finite', '>=', 0, '<=', 1});
            bits = double(bits);
            probability = double(probability);
            if bits == 0 || probability <= 0
                errors = 0;
                return
            elseif probability >= 1
                errors = bits;
                return
            end
            inverted = probability > 0.5;
            p = min(probability, 1 - probability);
            target = min(double(uniform), 1 - eps(1) / 2);
            accumulated = 0;
            errors = bits;
            logFactorial = gammaln(bits + 1);
            for candidate = 0:bits
                logProbability = logFactorial - gammaln(candidate + 1) - ...
                    gammaln(bits - candidate + 1) + candidate * log(p) + ...
                    (bits - candidate) * log(1 - p);
                accumulated = accumulated + exp(logProbability);
                if accumulated >= target
                    errors = candidate;
                    break
                end
            end
            if inverted
                errors = bits - errors;
            end
        end

        function result = ecc(rxProfile, packetBits, preambleBits, totalErrors, ...
                priorAccepted, signalLocked, nodeFailed)
            % Earlier rejection or lock/failure cannot be rescued by ECC.
            if nargin < 5, priorAccepted = true; end
            if nargin < 6, signalLocked = false; end
            if nargin < 7, nodeFailed = false; end
            rx = csr.phy.RadioProfile.validate(rxProfile);
            csr.phy.Model.bitCount(packetBits, 'packetBits');
            csr.phy.Model.bitCount(preambleBits, 'preambleBits');
            csr.phy.Model.bitCount(totalErrors, 'totalErrors');
            validateattributes(priorAccepted, {'logical'}, {'scalar'});
            validateattributes(signalLocked, {'logical'}, {'scalar'});
            validateattributes(nodeFailed, {'logical'}, {'scalar'});
            protected = max(0, double(packetBits) - double(preambleBits));
            limit = floor(rx.EccThreshold * protected);
            result = struct('Accepted', false, 'EccDropped', false, ...
                'ProtectedBits', protected, 'CorrectableBits', limit);
            if (~priorAccepted && ~signalLocked) || nodeFailed || signalLocked
                return
            end
            result.Accepted = protected == 0 || double(totalErrors) <= limit;
            result.EccDropped = ~result.Accepted;
        end

        function watts = dbmToWatts(dbm)
            validateattributes(dbm, {'numeric'}, {'scalar', 'real', 'finite'});
            watts = 10^((double(dbm) - 30) / 10);
            csr.phy.Model.nonnegative(watts, 'convertedPowerWatts');
        end

        function dbm = wattsToDbm(watts)
            csr.phy.Model.nonnegative(watts, 'watts');
            dbm = -Inf;
            if watts > 0
                dbm = 10 * log10(double(watts)) + 30;
            end
        end

        function snr = snrDb(signalWatts, noiseWatts)
            csr.phy.Model.nonnegative(signalWatts, 'signalWatts');
            csr.phy.Model.nonnegative(noiseWatts, 'noiseWatts');
            snr = -Inf;
            if signalWatts > 0 && noiseWatts > 0
                snr = 10 * log10(double(signalWatts) / double(noiseWatts));
            end
        end
    end

    methods (Static, Access = private)
        function result = hasClosure(tx, rx, distance)
            if strcmp(rx.ClosureMode, 'NEVER_OCCLUDED')
                result = true;
            elseif strcmp(rx.ClosureMode, 'DELEGATE') && ~isempty(rx.ClosureDelegate)
                result = rx.ClosureDelegate(distance, tx.TxHeightMeters, rx.RxHeightMeters);
                if ~islogical(result) || ~isscalar(result)
                    error('csr:phy:InvalidClosureResult', ...
                        'ClosureDelegate must return a scalar logical.');
                end
            else
                % DELEGATE without a hook uses the ns-3 geometric fallback.
                txHorizon = sqrt(tx.TxHeightMeters * ...
                    (2 * rx.EarthRadiusMeters + tx.TxHeightMeters));
                rxHorizon = sqrt(rx.RxHeightMeters * ...
                    (2 * rx.EarthRadiusMeters + rx.RxHeightMeters));
                result = distance <= txHorizon + rxHorizon;
            end
        end

        function [gain, loss, name] = pathGain(tx, rx, distance)
            if distance <= 0
                gain = 1; loss = 0; name = 'UNIT_GAIN';
                return
            elseif strcmp(rx.PropagationModel, 'LOG_DISTANCE')
                name = 'LOG_DISTANCE';
                loss = rx.RefLossDb + 10 * rx.PathlossExp * log10(max(distance, 1e-6));
                gain = 10^(-loss / 10);
                csr.phy.Model.nonnegative(gain, 'pathGainLinear');
                return
            end
            centerFrequency = tx.TxBaseFrequencyHz + tx.TxBwHz / 2;
            wavelength = csr.phy.Model.SpeedOfLightMetersPerSecond / centerFrequency;
            distanceSquared = distance * distance;
            distanceFourth = distanceSquared * distanceSquared;
            heightProductSquared = tx.TxHeightMeters * tx.TxHeightMeters * ...
                rx.RxHeightMeters * rx.RxHeightMeters;
            candidates = [1, wavelength * wavelength / (16 * pi * pi * distanceSquared), ...
                heightProductSquared / distanceFourth, ...
                heightProductSquared * 1e18 / ...
                    (distanceFourth * centerFrequency * centerFrequency)];
            if any(isnan(candidates)) || any(candidates < 0)
                error('csr:phy:UnrepresentablePropagation', ...
                    'Radio geometry exceeds representable propagation arithmetic.');
            end
            [gain, index] = min(candidates);
            names = {'UNIT_GAIN', 'FREE_SPACE', 'FLAT_EARTH', 'AD_HOC_WLAN'};
            name = names{index};
            loss = Inf;
            if gain > 0, loss = -10 * log10(gain); end
        end

        function errors = drawBinomial(bits, probability, stream)
            if bits == 0 || probability <= 0
                errors = 0;
            elseif probability >= 1
                errors = bits;
            else
                if isa(stream, 'function_handle')
                    uniform = stream();
                else
                    uniform = rand(stream);
                end
                errors = csr.phy.Model.sampleSourceBinomial(bits, probability, uniform);
            end
        end

        function validateInterval(interval)
            required = {'StartSec', 'EndSec', 'NoisePowerWatts', 'CollisionCount', ...
                'SameRateInterference', 'JsrDb', 'TimeOffsetSeconds', ...
                'HighRatePayloadJammer', 'HighRatePayloadJsrDb'};
            if ~isstruct(interval) || ~isscalar(interval) || ...
                    ~all(isfield(interval, required))
                error('csr:phy:InvalidInterval', ...
                    'Use Model.interval to construct a complete scalar interval.');
            end
            csr.phy.Model.nonnegative(interval.StartSec, 'interval.StartSec');
            csr.phy.Model.nonnegative(interval.EndSec, 'interval.EndSec');
            csr.phy.Model.nonnegative(interval.NoisePowerWatts, 'interval.NoisePowerWatts');
            csr.phy.Model.bitCount(interval.CollisionCount, 'interval.CollisionCount');
            if interval.EndSec < interval.StartSec
                error('csr:phy:InvalidInterval', 'Interval end precedes its start.');
            end
            validateattributes(interval.TimeOffsetSeconds, {'numeric'}, ...
                {'scalar', 'real', 'finite'});
            validateattributes(interval.JsrDb, {'numeric'}, {'scalar', 'real', 'nonnan'});
            validateattributes(interval.HighRatePayloadJsrDb, {'numeric'}, ...
                {'scalar', 'real', 'nonnan'});
            validateattributes(interval.SameRateInterference, {'logical'}, {'scalar'});
            validateattributes(interval.HighRatePayloadJammer, {'logical'}, {'scalar'});
        end

        function nonnegative(value, name)
            validateattributes(value, {'numeric'}, ...
                {'scalar', 'real', 'finite', 'nonnegative'}, mfilename, name);
        end

        function bitCount(value, name)
            validateattributes(value, {'numeric'}, ...
                {'scalar', 'real', 'finite', 'integer', 'nonnegative', ...
                '<=', double(intmax('uint32'))}, mfilename, name);
        end
    end
end
