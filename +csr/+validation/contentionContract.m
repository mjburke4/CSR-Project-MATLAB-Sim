function report = contentionContract(outputDirectory)
%CONTENTIONCONTRACT Matched MAC timing with prescribed receiver inputs.
% Fixed neighbor occupancy leaves exactly one modulo-probe slot. Receiver
% states/SYNC are prescribed public inputs; no RF delivery or RNG matching
% is claimed. Equal-time early/late insertion explicitly exercises FIFO.
if nargin < 1, outputDirectory = ''; end
rows = repmat(struct('case','','checkpoint','','time_seconds',0, ...
    'field','','actual',0,'expected',0,'pass',false),0,1);
runIdle('idle_p15',15*.013,.208);
runIdle('idle_literal',.195,.208);
runIdle('idle_p30',30*.013,.403);
runIdle('idle_p51',51*.013,.676);
runIdle('idle_p60',60*.013,.793);
runIdle('idle_before',.195-1e-9,.195);
runIdle('idle_after',.195+1e-9,.208);
runAccess('search_initial',0);
runAccess('sync_initial',1);
runAccess('track_initial',2);
runAccess('sync_busy',3);
runAccess('track_busy',4);
runAccess('track_tie_early',5);
runAccess('track_tie_late',6);
runRestart();
checkpoints = struct2table(rows);
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
reference = fullfile(root,'evidence','tranche-10-contract-reference','checkpoints.csv');
expected = readtable(reference,'TextType','string','VariableNamingRule','preserve');
matched = false(height(checkpoints),1);
if height(expected) == height(checkpoints) && ...
        isequal(expected.Properties.VariableNames,checkpoints.Properties.VariableNames)
    matched(:) = true;
    for name = {'case','checkpoint','field'}
        matched = matched & string(checkpoints.(name{1})) == string(expected.(name{1}));
    end
    for name = {'time_seconds','actual','expected','pass'}
        actual = double(checkpoints.(name{1})); target = double(expected.(name{1}));
        matched = matched & isfinite(actual) & isfinite(target) & abs(actual-target) <= 1e-9;
    end
end
summary = struct('Schema','csr-tranche10-contention-contract-v1', ...
    'Passed',all(checkpoints.pass) && all(matched), ...
    'CheckpointCount',height(checkpoints), ...
    'ReferenceSHA256',csr.validation.Artifacts.sha256(reference), ...
    'UnmatchedCount',sum(~matched),'FailedCount',sum(~checkpoints.pass), ...
    'Scope','Prescribed receiver/occupancy inputs; MAC-local clock and FIFO; no RF or RNG-stream equivalence');
if ~isempty(outputDirectory)
    if ~isfolder(outputDirectory), mkdir(outputDirectory); end
    writetable(checkpoints,fullfile(outputDirectory,'checkpoints.csv'));
    csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'summary.json'),summary);
