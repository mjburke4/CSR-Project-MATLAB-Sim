function report=run_nwk_owner_checks(mode)
% Synthetic public NWK/scheduler tests. No PHY, RNG or full-network execution.
if nargin<1,mode='candidate';end
assert(strcmp(mode,'candidate'),'Published tests run the repaired candidate only.');
root=fileparts(mfilename('fullpath'));candidate=fileparts(root);
restoredefaultpath;addpath(root,candidate,fullfile(candidate,'model'),'-begin');rehash;
assert(startsWith(which('ac.DiscoveryMembershipNwk'),candidate));
config=configure_case(131,900);config.Nwk.Neighbor.AdmissionEnabled=false;
config.Nwk.Neighbor.DiscoveryResponseEnabled=false;
ticSeconds=config.Hop.TicSeconds;checks={};representations={};
cleanup=onCleanup(@()ac.Trace.holder('set',[])); %#ok<NASGU>
% Retry has the older event ID at an exactly shared binary64 deadline.
for base=[0 1012.62]
 [n,s,p]=setup(config);s.run(base);due=base+ticSeconds;
 s.scheduleAt(due,@()p.push(880));assert(n.sendApplication(app(896)));
 s.run(due);expected=[880 896];
 if strcmp(mode,'baseline'),expected=[896 880];end
 assert(isequal(p.Queue,expected),'Retry/new arrival order unexpected');
 representations{end+1}=struct('base',base,'due',due,'base_hex',num2hex(base), ...
  'due_hex',num2hex(due),'rounded_due_ns',round(due*1e9),'observed_queue',p.Queue,'observed_times',p.Times, ...
  'scheduler_records',{p.Records});
end
checks{end+1}='older_retry_equal_deadline_fifo';
if strcmp(mode,'baseline')
 report=finish(root,mode,candidate,checks,representations,config);return
end
% Reverse installation order must reverse the synthetic FIFO insertion.
[n,s,p]=setup(config);assert(n.sendApplication(app(896)));s.scheduleAt(ticSeconds,@()p.push(880));
s.run(ticSeconds);assert(isequal(p.Queue,[896 880]));checks{end+1}='reversed_equal_deadline_installation_order';

% Local arrivals retain the first event/deadline; a generic control wake cannot bypass it.
[n,s,p]=setup(config);before=s.PendingCount;assert(n.sendApplication(app(1)));
assert(s.PendingCount==before+1);s.run(ticSeconds/2);assert(isempty(p.Sent));
assert(n.sendApplication(app(2)));assert(s.PendingCount==before+1);
n.wake();s.run(ticSeconds/2);assert(isempty(p.Sent));
s.run(ticSeconds);assert(isequal(p.Queue,[1 2]) && all(p.Times==ticSeconds));
checks{end+1}='coalesced_local_deadline_and_control_wake_scope';

% Direct (already HOP-delayed) service is inline and leaves local guard intact.
[n,s,p]=setup(config);p.Allowed=false;assert(n.sendApplication(app(1)));count=s.PendingCount;
n.checkDataQueue();assert(p.GateCalls==1 && s.PendingCount==count);
assert(n.sendApplication(app(2)));assert(s.PendingCount==count);
s.run(ticSeconds);assert(p.GateCalls==3 && isempty(p.Sent));
p.Allowed=true;n.checkDataQueue();assert(isequal(p.Queue,[1 2]) && all(p.Times==ticSeconds));
n.checkDataQueue();assert(numel(p.Sent)==2);checks{end+1}='direct_service_does_not_clear_local_guard_or_duplicate';

% A preinstalled HOP service callback owns its one TIC; no second event is added.
[n,s,p]=setup(config);s.scheduleAt(ticSeconds,@()n.checkDataQueue());
assert(n.sendApplication(app(3)));s.run(ticSeconds/2);assert(isempty(p.Sent));
s.run(ticSeconds);assert(isequal(p.Queue,3) && p.Times==ticSeconds);
checks{end+1}='already_delayed_hop_service_no_second_tic';

