function [row,applications] = performanceSummary(result)
%PERFORMANCESUMMARY Read-only performance diagnostics for complete network results.
% researchSummary owns the structural gate. Frame members, OTA transmissions,
% receiver observations and application identities remain separate units.
% See docs/tranche-5-performance-metrics.md for each denominator and boundary.
row = csr.analysis.researchSummary(result);
s = result.Statistics; trace = result.ProtocolTrace;
mac = result.NodeMacStatistics; hop = result.NodeHopStatistics;
nwk = result.NodeNwkStatistics;
applications = applicationOutcomes(trace,s);
received = strcmp(applications.Outcome,'delivered');
row.MetricsSchema = 'csr-performance-summary-v1';
row.GeneratedApplicationBytes = sum(applications.ApplicationBytes);
row.FirstGenerationSeconds = NaN; row.LastGenerationSeconds = NaN;
row.GenerationSpanSeconds = NaN; row.TrafficObservationSeconds = NaN;
row.ObservationMeanOfferedLoadBitsPerSecond = NaN;
if ~isempty(applications)
    row.FirstGenerationSeconds = min(applications.GeneratedSeconds);
    row.LastGenerationSeconds = max(applications.GeneratedSeconds);
    row.GenerationSpanSeconds = row.LastGenerationSeconds-row.FirstGenerationSeconds;
    row.TrafficObservationSeconds = row.DurationSeconds-row.FirstGenerationSeconds;
    if row.TrafficObservationSeconds > 0
        row.ObservationMeanOfferedLoadBitsPerSecond = ...
            8*row.GeneratedApplicationBytes/row.TrafficObservationSeconds;
    end
end
row.PlannedLastGenerationSeconds = NaN;
row.PlannedDrainSeconds = NaN;
row.ScheduledFlowRateSumBitsPerSecond = 0;
for k = 1:numel(result.Config.Traffic)
    flow = result.Config.Traffic(k);
    if flow.PacketCount == 0, continue; end
    last = double(flow.StartSeconds)+(double(flow.PacketCount)-1)*double(flow.IntervalSeconds);
    if isnan(row.PlannedLastGenerationSeconds) || last > row.PlannedLastGenerationSeconds
        row.PlannedLastGenerationSeconds = last;
    end
    row.ScheduledFlowRateSumBitsPerSecond = row.ScheduledFlowRateSumBitsPerSecond+ ...
        8*double(flow.ApplicationPayloadBytes)/double(flow.IntervalSeconds);
end
if ~isnan(row.PlannedLastGenerationSeconds)
    row.PlannedDrainSeconds = row.DurationSeconds-row.PlannedLastGenerationSeconds;
end
row.MaxLatencySeconds = NaN;
if any(received), row.MaxLatencySeconds = max(applications.LatencySeconds(received)); end
row.ApplicationsDrained = s.Pending == 0;
row.NwkPendingControlMessages = countTotal(nwk,'PendingControlMessages');
row.WaitingForHop = countTotal(nwk,'WaitingForHop');
row.ControlsDrained = row.ControlPending == 0 && row.ControlPendingTargets == 0 && ...
    row.NwkPendingControlMessages == 0;
row.ControlDrainScope = 'HOP and NWK ownership; current MAC feedback queue depth unavailable';
row.OwnershipDrained = row.DataDrained && row.ControlsDrained;
row.PhysicalAttempts = countTotal(s,'PhysicalAttempts');
row.DataMemberTransmissions = countTotal(s,'DataTransmissions');
row.ControlMemberTransmissions = countTotal(s,'ControlTransmissions');
row.NetworkControlMemberTransmissions = countTotal(hop,'ControlTransmitted');
row.AckFeedbackMemberTransmissions = countTotal(mac,'AckTransmissions');
row.MacMemberTransmissions = countTotal(mac,'SegmentsTransmitted');
row.ConcatenatedTransmissions = countTotal(mac,'ConcatenatedTransmissions');
if countTotal(mac,'Transmissions') ~= row.PhysicalTransmissions || ...
        row.DataMemberTransmissions+row.ControlMemberTransmissions ~= row.MacMemberTransmissions || ...
        row.NetworkControlMemberTransmissions+row.AckFeedbackMemberTransmissions ~= row.ControlMemberTransmissions || ...
        sum(strcmp(trace.Event,'tx_start')) ~= row.PhysicalTransmissions
    error('csr:performance:TransmissionAccounting','MAC, HOP, OTA and trace transmission counts disagree.');
