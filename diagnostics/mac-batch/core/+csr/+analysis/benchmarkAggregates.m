function [series,provenance] = benchmarkAggregates(result,options)
%BENCHMARKAGGREGATES Source-defined application bucket statistics for benchmarks.
% The input trace is observation-only. Actual modeled br_Network size is the
% application payload plus the seven-byte NWK header. The historical br_app
% eight-byte exclusion has already been applied by the scenario importer.
% No PHY, queue, or custody statistic is inferred from application totals.
%
% Required options: Scenario, ScenarioSHA256, ProfileID, SourceFile, and
% SourceFileSHA256. BucketWidthSeconds defaults to 60. The caller writes the
% table as CSV and adds provenance.output.sha256 after hashing that output.
if nargin < 2, options = struct(); end
if ~isstruct(options) || ~isscalar(options)
    error('csr:benchmark:Options','Options must be a scalar struct.');
end
allowed = {'Scenario','ScenarioSHA256','ProfileID','SourceFile', ...
    'SourceFileSHA256','BucketWidthSeconds','SourceCommit','SourceSnapshotSHA256'};
if ~isempty(setdiff(fieldnames(options),allowed))
    error('csr:benchmark:Options','Unknown benchmark aggregate option.');
end
scenario = requiredText(options,'Scenario');
scenarioHash = requiredHash(options,'ScenarioSHA256');
profile = requiredText(options,'ProfileID');
sourceFile = requiredText(options,'SourceFile');
sourceHash = requiredHash(options,'SourceFileSHA256');
width = 60;
if isfield(options,'BucketWidthSeconds'), width = options.BucketWidthSeconds; end
if ~isstruct(result) || ~isscalar(result) || ...
        ~all(isfield(result,{'Config','Statistics','ProtocolTrace'}))
    error('csr:benchmark:Result','Missing benchmark result fields.');
end
if ~isstruct(result.Config) || ~isfield(result.Config,'DurationSeconds')
    error('csr:benchmark:Result','Missing benchmark duration.');
end
duration = result.Config.DurationSeconds;
positiveScalar(width,'bucket width'); positiveScalar(duration,'duration');
width = double(width); duration = double(duration);
quotient = double(duration)/double(width); bucketCount = round(quotient);
if bucketCount < 1 || abs(quotient-bucketCount) > max(1e-12,1e-12*abs(bucketCount))
    error('csr:benchmark:Window','Duration must be an integer multiple of bucket width.');
end
statistics = result.Statistics;
if count(statistics,'OmittedTraceRecords') ~= 0
    error('csr:benchmark:TruncatedTrace','A complete protocol trace is required.');
end
generated = count(statistics,'Generated'); received = count(statistics,'Received');
dropped = count(statistics,'Dropped'); pending = count(statistics,'Pending');
if generated ~= received+dropped+pending
    error('csr:benchmark:Accounting','Application outcomes do not partition generations.');
end
trace = result.ProtocolTrace;
required = {'TimeSeconds','Event','NodeId','PeerId','PacketId','ApplicationBytes','Dscp'};
if ~istable(trace) || ~all(ismember(required,trace.Properties.VariableNames))
    error('csr:benchmark:Trace','Missing protocol trace columns.');
end
if ~isnumeric(trace.TimeSeconds) || ~isreal(trace.TimeSeconds)
    error('csr:benchmark:Trace','Trace times must be real numeric seconds.');
end
times = double(trace.TimeSeconds);
if any(~isfinite(times) | times < 0) || any(diff(times) < 0)
    error('csr:benchmark:Trace','Trace times must be finite, nonnegative and ordered.');
end
sent = trace(strcmp(trace.Event,'app_generate'),:);
delivered = trace(strcmp(trace.Event,'app_receive'),:);
if height(sent) ~= generated || height(delivered) ~= received
    error('csr:benchmark:Accounting','Trace generation/delivery counts disagree with counters.');
end
validateApplications(sent); validateApplications(delivered);
if numel(unique(sent.PacketId)) ~= height(sent) || ...
        numel(unique(delivered.PacketId)) ~= height(delivered)
    error('csr:benchmark:Identity','MATLAB application IDs must be unique at generation and delivery.');
end
[known,index] = ismember(delivered.PacketId,sent.PacketId);
if ~all(known)
    error('csr:benchmark:Identity','Delivery references an unknown generation.');
end
if any(delivered.TimeSeconds < sent.TimeSeconds(index)) || ...
        any(delivered.ApplicationBytes ~= sent.ApplicationBytes(index)) || ...
        any(delivered.Dscp ~= sent.Dscp(index)) || ...
        any(delivered.NodeId ~= sent.PeerId(index))
    error('csr:benchmark:Identity','Delivery identity, time, destination or size disagrees with generation.');
end
if sum(double(delivered.ApplicationBytes)) ~= count(statistics,'ApplicationBytesReceived')
    error('csr:benchmark:Accounting','Received payload bytes disagree with the result counter.');
