function rows = run_hop_replay(inputFile, outputFile)
% Prescribed decoded HOP ingress; real MAC and HOP, no PHY/NWK transport.
if nargin<1, inputFile=fullfile(fileparts(mfilename('fullpath')),'inputs.csv'); end
if nargin<2, outputFile='matlab-hop-replay.csv'; end
cases=readtable(inputFile,'TextType','string'); rows=table();
assert(~isfile(outputFile),'Use a fresh replay output file');
try
for k=1:height(cases)
    scheduler=csr.sim.EventScheduler(); streams=csr.sim.RandomStreams(132);
    options=csr.mac.Layer.defaults(); options.DutyCycleEnabled=false;
    options.ReservationSlotOverride=1; options.ActiveNodes=3;
    radio=struct('EnvelopeProfile','bare','RateKeyKbps',8,'TxPowerDbm',33);
    delivered=0; released=0; last=[];
    mac=csr.mac.Layer(2,scheduler,streams,options, ...
        struct('Transmit',@transmit,'Sent',@sent));
    hop=csr.hop.Layer(2,scheduler,streams,struct(), ...
        struct('EnqueueMac',@enqueue,'CancelMac',@cancel, ...
        'Deliver',@deliver,'NsdpRelease',@release));
    app=application(2,1,1,185);
    [ok,frame]=hop.send(app,1,radio); assert(ok && frame.Sequence==1);
    observe('admit');
    if cases.upstream_first_s(k)>=0
        scheduler.scheduleAt(cases.upstream_first_s(k),@()upstream(13));
    end
    if cases.upstream_second_s(k)>=0
        scheduler.scheduleAt(cases.upstream_second_s(k),@()upstream(14));
    end
    scheduler.scheduleAt(cases.feedback_s(k),@feedback);
    for tick=1:round(cases.stop_s(k)*1000)
        scheduler.scheduleAt(tick/1000,@()observe('state'));
    end
    scheduler.run(cases.stop_s(k)); observe('final');
    saveRows(); % Persist while the nested workspace is still live.
end
catch failure
    try
        saveRows();
    catch saveFailure
        warning('csr:replay:SaveFailed','Could not save partial replay: %s',saveFailure.message);
    end
    rethrow(failure);
end
saveRows();
    function saveRows()
        if ~isempty(rows), writetable(rows,outputFile); end
    end
    function a=application(source,destination,id,bytes)
        a=struct('Id',uint64(id),'SourceId',source,'DestinationId',destination, ...
            'GeneratedSeconds',scheduler.Now,'ApplicationPayloadBytes',bytes,'Dscp',0);
    end
    function accepted=enqueue(f)
        if isempty(f.TxPowerDbm), f.TxPowerDbm=33; end
        accepted=mac.enqueue(f);
    end
    function cancel(peer,sequence), mac.cancel(peer,sequence); end
    function sent(f), hop.notifySent(f); end
    function transmit(~,~)
        % Real MAC schedules finish and accounts airtime; outgoing frames
        % have no receiving peer in this controlled single-node experiment.
    end
    function accepted=deliver(~,~), delivered=delivered+1; accepted=true; end
    function release(~,~), released=released+1; end
    function upstream(sequence)
        % Final delivery to node2 deliberately avoids pretending to model NWK custody.
        f=csr.hop.Frames.data(application(8,2,sequence,185),8,2,uint16(sequence),radio);
        observe('upstream_before'); hop.receive(f,struct('Success',true)); observe('upstream_after');
    end
    function feedback()
        f=csr.hop.Frames.acknowledgment(1,2,uint16(1),uint64(1),uint64(0),radio);
        observe('feedback_before'); hop.receive(f,struct('Success',true)); observe('feedback_after');
    end
    function observe(event)
        a=hop.admission(1); s=mac.snapshot();
        values=[s.Transmissions mac.AckQueueCount mac.DataQueueCount ...
            hop.PendingDataCount a.NeighborOutstanding a.NeighborThreshold released delivered];
        if strcmp(event,'state') && isequal(values,last), return; end
        last=values;
        row=table(cases.case_id(k),scheduler.Now,string(event),values(1),values(2), ...
            values(3),values(4),values(5),values(6),values(7),values(8), ...
            'VariableNames',{'case_id','observed_time_s','event','mac_tx', ...
            'ack_queue','data_queue','hop_pending','neighbor_outstanding', ...
            'neighbor_threshold','released','delivered'});
        rows=[rows;row]; %#ok<AGROW>
    end
end
