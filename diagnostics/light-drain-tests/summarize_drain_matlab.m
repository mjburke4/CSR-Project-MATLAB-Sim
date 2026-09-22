function sources = summarize_drain_matlab(result,applications,schedule,trafficStop)
% Descriptive delivered-only latency; unresolved outcomes remain explicit.
admission=result.ApplicationAdmissionTrace;
assert(all(admission.TimeSeconds<trafficStop),'An application attempt occurred after traffic cutoff.');
assert(all(applications.GeneratedSeconds<trafficStop),'An application was generated after traffic cutoff.');
template=struct('SourceId',0,'PlannedAttempts',0,'Attempts',0,'Admitted',0, ...
    'Blocked',0,'BlockedFraction',NaN,'Delivered',0,'Dropped',0,'Pending',0, ...
    'DeliveryFraction',NaN,'DeliveredByTrafficStop',0,'DeliveredDuringDrain',0, ...
    'MeanLatencySeconds',NaN,'MedianLatencySeconds',NaN,'P95LatencySeconds',NaN, ...
    'TailSampleBelow20',true);
rows=repmat(template,numel(schedule),1);
for k=1:numel(schedule)
    id=schedule(k).SourceId;
    attempts=admission(admission.SourceId==id,:);
    apps=applications(applications.SourceId==id,:);
    assert(height(attempts)==schedule(k).PlannedAttempts,'Attempt count differs from the finite schedule.');
    wanted=round((schedule(k).StartSeconds+(0:height(attempts)-1)'*schedule(k).IntervalSeconds)*1e9);
    assert(isequal(round(attempts.TimeSeconds*1e9),wanted),'Attempt times differ from the finite schedule.');
    assert(sum(attempts.Accepted)==height(apps),'Admission/application identity counts disagree.');
    delivered=strcmp(apps.Outcome,'delivered');
    dropped=strcmp(apps.Outcome,'dropped'); pending=strcmp(apps.Outcome,'pending');
    assert(sum(delivered)+sum(dropped)+sum(pending)==height(apps),'Unknown application outcome.');
    r=template; r.SourceId=id; r.PlannedAttempts=schedule(k).PlannedAttempts;
    r.Attempts=height(attempts); r.Admitted=height(apps); r.Blocked=r.Attempts-r.Admitted;
    if r.Attempts>0, r.BlockedFraction=r.Blocked/r.Attempts; end
    r.Delivered=sum(delivered); r.Dropped=sum(dropped); r.Pending=sum(pending);
    if r.Admitted>0, r.DeliveryFraction=r.Delivered/r.Admitted; end
    % Outcome snapshot is after all events at cutoff; generation is exclusive.
    r.DeliveredByTrafficStop=sum(delivered & apps.ReceivedSeconds<=trafficStop);
    r.DeliveredDuringDrain=r.Delivered-r.DeliveredByTrafficStop;
    latencies=sort(apps.LatencySeconds(delivered));
    if ~isempty(latencies)
        r.MeanLatencySeconds=mean(latencies);
        r.MedianLatencySeconds=linearQuantile(latencies,0.5);
        r.P95LatencySeconds=linearQuantile(latencies,0.95);
    end
    r.TailSampleBelow20=r.Delivered<20;
    rows(k)=r;
end
sources=struct2table(rows);
end

function value=linearQuantile(sortedValues,p)
position=(numel(sortedValues)-1)*p; lower=floor(position)+1;
upper=min(lower+1,numel(sortedValues));
value=sortedValues(lower)+(position-floor(position))*(sortedValues(upper)-sortedValues(lower));
end