% Relay copies share local scheduling, but retain distinct per-copy custody.
[n,s,p]=setup(config);a=app(4);a.SourceId=4;a.Traversal=4;
before=s.PendingCount;[ok,why]=n.receiveData(a,4);assert(ok && isempty(why));
assert(s.PendingCount==before+1);assert(n.receiveData(a,4));assert(s.PendingCount==before+1);
assert(n.custodyCount(a)==2);s.run(ticSeconds);assert(numel(p.Sent)==2);
assert(p.Sent{1}.app.NwkCustodyId~=p.Sent{2}.app.NwkCustodyId);
n.releaseFromHop(p.Sent{1}.app,'test');assert(n.custodyCount(a)==1);
n.releaseFromHop(p.Sent{1}.app,'duplicate');assert(n.custodyCount(a)==1);
n.releaseFromHop(p.Sent{2}.app,'test');assert(n.custodyCount(a)==0);
checks{end+1}='relay_local_owner_and_distinct_copy_release';

limited=config;limited.Nwk.QueueLimit=1;[n,s,p]=setup(limited);
assert(n.sendApplication(app(1)));count=s.PendingCount;assert(~n.sendApplication(app(2)));
assert(s.PendingCount==count && n.custodyCount(app(2))==0);s.run(ticSeconds);assert(isequal(p.Queue,1));
checks{end+1}='rejected_arrival_no_event_or_custody';

[n,s,p]=setup(config);a=app(7);a.DestinationId=99;
assert(n.sendApplication(a));s.run(ticSeconds);assert(isempty(p.Sent) && n.custodyCount(a)==1);
relay=a;relay.SourceId=4;relay.Traversal=4;count=s.PendingCount;
[ok,why]=n.receiveData(relay,4);assert(~ok && strcmp(why,'no_route') && s.PendingCount==count);
n.observe(99,struct());s.run(s.Now);n.checkDataQueue();assert(numel(p.Sent)==1);
checks{end+1}='no_route_retained_local_and_rejected_relay';

[n,s,p]=setup(config);p.Accept=false;assert(n.sendApplication(app(8)));s.run(ticSeconds);
assert(numel(p.Sent)==1 && ~p.Sent{1}.accepted && n.custodyCount(app(8))==1);
p.Accept=true;n.checkDataQueue();assert(numel(p.Sent)==2 && p.Sent{2}.accepted);
assert(p.Sent{1}.app.NwkCustodyId==p.Sent{2}.app.NwkCustodyId);
checks{end+1}='send_rejection_retains_exact_owner';

[n,s,p]=setup(config);p.Reentrant=app(10);assert(n.sendApplication(app(9)));s.run(ticSeconds);
assert(isequal(p.Queue,9));s.run(2*ticSeconds);assert(isequal(p.Queue,[9 10]));
assert(isequal(p.Times,[ticSeconds 2*ticSeconds]));checks{end+1}='reentrant_enqueue_gets_new_local_owner';
report=finish(root,mode,candidate,checks,representations,config);
end
function [n,s,p]=setup(config)
s=csr.sim.EventScheduler(10000);p=NwkOwnerProbe(s);ac.Trace.holder('set',p);
cb=struct('CanSendData',@(peer)p.canSend(peer),'SendData',@(a,peer,o)p.send(a,peer,o), ...
 'CanSendControl',@(~)true,'SendControl',@(~,~,~)true);
n=ac.DiscoveryMembershipNwk(5,s,[],config,cb);p.Network=n;
n.observe(3,struct());n.observe(4,struct());s.run(0);
assert(n.routeAvailable(app(1)));p.GateCalls=0;p.Sent={};p.Queue=[];p.Times=[];p.Records={};
end
function a=app(id)
a=struct('Id',uint64(id),'SourceId',5,'DestinationId',3,'Dscp',0, ...
 'AckRequired',true,'HopCount',0,'Traversal',5,'PayloadBytes',185,'CreatedSeconds',0);
end
function report=finish(root,mode,candidate,checks,representations,config)
report=struct('passed',true,'mode',mode,'source',candidate,'checks',{checks}, ...
 'deadline_representations',{representations},'tic_seconds',config.Hop.TicSeconds, ...
 'baseline_discriminates_known_wrong_order',strcmp(mode,'baseline'), ...
 'scope','NWK/scheduler public components, synthetic FIFO sink; real MAC retention and node5 controls covered by existing suites', ...
 'fixture_changes','Neighbor admission and discovery response disabled for deterministic public observe route setup only');
fid=fopen(fullfile(root,['owner_checks_' mode '.json']),'w');assert(fid>=0);c=onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s',jsonencode(report,PrettyPrint=true));disp(report);
end