end
report = summary; report.Checkpoints = checkpoints;

    function check(scheduler,name,point,field,actual,target)
        row = struct('case',name,'checkpoint',point,'time_seconds',scheduler.Now, ...
            'field',field,'actual',double(actual),'expected',double(target), ...
            'pass',isfinite(double(actual)) && abs(double(actual)-double(target)) <= 1e-9);
        rows(end+1,1) = row;
    end

    function [mac,scheduler] = fixture(syncCallback)
        scheduler = csr.sim.EventScheduler();
        options = csr.mac.Layer.defaults(); options.DutyCycleEnabled = false;
        options.ActiveNodes = 3;
        options.SlotProfile = 'hist-2014-next-tslot-modulo-probe';
        options.SlotReduction = 29;
        callbacks = struct('Transmit',@(~,~)[]);
        if nargin > 0, callbacks.HasSync = syncCallback; end
        mac = csr.mac.Layer(1,scheduler,csr.sim.RandomStreams(129),options,callbacks);
        mac.start();
    end

    function occupy(mac,first)
        for peer = [2 3]
            heard = dataFrame(); heard.SourceId = peer;
            heard.ReservationSlot = first+2*(peer-2);
            mac.receive(heard,struct('Success',true));
            mac.receive(heard,struct('Success',true));
        end
    end

    function afterTx(mac,scheduler,name)
        check(scheduler,name,'after_tx','transmissions',mac.Counters.Transmissions,1);
        check(scheduler,name,'after_tx','opportunity_slot',mac.LastOpportunitySlot,1);
        check(scheduler,name,'after_tx','data_queue',mac.DataQueueCount,0);
        check(scheduler,name,'after_tx','state',stateCode(mac),3);
    end

    function runIdle(name,arrival,wake)
        [mac,scheduler] = fixture();
        mac.receiverChanged('Idle'); occupy(mac,0);
        scheduler.scheduleAt(arrival,@enqueue);
        scheduler.scheduleAt(wake-1e-6,@beforeWake);
        scheduler.scheduleAt(wake+1e-6,@prepared);
        tx = wake+.325;
        scheduler.scheduleAt(tx-1e-6,@beforeTx);
        scheduler.scheduleAt(tx+1e-6,@()afterTx(mac,scheduler,name));
        scheduler.run(tx+1e-5);
        function enqueue()
            mac.enqueue(dataFrame());
            check(scheduler,name,'queued','state',stateCode(mac),0);
            check(scheduler,name,'queued','preparation',mac.PreparationActive,0);
            check(scheduler,name,'queued','data_queue',mac.DataQueueCount,1);
        end
        function beforeWake()
            check(scheduler,name,'before_wake','state',stateCode(mac),0);
            check(scheduler,name,'before_wake','preparation',mac.PreparationActive,0);
            check(scheduler,name,'before_wake','transmissions',mac.Counters.Transmissions,0);
        end
        function prepared()
            check(scheduler,name,'prepared','state',stateCode(mac),1);
            check(scheduler,name,'prepared','preparation',mac.PreparationActive,1);
            check(scheduler,name,'prepared','counter',mac.ReservationCounter,1);
            check(scheduler,name,'prepared','transmissions',mac.Counters.Transmissions,0);
        end
        function beforeTx()
            check(scheduler,name,'before_tx','counter',mac.ReservationCounter,0);
            check(scheduler,name,'before_tx','transmissions',mac.Counters.Transmissions,0);
        end
    end

    function runAccess(name,mode)
        sync = mode == 1;
        [mac,scheduler] = fixture(@hasSync);
        occupy(mac,double(~any(mode==[1 2])));
        if mode == 2, mac.receiverChanged('Track'); end
        mac.enqueue(dataFrame());
        check(scheduler,name,'queued','state',stateCode(mac),1+(mode==2));
        check(scheduler,name,'queued','preparation',mac.PreparationActive,0);
        check(scheduler,name,'queued','transmissions',mac.Counters.Transmissions,0);
        check(scheduler,name,'queued','data_queue',mac.DataQueueCount,1);
        scheduler.scheduleAt(.014,@prepared);
        scheduler.scheduleAt(.299,@beforeHoldoff);
        if mode >= 3
            if mode == 6
                % Tick 0.312 is already armed by 0.299. This insertion at
                % 0.311 gives Track a later equal-time event ID than TSLOT.
                scheduler.scheduleAt(.311,@lateFreeze);
            elseif mode == 5
                % This event is inserted before the recurring 0.312 tick.
                scheduler.scheduleAt(.312,@freeze);
            else
                scheduler.scheduleAt(.310,@freeze);
            end
            scheduler.scheduleAt(.399,@frozen);
            scheduler.scheduleAt(.400,@resume);
        else
            scheduler.scheduleAt(.310,@resume);
        end
        tx = .325;
        if mode >= 3, tx = .416; end
        if mode == 6, tx = .403; end
        scheduler.scheduleAt(tx-1e-6,@beforeTx);
        scheduler.scheduleAt(tx+1e-6,@()afterTx(mac,scheduler,name));
        scheduler.run(tx+1e-5);
        function present = hasSync(), present = sync; end
        function prepared()
            check(scheduler,name,'prepared','preparation',mac.PreparationActive,mode~=2);
            check(scheduler,name,'prepared','counter',mac.ReservationCounter,1-2*(mode==2));
            check(scheduler,name,'prepared','transmissions',mac.Counters.Transmissions,0);
            check(scheduler,name,'prepared','state',stateCode(mac),1+(mode==2));
        end
        function beforeHoldoff()
            check(scheduler,name,'before_holdoff','transmissions',mac.Counters.Transmissions,0);
            check(scheduler,name,'before_holdoff','counter',mac.ReservationCounter,1-2*(mode==2));
        end
        function lateFreeze(), scheduler.scheduleAt(.312,@freeze); end
        function freeze()
            if mode == 3, sync = true; else, mac.receiverChanged('Track'); end
        end
        function frozen()
            check(scheduler,name,'frozen','counter',mac.ReservationCounter,1-(mode==6));
            check(scheduler,name,'frozen','transmissions',mac.Counters.Transmissions,0);
            check(scheduler,name,'frozen','preparation',mac.PreparationActive,1);
            check(scheduler,name,'frozen','state',stateCode(mac),1+(mode~=3));
        end
        function resume()
            if any(mode==[1 3]), sync = false; end
            if any(mode==[2 4 5 6]), mac.receiverChanged('Search'); end
            check(scheduler,name,'resume','counter',mac.ReservationCounter,1-(mode==6));
            check(scheduler,name,'resume','preparation',mac.PreparationActive,1);
            check(scheduler,name,'resume','state',stateCode(mac),1);
        end
        function beforeTx()
            check(scheduler,name,'before_tx','counter',mac.ReservationCounter,0);
            check(scheduler,name,'before_tx','transmissions',mac.Counters.Transmissions,0);
        end
    end

    function runRestart()
        name = 'idle_restart'; [mac,scheduler] = fixture();
        occupy(mac,1); mac.enqueue(dataFrame());
        scheduler.scheduleAt(.014,@initial);
        scheduler.scheduleAt(.020,@idle);
        scheduler.scheduleAt(.025,@restart);
        scheduler.scheduleAt(.038-1e-6,@beforeTick);
        scheduler.scheduleAt(.038+1e-6,@newTick);
        scheduler.scheduleAt(.350-1e-6,@beforeTx);
        scheduler.scheduleAt(.350+1e-6,@()afterTx(mac,scheduler,name));
        scheduler.run(.35001);
        function initial()
            check(scheduler,name,'initial','preparation',mac.PreparationActive,1);
            check(scheduler,name,'initial','counter',mac.ReservationCounter,1);
        end
        function idle()
            removed = mac.cancel(2,uint16(1)); mac.receiverChanged('Idle');
            check(scheduler,name,'idle','removed',removed,1);
            check(scheduler,name,'idle','preparation',mac.PreparationActive,0);
            check(scheduler,name,'idle','state',stateCode(mac),0);
        end
        function restart()
            occupy(mac,1); mac.receiverChanged('Search'); mac.enqueue(dataFrame());
            check(scheduler,name,'restart','preparation',mac.PreparationActive,0);
            check(scheduler,name,'restart','state',stateCode(mac),1);
        end
        function beforeTick()
            check(scheduler,name,'before_new_tick','preparation',mac.PreparationActive,0);
            check(scheduler,name,'before_new_tick','neighbor_counter',mac.neighborReservation(2),1);
        end
        function newTick()
            check(scheduler,name,'new_tick','preparation',mac.PreparationActive,1);
            check(scheduler,name,'new_tick','counter',mac.ReservationCounter,1);
            check(scheduler,name,'new_tick','neighbor_counter',mac.neighborReservation(2),0);
        end
        function beforeTx()
            check(scheduler,name,'before_tx','counter',mac.ReservationCounter,0);
            check(scheduler,name,'before_tx','transmissions',mac.Counters.Transmissions,0);
        end
    end
end

function value = stateCode(mac)
value = find(strcmp(mac.State,{'Idle','Search','Track','Tx'}))-1;
end

function frame = dataFrame()
application = struct('Id',uint64(1),'SourceId',1,'DestinationId',2, ...
    'GeneratedSeconds',0,'ApplicationPayloadBytes',16,'Dscp',0);
frame = csr.hop.Frames.data(application,1,2,uint16(1), ...
    struct('EnvelopeProfile','bare','RateKeyKbps',128,'TxPowerDbm',33));
end
