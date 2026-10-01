function report=retryPolicyPreflight(config,folder)
%RETRYPOLICYPREFLIGHT Existing policy boundaries and captured queue consequence.
% Uses unchanged public HOP/MAC APIs; no full network or native tape runs.
if ~isfolder(folder), mkdir(folder); end
root=fileparts(fileparts(mfilename('fullpath')));
assert(strcmp(config.Hop.DataQueuedRetryPolicy,'actual-tx'), ...
    'autocase:RetryPolicyPreflight','The base/natural configuration must retain actual-tx.');
testFile=fullfile(root,'TestQueuedRetryPolicy.m');
suite=matlab.unittest.TestSuite.fromFile(testFile);
assert(numel(suite)==16,'autocase:RetryPolicyPreflight','Expected all16 recovered public policy tests.');
results=run(suite);
checks=struct('name',{},'passed',{},'details',{});
for k=1:numel(results)
    checks(end+1)=struct('name',char(results(k).Name),'passed',logical(results(k).Passed), ...
        'details',struct('failed',logical(results(k).Failed),'incomplete',logical(results(k).Incomplete), ...
        'duration_seconds',double(results(k).Duration),'recovered_test_source','tests/TestQueuedRetryPolicy.m')); %#ok<AGROW>
end
legacyPassed=all([checks.passed]);
report=struct('schema','csr-retry-policy-preflight-v1','passed',false,'completed',false, ...
    'historical_tests_passed',legacyPassed, ...
    'checks',checks,'network_simulation_executed',false,'base_policy',config.Hop.DataQueuedRetryPolicy, ...
    'candidate_policy','native-provisional','historical_test_methods',16, ...
    'historical_test_git_blob','741a5e311c813c8b9498429d20a1222caceeec0e', ...
    'scope','Existing public policy tests plus source-grounded DATA29/DATA32 shared-scan chronology and resulting public MAC order', ...
    'limitations','Controlled public sent/ACK callbacks and isolated MAC queues. No native timing replay, PHY run or whole-network parity claim.');
ac.writeJson(fullfile(folder,'retry_policy_preflight.json'),report);
assert(legacyPassed,'autocase:RetryPolicyPreflight','A recovered policy boundary test failed.');

[old,oldQueue]=capturedCase(config,'actual-tx');
[native,nativeQueue]=capturedCase(config,'native-provisional');
assert(old.retransmissions_after_shared_scan==1 && native.retransmissions_after_shared_scan==2, ...
    'autocase:RetryPolicyPreflight','The surviving shared scan did not distinguish queued retry policies.');
assert(isequal(old.residual_sequences,[36 29]) && isequal(native.residual_sequences,[29 36]), ...
    'autocase:RetryPolicyPreflight','Captured residual queue order was not reproduced.');
assert(abs(old.second_retry_seconds-(322.879+config.Hop.TicSeconds))<1e-10 && ...
    abs(native.second_retry_seconds-(318.498+config.Hop.TicSeconds))<1e-10, ...
    'autocase:RetryPolicyPreflight','Second retry came from the wrong actual-transmit scan.');
checks(end+1)=checked('captured_shared_scan_survives_trigger_ack_and_changes_retry_order', ...
    struct('actual_tx',old,'native_provisional',native));

oldMac=drainMac(config,oldQueue,fullfile(folder,'actual_tx_mac'));
nativeMac=drainMac(config,nativeQueue,fullfile(folder,'native_provisional_mac'));
assert(isequal(oldMac.transmitted_sequences,[36 29]) && ...
    isequal(nativeMac.transmitted_sequences,[29 36]) && ...
    oldMac.queue_remaining==0 && nativeMac.queue_remaining==0, ...
    'autocase:RetryPolicyPreflight','Public MAC did not preserve the different residual admission order.');
checks(end+1)=checked('public_mac_selects_native_retry_before_newer_application', ...
    struct('actual_tx',oldMac,'native_provisional',nativeMac));
report.checks=checks; report.passed=all([checks.passed]); report.completed=true;
report.mac_component_runs=2;
report.seeded_mac_draws=oldMac.seeded_mac_draws+nativeMac.seeded_mac_draws;
report.mac_rng='Ordinary seeded CSR streams; no supplied or forced slot values';
report.captured_component_scope='DATA29/32 timing and ACK32 stimulus; remaining same-priority queue copies29/36 isolated after their matched earlier transmissions';
ac.writeJson(fullfile(folder,'retry_policy_preflight.json'),report);
end

