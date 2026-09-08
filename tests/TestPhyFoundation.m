classdef TestPhyFoundation < matlab.unittest.TestCase
    % Golden timing vectors from ns-3 486d9e0; run in MATLAB, not executed
    % by writing this file. Controlled loss tests do not validate CSR BER.

    methods (Test)
        function allOperationalRatesUseSourceIntervals(testCase)
            keys = [8 16 32 64 128 500 1000];
            intervals = [0.000510 0.000254 0.000126 0.000062 ...
                0.000030 0.000008 0.000004];
            bitRates = [7843.137254901961 15748.031496062993 ...
                31746.031746031746 64516.12903225806 ...
                133333.33333333334 500000 1000000];
            % Independent reference constants in csr-phy-ber-ecc-smoke.cc,
            % TestExactRates; ensure labels are never treated as exact bps.
            for k = 1:numel(keys)
                rate = csr.phy.rateDefinition(keys(k));
                testCase.verifyEqual(rate.RateKeyKbps, keys(k));
                testCase.verifyEqual(rate.FourBitIntervalSeconds, ...
                    intervals(k), 'AbsTol', 1e-15);
                testCase.verifyEqual(rate.BitsPerSecond, bitRates(k), ...
                    'AbsTol', 1e-9);
            end
            low = csr.phy.rateDefinition(8);
            medium = csr.phy.rateDefinition(500);
            high = csr.phy.rateDefinition(1000);
            testCase.verifyEqual(low.Modulation, 'CSR');
            testCase.verifyEqual(medium.Modulation, 'DPSK');
            testCase.verifyEqual(high.Modulation, 'DQPSK');
            testCase.verifyError(@() csr.phy.rateDefinition(250), ...
                'csr:phy:UnsupportedRate');
        end

        function knownPacketDurationsAtEveryRate(testCase)
            keys = [8 16 32 64 128 500 1000];
            % 100 modeled wire bytes, including whatever envelope the
            % scenario explicitly supplies. Reference durations in seconds.
            short = [0.125460 0.072212 0.045588 0.032276 ...
                0.025620 0.021044 0.020212];
            long = [1.117920 1.064672 1.038048 1.024736 ...
                1.018080 1.013504 1.012672];
            for k = 1:numel(keys)
                testCase.verifyEqual(csr.phy.airtime(100, keys(k), 'short'), ...
                    short(k), 'AbsTol', 1e-12);
                testCase.verifyEqual(csr.phy.airtime(100, keys(k), 'long'), ...
                    long(k), 'AbsTol', 1e-12);
            end
            % An empty wire payload still sends header and FCS.
            testCase.verifyEqual(csr.phy.airtime(0, 8, "short"), ...
                0.023460, 'AbsTol', 1e-12);
            testCase.verifyError(@() csr.phy.airtime(100, 8, 's'), ...
                'csr:phy:InvalidPreamble');
        end

        function propagationUsesDistanceAndConfiguredSpeed(testCase)
            channel = csr.phy.ControlledChannel();
            result = channel.evaluate([0 0 0], [3 4 0]);
            testCase.verifyEqual(result.DistanceMeters, 5);
            testCase.verifyEqual(result.DelaySeconds, 5 / 299792458);
            testCase.verifyTrue(result.Success);
            testCase.verifyEqual(result.Reason, 'success');
            slower = csr.phy.ControlledChannel(struct('PropagationSpeedMps', 10));
            delayed = slower.evaluate([0; 0], [3 4]);
            testCase.verifyEqual(delayed.DelaySeconds, 0.5);
            testCase.verifyError(@() channel.evaluate([0 0], [0 0 0]), ...
                'csr:phy:InvalidPosition');
        end

        function certainOutcomesDoNotConsumeRandomNumbers(testCase)
            stream = RandStream('mt19937ar', 'Seed', 73);
            state = stream.State;
            for probability = [0 1]
                channel = csr.phy.ControlledChannel( ...
                    struct('FixedDropProbability', probability));
                result = channel.evaluate([0 0 0], [1 0 0], stream);
                testCase.verifyEqual(result.Success, probability == 0);
                testCase.verifyEqual(stream.State, state);
                if probability == 1
                    testCase.verifyEqual(result.Reason, 'controlled_drop');
                end
            end
        end

        function explicitStreamsReproduceControlledLoss(testCase)
            channel = csr.phy.ControlledChannel( ...
                struct('FixedDropProbability', 0.5));
            first = RandStream('mt19937ar', 'Seed', 934);
            second = RandStream('mt19937ar', 'Seed', 934);
            globalState = rng;
            outcomes = false(1, 64);
            for k = 1:numel(outcomes)
                a = channel.evaluate([0 0], [10 0], first);
                b = channel.evaluate([0 0], [10 0], second);
                testCase.verifyEqual(a, b);
                outcomes(k) = a.Success;
            end
            testCase.verifyTrue(any(outcomes) && any(~outcomes));
            testCase.verifyEqual(rng, globalState);
            testCase.verifyError(@() channel.evaluate([0 0], [10 0]), ...
                'csr:phy:MissingRandomStream');
        end
    end
end
