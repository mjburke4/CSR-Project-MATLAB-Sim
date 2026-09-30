function report = keyRequestPreflight(config,folder)
%KEYREQUESTPREFLIGHT Exercise the candidate through public receiveControl.
% This is an isolated NWK/callback test. It creates no PHY, HOP or MAC model,
% requests no random variates and never accesses private candidate state.
if ~isfolder(folder), mkdir(folder); end
checks=struct('name',{},'passed',{},'details',{});

% The baseline must reproduce the evidence: fresh admission remains queued
% until the already-existing zero-delay pump gets a scheduler turn.
[layer,clock,probe]=makeLayer(config,false,4);
layer.receiveControl(discover(1),1);
state=layer.stats();
assert(isempty(probe.Calls) && state.PendingControlMessages==1, ...
    'autocase:KeyPreflight','Baseline KEY_REQUEST unexpectedly became inline.');
checks(end+1)=checked('baseline_key_request_is_deferred', ...
    struct('send_callbacks_before_scheduler',0,'pending_controls',state.PendingControlMessages));

% Candidate admission must be visible before any scheduler callback, with
% exactly the original unacknowledged KEY_REQUEST radio options/byte size.
[layer,clock,probe]=makeLayer(config,true,4);
layer.receiveControl(discover(1),1);
state=layer.stats();
assert(numel(probe.Calls)==1 && state.PendingControlMessages==1, ...
    'autocase:KeyPreflight','Candidate did not admit just one fresh owner inline.');
call=probe.Calls{1};
assert(strcmp(call.control.Type,'KEY_REQUEST') && isequal(call.peers,1) && ...
    ~call.options.AckRequired && call.control.WirePayloadBytes==18 && ...
    call.options.RateKeyKbps==8 && clock.Now==0, ...
    'autocase:KeyPreflight','Candidate changed KEY_REQUEST payload/transport semantics.');
checks(end+1)=checked('fresh_key_request_is_inline',call);

% An already-queued unrelated KEY_UPDATE must stay deferred. An unrelated
% application also remains in NWK custody; no general queue pump is invoked.
[layer,clock,probe]=makeLayer(config,true,4);
layer.receiveControl(struct('Type','KEY_REQUEST','Payload',struct('Generation',0)),2);
app=struct('Id',uint64(77),'SourceId',3,'DestinationId',8,'Dscp',0);
accepted=layer.sendApplication(app);
assert(accepted && isempty(probe.Calls),'autocase:KeyPreflight', ...
    'An unrelated owner was submitted before its pump.');
layer.receiveControl(discover(1),1);
state=layer.stats();
assert(numel(probe.Calls)==1 && strcmp(probe.Calls{1}.control.Type,'KEY_REQUEST') && ...
    state.PendingControlMessages==2 && state.PendingCustody==1 && probe.DataCalls==0, ...
    'autocase:KeyPreflight','Fresh admission flushed another control or application owner.');
checks(end+1)=checked('other_owners_are_not_flushed', ...
    struct('pending_controls',state.PendingControlMessages,'pending_applications',state.PendingCustody, ...
    'send_callbacks',numel(probe.Calls),'data_callbacks',probe.DataCalls));

% Replacement retains the existing cancel-before-replace and capacity rules.
[layer,clock,probe]=makeLayer(config,true,1);
layer.receiveControl(discover(1),1);
oldId=probe.Calls{1}.control.Id;
layer.receiveControl(discover(2),1);
state=layer.stats();
assert(numel(probe.Calls)==2 && numel(probe.Ledger)==3 && ...
    strcmp(probe.Ledger{1}.event,'send') && strcmp(probe.Ledger{2}.event,'cancel') && ...
    strcmp(probe.Ledger{3}.event,'send') && probe.Calls{2}.control.Id~=oldId && ...
    state.PendingControlMessages==1 && state.ControlQueueRejections==0, ...
    'autocase:KeyPreflight','Submitted KEY_REQUEST replacement broke ownership or capacity.');
checks(end+1)=checked('submitted_owner_replaced_after_cancellation', ...
    struct('ledger',{probe.Ledger},'pending_controls',state.PendingControlMessages));

