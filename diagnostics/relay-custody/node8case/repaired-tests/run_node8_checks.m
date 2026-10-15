function report=run_node8_checks(mode)
% Controlled public MAC/receiver ownership probes; no full scenario run.
% Fresh MATLAB process per source. Baseline intentionally reproduces defect.
if nargin<1,mode='candidate';end
assert(strcmp(mode,'candidate'),'Published tests run the repaired candidate only.');
root=fileparts(mfilename('fullpath'));candidate=fileparts(root);
restoredefaultpath;addpath(root,candidate,fullfile(candidate,'model'),'-begin');rehash;
assert(startsWith(which('ac.DiscoveryMembershipNwk'),candidate));
config=configure_case(131,900);
config.Nodes=config.Nodes(ismember([config.Nodes.Id],[1 2 3]));
assert(numel(config.Nodes)==3);
for k=1:3
    config.Nodes(k).PositionMeters=[0 0 1];
    config.Nodes(k).RadioProfile.StochasticSyncThreshold=false;
end
% Local component geometry fixes only; production scenario is untouched.
config.Phy.SyncToTrackSeconds=0.00663;
config.Mac.DutyCycleEnabled=true;config.Mac.WakeCycleSeconds=0.052;
config.Mac.SlotSeconds=0.013;config.Mac.HoldoffSeconds=0.3;
folder=fullfile(root,'checks',mode);if ~isfolder(folder),mkdir(folder);end
cases={'idle_rts','periodic_wake','ordinary_search','incoming','tx_completion','receive_completion','no_preamble','legacy_callback'};
if strcmp(mode,'candidate'),cases=[cases {'mac_only_preserves_pending','mac_only_allows_new_arrival'}];end
checks=struct('name',{},'passed',{},'details',{});
for k=1:numel(cases)
    kind=cases{k};local=fullfile(folder,kind);if ~isfolder(local),mkdir(local);end
    bridgeMode=mode;if strcmp(kind,'legacy_callback'),bridgeMode='legacy';end
    [s,streams,engine,timer,p,mac]=setup(config,local,bridgeMode,ismember(kind,{'idle_rts','periodic_wake','no_preamble','legacy_callback'}));
    cleanup=onCleanup(@()streams.close()); %#ok<NASGU>
    switch kind
        case {'idle_rts','legacy_callback'}
            mac.start();engine.transmit(frame(1,1));s.run(0.01);
            assert(strcmp(engine.state(3),'Idle') && engine.hasSync(3));
            assert(mac.enqueue(frame(3,2)));s.run(0.025);
            a=acquisitions(timer,3);state=engine.state(3);
            if strcmp(mode,'baseline') || strcmp(kind,'legacy_callback')
                assert(height(a)==1 && a.NowNanoseconds==13000000 && strcmp(state,'Track'));
            else
                assert(isempty(a) && strcmp(state,'Search'));
            end
            assert(mac.PendingCount==1 && mac.Counters.Transmissions==0);
        case 'periodic_wake'
            mac.start();engine.transmit(frame(1,1));s.run(0.052+0.00663+1e-9);
            a=acquisitions(timer,3);state=engine.state(3);
            assert(height(a)==1 && a.NowNanoseconds==52000000 && strcmp(state,'Track'));
        case 'ordinary_search'
            engine.setReceiverState(3,'Idle');engine.transmit(frame(1,1));s.run(0.01);
            engine.setReceiverState(3,'Search');s.run(0.01663);
            a=acquisitions(timer,3);state=engine.state(3);
            assert(height(a)==1 && a.NowNanoseconds==10000000 && strcmp(state,'Track'));
        case 'incoming'
            engine.transmit(frame(1,1));s.run(0.00663);
            a=acquisitions(timer,3);state=engine.state(3);
            assert(height(a)==1 && a.NowNanoseconds==0 && strcmp(state,'Track'));
        case 'tx_completion'
            own=frame(3,1);own.Preamble='short';
            ending=csr.phy.airtime(own.WirePayloadBytes,own.RateKeyKbps,own.Preamble);
            % Schedule the synthetic second transmitter on canonical integer
            % ticks. Raw binary64 subtraction can lie above its rounded tick
            % and rightly violates the zero-distance receive-start gate.
            arrival=ac.ReceiverTimer.target(0,ending-0.005);
            engine.transmit(own);s.run(arrival);engine.transmit(frame(1,2));s.run(ending+0.00663+1e-9);
            a=acquisitions(timer,3);state=engine.state(3);
            assert(height(a)==1 && a.NowNanoseconds==round(ending*1e9));
            % A signal begun during TX can remain rejected; timer ownership,
            % rather than successful packet decoding, is the tested contract.
        case 'receive_completion'
            first=frame(1,1);first.Preamble='short';
            ending=csr.phy.airtime(first.WirePayloadBytes,first.RateKeyKbps,first.Preamble);
            arrival=ac.ReceiverTimer.target(0,ending-0.005);
            engine.transmit(first);s.run(arrival);
            assert(strcmp(engine.state(3),'Track'));
            engine.transmit(frame(2,2));s.run(ending+0.007);
            a=acquisitions(timer,3);state=engine.state(3);
            assert(height(a)==2 && a.NowNanoseconds(1)==0 && ...
                any(a.NowNanoseconds(2)==round(ending*1e9)+[0 28]));
            % Both successful immediate and rejected 28ns receive returns
            % own acquisition. Actual outcome is recorded, not forced.
        case 'no_preamble'
            mac.start();s.run(0.01);assert(mac.enqueue(frame(3,2)));s.run(0.025);
            a=acquisitions(timer,3);state=engine.state(3);
            assert(isempty(a) && strcmp(state,'Search') && ~engine.hasSync(3));
        case 'mac_only_preserves_pending'
            engine.transmit(frame(1,1));s.run(0.001);
            engine.setReceiverState(3,'Search',false);s.run(0.00663);
            a=acquisitions(timer,3);state=engine.state(3);
            assert(height(a)==1 && a.NowNanoseconds==0 && strcmp(state,'Track'));
        case 'mac_only_allows_new_arrival'
            engine.setReceiverState(3,'Idle');s.run(0.001);
            engine.setReceiverState(3,'Search',false);s.run(0.002);
            engine.transmit(frame(1,1));s.run(0.00863);
            a=acquisitions(timer,3);state=engine.state(3);
            assert(height(a)==1 && a.NowNanoseconds==2000000 && strcmp(state,'Track'));
    end
    details=struct('receiver_state',state,'acquisition_targets',table2struct(a), ...
        'state_callbacks',{p.States},'random_summary',streams.summary());
    checks(end+1)=struct('name',kind,'passed',true,'details',details); %#ok<AGROW>
    ac.writeJson(fullfile(local,'result.json'),details);streams.close();clear cleanup;
