function report=receiverTimerPreflight(root,config,folder)
%RECEIVERTIMERPREFLIGHT Native geometry, public allocator and timer callbacks.
% Only bounded public component probes run; no full network simulation runs.
if ~isfolder(folder), mkdir(folder); end
checks=struct('name',{},'passed',{},'details',{});
reference=fullfile(root,'ref','receiver_timers');
samples=readFixture(fullfile(reference,'phy_component_fixture.csv'),{'component','cause'});
acquisitions=readFixture(fullfile(reference,'acquisition_schedule_fixture.csv'),{'cause','native_path'});
tx=readFixture(fullfile(reference,'native_TX_finish_arithmetic.csv'),{'different_binary64','native_completion_observed'});
assert(height(samples)==1542 && height(acquisitions)==1352 && height(tx)==811, ...
    'autocase:ReceiverTimerPreflight','Unexpected native fixture coverage.');

shifted=0;
for k=1:height(acquisitions)
    row=acquisitions(k,:);
    [target,detail]=ac.ReceiverTimer.target(row.origin_native_seconds,row.delay_seconds);
    assert(detail.NowNanoseconds==row.origin_ns && detail.DelayNanoseconds==row.delay_ns && ...
        detail.TargetNanoseconds==row.deadline_ns && target==row.deadline_native_seconds, ...
        'autocase:ReceiverTimerPreflight','Native acquisition target mismatch at row %d.',k);
    shifted=shifted+double(target~=row.floating_sum_seconds);
end
checks(end+1)=checked('all_native_acquisition_schedule_targets_match', ...
    struct('records',height(acquisitions),'changed_floating_sums',shifted));

for k=1:height(tx)
    [target,detail]=ac.ReceiverTimer.target(tx.start_ns(k)/1e9,tx.duration_seconds(k));
    assert(detail.DelayNanoseconds==tx.duration_ns(k) && detail.TargetNanoseconds==tx.deadline_ns(k) && ...
        target==tx.ns_division_seconds(k),'autocase:ReceiverTimerPreflight', ...
        'Native TX-finish target mismatch at row %d.',k);
end
observed=sum(strcmpi(tx.native_completion_observed,"True"));
assert(observed==810,'autocase:ReceiverTimerPreflight','Unexpected native TX completion evidence count.');
checks(end+1)=checked('all_native_tx_finish_targets_match_source_deadlines', ...
    struct('scheduled_targets',height(tx),'observed_native_completions',observed,'pending_at_capture_end',height(tx)-observed));

% Source-confirmed rejected-frame return has no observed instance in the
% native capture; this checks its target arithmetic, not network execution.
origin=45.662638077; [target,detail]=ac.ReceiverTimer.target(origin,28e-9);
assert(detail.DelayNanoseconds==28 && detail.TargetNanoseconds==45662638105 && target>origin, ...
    'autocase:ReceiverTimerPreflight','Rejected return must remain exactly 28 ns later.');
checks(end+1)=checked('source_only_rejected_return_uses_28_nanosecond_target', ...
    struct('delay_ns',28,'target_ns',detail.TargetNanoseconds,'native_observed_callbacks',0));

% Geometry-only allocation deliberately uses tiny positive noise. BER does not enter
% header/payload bit arithmetic; the real unchanged Model computes every
% floor and preserves raw physical signal geometry from the native fixture.
rx=config.Nodes(1).RadioProfile; front=struct('ReceivedPowerWatts',1);
stopped=samples(samples.node==3 & samples.draw_ordinal==75,:);
schedule=acquisitions(acquisitions.node==3 & acquisitions.deadline_ns==stopped.callback_ns,:);
assert(height(stopped)==1 && height(schedule)==1,'autocase:ReceiverTimerPreflight','Missing observed stop geometry.');
fixedEnd=ac.ReceiverTimer.target(schedule.origin_native_seconds,schedule.delay_seconds);
fixed=allocate(rx,front,stopped,stopped.interval_start_sec,fixedEnd);
oldEnd=schedule.origin_native_seconds+schedule.delay_seconds;
old=allocate(rx,front,stopped,stopped.interval_start_sec,oldEnd);
assert(fixed.PayloadBits==51 && old.PayloadBits==52 && fixedEnd<oldEnd, ...
    'autocase:ReceiverTimerPreflight','Actual allocator did not reproduce the 52-to-51 timer boundary.');
newErrors=csr.phy.Model.sampleSourceBinomial(51,stopped.probability,stopped.uniform);
oldErrors=csr.phy.Model.sampleSourceBinomial(52,stopped.probability,stopped.uniform);
assert(newErrors==0 && oldErrors==0,'autocase:ReceiverTimerPreflight','Unexpected same-uniform error characterization.');
checks(end+1)=checked('captured_raw_geometry_reproduces_52_and_corrected_51_bits', ...
    struct('old_payload_bits',old.PayloadBits,'fixed_payload_bits',fixed.PayloadBits, ...
    'old_end_seconds',oldEnd,'fixed_end_seconds',fixedEnd,'same_uniform_errors',[oldErrors newErrors]));

