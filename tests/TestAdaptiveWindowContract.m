classdef TestAdaptiveWindowContract < matlab.unittest.TestCase
    % Exercise production HOP methods with prescribed callbacks and timers.
    properties (Access = private)
        Contract
    end
    methods (TestClassSetup)
        function runOnce(test)
            directory = tempname;
            mkdir(directory);
            test.addTeardown(@()rmdir(directory,'s'));
            test.Contract = csr.validation.adaptiveWindowContract(directory);
        end
    end
    methods (Test)
        function allNativeCheckpointsMatch(test)
            test.verifyTrue(test.Contract.DiagnosticCompleted);
            test.verifyTrue(test.Contract.Passed);
            test.verifyEqual(test.Contract.CaseCount,9);
            test.verifyEqual(test.Contract.CheckpointCount,364);
            test.verifyEqual(test.Contract.FailedCount,0);
            test.verifyEqual(test.Contract.NativeComparison.MatchedRows,364);
        end
        function freshFlowAllowsExactlyOneOutstanding(test)
            test.verifyState('clean_growth_boundary',1, ...
                struct('threshold',0,'ack_count',0,'outstanding',0,'can_send',1));
            test.verifyState('clean_growth_boundary',4, ...
                struct('accepted',0,'outstanding',1,'can_send',0));
        end
        function thirdCleanAckGrowsThresholdAndAllowsTwo(test)
            test.verifyState('clean_growth_boundary',11, ...
                struct('threshold',1,'ack_count',0,'ack_total',3));
            test.verifyState('clean_growth_boundary',14, ...
                struct('accepted',1,'outstanding',2,'can_send',0));
            test.verifyState('clean_growth_boundary',16, ...
                struct('accepted',0,'outstanding',2));
        end
        function retriedThirdAckGrowsBeforeReset(test)
            test.verifyState('retried_third_ack',9,struct('retry_total',0));
            test.verifyState('retried_third_ack',10,struct('retry_total',1));
            test.verifyState('retried_third_ack',12, ...
                struct('threshold',1,'ack_count',0,'ack_total',3));
            test.verifyState('retried_third_ack',16,struct('threshold',1,'ack_count',1));
        end
        function retriedSecondAckResetsWithoutGrowth(test)
            test.verifyState('retried_second_ack',7, ...
                struct('threshold',0,'ack_count',0,'ack_total',2,'retry_total',1));
            test.verifyState('retried_second_ack',14,struct('threshold',0,'ack_count',2));
            test.verifyState('retried_second_ack',18,struct('threshold',1,'ack_count',0));
        end
        function ordinaryDackReleasesNsdpBeforeCapacity(test)
            test.verifyState('dack_hold_20',18,struct('threshold',1,'ack_count',0, ...
                'global_pending',1,'dack_holds',1,'resend',0,'nsdp_release_total',6));
            test.verifyState('dack_hold_20',21,struct('accepted',0,'outstanding',2));
            test.verifyState('dack_hold_20',23, ...
                struct('global_pending',1,'dack_holds',1,'nsdp_release_total',7));
            test.verifyState('dack_hold_20',24,struct('global_pending',0,'dack_holds',0, ...
                'dack_expired_total',1,'nsdp_release_total',7,'threshold',1,'ack_count',1));
        end
        function maximumRetryDackDoublesCapacityHold(test)
            test.verifyState('dack_hold_40',11, ...
                struct('dack_holds',1,'resend',0,'retry_total',2,'nsdp_release_total',3));
            test.verifyState('dack_hold_40',12,struct('dack_holds',1,'dack_expired_total',0));
            test.verifyState('dack_hold_40',13,struct('dack_holds',1,'global_pending',1));
            test.verifyState('dack_hold_40',14, ...
                struct('dack_holds',0,'global_pending',0,'dack_expired_total',1,'nsdp_release_total',3));
        end
        function finalFailureReleasesCapacityAndHonorsZeroFloor(test)
            test.verifyState('final_failure_floor',14,struct('fail_total',0,'outstanding',1));
            test.verifyState('final_failure_floor',15,struct('threshold',0,'ack_count',0, ...
                'fail_total',1,'global_pending',0,'nsdp_release_total',4));
            test.verifyState('final_failure_floor',20, ...
                struct('threshold',0,'fail_total',2,'global_pending',0,'nsdp_release_total',5));
            test.verifyState('final_failure_floor',21,struct('accepted',1,'outstanding',1));
        end
        function thresholdCeilingStillAllowsSeventeenEntries(test)
            test.verifyState('ceiling_global_capacity',153, ...
                struct('threshold',16,'ack_count',0,'ack_total',51));
            test.verifyState('ceiling_global_capacity',188, ...
                struct('accepted',0,'threshold',16,'outstanding',17,'global_pending',17));
        end
        function globalCapacityAndNeighborCapacityBlockIndependently(test)
            test.verifyState('ceiling_global_capacity',189, ...
                struct('peer',9,'threshold',0,'outstanding',0,'global_pending',17,'can_send',0));
            test.verifyState('ceiling_global_capacity',191, ...
                struct('accepted',1,'outstanding',1,'global_pending',17));
            test.verifyState('ceiling_global_capacity',193, ...
                struct('accepted',0,'threshold',16,'outstanding',16,'global_pending',17));
            test.verifyState('ceiling_global_capacity',195, ...
                struct('global_pending',1,'outstanding',1,'threshold',0,'can_send',0));
            test.verifyState('ceiling_global_capacity',196, ...
                struct('global_pending',0,'resend',0,'nsdp_release_total',69));
        end
        function newestFeedbackBitRunsFirstAndAckWinsOverlap(test)
            test.verifyState('grouped_feedback_order',20, ...
                struct('threshold',2,'ack_count',1,'ack_total',7,'dack_total',0));
            test.verifyState('grouped_feedback_order',25, ...
                struct('threshold',2,'ack_count',1,'ack_total',8,'dack_total',1,'dack_holds',1));
        end
        function repeatedFeedbackCannotReleaseOwnershipTwice(test)
            for step = [25 26 27]
                test.verifyState('grouped_feedback_order',step, ...
                    struct('ack_total',8,'dack_total',1,'dack_holds',1,'nsdp_release_total',9));
            end
            test.verifyState('grouped_feedback_order',28, ...
                struct('global_pending',0,'dack_holds',0,'dack_expired_total',1));
        end
        function observedFeedbackMotifPreservesGrowthBeforeRetryReset(test)
            test.verifyState('seed130_feedback_motif',30,struct('threshold',3,'ack_count',0, ...
                'ack_total',10,'retry_total',1,'global_pending',0,'nsdp_release_total',10));
        end
        function everyRowConservesOwnershipAndCapacity(test)
            rows = test.Contract.Checkpoints;
            test.verifyEqual(rows.global_pending,rows.resend+rows.dack_holds);
            completed = rows.ack_total+rows.dack_total+rows.fail_total;
            test.verifyEqual(rows.nsdp_release_total,completed);
            names = unique(string(rows.case_id),'stable');
            for index = 1:numel(names)
                selected = string(rows.case_id) == names(index);
                admitted = cumsum(rows.accepted(selected) == 1);
                test.verifyEqual(admitted,completed(selected)+rows.resend(selected));
            end
            test.verifyGreaterThanOrEqual(rows.threshold,zeros(height(rows),1));
            test.verifyLessThanOrEqual(rows.threshold,16*ones(height(rows),1));
            test.verifyGreaterThanOrEqual(rows.ack_count,zeros(height(rows),1));
            test.verifyLessThanOrEqual(rows.ack_count,2*ones(height(rows),1));
        end
        function productionRetryPolicyRemainsActualTx(test)
            test.verifyEqual(csr.hop.Layer.defaults().DataQueuedRetryPolicy,'actual-tx');
            test.verifyEqual(test.Contract.DataQueuedRetryPolicy,'actual-tx');
        end
    end
    methods (Access = private)
        function verifyState(test,caseId,step,expected)
            rows = test.Contract.Checkpoints;
            selected = string(rows.case_id) == string(caseId) & rows.step == step;
            test.assertEqual(sum(selected),1);
            fields = fieldnames(expected);
            for index = 1:numel(fields)
                field = fields{index};
                test.verifyEqual(rows.(field)(selected),double(expected.(field)), ...
                    sprintf('%s step %d field %s',caseId,step,field));
            end
        end
    end
end
