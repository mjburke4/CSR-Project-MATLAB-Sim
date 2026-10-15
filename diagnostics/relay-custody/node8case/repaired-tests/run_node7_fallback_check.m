function report=run_node7_fallback_check(mode)
% Public MAC regression for a deliberately non-nanosecond slot period.
% Invoke baseline and candidate in separate fresh MATLAB processes.
if nargin<1,mode='candidate';end
assert(strcmp(mode,'candidate'),'Published tests run the repaired candidate only.');
root=fileparts(mfilename('fullpath'));candidate=fileparts(root);
restoredefaultpath;addpath(root,candidate,fullfile(candidate,'model'),'-begin');rehash;
assert(startsWith(which('ac.DiscoveryMembershipNwk'),candidate));
folder=fullfile(root,'checks',mode,'run_node7_fallback_check');if ~isfolder(folder),mkdir(folder);end
config=configure_case(131,900);
config.Mac.SlotSeconds=0.0130000000001;
period=config.Mac.SlotSeconds;
assert(period~=round(period*1e9)/1e9);
s=csr.sim.EventScheduler(10000);streams=ac.Streams(config.Seed,s,'natural','',folder);
p=Node7WakeProbe();ac.Trace.holder('set',p);
cleanup=onCleanup(@()finish(streams)); %#ok<NASGU>
cb=struct('Transmit',@(f,d)p.transmit(f,d),'SetReceiverState',@(v)p.state(v), ...
    'SetReceiverStateMacOnly',@(v)p.state(v),'ReceiverState',@()p.State,'HasSync',@()false);
mac=ac.TerminalMac(7,s,streams,config,cb,ac.ReceiverTimer());mac.setActiveNodes(2,3);
mac.start();s.run(222.297352442);assert(strcmp(mac.State,'Idle'));
c=struct('Id',uint64(1),'Type','DISCOVER','Payload',struct('Subtype','broadcast','Sequence',1,'ActivePeers',[]),'WirePayloadBytes',19);
f=csr.hop.Frames.control(c,7,16777215,uint16(1), ...
    struct('RateKeyKbps',8,'TxPowerDbm',33,'Preamble','long','EnvelopeProfile','bare','AckRequired',false));
f.Id=uint64(1);assert(mac.enqueue(f));
s.run(222.309);assert(streams.Count==0 && ~mac.PreparationActive);
sleeps=p.select('mac_boundary','sleep_after');last=sleeps{end};
assert(round(last.time*1e9)==222308900000);
% Expected old continuous arithmetic, evaluated from the actual callback time.
expected=(floor(last.time/period)+1)*period;
assert(expected>last.time && last.details.IdleRtsEvent~=0);
s.run(expected-1e-9);assert(streams.Count==0);
s.run(expected);assert(streams.Count==1 && mac.PreparationActive);
draws=p.select('random_request');assert(numel(draws)==1 && draws{1}.time==expected);
idle=p.select('mac_boundary','idleRts_before');assert(numel(idle)==1 && idle{1}.time==expected);
assert(abs(expected-222.313)<1e-7);
report=struct('passed',true,'mode',mode,'slot_seconds',period, ...
    'sleep_time',last.time,'first_draw_time',draws{1}.time, ...
    'first_draw_hex',num2hex(draws{1}.time),'expected_continuous_time',expected, ...
    'scope','Non-grid slot retains continuous next-complete-cycle wake query.');
ac.writeJson(fullfile(folder,'result.json'),report);
ac.writeJson(fullfile(folder,'ownership_trace.json'),p.Rows);
% Exact accepted baseline bit pattern, retained as a compact regression oracle.
assert(strcmp(report.first_draw_hex,'406bca0418945fc5'));
finish(streams);clear cleanup;
end
function finish(streams),streams.close();ac.Trace.close();end
