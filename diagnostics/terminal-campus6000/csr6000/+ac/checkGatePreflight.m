function report=checkGatePreflight(config,folder)
%CHECKGATEPREFLIGHT Bounded public-API admission/deadline/owner checks.
% No private state is set. Inputs and completion outcomes enter through the
% same public Neighbors/NWK methods as the production HOP callback boundary.
if ~isfolder(folder), mkdir(folder); end
checks=struct('name',{},'passed',{},'details',{});
options=config.Nwk.Neighbor;

% Negative control reproduces the observed missing Overheard request.
[neighbors,clock,probe]=makeNeighbors('baseline',options); %#ok<ASGLU>
completeKeys(neighbors,probe,true);
neighbors.receiveControl('NEIGHBOR_CHECK',1,checkPayload('overheard'));
assert(probe.countChecks('discovery')==1 && probe.countChecks('overheard')==0, ...
    'autocase:CheckGatePreflight','Baseline no longer reproduces the broad proof gate.');
checks(end+1)=checked('baseline_discovery_suppresses_overheard', ...
    struct('discovery',1,'overheard',0));

for variant={'E','F'}
    name=variant{1};
    [neighbors,clock,probe]=makeNeighbors(name,options);
    % Before both key directions are established there is no check proof.
    neighbors.receiveControl('DISCOVER',1,discover());
    assert(probe.countChecks()==0,'autocase:CheckGatePreflight','Missing-key gate changed.');
    neighbors.receiveControl('KEY_UPDATE',1,struct('Generation',0));
    assert(probe.countChecks()==0,'autocase:CheckGatePreflight','Sent-key gate changed.');
    own=probe.last('KEY_UPDATE');
    neighbors.controlCompleted('KEY_UPDATE',1,own.payload,true);
    assert(probe.countChecks('discovery')==1 && probe.countChecks('overheard')==0, ...
        'autocase:CheckGatePreflight','Pending discovery did not retain first evaluation priority.');
    neighbors.receiveControl('NEIGHBOR_CHECK',1,checkPayload('overheard'));
    state=peerState(neighbors);
    assert(probe.countChecks('discovery')==1 && probe.countChecks('overheard')==1 && ...
        state.DiscoveryCheckActive,'autocase:CheckGatePreflight', ...
        'Discovery and Overheard did not coexist as separate outstanding proofs.');
    expectedFlag=strcmp(name,'E');
    assert(state.CheckActive==expectedFlag,'autocase:CheckGatePreflight', ...
        'Unexpected E/F flag ownership while discovery and overheard are outstanding.');
    firstDeadline=state.OverheardWhen+state.OverheardDelay;
    clock.run(firstDeadline/2);
    neighbors.receiveControl('NEIGHBOR_CHECK',1,checkPayload('overheard'));
    assert(probe.countChecks()==2,'autocase:CheckGatePreflight', ...
        'A duplicate proof was sent before its absolute deadline.');
    clock.run(firstDeadline);
    state=peerState(neighbors);
    assert(probe.countChecks('overheard')==2 && state.DiscoveryCheckActive && ...
        state.OverheardWhen==firstDeadline && state.OverheardDelay==2*firstDeadline, ...
        'autocase:CheckGatePreflight','Overdue proof was blocked or exponential deadline changed.');
    neighbors.receiveControl('NEIGHBOR_CHECK',1,checkPayload('overheard'));
    assert(probe.countChecks('overheard')==2,'autocase:CheckGatePreflight', ...
        'Retry reset allowed a duplicate at the same timestamp.');
    checks(end+1)=checked([name '_keys_discovery_and_absolute_deadline'], ...
        struct('first_deadline_s',firstDeadline,'overheard_requests',2, ...
        'discovery_requests',1,'initial_check_active',expectedFlag,'retry_delay_s',state.OverheardDelay));

    % A real incoming proof activates the peer; later input cannot create
    % another proof while active. Freshness expires through its public timer.
    neighbors.receiveControl('NEIGHBOR_CHECK',1,checkPayload('message'));
    assert(neighbors.isActive(1),'autocase:CheckGatePreflight','Completed-key peer did not activate.');
    before=probe.countChecks();
    neighbors.receiveControl('KEY_UPDATE',1,struct('Generation',0));
    neighbors.receiveControl('NEIGHBOR_CHECK',1,checkPayload('overheard'));
    assert(probe.countChecks()==before,'autocase:CheckGatePreflight','Active-peer gate changed.');
    fresh=options; fresh.FreshnessEnabled=true;
    fresh.FreshnessTimeoutSeconds=2; fresh.FreshnessPeriodSeconds=1;
    [stalePeer,staleClock,staleProbe]=makeNeighbors(name,fresh);
    completeKeys(stalePeer,staleProbe,true);
    stalePeer.start(); staleClock.run(3);
    state=peerState(stalePeer);
    assert(state.Stale,'autocase:CheckGatePreflight','Public freshness timer did not expire the peer.');
    before=staleProbe.countChecks();
    stalePeer.receiveControl('KEY_UPDATE',1,struct('Generation',0));
    state=peerState(stalePeer);
    assert(staleProbe.countChecks()==before && state.Stale, ...
        'autocase:CheckGatePreflight','Key input bypassed the stale-peer gate.');
    checks(end+1)=checked([name '_active_and_stale_gates'], ...
        struct('active_peer_suppresses_new_proofs',true,'stale_key_input_suppressed',true));
