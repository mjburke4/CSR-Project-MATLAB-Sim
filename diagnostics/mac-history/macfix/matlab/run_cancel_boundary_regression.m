function report = run_cancel_boundary_regression(root,outputDir)
%RUN_CANCEL_BOUNDARY_REGRESSION Exercise queue-cancellation boundary outcomes.
% Includes the no-match ACK shapes that stopped the first owner history run.
% No network simulation runs and no accepted production implementation changes.
if nargin<1 || isempty(root), root=fileparts(fileparts(mfilename('fullpath'))); end
if nargin<2 || isempty(outputDir), outputDir=fullfile(root,'out_cancel_boundary'); end
if ~isfolder(outputDir), mkdir(outputDir); end
names={'returned_node2_no_match','returned_node4_structured_no_match', ...
    'returned_node8_no_match','empty_queue','zero_bitmap','different_peer', ...
    'structured_matching_key','mixed_window_and_duplicate_copies', ...
    'sequence_wrap','bitmap_high_bit','ambiguous_key_rejects_atomically', ...
    'prepared_reservation_survives_cancellation'};
checks={@node2NoMatch,@node4NoMatch,@node8NoMatch,@emptyQueue, ...
    @zeroBitmap,@differentPeer,@structuredOnly,@mixedWindow,@sequenceWrap, ...
    @highBit,@ambiguousKey,@preparedReservation};
report=struct('test','MAC cancellation boundary regression','completed',true, ...
    'pass',false,'network_parity_claim',false,'runtime',version, ...
    'cases_total',numel(checks),'cases_passed',0,'cases',[], ...
    'output_directory',outputDir);
% Record the language-level shape on the owner's runtime without relying on
% it for correctness: the repaired implementation indexes by element count.
emptyUnique=unique([],'stable'); iterations=0;
for unused=emptyUnique %#ok<NASGU>
    iterations=iterations+1;
end
report.empty_unique_size=size(emptyUnique);
report.value_loop_empty_iterations=iterations;
rows=cell(1,numel(checks));
for k=1:numel(checks)
    row=struct('case',names{k},'pass',false,'error_identifier','','error_message','');
    try
        checks{k}(); row.pass=true; report.cases_passed=report.cases_passed+1;
    catch caught
        row.error_identifier=caught.identifier; row.error_message=caught.message;
    end
    rows{k}=row;
end
report.cases=rows; report.pass=report.cases_passed==report.cases_total;
file=fullfile(outputDir,'cancellation_regression_summary.json');
fid=fopen(file,'w'); assert(fid>=0,'mac_replay:Output','Cannot write %s.',file);
cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(report,'PrettyPrint',true));
end

