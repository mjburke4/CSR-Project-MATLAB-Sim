classdef TestMacHopScenarios < matlab.unittest.TestCase
    % Integrated protocol gates; these require an actual MATLAB execution.
    methods (Test)
        function reliableExchangeCompletesLinkAndApplicationCustody(test)
            config = csr.scenario.macHopNetwork('reliable');
            result = csr.runScenario(config);
            stats = result.Statistics;
            test.verifyGreaterThan(stats.Generated, 0);
            test.verifyEqual(stats.Received, stats.Generated);
            test.verifyEqual(stats.Dropped, 0);
            test.verifyGreaterThan(stats.AcksReceived, 0);
            test.verifyGreaterThan(stats.ControlTransmissions, 0);
            test.verifyEqual(stats.UnconfirmedHopTransfers, 0);
            test.verifyEqual(stats.ApplicationBytesReceived, ...
                TestMacHopScenarios.expectedBytes(config));
            TestMacHopScenarios.verifyCompletedAccounting(test, result);
        end

        function ackLossRetriesWithoutDuplicateApplicationDelivery(test)
            result = csr.runScenario(csr.scenario.macHopNetwork('ack_loss'));
            stats = result.Statistics;
            test.verifyGreaterThan(stats.FaultDrops, 0);
            test.verifyGreaterThan(stats.Retransmissions, 0);
            test.verifyGreaterThan(stats.DuplicateData, 0);
            test.verifyEqual(stats.Received, stats.Generated);
            test.verifyEqual(stats.UnconfirmedHopTransfers, 0);
            test.verifyTrue(any(strcmp(result.ProtocolTrace.Event, 'hop_retry')));
            test.verifyTrue(any(strcmp(result.ProtocolTrace.Event, 'fault_drop')));
            TestMacHopScenarios.verifyCompletedAccounting(test, result);
        end

        function dataLossPreservesCustodyUntilRetrySucceeds(test)
            result = csr.runScenario(csr.scenario.macHopNetwork('data_loss'));
            stats = result.Statistics;
            test.verifyGreaterThan(stats.FaultDrops, 0);
            test.verifyGreaterThan(stats.Retransmissions, 0);
            test.verifyEqual(stats.Received, stats.Generated);
            test.verifyGreaterThan(stats.DataTransmissions, stats.Generated);
            test.verifyEqual(stats.UnconfirmedHopTransfers, 0);
            TestMacHopScenarios.verifyCompletedAccounting(test, result);
        end

        function dackDefersSenderReleaseWhileRelayCanDeliver(test)
            result = csr.runScenario(csr.scenario.macHopNetwork('dack'));
            stats = result.Statistics;
            test.verifyGreaterThan(stats.DacksReceived, 0);
            test.verifyGreaterThan(stats.RelayAccepted, 0);
            test.verifyEqual(stats.Received, stats.Generated);
            test.verifyEqual(stats.UnconfirmedHopTransfers, 0);
            trace = result.ProtocolTrace;
            held = trace(strcmp(trace.Event, 'hop_dack'), :);
            expired = trace(strcmp(trace.Event, 'hop_dack_expired'), :);
            test.assertGreaterThan(height(held), 0);
            test.assertGreaterThan(height(expired), 0);
            % The source DACK hold is 20 seconds. Match the same link packet;
            % feedback repeats must not produce immediate capacity release.
            for index = 1:height(expired)
                matches = held.PacketId == expired.PacketId(index) & ...
                    held.NodeId == expired.NodeId(index);
                test.assertTrue(any(matches));
                test.verifyGreaterThanOrEqual(expired.TimeSeconds(index) - ...
                    min(held.TimeSeconds(matches)), 20 - 1e-9);
            end
            TestMacHopScenarios.verifyCompletedAccounting(test, result);
        end

        function fixedPathCompletesTwoRealLinkTransactions(test)
            result = csr.runScenario(csr.scenario.macHopNetwork('relay'));
            stats = result.Statistics;
            test.verifyEqual(stats.Received, stats.Generated);
            test.verifyGreaterThanOrEqual(stats.RelayAccepted, stats.Generated);
            test.verifyGreaterThanOrEqual(stats.DataTransmissions, 2*stats.Generated);
            test.verifyEqual(stats.UnconfirmedHopTransfers, 0);
            trace = result.ProtocolTrace;
            receptions = trace(strcmp(trace.Event, 'hop_receive'), :);
            test.verifyTrue(any(receptions.NodeId == 3), 'Relay must receive through HOP.');
            test.verifyTrue(any(receptions.NodeId == 1 & receptions.PeerId == 3), ...
                'Destination must receive the relay link, not a direct overheard copy.');
            TestMacHopScenarios.verifyCompletedAccounting(test, result);
        end

        function simultaneousContendersRetainCompleteAccounting(test)
            result = csr.runScenario(csr.scenario.macHopNetwork('collision'));
            stats = result.Statistics;
            test.verifyGreaterThan(stats.Generated, 1);
            test.verifyGreaterThan(stats.Received, 0);
            test.verifyGreaterThan(stats.DataTransmissions, 0);
            % Slotted access may avoid overlap. Do not demand a PHY collision
            % merely because applications offered traffic simultaneously.
            test.verifyEqual(stats.UnconfirmedHopTransfers, 0);
            TestMacHopScenarios.verifyCompletedAccounting(test, result);
        end

        function queuePressureHasExplicitTerminalOutcomes(test)
            result = csr.runScenario(csr.scenario.macHopNetwork('queue_pressure'));
            stats = result.Statistics;
            test.verifyGreaterThan(stats.QueueDrops, 0);
            test.verifyGreaterThan(stats.Dropped, 0);
            test.verifyGreaterThan(stats.MaxNetworkQueueDepth, 0);
            test.verifyEqual(stats.UnconfirmedHopTransfers, 0);
            TestMacHopScenarios.verifyCompletedAccounting(test, result);
        end

        function highRateDataUsesTheSameReliabilityStack(test)
            names = {'high_rate_500', 'high_rate_1000'};
            rates = [500, 1000];
            for index = 1:numel(names)
                result = csr.runScenario(csr.scenario.macHopNetwork(names{index}));
                stats = result.Statistics;
                test.verifyEqual(stats.Received, stats.Generated, names{index});
                test.verifyGreaterThan(stats.AcksReceived, 0, names{index});
                test.verifyGreaterThan(stats.ControlTransmissions, 0, names{index});
                test.verifyEqual(result.Config.Traffic.RateKeyKbps, rates(index));
                test.verifyTrue(any(result.PhyTrace.RateKeyKbps == rates(index) & ...
                    result.PhyTrace.Success), 'High-rate signals must reach the PHY receive path.');
                test.verifyEqual(stats.UnconfirmedHopTransfers, 0, names{index});
                TestMacHopScenarios.verifyCompletedAccounting(test, result);
            end
        end

        function permanentFeedbackLossDoesNotReclassifyDeliveredData(test)
            config = csr.scenario.macHopNetwork('ack_loss');
            config.Traffic = config.Traffic(1);
            config.Traffic.PacketCount = 1;
            config.Faults = config.Faults(1);
            config.Faults.Kind = 'ACK';
            config.Faults.Count = Inf;
            config.DurationSeconds = 90;
            result = csr.runScenario(config);
            stats = result.Statistics;
            test.verifyEqual(stats.Generated, 1);
            test.verifyEqual(stats.Received, 1);
            test.verifyEqual(stats.Dropped, 0);
            test.verifyGreaterThan(stats.Retransmissions, 0);
            test.verifyGreaterThan(stats.HopFailures, 0);
            test.verifyGreaterThan(stats.UnconfirmedHopTransfers, 0);
            TestMacHopScenarios.verifyCompletedAccounting(test, result);
        end

        function repeatedSeedReproducesProtocolAndPhyWithoutGlobalRngChanges(test)
            config = csr.scenario.macHopNetwork('collision');
            before = rng;
            first = csr.runScenario(config);
            second = csr.runScenario(config);
            test.verifyEqual(first.Statistics, second.Statistics);
            test.verifyEqual(first.Trace, second.Trace);
            test.verifyEqual(first.PhyTrace, second.PhyTrace);
            test.verifyEqual(first.NodeMacStatistics, second.NodeMacStatistics);
            test.verifyEqual(first.NodeHopStatistics, second.NodeHopStatistics);
            test.verifyEqual(rng, before);
        end

        function traceBoundsDoNotChangeReliabilityOutcomes(test)
            config = csr.scenario.macHopNetwork('ack_loss');
            full = csr.runScenario(config);
            config.Trace.MaxRecords = 1;
            config.Trace.MaxPhyRecords = 1;
            bounded = csr.runScenario(config);
            test.verifyLessThanOrEqual(height(bounded.Trace), 1);
            test.verifyLessThanOrEqual(height(bounded.PhyTrace), 1);
            fields = {'Generated', 'Received', 'Dropped', 'Pending', ...
                'Retransmissions', 'AcksReceived', 'DacksReceived', 'DuplicateData', ...
                'QueueDrops', 'PhysicalAttempts', 'PhysicalReceived', 'PhysicalDropped', ...
                'FaultDrops', 'HopFailures', 'UnconfirmedHopTransfers'};
            for index = 1:numel(fields)
                test.verifyEqual(bounded.Statistics.(fields{index}), ...
                    full.Statistics.(fields{index}), fields{index});
            end
            test.verifyGreaterThan(bounded.Statistics.OmittedTraceRecords, 0);
        end

        function stoppingBeforeFirstPacketCompletesRetainsPendingCustody(test)
            config = csr.scenario.macHopNetwork('reliable');
            config.Traffic = config.Traffic(1);
            config.Traffic.StartSeconds = 0;
            config.Traffic.PacketCount = 1;
            config.DurationSeconds = 0.2;
            result = csr.runScenario(config);
            stats = result.Statistics;
            test.verifyEqual(stats.Generated, 1);
            test.verifyEqual(stats.Received, 0);
            test.verifyEqual(stats.Dropped, 0);
            test.verifyEqual(stats.Pending, 1);
        end
    end

    methods (Static, Access = private)
        function verifyCompletedAccounting(test, result)
            stats = result.Statistics;
            test.verifyEqual(stats.Pending, 0);
            test.verifyEqual(stats.Generated, stats.Received + stats.Dropped);
            test.verifyEqual(stats.PhysicalPending, 0);
            test.verifyEqual(stats.PhysicalAttempts, ...
                stats.PhysicalReceived + stats.PhysicalDropped);
            test.verifyGreaterThanOrEqual(stats.PhysicalAttempts, stats.PhysicalReceived);
            test.verifyGreaterThanOrEqual(stats.UnconfirmedHopTransfers, 0);
            test.verifyEqual(sum(result.NodeHopStatistics.PendingData), 0);
            test.verifyEqual(sum(result.NodeHopStatistics.ResendQueueDepth), 0);
            test.verifyEqual(sum(result.NodeHopStatistics.DackHoldCount), 0);
            test.verifyEqual(sum(result.NodeStatistics.PendingCustody), 0);
        end

        function bytes = expectedBytes(config)
            bytes = sum([config.Traffic.PacketCount] .* [config.Traffic.ApplicationPayloadBytes]);
        end
    end
end