end

% Reachable difference: no pending Discovery, own Overheard awaiting ACK.
% The broad E flag suppresses a needed Message. F gives only Message that
% flag, and a later Overheard retry must preserve an already-true flag.
messageCounts=struct();
for variant={'E','F'}
    name=variant{1}; [neighbors,clock,probe]=makeNeighbors(name,options);
    completeKeys(neighbors,probe,false);
    assert(probe.countChecks('overheard')==1,'autocase:CheckGatePreflight', ...
        'Unsolicited key handshake did not produce its first Overheard.');
    neighbors.receiveControl('NEIGHBOR_CHECK',1,checkPayload('overheard'));
    expected=double(strcmp(name,'F'));
    assert(probe.countChecks('message')==expected,'autocase:CheckGatePreflight', ...
        'E/F Message flag characterization differs from its declared scope.');
    neighbors.receiveControl('NEIGHBOR_CHECK',1,checkPayload('overheard'));
    assert(probe.countChecks('message')==expected,'autocase:CheckGatePreflight', ...
        'Outstanding Message owner was duplicated before completion.');
    state=peerState(neighbors); clock.run(state.OverheardWhen+state.OverheardDelay);
    state=peerState(neighbors);
    assert(probe.countChecks('overheard')==2 && state.CheckActive, ...
        'autocase:CheckGatePreflight','Overheard retry cleared an existing Message flag.');
    neighbors.receiveControl('NEIGHBOR_CHECK',1,checkPayload('overheard'));
    assert(probe.countChecks('message')==expected,'autocase:CheckGatePreflight', ...
        'Non-Message transmission made an outstanding Message eligible again.');
    messageCounts.(name)=expected;
end
checks(end+1)=checked('message_flag_E_characterization_F_expectation', ...
    struct('message_requests',messageCounts,'outstanding_message_flag_preserved',true));

