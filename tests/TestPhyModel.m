classdef TestPhyModel < matlab.unittest.TestCase
    % Source-defined physical and error semantics, independent of scheduler.
    % Prepared MATLAB tests; execution requires a real MATLAB installation.

    methods (Test)
        function sourceDefaultsAndInvalidProfiles(testCase)
            profile = csr.phy.RadioProfile.defaults();
            testCase.verifyEqual(profile.NoiseFloorDbm, -106.975);
            testCase.verifyEqual(profile.SyncSnrThresholdVarianceDb2, 0.25);
            testCase.verifyEqual(profile.PropagationModel, 'OPNET_THREE_PATH');
            testCase.verifyEqual(profile.EccThreshold, 0.1);
            testCase.verifyEqual(csr.phy.RadioProfile.validate(struct()), profile);
            testCase.verifyError(@() csr.phy.RadioProfile.validate( ...
                struct('TxPowerDBm', 22)), 'csr:phy:UnknownRadioAttribute');
            for name = {'TxBwHz', 'DistanceScale', 'EarthRadiusMeters'}
                candidate = profile;
                candidate.(name{1}) = 0;
                testCase.verifyError(@() csr.phy.RadioProfile.validate(candidate), ...
                    'csr:phy:InvalidRadioProfile');
            end
            for value = [-0.1, 1.1, NaN, Inf]
                profile.EccThreshold = value;
                testCase.verifyError(@() csr.phy.RadioProfile.validate(profile), ...
                    'csr:phy:InvalidRadioProfile');
            end
        end

        function defaultThreePathSelectsFlatEarth(testCase)
            profile = csr.phy.RadioProfile.defaults();
            result = csr.phy.Model.frontEnd(profile, profile, [0 0 0], [100 0 0]);
            % At 100 m and unit heights, min gain is hTx^2*hRx^2/d^4=1e-8.
            testCase.verifyEqual(result.PathModel, 'FLAT_EARTH');
            testCase.verifyEqual(result.PathGainLinear, 1e-8, 'RelTol', 1e-12);
            testCase.verifyEqual(result.PathlossDb, 80, 'AbsTol', 1e-12);
            testCase.verifyEqual(result.ReceivedPowerDbm, -80, 'AbsTol', 1e-12);
            testCase.verifyEqual(result.SnrDb, 26.975, 'AbsTol', 1e-10);
            testCase.verifyTrue(result.Closure && result.ChannelMatched);
        end

        function allPropagationBranchesAndDistanceScale(testCase)
            profile = csr.phy.RadioProfile.defaults();
            colocated = csr.phy.Model.frontEnd(profile, profile, [0 0 0], [0 0 0]);
            testCase.verifyEqual(colocated.PathModel, 'UNIT_GAIN');
            testCase.verifyEqual(colocated.ReceivedPowerDbm, 0, 'AbsTol', 1e-12);
            near = csr.phy.Model.frontEnd(profile, profile, [0 0 0], [1 0 0]);
            testCase.verifyEqual(near.PathModel, 'FREE_SPACE');
            profile.TxBaseFrequencyHz = 2.4e9;
            profile.RxBaseFrequencyHz = 2.4e9;
            far = csr.phy.Model.frontEnd(profile, profile, [0 0 0], [1000 0 0]);
            testCase.verifyEqual(far.PathModel, 'AD_HOC_WLAN');
            profile.PropagationModel = 'LOG_DISTANCE';
            profile.DistanceScale = 2;
            profile.PathlossExp = 3;
            logDistance = csr.phy.Model.frontEnd(profile, profile, [0 0 0], [5 0 0]);
            testCase.verifyEqual(logDistance.DistanceMeters, 10);
            testCase.verifyEqual(logDistance.PathModel, 'LOG_DISTANCE');
            testCase.verifyEqual(logDistance.PathlossDb, 90, 'AbsTol', 1e-12);
        end

        function passbandFractionGainAndNoiseAreIndependent(testCase)
            tx = csr.phy.RadioProfile.defaults();
            rx = tx;
            tx.TxPowerDbm = 22;
            tx.TxAntennaGainDb = 3;
            rx.RxAntennaGainDb = 4;
            rx.RxBaseFrequencyHz = 30.5e6;
            rx.RxBwHz = 0.5e6;
            result = csr.phy.Model.frontEnd(tx, rx, [0 0 0], [100 0 0]);
            testCase.verifyEqual(result.BandOverlapHz, 0.5e6);
            testCase.verifyEqual(result.ReceivedPowerDbm, ...
                22 + 3 + 4 - 80 + 10 * log10(0.5), 'AbsTol', 1e-10);
            testCase.verifyEqual(result.NoisePowerDbm, ...
                -106.975 + 10 * log10(0.5), 'AbsTol', 1e-10);
            rx.ScaleNoiseWithBandwidth = false;
            fixedNoise = csr.phy.Model.frontEnd(tx, rx, [0 0 0], [100 0 0]);
            testCase.verifyEqual(fixedNoise.NoisePowerDbm, -106.975, 'AbsTol', 1e-10);
            rx.RxBaseFrequencyHz = 31e6; % Touching band edges have no overlap.
            disjoint = csr.phy.Model.frontEnd(tx, rx, [0 0 0], [100 0 0]);
            testCase.verifyFalse(disjoint.ChannelMatched);
            testCase.verifyEqual(disjoint.ReceivedPowerWatts, 0);
            testCase.verifyEqual(disjoint.SnrDb, -Inf);
        end

        function closureIsSeparateFromPowerAndSupportsDelegate(testCase)
            profile = csr.phy.RadioProfile.defaults();
            occluded = csr.phy.Model.frontEnd(profile, profile, [0 0 0], [8000 0 0]);
            testCase.verifyFalse(occluded.Closure);
            testCase.verifyTrue(occluded.ChannelMatched);
            profile.ClosureMode = 'NEVER_OCCLUDED';
            visible = csr.phy.Model.frontEnd(profile, profile, [0 0 0], [8000 0 0]);
            testCase.verifyTrue(visible.Closure);
            profile.ClosureMode = 'DELEGATE';
            profile.ClosureDelegate = @(distance, txHeight, rxHeight) ...
                distance <= 50 && txHeight == 1 && rxHeight == 1;
            delegated = csr.phy.Model.frontEnd(profile, profile, [0 0 0], [100 0 0]);
            testCase.verifyFalse(delegated.Closure);
            profile.ClosureDelegate = [];
            fallback = csr.phy.Model.frontEnd(profile, profile, [0 0 0], [100 0 0]);
            testCase.verifyTrue(fallback.Closure);
        end

        function zeroHeightAndZeroPowerDiagnostics(testCase)
            profile = csr.phy.RadioProfile.defaults();
            profile.TxHeightMeters = 0;
            result = csr.phy.Model.frontEnd(profile, profile, [0 0 0], [100 0 0]);
            testCase.verifyEqual(result.PathGainLinear, 0);
            testCase.verifyEqual(result.PathlossDb, Inf);
            testCase.verifyEqual(result.ReceivedPowerDbm, -Inf);
            testCase.verifyEqual(csr.phy.Model.wattsToDbm(0), -Inf);
            testCase.verifyEqual(csr.phy.Model.snrDb(1, 0), -Inf);
        end

        function processingGainAndDifferentialModes(testCase)
            profile = csr.phy.RadioProfile.defaults();
            front = struct('ReceivedPowerWatts', 1);
            interval = csr.phy.Model.interval(0, 1, 1);
            dpsk = csr.phy.Model.ber(profile, front, 500, interval);
            dqpsk = csr.phy.Model.ber(profile, front, 1000, interval);
            spread = csr.phy.Model.ber(profile, front, 8, interval);
            testCase.verifyEqual(dpsk.PayloadEffectiveSnrDb, 0, 'AbsTol', 1e-12);
            testCase.verifyEqual(dqpsk.PayloadEffectiveSnrDb, ...
                -3.010299956639812, 'AbsTol', 1e-12);
            testCase.verifyEqual(spread.HeaderEffectiveSnrDb, ...
                10 * log10(63.75), 'AbsTol', 1e-12);
            testCase.verifyEqual(dpsk.HeaderBer, dqpsk.HeaderBer);
            testCase.verifyEqual(spread.HeaderBer, spread.PayloadBer);
            testCase.verifyEqual(dpsk.PayloadBer, csr.phy.BerTables.dpsk(0));
            testCase.verifyEqual(dqpsk.PayloadBer, ...
                csr.phy.BerTables.dqpsk(dqpsk.PayloadEffectiveSnrDb));
            testCase.verifyError(@() csr.phy.Model.ber(profile, front, 250, interval), ...
                'csr:phy:UnsupportedRate');
        end

        function differentRateCollisionStillUsesHeaderCollisionTable(testCase)
            profile = csr.phy.RadioProfile.defaults();
            front = struct('ReceivedPowerWatts', 1);
            interval = csr.phy.Model.interval(0, 1, 10^1.8);
            interval.CollisionCount = 1;
            interval.JsrDb = -3;
            interval.TimeOffsetSeconds = 10e-6;
            interval.SameRateInterference = false;
            different = csr.phy.Model.ber(profile, front, 128, interval);
            testCase.verifyEqual(different.HeaderBer, csr.phy.BerTables.collision( ...
                8, -3, 10e-6, different.HeaderEffectiveSnrDb));
            testCase.verifyEqual(different.PayloadBer, ...
                csr.phy.BerTables.standard(different.PayloadEffectiveSnrDb));
            interval.SameRateInterference = true;
            same = csr.phy.Model.ber(profile, front, 128, interval);
            testCase.verifyEqual(same.HeaderBer, different.HeaderBer);
            testCase.verifyEqual(same.PayloadBer, csr.phy.BerTables.collision( ...
                128, -3, 10e-6, same.PayloadEffectiveSnrDb));
        end

        function highRateJamAddsNoiseToPayloadOnly(testCase)
            profile = csr.phy.RadioProfile.defaults();
            front = struct('ReceivedPowerWatts', 1);
            clean = csr.phy.Model.interval(0, 1, 1);
            jammed = clean;
            jammed.HighRatePayloadJammer = true;
            jammed.HighRatePayloadJsrDb = 0;
            before = csr.phy.Model.ber(profile, front, 500, clean);
            after = csr.phy.Model.ber(profile, front, 500, jammed);
            testCase.verifyEqual(after.HeaderEffectiveSnrDb, before.HeaderEffectiveSnrDb);
            testCase.verifyEqual(after.HeaderBer, before.HeaderBer);
            testCase.verifyEqual(after.PayloadEffectiveSnrDb, ...
                -3.010299956639812, 'AbsTol', 1e-12);
            testCase.verifyGreaterThan(after.PayloadBer, before.PayloadBer);
        end

        function sourceBinomialUsesInclusiveCdfAndComplement(testCase)
            % Binomial(2,1/4) masses are 9/16,6/16,1/16.
            testCase.verifyEqual(csr.phy.Model.sampleSourceBinomial(2, 0.25, 0.5), 0);
            testCase.verifyEqual(csr.phy.Model.sampleSourceBinomial(2, 0.25, 0.8), 1);
            testCase.verifyEqual(csr.phy.Model.sampleSourceBinomial(2, 0.25, 0.99), 2);
            testCase.verifyEqual(csr.phy.Model.sampleSourceBinomial(2, 0.75, 0.5), 2);
            testCase.verifyEqual(csr.phy.Model.sampleSourceBinomial(2, 0.75, 0.8), 1);
            testCase.verifyEqual(csr.phy.Model.sampleSourceBinomial(17, 0, 1), 0);
            testCase.verifyEqual(csr.phy.Model.sampleSourceBinomial(17, 1, 0), 17);
            testCase.verifyEqual(csr.phy.Model.sampleSourceBinomial(0, 0.5, 0.5), 0);
        end

        function intervalTruncationAndFinalActualBerRemainSourceStyle(testCase)
            profile = csr.phy.RadioProfile.defaults();
            front = struct('ReceivedPowerWatts', 1);
            rate = 4 / 0.00051;
            start = 48 / rate;
            % Two 1.5-bit intervals test one bit each, dropping fractions.
            first = csr.phy.Model.interval(start, start + 1.5 / rate, 1e9);
            second = csr.phy.Model.interval(start + 1.5 / rate, start + 3 / rate, 1e-9);
            result = csr.phy.Model.allocateErrors(profile, front, 0, 0, 51, ...
                8, [second, first], @() 0.99); % Sorting is part of contract.
            testCase.verifyEqual(result.HeaderBits, 0);
            testCase.verifyEqual(result.PayloadBits, 2);
            testCase.verifyEqual(result.PayloadErrors, 1);
            testCase.verifyEqual(result.TotalErrors, 1);
            testCase.verifyEqual(result.ActualBer, 0); % Last interval, not 1/2.
            testCase.verifyEqual(result.MinimumSnrDb, -90, 'AbsTol', 1e-10);
            testCase.verifyEqual(result.PeakNoisePowerWatts, 1e9);
            testCase.verifyGreaterThan(result.PacketErrorProbability, 0);
        end

        function zeroErrorIntervalsPreserveRandomState(testCase)
            profile = csr.phy.RadioProfile.defaults();
            front = struct('ReceivedPowerWatts', 1);
            stream = RandStream('mt19937ar', 'Seed', 9001);
            state = stream.State;
            interval = csr.phy.Model.interval(0, 1, 1e-9);
            result = csr.phy.Model.allocateErrors(profile, front, 0, 0, 64, ...
                8, interval, stream);
            testCase.verifyEqual(result.TotalErrors, 0);
            testCase.verifyEqual(result.PacketErrorProbability, 0);
            testCase.verifyEqual(stream.State, state);
            testCase.verifyGreaterThan(result.HeaderBits + result.PayloadBits, 0);
        end

        function eccIncludesBoundaryAndCannotRescueEarlierRejection(testCase)
            profile = csr.phy.RadioProfile.defaults();
            boundary = csr.phy.Model.ecc(profile, 900, 100, 80);
            testCase.verifyTrue(boundary.Accepted);
            testCase.verifyFalse(boundary.EccDropped);
            testCase.verifyEqual(boundary.ProtectedBits, 800);
            testCase.verifyEqual(boundary.CorrectableBits, 80);
            excessive = csr.phy.Model.ecc(profile, 900, 100, 81);
            testCase.verifyFalse(excessive.Accepted);
            testCase.verifyTrue(excessive.EccDropped);
            earlier = csr.phy.Model.ecc(profile, 900, 100, 0, false, false, false);
            locked = csr.phy.Model.ecc(profile, 900, 100, 0, true, true, false);
            failed = csr.phy.Model.ecc(profile, 900, 100, 0, true, false, true);
            for result = [earlier, locked, failed]
                testCase.verifyFalse(result.Accepted);
                testCase.verifyFalse(result.EccDropped);
            end
            empty = csr.phy.Model.ecc(profile, 100, 100, 0);
            testCase.verifyTrue(empty.Accepted);
        end
    end
end
