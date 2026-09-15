classdef TestAckServiceContract < matlab.unittest.TestCase
    % Check the source-backed contract through real MATLAB MAC/HOP methods.
    properties (Access = private)
        Contract
    end
    methods (TestClassSetup)
        function runOnce(test)
            directory = tempname;
            mkdir(directory);
            test.addTeardown(@()rmdir(directory,'s'));
            test.Contract = csr.validation.ackServiceContract(directory);
        end
    end
    methods (Test)
        function allCheckpointsMatchNativeReference(test)
            test.verifyTrue(test.Contract.Passed);
            test.verifyEqual(test.Contract.UnmatchedCount,0);
            test.verifyEqual(test.Contract.FailedCount,0);
            test.verifyEqual(numel(unique(string(test.Contract.Checkpoints.('case')))),6);
        end
        function replacementKeepsOriginalHoldoffAndOpportunity(test)
            test.verifyCase('mac_ack_wait');
            test.verifyCheckpoint('mac_ack_wait','replaced','ack_queue',1);
            test.verifyCheckpoint('mac_ack_wait','after_tx','transmissions',1);
        end
        function syncFreezesCountdownWithoutRestartingHoldoff(test)
            test.verifyCase('mac_ack_sync');
            test.verifyCheckpoint('mac_ack_sync','frozen','counter',1);
            test.verifyCheckpoint('mac_ack_sync','after_tx','transmissions',1);
        end
        function trackReturnResumesSameReservation(test)
            test.verifyCase('mac_ack_track');
            test.verifyCheckpoint('mac_ack_track','resume','preparation',1);
            test.verifyCheckpoint('mac_ack_track','after_tx','transmissions',1);
        end
        function dataCancellationPreservesPreparedAckOpportunity(test)
            test.verifyCase('mac_cancel_then_ack');
            test.verifyCheckpoint('mac_cancel_then_ack','canceled','preparation',1);
            test.verifyCheckpoint('mac_cancel_then_ack','new_ack','preparation',1);
            test.verifyCheckpoint('mac_cancel_then_ack','after_tx','transmissions',1);
        end
        function controlCancellationPreservesPreparedAckOpportunity(test)
            test.verifyCase('mac_control_cancel_then_ack');
            test.verifyCheckpoint('mac_control_cancel_then_ack','canceled','preparation',1);
            test.verifyCheckpoint('mac_control_cancel_then_ack','after_tx','transmissions',1);
        end
        function capacityReleasePrecedesNsdpAndDeferredWake(test)
            test.verifyCase('hop_release_order');
            test.verifyCheckpoint('hop_release_order','nsdp_callback','pending',0);
            test.verifyCheckpoint('hop_release_order','nsdp_callback','resend_queue',1);
            test.verifyCheckpoint('hop_release_order','completed','releases',1);
            test.verifyCheckpoint('hop_release_order','before_tic','wakes',0);
            test.verifyCheckpoint('hop_release_order','after_tic','wakes',1);
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