end
latencies = double(delivered.TimeSeconds)-double(sent.TimeSeconds(index));
[sendBucket,sendInWindow,sendAtStop,sendAfterStop] = buckets(sent.TimeSeconds,width,bucketCount);
[receiveBucket,receiveInWindow,receiveAtStop,receiveAfterStop] = ...
    buckets(delivered.TimeSeconds,width,bucketCount);
if any(receiveInWindow & ~sendInWindow(index))
    error('csr:benchmark:Identity','An in-window delivery has no in-window generation.');
end
sendBits = 8*(double(sent.ApplicationBytes)+7);
receiveBits = 8*(double(delivered.ApplicationBytes)+7);
sentCounts = accumulate(sendBucket,ones(height(sent),1),sendInWindow,bucketCount);
sentBitSums = accumulate(sendBucket,sendBits,sendInWindow,bucketCount);
receivedCounts = accumulate(receiveBucket,ones(height(delivered),1),receiveInWindow,bucketCount);
receivedBitSums = accumulate(receiveBucket,receiveBits,receiveInWindow,bucketCount);
delaySums = accumulate(receiveBucket,latencies,receiveInWindow,bucketCount);
packetSizeMeans = sentBitSums./sentCounts;
delayMeans = delaySums./receivedCounts;
values = [sentCounts/width,sentBitSums/width,packetSizeMeans, ...
    receivedCounts/width,receivedCounts,receivedBitSums/width,receivedBitSums,delayMeans];
names = {'Generator.Traffic Sent (packets/sec)','Generator.Traffic Sent (bits/sec)', ...
    'Generator.Packet Size (bits)','Sink.Traffic Received (packets/sec)', ...
    'Sink.Traffic Received (packets)','Sink.Traffic Received (bits/sec)', ...
    'Sink.Traffic Received (bits)','Sink.End-to-End Delay (seconds)'};
units = {'packets/s','bits/s','bits','packets/s','packets','bits/s','bits','s'};
aggregations = {'bucket_sum_per_second','bucket_sum_per_second','bucket_sample_mean', ...
    'bucket_sum_per_second','bucket_sum','bucket_sum_per_second','bucket_sum','bucket_sample_mean'};
n = bucketCount*numel(names);
statistic = reshape(repmat(names,bucketCount,1),n,1);
unit = reshape(repmat(units,bucketCount,1),n,1);
aggregation = reshape(repmat(aggregations,bucketCount,1),n,1);
value = repmat({''},n,1); valueStatus = repmat({'observed'},n,1);
flat = values(:);
for k = 1:n
    if isnan(flat(k)), valueStatus{k} = 'missing';
    else, value{k} = sprintf('%.17g',flat(k)); end
