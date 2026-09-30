function report=terminalPreflight(config,folder)
%TERMINALPREFLIGHT Public HOP/MAC terminal-copy checks with independent cases.
% Every case saves observed/expected state and public callback chronology.
% Failures are collected across all cases; the strict network gate still fails
% if any component check fails. Named nested getters read current callback state.
if ~isfolder(folder), mkdir(folder); end
checks=struct('name',{},'passed',{},'details',{});
resources=containers.Map('KeyType','char','ValueType','any');
probes=containers.Map('KeyType','char','ValueType','any');
cleanup=streamRegistryGuard(resources); %#ok<NASGU>
radio=componentRadio(config);
activeName=''; stages=struct('label',{},'passed',{},'actual',{},'expected',{});
report=struct('schema','csr-terminal-preflight-v2','completed',false,'passed',false, ...
    'checks',checks,'matlab_execution_required',true,'network_parity_claim',false, ...
    'fixture_radio',radio,'cleanup_ownership','Stable stream-handle registry captured by a file-local cleanup factory', ...
    'state_ownership','Six named nested getters read callback-mutated values at call time', ...
    'failure_policy','Attempt all 16 independent groups, persist observed/expected state, then fail the strict replay gate if any group failed', ...
    'scope','Public component ownership, real MAC queue/cancellation/drain, receiver DATA duplicate suppression; one monotonic scheduler per independent harness', ...
    'accounting_limit','A failed HOP owner with queued MAC copies is unresolved at cutoff. Raw network Statistics.Dropped is provisional and not a final application-loss ledger.');
runGroup('native_terminal_expiry_retains_two_previously_admitted_mac_copies',@retainsCopies);
runGroup('owner_release_once_with_live_copies_is_unresolved_at_cutoff',@cutoffRelease);
runGroup('actual_tx_policy_and_default_remain_unchanged',@actualTx);
runGroup('real_mac_drains_retained_copies_with_one_late_first_delivery',@realDrain);
runGroup('orphan_exact_ack_cancels_data_without_releasing_owner_twice',@exactAck);
runGroup('orphan_window_ack_cancels_data_without_releasing_owner_twice',@windowAck);
runGroup('orphan_window_dack_cancels_data_without_releasing_owner_twice',@windowDack);
runGroup('nonwindow_dack_keeps_disabled_native_single_dack_path',@singleDack);
runGroup('window_ack_dack_union_wraps_at_uint16_and_respects_peer',@windowWrap);
runGroup('overlapping_window_bits_prefer_ack_and_release_once',@overlap);
runGroup('grouped_routing_survives_partial_complete_and_repeated_exact_ack',@routingExact);
runGroup('data_window_cleanup_cannot_cancel_or_complete_grouped_routing',@routingWindow);
runGroup('mac_queue_full_retains_existing_cancel_and_release_behavior',@rejectedRetry);
runGroup('late_data_sent_restarts_only_one_scan_without_resurrecting_owner',@fallback);
runGroup('live_dack_preserves_hold_and_exactly_once_capacity_release',@liveDack);
runGroup('control_terminal_expiry_keeps_original_cleanup',@controlExpiry);
report.checks=checks; report.completed=numel(checks)==16; report.passed=report.completed && all([checks.passed]);
report.attempted_checks=numel(checks); report.passed_checks=sum([checks.passed]);
report.failed_checks=sum(~[checks.passed]);
if ~report.passed
    report.error_identifier='terminalcase:ComponentFailures';
    report.error_message=sprintf('%d of %d terminal component groups failed; all independent groups were attempted. Read terminal_preflight.json and per-component public_callback_trace.json.',report.failed_checks,numel(checks));
