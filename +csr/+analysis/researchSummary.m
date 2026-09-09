function row = researchSummary(result)
%RESEARCHSUMMARY Structural accounting and toolbox-free latency quantiles.
% Finite-stop pending work and packet losses are measurements. A structural
% pass does not assert delivery, convergence, or cross-simulator parity.
required = {'Config','Metadata','Statistics','ProtocolTrace', ...
    'NodeStatistics','NodeMacStatistics','NodeHopStatistics','NodeNwkStatistics'};
if ~isstruct(result) || ~isscalar(result) || ~all(isfield(result,required))
    error('csr:research:Result','A complete network-stack result is required.');
end
s = result.Statistics;
counts = {'Generated','Received','Dropped','Pending','PhysicalTransmissions', ...
    'PhysicalAttempts','PhysicalReceived','PhysicalDropped','PhysicalPending', ...
    'ApplicationBytesReceived','OmittedTraceRecords','OmittedPhyTraceRecords'};
for k = 1:numel(counts)
    name = counts{k};
    if ~isfield(s,name), error('csr:research:Counter','Missing counter %s.',name); end
    value = s.(name);
    if ~isnumeric(value) || ~isscalar(value) || ~isfinite(value) || value < 0 || fix(value) ~= value
        error('csr:research:Counter','Counter %s must be a nonnegative integer.',name);
    end
end
if s.Generated ~= s.Received+s.Dropped+s.Pending || ...
        s.PhysicalAttempts ~= s.PhysicalReceived+s.PhysicalDropped+s.PhysicalPending
    error('csr:research:Accounting','Application or receiver accounting does not balance.');
end
if ~result.Config.Trace.Enabled || s.OmittedTraceRecords ~= 0 || s.OmittedPhyTraceRecords ~= 0
    error('csr:research:TruncatedTrace','Research evidence requires enabled, complete protocol and PHY traces.');
end
expected = 0;
for k = 1:numel(result.Config.Traffic)
    f = result.Config.Traffic(k);
    if f.StartSeconds <= result.Config.DurationSeconds
        count = floor((result.Config.DurationSeconds-f.StartSeconds)/f.IntervalSeconds)+1;
        expected = expected+min(f.PacketCount,count);
    end
end
if s.Generated ~= expected || sum(result.NodeStatistics.Generated) ~= s.Generated || ...
        sum(result.NodeStatistics.Received) ~= s.Received || sum(result.NodeStatistics.Dropped) ~= s.Dropped
    error('csr:research:Generation','Scheduled traffic or node totals disagree with application accounting.');
end
trace = result.ProtocolTrace;
if any(~isfinite(trace.TimeSeconds)) || any(diff(trace.TimeSeconds) < 0)
    error('csr:research:TraceOrder','Protocol trace time must be finite and nondecreasing.');
end
sent = trace(strcmp(trace.Event,'app_generate'),:);
received = trace(strcmp(trace.Event,'app_receive'),:);
if height(sent) ~= s.Generated || height(received) ~= s.Received || ...
        numel(unique(sent.PacketId)) ~= height(sent) || numel(unique(received.PacketId)) ~= height(received)
    error('csr:research:TraceIdentity','Application trace identities or counts disagree with counters.');
end
[known,index] = ismember(received.PacketId,sent.PacketId);
if ~all(known) || any(received.NodeId ~= sent.PeerId(index)) || ...
        any(received.ApplicationBytes ~= sent.ApplicationBytes(index))
    error('csr:research:Delivery','A delivered application has an unknown identity, wrong endpoint or byte count.');
end
latency = received.TimeSeconds-sent.TimeSeconds(index);
if any(latency < 0) || sum(received.ApplicationBytes) ~= s.ApplicationBytesReceived
    error('csr:research:Delivery','Application latency or delivered-byte accounting is invalid.');
end
hop = result.NodeHopStatistics; nwk = result.NodeNwkStatistics;
pendingNames = {'PendingData','ResendQueueDepth','DackHoldCount','ControlPending','ControlPendingTargets'};
for k = 1:numel(pendingNames)
    values = hop.(pendingNames{k});
    if any(~isfinite(values) | values < 0 | fix(values) ~= values)
        error('csr:research:Ownership','HOP ownership counters must be nonnegative integers.');
    end
end
for field = {'PendingCustody','WaitingForRoute','WaitingForHop','PendingControlMessages'}
    values = nwk.(field{1});
    if any(~isfinite(values) | values < 0 | fix(values) ~= values)
        error('csr:research:Ownership','NWK ownership counters must be nonnegative integers.');
    end
end
if any(nwk.PendingCustody > result.Config.Nwk.QueueLimit) || ...
        any(result.NodeMacStatistics.MaxDataQueueDepth > result.Config.Mac.DataQueueLimit)
    error('csr:research:QueueBound','Network custody or MAC data storage exceeded its configured bound.');
end
row = struct('Scenario',result.Config.Name,'Seed',result.Config.Seed, ...
    'DurationSeconds',result.Config.DurationSeconds,'Nodes',numel(result.Config.Nodes), ...
    'Generated',s.Generated,'Received',s.Received,'Dropped',s.Dropped,'Pending',s.Pending, ...
    'ApplicationBytesReceived',s.ApplicationBytesReceived,'DeliveryRatio',s.DeliveryRatio, ...
    'GoodputBitsPerSecond',s.GoodputBitsPerSecond,'MeanLatencySeconds',s.MeanLatencySeconds, ...
    'LatencyP50Seconds',quantileNearest(latency,0.50), ...
    'LatencyP95Seconds',quantileNearest(latency,0.95), ...
    'LatencyP99Seconds',quantileNearest(latency,0.99), ...
    'PhysicalTransmissions',s.PhysicalTransmissions,'PhysicalReceived',s.PhysicalReceived, ...
    'PhysicalDropped',s.PhysicalDropped,'PhysicalPending',s.PhysicalPending, ...
    'HopPendingData',sum(hop.PendingData),'ResendQueueDepth',sum(hop.ResendQueueDepth), ...
    'DackHoldCount',sum(hop.DackHoldCount),'ControlPending',sum(hop.ControlPending), ...
    'ControlPendingTargets',sum(hop.ControlPendingTargets), ...
    'NwkPendingCustody',sum(nwk.PendingCustody),'WaitingForRoute',sum(nwk.WaitingForRoute), ...
    'ControlQueueRejections',sum(nwk.ControlQueueRejections), ...
    'RouteChanges',sum(nwk.RouteChanges),'HopFailures',s.HopFailures, ...
    'RuntimeSeconds',result.Metadata.RuntimeSeconds,'StructuralChecksPassed',true, ...
    'DataDrained',s.Pending == 0 && sum(hop.PendingData) == 0 && ...
        sum(hop.ResendQueueDepth) == 0 && sum(hop.DackHoldCount) == 0 && sum(nwk.PendingCustody) == 0, ...
    'ApplicationProfile',result.Config.ApplicationProfile,'MATLABRelease',result.Metadata.Release);
end

function value = quantileNearest(values,probability)
% Explicit nearest-rank empirical quantile; no Statistics Toolbox dependency.
if isempty(values), value = NaN; return; end
values = sort(values);
value = values(max(1,ceil(probability*numel(values))));
end
