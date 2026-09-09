classdef TestNativeIntegration < matlab.unittest.TestCase
    % Optional suite. Portable validation must not discover native tests.
    methods (TestClassSetup)
        function requireNativeInstallation(~)
            csr.sim.native.requireAvailable();
        end
    end
    methods (Test)
        function nativeClockPreservesEventOrdering(test)
            scheduler = csr.sim.NativeScheduler();
            observations = [];
            scheduler.scheduleAt(0.1, @first);
            cancelled = scheduler.scheduleAt(0.1, @() record(99));
            scheduler.scheduleAt(0.1, @() record(2));
            scheduler.scheduleAt(0.4, @() record(4));
            test.verifyTrue(scheduler.cancel(cancelled));
            test.verifyFalse(scheduler.cancel(cancelled));
            test.verifyEqual(scheduler.PendingCount, 3);
            count = scheduler.run(0.5);
            test.verifyEqual(observations, [1 2 3 4]);
            test.verifyEqual(count, 4);
            test.verifyEqual(scheduler.PendingCount, 0);
            test.verifyEqual(scheduler.Now, 0.5);
            test.verifyError(@() scheduler.run(1), 'csr:sim:NativeSingleRun');

            function first()
                record(1);
                scheduler.scheduleAt(scheduler.Now, @() record(3));
            end
            function record(value)
                observations(end+1) = value;
            end
        end
        function nativeClockPreservesFiniteHorizon(test)
            scheduler = csr.sim.NativeScheduler();
            scheduler.scheduleAt(2, @() error('csr:test:Unexpected', 'Past horizon'));
            test.verifyEqual(scheduler.run(1), 0);
            test.verifyEqual(scheduler.PendingCount, 1);
            test.verifyEqual(scheduler.Now, 1);
        end
        function nativeClockExecutesAtExactHorizon(test)
            % Portable scheduler includes time == horizon. The native clock
            % must invoke these callbacks itself; its missed-event guard
            % must never be bypassed by a final portable drain.
            scheduler = csr.sim.NativeScheduler();
            observations = [];
            scheduler.scheduleAt(1, @atHorizon);
            scheduler.scheduleAt(2, @() record(99));
            count = scheduler.run(1);
            test.verifyEqual(observations, [1 2]);
            test.verifyEqual(count, 2);
            test.verifyEqual(scheduler.Now, 1);
            test.verifyEqual(scheduler.PendingCount, 1);

            function atHorizon()
                record(1);
                scheduler.scheduleAt(scheduler.Now, @() record(2));
            end
            function record(value)
                observations(end+1) = value;
            end
        end
        function nativeClockRunsControlledCSRScenario(test)
            config = csr.scenario.smallNetwork();
            portable = csr.runScenario(config);
            config.Backend = 'wireless-clock';
            wireless = csr.runScenario(config);
            test.verifyEqual(wireless.Statistics, portable.Statistics);
            test.verifyEqual(wireless.Trace, portable.Trace);
        end
        function nativeClockPreservesAutonomousRoutedNetwork(test)
            % R2026a-only optional gate: the native clock drives the same
            % autonomous NWK, MAC/HOP and CSR PHY model, not native packets.
            config = csr.scenario.routedNetwork('autonomous');
            config.Backend = 'portable';
            portable = csr.runScenario(config);
            config.Backend = 'wireless-clock';
            wireless = csr.runScenario(config);
            test.assertGreaterThan(portable.Statistics.Received,0);
            test.assertNotEmpty(portable.ProtocolTrace);
            test.assertNotEmpty(portable.PhyTrace);
            % Config.Backend and Metadata.RuntimeSeconds intentionally differ;
            % compare semantic outputs, never wall-clock/runtime metadata.
            test.verifyEqual(wireless.Statistics,portable.Statistics);
            test.verifyEqual(wireless.ProtocolTrace,portable.ProtocolTrace);
            test.verifyEqual(wireless.PhyTrace,portable.PhyTrace);
            test.verifyEqual(wireless.Routes,portable.Routes);
            test.verifyEqual(wireless.Neighbors,portable.Neighbors);
            test.verifyEqual(wireless.NodeStatistics,portable.NodeStatistics);
            test.verifyEqual(wireless.NodeMacStatistics,portable.NodeMacStatistics);
            test.verifyEqual(wireless.NodeNwkStatistics,portable.NodeNwkStatistics);
            test.verifyEqual(wireless.NodeHopStatistics,portable.NodeHopStatistics);
        end
        function nativePacketChannelLifecycle(test)
            report = csr.sim.native.probePacketTransport();
            test.verifyEqual(report.Status, 'passed');
            test.verifyEqual(report.Receiver.NumPacketsCompleted, 2);
            test.verifyEqual(report.Overhearer.NumPacketsCompleted, 2);
            test.verifyEqual(report.OffChannel.NumPacketsPushed, 0);
        end
    end
end
