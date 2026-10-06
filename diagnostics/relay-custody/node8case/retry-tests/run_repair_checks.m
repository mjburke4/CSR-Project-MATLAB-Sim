function run_repair_checks(output,only)
root=fileparts(mfilename('fullpath'));source=fileparts(root);
restoredefaultpath;addpath(root,source,fullfile(source,'model'),'-begin');
assert(~isfolder(output));mkdir(output);report=struct('passed',false,'cases',{{}},'error','');
report.matlab_version=version;
config=configure_case(131,6000);report.config=config;report.class_path=which('ac.DiscoveryMembershipNwk');
assert(startsWith(report.class_path,source));
names={'snapshotLifecycle','requestFailure','automaticBeyondCap','requestRestart', ...
 'naturalSnapshot','naturalRequest','partialAck','inactivePruning','backpressure','staleRequestTimers'};
if nargin>1,assert(all(ismember(only,names)));names=only;end
for k=1:numel(names)
 name=names{k};entry=struct('name',name,'passed',false,'error','');
 try,entry.evidence=feval(name,config);entry.passed=true;
 catch e,entry.error=e.message;entry.stack=e.stack;end
 report.cases{end+1}=entry;write_json(fullfile(output,[name '.json']),entry);
 fprintf('%s: %d %s\n',name,entry.passed,entry.error);
end
checks={'requestWirePreflight','noPathWirePreflight','routeAdmissionPreflight', ...
 'discoveryMembershipPreflight','relayCustodyPreflight','terminalPreflight'};
if nargin>1,checks={};end
for k=1:numel(checks)
 name=checks{k};entry=struct('name',name,'passed',false,'error','');
 try
  entry.evidence=feval(['ac.' name],config,fullfile(output,name));entry.passed=entry.evidence.passed;
 catch e,entry.error=e.message;entry.stack=e.stack;end
 report.cases{end+1}=entry;write_json(fullfile(output,[name '.json']),entry);
 fprintf('%s: %d %s\n',name,entry.passed,entry.error);
end
report.source_scope='Published relay-custody diagnostic with focused retry repair';
report.passed=all(cellfun(@(e)e.passed,report.cases));
report.scope='Controlled NWK/HOP callbacks, natural no-ACK HOP timers and focused preflights. No stochastic network batch. PHY/ECC/RNG source unchanged.';
write_json(fullfile(output,'report.json'),report);assert(report.passed,'repair:ChecksFailed','See individual results');
end

function evidence=snapshotLifecycle(config)
p=RetryProbe(config);p.activate();rows=p.ofKind('snapshot');first=rows{1};assert(numel(rows)==1);
p.ackOther(first.control_id);p.Clock.run(1);p.receiveRequest(900);assert(numel(p.ofKind('snapshot'))==1);
p.Clock.run(2);p.complete(first,false);assert(numel(p.ofKind('snapshot'))==1);
p.Clock.run(5);p.receiveRequest(901);assert(numel(p.ofKind('snapshot'))==1);
p.Clock.run(20);p.action('watchdog');assert(numel(p.ofKind('snapshot'))==1);
assert(any(cellfun(@(e)strcmp(e.name,'routing_outbound_snapshot_timeout'),p.Events)));
p.Clock.run(21);p.receiveRequest(902);rows=p.ofKind('snapshot');assert(numel(rows)==2&&rows{end}.sequence~=first.sequence);
p.complete(rows{end},true);p.Clock.run(22);p.receiveRequest(903);assert(numel(p.ofKind('snapshot'))==3);
s=p.Layer.stats();assert(s.ControlResidualRetries==0&&s.ControlFailures==1&&s.SnapshotTimeouts==1);
evidence=p.export('snapshot_lifecycle');
end
function evidence=requestFailure(config)
p=RetryProbe(config);p.activate();p.ackOther(uint64([]));assert(p.Layer.startDiscovery(0,.001));p.Clock.run(.001);
rows=p.ofKind('request');first=rows{1};assert(numel(rows)==1);p.Clock.run(1);p.complete(first,false);
assert(numel(p.ofKind('request'))==1);p.Clock.run(8.001);rows=p.ofKind('request');
assert(numel(rows)==2&&rows{end}.sequence~=first.sequence&&rows{end}.control_id~=first.control_id);
assert(rows{end}.control.WirePayloadBytes==16&&strcmp(rows{end}.control.Payload.WireRepresentation,'legacy_request_header'));
s=p.Layer.stats();assert(s.ControlResidualRetries==0&&s.RouteRequests==2);evidence=p.export('request_failure');
end
function evidence=automaticBeyondCap(config)
p=RetryProbe(config);p.activate();rows=p.ofKind('automatic_update');first=rows{1};p.ackOther(first.control_id);
for cycle=1:6
 p.Clock.run(cycle);rows=p.ofKind('automatic_update');p.complete(rows{end},false);
 assert(numel(p.ofKind('automatic_update'))==cycle+1);