end
ac.writeJson(fullfile(folder,'terminal_preflight.json'),report);
if ~report.passed, error(report.error_identifier,'%s',report.error_message); end
    function runGroup(name,callback)
        activeName=name; stages=struct('label',{},'passed',{},'actual',{},'expected',{});
        details=struct('stages',stages); passed=false;
        try
            callback(); passed=true;
        catch caught
            details.error_identifier=caught.identifier; details.error_message=caught.message;
            details.error_stack=caught.stack;
        end
        details.stages=stages;
        checks(end+1)=struct('name',name,'passed',passed,'details',details); %#ok<AGROW>
        persist();
        fprintf('  Terminal component %d/16: %s -- %s\n',numel(checks),name,passLabel(passed));
    end
    function expect(label,condition,actual,expected)
        stages(end+1)=struct('label',label,'passed',logical(condition),'actual',actual,'expected',expected); %#ok<AGROW>
        persist(); % Save actual values and callback state BEFORE any assertion.
        assert(condition,'terminalcase:ObservedMismatch','%s: %s. Actual: %s. Expected: %s.', ...
            activeName,label,jsonencode(actual),jsonencode(expected));
    end
    function persist()
        items=values(probes);
        for j=1:numel(items), items{j}.Persist(); end
        report.checks=checks; report.current_group=activeName; report.current_stages=stages;
        ac.writeJson(fullfile(folder,'terminal_preflight.json'),report);
    end
    function h=fresh(candidate,policy,name)
        h=harness(config,fullfile(folder,name),candidate,policy,resources); probes(name)=h;
    end
    function h=episode(candidate,policy,name)
        h=fresh(candidate,policy,name);
        [okay,initial]=h.Hop.send(packet(1,radio),2);
        expect('initial DATA admission',okay,h.Evidence(),struct('accepted',true)); h.Original=initial;
        h.Hop.notifySent(initial); h.Clock.run(2.1);
        h.Clock.run(3); [okay,trigger]=h.Hop.sendControl(control(50,'KEY_UPDATE'),9,radio);
        expect('first independent scan trigger admission',okay,h.Evidence(),struct('accepted',true));
        h.Hop.notifySent(trigger); h.Clock.run(5.1);
        h.Clock.run(8); [okay,trigger]=h.Hop.sendControl(control(51,'KEY_UPDATE'),10,radio);
        expect('second independent scan trigger admission',okay,h.Evidence(),struct('accepted',true));
        h.Hop.notifySent(trigger); h.Clock.run(10.1);
    end
    function retainsCopies()
        old=episode(false,'native-provisional','old_native'); h=episode(true,'native-provisional','candidate_native');
        expect('terminal copy lifetime',old.Hop.stats().Failed==1 && old.Mac.DataQueueCount==0 && ...
            h.Hop.stats().Failed==1 && h.Mac.DataQueueCount==2,struct('old',old.Evidence(),'candidate',h.Evidence()), ...
            struct('old_queue',0,'candidate_queue',2,'old_owner_failures',1,'candidate_owner_failures',1));
    end
    function cutoffRelease()
        h=episode(true,'native-provisional','cutoff');
        expect('owner releases and live getters',h.Hop.PendingDataCount==0 && h.Hop.admission(2).NeighborOutstanding==0 && ...
            numel(h.Releases())==1 && numel(h.Terminals())==1 && h.Mac.DataQueueCount==2,h.Evidence(), ...
            struct('pending',0,'neighbor_outstanding',0,'releases',1,'terminals',1,'live_mac_copies',2, ...
            'application_fate','unresolved','terminal_application_drop_inferred',false));
    end
    function actualTx()
        a=episode(false,'actual-tx','old_actual'); b=episode(true,'actual-tx','candidate_actual');
        expect('default and complete public evidence',isequaln(a.Evidence(),b.Evidence()) && ...
            strcmp(csr.hop.Layer.defaults().DataQueuedRetryPolicy,'actual-tx'), ...
            struct('old',a.Evidence(),'candidate',b.Evidence(),'default',csr.hop.Layer.defaults().DataQueuedRetryPolicy), ...
            struct('old_and_candidate_equal',true,'default','actual-tx'));
    end
    function realDrain()
        h=episode(true,'native-provisional','real_drain'); h.Drain();
        expect('drain and duplicate suppression',h.Mac.Counters.Transmissions==2 && h.Mac.Counters.SegmentsTransmitted==2 && ...
            h.Mac.DataQueueCount==0 && h.Hop.PendingDataCount==0 && numel(h.Releases())==1 && numel(h.Terminals())==1 && ...
            numel(h.Deliveries())==1 && h.Receiver.stats().Duplicates==1,h.Evidence(), ...
            struct('actual_mac_transmissions',2,'segments',2,'queue',0,'pending',0,'releases',1,'terminals',1,'deliveries',1,'duplicates',1));
        txTimes=h.TransmissionTimes(); terminalTimes=h.TerminalTimes();
        expect('first delivery follows terminal owner failure',numel(txTimes)==2 && numel(terminalTimes)==1 && ...
            all(txTimes>terminalTimes(1)),h.Evidence(),struct('all_tx_after_terminal',true, ...
            'scope','Public receiver HOP delivery only; integrated recoverDrop counter is unchanged and source-reviewed, not exercised here'));
    end
    function exactAck(), orphan('exact_ack'); end
    function windowAck(), orphan('window_ack'); end
    function windowDack(), orphan('window_dack'); end
    function orphan(kind)
        h=episode(true,'native-provisional',kind);
        h.Hop.receive(feedback(2,h.Original.Sequence,kind)); h.Hop.receive(feedback(2,h.Original.Sequence,kind));
        expect('repeated feedback cleans copies only',h.Mac.DataQueueCount==0 && h.Mac.Counters.Canceled==2 && h.Hop.PendingDataCount==0 && ...
            h.Hop.stats().Failed==1 && h.Hop.stats().Acknowledged==0 && h.Hop.stats().Dacked==0 && ...
            h.Hop.stats().DackHoldCount==0 && numel(h.Releases())==1 && numel(h.Terminals())==1,h.Evidence(), ...
            struct('queue',0,'canceled',2,'pending',0,'failed',1,'acknowledged',0,'dacked',0,'dack_hold',0,'releases',1,'terminals',1));
    end
    function singleDack()
        h=episode(true,'native-provisional','single_dack'); h.Hop.receive(feedback(2,h.Original.Sequence,'single_dack'));
        expect('single DACK disabled',h.Mac.DataQueueCount==2 && h.Hop.stats().Dacked==0 && numel(h.Releases())==1, ...
            h.Evidence(),struct('queue',2,'dacked',0,'releases',1));
    end
    function windowWrap()
        h=fresh(true,'native-provisional','window_wrap');
        for sequence=[0 65535 65534]
            okay=h.Mac.enqueue(csr.hop.Frames.data(packet(100+sequence,radio),1,2,uint16(sequence),radio));
            expect('enqueue wrapped DATA',okay,h.Evidence(),struct('accepted',true,'sequence',sequence));
        end
        okay=h.Mac.enqueue(csr.hop.Frames.data(packet(200,radio),1,3,uint16(0),radio));
        expect('enqueue other peer DATA',okay,h.Evidence(),struct('accepted',true,'peer',3));
        frame=csr.hop.Frames.acknowledgment(2,1,uint16(0),uint64(1),uint64(2),struct('HasAckWindow',true)); h.Hop.receive(frame);
        expect('wrapped union removes only two copies',h.Mac.DataQueueCount==2 && h.Mac.Counters.Canceled==2 && h.Hop.PendingDataCount==0, ...
            h.Evidence(),struct('queue',2,'canceled',2,'pending',0,'removed_sequences',[0 65535]));
        h.Mac.cancelData(2,uint16(65534)); h.Mac.cancelData(3,uint16(0));
        expect('retained identities confirmed by exact removal',h.Mac.DataQueueCount==0,h.Evidence(), ...
            struct('queue',0,'retained_sequence',65534,'retained_other_peer',3));
    end
    function overlap()
        h=fresh(true,'native-provisional','overlap'); [okay,frame]=h.Hop.send(packet(1,radio),2);
        expect('DATA admission',okay,h.Evidence(),struct('accepted',true));
        both=csr.hop.Frames.acknowledgment(2,1,frame.Sequence,uint64(1),uint64(1),struct('HasAckWindow',true));
        h.Hop.receive(both); h.Hop.receive(both);
        expect('overlap prefers ACK once',h.Hop.stats().Acknowledged==1 && h.Hop.stats().Dacked==0 && ...
            h.Hop.PendingDataCount==0 && numel(h.Releases())==1 && numel(h.Terminals())==1,h.Evidence(), ...
            struct('acknowledged',1,'dacked',0,'pending',0,'releases',1,'terminals',1));
    end
    function routingExact()
        h=fresh(true,'native-provisional','routing_exact'); [okay,route]=h.Hop.sendControl(control(55,'ROUTING'),[2 3],radio);
        expect('grouped ROUTING owner admission',okay,h.Evidence(),struct('accepted',true)); okay=h.Mac.enqueue(route);
        expect('grouped ROUTING MAC admission',okay,h.Evidence(),struct('accepted',true));
        h.Hop.receive(feedback(2,route.HopSequences(1),'exact_ack'));
        expect('partial group ACK retains owner and copy',h.Hop.stats().ControlPending==1 && h.Mac.DataQueueCount==1, ...
            h.Evidence(),struct('control_pending',1,'queue',1));
        h.Hop.receive(feedback(3,route.HopSequences(2),'exact_ack')); h.Hop.receive(feedback(2,route.HopSequences(1),'exact_ack'));
        expect('complete and repeated group ACK retains copy',h.Hop.stats().ControlPending==0 && h.Hop.stats().ControlCompleted==1 && ...
            h.Mac.DataQueueCount==1 && h.Mac.Counters.Canceled==0,h.Evidence(), ...
            struct('control_pending',0,'control_completed',1,'queue',1,'canceled',0));
    end
    function routingWindow()
        h=fresh(true,'native-provisional','routing_window'); [okay,route]=h.Hop.sendControl(control(56,'ROUTING'),[2 3],radio);
        expect('grouped ROUTING owner admission',okay,h.Evidence(),struct('accepted',true)); okay=h.Mac.enqueue(route);
        expect('grouped ROUTING MAC admission',okay,h.Evidence(),struct('accepted',true));
        h.Hop.receive(feedback(2,route.HopSequences(1),'window_ack')); h.Hop.receive(feedback(3,route.HopSequences(2),'window_dack'));
        expect('DATA window cannot complete ROUTING',h.Hop.stats().ControlPending==1 && h.Mac.DataQueueCount==1 && ...
            h.Hop.stats().ControlAcknowledged==0 && h.Hop.stats().ControlCompleted==0,h.Evidence(), ...
            struct('control_pending',1,'queue',1,'control_acknowledged',0,'control_completed',0));
    end
    function rejectedRetry()
        h=fresh(true,'native-provisional','rejected_retry'); [okay,frame]=h.Hop.send(packet(1,radio),2);
        expect('DATA admission',okay,h.Evidence(),struct('accepted',true)); h.Hop.notifySent(frame); h.AcceptRetry(false); h.Clock.run(3);
        released=h.Releases();
        expect('queue rejection keeps cancellation',h.Hop.stats().Failed==1 && h.Hop.PendingDataCount==0 && numel(released)==1 && ...
            strcmp(released{1}.Reason,'mac_queue_full') && h.CancelCalls()==1,h.Evidence(), ...
            struct('failed',1,'pending',0,'releases',1,'release_reason','mac_queue_full','cancel_calls',1));
    end
    function fallback()
        h=episode(true,'native-provisional','fallback'); scheduledBefore=h.Clock.PendingCount; before=h.Hop.stats().Transmitted;
        expect('fallback timer setup',scheduledBefore==1 && strcmp(h.Mac.State,'Track') && h.Mac.Counters.Transmissions==0, ...
            h.Evidence(),struct('pending_timers',1,'state','Track','actual_mac_transmissions',0));
        h.Hop.notifySent(h.Original);
        expect('first orphan send creates fallback',h.Clock.PendingCount==scheduledBefore+1,h.Evidence(),struct('pending_timers',scheduledBefore+1));
        h.Hop.notifySent(h.Original);
        expect('second orphan send reuses fallback',h.Clock.PendingCount==scheduledBefore+1,h.Evidence(),struct('pending_timers',scheduledBefore+1));
        h.Clock.run(13);
        expect('fallback cannot resurrect owner',h.Clock.PendingCount==scheduledBefore && h.Hop.PendingDataCount==0 && ...
            h.Hop.stats().Transmitted==before+2 && numel(h.Releases())==1 && numel(h.Terminals())==1,h.Evidence(), ...
            struct('pending_timers',scheduledBefore,'pending_owner',0,'transmitted',before+2,'releases',1,'terminals',1));
    end
    function liveDack()
        h=fresh(true,'native-provisional','live_dack'); [okay,frame]=h.Hop.send(packet(1,radio),2);
        expect('DATA admission',okay,h.Evidence(),struct('accepted',true)); h.Hop.notifySent(frame); h.Clock.run(2.1);
        h.Hop.receive(feedback(2,frame.Sequence,'window_dack')); h.Hop.receive(feedback(2,frame.Sequence,'window_dack'));
        expect('DACK retains hold and releases once',h.Mac.DataQueueCount==0 && h.Hop.PendingDataCount==1 && ...
            h.Hop.stats().DackHoldCount==1 && numel(h.Releases())==1,h.Evidence(),struct('queue',0,'pending',1,'dack_hold',1,'releases',1));
        h.Clock.run(23);
        expect('DACK expiry does not release twice',h.Hop.PendingDataCount==0 && h.Hop.stats().DackExpired==1 && numel(h.Releases())==1, ...
            h.Evidence(),struct('pending',0,'dack_expired',1,'releases',1));
    end
    function controlExpiry()
        h=fresh(true,'native-provisional','control_expiry'); [okay,frame]=h.Hop.sendControl(control(70,'KEY_UPDATE'),2,radio);
        expect('control owner admission',okay,h.Evidence(),struct('accepted',true)); okay=h.Mac.enqueue(frame);
        expect('control MAC admission',okay,h.Evidence(),struct('accepted',true));
        h.Hop.notifySent(frame); h.Clock.run(2.1); h.Hop.notifySent(frame); h.Clock.run(4.2); h.Hop.notifySent(frame); h.Clock.run(8.3);
        expect('control expiry keeps original cancellation',h.Hop.stats().ControlFailed==1 && h.Hop.stats().Failed==0 && ...
            h.Mac.DataQueueCount==0 && h.CancelCalls()==1,h.Evidence(),struct('control_failed',1,'data_failed',0,'queue',0,'cancel_calls',1));
    end