for k=1:height(samples)
    row=samples(k,:); result=allocate(rx,front,row,row.interval_start_sec,row.interval_end_sec);
    assert(result.HeaderBits==row.expected_header_bits && result.PayloadBits==row.expected_payload_bits, ...
        'autocase:ReceiverTimerPreflight','Public Model bit allocation differs at native fixture row %d.',k);
    if strcmp(row.component,"header"), componentBits=result.HeaderBits; else, componentBits=result.PayloadBits; end
    assert(componentBits==row.bits,'autocase:ReceiverTimerPreflight','Consumed component count differs at row %d.',k);
end
checks(end+1)=checked('unchanged_public_model_matches_all_native_component_geometries', ...
    struct('component_rows',height(samples),'header_and_payload_counts_checked',2*height(samples), ...
    'raw_signal_geometry_preserved',true,'geometry_only_high_snr',true));

baseline=acquisitionProbe(config,folder,'baseline',schedule.origin_native_seconds,fixedEnd);
candidate=acquisitionProbe(config,folder,'candidate',schedule.origin_native_seconds,fixedEnd);
assert(strcmp(baseline.atNative,'Search') && strcmp(baseline.atOld,'Track') && ...
    strcmp(candidate.atNative,'Track') && candidate.random_draws==0 && baseline.random_draws==0, ...
    'autocase:ReceiverTimerPreflight','Actual acquire callbacks did not follow the corrected target.');
checks(end+1)=checked('actual_public_receiver_acquisition_uses_integer_sum_deadline', ...
    struct('baseline_state_at_native_deadline',baseline.atNative,'candidate_state_at_native_deadline',candidate.atNative, ...
    'baseline_state_at_old_deadline',baseline.atOld,'protected_bit_random_draws',0));

continuous=acquisitionProbe(config,folder,'continuous',schedule.origin_native_seconds,fixedEnd);
absent=acquisitionProbe(config,folder,'absent',schedule.origin_native_seconds,fixedEnd);
assert(strcmp(continuous.atNative,'Search') && strcmp(continuous.atOld,'Track') && continuous.timer_count==0 && ...
    strcmp(absent.atNative,'Search') && strcmp(absent.atOld,'Track') && absent.timer_count==0 && ...
    continuous.random_draws==0 && absent.random_draws==0, ...
    'autocase:ReceiverTimerPreflight','Continuous or absent TransportTiming no longer retains its original timing.');
checks(end+1)=checked('continuous_and_absent_transport_retain_original_acquisition', ...
    struct('continuous_timer_records',continuous.timer_count,'absent_timer_records',absent.timer_count));

pair=pairedCompletion(config,folder,schedule.origin_native_seconds);
checks(end+1)=checked('actual_phy_and_mac_completion_share_deadline_and_keep_existing_order',pair);
report=struct('schema','csr-receiver-timer-preflight-v1','passed',all([checks.passed]), ...
    'checks',checks,'network_simulation_executed',false,'random_variates_requested',pair.seeded_mac_draws, ...
    'scope','Unchanged public PHY allocator, controlled receiver acquisition, and one-radio public MAC/PHY TX component; no full-network parity claim', ...
    'random_scope','Only the one-radio MAC component uses measured seed-owned MAC draws; geometry/acquisition probes use none', ...
    'native_callback_scope','Native has one TX completion callback; two same-deadline callbacks preserve MATLAB existing decomposition', ...
    'rejected_return_limitation','28 ns arithmetic and source binding only; no captured rejected-return callback is claimed');
ac.writeJson(fullfile(folder,'receiver_timer_preflight.json'),report);
end

function result=allocate(rx,front,row,start,finish)
interval=csr.phy.Model.interval(start,finish,1e-100);
result=csr.phy.Model.allocateErrors(rx,front,row.signal_start_sec,row.preamble_bits, ...
    row.packet_bits,row.rate_key,interval,@unexpectedUniform);
end
function value=unexpectedUniform()
error('autocase:ReceiverTimerPreflight','High-SNR geometry should not request a uniform.');
value=0; %#ok<UNRCH>
end
function result=acquisitionProbe(config,folder,mode,origin,nativeDeadline)
local=fullfile(folder,['acquisition_' mode]); if ~isfolder(local), mkdir(local); end
config.Nodes=config.Nodes(ismember([config.Nodes.Id],[1 3]));
for k=1:numel(config.Nodes)
    config.Nodes(k).PositionMeters=[0 0 1]; config.Nodes(k).RadioProfile.StochasticSyncThreshold=false;
