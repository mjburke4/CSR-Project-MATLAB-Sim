classdef TestContentionContract < matlab.unittest.TestCase
    properties (Access = private)
        Contract
    end
    methods (TestClassSetup)
        function executeContracts(testCase)
            testCase.Contract = csr.validation.contentionContract();
        end
    end
    methods (Test)
        function completeNativeContract(testCase)
            result = testCase.Contract;
            testCase.verifyTrue(result.Passed);
            testCase.verifyEqual(result.Schema,'csr-tranche10-contention-contract-v1');
            testCase.verifyEqual(result.CheckpointCount,279);
            testCase.verifyEqual(result.FailedCount,0);
            testCase.verifyEqual(result.UnmatchedCount,0);
            testCase.verifyEqual(numel(unique(string(result.Checkpoints.case))),15);
        end
        function computedFifteenthBoundaryUsesFutureSlot(testCase)
            testCase.verifyCase('idle_p15',16);
        end
        function literalBoundaryRetainsNextSlot(testCase)
            testCase.verifyCase('idle_literal',16);
        end
        function thirtiethBoundaryUsesFutureSlot(testCase)
            testCase.verifyCase('idle_p30',16);
        end
        function fiftyFirstBoundaryUsesFutureSlot(testCase)
            testCase.verifyCase('idle_p51',16);
        end
        function sixtiethBoundaryUsesFutureSlot(testCase)
            testCase.verifyCase('idle_p60',16);
        end
        function oneNanosecondBeforeKeepsImmediateNextBoundary(testCase)
            testCase.verifyCase('idle_before',16);
        end
        function oneNanosecondAfterKeepsFollowingBoundary(testCase)
            testCase.verifyCase('idle_after',16);
        end
        function searchArrivalWaitsForSharedTimer(testCase)
            testCase.verifyCase('search_initial',19);
        end
        function existingSyncAllowsPreparationButFreezesCounters(testCase)
            testCase.verifyCase('sync_initial',19);
        end
        function initialTrackPreparesImmediatelyOnSearch(testCase)
            testCase.verifyCase('track_initial',19);
        end
        function syncEpisodePreservesTimerPhase(testCase)
            testCase.verifyCase('sync_busy',23);
        end
        function trackEpisodePreservesTimerPhase(testCase)
            testCase.verifyCase('track_busy',23);
        end
        function earlierInsertedTrackOwnsTheSharedBoundary(testCase)
            testCase.verifyCase('track_tie_early',23);
        end
        function laterInsertedTrackFollowsTheExistingTick(testCase)
            testCase.verifyCase('track_tie_late',23);
        end
        function idleRestartsOneTimerWithoutOldEpochCallbacks(testCase)
            testCase.verifyCase('idle_restart',18);
        end
        function fractionalNanosecondPeriodKeepsContinuousClock(testCase)
            scheduler = csr.sim.EventScheduler();
            period = .0130000001;
            mac = makeMac(scheduler,period); mac.enqueue(dataFrame());
            expected = period;
            testCase.verifyEqual(scheduler.nextTime(),expected);
            for index = 1:3
                scheduler.run(expected);
                expected = expected+period;
                testCase.verifyEqual(scheduler.nextTime(),expected);
            end
        end
        function timeBeyondExactNanosecondHorizonKeepsContinuousClock(testCase)
            scheduler = csr.sim.EventScheduler(); scheduler.run(1e7);
            mac = makeMac(scheduler,.013); mac.enqueue(dataFrame());
            expected = 1e7+.013;
            testCase.verifyEqual(scheduler.nextTime(),expected);
            scheduler.run(expected);
            testCase.verifyEqual(scheduler.nextTime(),expected+.013);
        end
        function integralPeriodRoundsOnlyTheMacEpoch(testCase)
            scheduler = csr.sim.EventScheduler(); start = .1000000004;
            scheduler.run(start); mac = makeMac(scheduler,.013); mac.enqueue(dataFrame());
            testCase.verifyEqual(scheduler.Now,start);
            testCase.verifyEqual(scheduler.nextTime(),.113);
            scheduler.run(.113-1e-9); testCase.verifyFalse(mac.PreparationActive);
            scheduler.run(.113); testCase.verifyTrue(mac.PreparationActive);
        end
    end
    methods (Access = private)
        function verifyCase(testCase,name,count)
            rows = testCase.Contract.Checkpoints;
            selected = rows(string(rows.case)==name,:);
            testCase.verifyEqual(height(selected),count);
            testCase.verifyTrue(all(selected.pass));
        end
    end
end

function mac = makeMac(scheduler,period)
options = csr.mac.Layer.defaults(); options.DutyCycleEnabled = false;
options.SlotSeconds = period;
mac = csr.mac.Layer(1,scheduler,csr.sim.RandomStreams(129),options, ...
    struct('Transmit',@(~,~)[]));
end

function frame = dataFrame()
application = struct('Id',uint64(1),'SourceId',1,'DestinationId',2, ...
    'GeneratedSeconds',0,'ApplicationPayloadBytes',16,'Dscp',0);
frame = csr.hop.Frames.data(application,1,2,uint16(1), ...
    struct('EnvelopeProfile','bare','RateKeyKbps',128,'TxPowerDbm',33));
end
