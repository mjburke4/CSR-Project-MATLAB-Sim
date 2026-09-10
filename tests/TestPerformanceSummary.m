classdef TestPerformanceSummary < matlab.unittest.TestCase
    methods (Test)
        function separatesApplicationRadioAndReceiverUnits(test)
            [row,applications] = csr.analysis.performanceSummary(syntheticResult());
            test.verifyEqual(row.Generated,3);
            test.verifyEqual(row.PhysicalTransmissions,5);
            test.verifyEqual(row.PhysicalAttempts,10);
            test.verifyEqual(row.MacMemberTransmissions,7);
            test.verifyEqual(row.DataMemberTransmissions,3);
            test.verifyEqual(row.ControlMemberTransmissions,4);
            test.verifyEqual(row.NetworkControlMemberTransmissions,2);
            test.verifyEqual(row.AckFeedbackMemberTransmissions,2);
            test.verifyEqual(row.ConcatenatedTransmissions,2);
            test.verifySize(applications,[3 11]);
            test.verifyEqual(applications.PacketId,uint64([1;2;3]));
            test.verifyEqual(applications.Outcome,{'delivered';'dropped';'delivered'});
            test.verifyEqual(applications.DropReason,{'';'queue_full';''});
        end

        function generationDenominatorsAreExplicit(test)
            row = csr.analysis.performanceSummary(syntheticResult());
            test.verifyEqual(row.GeneratedApplicationBytes,192);
            test.verifyEqual(row.FirstGenerationSeconds,10);
            test.verifyEqual(row.LastGenerationSeconds,30);
            test.verifyEqual(row.GenerationSpanSeconds,20);
            test.verifyEqual(row.TrafficObservationSeconds,90);
            test.verifyEqual(row.ObservationMeanOfferedLoadBitsPerSecond,8*192/90);
            test.verifyEqual(row.PlannedLastGenerationSeconds,30);
            test.verifyEqual(row.PlannedDrainSeconds,70);
            test.verifyEqual(row.ScheduledFlowRateSumBitsPerSecond,8*64/10);
        end

        function keepsLatencyQuantilesAndMissingMetricsHonest(test)
            [row,applications] = csr.analysis.performanceSummary(syntheticResult());
            test.verifyEqual(row.LatencyP95Seconds,60);
            test.verifyEqual(row.MaxLatencySeconds,60);
            test.verifyEqual(applications.LatencySeconds([1 3]),[30;60]);
            test.verifyTrue(isnan(applications.LatencySeconds(2)));
            test.verifyFalse(row.AirtimeAvailable);
            test.verifyTrue(isnan(row.TotalTransmitAirtimeSeconds));
            test.verifyFalse(row.CpuTimeAvailable);
            test.verifyTrue(isnan(row.CpuTimeSeconds));
            test.verifyFalse(row.ExecutedEventsAvailable);
            test.verifyTrue(isnan(row.ExecutedEvents));
            test.verifyEqual(row.RuntimeSeconds,0.25);
            test.verifyEqual(row.PendingSchedulerEvents,17);
        end

        function controlOwnershipDrainDoesNotMeanSchedulerQuiescence(test)
            result = syntheticResult();
            row = csr.analysis.performanceSummary(result);
            test.verifyTrue(row.ApplicationsDrained);
            test.verifyTrue(row.DataDrained);
            test.verifyTrue(row.ControlsDrained);
            test.verifyTrue(row.OwnershipDrained);
            test.verifyGreaterThan(row.PendingSchedulerEvents,0);
            test.verifyTrue(contains(row.ControlDrainScope,'MAC feedback queue depth unavailable'));
            result.NodeNwkStatistics.PendingControlMessages(2) = 1;
            result.NodeHopStatistics.ControlPending(1) = 1;
            result.NodeHopStatistics.ControlPendingTargets(1) = 2;
            row = csr.analysis.performanceSummary(result);
            test.verifyTrue(row.DataDrained);
            test.verifyFalse(row.ControlsDrained);
            test.verifyFalse(row.OwnershipDrained);
            test.verifyEqual(row.NwkPendingControlMessages,1);
        end

        function sumsDistinctRetryFailureAndQueueCounters(test)
            result = syntheticResult();
            result.NodeHopStatistics.Retransmissions = [2;3];
            result.NodeHopStatistics.ControlRetransmissions = [4;5];
            result.NodeHopStatistics.ControlFailed = [1;2];
            result.NodeHopStatistics.ControlTargetFailures = [3;4];
            result.NodeNwkStatistics.ControlFailures = [5;6];
            result.NodeNwkStatistics.ControlResidualRetries = [7;8];
            result.NodeNwkStatistics.NeighborDeactivations = [9;10];
            result.NodeNwkStatistics.RouteChanges = [11;12];
            result.NodeNwkStatistics.QueueAdmissionRejections = [13;14];
            result.NodeNwkStatistics.ControlQueueRejections = [15;16];
            row = csr.analysis.performanceSummary(result);
            test.verifyEqual(row.HopDataRetransmissions,5);
            test.verifyEqual(row.HopControlRetransmissions,9);
            test.verifyEqual(row.HopControlFailures,3);
            test.verifyEqual(row.HopControlTargetFailures,7);
            test.verifyEqual(row.ControlFailures,11);
            test.verifyEqual(row.ControlResidualRetries,15);
            test.verifyEqual(row.NeighborDeactivations,19);
            test.verifyEqual(row.RouteChanges,23);
            test.verifyEqual(row.QueueAdmissionRejections,27);
            test.verifyEqual(row.ControlQueueRejections,31);
        end

        function lateDeliveryOverridesAnEarlierDrop(test)
            result = syntheticResult();
            result.ProtocolTrace = [result.ProtocolTrace; traceRow(25,'app_drop',1,'retry_exhausted')];
            result.ProtocolTrace = sortrows(result.ProtocolTrace,'TimeSeconds');
            [row,applications] = csr.analysis.performanceSummary(result);
            test.verifyEqual(row.Dropped,1);
            test.verifyEqual(applications.Outcome{1},'delivered');
            test.verifyEmpty(applications.DropReason{1});
            test.verifyEqual(applications.LastEventSeconds(1),40);
        end

        function lateRelayCustodyRestoresPendingInsteadOfInventingLoss(test)
            result = syntheticResult();
            result.ProtocolTrace = [result.ProtocolTrace; traceRow(60,'relay_accept',2,'')];
            result.ProtocolTrace = sortrows(result.ProtocolTrace,'TimeSeconds');
            result.Statistics.Dropped = 0; result.Statistics.Pending = 1;
            result.NodeStatistics.Dropped(:) = 0;
            result.NodeNwkStatistics.PendingCustody(2) = 1;
            [row,applications] = csr.analysis.performanceSummary(result);
            test.verifyEqual(applications.Outcome{2},'pending');
            test.verifyEqual(applications.LastEventSeconds(2),60);
            test.verifyEmpty(applications.DropReason{2});
            test.verifyTrue(isnan(applications.LatencySeconds(2)));
            test.verifyFalse(row.DataDrained);
            test.verifyFalse(row.ApplicationsDrained);
        end

        function singletonGenerationAtStopHasNoRateDenominator(test)
            result = syntheticResult();
            result.Config.Traffic.StartSeconds = 100;
            result.Config.Traffic.PacketCount = 1;
            result.ProtocolTrace = result.ProtocolTrace(strcmp(result.ProtocolTrace.Event,'tx_start'),:);
            result.ProtocolTrace = [result.ProtocolTrace; traceRow(100,'app_generate',1,'')];
            result = setApplications(result,1,0,0,1);
            [row,applications] = csr.analysis.performanceSummary(result);
            test.verifyEqual(row.GenerationSpanSeconds,0);
            test.verifyEqual(row.TrafficObservationSeconds,0);
            test.verifyEqual(row.PlannedDrainSeconds,0);
            test.verifyTrue(isnan(row.ObservationMeanOfferedLoadBitsPerSecond));
            test.verifyTrue(isnan(row.MaxLatencySeconds));
            test.verifySize(applications,[1 11]);
        end

        function noApplicationsPreserveTypedEmptyTableAndMissingLatency(test)
            result = syntheticResult();
            result.Config.Traffic.PacketCount = 0;
            result.ProtocolTrace = result.ProtocolTrace(strcmp(result.ProtocolTrace.Event,'tx_start'),:);
            result = setApplications(result,0,0,0,0);
            [row,applications] = csr.analysis.performanceSummary(result);
            test.verifySize(applications,[0 11]);
            test.verifyClass(applications.PacketId,'uint64');
            test.verifyTrue(isnan(row.FirstGenerationSeconds));
            test.verifyTrue(isnan(row.PlannedDrainSeconds));
            test.verifyTrue(isnan(row.MaxLatencySeconds));
            test.verifyEqual(row.ScheduledFlowRateSumBitsPerSecond,0);
            test.verifyEqual(row.GeneratedApplicationBytes,0);
        end

        function futureTrafficIsVisibleAsANegativePlannedDrain(test)
            result = syntheticResult();
            future = result.Config.Traffic;
            future.StartSeconds = 110; future.PacketCount = 1;
            result.Config.Traffic = [result.Config.Traffic;future];
            row = csr.analysis.performanceSummary(result);
            test.verifyEqual(row.Generated,3);
            test.verifyEqual(row.PlannedLastGenerationSeconds,110);
            test.verifyEqual(row.PlannedDrainSeconds,-10);
            test.verifyEqual(row.ScheduledFlowRateSumBitsPerSecond,2*8*64/10);
        end

        function acceptsActualShortNetworkResultWithoutChangingIt(test)
            config = csr.scenario.routedNetwork('autonomous');
            config.Nwk.StartupMode = 'manual'; config.DurationSeconds = 0.1;
            config.Traffic.StartSeconds = 0.01; config.Traffic.PacketCount = 1;
            result = csr.runScenario(config); original = result;
            [row,applications] = csr.analysis.performanceSummary(result);
            test.verifyEqual(result,original);
            test.verifyEqual(row.Pending,1);
            test.verifyEqual(applications.Outcome,{'pending'});
            test.verifyFalse(row.DataDrained);
        end

        function retainsStructuralFailureGate(test)
            result = syntheticResult(); result.Statistics.OmittedTraceRecords = 1;
            test.verifyError(@()csr.analysis.performanceSummary(result),'csr:research:TruncatedTrace');
        end

        function rejectsMemberCountsThatDoNotMatchSourceAccounting(test)
            result = syntheticResult(); result.NodeMacStatistics.AckTransmissions(1) = 9;
            test.verifyError(@()csr.analysis.performanceSummary(result), ...
                'csr:performance:TransmissionAccounting');
            result = syntheticResult();
            result.ProtocolTrace(1,:) = [];
            test.verifyError(@()csr.analysis.performanceSummary(result), ...
                'csr:performance:TransmissionAccounting');
        end

        function rejectsOutcomeCountersWithoutSupportingTrace(test)
            result = syntheticResult();
            result.ProtocolTrace(strcmp(result.ProtocolTrace.Event,'app_drop'),:) = [];
            test.verifyError(@()csr.analysis.performanceSummary(result), ...
                'csr:performance:ApplicationOutcome');
        end

        function rejectsUnknownOutcomeIdentitiesAndChangedDscp(test)
            result = syntheticResult();
            result.ProtocolTrace = [result.ProtocolTrace;traceRow(95,'app_drop',999,'unknown')];
            test.verifyError(@()csr.analysis.performanceSummary(result), ...
                'csr:performance:ApplicationIdentity');
            result = syntheticResult();
            result.ProtocolTrace.Dscp(strcmp(result.ProtocolTrace.Event,'app_receive')) = 8;
            test.verifyError(@()csr.analysis.performanceSummary(result), ...
                'csr:performance:ApplicationIdentity');
        end

        function rejectsInvalidDiagnosticCounters(test)
            result = syntheticResult(); result.NodeNwkStatistics.ControlFailures(1) = NaN;
            test.verifyError(@()csr.analysis.performanceSummary(result),'csr:performance:Counter');
            result = syntheticResult(); result.Metadata.PendingEvents = -1;
            test.verifyError(@()csr.analysis.performanceSummary(result),'csr:performance:Counter');
        end
    end
