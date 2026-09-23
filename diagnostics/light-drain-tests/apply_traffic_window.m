function [config, schedule] = apply_traffic_window(config, trafficStop)
% Test-only schedule cap. Keep the simulator stop and admission gates intact.
validateattributes(trafficStop,{'numeric'},{'scalar','real','finite','positive'});
assert(trafficStop < config.DurationSeconds,'A positive drain interval is required.');
assert(strcmp(config.ApplicationGenerator,'historical-opnet-gated') && ...
    config.ApplicationFlowLimit==0,'Use the unchanged historical generator without an admission cap.');
stopTick=round(trafficStop*1e9);
schedule=repmat(struct('SourceId',0,'StartSeconds',0,'IntervalSeconds',0, ...
    'PlannedAttempts',0,'LastAttemptSeconds',NaN),numel(config.Traffic),1);
for k=1:numel(config.Traffic)
    flow=config.Traffic(k);
    startTick=round(flow.StartSeconds*1e9); intervalTick=round(flow.IntervalSeconds*1e9);
    assert(intervalTick>0,'The interval must be at least one nanosecond.');
    count=max(0,floor((stopTick-1-startTick)/intervalTick)+1);
    assert(count<=flow.PacketCount,'The cutoff cannot extend the imported schedule.');
    config.Traffic(k).PacketCount=count;
    last=NaN;
    if count>0, last=(startTick+(count-1)*intervalTick)/1e9; end
    schedule(k)=struct('SourceId',flow.SourceId,'StartSeconds',flow.StartSeconds, ...
        'IntervalSeconds',flow.IntervalSeconds,'PlannedAttempts',count,'LastAttemptSeconds',last);
end
config.SharedScenario.TestTrafficWindow=struct('StopExclusiveSeconds',trafficStop, ...
    'SimulationStopSeconds',config.DurationSeconds, ...
    'Mechanism','Fixture truncates scheduled attempts via Traffic.PacketCount; admission cap remains zero.');
config=csr.scenario.validate(config);
end
