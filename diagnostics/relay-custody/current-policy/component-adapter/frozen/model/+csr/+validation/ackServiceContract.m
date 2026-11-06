function report = ackServiceContract(outputDirectory)
%ACKSERVICECONTRACT Matched public-API MAC/HOP service checkpoints.
% Receiver states and feedback arrivals are prescribed, with no RF delivery
% claim. Occupied neighbors leave one free modulo-probe slot; the existing
% ns-3 and MATLAB forced-reservation options are intentionally not used.
if nargin < 1, outputDirectory = ''; end
rows = repmat(struct('case','','checkpoint','','time_seconds',0, ...
    'field','','actual',0,'expected',0,'pass',false),0,1);
runMac('mac_ack_wait',0,false,false);
runMac('mac_ack_sync',1,false,false);
runMac('mac_ack_track',2,false,false);
runMac('mac_cancel_then_ack',0,true,false);
runMac('mac_control_cancel_then_ack',0,true,true);
runHop();
checkpoints = struct2table(rows);
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
reference = fullfile(root,'evidence','tranche-9-contract-reference','checkpoints.csv');
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
summary = struct('Schema','csr-tranche9-ack-service-contract-v1', ...
    'Passed',all(checkpoints.pass) && all(matched), ...
    'CheckpointCount',height(checkpoints), ...
    'ReferenceSHA256',csr.validation.Artifacts.sha256(reference), ...
    'UnmatchedCount',sum(~matched),'FailedCount',sum(~checkpoints.pass), ...
    'Scope','Prescribed receiver states and ACK ingress; no RF delivery or RNG-stream equivalence');
if ~isempty(outputDirectory)
    if ~isfolder(outputDirectory), mkdir(outputDirectory); end
    writetable(checkpoints,fullfile(outputDirectory,'checkpoints.csv'));
    csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'summary.json'),summary);