end

function result = syntheticResult()
config = csr.scenario.routedNetwork('autonomous');
config.DurationSeconds = 100;
config.Traffic = config.Traffic(1);
config.Traffic.StartSeconds = 10; config.Traffic.IntervalSeconds = 10;
config.Traffic.PacketCount = 3; config.Traffic.ApplicationPayloadBytes = 64;
stats = struct('Generated',3,'Received',2,'Dropped',1,'Pending',0, ...
    'PhysicalTransmissions',5,'PhysicalAttempts',10,'PhysicalReceived',6, ...
    'PhysicalDropped',4,'PhysicalPending',0,'ApplicationBytesReceived',128, ...
    'OmittedTraceRecords',0,'OmittedPhyTraceRecords',0,'DeliveryRatio',2/3, ...
    'GoodputBitsPerSecond',8*128/100,'MeanLatencySeconds',45,'HopFailures',0, ...
    'DataTransmissions',3,'ControlTransmissions',4);
node = table([3;0],[0;2],[0;1],'VariableNames',{'Generated','Received','Dropped'});
mac = zeroCounters({'MaxDataQueueDepth','Transmissions','SegmentsTransmitted', ...
    'AckTransmissions','ConcatenatedTransmissions','DataQueueDrops','AckQueueDrops'});
