function report=test_timer_storage(repairRoot,out,guard)
% Synthetic passive timing calls only; never starts a network scheduler.
assert(isa(guard,'function_handle'));guard();assert(~isfolder(out)&&~isfile(out));mkdir(out);addpath(fileparts(mfilename('fullpath')));
old=timer_LegacyTransport('nanoseconds',17);new=csr.sim.TransportTiming('nanoseconds',17);
assert(isequaln(old.snapshot(),new.snapshot()));
old.attach();new.attach();
for k=1:17
    guard();
    id=bitshift(uint64(1),53)+uint64(k);
    a=old.plan(double(k),1e-6,.01,.001,2,1,id);
    b=new.plan(double(k),1e-6,.01,.001,2,1,id);
    assert(isequaln(a,b));old.record({a});new.record({b});
end
a=old.snapshot();b=new.snapshot();assert(isequaln(a,b));assert(isequal(fieldnames(a),fieldnames(b)));
assert(isequaln(rmfield(a,'Records'),new.snapshot(false)));
assert(isequaln([new.tableRows(1,7);new.tableRows(8,17)],a.Records));
writetable(a.Records,fullfile(out,'legacy_transport.csv'));
new.exportCsv(fullfile(out,'typed_transport.csv'),7,@()guard());
assert(isequal(bytes(fullfile(out,'legacy_transport.csv')),bytes(fullfile(out,'typed_transport.csv'))));
old=timer_LegacyReceiver(9);new=ac.ReceiverTimer(9);
assert(isequaln(old.snapshot(),new.snapshot()));
for k=1:12
    guard();
    purpose=sprintf('purpose_%d,"quoted"\nnext',k);
    a=old.plan(double(k),28e-9,2,purpose);b=new.plan(double(k),28e-9,2,purpose);assert(isequaln(a,b));
end
a=old.snapshot();b=new.snapshot();assert(isequaln(a,b));assert(isequal(fieldnames(a),fieldnames(b)));
assert(a.Count==12&&a.Omitted==3&&height(a.Records)==9);
assert(isequaln(rmfield(a,'Records'),new.snapshot(false)));
assert(isequaln([new.tableRows(1,4);new.tableRows(5,9)],a.Records));
writetable(a.Records,fullfile(out,'legacy_receiver.csv'));
new.exportCsv(fullfile(out,'typed_receiver.csv'),4,@()guard());
assert(isequal(bytes(fullfile(out,'legacy_receiver.csv')),bytes(fullfile(out,'typed_receiver.csv'))));
report=struct('passed',true,'network_executed',false,'transport_rows',17,'receiver_retained',9, ...
    'receiver_omitted',3,'exact_default_snapshots',true,'exact_csv_bytes',true,'target_arithmetic_unchanged',true);
end
function v=bytes(path)
f=fopen(path,'rb');assert(f>=0);c=onCleanup(@()fclose(f));v=fread(f,Inf,'*uint8'); %#ok<NASGU>
end