end
clock=csr.sim.EventScheduler(100); clock.run(origin);
streams=ac.Streams(config.Seed,clock,'natural','',local); cleanup=onCleanup(@()streams.close()); %#ok<NASGU>
timer=ac.ReceiverTimer(); timing=[];
if ~strcmp(mode,'absent')
    timingMode='nanoseconds'; if strcmp(mode,'continuous'), timingMode='continuous'; end
    timing=csr.sim.TransportTiming(timingMode);
end
if strcmp(mode,'baseline')
    engine=csr.phy.SignalEngine(config,clock,streams,@(frame,node,decision)[],[],[],timing);
else
    engine=ac.ReceiverTimerSignalEngine(config,clock,streams,@(frame,node,decision)[],[],[],timing,timer);
end
engine.transmit(discoveryFrame(1)); clock.run(nativeDeadline); atNative=engine.state(3);
clock.run(origin+config.Phy.SyncToTrackSeconds); atOld=engine.state(3);
random=streams.summary(); snapshot=timer.snapshot();
result=struct('atNative',atNative,'atOld',atOld,'random_draws',random.draw_count,'timer_count',snapshot.Count);
end
function result=pairedCompletion(config,folder,origin)
local=fullfile(folder,'paired_completion'); if ~isfolder(local), mkdir(local); end
config.Nodes=config.Nodes([config.Nodes.Id]==1);
clock=csr.sim.EventScheduler(1000); clock.run(origin);
streams=ac.Streams(config.Seed,clock,'natural','',local); cleanup=onCleanup(@()streams.close()); %#ok<NASGU>
timer=ac.ReceiverTimer(); timing=csr.sim.TransportTiming('nanoseconds');
probe=ac.ReceiverTimerProbe(); probe.Scheduler=clock;
engine=ac.ReceiverTimerSignalEngine(config,clock,streams,@(frame,node,decision)[],[], ...
    @(node,state)probe.phyState(node,state),timing,timer); probe.Engine=engine;
callbacks=struct('Transmit',@(frame,duration)probe.transmit(frame,duration), ...
    'SetReceiverState',@(state)engine.setReceiverState(1,state),'ReceiverState',@()engine.state(1), ...
    'HasSync',@()engine.hasSync(1),'Event',@(event,frame,details)probe.macEvent(event,frame,details));
mac=ac.ReceiverTimerMac(1,clock,streams,config,callbacks,timer); probe.Mac=mac;
assert(mac.enqueue(discoveryFrame(1)),'autocase:ReceiverTimerPreflight','Component frame was not admitted.');
while probe.TxCount==0
    next=clock.nextTime();
    assert(isfinite(next) && next<=origin+5,'autocase:ReceiverTimerPreflight','Bounded MAC component did not transmit.');
    clock.run(next);
end
snapshot=timer.snapshot(); records=snapshot.Records;
phy=records(records.Purpose=="phy_tx_finish",:); macTarget=records(records.Purpose=="mac_tx_finish",:);
assert(height(phy)==1 && height(macTarget)==1 && phy.TargetSeconds==macTarget.TargetSeconds, ...
    'autocase:ReceiverTimerPreflight','PHY and MAC completion targets diverged.');
clock.run(phy.TargetSeconds); state=mac.snapshot();
assert(probe.TxCount==1 && strcmp(engine.state(1),'Search') && strcmp(state.State,'Search') && ...
    numel(probe.Ledger)==2 && strcmp(probe.Ledger{1}.kind,'phy_search') && ...
    strcmp(probe.Ledger{2}.kind,'mac_search') && ...
    probe.Ledger{1}.time_s==phy.TargetSeconds && probe.Ledger{2}.time_s==phy.TargetSeconds, ...
    'autocase:ReceiverTimerPreflight','Actual TX completion callbacks changed MATLAB existing PHY-first ordering.');
random=streams.summary();
assert(all(endsWith(string({random.counts.key}),":mac_slot")), ...
    'autocase:ReceiverTimerPreflight','One-radio completion probe requested a non-MAC variate.');
result=struct('physical_transmissions',probe.TxCount,'deadline_seconds',phy.TargetSeconds, ...
    'callback_order',{probe.Ledger},'seeded_mac_draws',random.draw_count,'matlab_completion_callbacks',2);
end
function frame=discoveryFrame(source)
control=struct('Id',uint64(1),'Type','DISCOVER','Payload', ...
    struct('Subtype','broadcast','Sequence',1,'ActivePeers',[]),'WirePayloadBytes',19);
frame=csr.hop.Frames.control(control,source,16777215,uint16(1), ...
    struct('RateKeyKbps',8,'TxPowerDbm',33,'Preamble','long','EnvelopeProfile','bare','AckRequired',false));
end
function rows=readFixture(path,textNames)
options=detectImportOptions(path,'TextType','string');
textNames=intersect(textNames,options.VariableNames); options=setvartype(options,textNames,'string');
options=setvartype(options,setdiff(options.VariableNames,textNames),'double'); rows=readtable(path,options);
end
function value=checked(name,details)
value=struct('name',name,'passed',true,'details',details);
end