mac.Transmissions = [3;2]; mac.SegmentsTransmitted = [4;3];
mac.AckTransmissions = [1;1]; mac.ConcatenatedTransmissions = [1;1];
hop = zeroCounters({'PendingData','ResendQueueDepth','DackHoldCount', ...
    'ControlPending','ControlPendingTargets','ControlTransmitted','Retransmissions', ...
    'ControlRetransmissions','ControlFailed','ControlTargetFailures', ...
    'MacAdmissionRejected','FeedbackQueueDrops'});
hop.ControlTransmitted = [1;1];
nwk = zeroCounters({'PendingCustody','WaitingForRoute','WaitingForHop', ...
    'PendingControlMessages','ControlQueueRejections','RouteChanges', ...
    'ControlFailures','ControlResidualRetries','NeighborActivations', ...
    'NeighborDeactivations','SnapshotTimeouts','QueueAdmissionRejections'});
trace = traceRow(1,'tx_start',0,'');
for k = 2:5, trace = [trace;traceRow(k,'tx_start',0,'')]; end %#ok<AGROW>
for k = 1:3, trace = [trace;traceRow(k*10,'app_generate',k,'')]; end %#ok<AGROW>
trace = [trace;traceRow(40,'app_receive',1,'delivered'); ...
    traceRow(50,'app_drop',2,'queue_full');traceRow(90,'app_receive',3,'delivered')];
