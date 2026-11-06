function report=run_node7_checks(mode)
% Public component tests. Synthetic single-control fixture, not full replay.
if nargin<1,mode='candidate';end
assert(strcmp(mode,'candidate'),'Published tests run the repaired candidate only.');
root=fileparts(mfilename('fullpath'));candidate=fileparts(root);
restoredefaultpath;addpath(root,candidate,fullfile(candidate,'model'),'-begin');rehash;
assert(startsWith(which('ac.DiscoveryMembershipNwk'),candidate));
folder=fullfile(root,'checks',mode,'run_node7_checks');if ~isfolder(folder),mkdir(folder);end
config=configure_case(131,900);
checks=struct('name',{},'passed',{},'details',{});
[s,streams,p,mac]=setup(config,folder);
cleanup=onCleanup(@()finish(streams)); %#ok<NASGU>
mac.start();s.run(222.297352442);assert(strcmp(mac.State,'Idle'));
assert(mac.enqueue(frame()));
assert(~mac.PreparationActive && streams.Count==0);
if strcmp(mode,'baseline'),target=222.313;else,target=241.085;end
s.run(target-1e-7);assert(streams.Count==0 && ~mac.PreparationActive);
s.run(target+1e-9);assert(streams.Count==1 && mac.PreparationActive);
draws=p.select('random_request');assert(numel(draws)==1);
assert(round(draws{1}.time*1e9)==round(target*1e9));
checks(end+1)=pass('first_draw_boundary',struct('actual_time',draws{1}.time,'target',target));
idle=p.select('mac_boundary','idleRts_before');assert(numel(idle)==1);
assert(round(idle{1}.time*1e9)==round(target*1e9));
prep=p.select('mac_boundary','prepare_before');assert(numel(prep)==1);
assert(round(prep{1}.time*1e9)==round(target*1e9));
checks(end+1)=pass('draw_owned_by_idle_rts',struct('idle_rts',idle{1},'prepare',prep{1}));
before=p.select('mac_boundary','sleep_before');after=p.select('mac_boundary','sleep_after');
selected=find(cellfun(@(r) round(r.time*1e9)>=222308900000,before));
expected=1;if strcmp(mode,'candidate'),expected=20;end
assert(numel(selected)==expected);
for j=1:numel(selected)
    k=selected(j);b=before{k};a=after{k};
    assert(b.details.WakeEvent==a.details.WakeEvent && a.details.WakeEvent~=0);
    assert(b.details.SlotEvent~=0 && a.details.SlotEvent==0);
    assert(b.details.HoldoffEvent~=0 && a.details.HoldoffEvent==0);
    assert(~a.details.PreparationActive && strcmp(a.details.State,'Idle'));
    if j<expected,assert(a.details.IdleRtsEvent==0);else,assert(a.details.IdleRtsEvent~=0);end
    assertCancelled(p,b.details.SlotEvent);assertCancelled(p,b.details.HoldoffEvent);
end
checks(end+1)=pass('sleep_cancels_relative_timers_preserves_periodic_owner',struct('sleep_count',expected));
last=selected(end);oldId=before{last}.details.SlotEvent;newId=after{last}.details.IdleRtsEvent;
scheduled=p.select('scheduler_schedule');fired=p.select('scheduler_fire');
old=event(scheduled,oldId);fresh=event(scheduled,newId);
assert(round(old.details.DeadlineSeconds*1e9)==round(fresh.details.DeadlineSeconds*1e9));
assert(oldId~=newId && ~hasEvent(fired,oldId) && hasEvent(fired,newId));
% This MAC has no pending-TX-wake field: scheduled callback census proves
% deferral creates no replacement wake. Only periodicWake rearms wakes.
wakes=scheduled(cellfun(@(r) contains(r.details.Callback,'periodicWake'),scheduled));
cycles=p.select('mac_boundary','periodicWake_before');
assert(numel(wakes)==numel(cycles));
checks(end+1)=pass('same_deadline_old_slot_canceled_new_idle_rts_fires', ...
    struct('old_slot',old,'new_idle_rts',fresh,'periodic_wake_schedules',numel(wakes)));