end
function label=passLabel(passed)
if passed, label='PASS'; else, label='FAIL'; end
end

function h=harness(config,folder,candidate,policy,resources)
mkdir(folder); clock=csr.sim.EventScheduler();
streams=ac.Streams(config.Seed,clock,'natural','',folder);
resources(folder)=streams;
options=config.Hop; options.DataQueuedRetryPolicy=policy; options.TicSeconds=1e-6;
options.MaxResends=2; options.ResendSeconds=2; options.DackHoldSeconds=20;
macOptions=config.Mac; macOptions.DutyCycleEnabled=false; macOptions.ConcatenationEnabled=false;
releases={}; terminals={}; deliveries={}; terminalTimes=[]; txTimes=[]; cancels=0; acceptedRetry=true; blocked=true;
events=struct('time_s',{},'event',{},'details',{});
receiver=csr.hop.Layer(2,clock,streams,options,struct('EnqueueMac',@(frame)true,'Deliver',@deliver,'Event',@receiverEvent));
mac=ac.TerminalMac(1,clock,streams,macOptions, ...
    struct('Transmit',@transmit,'Sent',@sent,'ReceiverState',@receiverState,'Event',@macEvent));
callbacks=struct('EnqueueMac',@enqueue,'NsdpRelease',@release,'Terminal',@terminal, ...
    'CancelMac',@cancel,'CancelMacData',@cancelData,'Event',@hopEvent);