metadata = struct('Release','synthetic','RuntimeSeconds',0.25,'PendingEvents',17);
result = struct('Config',config,'Statistics',stats,'Metadata',metadata, ...
    'ProtocolTrace',trace,'PhyTrace',table(),'NodeStatistics',node, ...
    'NodeMacStatistics',mac,'NodeHopStatistics',hop,'NodeNwkStatistics',nwk);
end

function value = zeroCounters(names)
value = array2table(zeros(2,numel(names)),'VariableNames',names);
end

function value = traceRow(time,event,packetId,reason)
node = 1; peer = 2;
if strcmp(event,'app_receive'), node = 2; peer = 1; end
value = table(time,{event},node,peer,uint64(packetId),64,{reason},{'APP'},0,0,0,{''},0, ...
    'VariableNames',{'TimeSeconds','Event','NodeId','PeerId','PacketId', ...
    'ApplicationBytes','Reason','FrameKind','Sequence','Dscp','QueueDepth','ControlType','HopCount'});
end

function result = setApplications(result,generated,received,dropped,pending)
result.Statistics.Generated = generated; result.Statistics.Received = received;
result.Statistics.Dropped = dropped; result.Statistics.Pending = pending;
result.Statistics.ApplicationBytesReceived = received*64;
result.Statistics.DeliveryRatio = NaN; result.Statistics.MeanLatencySeconds = NaN;
result.Statistics.GoodputBitsPerSecond = 8*received*64/result.Config.DurationSeconds;
result.NodeStatistics.Generated = [generated;0];
result.NodeStatistics.Received = [0;received]; result.NodeStatistics.Dropped = [0;dropped];
result.NodeNwkStatistics.PendingCustody = [pending;0];
end
