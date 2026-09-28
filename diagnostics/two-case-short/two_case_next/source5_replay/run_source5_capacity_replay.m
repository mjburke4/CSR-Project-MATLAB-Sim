function report=run_source5_capacity_replay(fixtureDir,outputDir,policy)
%RUN_SOURCE5_CAPACITY_REPLAY Native-timed first-16 source-5 HOP boundary.
% Production HOP admission/retry/ACK logic runs with native actual TX and
% feedback times as supplied inputs. A test-owned FIFO models only the local
% NWK offer/wake boundary. Native HOP sequences differ because earlier
% controls are outside this bounded fixture; compare attempt identity and
% capacity, not sequence numbers. This is not a full NWK/PHY/MAC replay.
if nargin<3 || isempty(policy), policy='actual-tx'; end
if nargin<1 || isempty(fixtureDir)
    fixtureDir=fullfile(fileparts(mfilename('fullpath')),'fixtures');
end
if nargin<2 || isempty(outputDir)
    outputDir=fullfile(fileparts(mfilename('fullpath')),'out_capacity');
end
if ~any(strcmp(policy,{'actual-tx','native-provisional'}))
    error('source5:Policy','Expected a supported HOP retry policy.');
end
if ~isfolder(outputDir), mkdir(outputDir); end
manifest=jsondecode(fileread(fullfile(fixtureDir,'capacity_manifest.json')));
assert(strcmp(manifest.schema,'source5-native-capacity-boundary-v1') && ...
    manifest.seed==132 && manifest.unique_apps==16 && ...
    ~manifest.full_nwk_or_mac_state_replayed,'source5:Manifest','Wrong native boundary fixture.');
assert(strcmp(csr.validation.Artifacts.sha256(fullfile(fixtureDir,'capacity_events.csv')), ...
        manifest.capacity_events_sha256) && ...
    strcmp(csr.validation.Artifacts.sha256(fullfile(fixtureDir,'native_admission_reference.csv')), ...
        manifest.native_admission_reference_sha256), ...
    'source5:FixtureHash','Native capacity inputs or oracle changed.');
inputs=readtable(fullfile(fixtureDir,'capacity_events.csv'),'TextType','string');
native=readtable(fullfile(fixtureDir,'native_admission_reference.csv'),'TextType','string');
assert(height(inputs)==manifest.event_count && ...
    sum(strcmp(inputs.kind,'sent'))==manifest.sent_count && ...
    sum(strcmp(inputs.kind,'feedback_ack'))==manifest.feedback_ack_count && ...
    sum(strcmp(inputs.kind,'feedback_dack'))==manifest.feedback_dack_count, ...
    'source5:FixtureCoverage','Native capacity event counts changed.');
require(inputs,{'time_ns','event_order','kind','attempt_index','app_sequence'});
require(native,{'time_ns','attempt_index','pending_before','pending_after', ...
    'outstanding_before','outstanding_after','threshold'});