% Public NWK callbacks prove these two reliable checks have independent
% control IDs/custody, and completion of one cannot remove the other.
for variant={'E','F'}
    name=variant{1}; [layer,clock,probe]=makeNwk(name,config);
    layer.receiveControl(struct('Type','DISCOVER','Payload',discover()),1);
    first=probe.Calls{1}; layer.controlResult(first.control,1,true,true,[]);
    layer.receiveControl(struct('Type','KEY_UPDATE','Payload',struct('Generation',0)),1);
    clock.run(0); own=lastNwk(probe,'KEY_UPDATE');
    layer.controlResult(own.control,1,true,true,[]);
    layer.receiveControl(struct('Type','NEIGHBOR_CHECK','Payload',checkPayload('overheard')),1);
    clock.run(0);
    proofs={};
    for k=1:numel(probe.Calls)
        if strcmp(probe.Calls{k}.control.Type,'NEIGHBOR_CHECK'), proofs{end+1}=probe.Calls{k}; end %#ok<AGROW>
    end
    state=layer.stats();
    assert(numel(proofs)==2 && proofs{1}.control.Id~=proofs{2}.control.Id && ...
        proofs{1}.options.AckRequired && proofs{2}.options.AckRequired && ...
        state.PendingControlMessages==2,'autocase:CheckGatePreflight', ...
        'Two proof requests did not retain separate reliable owners.');
    layer.controlResult(proofs{1}.control,1,false,true,[]); state=layer.stats();
    assert(state.PendingControlMessages==1,'autocase:CheckGatePreflight', ...
        'One completed proof removed another owner.');
    layer.controlResult(proofs{2}.control,1,false,true,[]); state=layer.stats();
    assert(state.PendingControlMessages==0,'autocase:CheckGatePreflight', ...
        'Second completed proof retained unexpected custody.');
    checks(end+1)=checked([name '_independent_reliable_proof_owners'], ...
        struct('control_ids',[proofs{1}.control.Id proofs{2}.control.Id], ...
        'pending_after_first_completion',1,'pending_after_second_completion',0));
end

report=struct('schema','csr-check-gate-preflight-v1','passed',all([checks.passed]), ...
    'checks',checks,'network_simulation_executed',false,'random_variates_requested',0, ...
    'scope','Public admission, deadline and callback custody checks; full E/F network results remain separate', ...
    'E_limitation','Broad CheckActive still suppresses Message while a non-Message proof is outstanding', ...
    'F_scope','Only Message sets CheckActive; existing true state and original completion clearing remain');
ac.writeJson(fullfile(folder,'check_gate_preflight.json'),report);
end

function [neighbors,clock,probe]=makeNeighbors(variant,options)
clock=csr.sim.EventScheduler(200); probe=ac.CheckGateProbe(); probe.Scheduler=clock;
callbacks=struct('SendControl',@(kind,peers,payload,reliable)probe.send(kind,peers,payload,reliable));
switch variant
    case 'baseline', neighbors=csr.nwk.Neighbors(5,clock,options,callbacks);
    case 'E', neighbors=ac.CheckGateNeighbors(5,clock,options,callbacks);
    case 'F', neighbors=ac.MessageFlagNeighbors(5,clock,options,callbacks);
end
end

function completeKeys(neighbors,probe,withDiscovery)
if withDiscovery, neighbors.receiveControl('DISCOVER',1,discover()); end
neighbors.receiveControl('KEY_UPDATE',1,struct('Generation',0));
own=probe.last('KEY_UPDATE'); neighbors.controlCompleted('KEY_UPDATE',1,own.payload,true);
end

function state=peerState(neighbors)
data=neighbors.snapshot(); state=data.Peers([data.Peers.Id]==1);
assert(isscalar(state),'autocase:CheckGatePreflight','Expected exactly one peer record.');
end

function payload=discover()
payload=struct('Subtype','broadcast','Sequence',1,'ActivePeers',[]);
end

function payload=checkPayload(subtype)
payload=struct('Subtype',subtype,'Sequence',0,'Active',false,'Generation',0);
end

function [layer,clock,probe]=makeNwk(variant,config)
clock=csr.sim.EventScheduler(200); probe=ac.KeyProbe(); probe.Scheduler=clock;
callbacks=struct('SendControl',@(control,peers,options)probe.sendControl(control,peers,options), ...
    'CancelControl',@(peer,kind)probe.cancelControl(peer,kind),'CanSendControl',@(peers)true);
streams=csr.sim.RandomStreams(config.Seed);
if strcmp(variant,'E')
    layer=ac.CheckGateNwk(5,clock,streams,config,callbacks);
else
    layer=ac.MessageFlagNwk(5,clock,streams,config,callbacks);
end
probe.Layer=layer;
end

function row=lastNwk(probe,kind)
row=[];
for k=numel(probe.Calls):-1:1
    if strcmp(probe.Calls{k}.control.Type,kind), row=probe.Calls{k}; return; end
end
error('autocase:CheckGatePreflight','Missing NWK %s submission.',kind);
end

function value=checked(name,details)
value=struct('name',name,'passed',true,'details',details);
end
