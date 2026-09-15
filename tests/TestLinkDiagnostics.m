classdef TestLinkDiagnostics < matlab.unittest.TestCase
    % Passive instrumentation gates. Integrated fixtures use controlled line
    % closure to keep unit runs small; the ten benchmark cases use real PHY.
    % These tests require owner MATLAB execution, not merely static linting.
    methods (Test)
        function observerIsDisabledByDefault(test)
            config = emptyFixture();
            result = csr.runScenario(config);
            test.verifyFalse(any(isfield(result, ...
                {'LinkDecisionTrace','ActualFeedbackTrace','LinkDiagnostics'})));
            test.verifyFalse(isfield(result.Config,'LinkDiagnostics'));
        end

        function autonomousTrafficAndFullTracesAreNonPerturbed(test)
            [observed,plain] = runBoth(smallFixture());
            verifySameCore(test,observed,plain);
            test.verifyGreaterThan(observed.Statistics.Received,0);
            test.verifyGreaterThan(height(observed.ActualFeedbackTrace),0);
            decisions = observed.LinkDecisionTrace;
            test.verifyTrue(any(strcmp(decisions.InputFrameKind,'DATA')));
            test.verifyTrue(all(decisions.InputContextAvailable));
            test.verifyEqual(decisions.SelectedRateKeyKbps,decisions.InputRateKeyKbps);
            test.verifyEqual(decisions.SelectedPowerDbm,decisions.ConfiguredNodePowerDbm);
            test.verifyTrue(all(decisions.PowerDefaulted));
            test.verifyTrue(all(isnan(decisions.PeerS0Dbm)));
            test.verifyTrue(all(isnan(decisions.HopFailureCount)));
            test.verifyFalse(any(decisions.LinkControlApplied));
            verifyCounterClosure(test,observed);
        end

        function feedbackLossAndRetryTracesAreNonPerturbed(test)
            config = smallFixture(); config.Mac.AckTransmissions = 1;
            config.Faults = struct('Kind','ACK','SourceId',1,'DestinationId',2, ...
                'First',1,'Count',2,'StartSeconds',120,'EndSeconds',Inf,'ControlType','*');
            [observed,plain] = runBoth(config);
            verifySameCore(test,observed,plain);
            test.verifyGreaterThan(observed.Statistics.FaultDrops,0);
            verifyCounterClosure(test,observed);
        end

        function emptyFeedbackIsCompleteAndExportedWithHeaders(test)
            observer = csr.sim.LinkDiagnostics(10);
            simulation = csr.sim.NetworkSimulation(emptyFixture(),observer);
            result = simulation.run(); observer.assertComplete();
            test.verifyEmpty(result.LinkDecisionTrace);
            test.verifyEmpty(result.ActualFeedbackTrace);
            test.verifyTrue(result.LinkDiagnostics.Complete);
            directory = tempname; mkdir(directory);
            cleanup = onCleanup(@()rmdir(directory,'s')); %#ok<NASGU>
            csr.analysis.exportResults(result,directory);
            test.verifyTrue(contains(fileread(fullfile(directory,'link_decisions.csv')), ...
                'DecisionId,TimeSeconds,Stage'));
            test.verifyTrue(contains(fileread(fullfile(directory,'actual_feedback.csv')), ...
                'ObservationId,TimeSeconds,Stage'));
            summary = jsondecode(fileread(fullfile(directory,'summary.json')));
            test.verifyTrue(summary.LinkDiagnostics.Complete);
            test.verifyFalse(isfield(summary.Config,'LinkDiagnostics'));
        end

        function duplicateExactAckKeepsEarlierSelectionAcrossAggregateOverride(test)
            observer = csr.sim.LinkDiagnostics(10); observer.attach(5);
            first = acknowledgment(12,false,16,1);
            observer.observeDecision(1,first,[],33,false,true,'mac_enqueue',0);
            duplicate = acknowledgment(12,false,8,33);
            observer.observeDecision(2,duplicate,[],33,true,true,'',0);
            app = struct('Id',uint64(900),'SourceId',1,'DestinationId',2, ...
                'GeneratedSeconds',0,'ApplicationPayloadBytes',8);
            data = csr.hop.Frames.data(app,1,2,uint16(13), ...
                struct('RateKeyKbps',8,'TxPowerDbm',33));
            aggregate = csr.hop.Frames.aggregate({first,data},'long'); aggregate.Id = uint64(7);
            observer.observeTransmission(3,aggregate); observer.assertComplete();
            observed = observer.snapshot(); rows = observed.LinkDecisionTrace;
            test.verifyEqual(rows.RetainedDecisionId,uint64([1;1]));
            test.verifyEqual(rows.QueueDisposition,{'enqueued';'duplicate_retained'});
            actual = observed.ActualFeedbackTrace;
            test.verifyEqual(actual.DecisionId,uint64(1));
            test.verifyEqual(actual.SelectedRateKeyKbps,16);
            test.verifyEqual(actual.SelectedPowerDbm,1);
            test.verifyEqual(actual.RateKeyKbps,8);
            test.verifyEqual(actual.TxPowerDbm,33);
            test.verifyEqual(actual.RateBps,4/0.000510);
            test.verifyNotEqual(actual.RateBps,8000);
            test.verifyEqual([actual.SegmentIndex,actual.SegmentCount],[1,2]);
        end

        function cumulativeReplacementRestartsRepeatsAndPreservesDackKind(test)
            observer = csr.sim.LinkDiagnostics(10); observer.attach(2);
            first = acknowledgment(10,true,8,33);
            observer.observeDecision(1,first,[],33,true,true,'mac_enqueue',0);
            observer.observeTransmission(2,asAggregate(first,1));
            replacement = acknowledgment(11,true,16,30); replacement.Kind = 'DACK';
            replacement.DackBitmap = uint64(2);
            observer.observeDecision(3,replacement,[],30,true,true,'mac_ack_replace',0);
            observer.observeTransmission(4,asAggregate(replacement,2));
            observer.observeTransmission(5,asAggregate(replacement,3));
            observer.assertComplete(); observed = observer.snapshot();
            test.verifyEqual(observed.ActualFeedbackTrace.DecisionId,uint64([1;2;2]));
            test.verifyEqual(observed.ActualFeedbackTrace.FrameKind,{'ACK';'DACK';'DACK'});
            test.verifyEqual(observed.LinkDiagnostics.PendingFeedbackQueueEntries,0);
            test.verifyEqual(observed.LinkDecisionTrace.QueueDisposition,{'enqueued';'replaced'});
        end

        function exactDuplicateCanRetainAnExistingCumulativeIdentity(test)
            observer = csr.sim.LinkDiagnostics(10); observer.attach(5);
            first = acknowledgment(10,true,16,9);
            observer.observeDecision(1,first,[],9,true,true,'mac_enqueue',0);
            duplicate = acknowledgment(10,false,8,33);
            observer.observeDecision(2,duplicate,[],33,true,true,'',0);
            observer.observeTransmission(3,asAggregate(first,1));
            observer.assertComplete(); observed = observer.snapshot();
            test.verifyEqual(observed.LinkDecisionTrace.RetainedDecisionId,uint64([1;1]));
            test.verifyTrue(observed.ActualFeedbackTrace.HasAckWindow);
            test.verifyEqual(observed.ActualFeedbackTrace.SelectedRateKeyKbps,16);
        end

        function controlContextUsesAddressedSequenceAndExactFeedback(test)
            observer = csr.sim.LinkDiagnostics(10); observer.attach(5);
            radio = struct('RateKeyKbps',32,'TxPowerDbm',20);
            control = struct('Id',uint64(123),'Type','ROUTING','Payload',struct(), ...
                'WirePayloadBytes',40);
            incoming = csr.hop.Frames.control(control,2,[1,3],uint16([7,9]),radio);
            context = struct('Frame',incoming,'AggregateId',uint64(88),'NodeId',3, ...
                'Decision',struct('PathlossDb',100,'ReceivedPowerDbm',-80));
            feedback = acknowledgment(9,false,32,33); feedback.SourceId = 3;
            observer.observeDecision(4,feedback,context,33,true,true,'mac_enqueue',2);
            observed = observer.snapshot(); row = observed.LinkDecisionTrace;
            test.verifyTrue(row.InputContextAvailable);
            test.verifyEqual(row.InputSequence,9);
            test.verifyEqual(row.InputPacketId,uint64(123));
            test.verifyEqual(row.InputAggregateId,uint64(88));
            test.verifyEqual(row.InputControlType,{'ROUTING'});
            test.verifyEqual([row.InputPowerDbm,row.PathlossDb,row.InputReceivedPowerDbm],[20,100,-80]);
            test.verifyEqual(row.NwkFailureCount,2);
            test.verifyFalse(row.HasAckWindow);
        end

        function omittedNewTracesFailClosureButRetainCompleteCounts(test)
            observer = csr.sim.LinkDiagnostics(1); observer.attach(5);
            first = acknowledgment(10,true,8,33);
            observer.observeDecision(1,first,[],33,true,true,'mac_enqueue',NaN);
            second = acknowledgment(11,true,8,33);
            observer.observeDecision(2,second,[],33,true,true,'mac_ack_replace',NaN);
            observer.observeTransmission(3,asAggregate(second,1));
            observer.observeTransmission(4,asAggregate(second,2));
            observed = observer.snapshot(); summary = observed.LinkDiagnostics;
            test.verifyEqual([summary.DecisionCount,summary.ActualFeedbackCount],[2,2]);
            test.verifyEqual([summary.OmittedDecisionRecords,summary.OmittedActualFeedbackRecords],[1,1]);
            test.verifyEqual(height(observed.LinkDecisionTrace),1);
            test.verifyEqual(height(observed.ActualFeedbackTrace),1);
            test.verifyEqual(summary.UnmatchedActualFeedbackRecords,0);
            test.verifyFalse(summary.Complete);
            test.verifyError(@()observer.assertComplete(),'csr:diagnostics:Incomplete');
        end

        function zeroCapacityIsAnExplicitOmissionNotDisabledObservation(test)
            observer = csr.sim.LinkDiagnostics(0); observer.attach(5);
            frame = acknowledgment(10,true,8,33);
            observer.observeDecision(1,frame,[],33,true,true,'mac_enqueue',NaN);
            observed = observer.snapshot();
            test.verifyEmpty(observed.LinkDecisionTrace);
            test.verifyEqual(observed.LinkDiagnostics.OmittedDecisionRecords,1);
            test.verifyError(@()observer.assertComplete(),'csr:diagnostics:Incomplete');
        end

        function uncorrelatedActualTransmissionFailsClosure(test)
            observer = csr.sim.LinkDiagnostics(10); observer.attach(5);
            observer.observeTransmission(1,asAggregate(acknowledgment(10,true,8,33),1));
            observed = observer.snapshot();
            test.verifyEqual(observed.LinkDiagnostics.UnmatchedActualFeedbackRecords,1);
            test.verifyFalse(observed.ActualFeedbackTrace.DecisionMatched);
            test.verifyEqual(observed.ActualFeedbackTrace.DecisionId,uint64(0));
            test.verifyTrue(isnan(observed.ActualFeedbackTrace.SelectedPowerDbm));
            test.verifyError(@()observer.assertComplete(),'csr:diagnostics:Incomplete');
        end

        function rejectedFeedbackHasNoRetainedDecisionAndMissingInputsStayMissing(test)
            observer = csr.sim.LinkDiagnostics(10); observer.attach(5);
            frame = acknowledgment(10,true,8,33);
            observer.observeDecision(1,frame,[],33,true,false,'mac_queue_drop',NaN);
            observer.assertComplete(); observed = observer.snapshot(); row = observed.LinkDecisionTrace;
            test.verifyEqual(row.QueueDisposition,{'rejected'});
            test.verifyEqual(row.RetainedDecisionId,uint64(0));
            test.verifyFalse(row.InputContextAvailable);
            test.verifyTrue(all(isnan([row.InputSequence,row.InputRateBps,row.InputPowerDbm, ...
                row.PeerS0Dbm,row.HopFailureCount,row.NwkFailureCount])));
            test.verifyEqual(observed.LinkDiagnostics.PendingFeedbackQueueEntries,0);
        end

        function highBitBitmapRemainsExactInCsv(test)
            observer = csr.sim.LinkDiagnostics(10); observer.attach(5);
            frame = acknowledgment(10,true,8,33);
            frame.AckBitmap = bitshift(uint64(1),63);
            observer.observeDecision(1,frame,[],33,true,true,'mac_enqueue',NaN);
            observed = observer.snapshot(); path = [tempname '.csv'];
            cleanup = onCleanup(@()delete(path)); %#ok<NASGU>
            writetable(observed.LinkDecisionTrace,path);
            test.verifyTrue(contains(fileread(path),'9223372036854775808'));
            test.verifyClass(observed.LinkDecisionTrace.AckBitmap,'uint64');
        end

        function observerCannotBeSharedAcrossSimulations(test)
            observer = csr.sim.LinkDiagnostics(1);
            csr.sim.NetworkSimulation(emptyFixture(),observer);
            test.verifyError(@()csr.sim.NetworkSimulation(emptyFixture(),observer), ...
                'csr:diagnostics:ObserverReuse');
        end
    end