assert(height(native)==16 && isequal(double(native.attempt_index),(1:16)'), ...
    'source5:AdmitOracle','Native oracle must contain the ordered 16 admissions.');
times=double(inputs.time_ns); orders=double(inputs.event_order);
assert(all(isfinite(times) & times>=300e9 & times<330e9 & times==fix(times)) && ...
    numel(unique(orders))==height(inputs),'source5:InputOrder','Input time/order invalid.');
[~,order]=sortrows([times orders],[1 2]); inputs=inputs(order,:);
assert(sum(strcmp(inputs.kind,'local_offer'))==16 && ...
    sum(strcmp(inputs.kind,'feedback_ack'))+sum(strcmp(inputs.kind,'feedback_dack'))>=1, ...
    'source5:InputCoverage','Native HOP boundary inputs incomplete.');
scheduler=csr.sim.EventScheduler(1000000);
% Exactly 1/36 MHz; the source NWK first pump and HOP post-feedback wake
% are observed one TIC after offer/feedback, respectively.
ticSeconds=1/36e6;
pending=cell(0,1); queued=cell(0,1); sendCounts=zeros(1,16);
firstOffers=nan(1,16); nativeSeq=zeros(1,16); appIds=zeros(1,16,'uint64');
admissionTemplate=struct('time_ns',0,'attempt_index',0,'app_sequence',0, ...
    'local_hop_sequence',0,'pending_before',0,'pending_after',0, ...
    'outstanding_before',0,'outstanding_after',0,'threshold',0);
admissions=repmat(admissionTemplate,0,1);
eventTemplate=struct('time_ns',0,'kind','','attempt_index',0,'local_hop_sequence',0, ...
    'queued_copies',0,'pending_data',0,'peer_outstanding',0,'peer_threshold',0, ...
    'nwk_waiting',0,'reason','');
observed=repmat(eventTemplate,0,1);
hop=csr.hop.Layer(5,scheduler,[],struct('DataQueuedRetryPolicy',policy), ...
    struct('EnqueueMac',@enqueue,'CancelMac',@cancel, ...
    'NsdpRelease',@release,'Terminal',@terminal,'Wake',@wake,'Event',@hopEvent));
for k=1:height(inputs)
    row=table2struct(inputs(k,:));
    scheduler.scheduleAt(double(row.time_ns)/1e9,@()inputEvent(row));
end
report=struct('schema','source5-capacity-replay-v1','completed',false,'pass',false, ...
    'policy',policy,'scope',['Native first-16 source-5 app offers, actual DATA TX and ' ...
    'feedback times supplied to production HOP. Test-owned NWK FIFO; no private NWK ' ...
    'state, ACK workload or PHY reception is replayed.'], ...
    'native_parity_gate','HOP-boundary admission/capacity only', ...
    'full_network_parity_claim',false,'production_hop_executed',true, ...
    'native_input_event_count',height(inputs),'native_admission_count',height(native), ...
    'runtime',version,'error_identifier','','error_message','');
try
    scheduler.run(329.999999999);
    assert(all(isfinite(firstOffers)),'source5:Offer','Exactly 16 app offers required.');
    report.completed=true;
catch caught
    report.error_identifier=caught.identifier; report.error_message=caught.message;
    report.error_stack=caught.stack;
end
actual=struct2table(admissions); events=struct2table(observed);
writetable(actual,fullfile(outputDir,'admissions.csv'));
writetable(events,fullfile(outputDir,'events.csv'));
compare=struct('pass',false,'first_difference',struct(),'reference_count',height(native), ...
    'observed_count',height(actual));
if report.completed
    compare=compareAdmission(native,actual);
end
report.comparison=compare;
report.pass=report.completed && compare.pass;
report.queued_frame_copies=numel(queued);
report.actual_tx_indications=sum(sendCounts);
report.final_hop=hop.stats();
writeJson(fullfile(outputDir,'report.json'),report);

    function inputEvent(row)
        attempt=double(row.attempt_index);
        assert(isfinite(attempt) && attempt>=1 && attempt<=16 && fix(attempt)==attempt, ...
            'source5:Attempt','Unknown native attempt.');
        switch char(row.kind)
            case 'local_offer'
                assert(isnan(firstOffers(attempt)),'source5:DuplicateOffer','Repeated first offer.');
                firstOffers(attempt)=scheduler.Now;
                nativeSeq(attempt)=double(row.app_sequence);
                appIds(attempt)=uint64(attempt);
                app=struct('Id',uint64(attempt),'SourceId',5,'DestinationId',1, ...
                    'GeneratedSeconds',scheduler.Now,'ApplicationPayloadBytes',185,'Dscp',0);
                pending{end+1}=struct('App',app,'Submitted',false); %#ok<AGROW>
                scheduler.scheduleAt(scheduler.Now+ticSeconds,@pump);
                record('local_offer',attempt,0,'native_app_send');
            case 'sent'
                index=nextUnsent(attempt);
                assert(index>0,'source5:SentWithoutQueue','Native actual DATA TX lacks an HOP-queued copy.');
                entry=queued{index}; entry.Sent=true; queued{index}=entry;
                sendCounts(attempt)=sendCounts(attempt)+1;
                hop.notifySent(entry.Frame);
                record('actual_tx_input',attempt,double(entry.Frame.Sequence),'native_tx_start');
            case {'feedback_ack','feedback_dack'}
                seq=sequenceForAttempt(attempt);
                assert(seq>0,'source5:FeedbackWithoutOwner','Native feedback lacks an admitted owner.');
                isDack=strcmp(char(row.kind),'feedback_dack');
                a=uint64(~isDack); d=uint64(isDack);
                feedback=csr.hop.Frames.acknowledgment(1,5,uint16(seq),a,d, ...
                    struct('HasAckWindow',true));
                hop.receive(feedback);
                record(char(row.kind),attempt,seq,'native_hop_completion');
            otherwise
                error('source5:InputKind','Unrecognized native input kind %s.',char(row.kind));
        end
    end
    function index=nextUnsent(attempt)
        index=0;
        for n=1:numel(queued)
            entry=queued{n};
            if double(entry.Frame.App.Id)==attempt && ~entry.Sent, index=n; return; end
        end
    end
    function seq=sequenceForAttempt(attempt)
        seq=0;
        for n=1:numel(queued)
            entry=queued{n};
            if double(entry.Frame.App.Id)==attempt
                seq=double(entry.Frame.Sequence); return;
            end
        end
    end
    function accepted=enqueue(frame)
        queued{end+1}=struct('Frame',frame,'Sent',false); accepted=true;
        record('hop_enqueue',double(frame.App.Id),double(frame.Sequence),'accepted_test_boundary');
    end
    function cancel(~,~)
        % Native MAC queue content is *not* reconstructed here. HOP retry
        % copies remain in the transcript; later sent inputs select unsent.
    end
    function release(app,reason)
        for n=numel(pending):-1:1
            if pending{n}.App.Id==app.Id
                pending(n)=[];
                record('custody_release',double(app.Id),0,char(reason));
                return;
            end
        end
        error('source5:UnownedRelease','HOP released a packet absent from the test NWK FIFO.');
    end
    function terminal(~,~,~)
        % Real NWK terminal observes that releaseFromHop already transferred
        % custody. The test FIFO performs removal in release().
    end
    function wake()
        scheduler.scheduleAt(scheduler.Now,@pump);
        record('hop_wake',0,0,'post_feedback_tic');
    end
    function hopEvent(name,frame,details)
        attempt=0; seq=0;
        if isfield(frame,'App'), attempt=double(frame.App.Id); end
        if isfield(frame,'Sequence'), seq=double(frame.Sequence); end
        record(['hop_' char(name)],attempt,seq,jsonencode(details));
    end
    function pump()
        for n=1:numel(pending)
            entry=pending{n};
            if entry.Submitted, continue; end
            if ~hop.canSend(1), continue; end
            before=hop.admission(1);
            [accepted,frame]=hop.send(entry.App,1,struct('RateKeyKbps',8, ...
                'TxPowerDbm',22,'Preamble','short'));
            assert(accepted,'source5:UnexpectedRejection','HOP rejected its own allowed offer.');
            pending{n}.Submitted=true;
            after=hop.admission(1);
            row=admissionTemplate; row.time_ns=round(scheduler.Now*1e9);
            row.attempt_index=double(entry.App.Id);
            row.app_sequence=nativeSeq(row.attempt_index);
            row.local_hop_sequence=double(frame.Sequence);
            row.pending_before=before.PendingData; row.pending_after=after.PendingData;
            row.outstanding_before=before.NeighborOutstanding;
            row.outstanding_after=after.NeighborOutstanding;
            row.threshold=before.NeighborThreshold;
            admissions(end+1,1)=row; %#ok<AGROW>
            record('network_hop_admit',double(entry.App.Id),double(frame.Sequence),'production_hop');
        end
    end
    function record(kind,attempt,seq,reason)
        state=hop.admission(1); waiting=0;
        for n=1:numel(pending), waiting=waiting+double(~pending{n}.Submitted); end
        row=eventTemplate; row.time_ns=round(scheduler.Now*1e9);
        row.kind=char(kind); row.attempt_index=attempt; row.local_hop_sequence=seq;
        row.queued_copies=numel(queued); row.pending_data=state.PendingData;
        row.peer_outstanding=state.NeighborOutstanding;
        row.peer_threshold=state.NeighborThreshold; row.nwk_waiting=waiting;
        row.reason=char(reason); observed(end+1,1)=row; %#ok<AGROW>
    end
end

function result=compareAdmission(native,actual)
result=struct('pass',true,'first_difference',struct(), ...
    'reference_count',height(native),'observed_count',height(actual));
fields={'time_ns','attempt_index','app_sequence','pending_before','pending_after', ...
    'outstanding_before','outstanding_after','threshold'};
if height(native)~=height(actual)
    result.pass=false;
    result.first_difference=struct('kind','row_count','expected',height(native), ...
        'actual',height(actual)); return
end
for row=1:height(native)
    for k=1:numel(fields)
        name=fields{k}; expected=double(native.(name)(row)); seen=double(actual.(name)(row));
        if expected~=seen
            result.pass=false;
            result.first_difference=struct('kind','field','row',row,'field',name, ...
                'expected',expected,'actual',seen); return
        end
    end
end
end

function require(t,fields)
assert(all(ismember(fields,t.Properties.VariableNames)), ...
    'source5:Schema','Native capacity fixture has missing columns.');
end
function writeJson(file,value)
fid=fopen(file,'w'); assert(fid>=0,'source5:Output','Cannot write %s.',file);
cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
end