end
row.HopDataRetransmissions = countTotal(hop,'Retransmissions');
row.HopControlRetransmissions = countTotal(hop,'ControlRetransmissions');
row.HopControlFailures = countTotal(hop,'ControlFailed');
row.HopControlTargetFailures = countTotal(hop,'ControlTargetFailures');
row.ControlFailures = countTotal(nwk,'ControlFailures');
row.ControlResidualRetries = countTotal(nwk,'ControlResidualRetries');
row.NeighborActivations = countTotal(nwk,'NeighborActivations');
row.NeighborDeactivations = countTotal(nwk,'NeighborDeactivations');
row.SnapshotTimeouts = countTotal(nwk,'SnapshotTimeouts');
row.QueueAdmissionRejections = countTotal(nwk,'QueueAdmissionRejections');
row.HopMacAdmissionRejections = countTotal(hop,'MacAdmissionRejected');
row.MacDataQueueRejections = countTotal(mac,'DataQueueDrops');
row.MacFeedbackQueueRejections = countTotal(mac,'AckQueueDrops');
row.HopFeedbackQueueDrops = countTotal(hop,'FeedbackQueueDrops');
row.PendingSchedulerEvents = countTotal(result.Metadata,'PendingEvents');
row.ProtocolTraceRecords = height(trace);
row.PhyTraceRecords = height(result.PhyTrace);
% DurationSeconds exists in MAC callback details but is not serialized into
% this result. PHY ends include early receiver failures, not TX completions.
row.AirtimeAvailable = false;
row.TotalTransmitAirtimeSeconds = NaN;
row.DataTransmitAirtimeSeconds = NaN;
row.ControlTransmitAirtimeSeconds = NaN;
row.AckFeedbackTransmitAirtimeSeconds = NaN;
% RuntimeSeconds is elapsed wall time. Neither CPU seconds nor an executed
% scheduler callback count is exported by the unchanged network simulator.
row.CpuTimeAvailable = false; row.CpuTimeSeconds = NaN;
row.ExecutedEventsAvailable = false; row.ExecutedEvents = NaN;
end

function applications = applicationOutcomes(trace,statistics)
sent = trace(strcmp(trace.Event,'app_generate'),:);
n = height(sent);
applications = table(sent.PacketId(:),sent.NodeId(:),sent.PeerId(:), ...
    sent.ApplicationBytes(:),sent.Dscp(:),sent.TimeSeconds(:),sent.TimeSeconds(:), ...
    NaN(n,1),NaN(n,1),repmat({'pending'},n,1),repmat({''},n,1), ...
    'VariableNames',{'PacketId','SourceId','DestinationId','ApplicationBytes','Dscp', ...
    'GeneratedSeconds','LastEventSeconds','ReceivedSeconds','LatencySeconds','Outcome','DropReason'});
if n == 0, return; end
relevant = ismember(trace.Event,{'app_drop','relay_accept','app_receive'});
events = trace(relevant,:);
[known,positions] = ismember(events.PacketId,applications.PacketId);
if ~all(known)
    error('csr:performance:ApplicationIdentity','An application outcome references an unknown generation.');
end
for k = 1:height(events)
    index = positions(k); event = events.Event{k};
    if events.TimeSeconds(k) < applications.GeneratedSeconds(index) || ...
            events.ApplicationBytes(k) ~= applications.ApplicationBytes(index)
        error('csr:performance:ApplicationIdentity','Application outcome time or payload disagrees with generation.');
    end
    if strcmp(applications.Outcome{index},'delivered')
        if strcmp(event,'app_drop')
            error('csr:performance:ApplicationOutcome','Delivered applications cannot be dropped again.');
        end
        continue
    end
    applications.LastEventSeconds(index) = events.TimeSeconds(k);
    if strcmp(event,'app_receive')
        if events.Dscp(k) ~= applications.Dscp(index)
            error('csr:performance:ApplicationIdentity','Delivered application DSCP disagrees with generation.');
        end
        applications.Outcome{index} = 'delivered';
        applications.DropReason{index} = '';
        applications.ReceivedSeconds(index) = events.TimeSeconds(k);
        applications.LatencySeconds(index) = events.TimeSeconds(k)-applications.GeneratedSeconds(index);
    elseif strcmp(event,'app_drop')
        applications.Outcome{index} = 'dropped';
        applications.DropReason{index} = events.Reason{k};
    else
        % A relay may retain late custody after an earlier terminal drop.
        applications.Outcome{index} = 'pending';
        applications.DropReason{index} = '';
    end
end
if sum(strcmp(applications.Outcome,'delivered')) ~= statistics.Received || ...
        sum(strcmp(applications.Outcome,'dropped')) ~= statistics.Dropped || ...
        sum(strcmp(applications.Outcome,'pending')) ~= statistics.Pending
    error('csr:performance:ApplicationOutcome','Reconstructed terminal application outcomes disagree with counters.');
end
end

function value = countTotal(item,name)
if istable(item)
    available = ismember(name,item.Properties.VariableNames);
else
    available = isstruct(item) && isfield(item,name);
end
if ~available
    error('csr:performance:Counter','Missing performance counter %s.',name);
end
values = item.(name);
if ~isnumeric(values) || any(~isfinite(values(:)) | values(:) < 0 | fix(values(:)) ~= values(:))
    error('csr:performance:Counter','Performance counter %s must contain nonnegative integers.',name);
end
value = sum(double(values(:)));
end