end

function config = smallFixture()
config = csr.scenario.routedNetwork('autonomous');
config.Nodes = config.Nodes(1:2); config.Traffic.SourceId = 2;
config.Traffic.PacketCount = 2; config.Traffic.IntervalSeconds = 5;
config.DurationSeconds = 180; config.Mac.DutyCycleEnabled = false;
config.Trace.MaxRecords = 100000; config.Trace.MaxPhyRecords = 100000;
end

function config = emptyFixture()
config = smallFixture(); config.DurationSeconds = 1;
config.Nwk.StartupMode = 'manual'; config.Traffic.PacketCount = 0;
config.Trace.MaxRecords = 100; config.Trace.MaxPhyRecords = 100;
end

function [observed,plain] = runBoth(config)
simulation = csr.sim.NetworkSimulation(config); plain = simulation.run();
observer = csr.sim.LinkDiagnostics(100000);
simulation = csr.sim.NetworkSimulation(config,observer); observed = simulation.run();
observer.assertComplete();
end

function verifySameCore(test,observed,plain)
core = rmfield(observed,{'LinkDecisionTrace','ActualFeedbackTrace','LinkDiagnostics'});
% Elapsed host time is the sole nondeterministic legacy result field. Every
% other existing field, including the full PHY/protocol/admission tables and
% pending scheduler event count, must compare exactly with the observer off.
core.Metadata.RuntimeSeconds = 0; plain.Metadata.RuntimeSeconds = 0;
test.verifyEqual(core,plain);
test.verifyTrue(observed.LinkDiagnostics.Complete);
test.verifyEqual(observed.LinkDiagnostics.ScheduledEvents,0);
test.verifyEqual(observed.LinkDiagnostics.RandomDraws,0);
end