end
series = table(repmat({'csr-aggregate-series-v1'},n,1),repmat({scenario},n,1), ...
    statistic,repmat((1:bucketCount)'*width,numel(names),1),value, ...
    repmat({'matlab'},n,1),unit,aggregation,repmat({''},n,1),valueStatus, ...
    repmat({sourceFile},n,1),repmat({sourceHash},n,1), ...
    'VariableNames',{'schema','scenario','statistic','time_s','value','source', ...
    'unit','aggregation','raw_value','value_status','source_file','source_file_sha256'});
window = struct('start_time_s',0,'stop_time_s',duration,'bucket_width_s',width, ...
    'bucket_count',bucketCount,'timestamp','bucket_end', ...
    'start_endpoint','inclusive','stop_endpoint','exclusive', ...
    'interval','[previous_bucket_end,bucket_end); t=0 included, t=stop excluded', ...
    'boundary_quotient_absolute_tolerance',1e-12);
provenance = struct('schema','csr-benchmark-source-provenance-v1', ...
    'output_schema','csr-aggregate-series-v1','source','matlab','scenario',scenario, ...
    'scenario_sha256',scenarioHash,'profile_id',profile,'window',window, ...
    'source_file',sourceFile,'source_file_sha256',sourceHash);
if isfield(options,'SourceCommit')
    provenance.source_commit = requiredText(options,'SourceCommit');
end
if isfield(options,'SourceSnapshotSHA256')
    provenance.source_snapshot_sha256 = requiredHash(options,'SourceSnapshotSHA256');
end
if isfield(result,'Metadata') && isfield(result.Metadata,'SourceCommit')
    provenance.ns3_reference_commit = result.Metadata.SourceCommit;
end
provenance.application_accounting = struct('generated',generated,'received',received, ...
    'dropped',dropped,'pending',pending,'in_window_sent',sum(sendInWindow), ...
    'in_window_received',sum(receiveInWindow), ...
    'excluded_at_stop_sent',sum(sendAtStop),'excluded_at_stop_received',sum(receiveAtStop), ...
    'excluded_after_stop_sent',sum(sendAfterStop),'excluded_after_stop_received',sum(receiveAfterStop), ...
    'delay_matching','Exact MATLAB application ID; validated final destination, size, DSCP and generation time', ...
    'delivery_semantics','Unique final-destination applications; ns-3 source-proved repeated delivery rows can differ');
provenance.application_size_semantics = struct('payload_field','ProtocolTrace.ApplicationBytes', ...
    'network_header_bytes',7,'derived_bits','8 * (ApplicationBytes + 7)', ...
    'legacy_trace_size_exclusion_bits',0, ...
    'importer_exclusion','Legacy configured bytes minus 8 br_app bytes minus 7 NWK header bytes gives payload');
provenance.missing_sample_mean_bucket_ends_s = struct( ...
    'packet_size',reshape(find(sentCounts == 0)*width,1,[]), ...
    'end_to_end_delay',reshape(find(receivedCounts == 0)*width,1,[]));
provenance.mean_definitions = struct('reported_bucket_mean', ...
    'Arithmetic mean of observed bucket means; not a packet-weighted mean', ...
    'delay_bucket','Arithmetic mean of final-delivery latencies received in the bucket', ...
    'packet_size_bucket','Arithmetic mean of modeled br_Network bits generated in the bucket');
provenance.semantic_limits = {'Aggregate observations do not establish OPNET packet/event equivalence.', ...
    'Different seeds, generators, MAC/envelope profiles or observation windows must not be silently compared.', ...
    'PHY/ECC and queue sample statistics are unavailable from these application observations.', ...
    'Missing sample means remain empty and do not become zero.'};
if isfield(result,'ApplicationAdmissionStatistics')
    provenance.application_admission = admissionSummary(result.ApplicationAdmissionStatistics,generated);
end
end

function [index,inWindow,atStop,afterStop] = buckets(times,width,bucketCount)
quotient = double(times)/double(width); nearest = round(quotient);
snap = abs(quotient-nearest) <= 1e-12; quotient(snap) = nearest(snap);
atStop = quotient == bucketCount; afterStop = quotient > bucketCount;
inWindow = quotient >= 0 & quotient < bucketCount;
index = floor(quotient)+1;
end

function totals = accumulate(index,values,include,bucketCount)
totals = zeros(bucketCount,1);
if any(include), totals = accumarray(index(include),values(include),[bucketCount,1],@sum,0); end
end

function validateApplications(rows)
for name = {'PacketId','NodeId','PeerId','ApplicationBytes','Dscp'}
    values = rows.(name{1});
    if ~isnumeric(values) || ~isreal(values) || any(~isfinite(values) | values < 0 | fix(values) ~= values)
        error('csr:benchmark:Identity','Application identities and sizes must be nonnegative integers.');
    end
end
if any(rows.PacketId == 0) || any(rows.NodeId > 16777214 | rows.PeerId > 16777214) || ...
        any(rows.Dscp > 255)
    error('csr:benchmark:Identity','Application ID, endpoint or DSCP is outside the supported range.');
end
end

function summary = admissionSummary(rows,generated)
names = {'Attempts','Admitted','BlockedDiscovery','BlockedTopology', ...
    'BlockedGatewayRoute','BlockedDestination','BlockedNsdp'};
if ~istable(rows) || ~all(ismember(names,rows.Properties.VariableNames))
    error('csr:benchmark:Admission','Application admission counters are incomplete.');
end
totals = zeros(1,numel(names));
for k = 1:numel(names)
    values = rows.(names{k});
    if ~isnumeric(values) || ~isreal(values) || any(~isfinite(values) | values < 0 | fix(values) ~= values)
        error('csr:benchmark:Admission','Application admission counters must be nonnegative integers.');
    end
    totals(k) = sum(double(values));
end
if any(rows.Attempts ~= sum(rows{:,names(2:end)},2)) || totals(2) ~= generated
    error('csr:benchmark:Admission','Application decisions must partition attempts and match actual generations.');
end
summary = cell2struct(num2cell(totals),names,2);
summary.Semantics = 'Generator attempts include pre-creation gate blocks; traffic-sent series counts admitted app_generate only';
end

function value = count(object,name)
if ~isstruct(object) || ~isfield(object,name)
    error('csr:benchmark:Accounting','Missing application counter %s.',name);
end
value = object.(name);
if ~isnumeric(value) || ~isreal(value) || ~isscalar(value) || ~isfinite(value) || value < 0 || fix(value) ~= value
    error('csr:benchmark:Accounting','Counter %s must be a nonnegative integer.',name);
end
value = double(value);
end

function positiveScalar(value,label)
if ~isnumeric(value) || ~isreal(value) || ~isscalar(value) || ~isfinite(value) || value <= 0
    error('csr:benchmark:Window','%s must be finite and positive.',label);
end
end

function value = requiredText(options,name)
if ~isfield(options,name), error('csr:benchmark:Options','Missing option %s.',name); end
value = options.(name);
if isstring(value) && isscalar(value), value = char(value); end
if ~ischar(value) || ~isrow(value) || isempty(strtrim(value))
    error('csr:benchmark:Options','Option %s must be nonempty text.',name);
end
end

function value = requiredHash(options,name)
value = requiredText(options,name);
if isempty(regexp(value,'^[0-9a-f]{64}$','once'))
    error('csr:benchmark:Options','Option %s must be a lowercase SHA-256.',name);
end
end
