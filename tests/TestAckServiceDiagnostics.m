classdef TestAckServiceDiagnostics < matlab.unittest.TestCase
    % T9 passive event evidence gates. Runtime execution belongs to the owner;
    % linting or the availability of these methods is not a MATLAB pass.
    methods (Test)
        function serviceFieldsAreOptInAndLinkOnlyIsUnchanged(test)
            plain = csr.sim.NetworkSimulation(emptyFixture()); plain = plain.run();
            observer = csr.sim.LinkDiagnostics(100);
            linked = csr.sim.NetworkSimulation(emptyFixture(),observer); linked = linked.run();
            test.verifyFalse(any(isfield(plain,{'ServiceTrace','ServiceDiagnostics'})));
            test.verifyFalse(any(isfield(linked,{'ServiceTrace','ServiceDiagnostics'})));
            test.verifyFalse(isfield(linked.Config,'ServiceDiagnostics'));
        end

        function defaultWindowIncludesStartAndExcludesEnd(test)
            observer = csr.sim.AckServiceDiagnostics(10); observer.attach(5);
            observer.observeService(299.999,1,'mac_state',struct(),struct('State','Idle'));
            observer.observeService(300,1,'mac_state',struct(),struct('State','Search'));
            observer.observeService(319.999,1,'mac_state',struct(),struct('State','Tx'));
            observer.observeService(320,1,'mac_state',struct(),struct('State','Search'));
            observer.assertComplete(); observed = observer.snapshot();
            test.verifyEqual(observed.ServiceTrace.TimeSeconds,[300;319.999]);
            test.verifyEqual(observed.ServiceDiagnostics.ServiceEventCount,2);
            test.verifyEqual(observed.ServiceDiagnostics.OutOfWindowServiceEvents,2);
            test.verifyEqual(observed.ServiceDiagnostics.WindowBoundary,'start_inclusive_end_exclusive');
        end

        function sameTimeOrderIncludesAdmissionAmongProtocolCallbacks(test)
            observer = csr.sim.AckServiceDiagnostics(10,[10 20]); observer.attach(5);
            observer.observeService(12,2,'network_custody_release',application(41),struct('Reason','ack'));
            observer.observeService(12,2,'hop_ack',data(41),capacity());
            admission = attempt(12,true,uint64(42)); observer.observeAdmission(admission);
            observed = observer.snapshot(); rows = observed.ServiceTrace;
            test.verifyEqual(rows.ObservationId,uint64([1;2;3]));
            test.verifyEqual(rows.Event,{'network_custody_release';'hop_ack';'application_attempt'});
            test.verifyEqual(rows.Stage,{'protocol_callback';'protocol_callback';'application_attempt'});
            test.verifyEqual(rows.Layer,{'NWK';'HOP';'APP'});
            test.verifyEqual(rows.PacketId,uint64([41;41;42]));
            test.verifyEqual(rows.NodeId,[2;2;2]);
        end

        function typedCapacityReservationAndOpaqueDetailsAreCopied(test)
            observer = csr.sim.AckServiceDiagnostics(10); observer.attach(5);
            details = capacity(); details.ReservationSlot = 7;
            details.ReservationCounter = -1; details.State = 'Search';
            details.Extra = struct('Peers',[1 3],'Retained',true,'Description','a,b');
            observer.observeService(301,2,'hop_ack',data(51),details);
            observed = observer.snapshot(); row = observed.ServiceTrace;
            test.verifyEqual(row.ReservationSlot,7); test.verifyEqual(row.ReservationCounter,-1);
            test.verifyEqual(row.State,{'Search'});
            test.verifyEqual([row.PendingData,row.GlobalSpare,row.NeighborOutstanding,row.NeighborSpare], ...
                [7,26,3,6]);
            test.verifyEqual([row.GlobalAllowed,row.NeighborAllowed],[1,1]);
            test.verifyTrue(isnan(row.NsdpBefore)); test.verifyTrue(isnan(row.CapacityReleased));
            test.verifyEqual(jsondecode(row.DetailsJSON{1}),jsondecode(jsonencode(details)));
        end

        function receivedControlUsesAddressedSequenceAndPeer(test)
            observer = csr.sim.AckServiceDiagnostics(10); observer.attach(5);
            control = struct('Id',uint64(73),'Type','ROUTING','Payload',struct(), ...
                'WirePayloadBytes',40);
            frame = csr.hop.Frames.control(control,2,[1 3],uint16([7 9]),struct());
            observer.observeService(302,3,'hop_control_receive',frame,struct('FirstReception',true));
            observed = observer.snapshot(); row = observed.ServiceTrace;
            test.verifyEqual([row.NodeId,row.PeerId,row.Sequence],[3,2,9]);
            test.verifyEqual(row.PacketId,uint64(73)); test.verifyTrue(row.PacketIdAvailable);
            test.verifyEqual(row.ControlType,{'ROUTING'});
            test.verifyEqual(jsondecode(row.FrameDestinationsJSON{1}),[1;3]);
            test.verifyEqual(jsondecode(row.HopSequencesJSON{1}),[7;9]);
        end

        function blockedAttemptHasNoInventedPacketIdentity(test)
            observer = csr.sim.AckServiceDiagnostics(10); observer.attach(5);
            admission = attempt(303,false,uint64(0)); observer.observeAdmission(admission);
            observed = observer.snapshot(); row = observed.ServiceTrace;
            test.verifyFalse(row.PacketIdAvailable); test.verifyEqual(row.PacketId,uint64(0));
            test.verifyEqual([row.Accepted,row.NsdpCount,row.NsdpLimit,row.AttemptIndex],[0,16,16,123]);
            test.verifyEqual(row.Reason,{'nsdp_full'});
            test.verifyTrue(all(isnan([row.PendingData,row.NeighborOutstanding,row.Sequence])));
            test.verifyEqual(jsondecode(row.DetailsJSON{1}),jsondecode(jsonencode(admission)));
        end

        function aggregateMemberIdIsNotAnInventedOtaIdentity(test)
            observer = csr.sim.AckServiceDiagnostics(10); observer.attach(5);
            frame = data(99); frame.Kind = 'AGGREGATE'; frame.Id = uint64(456);
            observer.observeService(304,2,'mac_transmit',frame,struct('DurationSeconds',0.1,'Segments',2));
            observed = observer.snapshot(); row = observed.ServiceTrace;
            test.verifyFalse(row.AggregateIdAvailable); test.verifyEqual(row.AggregateId,uint64(0));
            test.verifyFalse(row.PacketIdAvailable); test.verifyEqual(row.PacketId,uint64(0));
            test.verifyEqual(row.SegmentCount,2);
        end

        function exactFeedbackBitmapAndApplicationIdSurviveCsv(test)
            observer = csr.sim.AckServiceDiagnostics(10); observer.attach(5);
            frame = acknowledgment(); frame.AckBitmap = bitshift(uint64(1),63);
            observer.observeService(305,1,'mac_enqueue',frame,struct('AckDepth',1));
            packetId = bitshift(uint64(1),53)+uint64(1);
            observer.observeService(305,2,'hop_admit',data(packetId),capacity());
            observed = observer.snapshot(); rows = observed.ServiceTrace;
            test.verifyClass(rows.AckBitmap,'uint64'); test.verifyClass(rows.PacketId,'uint64');
            test.verifyTrue(rows.FeedbackIdentityAvailable(1));
            test.verifyEqual(rows.PacketId(2),packetId);
            path = [tempname '.csv']; cleanup = onCleanup(@()delete(path)); %#ok<NASGU>
            writetable(rows,path); csv = fileread(path);
            test.verifyTrue(contains(csv,'9223372036854775808'));
            test.verifyTrue(contains(csv,'9007199254740993'));
        end

        function serviceWindowDoesNotFilterInheritedFeedbackCorrelation(test)
            observer = csr.sim.AckServiceDiagnostics(10); observer.attach(5);
            frame = acknowledgment();
            observer.observeDecision(299,frame,[],33,true,true,'mac_enqueue',NaN);
            aggregate = csr.hop.Frames.aggregate({frame},'short'); aggregate.Id = uint64(7);
            observer.observeTransmission(321,aggregate);
            observer.assertComplete(); observed = observer.snapshot();
            test.verifyEmpty(observed.ServiceTrace);
            test.verifyEqual(observed.LinkDecisionTrace.TimeSeconds,299);
            test.verifyEqual(observed.ActualFeedbackTrace.TimeSeconds,321);
            test.verifyTrue(observed.ServiceDiagnostics.Complete);
            test.verifyTrue(observed.ActualFeedbackTrace.DecisionMatched);
        end

        function serviceCapCountsOmissionsAndFailsCompleteness(test)
            observer = csr.sim.AckServiceDiagnostics(1); observer.attach(5);
            for index = 1:3
                observer.observeService(300+index,2,'mac_prepare',struct(),struct('ReservationSlot',index));
            end
            observed = observer.snapshot(); summary = observed.ServiceDiagnostics;
            test.verifyEqual([summary.ServiceEventCount,summary.CapturedServiceRecords,summary.OmittedServiceRecords], ...
                [3,1,2]);
            test.verifyEqual(height(observed.ServiceTrace),1);
            test.verifyTrue(observed.LinkDiagnostics.Complete); test.verifyFalse(summary.Complete);
            test.verifyError(@()observer.assertComplete(),'csr:diagnostics:IncompleteService');
        end

        function zeroCapStillObservesAndRejectsIncompleteEvidence(test)
            observer = csr.sim.AckServiceDiagnostics(0); observer.attach(5);
            observer.observeService(301,2,'mac_state',struct(),struct('State','Search'));
            observed = observer.snapshot(); test.verifyEmpty(observed.ServiceTrace);
            test.verifyEqual(observed.ServiceDiagnostics.OmittedServiceRecords,1);
            test.verifyError(@()observer.assertComplete(),'csr:diagnostics:IncompleteService');
        end

        function superclassReuseAndIncompleteFeedbackGatesRemainActive(test)
            observer = csr.sim.AckServiceDiagnostics(10); observer.attach(5);
            test.verifyError(@()observer.attach(5),'csr:diagnostics:ObserverReuse');
            aggregate = csr.hop.Frames.aggregate({acknowledgment()},'short'); aggregate.Id = uint64(1);
            observer.observeTransmission(301,aggregate); observed = observer.snapshot();
            test.verifyFalse(observed.ServiceDiagnostics.Complete);
            test.verifyFalse(observed.ServiceDiagnostics.InheritedFeedbackComplete);
            test.verifyError(@()observer.assertComplete(),'csr:diagnostics:Incomplete');
        end

        function invalidWindowOrderIsRejected(test)
            test.verifyError(@()csr.sim.AckServiceDiagnostics(10,[320 300]),'csr:diagnostics:ServiceWindow');
        end

        function emptyWindowExportsHeadersAndSummary(test)
            observer = csr.sim.AckServiceDiagnostics(100);
            simulation = csr.sim.NetworkSimulation(emptyFixture(),observer); result = simulation.run();
            observer.assertComplete(); test.verifyEmpty(result.ServiceTrace);
            directory = tempname; mkdir(directory);
            cleanup = onCleanup(@()rmdir(directory,'s')); %#ok<NASGU>
            csr.analysis.exportResults(result,directory);
            test.verifyTrue(contains(fileread(fullfile(directory,'service_trace.csv')), ...
                'ObservationId,TimeSeconds,Stage,Layer,Event,NodeId'));
            summary = jsondecode(fileread(fullfile(directory,'summary.json')));
            test.verifyEqual(summary.ServiceDiagnostics.SchemaVersion,'csr-matlab-ack-service-diagnostics-v1');
            test.verifyTrue(summary.ServiceDiagnostics.Complete);
            test.verifyTrue(summary.LinkDiagnostics.Complete);
        end

        function cancellationWrappersPreserveBothOriginalCallbacks(test)
            for mode={'sequence','control'}
                observer=csr.sim.AckServiceDiagnostics(100,[0 1]);
                observed=cancellationFixture(observer,mode{1});
                plain=cancellationFixture([],mode{1});
                test.verifyEqual(observed,plain);
                observer.assertComplete(); evidence=observer.snapshot();
                rows=evidence.ServiceTrace(strcmp(evidence.ServiceTrace.Stage,'cancellation_callback'),:);
                test.verifyEqual(height(rows),2);
                test.verifyEqual(rows.NodeId,[2;2]); test.verifyEqual(rows.PeerId,[1;1]);
                test.verifyTrue(isnan(rows.RemovedCount(1))); test.verifyEqual(rows.RemovedCount(2),1);
                test.verifyEqual(rows.DataDepth,[1;0]); test.verifyEqual(rows.AckDepth,[0;0]);
                test.verifyFalse(any(rows.PacketIdAvailable));
                test.verifyFalse(any(rows.AggregateIdAvailable));
                test.verifyTrue(all(cellfun(@isempty,rows.FrameKind)));
                if strcmp(mode{1},'sequence')
                    test.verifyEqual(rows.Event,{'mac_cancel_before';'mac_cancel_after'});
                    test.verifyEqual(rows.Sequence,[1;1]);
                    test.verifyTrue(all(cellfun(@isempty,rows.ControlType)));
                else
                    test.verifyEqual(rows.Event,{'mac_control_cancel_before';'mac_control_cancel_after'});
                    test.verifyTrue(all(isnan(rows.Sequence)));
                    test.verifyEqual(rows.ControlType,{'KEY_REQUEST';'KEY_REQUEST'});
                end
                test.verifyEqual(evidence.ServiceDiagnostics.AdditionalStateReads,12);
                test.verifyTrue(evidence.ServiceDiagnostics.CancellationPairsComplete);
            end
        end

        function cancellationSnapshotsAreNotReadOutsideTheWindow(test)
            observer=csr.sim.AckServiceDiagnostics(100); cancellationFixture(observer,'control');
            observer.assertComplete(); evidence=observer.snapshot();
            test.verifyEqual(evidence.ServiceDiagnostics.CancellationSnapshotCount,0);
            test.verifyEqual(evidence.ServiceDiagnostics.AdditionalStateReads,0);
            test.verifyEmpty(evidence.ServiceTrace);
        end

        function unmatchedCancellationSelectorsFailCompleteness(test)
            observer=csr.sim.AckServiceDiagnostics(10); observer.attach(5);
            state=cancellationState();
            observer.observeCancellation(301,2,'mac_cancel_before',1,uint16(7),'',NaN,state);
            test.verifyError(@()observer.assertComplete(),'csr:diagnostics:IncompleteCancellation');
            observer.observeCancellation(301,2,'mac_cancel_after',3,uint16(7),'',0,state);
            evidence=observer.snapshot();
            test.verifyEqual(evidence.ServiceDiagnostics.CancellationPairErrors,1);
            test.verifyFalse(evidence.ServiceDiagnostics.CancellationPairsComplete);
            test.verifyError(@()observer.assertComplete(),'csr:diagnostics:IncompleteCancellation');
        end

        function cancellationCapCountsAllObservedSnapshots(test)
            observer=csr.sim.AckServiceDiagnostics(1); observer.attach(5);
            state=cancellationState();
            observer.observeCancellation(301,2,'mac_control_cancel_before',1,NaN,'KEY_REQUEST',NaN,state);
            state.DataDepth=0;
            observer.observeCancellation(301,2,'mac_control_cancel_after',1,NaN,'KEY_REQUEST',1,state);
            evidence=observer.snapshot(); summary=evidence.ServiceDiagnostics;
            test.verifyEqual([summary.CancellationSnapshotCount,summary.AdditionalStateReads],[2,12]);
            test.verifyTrue(summary.CancellationPairsComplete);
            test.verifyEqual(summary.OmittedServiceRecords,1);
            test.verifyError(@()observer.assertComplete(),'csr:diagnostics:IncompleteService');
        end

        function integratedProtocolAndAdmissionResultsAreNonPerturbed(test)
            config = smallFixture();
            [observed,plain] = runBoth(config); verifySameCore(test,observed,plain);
            test.verifyGreaterThan(observed.Statistics.Received,0);
            test.verifyGreaterThan(height(observed.ServiceTrace),0);
            rows = observed.ServiceTrace;
            test.verifyTrue(any(strcmp(rows.Event,'mac_prepare')));
            test.verifyTrue(any(strcmp(rows.Event,'hop_ack')));
            test.verifyTrue(any(strcmp(rows.Event,'network_custody_release')));
            admissions = rows(strcmp(rows.Stage,'application_attempt'),:);
            test.verifyEqual(height(admissions),2);
            test.verifyEqual(admissions.TimeSeconds,observed.ApplicationAdmissionTrace.TimeSeconds);
            test.verifyEqual(admissions.PacketId,observed.ApplicationAdmissionTrace.PacketId);
            test.verifyEqual(admissions.NsdpCount,observed.ApplicationAdmissionTrace.NsdpCount);
            protocol = observed.ProtocolTrace;
            protocol = protocol(protocol.TimeSeconds>=0 & protocol.TimeSeconds<180,:);
            callbacks = rows(strcmp(rows.Stage,'protocol_callback'),:);
            for index = 1:height(callbacks)
                test.verifyTrue(any(protocol.TimeSeconds==callbacks.TimeSeconds(index) & ...
                    protocol.NodeId==callbacks.NodeId(index) & strcmp(protocol.Event,callbacks.Event{index})));
            end
        end

        function observerRetainsEventsWhenLegacyTraceIsDisabled(test)
            config = smallFixture(); config.Trace.Enabled = false;
            [observed,plain] = runBoth(config); verifySameCore(test,observed,plain);
            test.verifyEmpty(observed.ProtocolTrace);
            test.verifyGreaterThan(height(observed.ServiceTrace),0);
            test.verifyEqual(sum(strcmp(observed.ServiceTrace.Stage,'application_attempt')),2);
        end
    end