end
rows=p.ofKind('automatic_update');assert(all(cellfun(@(r)r.sequence==first.sequence&&isequal(r.bytes,first.bytes),rows)));
assert(numel(unique(cellfun(@(r)double(r.control_id),rows)))==7);p.complete(rows{end},true);
% Delayed failure from an old HOP transaction must not resurrect its owner.
p.Layer.controlResult(first.control,3,false,true,3);p.Clock.run(6);assert(numel(p.ofKind('automatic_update'))==7);
s=p.Layer.stats();assert(s.ControlResidualRetries==6&&s.ControlFailures==0&&s.PendingControlMessages==0);
evidence=p.export('automatic_beyond_cap');
end
function evidence=requestRestart(config)
p=RetryProbe(config);p.activate();p.ackOther(uint64([]));assert(p.Layer.startDiscovery(0,.001));p.Clock.run(.001);p.ackOther(uint64([]));
p.Clock.run(8.001);p.ackOther(uint64([]));p.Clock.run(16.001);p.ackOther(uint64([]));assert(numel(p.ofKind('request'))==3);
% A second discovery before final response timeout must not prematurely restart.
p.Clock.run(23);assert(p.Layer.startDiscovery(0,.001));p.Clock.run(23.002);assert(numel(p.ofKind('request'))==3);
p.Clock.run(24.001);assert(p.Layer.startDiscovery(0,.001));p.Clock.run(24.003);rows=p.ofKind('request');
assert(numel(rows)==4&&rows{end}.sequence~=rows{3}.sequence);p.ackOther(uint64([]));
p.Clock.run(32.003);rows=p.ofKind('request');assert(numel(rows)==5);s=p.Layer.stats();
assert(s.DiscoveryCompletions==3&&s.RouteRequests==5);evidence=p.export('request_restart_after_full_final_interval');
end
function evidence=naturalSnapshot(config),evidence=natural(config,'snapshot');end
function evidence=naturalRequest(config),evidence=natural(config,'request');end
function evidence=natural(config,kind)
p=RetryProbe(config);p.NaturalKind=kind;p.activate();keep=p.ofKind(kind);ids=uint64([]);
for k=1:numel(keep),ids(end+1)=keep{k}.control_id;end
p.ackOther(ids);if strcmp(kind,'request'),assert(p.Layer.startDiscovery(0,.001));p.Clock.run(.001);end
p.Clock.run(9);assert(numel(p.NaturalCompletions)==1&&~p.NaturalCompletions{1}.success);
start=0;if strcmp(kind,'request'),start=.001;end
assert(abs(p.NaturalCompletions{1}.t_s-(start+8+3*config.Hop.TicSeconds))<1e-12);
rows=p.ofKind(kind);first=rows{1};same=rows(cellfun(@(r)r.sequence==first.sequence,rows));assert(numel(same)==1);
if strcmp(kind,'request')
 assert(numel(rows)==2&&rows{2}.t_s<p.NaturalCompletions{1}.t_s);
else,assert(numel(rows)==1);end
s=p.Layer.stats();assert(s.ControlResidualRetries==0);evidence=p.export(['natural_no_ack_' kind]);
end
function evidence=partialAck(config)
p=RetryProbe(config);p.activate(3);p.activate(5);p.ackOther(uint64([]));
% Admission alone need not mark a selected route change. Learn a real route
% after both peers are active to obtain the native grouped automatic stream.
p.Clock.run(.1);record=struct('Operation','UPDATE','NodeId',7,'Capability',1, ...
 'HopCount',1,'Cost',10,'Path',7);
