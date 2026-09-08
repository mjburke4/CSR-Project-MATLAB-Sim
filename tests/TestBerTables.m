classdef TestBerTables < matlab.unittest.TestCase
    % Independent expected values from csr-phy-ber-ecc-smoke.cc at 486d9e0.
    % Table generation and native C++ comparison do not execute these tests.

    methods (Test)
        function standardSourceGoldenSamples(testCase)
            x = [-20 -10 0 10 11.7 11.8];
            expected = [0.496806122489 0.466562489451 0.174688707266 ...
                8.2e-9 1e-12 0];
            testCase.verifyEqual(csr.phy.BerTables.standard(x), expected, 'AbsTol', 1e-15);
            testCase.verifyEqual(csr.phy.BerTables.lookup('csr', x), expected, 'AbsTol', 1e-15);
        end

        function highRateSourceGoldenSamples(testCase)
            x = [-20 -10 0 5 10];
            expected = [0.49502491687458405 0.45241870901797976 ...
                0.18393972058572117 0.021164609811602494 2.2699964881242427e-5];
            testCase.verifyEqual(csr.phy.BerTables.dpsk(x), expected, 'AbsTol', 1e-15);
            x = [-20 -10 0 5 10 16.25 20];
            expected = [0.658547624308 0.554134144522 0.204905205908 ...
                0.039282506101 0.000445472657 1e-12 0];
            testCase.verifyEqual(csr.phy.BerTables.dqpsk(x), expected, 'AbsTol', 1e-15);
            testCase.verifyGreaterThan(csr.phy.BerTables.dqpsk(-20), 0.5);
            testCase.verifyEqual(csr.phy.BerTables.dpsk([NaN -Inf Inf]), [0.5 0.5 0]);
        end

        function collisionSourceGoldenSamplesAcrossAllRates(testCase)
            % Columns: rate, JSR dB, offset seconds, effective SNR dB, BER.
            vectors = [8 -12 0 3.9794 0.019057765152; ...
                16 -9 127e-6 3.9794 0.017468631629; ...
                32 -3 63e-6 3.9794 0.020387961648; ...
                64 0 31e-6 3.9794 0.037136008523; ...
                128 0 0 -6.0206 0.421677468040];
            for k = 1:size(vectors, 1)
                row = vectors(k, :);
                actual = csr.phy.BerTables.collision(row(1), row(2), row(3), row(4));
                testCase.verifyEqual(actual, row(5), 'AbsTol', 1e-15);
            end
        end

        function interpolationClampAndSparseTailFollowSource(testCase)
            testCase.verifyEqual(csr.phy.BerTables.standard(-19.95), ...
                0.49676869544900004, 'AbsTol', 1e-14);
            testCase.verifyEqual(csr.phy.BerTables.standard([-100 100 NaN]), ...
                [0.496806122489 0 0.496806122489], 'AbsTol', 1e-15);
            testCase.verifyEqual(csr.phy.BerTables.collision(128, 0, 0, [-100 100 -5.5206]), ...
                [0.421677468040 0.250015536222 0.413053200462], 'AbsTol', 1e-14);
            % Exact table tail edge and halfway into first implicit zero.
            testCase.verifyEqual(csr.phy.BerTables.standard(11.7), 1e-12);
            testCase.verifyEqual(csr.phy.BerTables.standard(11.75), 0.5e-12, 'AbsTol', 1e-25);
            testCase.verifyEqual(csr.phy.BerTables.dqpsk(16.375), 0.5e-12);
            testCase.verifyEqual(csr.phy.BerTables.dqpsk([16.5 Inf]), [0 0]);
            testCase.verifySize(csr.phy.BerTables.standard(zeros(2, 3)), [2 3]);
            testCase.verifySize(csr.phy.BerTables.standard(zeros(0, 2)), [0 2]);
        end

        function jsrBoundaryQuantizationMatchesSource(testCase)
            x = [-1000 -10.500001 -10.5 -10.499999 -7.5 -7.499999 ...
                -4.5 -4.499999 -1.5 -1.499999 20 NaN -Inf Inf];
            expected = [-12 -12 -12 -9 -9 -6 -6 -3 -3 0 0 0 -12 0];
            for k = 1:numel(x)
                testCase.verifyEqual(csr.phy.BerTables.quantizeJsrDb(x(k)), expected(k));
            end
        end

        function circularTimingQuantizationMatchesSource(testCase)
            vectors = [128 0 0; 128 0.4999e-6 0; 128 0.5001e-6 0.5; ...
                128 1.5001e-6 1; 128 -0.4999e-6 0; 128 -0.5001e-6 14.5; ...
                128 30e-6 0; 8 509.5001e-6 0; 16 127e-6 63.5; ...
                128 NaN 0; 128 Inf 0];
            for k = 1:size(vectors, 1)
                testCase.verifyEqual(csr.phy.BerTables.quantizeChipOffset( ...
                    vectors(k, 1), vectors(k, 2)), vectors(k, 3));
            end
            expected = csr.phy.BerTables.collision(8, -12, 0, 3.9794);
            testCase.verifyEqual(csr.phy.BerTables.collision(999, -12, 0, 3.9794), expected);
        end

        function fourBitIntervalsAndExplicitDispatch(testCase)
            keys = [8 16 32 64 128 500 1000];
            expected = [510 254 126 62 30 8 4] * 1e-6;
            for k = 1:numel(keys)
                testCase.verifyEqual(csr.phy.BerTables.symbolDurationSeconds(keys(k)), ...
                    expected(k), 'AbsTol', 1e-18);
            end
            testCase.verifyEqual(csr.phy.BerTables.lookup('DPSK', 0), 0.18393972058572117, ...
                'AbsTol', 1e-15);
            testCase.verifyEqual(csr.phy.BerTables.lookup('DQPSK', 0), 0.204905205908);
            testCase.verifyError(@() csr.phy.BerTables.lookup('other', 0), ...
                'csr:phy:UnknownBerFamily');
        end
    end
end