function [result,residual]=capturedCase(config,policy)
assert(config.Hop.MaxResends==2 && config.Hop.ResendSeconds==2, ...
    'autocase:RetryPolicyPreflight','Captured chronology requires the actual two-retry, two-second policy.');
clock=csr.sim.EventScheduler(); streams=csr.sim.RandomStreams(config.Seed);
hopConfig=config.Hop; hopConfig.DataQueuedRetryPolicy=policy;
admissions={}; releases={}; lastAllocated=0;
hop=csr.hop.Layer(5,clock,streams,hopConfig, ...
    struct('EnqueueMac',@enqueue,'NsdpRelease',@release));
radio=struct('RateKeyKbps',8,'TxPowerDbm',33,'Preamble','short','EnvelopeProfile','bare','Dscp',0);
% A fresh peer starts with one allowed outstanding DATA owner. Three public
% sent/ACK exchanges open a two-owner window, before the captured episode.
% Keep this component warm-up separate from the five captured admissions.
for k=1:3
    [accepted,warm]=hop.send(app(1000+k,0),1,radio);
    assert(accepted,'autocase:RetryPolicyPreflight','Public capacity warm-up was refused.');
    hop.notifySent(warm);
    ack=csr.hop.Frames.acknowledgment(1,5,warm.Sequence,uint64(0),uint64(0),struct('HasAckWindow',false));
    hop.receive(ack);
end
clock.run(3);
window=hop.admission(1); acknowledgedBefore=hop.stats().Acknowledged;
assert(acknowledgedBefore==3 && hop.PendingDataCount==0 && window.NeighborThreshold==1 && ...
    numel(admissions)==3 && numel(releases)==3 && clock.PendingCount==0, ...
    'autocase:RetryPolicyPreflight','Public warm-up did not establish the required two-owner window.');
warmup=struct('public_acknowledged_data',3,'sequences',[1 2 3], ...
    'neighbor_threshold',window.NeighborThreshold,'pending_after_warmup',hop.PendingDataCount, ...
    'scheduled_scans_drained',true,'scope','Separate component setup, not captured network traffic');
admissions={}; releases={};
% Advance only the real public sequence allocator. Best-effort key controls
% create no DATA owner, timer or MAC backlog in this callback-only fixture.
allocateThrough(28);
clock.run(312.653111114);
[accepted,original]=hop.send(app(11,300.2),1,radio);
assert(accepted && original.Sequence==29,'autocase:RetryPolicyPreflight','Could not allocate public DATA29 owner.');
clock.run(313.771111113778); allocateThrough(31);
[accepted,trigger]=hop.send(app(14,300.26),1,radio);
assert(accepted && trigger.Sequence==32,'autocase:RetryPolicyPreflight','Could not allocate public DATA32 scan trigger.');
clock.run(313.820); hop.notifySent(original);
clock.run(316.498); hop.notifySent(trigger);
clock.run(318.061111086);
ack=csr.hop.Frames.acknowledgment(1,5,uint16(32),uint64(0),uint64(0),struct('HasAckWindow',false));
hop.receive(ack);
assert(hop.stats().Acknowledged==acknowledgedBefore+1 && hop.PendingDataCount==1, ...
    'autocase:RetryPolicyPreflight','ACK32 did not remove only its own live owner.');
clock.run(318.499);
afterShared=hop.stats().Retransmissions;
retry1=admissions{find(cellfun(@(r)r.frame.Sequence==29 && r.frame.RetryCount==1,admissions),1)}.frame;
clock.run(320.879); hop.notifySent(retry1);
clock.run(322.260111114); allocateThrough(35);
[accepted,newer]=hop.send(app(250,304.98),1,radio);
assert(accepted && newer.Sequence==36,'autocase:RetryPolicyPreflight','Could not allocate public DATA36 owner.');
clock.run(323);
ownerRows=admissions(cellfun(@(r)r.frame.Sequence==29,admissions));
assert(isequal(cellfun(@(r)double(r.frame.RetryCount),ownerRows),[0 1 2]) && ...
    numel(admissions)==5 && hop.PendingDataCount==2, ...
    'autocase:RetryPolicyPreflight','Complete DATA admission history contains unexpected extra or missing copies.');