end
report=struct('mode',mode,'passed',all([checks.passed]),'checks',checks, ...
    'scope','Synthetic public component ownership; baseline reproduces extra acquisition; no network parity claim', ...
    'private_model_mutation',false,'production_scenario_changed',false);
ac.writeJson(fullfile(folder,'node8_checks.json'),report);
end
function [s,streams,engine,timer,p,mac]=setup(config,folder,mode,withMac)
s=csr.sim.EventScheduler(10000);streams=ac.Streams(config.Seed,s,'natural','',folder);
timer=ac.ReceiverTimer();p=Node8OwnershipProbe();p.Clock=s;
engine=ac.ReceiverTimerSignalEngine(config,s,streams,@(f,n,d)[],[],@(n,v)p.state(n,v), ...
    csr.sim.TransportTiming('nanoseconds'),timer);p.Engine=engine;mac=[];
if withMac
    cb=struct('Transmit',@(f,d)p.transmit(f,d),'SetReceiverState',@(v)engine.setReceiverState(3,v), ...
        'ReceiverState',@()engine.state(3),'HasSync',@()engine.hasSync(3));
    if strcmp(mode,'candidate')
        cb.SetReceiverStateMacOnly=@(v)engine.setReceiverState(3,v,false);
    end
    mac=ac.TerminalMac(3,s,streams,config,cb,timer);p.Mac=mac;
end
end
function a=acquisitions(timer,node)
v=timer.snapshot();assert(v.Omitted==0);a=v.Records;
if ~isempty(a),a=a(a.NodeId==node & a.Purpose=="acquisition",:);end
end
function f=frame(source,id)
c=struct('Id',uint64(id),'Type','DISCOVER','Payload',struct('Subtype','broadcast','Sequence',id,'ActivePeers',[]),'WirePayloadBytes',19);
f=csr.hop.Frames.control(c,source,16777215,uint16(id), ...
    struct('RateKeyKbps',8,'TxPowerDbm',33,'Preamble','long','EnvelopeProfile','bare','AckRequired',false));
f.Id=uint64(id);
end