function node2NoMatch()
mac=fixture(2); mac.enqueue(frame(26,4,5)); mac.enqueue(frame(27,4,6));
expectNoop(mac,4,4,uint64(1));
assert(mac.cancel(4,5)==1 && mac.cancel(4,6)==1 && mac.DataQueueCount==0);
end
function node4NoMatch()
mac=fixture(4);
a=frame(31,2,4); a=structured(a,[2]);
b=frame(32,2,5); b=structured(b,[2 5]);
mac.enqueue(a); mac.enqueue(b); expectNoop(mac,2,1,uint64(1));
assert(mac.cancel(2,4)==1 && mac.cancel(2,5)==1 && mac.DataQueueCount==0);
end
function node8NoMatch()
mac=fixture(8); key=frame(116,7,2); key.AckRequired=false;
key.Kind='CONTROL'; key.Control=struct('Type','KEY_REQUEST');
mac.enqueue(key); mac.enqueue(frame(118,7,3)); expectNoop(mac,7,1,uint64(1));
assert(mac.cancel(7,3)==1 && mac.DataQueueCount==1);
assert(mac.cancelControl(7,'KEY_REQUEST')==1 && mac.DataQueueCount==0);
end
function emptyQueue()
mac=fixture(2); expectNoop(mac,4,9,uint64(1));
end
function zeroBitmap()
mac=fixture(2); mac.enqueue(frame(1,4,9)); expectNoop(mac,4,9,uint64(0));
assert(mac.cancel(4,9)==1 && mac.DataQueueCount==0);
end
function differentPeer()
mac=fixture(2); mac.enqueue(frame(1,8,9)); expectNoop(mac,4,9,uint64(1));
assert(mac.cancel(8,9)==1 && mac.DataQueueCount==0);
end
function structuredOnly()
mac=fixture(2); mac.enqueue(structured(frame(1,4,9),[4 8]));
expectNoop(mac,4,9,uint64(1));
% The native boundary protects the group, while HOP's direct public cancel
% still cancels its primary key. The bridge must not change that API.
assert(mac.cancel(4,9)==1 && mac.DataQueueCount==0);
end
function mixedWindow()
mac=fixture(2);
mac.enqueue(frame(1,4,9)); mac.enqueue(frame(2,4,9)); mac.enqueue(frame(3,4,7));
mac.enqueue(structured(frame(4,4,8),[4 8])); mac.enqueue(frame(5,4,10));
mac.enqueue(frame(6,8,9)); mac.enqueue(frame(7,4,65481));
% Base 9 with bits 0 and 2 removes three copies at keys 9 and 7.
assert(mac.replayCancelWindow(4,9,uint64(5))==3 && mac.DataQueueCount==4);
assert(mac.Counters.Canceled==3);
assert(mac.cancel(4,9)==0 && mac.cancel(4,7)==0);
assert(mac.cancel(4,8)==1 && mac.cancel(4,10)==1 && mac.cancel(8,9)==1);
% Sequence 65481 has age 64, just outside the 64-bit bitmap.
assert(mac.cancel(4,65481)==1 && mac.DataQueueCount==0);
end
function sequenceWrap()
mac=fixture(2); mac.enqueue(frame(1,4,65535));
assert(mac.replayCancelWindow(4,0,uint64(2))==1 && mac.DataQueueCount==0);
end
function highBit()
mac=fixture(2); mac.enqueue(frame(1,4,37));
assert(mac.replayCancelWindow(4,100,bitshift(uint64(1),63))==1 && mac.DataQueueCount==0);
end
function ambiguousKey()
mac=fixture(2); mac.enqueue(frame(1,4,9));
mac.enqueue(structured(frame(2,4,9),[4 8]));
before=mac.snapshot(); rejected=false;
try
    mac.replayCancelWindow(4,9,uint64(1));
catch caught
    rejected=strcmp(caught.identifier,'mac_replay:AmbiguousCancellation');
end
assert(rejected && isequaln(before,mac.snapshot()), ...
    'Protected and ordinary copies sharing a key must reject before mutation.');
assert(mac.cancel(4,9)==2 && mac.DataQueueCount==0);
end
function preparedReservation()
[mac,scheduler]=fixture(2); mac.enqueue(frame(1,4,9));
scheduler.run(0.013);
assert(mac.PreparationActive && mac.ReservationCounter>=0);
before=[mac.ReservationSlot mac.ReservationCounter mac.PreparationActive];
expectNoop(mac,4,8,uint64(1));
assert(mac.replayCancelWindow(4,9,uint64(1))==1 && mac.DataQueueCount==0);
after=[mac.ReservationSlot mac.ReservationCounter mac.PreparationActive];
assert(isequal(before,after),'Cancellation must retain the live prepared opportunity.');
end
function expectNoop(mac,peer,base,bitmap)
before=mac.snapshot(); prepared=mac.PreparationActive;
assert(mac.replayCancelWindow(peer,base,bitmap)==0, ...
    'A window with no eligible queued key must remove zero frames.');
assert(isequaln(before,mac.snapshot()) && prepared==mac.PreparationActive, ...
    'A no-match window must leave queue, counters and reservation state unchanged.');
end
function [mac,scheduler]=fixture(node)
scheduler=mac_replay.Scheduler(100);
tape=table(node,1,0,31,0,'VariableNames',{'node','ordinal','min','max','draw'});
streams=csr.validation.ReplayStreams(tape,@()scheduler.Now,'cancel_regression');
config=csr.mac.Layer.defaults();
config.SlotProfile='hist-2014-next-tslot-modulo-probe';
config.ReservationSlotOverride=10;
mac=mac_replay.MacLayer(node,scheduler,streams,config,struct('Transmit',@unexpectedTransmit));
end
function value=frame(id,peer,sequence)
value=struct('Id',uint64(id),'Kind','DATA','DestinationId',peer,'Sequence',sequence, ...
    'Dscp',7,'AckRequired',true,'HasAckWindow',false);
end
function value=structured(value,peers)
value.Kind='CONTROL'; value.Control=struct('Type','ROUTING'); value.DestinationIds=peers;
end
function unexpectedTransmit(~,~)
error('mac_replay:BoundaryCheck','Cancellation regression unexpectedly transmitted.');
end
