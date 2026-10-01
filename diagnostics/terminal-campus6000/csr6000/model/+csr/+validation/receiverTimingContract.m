function report = receiverTimingContract(outputDirectory)
%RECEIVERTIMINGCONTRACT Fixed transmissions through the real receive pipeline.
% The source-aligned receiver wakes every .988 s. A single 617-byte, long
% preamble frame traverses 1200 m at the unchanged 128-kbps/+33-dBm profile.
% Only stochastic SYNC-threshold sampling is disabled for this fixture.
% Source BER tables and ECC remain active; zero BER/errors are checked.
% No HOP ACK generation, reservation override, or cross-simulator RNG claim.
if nargin < 1, outputDirectory = ''; end
rows = repmat(struct('case','','checkpoint','','time_seconds',0, ...
    'field','','actual',0,'expected',0,'pass',false),0,1);
runCase('preamble_before_wake',.962,.994630,false);
runCase('preamble_at_wake',.988,.994634,false);
runCase('preamble_after_wake',.990,.996634,false);
runCase('acquisition_canceled_by_sleep',.991,1.982630,true);
checkpoints = struct2table(rows);
root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
reference = fullfile(root,'evidence','tranche-10-receiver-reference','checkpoints.csv');
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
        tolerance = zeros(height(checkpoints),1);
        if strcmp(name{1},'time_seconds')
            tolerance(:) = 1e-12;
        elseif any(strcmp(name{1},{'actual','expected'}))
            tolerance(endsWith(string(checkpoints.field),'_seconds')) = 1e-12;
        end
        matched = matched & isfinite(actual) & isfinite(target) & abs(actual-target) <= tolerance;
    end
end
summary = struct('Schema','csr-tranche10-receiver-contract-v1', ...
    'Passed',all(checkpoints.pass) && all(matched), ...
    'CheckpointCount',height(checkpoints), ...
    'ReferenceSHA256',csr.validation.Artifacts.sha256(reference), ...
    'UnmatchedCount',sum(~matched),'FailedCount',sum(~checkpoints.pass), ...
    'Scope',['Controlled fixed-TX receive timing with source BER/ECC, deterministic SYNC threshold, ' ...
        'and source-aligned periodic wake; no contention, HOP feedback, or RNG-stream equivalence']);
if ~isempty(outputDirectory)
    if ~isfolder(outputDirectory), mkdir(outputDirectory); end
    writetable(checkpoints,fullfile(outputDirectory,'checkpoints.csv'));
    csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'summary.json'),summary);
