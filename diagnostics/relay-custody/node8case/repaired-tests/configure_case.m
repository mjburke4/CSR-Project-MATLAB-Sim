function config=configure_case(seed,stop)
root=fileparts(fileparts(mfilename('fullpath')));
config=csr.scenario.importNs3(fullfile(root,'inputs',sprintf('s%d.csv',seed)), ...
    struct('HistoricalBenchmark',true,'FlowLimit',0,'Backend','portable'));
assert(config.DurationSeconds==6000 && config.Seed==seed);
assert(strcmp(config.Hop.DataQueuedRetryPolicy,'actual-tx'));
config.Hop.DataQueuedRetryPolicy='native-provisional';
config.DurationSeconds=stop;
config.Trace.Enabled=true;config.Trace.MaxRecords=1500000;
config.Trace.MaxPhyRecords=1500000;
if stop<6000,config.Trace.MaxRecords=100000;config.Trace.MaxPhyRecords=100000;end
config.Trace.MaxApplicationAdmissionRecords=max(1,6*ceil(max(0,stop-300)/0.02));
config.MaxEvents=18000000;
config=csr.scenario.validate(config);
end