second=admissions{find(cellfun(@(r)r.frame.Sequence==29 && r.frame.RetryCount==2,admissions),1)};
residualRows=admissions(cellfun(@(r)(r.frame.Sequence==29 && r.frame.RetryCount==2) || r.frame.Sequence==36,admissions));
assert(numel(residualRows)==2 && hop.stats().Failed==0 && numel(releases)==1, ...
    'autocase:RetryPolicyPreflight','Unexpected extra owner, exhaustion or capacity release in captured chronology.');
residual=cellfun(@(r)r.frame,residualRows,'UniformOutput',false);
result=struct('policy',policy,'initial_sequence',double(original.Sequence), ...
    'separate_capacity_warmup',warmup, ...
    'trigger_sequence',double(trigger.Sequence),'trigger_acknowledged',true, ...
    'retransmissions_after_shared_scan',afterShared,'second_retry_seconds',second.time_s, ...
    'residual_sequences',cellfun(@(r)double(r.Sequence),residual), ...
    'residual_retry_counts',cellfun(@(r)double(r.RetryCount),residual), ...
    'pending_data_owners',hop.PendingDataCount,'capacity_releases',numel(releases), ...
    'initial_admission_seconds',312.653111114,'trigger_admission_seconds',313.771111113778, ...
    'initial_app_attempt',11,'trigger_app_attempt',14,'new_app_attempt',250, ...
    'initial_tx_seconds',313.820,'trigger_tx_seconds',316.498,'trigger_ack_seconds',318.061111086, ...
    'retry1_tx_seconds',320.879,'new_data_admission_seconds',322.260111114);

    function accepted=enqueue(frame)
        accepted=true;
        lastAllocated=max(lastAllocated,double(frame.Sequence));
        if strcmp(frame.Kind,'DATA')
            admissions{end+1}=struct('time_s',clock.Now,'frame',frame);
        end
    end
    function release(packet,reason)
        releases{end+1}=struct('packet',packet,'reason',reason);
    end
    function allocateThrough(last)
        current=lastAllocated;
        for sequence=current+1:last
            control=struct('Id',uint64(10000+sequence),'Type','KEY_REQUEST','Payload',struct(),'WirePayloadBytes',16);
            [okay,frame]=hop.sendControl(control,1,struct('AckRequired',false));
            assert(okay && frame.Sequence==sequence,'autocase:RetryPolicyPreflight','Public sequence allocation changed.');
        end
    end
    function packet=app(attempt,generated)
        flow=struct('SourceId',5,'DestinationId',1,'ApplicationPayloadBytes',185);
        packet=csr.packet(attempt,flow,generated,radio);
        packet.FlowOrdinal=attempt; packet.FlowIndex=4;
    end
end

function result=drainMac(config,frames,folder)
if ~isfolder(folder), mkdir(folder); end
clock=csr.sim.EventScheduler();
streams=ac.Streams(config.Seed,clock,'natural','',folder);
cleanup=onCleanup(@()streams.close()); %#ok<NASGU>
options=config.Mac; options.DutyCycleEnabled=false; options.ConcatenationEnabled=false;
sent=[]; times=[];
mac=csr.mac.Layer(5,clock,streams,options,struct('Transmit',@transmit));
for k=1:numel(frames)
    assert(mac.enqueue(frames{k}),'autocase:RetryPolicyPreflight','Isolated MAC refused a residual frame.');
end
clock.run(20);
assert(mac.Counters.Transmissions==2 && mac.Counters.SegmentsTransmitted==2, ...
    'autocase:RetryPolicyPreflight','Expected exactly two public MAC transmissions.');
random=streams.summary();
assert(all(endsWith(string({random.counts.key}),':mac_slot')), ...
    'autocase:RetryPolicyPreflight','Isolated MAC requested a non-MAC random variate.');
result=struct('transmitted_sequences',sent,'transmitted_at_seconds',times,'seeded_mac_draws',random.draw_count, ...
    'queue_remaining',mac.DataQueueCount,'concatenation_enabled',false,'duty_cycle_enabled',false, ...
    'scope','Isolated real MAC stable FIFO selection; not captured network timing');
    function transmit(frame,duration) %#ok<INUSD>
        assert(numel(frame.Segments)==1,'autocase:RetryPolicyPreflight','Unexpected aggregate in FIFO component.');
        sent(end+1)=double(frame.Segments{1}.Sequence); times(end+1)=clock.Now;
    end
end
function value=checked(name,details)
value=struct('name',name,'passed',true,'details',details);
end
