function report=discoveryIdentityPreflight(root,folder)
%DISCOVERYIDENTITYPREFLIGHT Rebuild the observed rejected aggregate via Frames.
% Comparator-only checks; no simulation, scheduler or random provider runs.
if ~isfolder(folder), mkdir(folder); end
checks=struct('name',{},'passed',{},'details',{});
stop=jsondecode(fileread(fullfile(root,'ref','history','I_control_wire','first_divergence.json')));
native=ac.Fixture.readTx(fullfile(root,'ref','native','tx_signatures.csv'));
identity=double(stop.node)*4294967296+double(stop.ordinal);
rows=native(native.tx_id==identity,:);
assert(height(rows)==3 && stop.node==3 && stop.ordinal==17, ...
    'autocase:DiscoveryIdentityPreflight','Unexpected captured I boundary.');
frame=rebuild(stop.actual);
[old,failures]=ac.TxSignature.compare(frame,rows);
assert(isequal(failures,{'child3.hop_sequence'}) && old.child_count==3 && old.total_wire_bytes==109, ...
    'autocase:DiscoveryIdentityPreflight','Public Frames reconstruction did not reproduce the actual I mismatch.');
[actual,failures]=ac.DiscoveryTxSignature.compare(frame,rows);
assert(isempty(failures),'autocase:DiscoveryIdentityPreflight','Declared trace identity still blocks the observed frame.');
identityRecord=actual.children{3}.discovery_outer_sequence_identity;
assert(identityRecord.actual==1 && identityRecord.native==4 && ...
    strcmp(identityRecord.policy,'trace_only_broadcast_discover_identifier') && ~isempty(identityRecord.reason) && ...
    actual.children{3}.hop_sequence==1 && actual.children{3}.discover_sequence==1, ...
    'autocase:DiscoveryIdentityPreflight','Normalization omitted its raw values, reason or semantic discovery sequence.');
checks(end+1)=checked('captured_I_frame_passes_with_explicit_raw_identity_record',identityRecord);

changed=frame; changed.Segments{3}.Control.Payload.Sequence=2;
[~,failures]=ac.DiscoveryTxSignature.compare(changed,rows);
mustContain(failures,'child3.discover_sequence');
checks(end+1)=checked('discovery_payload_sequence_remains_strict',struct('expected_failure','child3.discover_sequence'));

changed=frame; changed.Segments{3}.WirePayloadBytes=20; changed.WirePayloadBytes=110;
[~,failures]=ac.DiscoveryTxSignature.compare(changed,rows);
mustContain(failures,'parent.total_wire_bytes'); mustContain(failures,'child3.wire_bytes');
checks(end+1)=checked('child_and_aggregate_wire_sizes_remain_strict',struct('changed_child_bytes',20,'changed_total_bytes',110));

% Each actual-side eligibility gate must leave the outer sequence strict.
changed=frame; changed.Segments{3}.DestinationId=1; changed.Segments{3}.DestinationIds=1;
mustRemainStrict(changed,rows);
changed=frame; changed.Segments{3}.AckRequired=true; mustRemainStrict(changed,rows);
changed=frame; changed.Segments{3}.HasAckWindow=true; mustRemainStrict(changed,rows);
changed=frame; changed.Segments{3}.DestinationIds=[16777215 1];
changed.Segments{3}.HopSequences=uint16([1 1]); mustRemainStrict(changed,rows);
checks(end+1)=checked('actual_address_ack_window_and_group_eligibility_are_required',struct('negative_cases',4));

