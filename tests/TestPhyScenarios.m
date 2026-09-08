classdef TestPhyScenarios < matlab.unittest.TestCase
    % Behavioral scenario gates for the integrated network-level PHY.
    % These tests are prepared for real MATLAB; source/static checks do not
    % constitute execution of this class.
    methods (Test)
        function cleanLinksDeliverAndOverhearWithoutAppDuplication(test)
            result = csr.runScenario(csr.scenario.phyNetwork('clean'));
            stats = result.Statistics;
            test.verifyEqual(stats.Generated, 6);
            test.verifyEqual(stats.Transmitted, 6);
            test.verifyEqual(stats.Received, 6);
            test.verifyEqual(stats.Dropped, 0);
            test.verifyEqual(stats.Pending, 0);
            test.verifyEqual(stats.ApplicationBytesReceived, 384);
            test.verifyEqual(stats.PhysicalAttempts, 12);
            test.verifyEqual(stats.PhysicalReceived, 12);
            test.verifyEqual(stats.PhysicalDropped, 0);
            test.verifyEqual(stats.Overheard, 6);
            test.verifyEqual(stats.Collisions, 0);
            % Literal wire timing from source, including bare 32-byte envelope.
            packetDuration = (7888+48+8*(64+32)+32)*510e-6/4;
            test.verifyEqual(stats.MeanLatencySeconds, ...
                packetDuration + 150/3e8, 'AbsTol', 1e-11);
            TestPhyScenarios.verifyCompletedAccounting(test, stats);
        end

        function weakOutOfBandAndOccludedLinksCannotDeliver(test)
            cases = {'weak', 'band_mismatch', 'closure'};
            for k = 1:numel(cases)
                result = csr.runScenario(csr.scenario.phyNetwork(cases{k}));
                stats = result.Statistics;
                test.verifyEqual(stats.Generated, 1, cases{k});
                test.verifyEqual(stats.Transmitted, 1, cases{k});
                test.verifyEqual(stats.Received, 0, cases{k});
                test.verifyEqual(stats.Dropped, 1, cases{k});
                test.verifyEqual(stats.PhysicalAttempts, 1, cases{k});
                test.verifyEqual(stats.PhysicalReceived, 0, cases{k});
                test.verifyEqual(stats.PhysicalDropped, 1, cases{k});
                test.verifyEqual(stats.ApplicationBytesReceived, 0, cases{k});
                TestPhyScenarios.verifyCompletedAccounting(test, stats);
            end
        end

        function bothHighRateModesDeliverWithSourceTiming(test)
            cases = {'high_rate_500', 'high_rate_1000'};
            intervals = [8e-6, 4e-6];
            for k = 1:numel(cases)
                result = csr.runScenario(csr.scenario.phyNetwork(cases{k}));
                stats = result.Statistics;
                test.verifyEqual(stats.Received, 6, cases{k});
                test.verifyEqual(stats.PhysicalReceived, 12, cases{k});
                test.verifyEqual(stats.ApplicationBytesReceived, 384, cases{k});
                % Preamble/header remain at S0; only payload/FCS accelerate.
                expectedDuration = (7888+48)*510e-6/4 + ...
                    (8*(64+32)+32)*intervals(k)/4;
                test.verifyEqual(stats.MeanLatencySeconds, ...
                    expectedDuration + 150/3e8, 'AbsTol', 1e-11);
                TestPhyScenarios.verifyCompletedAccounting(test, stats);
            end
        end

        function overlapsReachCollisionAccountingAndKeepPacketCustody(test)
            cases = {'collision', 'mixed_rate'};
            for k = 1:numel(cases)
                result = csr.runScenario(csr.scenario.phyNetwork(cases{k}));
                stats = result.Statistics;
                test.verifyEqual(stats.Generated, 2, cases{k});
                test.verifyEqual(stats.Transmitted, 2, cases{k});
                test.verifyGreaterThan(stats.Collisions, 0, cases{k});
                test.verifyEqual(stats.PhysicalAttempts, 4, cases{k});
                TestPhyScenarios.verifyCompletedAccounting(test, stats);
                % BER/ECC decides selected-packet outcome. Collision alone is
                % deliberately not asserted to force a packet drop.
            end
        end

        function repeatedSeedReproducesInterferenceResults(test)
            config = csr.scenario.phyNetwork('mixed_rate');
            globalState = rng;
            first = csr.runScenario(config);
            second = csr.runScenario(config);
            test.verifyEqual(first.Trace, second.Trace);
            test.verifyEqual(first.PhyTrace, second.PhyTrace);
            test.verifyEqual(first.Statistics, second.Statistics);
            test.verifyEqual(rng, globalState);
        end

        function traceLimitsPreservePhysicalAndApplicationOutcomes(test)
            config = csr.scenario.phyNetwork('collision');
            full = csr.runScenario(config);
            config.Trace.MaxRecords = 1;
            config.Trace.MaxPhyRecords = 1;
            bounded = csr.runScenario(config);
            test.verifyLessThanOrEqual(height(bounded.Trace), 1);
            test.verifyLessThanOrEqual(height(bounded.PhyTrace), 1);
            fields = {'Generated', 'Received', 'Dropped', 'Pending', ...
                'PhysicalAttempts', 'PhysicalReceived', 'PhysicalDropped', ...
                'Collisions', 'Overheard'};
            for k = 1:numel(fields)
                test.verifyEqual(bounded.Statistics.(fields{k}), ...
                    full.Statistics.(fields{k}));
            end
        end

        function horizonKeepsUnfinishedPacketPending(test)
            config = csr.scenario.phyNetwork('clean');
            config.DurationSeconds = 0.2;
            result = csr.runScenario(config);
            test.verifyEqual(result.Statistics.Generated, 1);
            test.verifyEqual(result.Statistics.Transmitted, 1);
            test.verifyEqual(result.Statistics.Received, 0);
            test.verifyEqual(result.Statistics.Dropped, 0);
            test.verifyEqual(result.Statistics.Pending, 1);
        end
    end

    methods (Static, Access = private)
        function verifyCompletedAccounting(test, stats)
            test.verifyEqual(stats.Pending, 0);
            test.verifyEqual(stats.Generated, stats.Received + stats.Dropped);
            test.verifyEqual(stats.PhysicalAttempts, ...
                stats.PhysicalReceived + stats.PhysicalDropped);
        end
    end
end
