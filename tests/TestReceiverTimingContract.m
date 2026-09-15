classdef TestReceiverTimingContract < matlab.unittest.TestCase
    % Fixed physical stimuli with actual receiver/MAC state transitions.
    properties (Access = private)
        Contract
    end
    methods (TestClassSetup)
        function runOnce(test)
            directory = tempname;
            mkdir(directory);
            test.addTeardown(@()rmdir(directory,'s'));
            test.Contract = csr.validation.receiverTimingContract(directory);
        end
    end
    methods (Test)
        function allCheckpointsMatchNativeReference(test)
            test.verifyTrue(test.Contract.Passed);
            test.verifyEqual(test.Contract.UnmatchedCount,0);
            test.verifyEqual(test.Contract.FailedCount,0);
            test.verifyEqual(numel(unique(string(test.Contract.Checkpoints.('case')))),4);
        end
        function admittedPreambleWaitsForPeriodicWake(test)
            test.verifyCase('preamble_before_wake');
            test.verifyCheckpoint('preamble_before_wake','after_arrival','idle',1);
            test.verifyCheckpoint('preamble_before_wake','after_arrival','sync_present',1);
        end
        function arrivalAtWakeStillRequiresPropagationAndAcquisition(test)
            test.verifyCase('preamble_at_wake');
            test.verifyCheckpoint('preamble_at_wake','before_track','search',1);
            test.verifyCheckpoint('preamble_at_wake','after_track','track',1);
        end
        function acquisitionBeforeSleepKeepsReceiverBusy(test)
            test.verifyCase('preamble_after_wake');
            test.verifyCheckpoint('preamble_after_wake','after_first_sleep','idle',0);
            test.verifyCheckpoint('preamble_after_wake','before_end','track',1);
        end
        function sleepCancelsAcquisitionUntilNextWake(test)
            test.verifyCase('acquisition_canceled_by_sleep');
            test.verifyCheckpoint('acquisition_canceled_by_sleep','after_first_sleep','idle',1);
            test.verifyCheckpoint('acquisition_canceled_by_sleep','before_second_wake','idle',1);
            test.verifyCheckpoint('acquisition_canceled_by_sleep','after_track','track',1);
        end
        function deliveryPrecedesBackToSearchAndNoSignalSleep(test)
            names = unique(string(test.Contract.Checkpoints.('case')),'stable');
            for name = names'
                test.verifyCheckpoint(name,'delivery','track',1);
                test.verifyCheckpoint(name,'after_end','search',1);
                test.verifyCheckpoint(name,'before_sleep','search',1);
                test.verifyCheckpoint(name,'after_sleep','idle',1);
            end
        end
        function unchangedBerAndEccAreErrorFreeForControlledLink(test)
            names = unique(string(test.Contract.Checkpoints.('case')),'stable');
            for name = names'
                test.verifyCheckpoint(name,'delivery','success',1);
                test.verifyCheckpoint(name,'delivery','header_ber',0);
                test.verifyCheckpoint(name,'delivery','payload_ber',0);
                test.verifyCheckpoint(name,'delivery','header_errors',0);
                test.verifyCheckpoint(name,'delivery','payload_errors',0);
            end
        end
    end
    methods (Access = private)
        function verifyCase(test,name)
            rows = test.Contract.Checkpoints;
            selected = string(rows.('case')) == name;
            test.assertTrue(any(selected));
            test.verifyTrue(all(rows.pass(selected)));
        end
        function verifyCheckpoint(test,name,point,field,value)
            rows = test.Contract.Checkpoints;
            selected = string(rows.('case')) == name & ...
                string(rows.checkpoint) == point & string(rows.field) == field;
            test.assertEqual(sum(selected),1);
            test.verifyEqual(rows.actual(selected),double(value));
        end
    end
end
