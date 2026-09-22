function report = run_mac_tests(coreRoot, outputDirectory)
% Controlled real-MAC tests; no PHY, HOP or campus reconstruction.
here=fileparts(mfilename('fullpath'));
if nargin<2, outputDirectory=fullfile(here,'results'); end
assert(~isfolder(outputDirectory),'Use a fresh output directory.');
addpath(coreRoot,'-begin');
assert(strcmp(csr.validation.Artifacts.canonicalPath(which('csr.mac.Layer')), ...
    csr.validation.Artifacts.canonicalPath(fullfile(coreRoot,'+csr','+mac','Layer.m'))), ...
    'Supply an absolute accepted core root; another csr package is shadowing it.');
expected=jsondecode(fileread(fullfile(here,'..','accepted-core.json')));
for k=1:numel(expected)
    assert(strcmp(csr.validation.Artifacts.sha256(fullfile(coreRoot,expected(k).path)),expected(k).sha256),'Accepted core mismatch');
end
mkdir(outputDirectory); diary(fullfile(outputDirectory,'run.log'));
cleanup=onCleanup(@()diary('off')); %#ok<NASGU>
report=struct('status','running','matlab_executed',true,'native_executed',false, ...
    'version',version,'release',version('-release'),'case_count',0, ...
    'scope','Real MAC with fixed reservation slot 1; controlled frame arrivals and receiver states.');
rows=table(); inputs=table(); checks=table();
sourceBefore=csr.validation.Artifacts.sourceSnapshot(coreRoot);
copyfile(fullfile(here,'cases.csv'),fullfile(outputDirectory,'cases.csv'));
csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'source.json'),sourceBefore);
cases=readtable(fullfile(here,'cases.csv'),'TextType','string');
try
    for c=1:height(cases), runCase(cases(c,:)); end
    assert(isequal(sourceBefore,csr.validation.Artifacts.sourceSnapshot(coreRoot)), ...
        'Core source changed during execution.');
    report.case_count=height(cases); report.status='completed';
    report.structural_passed=all(checks.pass);
    report.cross_engine_compared=false;
catch failure
    report.status='failed'; report.error=failure.message;
    saveEvidence(); rethrow(failure);
end
saveEvidence();
assert(report.structural_passed,'MAC structural expectations failed; preserve results.');
    function saveEvidence()
        writetable(rows,fullfile(outputDirectory,'events.csv'));
        writetable(inputs,fullfile(outputDirectory,'inputs.csv'));
        writetable(checks,fullfile(outputDirectory,'checks.csv'));
        csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'metadata.json'),report);
    end
    function runCase(entry)
        scheduler=csr.sim.EventScheduler(); config=csr.mac.Layer.defaults();
        config.DutyCycleEnabled=false; config.ReservationSlotOverride=1; config.ActiveNodes=3;
        radio=struct('EnvelopeProfile','bare','RateKeyKbps',entry.rate_kbps,'TxPowerDbm',33);
        app=struct('Id',uint64(1),'SourceId',2,'DestinationId',1, ...
            'GeneratedSeconds',0,'ApplicationPayloadBytes',entry.payload_bytes,'Dscp',0);
        data=csr.hop.Frames.data(app,2,1,uint16(1),radio);
        ack=csr.hop.Frames.acknowledgment(2,8,uint16(13),uint64(1),uint64(0),radio);
        assert(data.WirePayloadBytes==entry.payload_bytes+32 && ack.WirePayloadBytes==41);
        ordinal=0; ackTotal=0; ackCopies=0; refreshed=false; dataOrdinal=[];
        mac=csr.mac.Layer(2,scheduler,csr.sim.RandomStreams(132),config,struct('Transmit',@record));
        mac.enqueue(data); input('data');
        if entry.ack_at_s>=0, scheduler.scheduleAt(entry.ack_at_s,@admitAck); end
        if entry.freeze_start_s>=0
            scheduler.scheduleAt(entry.freeze_start_s,@()freeze('Track'));
            scheduler.scheduleAt(entry.freeze_end_s,@()freeze('Search'));
        end
        scheduler.run(20);
        check('drained',mac.PendingCount,0);
        check('data_transmissions',numel(dataOrdinal),1);
        if numel(dataOrdinal)==1, check('data_ordinal',dataOrdinal,entry.expected_data_ordinal); end
        check('ack_total',ackTotal,entry.expected_ack_count);
        check('refresh_count',double(refreshed),double(entry.refresh_after_ack>0));
        function input(kind)
            inputs=[inputs;table(entry.case_id,string(kind),scheduler.Now,ordinal, ...
                'VariableNames',{'case_id','input','time_s','after_ordinal'})]; %#ok<AGROW>
        end
        function admitAck()
            ackCopies=0; assert(mac.enqueue(ack)); input('ack');
        end
        function freeze(state)
            mac.receiverChanged(state); input(lower(state));
        end
        function check(field,actual,expected)
            checks=[checks;table(entry.case_id,string(field),double(actual),double(expected), ...
                actual==expected,'VariableNames',{'case_id','field','actual','expected','pass'})]; %#ok<AGROW>
        end
        function record(envelope,~)
            ordinal=ordinal+1; kinds=string(cellfun(@(f)f.Kind,envelope.Segments,'UniformOutput',false));
            nAck=sum(kinds=="ACK"); nData=sum(kinds=="DATA");
            assert(nAck<=1 && nData<=1,'Unexpected membership.');
            ackTotal=ackTotal+nAck; ackCopies=ackCopies+nAck;
            if nData, dataOrdinal(end+1)=ordinal; end
            rows=[rows;table(entry.case_id,ordinal,scheduler.Now,scheduler.Now,nAck,nData, ...
                mac.DataQueueCount-nData,mac.AckQueueCount-double(nAck>0 && ackCopies==5), ...
                envelope.WirePayloadBytes,envelope.RateKeyKbps,mac.ReservationCounter, ...
                'VariableNames',{'case_id','ordinal','tx_time_s','sample_time_s','ack_segments', ...
                'data_segments','data_queue_after','ack_queue_after','wire_bytes','rate_kbps','reservation_after'})]; %#ok<AGROW>
            if entry.refresh_after_ack>0 && ~refreshed && ackTotal==entry.refresh_after_ack
                refreshed=true; scheduler.scheduleAt(scheduler.Now+.001,@admitAck);
            end
        end
    end
end
