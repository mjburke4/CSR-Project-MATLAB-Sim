classdef TestReplayContract < matlab.unittest.TestCase
    % Functional MATLAB execution is distinct from numerical native matching.
    % A complete differing trajectory is retained for diagnosis. These tests
    % require the real service chain and independently pinned reference files.
    properties (Access = private)
        Contract
        Directory
    end
    methods (TestClassSetup)
        function runOnce(test)
            test.Directory = tempname; mkdir(test.Directory);
            test.addTeardown(@()rmdir(test.Directory,'s'));
            test.Contract = csr.validation.replayContract(test.Directory);
        end
    end
    methods (Test)
        function everyBoundedCaseCompletes(test)
            test.verifyTrue(test.Contract.DiagnosticCompleted);
            test.verifyEqual(test.Contract.CaseCount,4);
            test.verifyEqual(test.Contract.CheckpointCount,56);
            test.verifyTrue(test.Contract.Passed);
            test.verifyEqual(test.Contract.FailedCount,0);
            rows = test.Contract.Events;
            tx = rows(string(rows.event)=="tx_start",:);
            test.assertGreaterThan(height(tx),0);
            test.verifyEqual(tx.rate_kbps,128*ones(height(tx),1));
            test.verifyEqual(tx.power_dbm,33*ones(height(tx),1));
            for name=["ab","ba","slow","track"]
                ack = string(tx.('case'))==name & tx.node==1 & tx.app_source==0;
                test.verifyGreaterThan(sum(ack),0, ...
                    sprintf('Case %s must transmit real HOP-generated ACKs.',name));
            end
            for index=1:numel(test.Contract.CaseResults)
                test.verifyEmpty(test.Contract.CaseResults(index).ErrorStack);
            end
        end
        function noAdmissionOrCustodyRemainsAtHorizon(test)
            rows = test.Contract.Checkpoints;
            names = string(rows.checkpoint);
            test.verifyEqual(rows.actual(names=="admitted"),4*ones(8,1));
            test.verifyEqual(rows.actual(names=="delivered"),4*ones(8,1));
            test.verifyEqual(rows.actual(names=="released"),4*ones(8,1));
            test.verifyEqual(rows.actual(names=="pending"),zeros(8,1));
        end
        function completedDrawsRetainRawAndResolvedSelections(test)
            rows = test.Contract.Draws;
            test.assertGreaterThan(height(rows),0);
            test.verifyTrue(all(rows.draw>=rows.min & rows.draw<=rows.max));
            test.verifyTrue(all(rows.resolved>=0 & rows.resolved<=31));
            test.verifyTrue(all(ismember(string(rows.purpose),["prepare","advertise"])));
            usage = test.Contract.Usage;
            test.verifyEqual(height(usage),12);
            test.verifyEqual(usage.supplied,128*ones(12,1));
            test.verifyEqual(usage.supplied,usage.consumed+usage.unused);
            test.verifyEqual(sum(usage.consumed),height(rows));
        end
        function callbackSeesReleasedCapacityBeforeResendRemoval(test)
            rows = test.Contract.Events;
            release = string(rows.event)=="release";
            test.verifyEqual(sum(release),32);
            test.verifyEqual(rows.hop_pending(release),rows.neighbor_outstanding(release));
            test.verifyTrue(all(rows.resend_queue(release)>rows.hop_pending(release)));
        end
        function wakeFollowsActualFeedbackProcessingByOneTic(test)
            rows = test.Contract.Events;
            releaseIndices = find(string(rows.event)=="release");
            for index=reshape(releaseIndices,1,[])
                same = string(rows.('case'))==string(rows.('case')(index)) & ...
                    rows.node==rows.node(index) & rows.order>rows.order(index);
                after = find(same & string(rows.event)=="ingress_after",1);
                wake = find(same & string(rows.event)=="wake",1);
                test.assertNotEmpty(after); test.assertNotEmpty(wake);
                test.verifyLessThan(after,wake);
                test.verifyEqual(rows.time_ns(after),rows.time_ns(index));
                delta = rows.time_ns(wake)-rows.time_ns(after);
                test.verifyLessThanOrEqual(abs(delta-1e9/36e6),1);
            end
        end
        function receiverTrackFreezesGatewayAcknowledgmentService(test)
            rows = test.Contract.Events;
            selected = string(rows.('case'))=="track" & rows.node==1;
            busy = rows(selected & string(rows.event)=="busy",:);
            test.verifyEqual(busy.mac_state,[2;1]);
            test.verifyEqual(busy.time_ns,[250000000;650000000]);
            transmitting = selected & string(rows.event)=="tx_start";
            test.verifyFalse(any(transmitting & rows.time_ns>=250000000 & rows.time_ns<650000000));
            test.verifyTrue(any(transmitting & rows.time_ns>=650000000));
        end
        function everyComparedTrajectoryIsCompleteAndPinned(test)
            contract = test.Contract;
            test.verifyTrue(contract.ComparedEntireTrajectories);
            for name={'EventComparison','DrawComparison','UsageComparison'}
                comparison = contract.(name{1});
                test.verifyTrue(comparison.ReferencePresent);
                test.verifyTrue(comparison.SchemaMatches);
                test.verifyEqual(comparison.ComparedRows,max(comparison.ActualRows,comparison.ReferenceRows));
            end
            test.verifyEqual(numel(contract.InputBindings),3);
            test.verifyEqual(numel(contract.ReferenceBindings),3);
            test.verifyTrue(all(strlength(string({contract.InputBindings.SHA256}))==64));
            test.verifyTrue(all(strlength(string({contract.ReferenceBindings.SHA256}))==64));
            test.verifyEqual(contract.MatchesNative,contract.UnmatchedCount==0);
        end
        function writesEvidenceBeforeReportingNumericalDisposition(test)
            for name={'events.csv','draws.csv','usage.csv','check.csv','summary.json'}
                test.verifyTrue(isfile(fullfile(test.Directory,name{1})));
            end
            summary = jsondecode(fileread(fullfile(test.Directory,'summary.json')));
            test.verifyEqual(summary.EventCount,height(test.Contract.Events));
            test.verifyEqual(summary.DrawCount,height(test.Contract.Draws));
            test.verifyEqual(summary.UnmatchedCount,test.Contract.UnmatchedCount);
            test.verifyEqual(summary.MatchesNative,test.Contract.MatchesNative);
        end
    end
end