end
report = summary;
report.Checkpoints = checkpoints;

    function check(scheduler,name,point,field,actual,target)
        tolerance = 0;
        if endsWith(field,'_seconds'), tolerance = 1e-12; end
        row = struct('case',name,'checkpoint',point,'time_seconds',scheduler.Now, ...
            'field',field,'actual',double(actual),'expected',double(target), ...
            'pass',isfinite(double(actual)) && abs(double(actual)-double(target)) <= tolerance);
        rows(end+1,1) = row;
    end

    function runCase(name,txAt,trackAt,missFirstWindow)
        config = csr.scenario.smallNetwork();
        profile = csr.phy.RadioProfile.defaults();
        profile.StochasticSyncThreshold = false;
        profile.TxPowerDbm = 33;
        config.Nodes = struct('Id',{1,2},'PositionMeters',{[0 0 1],[1200 0 1]}, ...
            'RadioProfile',{profile,profile});
        config.Channel.PropagationSpeedMps = 3e8;
        scheduler = csr.sim.EventScheduler(); streams = csr.sim.RandomStreams(129);
        mac = []; received = 0;
        engine = csr.phy.SignalEngine(config,scheduler,streams,@receive,[],@stateChanged);
        options = csr.mac.Layer.defaults();
        mac = csr.mac.Layer(1,scheduler,streams,options, ...
            struct('Transmit',@unexpectedTransmit, ...
            'SetReceiverState',@(value)engine.setReceiverState(1,value), ...
            'ReceiverState',@()engine.state(1),'HasSync',@()engine.hasSync(1)));
        mac.start();
        frame = csr.packet(uint64(1),struct('SourceId',2,'DestinationId',1, ...
            'ApplicationPayloadBytes',585,'TxPowerDbm',33),txAt, ...
            struct('RateKeyKbps',128,'Preamble','long','EnvelopeProfile','bare'));
        arrivalAt = txAt+4e-6;
        preambleEnd = arrivalAt+1.005720;
        receiveEnd = arrivalAt+1.049100;
        probe = 1e-9;
        check(scheduler,name,'initial','idle',strcmp(engine.state(1),'Idle'),1);
        check(scheduler,name,'initial','sync_present',engine.hasSync(1),0);
        check(scheduler,name,'initial','received',received,0);
        check(scheduler,name,'initial','wire_bytes',frame.WirePayloadBytes,617);
        scheduler.scheduleAt(txAt,@transmit);
        scheduler.scheduleAt(arrivalAt-probe,@beforeArrival);
        scheduler.scheduleAt(arrivalAt+probe,@afterArrival);
        scheduler.scheduleAt(.988-probe,@beforeWake);
        scheduler.scheduleAt(.988+probe,@afterWake);
        scheduler.scheduleAt(trackAt-probe,@beforeTrack);
        scheduler.scheduleAt(trackAt+probe,@afterTrack);
        scheduler.scheduleAt(.996900+probe,@afterFirstSleep);
        if missFirstWindow
            scheduler.scheduleAt(1.976-probe,@beforeSecondWake);
            scheduler.scheduleAt(1.976+probe,@afterSecondWake);
        end
        scheduler.scheduleAt(preambleEnd-probe,@beforePreambleEnd);
        scheduler.scheduleAt(preambleEnd+probe,@afterPreambleEnd);
        scheduler.scheduleAt(receiveEnd-probe,@beforeEnd);
        scheduler.scheduleAt(receiveEnd+probe,@afterEnd);
        scheduler.scheduleAt(receiveEnd+.0078-probe,@beforeSleep);
        scheduler.scheduleAt(receiveEnd+.0078+probe,@afterSleep);
        scheduler.run(receiveEnd+.008);

        function transmit()
            duration = csr.phy.airtime(frame.WirePayloadBytes,frame.RateKeyKbps,frame.Preamble);
            check(scheduler,name,'transmit','duration_seconds',duration,1.049100);
            engine.transmit(frame,duration);
        end
        function stateChanged(id,value)
            if id == 1 && ~isempty(mac), mac.receiverChanged(value); end
        end
        function receive(value,id,decision)
            if id ~= 1, return; end
            received = received+1;
            mac.receive(value,decision);
            check(scheduler,name,'delivery','received',received,1);
            check(scheduler,name,'delivery','sequence',value.Id,1);
            check(scheduler,name,'delivery','track',strcmp(engine.state(1),'Track'),1);
            check(scheduler,name,'delivery','time_seconds',scheduler.Now,receiveEnd);
            check(scheduler,name,'delivery','success',decision.Success,1);
            check(scheduler,name,'delivery','header_ber',decision.HeaderBer,0);
            check(scheduler,name,'delivery','payload_ber',decision.PayloadBer,0);
            check(scheduler,name,'delivery','header_errors',decision.HeaderErrors,0);
            check(scheduler,name,'delivery','payload_errors',decision.PayloadErrors,0);
            check(scheduler,name,'delivery','sync_present',engine.hasSync(1),0);
        end
        function beforeArrival()
            check(scheduler,name,'before_arrival','sync_present',engine.hasSync(1),0);
        end
        function afterArrival()
            check(scheduler,name,'after_arrival','sync_present',engine.hasSync(1),1);
            check(scheduler,name,'after_arrival','idle',strcmp(engine.state(1),'Idle'),txAt < .988);
        end
        function beforeWake()
            check(scheduler,name,'before_wake','idle',strcmp(engine.state(1),'Idle'),1);
        end
        function afterWake()
            check(scheduler,name,'after_wake','search',strcmp(engine.state(1),'Search'),1);
        end
        function beforeTrack()
            check(scheduler,name,'before_track','search',strcmp(engine.state(1),'Search'),1);
            check(scheduler,name,'before_track','received',received,0);
        end
        function afterTrack()
            check(scheduler,name,'after_track','track',strcmp(engine.state(1),'Track'),1);
        end
        function afterFirstSleep()
            check(scheduler,name,'after_first_sleep','idle',strcmp(engine.state(1),'Idle'),missFirstWindow);
            check(scheduler,name,'after_first_sleep','sync_present',engine.hasSync(1),1);
            check(scheduler,name,'after_first_sleep','received',received,0);
        end
        function beforeSecondWake()
            check(scheduler,name,'before_second_wake','idle',strcmp(engine.state(1),'Idle'),1);
        end
        function afterSecondWake()
            check(scheduler,name,'after_second_wake','search',strcmp(engine.state(1),'Search'),1);
        end
        function beforePreambleEnd()
            check(scheduler,name,'before_preamble_end','sync_present',engine.hasSync(1),1);
            check(scheduler,name,'before_preamble_end','track',strcmp(engine.state(1),'Track'),1);
        end
        function afterPreambleEnd()
            check(scheduler,name,'after_preamble_end','sync_present',engine.hasSync(1),0);
            check(scheduler,name,'after_preamble_end','track',strcmp(engine.state(1),'Track'),1);
        end
        function beforeEnd()
            check(scheduler,name,'before_end','track',strcmp(engine.state(1),'Track'),1);
            check(scheduler,name,'before_end','received',received,0);
        end
        function afterEnd()
            check(scheduler,name,'after_end','search',strcmp(engine.state(1),'Search'),1);
            check(scheduler,name,'after_end','received',received,1);
            check(scheduler,name,'after_end','sync_present',engine.hasSync(1),0);
        end
        function beforeSleep()
            check(scheduler,name,'before_sleep','search',strcmp(engine.state(1),'Search'),1);
        end
        function afterSleep()
            check(scheduler,name,'after_sleep','idle',strcmp(engine.state(1),'Idle'),1);
            check(scheduler,name,'after_sleep','received',received,1);
        end
    end
end

function unexpectedTransmit(~,~)
error('csr:validation:ReceiverContractTransmit','Receiver-only fixture unexpectedly queued a transmission.');
end
