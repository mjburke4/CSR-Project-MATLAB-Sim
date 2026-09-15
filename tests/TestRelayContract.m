classdef TestRelayContract < matlab.unittest.TestCase
    % Test actual MATLAB relay service separately from exact native parity.
    % Complete numerical residuals remain reportable; structural failures fail.
    properties (Access = private)
        Contract
        Directory
    end
    methods (TestClassSetup)
        function runOnce(test)
            test.Directory = tempname; mkdir(test.Directory);
            test.addTeardown(@()rmdir(test.Directory,'s'));
            test.Contract = csr.validation.relayContract(test.Directory);
        end
    end
    methods (Test)
        function everyBoundedRelayCaseCompletes(test)
            test.verifyTrue(test.Contract.DiagnosticCompleted);
            test.verifyEqual(test.Contract.CaseCount,4);
            test.verifyTrue(test.Contract.Passed);
            test.verifyEqual(test.Contract.FailedCount,0);
            for index=1:numel(test.Contract.CaseResults)
                test.verifyEmpty(test.Contract.CaseResults(index).ErrorStack);
            end
        end
        function allApplicationsArriveExactlyOnceAtGateway(test)
            rows = test.Contract.Events;
            delivered = rows(string(rows.event)=="deliver",:);
            test.verifyEqual(height(delivered),120);
            test.verifyEqual(delivered.node,ones(120,1));
            test.verifyEqual(delivered.peer,5*ones(120,1));
            pairs = ["relay","4";"local","5";"mix","4";"mix","5";"sw","4";"sw","5"];
            for index=1:size(pairs,1)
                selected = string(delivered.('case'))==pairs(index,1) & ...
                    delivered.app_source==str2double(pairs(index,2));
                test.verifyEqual(sort(double(delivered.app_id(selected))),(1:20)');
            end
        end
        function relayPreservesSourceIdentityAcrossBothHops(test)
            rows = test.Contract.Events;
            tx = rows(string(rows.event)=="tx_start" & rows.app_source==4,:);
            for name=["relay","mix","sw"]
                selected = string(tx.('case'))==name;
                first = tx(selected & tx.node==4,:); second = tx(selected & tx.node==5,:);
                test.verifyEqual(sort(unique(double(first.app_id))),(1:20)');
                test.verifyEqual(sort(unique(double(second.app_id))),(1:20)');
                test.verifyEqual(first.peer,5*ones(height(first),1));
                test.verifyEqual(second.peer,ones(height(second),1));
            end
            test.verifyFalse(any(rows.node==4 & rows.peer==1 & string(rows.event)=="tx_start"));
        end
        function mixedRelayServesBothOriginalAndTransitTraffic(test)
            rows = test.Contract.Events;
            for name=["mix","sw"]
                selected = string(rows.('case'))==name & rows.node==5 & ...
                    rows.peer==1 & string(rows.event)=="tx_start";
                tx = rows(selected,:);
                for source=[4 5]
                    test.verifyEqual(sort(unique(double(tx.app_id(tx.app_source==source)))),(1:20)');
                end
                test.verifyGreaterThan(sum(tx.app_source==4),0);
                test.verifyGreaterThan(sum(tx.app_source==5),0);
            end
        end
        function applicationAdmissionHonorsRealPairCapacity(test)
            rows = test.Contract.Events;
            admitted = rows(string(rows.event)=="admit",:);
            test.verifyEqual(height(admitted),120);
            for node=[4 5]
                selected = admitted.node==node; pair = admitted.nsdp4;
                if node==5, pair = admitted.nsdp5; end
                test.verifyTrue(all(pair(selected)>=1 & pair(selected)<=16));
            end
            blocked = rows(string(rows.event)=="blocked",:);
            test.assertGreaterThan(height(blocked),0);
            for index=1:height(blocked)
                count = blocked.nsdp4(index);
                if blocked.node(index)==5, count = blocked.nsdp5(index); end
                test.verifyGreaterThanOrEqual(count,16);
            end
        end
        function networkCustodyAccountsForBothOriginalSources(test)
            rows = test.Contract.Events;
            test.verifyEqual(rows.nwk_custody,rows.nsdp4+rows.nsdp5);
            test.verifyTrue(all(rows.nwk_waiting>=0 & rows.nwk_waiting<=rows.nwk_custody));
            releases = rows(string(rows.event)=="release",:);
            test.verifyEqual(height(releases),180);
            test.verifyEqual(releases.app_id,zeros(180,1,'uint64'));
        end
        function dackHeldCapacityIsVisibleThenDrains(test)
            rows = test.Contract.Events;
            checkpoint = rows(string(rows.event)=="checkpoint",:);
            final = rows(string(rows.event)=="final",:);
            test.verifyEqual(height(checkpoint),12); test.verifyEqual(height(final),12);
            test.verifyEqual(checkpoint.time_ns,16000000000*ones(12,1));
            test.verifyEqual(final.time_ns,24000000000*ones(12,1));
            test.verifyEqual(checkpoint.hop_pending,checkpoint.resend_queue+checkpoint.dack_holds);
            test.verifyEqual(final.hop_pending,zeros(12,1));
            test.verifyEqual(final.dack_holds,zeros(12,1));
            test.verifyEqual(final.resend_queue,zeros(12,1));
            test.verifyEqual(final.nwk_waiting,zeros(12,1));
            test.verifyEqual(final.nwk_custody,zeros(12,1));
            % Hold incidence/count is a measured difference, not a required
            % MATLAB outcome copied from the native reference.
        end
        function feedbackUsesFixedRadioAndActualHopBitmaps(test)
            rows = test.Contract.Events;
            tx = rows(string(rows.event)=="tx_start",:);
            test.assertGreaterThan(height(tx),0);
            test.verifyEqual(tx.rate_kbps,128*ones(height(tx),1));
            test.verifyEqual(tx.power_dbm,33*ones(height(tx),1));
            ack = tx(tx.app_source==0,:);
            test.assertGreaterThan(height(ack),0);
            test.verifyTrue(all(ack.ack_bits>0 | ack.dack_bits>0));
            test.verifyTrue(all(ack.app_id==0));
        end
        function everyDrawRetainsRawSupportAndProductionResolution(test)
            rows = test.Contract.Draws; usage = test.Contract.Usage;
            test.assertGreaterThan(height(rows),0);
            test.verifyTrue(all(rows.draw>=rows.min & rows.draw<=rows.max));
            test.verifyEqual(rows.min,zeros(height(rows),1));
            test.verifyEqual(rows.max,31*ones(height(rows),1));
            test.verifyTrue(all(rows.resolved>=0 & rows.resolved<=31));
            test.verifyTrue(all(ismember(string(rows.purpose),["prepare","advertise"])));
            test.verifyEqual(height(usage),12);
            test.verifyEqual(usage.supplied,256*ones(12,1));
            test.verifyEqual(usage.supplied,usage.consumed+usage.unused);
            test.verifyEqual(sum(usage.consumed),height(rows));
        end
        function releaseObserversPreserveHopCallbackOrdering(test)
            rows = test.Contract.Events;
            release = string(rows.event)=="release";
            test.verifyEqual(rows.hop_pending(release),rows.neighbor_outstanding(release));
            delta = rows.resend_queue(release)+rows.dack_holds(release)-rows.hop_pending(release);
            test.verifyTrue(all(delta==0 | delta==1));
            points = test.Contract.Checkpoints;
            selected = string(points.checkpoint)=="release_order_failures";
            test.verifyEqual(points.actual(selected),zeros(4,1));
        end
        function wholeTrajectoriesAndInputsRemainIndependentlyPinned(test)
            contract = test.Contract;
            test.verifyTrue(contract.ComparedEntireTrajectories);
            for name={'EventComparison','DrawComparison','UsageComparison'}
                comparison = contract.(name{1});
                test.verifyTrue(comparison.ReferencePresent); test.verifyTrue(comparison.SchemaMatches);
                test.verifyEqual(comparison.ComparedRows,max(comparison.ActualRows,comparison.ReferenceRows));
            end
            test.verifyEqual(numel(contract.InputBindings),3); test.verifyEqual(numel(contract.ReferenceBindings),3);
            test.verifyTrue(all(strlength(string({contract.InputBindings.SHA256}))==64));
            test.verifyTrue(all(strlength(string({contract.ReferenceBindings.SHA256}))==64));
            test.verifyEqual(contract.MatchesNative,contract.UnmatchedCount==0);
        end
        function evidenceRetainsFailuresAndScopeWithoutInventingParity(test)
            for name={'events.csv','draws.csv','usage.csv','check.csv','summary.json'}
                test.verifyTrue(isfile(fullfile(test.Directory,name{1})));
            end
            summary = jsondecode(fileread(fullfile(test.Directory,'summary.json')));
            test.verifyEqual(summary.EventCount,height(test.Contract.Events));
            test.verifyEqual(summary.DrawCount,height(test.Contract.Draws));
            test.verifyEqual(summary.UnmatchedCount,test.Contract.UnmatchedCount);
            test.verifyEqual(summary.MatchesNative,test.Contract.MatchesNative);
            for index=1:numel(summary.CaseResults)
                result = summary.CaseResults(index);
                test.verifyGreaterThanOrEqual(result.PendingControls,zeros(size(result.PendingControls)));
                test.verifyEqual(result.FinalHopPending,zeros(size(result.FinalHopPending)));
                test.verifyEqual(result.FinalDackHolds,zeros(size(result.FinalDackHolds)));
                test.verifyEqual(result.Drops,0);
            end
        end
    end
end
