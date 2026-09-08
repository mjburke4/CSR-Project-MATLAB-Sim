classdef TestFoundation < matlab.unittest.TestCase
    methods (Test)
        function smallNetworkAccounting(test)
            result = csr.runScenario();
            test.verifyEqual(result.Statistics.Generated, 6);
            test.verifyEqual(result.Statistics.Received, 6);
            test.verifyEqual(result.Statistics.Transmitted, 6);
            test.verifyEqual(result.Statistics.Dropped, 0);
            test.verifyEqual(result.Statistics.Pending, 0);
            test.verifyEqual(result.Statistics.ApplicationBytesReceived, 384);
            test.verifyEqual(result.Statistics.GoodputBitsPerSecond, 307.2, 'AbsTol', 1e-10);
            % Independent literal expectation: long preamble + S0 header + bare DATA/FCS.
            expectedAirtime = (7888 + 48 + 8*(64+32) + 32)*510e-6/4;
            expectedDelay = expectedAirtime + 150/299792458;
            test.verifyEqual(result.Statistics.MeanLatencySeconds, expectedDelay, 'AbsTol', 1e-12);
        end
        function finiteHorizonPreservesPending(test)
            config = csr.scenario.smallNetwork();
            config.DurationSeconds = 0.2;
            result = csr.runScenario(config);
            test.verifyEqual(result.Statistics.Generated, 1);
            test.verifyEqual(result.Statistics.Transmitted, 1);
            test.verifyEqual(result.Statistics.Pending, 1);
            test.verifyEqual(result.Statistics.Received, 0);
            test.verifyEqual(result.Statistics.Dropped, 0);
        end
        function allDropsRetainAccounting(test)
            config = csr.scenario.smallNetwork();
            config.Channel.FixedDropProbability = 1;
            result = csr.runScenario(config);
            test.verifyEqual(result.Statistics.Dropped, 6);
            test.verifyEqual(result.Statistics.Received, 0);
            test.verifyEqual(result.Statistics.Pending, 0);
        end
        function repeatedSeedReproducesTrace(test)
            config = csr.scenario.smallNetwork();
            config.Channel.FixedDropProbability = 0.4;
            first = csr.runScenario(config);
            second = csr.runScenario(config);
            test.verifyEqual(first.Trace, second.Trace);
            test.verifyEqual(first.Statistics, second.Statistics);
        end
        function loggingDoesNotAffectResults(test)
            config = csr.scenario.smallNetwork();
            full = csr.runScenario(config);
            config.Trace.MaxRecords = 2;
            bounded = csr.runScenario(config);
            test.verifyEqual(height(bounded.Trace), 2);
            test.verifyEqual(bounded.Statistics.OmittedTraceRecords, 16);
            test.verifyEqual(bounded.Statistics.Received, full.Statistics.Received);
            config.Trace.Enabled = false;
            disabled = csr.runScenario(config);
            test.verifyEqual(height(disabled.Trace), 0);
            test.verifyEqual(disabled.Statistics.Received, full.Statistics.Received);
        end
        function invalidEndpointRejected(test)
            config = csr.scenario.smallNetwork();
            config.Traffic(1).DestinationId = 999;
            test.verifyError(@() csr.runScenario(config), 'csr:scenario:Endpoint');
        end
        function singletonAndEmptyScenarioTables(test)
            config = csr.scenario.smallNetwork();
            config.Trace.MaxRecords = 1;
            result = csr.runScenario(config);
            test.verifyEqual(height(result.Trace), 1);
            test.verifyEqual(result.Statistics.OmittedTraceRecords, 17);
            config.Nodes = config.Nodes(1);
            config.Traffic = config.Traffic([]);
            result = csr.runScenario(config);
            test.verifyEqual(height(result.NodeStatistics), 1);
            test.verifyEqual(height(result.Trace), 0);
            test.verifyEqual(result.Statistics.Generated, 0);
            test.verifyTrue(isnan(result.Statistics.DeliveryRatio));
        end
        function serializesEachTransmitter(test)
            config = csr.scenario.smallNetwork();
            config.Traffic = config.Traffic(1);
            config.Traffic.IntervalSeconds = 0.01;
            result = csr.runScenario(config);
            tx = result.Trace(strcmp(result.Trace.Event, 'tx_start'), :);
            expectedDuration = (7888+48+8*96+32)*510e-6/4;
            test.verifyEqual(diff(tx.TimeSeconds), repmat(expectedDuration,2,1), 'AbsTol', 1e-12);
            test.verifyEqual(result.Statistics.Pending, 0);
        end
    end
end