end

function app = application(id)
app = struct('Id',uint64(id),'SourceId',2,'DestinationId',1, ...
    'GeneratedSeconds',300,'ApplicationPayloadBytes',8);
end

function frame = data(id)
frame = csr.hop.Frames.data(application(id),2,1,uint16(10),struct('RateKeyKbps',128,'TxPowerDbm',33));
end

function frame = acknowledgment()
frame = csr.hop.Frames.acknowledgment(1,2,uint16(10),uint64(1),uint64(0), ...
    struct('RateKeyKbps',128,'TxPowerDbm',33));
end

function details = capacity()
details = struct('PendingData',7,'PendingThreshold',32,'GlobalSpare',26, ...
    'NeighborOutstanding',3,'NeighborThreshold',8,'NeighborSpare',6, ...
    'GlobalAllowed',true,'NeighborAllowed',true);
end

function row = attempt(time,accepted,packetId)
row = csr.sim.ApplicationGenerator.emptyTrace();
row.TimeSeconds = time; row.FlowIndex = 1; row.AttemptIndex = 123;
row.SourceId = 2; row.ConfiguredDestinationId = 1; row.DestinationId = 1;
row.Accepted = accepted; row.PacketId = packetId;
if accepted, row.Reason = 'admitted'; row.NsdpCount = 15;
else, row.Reason = 'nsdp_full'; row.NsdpCount = 16; end
end

