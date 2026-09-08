classdef TestMacHopCustody < matlab.unittest.TestCase
    % Regression fixtures for queue wake and end-to-end custody boundaries.
    % Parameter overrides isolate structural failures; operational defaults in
    % macHopNetwork are unchanged. These tests require actual MATLAB execution.
    methods (Test)
        function macDequeueAdmitsAnotherPeerBeforeFeedbackArrives(test)
            config = csr.scenario.macHopNetwork('reliable');
            config.Mac.DutyCycleEnabled = false;
            config.Mac.DataQueueLimit = 1;
            config.Mac.ConcatenationEnabled = false;
            config.Traffic(1).PacketCount = 1;
            config.Traffic(2) = config.Traffic(1);
            config.Traffic(2).DestinationId = 3;
            config.Traffic(2).Path = [2 3];
            result = csr.runScenario(config);
            trace = result.ProtocolTrace;
            transmissions = trace(strcmp(trace.Event, 'tx_start') & trace.NodeId == 2, :);
            submissions = trace(strcmp(trace.Event, 'network_submit') & ...
                trace.NodeId == 2 & trace.PeerId == 3, :);
            feedback = trace(strcmp(trace.Event, 'hop_ack') & ...
                trace.NodeId == 2 & trace.PeerId == 1, :);
            test.assertGreaterThan(height(transmissions), 0);
            test.assertGreaterThan(height(submissions), 0);
            test.assertGreaterThan(height(feedback), 0);
            test.verifyEqual(submissions.TimeSeconds(1), transmissions.TimeSeconds(1));
            test.verifyLessThan(submissions.TimeSeconds(1), feedback.TimeSeconds(1));
            % Establish that the second peer really encountered the full MAC
            % queue before dequeue caused its same-time re-admission.
            source = result.NodeHopStatistics(result.NodeHopStatistics.NodeId == 2, :);
            test.verifyGreaterThan(source.MacAdmissionRejected, 0);
            test.verifyEqual(result.Statistics.Generated, 2);
            test.verifyEqual(result.Statistics.Received, 2);
            test.verifyEqual(result.Statistics.Dropped, 0);
            TestMacHopCustody.verifyDrained(test, result);
        end

        function dackRetryCannotMoveOnwardCustodyBackToEarlierRelay(test)
            config = csr.scenario.macHopNetwork('relay');
            config.Nodes(4) = config.Nodes(3);
            config.Nodes(4).Id = 4;
            config.Nodes(4).PositionMeters = [100 200 1];
            config.Traffic.PacketCount = 1;
            config.Traffic.Path = [2 3 4 1];
            config.Mac.DutyCycleEnabled = false;
            config.Mac.ConcatenationEnabled = false;
            config.Mac.AckTransmissions = 1;
            config.Hop.NsdpLimit = 0;
            % The extra resend interval lets the second relay take custody
            % before the source retries its unconfirmed first-hop DATA.
            config.Hop.ResendSeconds = 6;
            fault = struct('Kind', 'DACK', 'SourceId', 3, 'DestinationId', 2, ...
                'First', 1, 'Count', Inf, 'StartSeconds', 0, 'EndSeconds', Inf);
            config.Faults = [fault, fault];
            config.Faults(2).Kind = 'DATA';
            config.Faults(2).SourceId = 4;
            config.Faults(2).DestinationId = 1;
            result = csr.runScenario(config);
            stats = result.Statistics;
            trace = result.ProtocolTrace;
            accepts = trace(strcmp(trace.Event, 'relay_accept'), :);
            onward = accepts(accepts.NodeId == 4, :);
            retries = trace(strcmp(trace.Event, 'hop_retry') & trace.NodeId == 2, :);
            repeatReceives = trace(strcmp(trace.Event, 'hop_receive') & ...
                trace.NodeId == 3 & trace.PeerId == 2, :);
            drops = trace(strcmp(trace.Event, 'app_drop'), :);
            test.assertEqual(height(onward), 1);
            test.assertGreaterThan(height(retries), 0);
            test.verifyTrue(any(retries.TimeSeconds > onward.TimeSeconds(1)), ...
                'The fixture must retry the earlier hop after node 4 accepts custody.');
            test.verifyTrue(any(repeatReceives.TimeSeconds > onward.TimeSeconds(1)), ...
                'Node 3 must actually receive the earlier-hop retry after custody moved onward.');
            test.verifyEqual(height(accepts), 2);
            test.verifyEqual(stats.RelayAccepted, 2);
            test.verifyEqual(sort(accepts.NodeId), [3; 4]);
            test.assertEqual(height(drops), 1);
            test.verifyEqual(drops.NodeId, 4);
            test.verifyEqual(stats.Generated, 1);
            test.verifyEqual(stats.Received, 0);
            test.verifyEqual(stats.Dropped, 1);
            test.verifyGreaterThan(stats.FaultDrops, 0);
            TestMacHopCustody.verifyDrained(test, result);
        end

        function longFinalAttemptCanArriveAfterSenderExpiration(test)
            config = csr.scenario.macHopNetwork('data_loss');
            config.Mac.DutyCycleEnabled = false;
            config.Mac.ConcatenationEnabled = false;
            config.Traffic.ApplicationPayloadBytes = 4096;
            config.Faults.Count = 2;
            config.DurationSeconds = 90;
            result = csr.runScenario(config);
            stats = result.Statistics;
            trace = result.ProtocolTrace;
            drops = trace(strcmp(trace.Event, 'app_drop'), :);
            deliveries = trace(strcmp(trace.Event, 'app_receive'), :);
            test.verifyGreaterThan(csr.phy.airtime(4096 + 32, 8, 'long'), ...
                2*config.Hop.ResendSeconds);
            test.assertEqual(height(drops), 1);
            test.assertEqual(height(deliveries), 1);
            test.verifyEqual(drops.PacketId, deliveries.PacketId);
            test.verifyGreaterThan(deliveries.TimeSeconds, drops.TimeSeconds);
            test.verifyEqual(stats.Generated, 1);
            test.verifyEqual(stats.Received, 1);
            test.verifyEqual(stats.Dropped, 0);
            test.verifyEqual(stats.LateDeliveries, 1);
            test.verifyEqual(stats.ApplicationBytesReceived, 4096);
            test.verifyEqual(stats.FaultDrops, 2);
            test.verifyEqual(sum(result.NodeStatistics.Dropped), 0);
            test.verifyEmpty(fieldnames(stats.DropReasons));
            TestMacHopCustody.verifyDrained(test, result);
        end
    end

    methods (Static, Access = private)
        function verifyDrained(test, result)
            stats = result.Statistics;
            test.verifyEqual(stats.Pending, 0);
            test.verifyEqual(stats.Generated, stats.Received + stats.Dropped);
            test.verifyEqual(stats.PhysicalPending, 0);
            test.verifyEqual(stats.PhysicalAttempts, stats.PhysicalReceived + stats.PhysicalDropped);
            test.verifyEqual(sum(result.NodeStatistics.PendingCustody), 0);
            test.verifyEqual(sum(result.NodeHopStatistics.PendingData), 0);
            test.verifyEqual(sum(result.NodeHopStatistics.ResendQueueDepth), 0);
            test.verifyEqual(sum(result.NodeHopStatistics.DackHoldCount), 0);
        end
    end
end