end
report = summary;
report.Checkpoints = checkpoints;

    function check(scheduler,name,point,field,actual,target)
        row = struct('case',name,'checkpoint',point,'time_seconds',scheduler.Now, ...
            'field',field,'actual',double(actual),'expected',double(target), ...
            'pass',isfinite(double(actual)) && abs(double(actual)-double(target)) <= 1e-9);
        rows(end+1,1) = row;
    end

    function runMac(name,freeze,cancelData,cancelControl)
        scheduler = csr.sim.EventScheduler();
        options = csr.mac.Layer.defaults();
        options.DutyCycleEnabled = false;
        options.ActiveNodes = 3;
        options.SlotProfile = 'hist-2014-next-tslot-modulo-probe';
        options.SlotReduction = 29; % Fixed fixture input, no supervisor process.
        sync = false; rate = 0; power = 0;
        mac = csr.mac.Layer(1,scheduler,csr.sim.RandomStreams(129),options, ...
            struct('Transmit',@transmit,'HasSync',@hasSync));
        occupy();
        if cancelControl
            control = struct('Id',uint64(7),'Type','KEY_REQUEST', ...
                'Payload',struct(),'WirePayloadBytes',32);
            mac.enqueue(csr.hop.Frames.control(control,1,2,uint16(7), ...
                struct('EnvelopeProfile','bare','RateKeyKbps',128,'TxPowerDbm',33, ...
                'AckRequired',false)));
        elseif cancelData, mac.enqueue(frame(7,false));
        else, mac.enqueue(frame(10,true)); end
        scheduler.scheduleAt(.014,@prepared);
        if ~cancelData, scheduler.scheduleAt(.200,@replace); end
        scheduler.scheduleAt(.299,@beforeHoldoff);
        if freeze
            scheduler.scheduleAt(.310,@startFreeze);
            scheduler.scheduleAt(.399,@frozen);
            scheduler.scheduleAt(.400,@resume);
        end
        if cancelData
            scheduler.scheduleAt(.315,@cancel);
            scheduler.scheduleAt(.320,@newAck);
        end
        tx = .325; if freeze, tx = .416; end
        scheduler.scheduleAt(tx-.001,@occupy);
        scheduler.scheduleAt(tx-.000001,@beforeTx);
        scheduler.scheduleAt(tx+.000001,@afterTx);
        scheduler.run(tx+.00001);

        function occupy()
            for peer = [2 3]
                heard = frame(0,false); heard.SourceId = peer;
                heard.ReservationSlot = 2*peer-3; % 1 and 3 before next tick.
                mac.receive(heard,struct('Success',true));
                mac.receive(heard,struct('Success',true));
            end
        end
        function prepared()
            check(scheduler,name,'prepared','counter',mac.ReservationCounter,1);
            check(scheduler,name,'prepared','preparation',mac.PreparationActive,1);
            check(scheduler,name,'prepared','transmissions',mac.Counters.Transmissions,0);
        end
        function replace()
            mac.enqueue(frame(11,true));
            check(scheduler,name,'replaced','ack_queue',mac.AckQueueCount,1);
            check(scheduler,name,'replaced','counter',mac.ReservationCounter,1);
        end
        function beforeHoldoff()
            check(scheduler,name,'before_holdoff','transmissions',mac.Counters.Transmissions,0);
        end
        function startFreeze()
            if freeze == 1, sync = true; else, mac.receiverChanged('Track'); end
        end
        function frozen()
            check(scheduler,name,'frozen','counter',mac.ReservationCounter,1);
            check(scheduler,name,'frozen','transmissions',mac.Counters.Transmissions,0);
        end
        function resume()
            if freeze == 1, sync = false; else, mac.receiverChanged('Search'); end
            check(scheduler,name,'resume','preparation',mac.PreparationActive,1);
        end
        function cancel()
            if cancelControl, removed = mac.cancelControl(2,'KEY_REQUEST');
            else, removed = mac.cancel(2,uint16(7)); end
            check(scheduler,name,'canceled','removed',removed,1);
            check(scheduler,name,'canceled','data_queue',mac.DataQueueCount,0);
            check(scheduler,name,'canceled','preparation',mac.PreparationActive,1);
            check(scheduler,name,'canceled','counter',mac.ReservationCounter,0);
        end
        function newAck()
            mac.enqueue(frame(11,true));
            check(scheduler,name,'new_ack','ack_queue',mac.AckQueueCount,1);
            check(scheduler,name,'new_ack','preparation',mac.PreparationActive,1);
        end
        function beforeTx()
            check(scheduler,name,'before_tx','transmissions',mac.Counters.Transmissions,0);
            check(scheduler,name,'before_tx','counter',mac.ReservationCounter,0);
        end
        function afterTx()
            check(scheduler,name,'after_tx','transmissions',mac.Counters.Transmissions,1);
            check(scheduler,name,'after_tx','advertised_slot',mac.LastAdvertisedReservation,1);
            check(scheduler,name,'after_tx','ack_queue',mac.AckQueueCount,1);
            check(scheduler,name,'after_tx','data_queue',mac.DataQueueCount,0);
            check(scheduler,name,'after_tx','rate_key_kbps',rate,128);
            check(scheduler,name,'after_tx','power_dbm',power,33);
        end
        function transmit(envelope,~)
            rate = envelope.RateKeyKbps; power = envelope.TxPowerDbm;
        end
        function present = hasSync(), present = sync; end
    end

    function runHop()
        name = 'hop_release_order';
        scheduler = csr.sim.EventScheduler(); streams = csr.sim.RandomStreams(129);
        options = csr.mac.Layer.defaults(); options.DutyCycleEnabled = false;
        mac = csr.mac.Layer(1,scheduler,streams,options,struct('Transmit',@(~,~)[]));
        mac.start(); mac.receiverChanged('Track');
        releases = 0; wakes = 0;
        hop = csr.hop.Layer(1,scheduler,streams,struct(), ...
            struct('EnqueueMac',@(f)mac.enqueue(f),'CancelMac',@(p,s)mac.cancel(p,s), ...
            'NsdpRelease',@release,'Wake',@wake));
        hop.send(app(1,3),2,struct('EnvelopeProfile','bare','RateKeyKbps',128,'TxPowerDbm',33));
        check(scheduler,name,'admitted','pending',hop.PendingDataCount,1);
        check(scheduler,name,'admitted','can_send',hop.canSend(2),0);
        scheduler.scheduleAt(.100,@feedback);
        scheduler.scheduleAt(.100000001,@beforeTic);
        scheduler.scheduleAt(.100000100,@afterTic);
        scheduler.run(.101);

        function release(application,~)
            releases = releases+1; state = hop.state(2);
            check(scheduler,name,'nsdp_callback','source',application.SourceId,1);
            check(scheduler,name,'nsdp_callback','destination',application.DestinationId,3);
            check(scheduler,name,'nsdp_callback','pending',state.PendingData,0);
            check(scheduler,name,'nsdp_callback','outstanding',state.NeighborOutstanding,0);
            check(scheduler,name,'nsdp_callback','resend_queue',state.ResendQueueDepth,1);
            check(scheduler,name,'nsdp_callback','mac_queue',mac.DataQueueCount,1);
        end
        function wake(), wakes = wakes+1; end
        function feedback()
            ack = csr.hop.Frames.acknowledgment(2,1,uint16(1),uint64(1),uint64(0), ...
                struct('EnvelopeProfile','bare','RateKeyKbps',128,'TxPowerDbm',33));
            hop.receive(ack); hop.receive(ack);
            state = hop.state(2);
            check(scheduler,name,'completed','pending',hop.PendingDataCount,0);
            check(scheduler,name,'completed','resend_queue',state.ResendQueueDepth,0);
            check(scheduler,name,'completed','mac_queue',mac.DataQueueCount,0);
            check(scheduler,name,'completed','can_send',hop.canSend(2),1);
            check(scheduler,name,'completed','releases',releases,1);
            check(scheduler,name,'completed','wakes',wakes,0);
        end
        function beforeTic(), check(scheduler,name,'before_tic','wakes',wakes,0); end
        function afterTic()
            check(scheduler,name,'after_tic','wakes',wakes,1);
            check(scheduler,name,'after_tic','can_send',hop.canSend(2),1);
        end
    end
end

function output = app(sequence,destination)
output = struct('Id',uint64(sequence),'SourceId',1,'DestinationId',destination, ...
    'GeneratedSeconds',0,'ApplicationPayloadBytes',16,'Dscp',0);
end

function output = frame(sequence,isAck)
radio = struct('EnvelopeProfile','bare','RateKeyKbps',128,'TxPowerDbm',33);
if isAck
    bitmap = uint64(3); if sequence == 10, bitmap = uint64(1); end
    output = csr.hop.Frames.acknowledgment(1,2,uint16(sequence),bitmap,uint64(0),radio);
else
    output = csr.hop.Frames.data(app(sequence,2),1,2,uint16(sequence),radio);
end
end
