function summary = batch_case_analysis(result,applications,caseDir,referenceDir,targetPercent)
%BATCH_CASE_ANALYSIS Finite-stop accounting against the pinned native ledger.
% No simulation callbacks or production changes. The raw trace is retained for
% a separate offline causal-path decomposition after this owner return.
validateattributes(targetPercent,{'numeric'},{'scalar','real','finite','positive'});
seed=double(result.Config.Seed); stop=double(result.Config.DurationSeconds);
sources=[2 3 4 5 7 8]; start=300; horizons=[60 300 600 1200];
if ~ismember(seed,[131 132]) || stop~=6000
    error('csr6000:AnalysisScope','Expected seed 131/132 at the 6000-second cutoff.');
end
nativePath=fullfile(referenceDir,'applications.csv');
nativeCountsPath=fullfile(referenceDir,'app-admission-diagnostics.csv');
native=readtable(nativePath,'TextType','string','VariableNamingRule','preserve');
nativeCounts=readtable(nativeCountsPath,'TextType','string','VariableNamingRule','preserve');
requireColumns(native,{'model','seed','source','destination','native_app_id', ...
    'attempt_index_0based','generated_time_ns','source_admitted_time_ns', ...
    'first_delivery_time_ns','delivery_event_count','status','cutoff_ns','latency_ns', ...
    'proven_terminal_drop_count_lower_bound'});
requireColumns(nativeCounts,{'source','configured_destination','attempts','admitted', ...
    'blocked_discovery','blocked_topology','blocked_gateway_route','blocked_destination','blocked_nsdp'});
requireColumns(applications,{'PacketId','SourceId','DestinationId','GeneratedSeconds', ...
    'ReceivedSeconds','LatencySeconds','Outcome','DropReason'});
if any(double(native.seed)~=seed) || any(double(native.cutoff_ns)~=round(stop*1e9)) || ...
        any(string(native.model)~="native")
    error('csr6000:ReferenceIdentity','Native ledger seed, model or cutoff differs.');
