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
if isfield(result.Config,'ApplicationGenerator') && ...
        strcmp(result.Config.ApplicationGenerator,'historical-opnet-gated')
    expected = historicalGeneration(result);
else
    for k = 1:numel(result.Config.Traffic)
        f = result.Config.Traffic(k);
        if f.StartSeconds <= result.Config.DurationSeconds
            count = floor((result.Config.DurationSeconds-f.StartSeconds)/f.IntervalSeconds)+1;
            expected = expected+min(f.PacketCount,count);
        end
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

function admitted = historicalGeneration(result)
% An attempt blocked by br_app creates no application packet. Complete
% per-flow counters are required even when the separate admission trace is
% explicitly bounded; the main protocol/PHY traces remain complete gates.
if ~all(isfield(result,{'ApplicationAdmissionStatistics','ApplicationAdmissionTrace'}))
    error('csr:research:Admission','Historical execution needs admission evidence.');
end
rows = result.ApplicationAdmissionStatistics;
trace = result.ApplicationAdmissionTrace;
names = {'Attempts','Admitted','BlockedDiscovery','BlockedTopology', ...
    'BlockedGatewayRoute','BlockedDestination','BlockedNsdp'};
required = [{'FlowIndex','SourceId','ConfiguredDestinationId'},names];
if ~istable(rows) || ~all(ismember(required,rows.Properties.VariableNames)) || ...
        height(rows) ~= numel(result.Config.Traffic) || ...
        ~isequal(double(rows.FlowIndex(:)),(1:height(rows))')
    error('csr:research:Admission','Admission rows must identify every configured flow.');
end
values = rows{:,names};
if any(~isfinite(values(:)) | values(:)<0 | fix(values(:))~=values(:)) || ...
        any(rows.Attempts ~= sum(values(:,2:end),2))
    error('csr:research:Admission','Every attempt must partition into admission or one gate reason.');
end
limit = result.Config.ApplicationFlowLimit;
for k = 1:height(rows)
    flow = result.Config.Traffic(k);
    stopTick = round(result.Config.DurationSeconds*1e9);
    startTick = round(flow.StartSeconds*1e9);
    intervalTick = round(flow.IntervalSeconds*1e9);
    if intervalTick<1
        error('csr:research:Admission','Historical attempts require at least one nanosecond intervals.');
    end
    possible = min(flow.PacketCount,max(0,floor((stopTick-1-startTick)/intervalTick)+1));
    if rows.SourceId(k)~=flow.SourceId || rows.ConfiguredDestinationId(k)~=flow.DestinationId || ...
            rows.Attempts(k)>possible || (limit>0 && rows.Admitted(k)>limit) || ...
            ((limit==0 || rows.Admitted(k)<limit) && rows.Attempts(k)~=possible)
        error('csr:research:Admission','Timed attempts, endpoints or admitted cap disagree with the configuration.');
    end
end
required = {'TimeSeconds','FlowIndex','AttemptIndex','SourceId', ...
    'DestinationId','PacketId','Accepted','Reason'};
if ~istable(trace) || ~all(ismember(required,trace.Properties.VariableNames)) || ...
        ~isfield(result.Statistics,'OmittedApplicationAdmissionRecords')
    error('csr:research:Admission','Admission trace and its explicit omission count are required.');
end
omitted = result.Statistics.OmittedApplicationAdmissionRecords;
if ~isnumeric(omitted) || ~isscalar(omitted) || ~isfinite(omitted) || ...
        omitted<0 || fix(omitted)~=omitted || ...
        height(trace)+omitted~=sum(rows.Attempts)
    error('csr:research:Admission','Bounded trace coverage does not equal all counted attempts.');
end
if any(~isfinite(trace.TimeSeconds)) || any(diff(trace.TimeSeconds)<0) || ...
        any(trace.TimeSeconds<0 | trace.TimeSeconds>=result.Config.DurationSeconds) || ...
        any(~isfinite(trace.FlowIndex) | trace.FlowIndex<1 | ...
            trace.FlowIndex>height(rows) | fix(trace.FlowIndex)~=trace.FlowIndex) || ...
        any(~ismember(double(trace.Accepted),[0 1]))
    error('csr:research:Admission','Admission trace time, flow or success flag is invalid.');
end
reasons = {'discovery_active','topology_unknown','gateway_route_unknown', ...
    'destination_unavailable','nsdp_full'};
yes = logical(trace.Accepted);
if any(trace.PacketId(~yes)~=0) || any(trace.PacketId(yes)==0) || ...
        any(~ismember(trace.Reason(~yes),reasons)) || ...
        any(~strcmp(trace.Reason(yes),'admitted'))
    error('csr:research:Admission','A blocked attempt cannot own a packet or an unknown reason.');
end
for k = 1:height(rows)
    selected = trace.FlowIndex==k;
    indices = trace.AttemptIndex(selected);
    if any(~isfinite(indices) | indices<1 | fix(indices)~=indices | indices>rows.Attempts(k)) || ...
            any(diff(indices)~=1) || (~isempty(indices) && indices(1)~=1) || ...
            any(trace.SourceId(selected)~=rows.SourceId(k))
        error('csr:research:Admission','Recorded attempts must be the ordered prefix for each flow.');
    end
    flow = result.Config.Traffic(k);
    ticks = round(flow.StartSeconds*1e9)+(indices-1)*round(flow.IntervalSeconds*1e9);
    if any(abs(trace.TimeSeconds(selected)-ticks/1e9)>1e-12)
        error('csr:research:Admission','Recorded attempt times disagree with the configured interrupt schedule.');
    end
    observed = zeros(1,numel(names)-1);
    observed(1) = sum(yes(selected));
    for j = 1:numel(reasons)
        observed(j+1) = sum(strcmp(trace.Reason(selected),reasons{j}));
    end
    counted = values(k,2:end);
    if any(observed>counted) || (omitted==0 && any(observed~=counted))
        error('csr:research:Admission','Observed admission reasons disagree with per-flow counters.');
    end
end
sent = result.ProtocolTrace(strcmp(result.ProtocolTrace.Event,'app_generate'),:);
accepted = trace(yes,:);
[known,index] = ismember(accepted.PacketId,sent.PacketId);
if ~all(known) || numel(unique(accepted.PacketId))~=height(accepted) || ...
        any(accepted.TimeSeconds~=sent.TimeSeconds(index)) || ...
        any(accepted.SourceId~=sent.NodeId(index)) || any(accepted.DestinationId~=sent.PeerId(index))
    error('csr:research:Admission','Admitted identities do not match actual generated applications.');
end
if omitted==0 && height(accepted)~=sum(rows.Admitted)
    error('csr:research:Admission','A complete admission trace must contain every admitted application.');
end
admitted = sum(rows.Admitted);
end

function value = quantileNearest(values,probability)
% Explicit nearest-rank empirical quantile; no Statistics Toolbox dependency.
if isempty(values), value = NaN; return; end
values = sort(values);
value = values(max(1,ceil(probability*numel(values))));
end
