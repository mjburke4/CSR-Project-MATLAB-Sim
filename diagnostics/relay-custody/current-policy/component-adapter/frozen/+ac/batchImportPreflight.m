function output=batchImportPreflight(fixture,seed,stopSeconds,folder)
%BATCHIMPORTPREFLIGHT Validate the actual per-case fixture, including controls.
% No network events are scheduled. Absent packet kinds are recorded explicitly.
if ~isfolder(folder), mkdir(folder); end
rows=ac.Fixture.readRandom(fullfile(fixture,'random_draws.csv'));
tx=ac.Fixture.readTx(fullfile(fixture,'tx_signatures.csv'));
receipt=jsondecode(fileread(fullfile(fixture,'receipt.json')));
assert(strcmp(receipt.schema,'csr-autonomous-passive-native-capture-v1') && ...
    strcmp(receipt.status,'verified_exact_native_prefix') && receipt.seed==seed && ...
    receipt.stop_ns_exclusive==stopSeconds*1e9 && receipt.canonical_rows>0 && ...
    numel(receipt.canonical_fields)==30 && ...
    strcmp(receipt.source_pin,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b') && ...
    strcmp(receipt.engine_pin,'6b5cd24ea80713ce16d88575869aedd6f432bdae'), ...
    'paritybatch:NativeFidelity','Wrong or unverified native capture for seed %g.',seed);
assert(height(rows)==receipt.random_rows && height(tx)==receipt.tx_children && ...
    numel(unique(tx.tx_id))==receipt.tx_count && ...
    all(rows.time_ns>=0 & rows.time_ns<stopSeconds*1e9) && ...
    all(tx.time_ns>=0 & tx.time_ns<stopSeconds*1e9), ...
    'paritybatch:NativePopulation','Native fixture population or endpoint does not match its receipt.');
required={'flags','is_ack','is_dack','destination_type','security_count'};
assert(all(ismember(required,tx.Properties.VariableNames)), ...
    'paritybatch:ControlSchema','Native control comparison fields are absent.');
assert(all(ismember(tx.kind,[0 1 2 4 5 6 7 8 9])), ...
    'paritybatch:ControlKind','An unreviewed packet kind occurs in this native fixture.');
assert(all(isfinite(tx.flags) & tx.flags==floor(tx.flags) & tx.flags>=0 & tx.flags<=255) && ...
    all(isfinite(tx.destination_type)) && ...
    all(isfinite(tx.security_count(ismember(tx.kind,[4 5 6 8 9])))), ...
    'paritybatch:ControlSchema','Invalid native flags, destination type, or protection count.');
identities=unique(tx.tx_id);
for k=1:numel(identities)
    part=tx(tx.tx_id==identities(k),:);
    assert(all(part.child_count==height(part)) && ...
        isequal(reshape(part.child_index,1,[]),0:height(part)-1) && ...
        all(part.tx_id==part.source*4294967296+part.source_tx_ordinal) && ...
        all(part.time_ns==part.time_ns(1)) && all(part.source==part.source(1)) && ...
        all(part.total_wire_bytes==sum(part.wire_bytes)), ...
        'paritybatch:TxPopulation','Native TX child grouping is inconsistent.');
end
% The earliest MAC request is taken from this seed, not the seed-132 value.
firstIndex=find(rows.purpose=="mac_slot",1);
assert(~isempty(firstIndex),'paritybatch:FirstMac','Native capture contains no MAC sample.');
first=rows(firstIndex,:);
assert(first.ordinal==1,'paritybatch:FirstMac','First MAC request must start at ordinal one.');
scheduler=csr.sim.EventScheduler(10);
streams=ac.FeedbackStreams(seed,scheduler,'native',fullfile(fixture,'random_draws.csv'),folder);
closeStreams=onCleanup(@()streams.close()); %#ok<NASGU>
executed=scheduler.run(first.time_ns/1e9);
assert(executed==0 && scheduler.PendingCount==0,'paritybatch:ImportEvents','Import preflight scheduled an event.');
names={'low','high','active_nodes','reported_nodes','reservation_counter','reservation_slot','profile','state'};
request=struct();
for k=1:numel(names)
    value=first.(names{k}); if isstring(value), value=char(value); end
    request.(names{k})=value;
end
value=streams.take(first.node,'mac_slot',request);
assert(value==first.value,'paritybatch:FirstMac','The seed-specific first MAC sample changed.');
negative=struct('population',{},'field',{},'passed',{});
for purpose=["mac_slot","sync_threshold","phy_binomial"]
    part=rows(rows.purpose==purpose,:);
    if isempty(part), continue; end
    switch purpose
        case "mac_slot", names={'state','low','high'};
        case "sync_threshold", names={'mean','variance','tx_id'};
        case "phy_binomial", names={'component','bits','probability','interval_ordinal'};
    end
    for k=1:numel(names)
        bad=part(1,:); bad=eraseRequired(bad,names{k});
        expectRequiredFailure(@()ac.Fixture.validateRandom(bad),names{k});
        negative(end+1)=struct('population',char(purpose),'field',names{k},'passed',true); %#ok<AGROW>
    end
end
% Mutation tests cover every observed control subtype. A seed without DATA
% cannot claim DATA coverage merely because validation of an empty table succeeds.
coverage=struct('kind',{},'subtype',{},'rows',{},'required_fields_checked',{});
for kind=[0 1 2 4 5 6 7 8 9]
    part=tx(tx.kind==kind,:);
    subtypes="";
    if kind==4, subtypes=unique(part.discover_subtype); end
    if kind==5, subtypes=unique(part.check_subtype); end
    if isempty(part)
        coverage(end+1)=struct('kind',kind,'subtype','not_observed','rows',0,'required_fields_checked',{{}}); %#ok<AGROW>
        continue;
    end
    for subtype=reshape(subtypes,1,[])
        selected=part;
        if kind==4, selected=part(part.discover_subtype==subtype,:); end
        if kind==5, selected=part(part.check_subtype==subtype,:); end
        names={'hop_source','hop_destination','hop_sequence','kind','wire_bytes','ackable','has_ack_window'};
        switch kind
            case 0, names=[names {'network_source','network_destination','network_dscp','application_bytes','app_attempt_index','app_flow_index','app_generated_time_ns'}];
            case 4
                assert(ismember(subtype,["broadcast","chirp"]),'paritybatch:DiscoverySubtype','Unknown discovery subtype.');
                names=[names {'discover_subtype','discover_sequence'}];
            case 5
                assert(ismember(subtype,["discovery","overheard","message","no_path"]), ...
                    'paritybatch:CheckSubtype','Unknown neighbor-check subtype.');
                names=[names {'check_subtype','check_sequence'}];
                if subtype=="discovery", names=[names {'check_active'}]; end
                if subtype=="no_path", names=[names {'check_target'}]; end
            case 6, names=[names {'routing_section_hex'}];
            case 7, names=[names {'snmp_command','snmp_source','snmp_destination','snmp_value'}];
        end
        for k=1:numel(names)
            bad=eraseRequired(selected(1,:),names{k});
            expectRequiredFailure(@()ac.Fixture.validateTx(bad),names{k});
            negative(end+1)=struct('population',sprintf('kind_%g_%s',kind,char(subtype)), ...
                'field',names{k},'passed',true); %#ok<AGROW>
        end
        coverage(end+1)=struct('kind',kind,'subtype',char(subtype),'rows',height(selected), ...
            'required_fields_checked',{names}); %#ok<AGROW>
    end
end
output=struct('schema','csr-batch-native-import-v1','passed',true,'seed',seed, ...
    'stop_seconds_exclusive',stopSeconds,'native_random_rows',height(rows), ...
    'native_tx_count',numel(unique(tx.tx_id)),'native_tx_children',height(tx), ...
    'first_mac_node',first.node,'first_mac_time_ns',first.time_ns,'first_mac_value',value, ...
    'control_coverage',coverage,'malformed_required_fields_rejected',negative, ...
    'network_simulation_executed',false,'scheduled_events',0,'executed_events',executed, ...
    'receiver_state_or_feedback_replayed',false);
ac.writeJson(fullfile(folder,'preflight.json'),output);
end
function row=eraseRequired(row,name)
if isstring(row.(name)), row.(name)=""; else, row.(name)=NaN; end
end
function expectRequiredFailure(callback,name)
failed=false;
try, callback(); catch caught
    assert(strcmp(caught.identifier,'autocase:FixtureRequired'), ...
        'paritybatch:WrongRejection','Unexpected rejection for %s: %s.',name,caught.identifier);
    failed=true;
end
assert(failed,'paritybatch:RequiredAccepted','Malformed required field %s was accepted.',name);
end