function verifyCounterClosure(test,result)
test.verifyEqual(height(result.LinkDecisionTrace), ...
    sum(result.NodeHopStatistics.AckGenerated+result.NodeHopStatistics.DackGenerated));
test.verifyEqual(height(result.ActualFeedbackTrace),sum(result.NodeMacStatistics.AckTransmissions));
test.verifyEqual(sum(strcmp(result.LinkDecisionTrace.QueueDisposition,'rejected')), ...
    sum(result.NodeHopStatistics.FeedbackQueueDrops));
test.verifyEqual(sum(strcmp(result.LinkDecisionTrace.QueueDisposition,'replaced')), ...
    sum(result.NodeMacStatistics.AckReplacements));
test.verifyEqual(sum(strcmp(result.LinkDecisionTrace.QueueDisposition,'enqueued')), ...
    sum(result.NodeMacStatistics.AckEnqueued));
test.verifyTrue(all(result.ActualFeedbackTrace.DecisionMatched));
for index = 1:height(result.NodeMacStatistics)
    node = result.NodeMacStatistics.NodeId(index);
    test.verifyEqual(sum(result.ActualFeedbackTrace.NodeId==node), ...
        result.NodeMacStatistics.AckTransmissions(index));
end
tx = result.ProtocolTrace(strcmp(result.ProtocolTrace.Event,'tx_start'),:);
test.verifyTrue(all(ismember(result.ActualFeedbackTrace.AggregateId,tx.PacketId)));
end

function frame = acknowledgment(sequence,hasWindow,rate,power)
frame = csr.hop.Frames.acknowledgment(1,2,uint16(sequence),uint64(1),uint64(0), ...
    struct('HasAckWindow',hasWindow,'RateKeyKbps',rate,'TxPowerDbm',power));
end

function aggregate = asAggregate(frame,id)
aggregate = csr.hop.Frames.aggregate({frame},'short'); aggregate.Id = uint64(id);
end
