function report=feedbackIdentityPreflight(root,folder)
%FEEDBACKIDENTITYPREFLIGHT Public Frames and strict wire-feedback comparison.
% No network, scheduler, HOP state machine or random provider is run.
if ~isfolder(folder), mkdir(folder); end
checks=struct('name',{},'passed',{},'details',{});
stop=jsondecode(fileread(fullfile(root,'ref','history','M_discovery_membership','first_divergence.json')));
native=ac.Fixture.readTx(fullfile(root,'ref','native','tx_signatures.csv'));
identity=double(stop.node)*4294967296+double(stop.ordinal);
rows=native(native.tx_id==identity,:);
assert(stop.node==8 && stop.ordinal==74 && height(rows)==1, ...
    'autocase:FeedbackIdentityPreflight','Unexpected captured M boundary.');
item=stop.actual.children; if iscell(item), item=item{1}; end
assert(item.kind==2 && item.hop_sequence==30 && item.wire_bytes==41, ...
    'autocase:FeedbackIdentityPreflight','Unexpected captured M feedback fields.');
radio=radioFor(stop.actual,'DACK',logical(item.has_ack_window));
child=csr.hop.Frames.acknowledgment(item.hop_source,item.hop_destination, ...
    uint16(item.hop_sequence),bitmap(item.ack_bitmap_hex),bitmap(item.dack_bitmap_hex),radio);
frame=csr.hop.Frames.aggregate({child},radio.Preamble);
frame.ReservationSlot=stop.actual.reservation_slot;
[old,failures]=ac.DiscoveryTxSignature.compare(frame,rows);
assert(isequal(failures,{'child1.kind'}) && old.children{1}.kind==2, ...
    'autocase:FeedbackIdentityPreflight','Public Frames did not reproduce the actual M mismatch.');
[actual,failures]=ac.FeedbackTxSignature.compare(frame,rows);
assert(isempty(failures),'autocase:FeedbackIdentityPreflight','Captured M feedback still fails.');
projection=actual.children{1}.feedback_kind_projection;
assert(strcmp(projection.logical_kind,'DACK') && projection.logical_kind_code==2 && ...
    projection.projected_outer_kind==1 && projection.native_outer_kind==1 && ...
    projection.native_is_ack==1 && projection.native_is_dack==1 && ...
    strcmp(projection.policy,'native_mac_ack_type_precedence') && ~isempty(projection.reason), ...
    'autocase:FeedbackIdentityPreflight','Projection did not preserve explicit logical and native roles.');
checks(end+1)=checked('actual_M_frame_reproduced_then_projected_with_both_flags',projection);

% Each fixture child is checked in a one-child envelope. Only aggregate
% count/size/index are adapted; all native child fields and radio values stay.
feedback=native(native.is_ack==1,:);
assert(height(feedback)==1104 && sum(feedback.is_dack==1)==21, ...
    'autocase:FeedbackIdentityPreflight','Unexpected frozen feedback fixture population.');
for k=1:height(feedback)
    expected=singleChild(feedback(k,:));
    supplied=fromNative(expected);
    [value,failures]=ac.FeedbackTxSignature.compare(supplied,expected);
    assert(isempty(failures) && value.children{1}.is_ack==1 && ...
        value.children{1}.is_dack==expected.is_dack, ...
        'autocase:FeedbackIdentityPreflight','Feedback fixture row %d did not match.',k);
end
% Source-supported combinations absent from the captured row population:
% feedback role is independent of ACK-window presence and stored DACK bits.
expected=singleChild(feedback(find(feedback.has_ack_window==0,1),:));
expected.is_dack=1; expected.flags=double(bitor(uint16(expected.flags),uint16(4)));
[value,failures]=ac.FeedbackTxSignature.compare(fromNative(expected),expected);
assert(isempty(failures) && value.children{1}.is_dack==1 && value.children{1}.has_ack_window==0, ...
    'autocase:FeedbackIdentityPreflight','DACK role incorrectly requires a feedback window.');
expected=rows; expected.is_dack=0;
expected.flags=double(bitand(uint16(expected.flags),uint16(251)));
[value,failures]=ac.FeedbackTxSignature.compare(fromNative(expected),expected);
assert(isempty(failures) && value.children{1}.is_dack==0 && ...
    strcmp(value.children{1}.dack_bitmap_hex,'0000000000000001'), ...
    'autocase:FeedbackIdentityPreflight','Retained DACK bits incorrectly determine an ACK frame role.');
checks(end+1)=checked('all_native_feedback_children_match_public_frame_constructors', ...
    struct('children',height(feedback),'plain_ack',sum(feedback.is_dack==0), ...
    'dack_flagged',sum(feedback.is_dack==1),'single_child_scaffold',true, ...
    'additional_source_supported_synthetic_cases',{{'nonwindow_DACK','window_ACK_retaining_nonzero_DACK_bitmap'}}));

for name={'is_ack','is_dack','flags'}
    changed=removevars(rows,name{1});
    mustFail(frame,changed,'child1.feedback_flag_schema');
end
for flagValue=[NaN 1.5 256]
    changed=rows; changed.flags=flagValue;
    mustFail(frame,changed,'child1.feedback_flags');
end
for name={'is_ack','is_dack'}
    changed=rows; changed.(name{1})=0;
    mustFail(frame,changed,['child1.' name{1}]);
    changed=rows; changed.(name{1})=NaN;
    mustFail(frame,changed,['child1.' name{1}]);
