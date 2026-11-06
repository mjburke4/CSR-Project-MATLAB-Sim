function report=run_node5_checks(mode)
% Public-API checks. Immediate assertions execute before any scheduler run.
% Invoke in a fresh MATLAB process; baseline loads the frozen candidate.
if nargin<1,mode='candidate';end
assert(strcmp(mode,'candidate'),'Published tests run the repaired candidate only.');
root=fileparts(mfilename('fullpath'));candidate=fileparts(root);
restoredefaultpath;addpath(root,candidate,fullfile(candidate,'model'),'-begin');rehash;
assert(startsWith(which('ac.DiscoveryMembershipNwk'),candidate));
config=configure_case(131,900);names={};
originalControlRetrySeconds=config.Nwk.ControlRetrySeconds;
% Isolate the NWK retryControls callback from the independent neighbor retry.
% The imported 8 s NWK retry follows the 5 s admission timer, whose evaluate
% callback legitimately queues an additional 'overheard' check and wake.
% This focused fixture uses 10 ms; the native replay configuration is untouched.
config.Nwk.ControlRetrySeconds=0.01;
assert(config.Nwk.ControlRetrySeconds<config.Nwk.Neighbor.AdmissionRetrySeconds);
[nwk,s,p,key]=setup(config,true);
nwk.controlResult(key,3,true,true,[]);
rows=p.select('NEIGHBOR_CHECK',3);
if strcmp(mode,'baseline')
    assert(isempty(rows),'Baseline unexpectedly admits inside ACK callback');
    s.run(0);rows=p.select('NEIGHBOR_CHECK',3);assert(numel(rows)==1);
    names={'baseline_deferred_not_immediate'};
else
    assert(numel(rows)==1 && rows{1}.Accepted);
    assert(strcmp(rows{1}.Control.Payload.Subtype,'discovery'));
    assert(rows{1}.Control.Payload.Sequence==uint32(17));
    assert(rows{1}.Options.AckRequired && isequal(rows{1}.Peers,3));
    names{end+1}='discovery_check_admitted_before_ack_callback_return';
    nwk.controlResult(key,3,true,true,[]);s.run(0);
    assert(numel(p.select('NEIGHBOR_CHECK',3))==1);
    names{end+1}='duplicate_completion_and_deferred_wake_no_duplicate';

    [nwk,s,p,key]=setup(config,true);p.Allowed=false;
    nwk.controlResult(key,3,true,true,[]);
    assert(isempty(p.select('NEIGHBOR_CHECK',3)));s.run(0);
    assert(isempty(p.select('NEIGHBOR_CHECK',3)));
    p.Allowed=true;s.run(config.Nwk.ControlRetrySeconds+1e-9);
    rows=p.select('NEIGHBOR_CHECK',3);assert(numel(rows)==1 && rows{1}.Accepted);
    names{end+1}='can_send_gate_retains_owner_for_timed_retry';

    [nwk,s,p,key]=setup(config,true);p.RejectChecks=true;
    nwk.controlResult(key,3,true,true,[]);rows=p.select('NEIGHBOR_CHECK',3);
    assert(numel(rows)==1 && ~rows{1}.Accepted);id=rows{1}.Control.Id;
    s.run(0);rows=p.select('NEIGHBOR_CHECK',3);assert(numel(rows)==2 && ~rows{2}.Accepted);
    p.RejectChecks=false;s.run(config.Nwk.ControlRetrySeconds+1e-9);
    rows=p.select('NEIGHBOR_CHECK',3);
    assert(numel(rows)==3 && rows{3}.Accepted && all(cellfun(@(r)r.Control.Id==id,rows)));
    names{end+1}='send_rejection_rolls_back_same_owner_and_retries';

    for outcome={'failed','incomplete','stale_generation','unknown_owner'}
        [nwk,~,p,key]=setup(config,true);kind=outcome{1};
        success=true;complete=true;
        if strcmp(kind,'failed'),success=false;end
        if strcmp(kind,'incomplete'),complete=false;end
        if strcmp(kind,'stale_generation'),key.Payload.Generation=key.Payload.Generation+1;end
        if strcmp(kind,'unknown_owner'),key.Id=key.Id+uint64(100000);end
        nwk.controlResult(key,3,success,complete,[]);
        assert(isempty(p.select('NEIGHBOR_CHECK',3)));
        names{end+1}=[kind '_completion_no_immediate_check'];
    end

    [nwk,~,p,key]=setup(config,false);nwk.controlResult(key,3,true,true,[]);
    assert(isempty(p.select('NEIGHBOR_CHECK',3)));
    names{end+1}='non_discovery_check_not_immediately_admitted';

    [nwk,~,p,key]=setup(config,true);p.BlockedPeers=4;
    nwk.receiveControl(struct('Type','KEY_UPDATE','Payload',struct()),4);
    assert(isempty(p.select('KEY_UPDATE',4)));p.BlockedPeers=[];
    nwk.controlResult(key,3,true,true,[]);
    assert(numel(p.select('NEIGHBOR_CHECK',3))==1);
    assert(isempty(p.select('KEY_UPDATE',4)));
    names{end+1}='ack_callback_does_not_pump_unrelated_owner';
end
report=struct('passed',true,'mode',mode,'source',which('ac.DiscoveryMembershipNwk'),'checks',{names}, ...
    'fixture_control_retry_seconds',config.Nwk.ControlRetrySeconds, ...
    'imported_control_retry_seconds',originalControlRetrySeconds, ...
    'neighbor_admission_retry_seconds',config.Nwk.Neighbor.AdmissionRetrySeconds, ...
    'scope','Public NWK admission boundaries; not a complete MAC/receiver integration test');
fid=fopen(fullfile(root,['checks_' mode '.json']),'w');assert(fid>=0);
cleanup=onCleanup(@()fclose(fid));fprintf(fid,'%s',jsonencode(report,PrettyPrint=true));
disp(report);
end

function [nwk,s,p,key]=setup(config,discovery)
s=csr.sim.EventScheduler(10000);p=Node5AckProbe();
callbacks=struct('CanSendControl',@(peers)p.canSend(peers), ...
    'SendControl',@(control,peers,options)p.send(control,peers,options));
nwk=ac.DiscoveryMembershipNwk(5,s,[],config,callbacks);
if discovery
    nwk.receiveControl(struct('Type','DISCOVER','Payload', ...
        struct('Subtype','broadcast','Sequence',uint32(17))),3);
end
nwk.receiveControl(struct('Type','KEY_UPDATE','Payload',struct()),3);
rows=p.select('KEY_UPDATE',3);assert(numel(rows)==1 && rows{1}.Accepted);
key=rows{1}.Control;assert(isempty(p.select('NEIGHBOR_CHECK',3)));
end
