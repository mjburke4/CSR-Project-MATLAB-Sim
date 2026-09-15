classdef TestClockBoundaryContract < matlab.unittest.TestCase
    properties (Access = private)
        Contract
    end
    methods (TestClassSetup)
        function executeContract(testCase)
            testCase.Contract = csr.validation.clockBoundaryContract();
        end
    end
    methods (Test)
        function completesActualMacCounterContract(testCase)
            result = testCase.Contract;
            testCase.verifyTrue(result.DiagnosticCompleted);
            testCase.verifyTrue(result.Passed);
            testCase.verifyEqual(result.CaseCount,6);
            testCase.verifyEqual(result.EventCount,18);
            testCase.verifyEqual(result.CheckpointCount,72);
            testCase.verifyEqual(result.FailedCount,0);
            testCase.verifyEqual(result.Events.data_queue,ones(18,1));
            testCase.verifyEqual(result.Events.transmissions,zeros(18,1));
        end
        function earlierInsertionObservesCounterBeforeRealTick(testCase)
            testCase.verifyCounter('tie_early',[16;16;15],[16;16;15]);
        end
        function laterInsertionObservesExistingTickFirst(testCase)
            testCase.verifyCounter('tie_late',[15;15;15],[15;16;16]);
        end
        function oneNanosecondBeforePrecedesTick(testCase)
            testCase.verifyCounter('before',[16;16;15],[16;16;15]);
        end
        function oneNanosecondAfterFollowsTick(testCase)
            testCase.verifyCounter('after',[15;15;15],[15;16;16]);
        end
        function continuousIngressRetainsOneUlpResidual(testCase)
            result = testCase.Contract;
            row = result.Boundary(string(result.Boundary.case)=="continuous",:);
            testCase.verifyEqual(row.arrival_minus_tick_seconds,eps(2.011501));
            testCase.verifyNotEqual(string(row.arrival_seconds_hex),string(row.tick_seconds_hex));
            testCase.verifyCounter('continuous',[15;15;15],[15;16;16]);
            testCase.verifyTrue(result.ExpectedContinuousResidual);
            testCase.verifyFalse(result.MatchesNative);
            testCase.verifyEqual(result.UnmatchedCount,3);
        end
        function quantizedTransportRestoresTieWithoutChangingScheduler(testCase)
            result = testCase.Contract;
            row = result.Boundary(string(result.Boundary.case)=="quantized",:);
            testCase.verifyEqual(row.arrival_minus_tick_seconds,0);
            testCase.verifyTrue(row.transport_quantized);
            testCase.verifyEqual(string(row.arrival_seconds_hex),string(row.tick_seconds_hex));
            testCase.verifyCounter('quantized',[16;16;15],[16;16;15]);
            testCase.verifyFalse(result.GlobalClockChanged);
            scheduler = csr.sim.EventScheduler();
            arrival = 1.989 + csr.phy.airtime(48,128,'short') + .000001;
            scheduler.scheduleAt(arrival,@()[]);
            testCase.verifyEqual(scheduler.nextTime(),arrival);
            testCase.verifyGreaterThan(scheduler.nextTime(),2.011501);
        end
        function allFiveSharedIntegerCasesMatchNative(testCase)
            testCase.verifyTrue(testCase.Contract.SharedIntegerMatchesNative);
            rows = testCase.Contract.Boundary;
            testCase.verifyEqual(sum(rows.transport_quantized),1);
            testCase.verifyEqual(sum(rows.late_insertion),1);
        end
    end
    methods (Access = private)
        function verifyCounter(testCase,name,local,neighbor)
            rows = testCase.Contract.Events;
            rows = rows(string(rows.case)==name,:);
            testCase.verifyEqual(rows.order,[1;2;3]);
            testCase.verifyEqual(string(rows.phase),["ingress_before";"ingress_after";"settled"]);
            testCase.verifyEqual(rows.local_counter,local);
            testCase.verifyEqual(rows.neighbor_counter,neighbor);
        end
    end
end