function config = smallFixture()
config = csr.scenario.routedNetwork('autonomous');
config.Nodes = config.Nodes(1:2); config.Traffic.SourceId = 2;
config.Traffic.PacketCount = 2; config.Traffic.IntervalSeconds = 5;
config.ApplicationGenerator = 'historical-opnet-gated';
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
observer = csr.sim.AckServiceDiagnostics(100000,[0 config.DurationSeconds]);
simulation = csr.sim.NetworkSimulation(config,observer); observed = simulation.run();
observer.assertComplete();
end

function verifySameCore(test,observed,plain)
core = rmfield(observed,{'LinkDecisionTrace','ActualFeedbackTrace','LinkDiagnostics', ...
    'ServiceTrace','ServiceDiagnostics'});
core.Metadata.RuntimeSeconds = 0; plain.Metadata.RuntimeSeconds = 0;
test.verifyEqual(core,plain);
test.verifyTrue(observed.ServiceDiagnostics.Complete);
test.verifyEqual(observed.ServiceDiagnostics.ScheduledEvents,0);
test.verifyEqual(observed.ServiceDiagnostics.RandomDraws,0);
snapshots=sum(strcmp(observed.ServiceTrace.Stage,'cancellation_callback'));
test.verifyEqual(observed.ServiceDiagnostics.CancellationSnapshotCount,snapshots);
test.verifyEqual(observed.ServiceDiagnostics.AdditionalStateReads,6*snapshots);
test.verifyTrue(observed.ServiceDiagnostics.CancellationPairsComplete);
test.verifyEqual(observed.ServiceDiagnostics.CancellationPairErrors,0);
end