if candidate, hop=ac.TerminalHop(1,clock,streams,options,callbacks);
else, hop=csr.hop.Layer(1,clock,streams,options,callbacks); end
h=struct('Clock',clock,'Hop',hop,'Mac',mac,'Receiver',receiver, ...
    'Releases',@getReleases,'Terminals',@getTerminals,'Deliveries',@getDeliveries, ...
    'TransmissionTimes',@getTransmissionTimes,'TerminalTimes',@getTerminalTimes, ...
    'CancelCalls',@getCancelCalls,'AcceptRetry',@setAccepted,'Evidence',@evidence,'Drain',@drain, ...
    'Persist',@persist);
    % Named nested getters observe the shared callback workspace at call time.
    % Anonymous @()value getters would freeze initial empty/zero values.
    function value=getReleases(), value=releases; end
    function value=getTerminals(), value=terminals; end
    function value=getDeliveries(), value=deliveries; end
    function value=getTransmissionTimes(), value=txTimes; end
    function value=getTerminalTimes(), value=terminalTimes; end
    function value=getCancelCalls(), value=cancels; end
    function logEvent(name,details)
        events(end+1)=struct('time_s',clock.Now,'event',name,'details',details);
    end
    function persist()
        ac.writeJson(fullfile(folder,'public_callback_trace.json'),struct( ...
            'schema','csr-terminal-public-callback-trace-v1','events',events, ...
            'state',evidence(),'scope','Public component callbacks and state only; no private state injection'));
    end
    function okay=enqueue(frame)
        okay=true;
        if strcmp(frame.Kind,'DATA') && frame.RetryCount>0
            okay=acceptedRetry;
            if okay, okay=mac.enqueue(frame); end
        end
        logEvent('enqueue_callback',struct('frame',frame,'accepted',okay,'mac_queue',mac.DataQueueCount));
    end
    function hopEvent(name,frame,details), logEvent(['sender_' name],struct('frame',frame,'details',details)); end
    function receiverEvent(name,frame,details), logEvent(['receiver_' name],struct('frame',frame,'details',details)); end
    function macEvent(name,frame,details), logEvent(['mac_' name],struct('frame',frame,'details',details)); end
    function removed=cancelData(peer,sequence)
        removed=mac.cancelData(peer,sequence);
        logEvent('cancel_data_callback',struct('peer',peer,'sequence',sequence,'removed',removed));
    end
    function setAccepted(value), acceptedRetry=value; logEvent('accept_retry',struct('value',value)); end
    function removed=cancel(peer,sequence)
        cancels=cancels+1; removed=mac.cancel(peer,sequence);
        logEvent('cancel_callback',struct('peer',peer,'sequence',sequence,'removed',removed));
    end
    function release(app,reason)
        releases{end+1}=struct('App',app,'Reason',reason);
        logEvent('nsdp_release',struct('application_id',app.Id,'reason',reason,'count',numel(releases)));
    end
    function terminal(app,success,reason)
        terminals{end+1}=struct('App',app,'Success',success,'Reason',reason); terminalTimes(end+1)=clock.Now;
        logEvent('terminal_callback',struct('application_id',app.Id,'success',success,'reason',reason,'count',numel(terminals)));
    end
    function okay=deliver(app,peer) %#ok<INUSD>
        deliveries{end+1}=app; okay=true;
        logEvent('delivery_callback',struct('application_id',app.Id,'count',numel(deliveries)));
    end
    function transmit(frame,duration) %#ok<INUSD>
        txTimes(end+1)=clock.Now;
        logEvent('actual_mac_transmit',struct('frame',frame,'duration_s',duration));
        for k=1:numel(frame.Segments), receiver.receive(frame.Segments{k}); end
    end
    function sent(frame), logEvent('actual_mac_sent',struct('frame',frame)); hop.notifySent(frame); end
    function state=receiverState()
        if blocked, state='Track'; else, state='Search'; end
    end
    function drain()
        blocked=false; logEvent('release_receiver_track',struct('state','Search'));
        mac.receiverChanged('Search'); clock.run(clock.Now+20);
    end
    function reason=releaseReason(record), reason=record.Reason; end
    function value=evidence()
        value=struct('hop',hop.stats(),'pending',hop.PendingDataCount,'mac_queue',mac.DataQueueCount, ...
            'releases',numel(releases),'terminals',numel(terminals),'cancel_calls',cancels, ...
            'admission',hop.admission(2),'mac_counters',mac.Counters,'mac_state',mac.State, ...
            'scheduler_pending',clock.PendingCount,'time_s',clock.Now,'receiver',receiver.stats(), ...
            'delivery_count',numel(deliveries),'transmission_times_s',txTimes,'terminal_times_s',terminalTimes, ...
            'release_reasons',{cellfun(@releaseReason,releases,'UniformOutput',false)}, ...
            'getter_counts',struct('releases',numel(getReleases()),'terminals',numel(getTerminals()), ...
            'deliveries',numel(getDeliveries()),'cancel_calls',getCancelCalls()));
    end