ac.writeJson(fullfile(folder,'ownership_trace.json'),p.Rows);
streams.close();ac.Trace.close();clear cleanup;
% No pending work: genuine periodic wake/sleep remains autonomous and draws
% no MAC randomness, irrespective of numerical side of the awake boundary.
emptyFolder=fullfile(folder,'empty');if ~isfolder(emptyFolder),mkdir(emptyFolder);end
[s,streams,p,mac]=setup(config,emptyFolder);cleanup=onCleanup(@()finish(streams)); %#ok<NASGU>
mac.start();s.run(241.081);
assert(streams.Count==0 && mac.PendingCount==0 && ~mac.PreparationActive && strcmp(mac.State,'Idle'));
assert(numel(p.select('mac_boundary','periodicWake_before'))==21);
assert(isempty(p.select('mac_boundary','idleRts_before')));
checks(end+1)=pass('empty_queue_genuine_periodic_wake',struct('draws',streams.Count,'state',mac.State));
if strcmp(mode,'candidate')
    cycle=0.988;window=0.0011+0.0078;
    n1=222308900000;n2=241080900000;
    assert(ac.NativePeriodicWake.next(n1,cycle,window)==n1/1e9);
    assert(ac.NativePeriodicWake.next(n2,cycle,window)==242.06);
    for ns=[n1 n2]
        assert(ac.NativePeriodicWake.next(ns-1,cycle,window)==(ns-1)/1e9);
        assert(ac.NativePeriodicWake.next(ns+1,cycle,window)>(ns+1)/1e9);
    end
    assert(ac.NativePeriodicWake.next(1000000,cycle,window)==cycle);
    checks(end+1)=pass('awake_expiry_both_binary_sides_and_adjacent_nanoseconds',struct('first_ns',n1,'release_ns',n2));
    native=readtable(fullfile(root,'arithmetic_probe.csv'));
    [native.Nanoseconds,native.NativeFmod]=native_boundary_fixture();
    native.Projected=native.Nanoseconds/1e9;
    for k=1:height(native)
        assert(ac.NativePeriodicWake.positiveFmod(native.Projected(k),cycle)==native.NativeFmod(k));
        inside=k<20;
        next=ac.NativePeriodicWake.next(native.Nanoseconds(k),cycle,window);
        assert((next==native.Projected(k))==inside);
        slot=(floor(native.Nanoseconds(k)/13000000)+1)*13000000/1e9;
        assert((abs(next-slot)<=.013/2)==inside);
    end
    ext=readtable(fullfile(root,'extended_arithmetic.csv'));
    for k=1:height(ext)
        assert(ac.NativePeriodicWake.positiveFmod(ext.Projected(k),cycle)==ext.ExpectedFmod(k));
    end
    checks(end+1)=pass('exact_native20_and_extended87_fmod',struct('native_rows',height(native),'extension_rows',height(ext)));
end
report=struct('passed',true,'mode',mode,'checks',checks, ...
    'scope','Synthetic public MAC fixture; native 433-event prefix and slot9 are strict replay assertions.');
ac.writeJson(fullfile(folder,'node7_checks.json'),report);
finish(streams);clear cleanup;
end
function [s,streams,p,mac]=setup(config,folder)
s=csr.sim.EventScheduler(10000);streams=ac.Streams(config.Seed,s,'natural','',folder);
p=Node7WakeProbe();ac.Trace.holder('set',p);
cb=struct('Transmit',@(f,d)p.transmit(f,d),'SetReceiverState',@(v)p.state(v), ...
    'SetReceiverStateMacOnly',@(v)p.state(v),'ReceiverState',@()p.State,'HasSync',@()false);
mac=ac.TerminalMac(7,s,streams,config,cb,ac.ReceiverTimer());
mac.setActiveNodes(2,3);
end
function out=pass(name,details),out=struct('name',name,'passed',true,'details',details);end
function finish(streams),streams.close();ac.Trace.close();end
function assertCancelled(p,id)
rows=p.select('scheduler_cancel');r=event(rows,id);assert(r.details.WasPending);
end
function tf=hasEvent(rows,id),tf=any(cellfun(@(r) r.details.EventId==id,rows));end
function r=event(rows,id)
ix=find(cellfun(@(r) r.details.EventId==id,rows));assert(numel(ix)==1);r=rows{ix};
end
function f=frame()
c=struct('Id',uint64(1),'Type','DISCOVER','Payload',struct('Subtype','broadcast','Sequence',1,'ActivePeers',[]),'WirePayloadBytes',19);
f=csr.hop.Frames.control(c,7,16777215,uint16(1), ...
    struct('RateKeyKbps',8,'TxPowerDbm',33,'Preamble','long','EnvelopeProfile','bare','AckRequired',false));
f.Id=uint64(1);
end