function state = cancellationState()
state=struct('State','Search','PreparationActive',true,'ReservationSlot',1, ...
    'ReservationCounter',0,'DataDepth',1,'AckDepth',0);
end

function state = cancellationFixture(observer,mode)
simulation=csr.sim.NetworkSimulation(emptyFixture(),observer);
control=struct('Id',uint64(99),'Type','KEY_REQUEST','Payload',struct(),'WirePayloadBytes',32);
[accepted,frame]=simulation.Hops{2}.sendControl(control,1, ...
    struct('RateKeyKbps',128,'TxPowerDbm',33,'AckRequired',true));
assert(accepted,'The controlled HOP fixture must admit its one control.');
if strcmp(mode,'sequence')
    feedback=csr.hop.Frames.acknowledgment(1,2,frame.Sequence,uint64(0),uint64(0), ...
        struct('HasAckWindow',false));
    simulation.Hops{2}.receive(feedback);
else
    removed=simulation.Hops{2}.cancelQueuedControl(1,'KEY_REQUEST');
    assert(removed==1,'The original control cancellation return value must survive the wrapper.');
end
state=struct('Mac',simulation.Macs{2}.snapshot(),'Hop',simulation.Hops{2}.stats(), ...
    'PreparationActive',simulation.Macs{2}.PreparationActive, ...
    'SchedulerPendingCount',simulation.Scheduler.PendingCount);
end