end
function app=packet(id,radio)
flow=struct('SourceId',1,'DestinationId',2,'ApplicationPayloadBytes',185, ...
    'TxPowerDbm',radio.TxPowerDbm);
app=csr.packet(id,flow,0,radio);
end
function value=control(id,type)
value=struct('Id',uint64(id),'Type',type,'Payload',struct(),'WirePayloadBytes',16);
end
function frame=feedback(peer,sequence,kind)
ack=uint64(0); dack=uint64(0); hasWindow=false; frameKind='ACK';
switch kind
    case 'window_ack', ack=uint64(1); hasWindow=true;
    case 'window_dack', dack=uint64(1); hasWindow=true; frameKind='DACK';
    case 'single_dack', frameKind='DACK';
end
frame=csr.hop.Frames.acknowledgment(peer,1,sequence,ack,dack, ...
    struct('HasAckWindow',hasWindow,'Kind',frameKind));
end

function radio=componentRadio(config)
% csr.packet requires complete radio fields and reads TX power from FLOW.
% Reuse the validated scenario's radio and source-node RF power, never an
% incomplete struct or an invented per-test radio default.
radio=config.Radio;
required={'EnvelopeProfile','RateKeyKbps','Preamble'};
assert(all(isfield(radio,required)),'terminalcase:ComponentRadio', ...
    'The validated scenario must supply all packet radio fields.');
index=find([config.Nodes.Id]==1);
assert(isscalar(index),'terminalcase:ComponentRadio','Expected one component source node1.');
radio.TxPowerDbm=config.Nodes(index).RadioProfile.TxPowerDbm;
validateattributes(radio.TxPowerDbm,{'numeric'},{'scalar','real','finite'});
end
function guard=streamRegistryGuard(resources)
% This local function captures its MAP HANDLE by value. Its cleanup never
% accesses a nested caller's partially destroyed shared workspace.
guard=onCleanup(@()closeStreamRegistry(resources));
end
function closeStreamRegistry(resources)
items=values(resources);
for k=1:numel(items)
    items{k}.close();
end
end
