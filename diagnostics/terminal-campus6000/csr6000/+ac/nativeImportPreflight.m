function output=nativeImportPreflight(root,folder)
%NATIVEIMPORTPREFLIGHT Small regression for typed input, with no network run.
if ~isfolder(folder), mkdir(folder); end
path=fullfile(root,'ref','native','random_draws.csv');
rows=ac.Fixture.readRandom(path);
tx=ac.Fixture.readTx(fullfile(root,'ref','native','tx_signatures.csv'));
first=rows(find(rows.purpose=="mac_slot",1),:);
assert(first.node==1 && first.ordinal==1 && first.time_ns==10010000000 && ...
    first.value==11 && first.component=="",'autocase:PreflightReference', ...
    'The original first native MAC request is not present.');
scheduler=csr.sim.EventScheduler(10);
streams=ac.Streams(132,scheduler,'native',path,folder);
closeStreams=onCleanup(@()streams.close()); %#ok<NASGU>
% Advancing an empty scheduler creates or executes no protocol events.
executed=scheduler.run(first.time_ns/1e9);
assert(executed==0 && scheduler.PendingCount==0,'autocase:PreflightEvents', ...
    'The import preflight must not schedule simulator callbacks.');
names={'low','high','active_nodes','reported_nodes','reservation_counter','reservation_slot','profile','state'};
request=struct();
for k=1:numel(names)
    value=first.(names{k}); if isstring(value), value=char(value); end
    request.(names{k})=value;
end
value=streams.take(first.node,'mac_slot',request);
assert(value==11,'autocase:PreflightDraw','The first native MAC sample was not returned.');
% The accepted empty component must not weaken a required PHY component.
phy=rows(find(rows.purpose=="phy_binomial",1),:); phy.component="";
expectRequiredFailure(@()ac.Fixture.validateRandom(phy),'empty_phy_component');
mac=first; mac.state="";
expectRequiredFailure(@()ac.Fixture.validateRandom(mac),'empty_mac_state');
sync=rows(find(rows.purpose=="sync_threshold",1),:); sync.mean=NaN;
expectRequiredFailure(@()ac.Fixture.validateRandom(sync),'missing_sync_mean');
routing=tx(find(tx.kind==6,1),:); routing.routing_section_hex="";
expectRequiredFailure(@()ac.Fixture.validateTx(routing),'empty_routing_section');
output=struct('schema','csr-native-import-regression-v1','passed',true, ...
    'native_random_rows',height(rows),'native_tx_children',height(tx), ...
    'first_mac_value',value,'legitimate_empty_mac_component_accepted',true, ...
    'invalid_required_fields_rejected',{{'empty_phy_component','empty_mac_state', ...
        'missing_sync_mean','empty_routing_section'}}, ...
    'scheduled_events',0,'executed_events',executed,'network_simulation_executed',false, ...
    'scope','CSV/runtime import regression only; no network parity claim');
ac.writeJson(fullfile(folder,'preflight.json'),output);
end
function expectRequiredFailure(callback,name)
failed=false;
try
    callback();
catch caught
    assert(strcmp(caught.identifier,'autocase:FixtureRequired'), ...
        'autocase:PreflightWrongFailure','Unexpected rejection for %s: %s.',name,caught.identifier);
    failed=true;
end
assert(failed,'autocase:PreflightMissingFailure','Malformed required field was accepted: %s.',name);
end