% Full capacity rejects the new owner before any inline SendControl call.
[layer,clock,probe]=makeLayer(config,true,1);
layer.receiveControl(struct('Type','KEY_REQUEST','Payload',struct('Generation',0)),2);
layer.receiveControl(discover(1),1);
state=layer.stats();
assert(isempty(probe.Calls) && state.PendingControlMessages==1 && ...
    state.ControlQueueRejections==1,'autocase:KeyPreflight', ...
    'Capacity rejection occurred after submission or lost an existing owner.');
checks(end+1)=checked('capacity_checked_before_inline_submission', ...
    struct('pending_controls',state.PendingControlMessages,'rejections',state.ControlQueueRejections));

% A rejected HOP submission must retain the original owner and use the
% existing wake path. A successful same-time retry must not be duplicated.
[layer,clock,probe]=makeLayer(config,true,4);
probe.Accept=false; layer.receiveControl(discover(1),1);
state=layer.stats();
assert(numel(probe.Calls)==1 && state.PendingControlMessages==1, ...
    'autocase:KeyPreflight','Rejected inline submission lost its owner.');
oldId=probe.Calls{1}.control.Id;
probe.Accept=true; executed=clock.run(0);
assert(executed>0 && numel(probe.Calls)==2 && probe.Calls{2}.control.Id==oldId, ...
    'autocase:KeyPreflight','Rejected inline submission did not retry its retained owner.');
clock.run(0);
assert(numel(probe.Calls)==2,'autocase:KeyPreflight','Accepted owner was submitted twice.');
checks(end+1)=checked('rejected_submission_uses_original_wake_retry', ...
    struct('owner_id',oldId,'send_callbacks',numel(probe.Calls),'same_time_callbacks_executed',executed));

% SendControl may synchronously complete/remove the owner. Candidate code
% must re-find it by ID after the callback and must not resurrect it.
[layer,clock,probe]=makeLayer(config,true,4);
probe.CompleteInline=true; layer.receiveControl(discover(1),1);
state=layer.stats();
assert(numel(probe.Calls)==1 && state.PendingControlMessages==0, ...
    'autocase:KeyPreflight','Synchronous completion resurrected or retained its owner.');
clock.run(0); state=layer.stats();
assert(numel(probe.Calls)==1 && state.PendingControlMessages==0, ...
    'autocase:KeyPreflight','Wake after synchronous completion resubmitted its owner.');
checks(end+1)=checked('synchronous_completion_does_not_resurrect_owner', ...
    struct('send_callbacks',numel(probe.Calls),'pending_controls',state.PendingControlMessages));

report=struct('schema','csr-inline-key-request-preflight-v1','passed',all([checks.passed]), ...
    'checks',checks,'network_simulation_executed',false,'random_variates_requested',0, ...
    'scope','Public NWK receiveControl and callback boundary; not an end-to-end PHY/MAC parity result');
ac.writeJson(fullfile(folder,'key_request_preflight.json'),report);
end

function [layer,clock,probe]=makeLayer(config,candidate,limit)
config.Nwk.ControlQueueLimit=limit;
clock=csr.sim.EventScheduler(100); probe=ac.KeyProbe(); probe.Scheduler=clock;
callbacks=struct('SendControl',@(control,peers,options)probe.sendControl(control,peers,options), ...
    'CancelControl',@(peer,kind)probe.cancelControl(peer,kind), ...
    'SendData',@(app,peer,options)probe.sendData(app,peer,options), ...
    'CanSendControl',@(peers)true,'CanSendData',@(peer)true);
streams=csr.sim.RandomStreams(config.Seed);
if candidate
    layer=ac.InlineKeyNwk(3,clock,streams,config,callbacks);
else
    layer=csr.nwk.Layer(3,clock,streams,config,callbacks);
end
probe.Layer=layer;
end

function control=discover(sequence)
control=struct('Type','DISCOVER','Payload', ...
    struct('Subtype','broadcast','Sequence',sequence,'ActivePeers',[]));
end

function value=checked(name,details)
value=struct('name',name,'passed',true,'details',details);
end