end
flows=result.Config.Traffic;
if numel(flows)~=numel(sources) || ~isequal(sort(double([flows.SourceId])),sources) || ...
        any([flows.DestinationId]~=1) || any([flows.StartSeconds]~=start) || ...
        any([flows.IntervalSeconds]~=0.02) || any([flows.PacketCount]~=285000) || ...
        ~isequal(sort(double(nativeCounts.source(:))).',sources)
    error('csr6000:AttemptSchedule','Expected the six original fixed campus schedules.');
end
counts=result.ApplicationAdmissionStatistics;
requireColumns(counts,{'SourceId','ConfiguredDestinationId','Attempts','Admitted', ...
    'BlockedDiscovery','BlockedTopology','BlockedGatewayRoute','BlockedDestination','BlockedNsdp'});
if ~isequal(sort(double(counts.SourceId(:))).',sources)
    error('csr6000:AdmissionSources','Admission counters must contain exactly the six sources.');
end
matlab=matlabPopulation(applications,result.ProtocolTrace,flows,stop);
reference=nativePopulation(native,flows,stop);
populations={matlab,reference}; models={'matlab','native'};
accounting=repmat(accountTemplate(),12,1); index=0;
for modelIndex=1:2
    p=populations{modelIndex};
    for source=sources
        index=index+1; selected=p.Source==source;
        if modelIndex==1
            c=counts(counts.SourceId==source,:);
            attempted=double(c.Attempts); admitted=double(c.Admitted);
            blocked=double(c{1,{'BlockedDiscovery','BlockedTopology','BlockedGatewayRoute', ...
                'BlockedDestination','BlockedNsdp'}});
        else
            c=nativeCounts(nativeCounts.source==source,:);
            attempted=double(c.attempts); admitted=double(c.admitted);
            blocked=double(c{1,{'blocked_discovery','blocked_topology','blocked_gateway_route', ...
                'blocked_destination','blocked_nsdp'}});
        end
        if attempted~=285000 || admitted~=sum(selected) || ...
                any(blocked<0 | fix(blocked)~=blocked) || admitted+sum(blocked)~=attempted
            error('csr6000:Accounting','Source %d %s admission counters do not close.',source,models{modelIndex});
        end
        a=describe(p,selected,attempted,modelIndex==1);
        a.model=models{modelIndex}; a.seed=seed; a.source=source;
        a.blocked_discovery=blocked(1); a.blocked_topology=blocked(2);
        a.blocked_gateway_route=blocked(3); a.blocked_destination=blocked(4);
        a.blocked_nsdp=blocked(5); accounting(index)=a;
    end
end
if sum([accounting(1:6).admitted])~=result.Statistics.Generated || ...
        sum([accounting(1:6).delivered])~=result.Statistics.Received || ...
        sum([accounting(1:6).raw_model_dropped])~=result.Statistics.Dropped || ...
        sum([accounting(1:6).raw_model_pending])~=result.Statistics.Pending
    error('csr6000:OutcomeCounts','Application outcomes disagree with current run counters.');
end

comparisons=repmat(comparisonTemplate(),6,1);
for k=1:6
    m=accounting(k); n=accounting(k+6); c=comparisonTemplate();
    c.seed=seed; c.source=sources(k); c.target_percent=targetPercent;
    c.matlab_delivered=m.delivered; c.native_delivered=n.delivered;
    c.matlab_mean_delivered_latency_s=m.mean_delivered_latency_s;
    c.native_mean_delivered_latency_s=n.mean_delivered_latency_s;
    [c.delivered_signed_relative_percent,c.delivered_absolute_relative_percent, ...
        c.delivered_relative_defined,c.delivered_target_pass,c.delivered_comparison_status]= ...
        relativeMetric(m.delivered,n.delivered,targetPercent,true);
    [c.latency_signed_relative_percent,c.latency_absolute_relative_percent, ...
        c.latency_relative_defined,c.latency_target_pass,c.latency_comparison_status]= ...
        relativeMetric(m.mean_delivered_latency_s,n.mean_delivered_latency_s,targetPercent,false);
    comparisons(k)=c;
end

fixedAge=repmat(horizonTemplate(),numel(horizons)*2*7,1); index=0;
for horizon=horizons
    endExclusive=stop-horizon;
    for modelIndex=1:2
        p=populations{modelIndex};
        for source=[0 sources]
            index=index+1;
            sourceSelected=true(size(p.Source)); selectedSources=sources;
            if source~=0, sourceSelected=p.Source==source; selectedSources=source; end
            eligible=sourceSelected & p.GeneratedNS>=round(start*1e9) & ...
                p.GeneratedNS<round(endExclusive*1e9);
            scheduled=0;
            for so=selectedSources
                f=flows([flows.SourceId]==so);
                scheduled=scheduled+scheduledCount(f,round(start*1e9),round(endExclusive*1e9));
            end
            timely=eligible & p.Delivered & p.DeliveryNS<=p.GeneratedNS+round(horizon*1e9);
            later=eligible & p.Delivered & ~timely;
            h=horizonTemplate(); h.model=models{modelIndex}; h.seed=seed; h.source=source;
            h.horizon_s=horizon; h.generation_start_s=start;
            h.generation_end_exclusive_s=endExclusive; h.scheduled_attempts=scheduled;
            h.admitted=sum(eligible); h.not_admitted=scheduled-h.admitted;
            h.delivered_by_age=sum(timely); h.delivered_later_by_stop=sum(later);
            h.unresolved_at_stop=sum(eligible & p.Unresolved);
            h.proven_terminal_drop_lower_bound=sum(p.DropLowerBound(eligible));
            if modelIndex==1
                h.raw_model_dropped_by_stop=sum(eligible & p.Dropped);
                h.raw_model_pending_at_stop=sum(eligible & p.Pending);
            end
            h.fraction_of_scheduled=ratio(h.delivered_by_age,scheduled);
            h.fraction_of_admitted=ratio(h.delivered_by_age,h.admitted);
            h.admissions_outside_window=sum(sourceSelected)-h.admitted;
            if h.not_admitted<0 || h.delivered_by_age+h.delivered_later_by_stop+ ...
                    sum(eligible & ~p.Delivered)~=h.admitted
                error('csr6000:HorizonAccounting','Fixed-age accounting failed.');
            end
            fixedAge(index)=h;
        end
    end
end

totals=struct();
for modelIndex=1:2
    p=populations{modelIndex};
    t=describe(p,true(size(p.Source)),sum([accounting((modelIndex-1)*6+(1:6)).attempted]),modelIndex==1);
    t.model=models{modelIndex}; t.seed=seed; t.source=0;
    for field={'blocked_discovery','blocked_topology','blocked_gateway_route','blocked_destination','blocked_nsdp'}
        t.(field{1})=sum([accounting((modelIndex-1)*6+(1:6)).(field{1})]);
    end
    totals.(models{modelIndex})=t;
end
common=[accounting(1:6).delivered]>0 & [accounting(7:12).delivered]>0;
weights=zeros(1,6);
if any(common)
    nativeDelivered=[accounting(7:12).delivered];
    weights(common)=nativeDelivered(common)/sum(nativeDelivered(common));
    mmean=sum(weights(common).*[accounting(find(common)).mean_delivered_latency_s]); %#ok<FNDSB>
    nmean=sum(weights(common).*[accounting(6+find(common)).mean_delivered_latency_s]);
else
    mmean=NaN; nmean=NaN;
end
standardized=struct('scope','within_seed_common_source_delivered_populations', ...
    'weighting','native_delivered_counts_normalized_over_common_sources', ...
    'sources',sources,'common_source_mask',common,'weights',weights, ...
    'common_sources',sources(common),'excluded_sources',sources(~common), ...
    'matlab_weighted_mean_latency_s',mmean,'native_weighted_mean_latency_s',nmean, ...
    'matlab_excluded_deliveries',sum([accounting(find(~common)).delivered]), ...
    'native_excluded_deliveries',sum([accounting(6+find(~common)).delivered]), ...
    'comparison_is_descriptive_not_acceptance_gate',true);
[standardized.signed_relative_percent,standardized.absolute_relative_percent, ...
    standardized.relative_defined,~,standardized.comparison_status]=relativeMetric(mmean,nmean,targetPercent,false);
[pooledSigned,pooledAbsolute,pooledDefined,~,pooledStatus]=relativeMetric( ...
    totals.matlab.mean_delivered_latency_s,totals.native.mean_delivered_latency_s,targetPercent,false);

analysisDir=fullfile(caseDir,'analysis');
if ~isfolder(analysisDir), mkdir(analysisDir); end
writeRows(fullfile(analysisDir,'source_accounting.csv'),accounting);
writeRows(fullfile(analysisDir,'source_target_comparison.csv'),comparisons);
writeRows(fullfile(analysisDir,'fixed_age_delivery.csv'),fixedAge);
matlabLedger=populationTable(matlab,seed,'matlab');
nativeLedger=populationTable(reference,seed,'native');
writetable(matlabLedger,fullfile(analysisDir,'admitted_identity_ledger.csv'));
writetable(matlabLedger(~matlab.Delivered,:),fullfile(analysisDir,'matlab_unfinished.csv'));
writetable(nativeLedger(~reference.Delivered,:),fullfile(analysisDir,'native_unresolved.csv'));

definedCounts=[comparisons.delivered_relative_defined];
definedLatency=[comparisons.latency_relative_defined];
evaluatedPass=[comparisons(definedCounts).delivered_target_pass,comparisons(definedLatency).latency_target_pass];
allDefined=all(definedCounts & definedLatency);
summary=struct('schema','csr6000-case-comparison-v2','completed',true, ...
    'seed',seed,'cutoff_s',stop,'target_percent',targetPercent, ...
    'acceptance_established',false,'network_parity_established',false, ...
    'target_scope','Per-source delivered counts and delivered-only mean latency relative to nonzero native values.', ...
    'relative_count_cells_evaluated',sum(definedCounts), ...
    'relative_latency_cells_evaluated',sum(definedLatency), ...
    'all_sources_have_defined_relative_metrics',allDefined, ...
    'all_evaluated_relative_targets_pass',~isempty(evaluatedPass) && all(evaluatedPass==1), ...
    'all_source_relative_targets_pass',allDefined && all(evaluatedPass==1), ...
    'totals',totals,'source_accounting',accounting,'source_comparisons',comparisons, ...
    'raw_pooled_latency_comparison',struct('signed_relative_percent',pooledSigned, ...
        'absolute_relative_percent',pooledAbsolute,'relative_defined',pooledDefined, ...
        'comparison_status',pooledStatus,'comparison_is_descriptive_not_acceptance_gate',true), ...
    'native_delivery_weighted_latency',standardized, ...
    'fixed_age_horizons_s',horizons, ...
    'fixed_age_method','For each T, identical half-open generation window [300,6000-T); final delivery by generation+T over scheduled attempts and admitted applications separately.', ...
    'phase_analysis_status','pending_offline_analysis_of_complete_returned_protocol_trace', ...
    'matlab_raw_outcome_semantics','Raw dropped/pending counters are preserved; all admitted-but-undelivered applications remain unresolved at cutoff. No proven final loss or live-copy split is inferred.', ...
    'native_application_sha256',csr.validation.Artifacts.sha256(nativePath), ...
    'native_admission_counter_sha256',csr.validation.Artifacts.sha256(nativeCountsPath), ...
    'quantile_method','Linear interpolation at index 1+(n-1)*p; core MATLAB only.', ...
    'limitations',{{'Same numeric seed or scheduled interrupt does not pair random streams or application IDs.', ...
        'Delivered latency is conditioned on completion by the cutoff; unfinished ages are not latency.', ...
        'Native unresolved identities may include unobserved terminal losses; native terminal-drop and live-pending totals remain unknown.', ...
        'MATLAB raw dropped is provisional custody loss recoverable by late copies; raw pending and dropped do not establish the final loss/live-copy split.', ...
        'Zero native reference values have undefined relative error; zero-zero counts are reported separately.', ...
        'Common-source weighting excludes unsupported sources explicitly and does not establish whole-network parity.'}});
csr.validation.Artifacts.writeJson(fullfile(analysisDir,'comparison_summary.json'),summary);
end

function p=matlabPopulation(a,trace,flows,stop)
p=populationTemplate(height(a)); p.Source=double(a.SourceId); p.Destination=double(a.DestinationId);
p.AppId=double(a.PacketId); p.GeneratedNS=round(double(a.GeneratedSeconds)*1e9);
p.DeliveryNS=round(double(a.ReceivedSeconds)*1e9); p.Status=string(a.Outcome);
if any(~ismember(p.Status,["delivered","dropped","pending"]))
    error('csr6000:Outcome','Unknown MATLAB application outcome.');
end
p.Delivered=p.Status=="delivered"; p.DeliveryEventCount=double(p.Delivered); p.Dropped=p.Status=="dropped";
p.Pending=p.Status=="pending"; p.Unresolved=~p.Delivered; p.DropLowerBound=zeros(height(a),1);
p.LatencySeconds=double(a.LatencySeconds); p.DropReason=string(a.DropReason);
p.RawModelOutcome=p.Status; p.Status(~p.Delivered)="unresolved_at_cutoff";
p.AttemptIndex=attemptIndices(p,flows); p.AgeAtCutoff=stop-p.GeneratedNS/1e9;
p.LastCustodyNode=p.Source; p.LastCustodyTime=p.GeneratedNS/1e9;
requireColumns(trace,{'Event','PacketId','NodeId','TimeSeconds'});
relay=trace(strcmp(trace.Event,'relay_accept'),:);
[known,positions]=ismember(double(relay.PacketId),p.AppId);
if ~all(known), error('csr6000:CustodyIdentity','Unknown relay-custody application.'); end
for k=1:height(relay)
    index=positions(k); p.LastCustodyNode(index)=double(relay.NodeId(k));
    p.LastCustodyTime(index)=double(relay.TimeSeconds(k));
end
validatePopulation(p,stop);
end

function p=nativePopulation(a,flows,stop)
p=populationTemplate(height(a)); p.Source=double(a.source); p.Destination=double(a.destination);
p.AppId=double(a.native_app_id); p.GeneratedNS=double(a.generated_time_ns);
p.DeliveryNS=double(a.first_delivery_time_ns); p.Status=string(a.status);
if any(~ismember(p.Status,["delivered","unresolved_at_cutoff"])) || ...
        any(double(a.source_admitted_time_ns)~=p.GeneratedNS)
    error('csr6000:NativeFate','Native fixture fate or admission semantics changed.');
end
p.RawModelOutcome=repmat("not_available",height(a),1);
p.Delivered=p.Status=="delivered"; p.Unresolved=~p.Delivered;
p.DeliveryEventCount=double(a.delivery_event_count);
p.LatencySeconds=double(a.latency_ns)/1e9;
p.DropLowerBound=double(a.proven_terminal_drop_count_lower_bound);
p.AttemptIndex=attemptIndices(p,flows);
if any(p.AttemptIndex~=double(a.attempt_index_0based)) || ...
        any(~isfinite(p.DeliveryEventCount) | fix(p.DeliveryEventCount)~=p.DeliveryEventCount) || ...
        any(p.DeliveryEventCount(p.Delivered)<1) || any(p.DeliveryEventCount(~p.Delivered)~=0)
    error('csr6000:NativeIdentity','Native attempt identity or first-delivery count differs.');
end
p.AgeAtCutoff=stop-p.GeneratedNS/1e9; validatePopulation(p,stop);
end

function p=populationTemplate(n)
p=struct('Source',zeros(n,1),'Destination',zeros(n,1),'AppId',zeros(n,1), ...
    'GeneratedNS',zeros(n,1),'DeliveryNS',NaN(n,1),'AttemptIndex',zeros(n,1), ...
    'Status',strings(n,1),'RawModelOutcome',strings(n,1),'Delivered',false(n,1),'DeliveryEventCount',zeros(n,1),'Dropped',false(n,1), ...
    'Pending',false(n,1),'Unresolved',false(n,1),'DropLowerBound',zeros(n,1), ...
    'LatencySeconds',NaN(n,1),'DropReason',strings(n,1),'AgeAtCutoff',zeros(n,1), ...
    'LastCustodyNode',NaN(n,1),'LastCustodyTime',NaN(n,1));
end

function indices=attemptIndices(p,flows)
indices=NaN(size(p.Source));
for k=1:numel(flows)
    f=flows(k); selected=p.Source==f.SourceId;
    indices(selected)=(p.GeneratedNS(selected)-round(f.StartSeconds*1e9))/round(f.IntervalSeconds*1e9);
    if any(indices(selected)<0 | indices(selected)>=f.PacketCount | fix(indices(selected))~=indices(selected))
        error('csr6000:AttemptIdentity','Application generation is off the fixed attempt schedule.');
    end
end
if any(~isfinite(indices)) || size(unique([p.Source indices],'rows'),1)~=numel(indices)
    error('csr6000:AttemptIdentity','Unknown source or duplicate admitted scheduled attempt.');
end
end

function validatePopulation(p,stop)
if numel(unique(p.AppId))~=numel(p.AppId) || any(p.GeneratedNS<0 | p.GeneratedNS>=round(stop*1e9)) || ...
        any(p.Destination~=1) || any(~isfinite(p.LatencySeconds(p.Delivered))) || ...
        any(p.LatencySeconds(p.Delivered)<0) || ...
        any(p.DeliveryNS(p.Delivered)<p.GeneratedNS(p.Delivered) | p.DeliveryNS(p.Delivered)>round(stop*1e9)) || ...
        any(isfinite(p.LatencySeconds(~p.Delivered))) || any(isfinite(p.DeliveryNS(~p.Delivered))) || ...
        any(abs(p.LatencySeconds(p.Delivered)-(p.DeliveryNS(p.Delivered)-p.GeneratedNS(p.Delivered))/1e9)>2e-9)
    error('csr6000:ApplicationLedger','Invalid admitted identity, outcome time or latency.');
end
end

function a=describe(p,selected,attempted,isMatlab)
a=accountTemplate(); d=selected & p.Delivered; u=selected & p.Unresolved;
a.attempted=attempted; a.admitted=sum(selected); a.not_admitted=attempted-a.admitted;
a.delivered=sum(d); a.undelivered_total=sum(selected & ~p.Delivered);
a.delivery_events=sum(p.DeliveryEventCount(selected));
a.duplicate_delivery_events=a.delivery_events-a.delivered;
a.proven_terminal_drop_lower_bound=sum(p.DropLowerBound(selected));
a.unresolved_at_cutoff=sum(u);
if isMatlab
    a.raw_model_dropped=sum(selected & p.Dropped); a.raw_model_pending=sum(selected & p.Pending);
    a.terminal_drop_total_known=false;
end
a.delivery_fraction_of_attempts=ratio(a.delivered,attempted);
a.delivery_fraction_of_admitted=ratio(a.delivered,a.admitted);
a.mean_delivered_latency_s=average(p.LatencySeconds(d));
a.p50_delivered_latency_s=quantileCore(p.LatencySeconds(d),0.5);
a.p95_delivered_latency_s=quantileCore(p.LatencySeconds(d),0.95);
a.max_delivered_latency_s=maximum(p.LatencySeconds(d));
a.mean_unresolved_age_s=average(p.AgeAtCutoff(u));
a.p95_unresolved_age_s=quantileCore(p.AgeAtCutoff(u),0.95);
a.max_unresolved_age_s=maximum(p.AgeAtCutoff(u));
end

function a=accountTemplate()
a=struct('model','','seed',0,'source',0,'destination',1,'attempted',0,'admitted',0, ...
    'not_admitted',0,'delivered',0,'delivery_events',0,'duplicate_delivery_events',0, ...
    'raw_model_dropped',NaN,'raw_model_pending',NaN, ...
    'unresolved_at_cutoff',0,'undelivered_total',0,'proven_terminal_drop_lower_bound',0, ...
    'terminal_drop_total_known',false,'blocked_discovery',0,'blocked_topology',0, ...
    'blocked_gateway_route',0,'blocked_destination',0,'blocked_nsdp',0, ...
    'delivery_fraction_of_attempts',NaN,'delivery_fraction_of_admitted',NaN, ...
    'mean_delivered_latency_s',NaN,'p50_delivered_latency_s',NaN, ...
    'p95_delivered_latency_s',NaN,'max_delivered_latency_s',NaN, ...
    'mean_unresolved_age_s',NaN,'p95_unresolved_age_s',NaN,'max_unresolved_age_s',NaN);
end

function c=comparisonTemplate()
c=struct('seed',0,'source',0,'target_percent',NaN,'matlab_delivered',0,'native_delivered',0, ...
    'matlab_mean_delivered_latency_s',NaN,'native_mean_delivered_latency_s',NaN, ...
    'delivered_signed_relative_percent',NaN,'delivered_absolute_relative_percent',NaN, ...
    'delivered_relative_defined',false,'delivered_target_pass',NaN,'delivered_comparison_status','', ...
    'latency_signed_relative_percent',NaN,'latency_absolute_relative_percent',NaN, ...
    'latency_relative_defined',false,'latency_target_pass',NaN,'latency_comparison_status','');
end

function h=horizonTemplate()
h=struct('model','','seed',0,'source',0,'horizon_s',0,'generation_start_s',0, ...
    'generation_end_exclusive_s',0,'scheduled_attempts',0,'admitted',0,'not_admitted',0, ...
    'delivered_by_age',0,'delivered_later_by_stop',0,'raw_model_dropped_by_stop',NaN, ...
    'raw_model_pending_at_stop',NaN,'unresolved_at_stop',0,'proven_terminal_drop_lower_bound',0, ...
    'fraction_of_scheduled',NaN,'fraction_of_admitted',NaN,'admissions_outside_window',0);
end

function [signed,absolute,defined,passed,status]=relativeMetric(current,reference,target,isCount)
signed=NaN; absolute=NaN; defined=false; passed=NaN;
if ~isfinite(reference)
    status='undefined_no_native_delivered_population';
elseif reference==0
    if isCount && current==0, status='both_zero_counts_equal_relative_undefined';
    else, status='undefined_zero_native_reference'; end
elseif ~isfinite(current)
    status='undefined_no_matlab_delivered_population';
else
    signed=100*(current/reference-1); absolute=abs(signed); defined=true;
    passed=double(absolute<=target); status='within_target';
    if ~passed, status='outside_target'; end
end
end

function count=scheduledCount(flow,lower,upper)
first=round(flow.StartSeconds*1e9); interval=round(flow.IntervalSeconds*1e9);
lo=max(0,ceil((lower-first)/interval));
hi=min(flow.PacketCount-1,ceil((upper-first)/interval)-1);
count=max(0,hi-lo+1);
end

function t=populationTable(p,seed,model)
n=numel(p.Source); t=table(repmat(string(model),n,1),repmat(seed,n,1),p.Source,p.Destination, ...
    p.AppId,p.AttemptIndex,p.GeneratedNS,p.GeneratedNS,p.DeliveryNS,p.DeliveryEventCount,p.Status,p.RawModelOutcome,p.DropReason, ...
    p.LatencySeconds,p.AgeAtCutoff,p.LastCustodyNode,p.LastCustodyTime, ...
    repmat(false,n,1),'VariableNames',{'model','seed','source','destination','app_id', ...
    'attempt_index_0based','generated_time_ns','source_admitted_time_ns','first_delivery_time_ns','delivery_event_count', ...
    'status','raw_model_outcome','drop_reason','delivered_latency_s','age_at_cutoff_s', ...
    'last_observed_custody_node','last_observed_custody_time_s','age_proves_live_queued_copy'});
end

function requireColumns(t,names)
if ~istable(t) || ~all(ismember(names,t.Properties.VariableNames))
    error('csr6000:AnalysisSchema','Required analysis table columns are missing.');
end
end

function writeRows(path,rows)
t=struct2table(rows,'AsArray',true);
for name=t.Properties.VariableNames
    if iscellstr(t.(name{1})), t.(name{1})=string(t.(name{1})); end %#ok<ISCLSTR>
end
writetable(t,path);
end

function value=ratio(n,d)
value=NaN; if d>0, value=n/d; end
end

function value=average(x)
value=NaN; if ~isempty(x), value=mean(x); end
end

function value=maximum(x)
value=NaN; if ~isempty(x), value=max(x); end
end

function value=quantileCore(x,p)
value=NaN; if isempty(x), return; end
x=sort(x); index=1+(numel(x)-1)*p; lo=floor(index); hi=ceil(index);
value=x(lo)+(index-lo)*(x(hi)-x(lo));
end
