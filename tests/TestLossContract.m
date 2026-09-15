classdef TestLossContract < matlab.unittest.TestCase
    % Real MATLAB service checks; exact native residuals remain reportable.
    properties (Access = private)
        Contract
        Directory
    end
    methods (TestClassSetup)
        function runOnce(test)
            test.Directory = tempname; mkdir(test.Directory);
            test.addTeardown(@()rmdir(test.Directory,'s'));
            test.Contract = csr.validation.lossContract(test.Directory);
        end
    end
    methods (Test)
        function fourBoundedCasesCompleteWithoutStructuralFailure(test)
            test.verifyTrue(test.Contract.DiagnosticCompleted);
            test.verifyTrue(test.Contract.Passed);
            test.verifyEqual(test.Contract.CaseCount,4);
            test.verifyEqual(test.Contract.FailedCount,0);
            for result=reshape(test.Contract.CaseResults,1,[])
                test.verifyEmpty(result.ErrorIdentifier);
                test.verifyEmpty(result.ErrorStack);
            end
        end
        function generationIdentitiesAndDueTimesRemainIndependentOfAdmission(test)
            rows = test.Contract.Events;
            for name=["ok","data","ack","out"]
                for source=[4 5]
                    selected = string(rows.('case'))==name & rows.app_source==source;
                    due = rows(selected & string(rows.event)=="generate",:);
                    admit = rows(selected & string(rows.event)=="admit",:);
                    test.verifyEqual(due.app_id,uint64((1:48)'));
                    test.verifyEqual(due.time_ns,[zeros(20,1);(1:28)'*1e9]);
                    test.verifyEqual(admit.app_id,due.app_id);
                    test.verifyGreaterThanOrEqual(admit.time_ns,due.time_ns);
                    test.verifyGreaterThan(admit.order,due.order);
                end
            end
        end
        function realApplicationAdmissionRespectsPairCapacity(test)
            rows = test.Contract.Events;
            admit = rows(string(rows.event)=="admit",:);
            blocked = rows(string(rows.event)=="blocked",:);
            test.verifyEqual(height(admit),384);
            test.assertGreaterThan(height(blocked),0);
            for node=[4 5]
                count = admit.nsdp4; blockedCount = blocked.nsdp4;
                if node==5, count = admit.nsdp5; blockedCount = blocked.nsdp5; end
                test.verifyTrue(all(count(admit.node==node)>=1 & count(admit.node==node)<=16));
                test.verifyTrue(all(blockedCount(blocked.node==node)>=16));
            end
        end
        function everyAdmittedIdentityHasDeliveryOrObservedTerminalFailure(test)
            rows = test.Contract.Events; ended = test.Contract.Terminals;
            for name=["ok","data","ack","out"]
                for source=[4 5]
                    selected = string(rows.('case'))==name & rows.app_source==source;
                    admitted = rows.app_id(selected & string(rows.event)=="admit");
                    delivered = rows.app_id(selected & string(rows.event)=="deliver");
                    failed = ended.app_id(string(ended.('case'))==name & ...
                        ended.app_source==source & ended.success==0);
                    test.verifyEqual(numel(delivered),numel(unique(delivered)));
                    test.verifyEmpty(setdiff(admitted,union(delivered,failed)));
                    test.verifyEmpty(setdiff(delivered,admitted));
                    test.verifyEmpty(setdiff(failed,admitted));
                end
            end
            % A lost ACK may leave both a delivered app and a failed sender
            % owner. Do not require those outcome sets to be disjoint.
            control = rows(string(rows.('case'))=="ok" & string(rows.event)=="deliver",:);
            test.verifyEqual(height(control),96);
            test.verifyFalse(any(ended.success(string(ended.('case'))=="ok")==0));
        end
        function relayPreservesIdentityAndUsesOnlyTheFixedChain(test)
            rows = test.Contract.Events;
            data = rows(string(rows.event)=="tx_start" & rows.app_source>0,:);
            test.verifyTrue(all((data.node==4 & data.peer==5) | (data.node==5 & data.peer==1)));
            test.verifyTrue(all(data.app_source(data.node==4)==4));
            test.verifyTrue(all(ismember(data.app_source(data.node==5),[4 5])));
            delivered = rows(string(rows.event)=="deliver",:);
            test.verifyTrue(all(delivered.node==1 & delivered.peer==5));
            for name=["ok","data","ack","out"]
                relay = data(string(data.('case'))==name & data.node==5,:);
                test.verifyTrue(any(relay.app_source==4));
                test.verifyTrue(any(relay.app_source==5));
            end
        end
        function allThreeDeclaredFaultsAreActuallyExercised(test)
            rows = test.Contract.Transport;
            lost = rows(string(rows.decision)=="drop",:);
            test.verifyFalse(any(string(lost.('case'))=="ok"));
            for name=["data","ack"]
                selected = lost(string(lost.('case'))==name,:);
                test.verifyEqual(numel(unique(selected.group_id)),2);
                if name=="data"
                    test.verifyTrue(all(string(selected.reason)=="first_data"));
                    edges = unique([selected.sender selected.receiver],'rows');
                    test.verifyEqual(edges,[4 5;5 1]);
                else
                    test.verifyTrue(all(string(selected.reason)=="first_feedback"));
                    edges = unique([selected.sender selected.receiver],'rows');
                    test.verifyEqual(edges,[1 5;5 4]);
                end
            end
            outage = rows(string(rows.('case'))=="out",:);
            blackout = outage.tx_time_ns>=8e9 & outage.tx_time_ns<9.5e9;
            test.assertTrue(any(blackout));
            test.verifyEqual(string(outage.decision)=="drop",blackout);
            test.verifyGreaterThan(outage.boundary_distance_ns,1000*ones(height(outage),1));
        end
        function droppedSegmentsHaveLossObservationsAndNoIngress(test)
            frames = test.Contract.Transport; rows = test.Contract.Events;
            % Include actual arrival time, identity, sequence and both exact
            % maps so retransmissions cannot be mistaken for an earlier loss.
            transportKeys = string(frames.('case'))+":"+string(frames.arrival_ns)+":"+ ...
                string(frames.receiver)+":"+string(frames.sender)+":"+ ...
                string(frames.app_source)+":"+string(frames.app_id)+":"+ ...
                string(frames.hop_seq)+":"+string(frames.ack_bits)+":"+string(frames.dack_bits);
            eventKeys = string(rows.('case'))+":"+string(rows.time_ns)+":"+ ...
                string(rows.node)+":"+string(rows.peer)+":"+ ...
                string(rows.app_source)+":"+string(rows.app_id)+":"+ ...
                string(rows.hop_seq)+":"+string(rows.ack_bits)+":"+string(rows.dack_bits);
            dropKeys = transportKeys(string(frames.decision)=="drop");
            passKeys = transportKeys(string(frames.decision)=="pass");
            test.verifyEqual(sort(eventKeys(string(rows.event)=="loss")),sort(dropKeys));
            test.verifyEqual(sort(eventKeys(string(rows.event)=="ingress_before")),sort(passKeys));
            test.verifyEqual(sort(eventKeys(string(rows.event)=="ingress_after")),sort(passKeys));
            test.verifyFalse(any(ismember(eventKeys(string(rows.event)=="ingress_before"),dropKeys)));
            txKeys = string(frames.('case'))+":"+string(frames.tx_time_ns)+":"+ ...
                string(frames.sender)+":"+string(frames.receiver)+":"+ ...
                string(frames.app_source)+":"+string(frames.app_id)+":"+ ...
                string(frames.hop_seq)+":"+string(frames.ack_bits)+":"+string(frames.dack_bits);
            test.verifyEqual(sort(eventKeys(string(rows.event)=="tx_start")),sort(txKeys));
        end
        function receiverGroupsShareOneCachedTransportDecision(test)
            rows = test.Contract.Transport;
            test.verifyTrue(all(ismember(string(rows.kind),["DATA","ACK","DACK"])));
            test.verifyGreaterThan(rows.arrival_ns,rows.tx_time_ns);
            for name=["ok","data","ack","out"]
                selected = rows(string(rows.('case'))==name,:);
                for id=reshape(unique(selected.group_id),1,[])
                    group = selected(selected.group_id==id,:);
                    test.verifyEqual(numel(unique(string(group.decision))),1);
                    test.verifyEqual(numel(unique(string(group.reason))),1);
                    test.verifyEqual(numel(unique(group.tx_id)),1);
                    test.verifyEqual(numel(unique(group.receiver)),1);
                    test.verifyEqual(numel(unique(group.segment_index)),height(group));
                    test.verifyEqual(group.group_segments,height(group)*ones(height(group),1));
                end
            end
        end
        function productionCapacityAndCustodyDrainByTheFixedStop(test)
            rows = test.Contract.Events;
            final = rows(string(rows.event)=="final",:);
            stable = rows(ismember(string(rows.event),["checkpoint","final"]),:);
            test.verifyEqual(height(final),12);
            test.verifyEqual(height(stable),72);
            test.verifyEqual(final.time_ns,64e9*ones(12,1));
            for field={"hop_pending","resend_queue","dack_holds","nwk_waiting","nwk_custody", ...
                    "nsdp4","nsdp5","ack_queue","data_queue"}
                test.verifyEqual(final.(field{1}),zeros(12,1));
            end
            test.verifyEqual(stable.hop_pending,stable.resend_queue+stable.dack_holds);
            test.verifyEqual(stable.neighbor_outstanding,stable.hop_pending);
            test.verifyEqual(rows.nwk_custody,rows.nsdp4+rows.nsdp5);
            test.verifyTrue(all(rows.nwk_waiting>=0 & rows.nwk_waiting<=rows.nwk_custody));
        end
        function blockedTrafficResumesAfterObservedDackHeldCapacity(test)
            rows = test.Contract.Events;
            for name=["ok","data","ack","out"]
                selected = rows(string(rows.('case'))==name,:);
                held = selected(string(selected.event)=="blocked" & selected.node==4 & ...
                    selected.dack_holds>0 & selected.nwk_waiting>0,:);
                test.assertGreaterThan(height(held),0);
                later = selected(string(selected.event)=="admit" & selected.node==4 & ...
                    selected.time_ns>held.time_ns(1),:);
                test.verifyGreaterThan(height(later),0);
            end
        end
        function continuedTrafficCrossesTheTwentySecondHoldInterval(test)
            rows = test.Contract.Events;
            for name=["ok","data","ack","out"]
                for source=[4 5]
                    selected = rows(string(rows.('case'))==name & rows.app_source==source,:);
                    generated = selected(string(selected.event)=="generate",:);
                    admitted = selected(string(selected.event)=="admit",:);
                    test.verifyEqual(sum(generated.time_ns>20e9),8);
                    test.verifyTrue(any(admitted.time_ns>20e9));
                    test.verifyTrue(all(admitted.time_ns<40e9));
                end
                delivered = rows(string(rows.('case'))==name & string(rows.event)=="deliver",:);
                test.verifyTrue(any(delivered.time_ns>9.5e9));
            end
        end
        function hopCompletionIsDistinctFromGatewayDelivery(test)
            ended = test.Contract.Terminals;
            keys = string(ended.('case'))+":"+string(ended.node)+":"+ ...
                string(ended.app_source)+":"+string(ended.app_id);
            test.verifyEqual(numel(unique(keys)),height(ended));
            test.verifyTrue(all(ismember(string(ended.reason),["ack","dack_custody","retry_exhausted","mac_queue_full"])));
            test.verifyEqual(logical(ended.success),ismember(string(ended.reason),["ack","dack_custody"]));
            for result=reshape(test.Contract.CaseResults,1,[])
                selected = string(ended.('case'))==string(result.Case);
                test.verifyEqual(result.FailedTerminals,sum(ended.success(selected)==0));
                test.verifyEqual(result.Drops,result.FailedTerminals);
                test.verifyEqual(sum(result.Released),sum(selected));
            end
        end
        function everyRawDrawRetainsExactSupportAndUsageAccounting(test)
            rows = test.Contract.Draws; usage = test.Contract.Usage;
            test.assertGreaterThan(height(rows),0);
            test.verifyEqual(rows.min,zeros(height(rows),1));
            test.verifyEqual(rows.max,31*ones(height(rows),1));
            test.verifyTrue(all(rows.draw>=0 & rows.draw<=31));
            test.verifyTrue(all(rows.resolved>=0 & rows.resolved<=31));
            test.verifyTrue(all(ismember(string(rows.purpose),["prepare","advertise"])));
            test.verifyEqual(height(usage),12);
            test.verifyEqual(usage.supplied,1024*ones(12,1));
            test.verifyEqual(usage.supplied,usage.consumed+usage.unused);
            test.verifyEqual(sum(usage.consumed),height(rows));
        end
        function actualDataAndFeedbackKeepThePinnedRadioProfile(test)
            rows = test.Contract.Events;
            tx = rows(string(rows.event)=="tx_start",:);
            test.verifyEqual(tx.rate_kbps,128*ones(height(tx),1));
            test.verifyEqual(tx.power_dbm,33*ones(height(tx),1));
            feedback = tx(tx.app_source==0,:);
            test.assertGreaterThan(height(feedback),0);
            test.verifyTrue(all(feedback.ack_bits>0 | feedback.dack_bits>0));
        end
        function fullWidthBitmapsSurviveCsvExportExactly(test)
            rows = test.Contract.Events;
            test.verifyClass(rows.ack_bits,'uint64'); test.verifyClass(rows.dack_bits,'uint64');
            test.verifyClass(test.Contract.Transport.ack_bits,'uint64');
            test.verifyClass(test.Contract.Transport.dack_bits,'uint64');
            test.assertTrue(any(rows.ack_bits>uint64(flintmax)));
            for file=["events","transport"]
                path = fullfile(test.Directory,file+".csv");
                options = detectImportOptions(path,'VariableNamingRule','preserve');
                options = setvartype(options,{'app_id','ack_bits','dack_bits'},'string');
                exported = readtable(path,options);
                actual = test.Contract.Events;
                if file=="transport", actual = test.Contract.Transport; end
                for field={'app_id','ack_bits','dack_bits'}
                    test.verifyEqual(exported.(field{1}),string(actual.(field{1})));
                end
            end
        end
        function completeEvidenceRetainsDiagnosticAndExactComparisonResults(test)
            contract = test.Contract;
            test.verifyTrue(contract.ComparedEntireTrajectories);
            for name={'EventComparison','DrawComparison','UsageComparison','TransportComparison','TerminalComparison'}
                comparison = contract.(name{1});
                test.verifyTrue(comparison.ReferencePresent); test.verifyTrue(comparison.SchemaMatches);
                test.verifyEqual(comparison.ComparedRows,max(comparison.ActualRows,comparison.ReferenceRows));
            end
            test.verifyEqual(contract.MatchesNative,contract.UnmatchedCount==0);
            test.verifyEqual(numel(contract.InputBindings),4);
            test.verifyEqual(numel(contract.ReferenceBindings),5);
            for name={'events.csv','draws.csv','usage.csv','check.csv','transport.csv','terminal.csv','summary.json'}
                test.verifyTrue(isfile(fullfile(test.Directory,name{1})));
            end
            summary = jsondecode(fileread(fullfile(test.Directory,'summary.json')));
            test.verifyEqual(summary.EventCount,height(contract.Events));
            test.verifyEqual(summary.TransportCount,height(contract.Transport));
            test.verifyEqual(summary.TerminalCount,height(contract.Terminals));
            test.verifyEqual(summary.Passed,contract.Passed);
            test.verifyEqual(summary.MatchesNative,contract.MatchesNative);
        end
    end
end