sections=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords({record}),900);
p.Layer.receiveControl(struct('Type','ROUTING','Payload',struct('Bytes',sections{1})),3);
p.Clock.run(.1);rows=p.ofKind('automatic_update');
rows=rows(cellfun(@(r)numel(r.peers)==2,rows));assert(~isempty(rows));first=rows{end};p.ackOther(first.control_id);
p.Clock.run(1);p.Layer.controlResult(first.control,3,true,false,[3 5]);p.Clock.run(1);
n=numel(p.ofKind('automatic_update'));p.Layer.controlResult(first.control,5,false,true,[3 5]);p.Clock.run(1);
rows=p.ofKind('automatic_update');assert(numel(rows)==n+1);last=rows{end};
assert(isequal(last.peers,5)&&last.control_id~=first.control_id&&isequal(last.bytes,first.bytes)&&last.sequence==first.sequence);
for cycle=2:5,p.Clock.run(cycle);p.complete(last,false);rows=p.ofKind('automatic_update');last=rows{end};assert(isequal(last.peers,5));end
p.complete(last,true);s=p.Layer.stats();assert(s.ControlResidualRetries==5&&s.PendingControlMessages==0);
evidence=p.export('partial_ack_only_peer5_retried');
end
function evidence=inactivePruning(config)
% Test-only liveness override provides a public deactivation boundary. Pilot
% configuration and production defaults are not changed.
config.Nwk.Neighbor.FreshnessEnabled=true;config.Nwk.Neighbor.FreshnessTimeoutSeconds=.5;
config.Nwk.Neighbor.FreshnessPeriodSeconds=.1;
p=RetryProbe(config);p.activate();rows=p.ofKind('automatic_update');first=rows{1};p.ackOther(first.control_id);
p.Layer.start();p.Clock.run(.7);peers=p.Layer.neighborsSnapshot();assert(~peers([peers.PeerId]==3).Active);
n=numel(p.ofKind('automatic_update'));p.complete(first,false);assert(numel(p.ofKind('automatic_update'))==n);
s=p.Layer.stats();assert(s.NeighborDeactivations==1&&s.ControlResidualRetries==0);
evidence=p.export('inactive_owner_pruned');evidence.fixture_override=config.Nwk.Neighbor;
end
function evidence=backpressure(config)
p=RetryProbe(config);p.activate();rows=p.ofKind('automatic_update');first=rows{1};p.ackOther(first.control_id);
p.Clock.run(1);p.CanSend=false;p.complete(first,false);assert(numel(p.ofKind('automatic_update'))==1);
p.Clock.run(2);p.CanSend=true;p.Accept=false;p.Layer.wake();p.Clock.run(2);rows=p.ofKind('automatic_update');
assert(numel(rows)==2&&~rows{end}.accepted);blocked=rows{end};
p.Clock.run(3);p.Accept=true;p.Layer.wake();p.Clock.run(3);rows=p.ofKind('automatic_update');last=rows{end};
assert(numel(rows)==3&&last.accepted&&last.control_id==blocked.control_id&&isequal(last.bytes,first.bytes));
p.complete(last,true);p.Clock.run(10);assert(numel(p.ofKind('automatic_update'))==3);
s=p.Layer.stats();assert(s.PendingControlMessages==0&&s.ControlResidualRetries==1);evidence=p.export('blocked_residual_preserves_owner');
end
function evidence=staleRequestTimers(config)
p=RetryProbe(config);p.activate();p.ackOther(uint64([]));assert(p.Layer.startDiscovery(0,.001));p.Clock.run(.001);p.ackOther(uint64([]));
p.Clock.run(1);s=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords({struct('Operation','FLUSH')}),900);
p.Layer.receiveControl(struct('Type','ROUTING','Payload',struct('Bytes',s{1})),3);p.Clock.run(1);
p.Clock.run(2);assert(p.Layer.startDiscovery(0,.001));p.Clock.run(2.002);assert(numel(p.ofKind('request'))==2);
p.Clock.run(8.002);assert(numel(p.ofKind('request'))==2);p.Clock.run(10.002);assert(numel(p.ofKind('request'))==3);
p.Clock.run(20.002);stats=p.Layer.stats();assert(stats.SnapshotTimeouts==0);p.Clock.run(22.002);
stats=p.Layer.stats();assert(stats.SnapshotTimeouts==1);evidence=p.export('old_request_generation_cannot_mutate_new');
end