end
names={'ackable','is_ack','is_dack','has_ack_window'};
for k=1:4
    changed=rows; changed.flags=double(bitxor(uint16(changed.flags),bitshift(uint16(1),k-1)));
    mustFail(frame,changed,['child1.flag_' names{k}]);
end
checks(end+1)=checked('native_flag_schema_values_and_encoded_bits_remain_strict',struct('negative_cases',14));

changed=frame; changed.Segments{1}.AckBitmap=bitxor(child.AckBitmap,bitshift(uint64(1),63));
mustFail(changed,rows,'child1.ack_bitmap_hex');
changed=frame; changed.Segments{1}.DackBitmap=bitxor(child.DackBitmap,bitshift(uint64(1),63));
mustFail(changed,rows,'child1.dack_bitmap_hex');
checks(end+1)=checked('both_full_width_feedback_bitmaps_remain_strict',struct('negative_cases',2,'mutated_bit',63));

changed=frame; changed.Segments{1}.Sequence=uint16(31); mustFail(changed,rows,'child1.hop_sequence');
changed=frame; changed.Segments{1}.SourceId=5; mustFail(changed,rows,'child1.hop_source');
changed=frame; changed.Segments{1}.DestinationId=4; mustFail(changed,rows,'child1.hop_destination');
checks(end+1)=checked('feedback_sequence_and_both_addresses_remain_strict',struct('negative_cases',3));

changed=frame; changed.Segments{1}.WirePayloadBytes=42; changed.WirePayloadBytes=42;
mustFail(changed,rows,'parent.total_wire_bytes'); mustFail(changed,rows,'child1.wire_bytes');
changed=frame; changed.Segments{1}.Dscp=0; mustFail(changed,rows,'child1.dscp');
changed=frame; changed.Segments{1}.AckRequired=true;
mustFail(changed,rows,'child1.ackable'); mustFail(changed,rows,'child1.flag_ackable');
changed=frame; changed.Segments{1}.HasAckWindow=false;
mustFail(changed,rows,'child1.has_ack_window'); mustFail(changed,rows,'child1.flag_has_ack_window');
checks(end+1)=checked('feedback_size_dscp_reliability_and_window_remain_strict',struct('negative_cases',4));

changed=frame; changed.Segments{1}.Kind='ACK';
mustFail(changed,rows,'child1.is_dack'); mustFail(changed,rows,'child1.flag_is_dack');
changed=rows; changed.kind=2; mustFail(frame,changed,'child1.kind');
checks(end+1)=checked('plain_ack_and_native_outer_dack_cannot_masquerade', ...
    struct('negative_cases',2,'bitmaps_do_not_define_feedback_role',true));

control=struct('Id',uint64(1),'Type','KEY_REQUEST','Payload',struct(),'WirePayloadBytes',41);
radio=radioFor(stop.actual,'ACK',true); radio.AckRequired=true;
other=csr.hop.Frames.control(control,8,7,uint16(30),radio);
other=csr.hop.Frames.aggregate({other},radio.Preamble); other.ReservationSlot=frame.ReservationSlot;
[value,failures]=ac.FeedbackTxSignature.compare(other,rows);
assert(any(strcmp(failures,'child1.kind')) && ...
    ~isfield(value.children{1},'feedback_kind_projection'), ...
    'autocase:FeedbackIdentityPreflight','Reliable control received feedback projection.');
checks(end+1)=checked('reliable_control_kind_is_not_projected',struct('expected_failure','child1.kind'));

report=struct('schema','csr-feedback-identity-preflight-v1','passed',all([checks.passed]), ...
    'checks',checks,'network_simulation_executed',false,'scheduled_events',0,'random_variates_requested',0, ...
    'captured_native_tx_identity',identity,'native_feedback_children',height(feedback), ...
    'scope','Actual M boundary and all native feedback children via public Frames; strict comparator mutation checks', ...
    'limitations','The fixture sweep isolates each native child. No new transport run, HOP completion test or post-stop network parity claim.');
ac.writeJson(fullfile(folder,'feedback_identity_preflight.json'),report);
end

function radio=radioFor(parent,kind,hasWindow)
preamble='short'; if parent.preamble==1, preamble='long'; end
radio=struct('RateKeyKbps',parent.rate_kbps,'TxPowerDbm',parent.tx_power_dbm, ...
    'Preamble',preamble,'EnvelopeProfile','bare','Kind',kind,'HasAckWindow',hasWindow);
end
function row=singleChild(row)
row.child_count=1; row.total_wire_bytes=row.wire_bytes; row.child_index=0;
end
function frame=fromNative(row)
kind='ACK'; if row.is_dack==1, kind='DACK'; end
radio=radioFor(table2struct(row),kind,logical(row.has_ack_window));
child=csr.hop.Frames.acknowledgment(row.hop_source,row.hop_destination,uint16(row.hop_sequence), ...
    bitmap(row.ack_bitmap_hex),bitmap(row.dack_bitmap_hex),radio);
frame=csr.hop.Frames.aggregate({child},radio.Preamble); frame.ReservationSlot=row.reservation_slot;
end
function value=bitmap(text)
text=char(text);
assert(numel(text)==16,'autocase:FeedbackIdentityPreflight','Expected full-width bitmap hex.');
value=bitor(bitshift(uint64(hex2dec(text(1:8))),32),uint64(hex2dec(text(9:16))));
end
function mustFail(frame,rows,name)
[~,failures]=ac.FeedbackTxSignature.compare(frame,rows);
assert(any(strcmp(failures,name)),'autocase:FeedbackIdentityPreflight','Expected strict mismatch: %s.',name);
end
function value=checked(name,details)
value=struct('name',name,'passed',true,'details',details);
end