% Mutating native expectations proves eligibility is checked on both sides.
changedRows=rows; changedRows.kind(3)=8; mustRemainStrict(frame,changedRows);
changedRows=rows; changedRows.hop_destination(3)=1; mustRemainStrict(frame,changedRows);
changedRows=rows; changedRows.ackable(3)=1; mustRemainStrict(frame,changedRows);
changedRows=rows; changedRows.has_ack_window(3)=1; mustRemainStrict(frame,changedRows);
changedRows=rows; changedRows.discover_subtype(3)="chirp"; mustRemainStrict(frame,changedRows);
changedRows=rows; changedRows.destination_type(3)=0; mustRemainStrict(frame,changedRows);
changedRows=rows; changedRows.flags(3)=double(bitand(uint16(changedRows.flags(3)),uint16(127)));
mustRemainStrict(frame,changedRows);
changedRows=rows; changedRows.security_count(3)=NaN; mustRemainStrict(frame,changedRows);
checks(end+1)=checked('native_kind_address_ack_window_subtype_and_protection_are_required',struct('negative_cases',8));

changed=frame; changed.Segments{2}.Sequence=uint16(8);
[~,failures]=ac.DiscoveryTxSignature.compare(changed,rows); mustContain(failures,'child2.hop_sequence');
changed=frame; changed.Segments{1}.Sequence=uint16(8);
[~,failures]=ac.DiscoveryTxSignature.compare(changed,rows); mustContain(failures,'child1.hop_sequence');
checks(end+1)=checked('reliable_routing_and_ack_outer_sequences_remain_strict',struct('negative_cases',2));

% Even matching chirp subtype is outside this narrowly proven exception.
changed=frame; changed.Segments{3}.Control.Payload.Subtype='chirp';
changedRows=rows; changedRows.discover_subtype(3)="chirp"; mustRemainStrict(changed,changedRows);
changed=frame; changed.Segments{3}.Control.Type='KEY_REQUEST'; mustRemainStrict(changed,rows);
checks(end+1)=checked('uncovered_chirp_and_other_control_kinds_remain_strict',struct('negative_cases',2));

report=struct('schema','csr-discovery-identity-preflight-v1','passed',all([checks.passed]), ...
    'checks',checks,'network_simulation_executed',false,'scheduled_events',0,'random_variates_requested',0, ...
    'captured_native_tx_identity',identity, ...
    'scope','Public Frames reconstruction of actual I stop plus comparator mutation checks; no network behavior change or full-parity claim');
ac.writeJson(fullfile(folder,'discovery_identity_preflight.json'),report);
end

function frame=rebuild(parent)
items=parent.children; if ~iscell(items), items=num2cell(items); end
children=cell(size(items));
preamble='short'; if parent.preamble==1, preamble='long'; end
for k=1:numel(items)
    item=items{k};
    radio=struct('RateKeyKbps',parent.rate_kbps,'TxPowerDbm',parent.tx_power_dbm, ...
        'Preamble',preamble,'EnvelopeProfile','bare','AckRequired',logical(item.ackable), ...
        'HasAckWindow',logical(item.has_ack_window));
    if item.kind==1
        children{k}=csr.hop.Frames.acknowledgment(item.hop_source,item.hop_destination, ...
            uint16(item.hop_sequence),uint64(0),uint64(0),radio);
    else
        control=struct('Id',uint64(k),'Type',item.control_type,'Payload',item.control_payload, ...
            'WirePayloadBytes',item.wire_bytes);
        children{k}=csr.hop.Frames.control(control,item.hop_source,item.hop_destination, ...
            uint16(item.hop_sequence),radio);
    end
end
frame=csr.hop.Frames.aggregate(children,preamble); frame.ReservationSlot=parent.reservation_slot;
end
function mustRemainStrict(frame,rows)
[actual,failures]=ac.DiscoveryTxSignature.compare(frame,rows);
mustContain(failures,'child3.hop_sequence');
assert(~isfield(actual.children{3},'discovery_outer_sequence_identity'), ...
    'autocase:DiscoveryIdentityPreflight','An ineligible frame received the trace-identity exception.');
end
function mustContain(failures,name)
assert(any(strcmp(failures,name)),'autocase:DiscoveryIdentityPreflight','Expected strict field mismatch: %s.',name);
end
function value=checked(name,details)
value=struct('name',name,'passed',true,'details',details);
end
