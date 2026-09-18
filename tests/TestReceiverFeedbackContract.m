classdef TestReceiverFeedbackContract < matlab.unittest.TestCase
    % Verify common controlled milestones without hiding diagnostic deltas.
    properties (Access = private)
        Contract
        InputContract
        OutputDirectory
    end
    methods (TestClassSetup)
        function runOnce(test)
            root = fileparts(fileparts(mfilename('fullpath')));
            directory = tempname;
            mkdir(directory);
            test.addTeardown(@()rmdir(directory,'s'));
            test.OutputDirectory = directory;
            test.Contract = csr.validation.receiverFeedbackContract(directory,root);
            test.InputContract = jsondecode(fileread(fullfile(root,'scenarios','t23','contract.json')));
        end
    end
    methods (Test)
        function allControlledActionsComplete(test)
            test.verifyTrue(test.Contract.DiagnosticCompleted);
            test.verifyEqual(test.Contract.CaseCount,7);
            test.verifyEqual(test.Contract.CheckpointCount,123);
            test.verifyEqual(test.Contract.CaseCount,test.InputContract.case_count);
            test.verifyEqual(test.Contract.CheckpointCount,test.InputContract.action_count);
            test.verifyTrue(test.Contract.NativeComparison.ReferencePresent);
            test.verifyTrue(test.Contract.NativeComparison.SchemaMatches);
            test.verifyTrue(test.Contract.NativeFeedbackComparison.ReferencePresent);
            test.verifyTrue(test.Contract.NativeFeedbackComparison.SchemaMatches);
        end
        function commonHandDerivedMilestonesHold(test)
            % The separately labelled native_milestones are observations of
            % native replay ownership, not assertions imposed on MATLAB.
            milestones = test.InputContract.milestones;
            for index = 1:numel(milestones)
                entry = milestones(index);
                test.verifyState(entry.case_id,entry.step,entry.equals);
            end
        end
        function everyCheckpointConservesRealOwnership(test)
            rows = test.Contract.Checkpoints;
            test.verifyEqual(rows.nwk_owned,rows.nsdp_relay+rows.nsdp_local);
            test.verifyEqual(rows.nwk_owned,rows.nwk_waiting+rows.hop_resend);
            test.verifyEqual(rows.hop_pending,rows.hop_resend+rows.hop_holds);
            test.verifyEqual(rows.hop_outstanding,rows.hop_pending);
            test.verifyEqual(rows.nsdp_releases,rows.ack_completed+rows.dack_completed);
            test.verifyGreaterThanOrEqual(rows.nwk_owned,zeros(height(rows),1));
            test.verifyGreaterThanOrEqual(rows.nwk_waiting,zeros(height(rows),1));
        end
        function localQuotaDoesNotCountRelayedOwnership(test)
            rows = test.selectCase('local_relay_independence');
            local = string(rows.action) == "LOCAL";
            test.verifyEqual(sum(rows.accepted(local) == 1),16);
            test.verifyEqual(sum(rows.accepted(local) == 0),1);
            test.verifyEqual(rows.nsdp_local(end),16);
            test.verifyEqual(rows.nsdp_relay(end),17);
            test.verifyEqual(rows.nwk_owned(end),33);
            test.verifyLessThanOrEqual(test.Contract.Checkpoints.nsdp_local, ...
                16*ones(test.Contract.CheckpointCount,1));
        end
        function feedbackUsesPreEnqueueRelayPressure(test)
            feedback = test.Contract.Feedback;
            chosen = feedback(string(feedback.case_id) == "relay_boundary",:);
            test.assertEqual(height(chosen),17);
            test.verifyEqual(string(chosen.kind(15:17)),["ACK";"ACK";"DACK"]);
            test.verifyEqual(chosen.relay_nsdp(15:17),[15;16;17]);
            test.verifyEqual(string(chosen.ack_hex(17)),"000000000001FFFE");
            test.verifyEqual(string(chosen.dack_hex(17)),"0000000000000001");
        end
        function ackReplayAvoidsRepeatedNetworkDelivery(test)
            rows = test.selectCase('ack_duplicate');
            test.verifyEqual(rows.rx_received(end),2);
            test.verifyEqual(rows.rx_delivered(end),1);
            test.verifyEqual(rows.rx_duplicates(end),1);
            test.verifyEqual(rows.nwk_owned(end),1);
            test.verifyEqual(rows.ack_generated(end),2);
        end
        function dackReplayReachesNetworkForReassessment(test)
            pressure = test.selectCase('dack_duplicate_pressure');
            test.verifyEqual(pressure.rx_delivered(end),18);
            test.verifyEqual(pressure.dack_generated(end),2);
            drained = test.selectCase('dack_reassessment_after_release');
            test.verifyEqual(drained.rx_delivered(end),18);
            test.verifyEqual(drained.ack_generated(end),17);
            test.verifyEqual(drained.dack_generated(end),1);
            test.verifyEqual(drained.nsdp_releases(end),3);
        end
        function actualFeedbackRecordsPreserveExactWindows(test)
            feedback = test.Contract.Feedback;
            rows = test.Contract.Checkpoints;
            test.verifyEqual(height(feedback),test.Contract.FeedbackCount);
            for index = 1:height(feedback)
                selected = string(rows.case_id) == string(feedback.case_id(index)) & ...
                    rows.step == feedback.step(index);
                test.assertEqual(sum(selected),1);
                test.verifyEqual(string(rows.action(selected)),"RX");
                test.verifyEqual(rows.rx_highest(selected),feedback.sequence(index));
                test.verifyEqual(string(rows.rx_ack_hex(selected)),string(feedback.ack_hex(index)));
                test.verifyEqual(string(rows.rx_dack_hex(selected)),string(feedback.dack_hex(index)));
                test.verifyEqual(rows.nwk_owned(selected),feedback.nwk_owned(index));
                test.verifyLessThan(feedback.time_s(index),rows.time_s(selected));
            end
            for name = {'ack_hex','dack_hex'}
                values = string(feedback.(name{1}));
                test.verifyTrue(all(~cellfun(@isempty, ...
                    regexp(cellstr(values),'^[0-9A-F]{16}$','once'))));
            end
        end
        function emittedFeedbackRecordsMatchCounters(test)
            rows = test.Contract.Checkpoints;
            cases = unique(string(rows.case_id),'stable');
            feedback = test.Contract.Feedback;
            for index = 1:numel(cases)
                selected = rows(string(rows.case_id) == cases(index),:);
                emitted = feedback(string(feedback.case_id) == cases(index),:);
                test.verifyEqual(selected.rx_received,cumsum(string(selected.action) == "RX"));
                test.verifyEqual(height(emitted), ...
                    selected.ack_generated(end)+selected.dack_generated(end));
                for stepIndex = 1:height(selected)
                    throughStep = emitted.step <= selected.step(stepIndex);
                    test.verifyEqual(sum(throughStep & string(emitted.kind) == "ACK"), ...
                        selected.ack_generated(stepIndex));
                    test.verifyEqual(sum(throughStep & string(emitted.kind) == "DACK"), ...
                        selected.dack_generated(stepIndex));
                end
                for name = {'rx_received','rx_delivered','rx_duplicates','ack_generated', ...
                        'dack_generated','nsdp_releases','ack_completed','dack_completed'}
                    value = selected.(name{1});
                    test.verifyGreaterThanOrEqual(diff(value),zeros(height(selected)-1,1));
                end
            end
        end
        function comparisonReportsDifferencesWithoutRewritingThem(test)
            a = test.Contract.NativeComparison;
            b = test.Contract.NativeFeedbackComparison;
            test.verifyEqual(a.MatchedRows+a.UnmatchedRows,max(a.ActualRows,a.ReferenceRows));
            test.verifyEqual(b.MatchedRows+b.UnmatchedRows,max(b.ActualRows,b.ReferenceRows));
            test.verifyEqual(numel(a.FailedRows),a.UnmatchedRows);
            test.verifyEqual(numel(b.FailedRows),b.UnmatchedRows);
            test.verifyEqual(test.Contract.FailedCount,a.UnmatchedRows);
            test.verifyEqual(test.Contract.FeedbackFailedCount,b.UnmatchedRows);
            test.verifyEqual(test.Contract.Passed,a.UnmatchedRows == 0 && b.UnmatchedRows == 0);
        end
        function savedEvidenceRetainsInputBindings(test)
            directory = test.OutputDirectory;
            test.verifyTrue(isfile(fullfile(directory,'checkpoints.csv')));
            test.verifyTrue(isfile(fullfile(directory,'feedback.csv')));
            test.verifyTrue(isfile(fullfile(directory,'summary.json')));
            test.verifyEqual(csr.validation.Artifacts.sha256(fullfile(directory,'actions.csv')), ...
                test.Contract.ActionsSHA256);
            test.verifyEqual(csr.validation.Artifacts.sha256(fullfile(directory,'cases.csv')), ...
                test.Contract.CasesSHA256);
        end
        function productionPolicyAndPressureLimitRemainUnchanged(test)
            options = csr.hop.Layer.defaults();
            test.verifyEqual(options.DataQueuedRetryPolicy,'actual-tx');
            test.verifyEqual(options.NsdpLimit,16);
            test.verifyEqual(test.Contract.DataQueuedRetryPolicy,'actual-tx');
        end
    end
    methods (Access = private)
        function rows = selectCase(test,caseId)
            allRows = test.Contract.Checkpoints;
            rows = allRows(string(allRows.case_id) == string(caseId),:);
            test.assertNotEmpty(rows);
        end
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
