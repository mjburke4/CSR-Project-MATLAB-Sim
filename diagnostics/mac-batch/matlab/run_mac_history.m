function report = run_mac_history(root,outputDir)
%RUN_MAC_HISTORY Independently replay captured seed-132 MAC inputs per node.
% The accepted queue/slot/TX implementation runs in a generated validation
% adapter whose receiver duty edges are owned by the common input tape.
% No MATLAB toolbox, network simulation, or production-source edit is needed.
if nargin<1 || isempty(root), root=fileparts(fileparts(mfilename('fullpath'))); end
if nargin<2 || isempty(outputDir), outputDir=fullfile(root,'out_mac_history'); end
if ~isfolder(outputDir), mkdir(outputDir); end
inputDir=fullfile(root,'inputs'); referenceDir=fullfile(root,'reference');
fidelity=jsondecode(fileread(fullfile(referenceDir,'fidelity.json')));
assert(isfield(fidelity,'all_passed') && fidelity.all_passed && ...
    isfield(fidelity,'source_capture') && fidelity.source_capture.exact_prefix, ...
    'mac_replay:NativeFidelity','Native capture and isolated replay fidelity gate did not pass.');
profile=jsondecode(fileread(fullfile(inputDir,'profile.json')));
bridge=checkCancellationBoundary();
writeJson(fullfile(outputDir,'cancellation_boundary_checks.json'),bridge);
assert(bridge.pass,'mac_replay:CancellationBridge','Cancellation boundary checks failed: %s',bridge.error_message);
inputs=readTextTable(fullfile(inputDir,'inputs.csv'));
frames=readTextTable(fullfile(inputDir,'frames.csv'));
drawInput=readTextTable(fullfile(inputDir,'draws.csv'));
required(inputs,{'time_ns','event_order','node','kind','peer','sequence', ...
    'frame_id','value','value2','value3','ack_bitmap','dack_bitmap'},'inputs');
required(drawInput,{'time_ns','event_order','node','ordinal','min','max','draw'},'draws');
stopNs=option(profile,'replay_stop_ns',665000000000);
compareStart=option(profile,'comparison_start_ns',657000000000);
compareStop=option(profile,'comparison_stop_ns',665000000000);
nodes=reshape(double(option(profile,'nodes',[2 4 8])),1,[]);
report=struct('test','common-input MAC scheduling history','completed',true, ...
    'behavioral_pass',true,'network_parity_claim',false,'runtime',version, ...
    'scope',['Conditional MAC scheduling under recorded receiver availability; ' ...
    'does not establish independent duty-cycle or full-network parity.'], ...
    'node_reports',[],'output_directory',outputDir,'wall_seconds',0, ...
    'native_fidelity_pass',true,'cancellation_boundary_checks',bridge);
timer=tic;
for node=nodes
    nodeDir=fullfile(outputDir,sprintf('node%d',node));
    if ~isfolder(nodeDir), mkdir(nodeDir); end
    try
        result=replayNode(node,inputs,frames,drawInput,profile,referenceDir,nodeDir,stopNs,compareStart,compareStop);
    catch caught
        result=struct('node',node,'completed',false,'behavioral_pass',false, ...
            'error_identifier',caught.identifier,'error_message',caught.message, ...
            'error_stack',caught.stack,'output_directory',nodeDir);
        writeJson(fullfile(nodeDir,'run_summary.json'),result);
    end
    if isempty(report.node_reports), report.node_reports={result};
    else, report.node_reports{end+1}=result; end
    report.completed=report.completed && result.completed;
    report.behavioral_pass=report.behavioral_pass && result.behavioral_pass;
    fprintf('MAC node %d: completed=%d, comparison pass=%d\n',node,result.completed,result.behavioral_pass);
end
report.wall_seconds=toc(timer);
report.pass=report.behavioral_pass;
writeJson(fullfile(outputDir,'run_summary.json'),report);
end

function result=checkCancellationBoundary()
% Exercise only the representation bridge. These checks do not predict TX.
result=struct('pass',false,'cases_passed',0,'error_message','');
try
    scheduler=mac_replay.Scheduler(100);
    tape=table(2,1,0,31,0,'VariableNames',{'node','ordinal','min','max','draw'});
    streams=csr.validation.ReplayStreams(tape,@()scheduler.Now,'boundary');
    config=csr.mac.Layer.defaults();
    config.SlotProfile='hist-2014-next-tslot-modulo-probe';
    mac=mac_replay.MacLayer(2,scheduler,streams,config,struct('Transmit',@ignoreTransmit));
    frame=struct('Id',uint64(1),'Kind','DATA','DestinationId',4,'Sequence',9, ...
        'Dscp',0,'AckRequired',true,'HasAckWindow',false);
    control=frame; control.Id=uint64(2); control.Kind='CONTROL';
    control.Sequence=8; control.DestinationIds=[4 8];
    control.Control=struct('Type','ROUTING');
    mac.enqueue(control); mac.enqueue(frame);
    assert(mac.replayCancelWindow(4,9,uint64(3))==1 && mac.DataQueueCount==1, ...
        'A cumulative bitmap must retain the structured frame.');
    assert(mac.cancel(4,8)==1 && mac.DataQueueCount==0, ...
        'Production direct cancellation must remain unchanged.');
    result.cases_passed=result.cases_passed+1;
    frame.Sequence=65535; mac.enqueue(frame);
    assert(mac.replayCancelWindow(4,0,uint64(2))==1 && mac.DataQueueCount==0, ...
        'Window age must wrap in the 16-bit sequence space.');
    result.cases_passed=result.cases_passed+1;
    frame.Sequence=37; mac.enqueue(frame);
    high=decimalUint64('9223372036854775808');
    assert(high==bitshift(uint64(1),63) && mac.replayCancelWindow(4,100,high)==1, ...
        'Bit 63 must survive decimal conversion and queue cancellation.');
    result.cases_passed=result.cases_passed+1;
    frame.Sequence=8; mac.enqueue(frame); mac.enqueue(control);
    rejected=false;
    try
        mac.replayCancelWindow(4,8,uint64(1));
    catch caught
        rejected=strcmp(caught.identifier,'mac_replay:AmbiguousCancellation');
    end
    assert(rejected && mac.DataQueueCount==2,'Ambiguous protected keys must reject without queue mutation.');
    result.cases_passed=result.cases_passed+1;
    result.pass=true;
catch caught
    result.error_message=caught.message; result.error_identifier=caught.identifier;
end
end
function ignoreTransmit(~,~)
error('mac_replay:BoundaryCheck','A cancellation bridge check unexpectedly transmitted.');
end

function report=replayNode(node,inputs,frames,drawInput,profile,referenceDir,out,stopNs,compareStart,compareStop)
inputs=inputs(numberColumn(inputs,'node')==node & numberColumn(inputs,'time_ns')<stopNs,:);
inputTimes=numberColumn(inputs,'time_ns'); inputOrders=numberColumn(inputs,'event_order');
assert(numel(unique(inputOrders))==height(inputs),'mac_replay:Order','Input event orders are not unique.');
assert(all(inputTimes>=0 & fix(inputTimes)==inputTimes & inputTimes<=flintmax), ...
    'mac_replay:Time','Input times must be exact nonnegative integer nanoseconds.');
[~,order]=sortrows([inputTimes inputOrders],[1 2]); inputs=inputs(order,:);
tape=drawInput(numberColumn(drawInput,'node')==node & numberColumn(drawInput,'time_ns')<stopNs,:);
for name={'time_ns','event_order','node','ordinal','min','max','draw'}
    tape.(name{1})=numberColumn(tape,name{1});
end
[~,order]=sort(tape.ordinal); tape=tape(order,:);
scheduler=mac_replay.Scheduler(2000000);
streams=csr.validation.ReplayStreams(tape,@()scheduler.Now,sprintf('node%d',node));
config=csr.mac.Layer.defaults();
config.SlotProfile=char(option(profile,'slot_profile','hist-2014-next-tslot-modulo-probe'));
assert(strcmp(config.SlotProfile,'hist-2014-next-tslot-modulo-probe'), ...
    'mac_replay:Profile','This capture requires the historical campus modulo-probe profile.');
config.ActiveNodes=double(option(profile,'initial_active_nodes',1));
config.ReportedActiveNodes=double(option(profile,'initial_reported_nodes',0));
config.DutyCycleEnabled=true;
config.ReservationSlotOverride=-1;
state='Search'; syncPresent=false; mac=[]; localActive=config.ActiveNodes; reported=config.ReportedActiveNodes;
txTemplate=struct('time_ns',0,'node',node,'consumed_slot',-1,'next_slot',-1, ...
    'wirebytes',0,'rate',0,'power',0,'preamble_bits',0,'duration_ns',0,'frame_ids','');
txRows=repmat(txTemplate,0,1);
eventTemplate=struct('event_index',0,'time_ns',0,'node',node,'event','', ...
    'frame_id',0,'peer',0,'sequence',0,'state','','data_depth',0,'ack_depth',0, ...
    'reservation_slot',-1,'reservation_counter',-1,'consumed_slot',-1, ...
    'preparation_active',false,'holdoff_over',false,'sync_present',false,'detail','');
eventRows=repmat(eventTemplate,0,1);
inputTemplate=struct('event_order',0,'time_ns',0,'kind','','applied',false,'reason','');
inputRows=repmat(inputTemplate,0,1);
callbacks=struct('Transmit',@transmit,'Sent',@sent,'Event',@observe, ...
    'ReceiverState',@getReceiver,'SetReceiverState',@setReceiver,'HasSync',@hasSync);
mac=mac_replay.MacLayer(node,scheduler,streams,config,callbacks);
frameMap=containers.Map('KeyType','double','ValueType','any');
for k=1:height(frames)
    row=table2struct(frames(k,:));
    if isfield(row,'node') && asNumber(row.node)~=node, continue; end
    frame=makeFrame(row); frameMap(double(frame.Id))=frame;
end
for k=1:height(inputs)
    row=table2struct(inputs(k,:));
    scheduler.scheduleAt(asNumber(row.time_ns)/1e9,@()applyInput(row));
end
report=struct('node',node,'completed',false,'behavioral_pass',false, ...
    'error_identifier','','error_message','','output_directory',out, ...
    'comparison_start_ns',compareStart,'comparison_stop_ns',compareStop);
timer=tic;
try
    mac.start();
    % The native fixture stops before callbacks at its stop timestamp.
    % All input times are integral ns; executing through stop-1 ns gives the
    % same half-open interval without changing any callback timestamp.
    scheduler.run((stopNs-1)/1e9);
    report.completed=true;
catch caught
    report.error_identifier=caught.identifier; report.error_message=caught.message;
    report.error_stack=caught.stack;
end
report.wall_seconds=toc(timer); report.last_time_ns=round(scheduler.Now*1e9);
tx=struct2table(txRows); events=struct2table(eventRows); applied=struct2table(inputRows);
draws=streams.draws(); usage=streams.usage();
writetable(tx,fullfile(out,'tx.csv')); writetable(events,fullfile(out,'mac_events.csv'));
writetable(applied,fullfile(out,'input_application.csv'));
writetable(draws,fullfile(out,'draws.csv')); writetable(usage,fullfile(out,'draw_usage.csv'));
writeJson(fullfile(out,'final_state.json'),mac.snapshot());
report.inputs_supplied=height(inputs); report.inputs_processed=height(applied);
report.unused_draws=sum(usage.unused); report.transmissions=height(tx);
report.receiver_inputs_ignored_during_own_tx=sum(~applied.applied & strcmp(applied.reason,'own_tx_active'));
try
    refTx=readTextTable(fullfile(referenceDir,'tx.csv'));
    refTx=refTx(numberColumn(refTx,'node')==node & numberColumn(refTx,'time_ns')<stopNs,:);
    fields={'time_ns','node','consumed_slot','next_slot','wirebytes','rate','power','preamble_bits','duration_ns','frame_ids'};
    comparison=compareRows(refTx,tx,fields,'all TX events from natural startup');
    selected=tx.time_ns>=compareStart & tx.time_ns<compareStop;
    refSelected=numberColumn(refTx,'time_ns')>=compareStart & numberColumn(refTx,'time_ns')<compareStop;
    window=compareRows(refTx(refSelected,:),tx(selected,:),fields,'target 657–665 second TX events');
    refDrawPath=fullfile(referenceDir,'draws.csv');
    if isfile(refDrawPath)
        refDraw=readTextTable(refDrawPath);
        refDraw=refDraw(numberColumn(refDraw,'node')==node & numberColumn(refDraw,'time_ns')<stopNs,:);
    else
        refDraw=drawInput(numberColumn(drawInput,'node')==node & numberColumn(drawInput,'time_ns')<stopNs,:);
    end
    drawComparison=compareRows(refDraw,draws,{'time_ns','node','ordinal','min','max','draw'},'raw draw timing, order and support');
catch caught
    comparison=struct('pass',false,'message',caught.message,'error_identifier',caught.identifier);
    window=struct('pass',false,'message','Reference comparison could not complete.');
    drawComparison=window;
end
report.warmup_tx_pass=comparison.pass; report.target_tx_pass=window.pass;
report.raw_draw_pass=drawComparison.pass;
report.behavioral_pass=report.completed && comparison.pass && window.pass && ...
    drawComparison.pass && report.unused_draws==0 && report.inputs_processed==report.inputs_supplied;
writeJson(fullfile(out,'tx_comparison.json'),comparison);
writeJson(fullfile(out,'target_comparison.json'),window);
writeJson(fullfile(out,'draw_comparison.json'),drawComparison);
writeJson(fullfile(out,'run_summary.json'),report);

    function setReceiver(next)
        state=char(next);
    end
    function current=getReceiver()
        current=state;
    end
    function present=hasSync()
        present=syncPresent;
    end
    function transmit(frame,duration)
        state='Tx';
        streams.resolve(node,'advertise',mac.LastAdvertisedReservation);
        row=txTemplate; row.time_ns=round(scheduler.Now*1e9);
        row.consumed_slot=mac.LastOpportunitySlot; row.next_slot=frame.ReservationSlot;
        row.wirebytes=frame.WirePayloadBytes; row.rate=frame.RateKeyKbps;
        row.power=frame.TxPowerDbm; row.duration_ns=round(duration*1e9);
        if strcmp(frame.Preamble,'long'), row.preamble_bits=7888; else, row.preamble_bits=104; end
        row.frame_ids=strjoin(cellfun(@(f)sprintf('%.0f',double(f.Id)),frame.Segments,'UniformOutput',false),';');
        txRows(end+1,1)=row;
    end
    function sent(frame)
        observe('mac_sent',frame,struct());
    end
    function observe(name,frame,details)
        if isempty(mac), return; end
        if strcmp(name,'mac_prepare'), streams.resolve(node,'prepare',mac.ReservationSlot); end
        row=eventTemplate; row.event_index=numel(eventRows)+1;
        row.time_ns=round(scheduler.Now*1e9); row.event=char(name); row.state=mac.State;
        row.data_depth=mac.DataQueueCount; row.ack_depth=mac.AckQueueCount;
        row.reservation_slot=mac.ReservationSlot; row.reservation_counter=mac.ReservationCounter;
        row.consumed_slot=mac.LastOpportunitySlot; row.preparation_active=mac.PreparationActive;
        row.holdoff_over=mac.HoldoffOver; row.sync_present=syncPresent;
        if isfield(frame,'Id'), row.frame_id=double(frame.Id); end
        if isfield(frame,'DestinationId'), row.peer=double(frame.DestinationId); end
        if isfield(frame,'Sequence'), row.sequence=double(frame.Sequence); end
        row.detail=jsonencode(details); eventRows(end+1,1)=row;
    end
    function applyInput(input)
        appliedRow=inputTemplate; appliedRow.event_order=asNumber(input.event_order);
        appliedRow.time_ns=round(scheduler.Now*1e9); appliedRow.kind=char(input.kind);
        appliedRow.applied=true; appliedRow.reason='applied';
        peer=0; if strlength(string(input.peer))>0, peer=asNumber(input.peer); end
        kind=char(input.kind);
        switch kind
            case 'enqueue'
                id=asNumber(input.frame_id);
                assert(isKey(frameMap,id),'mac_replay:Frame','Unknown frame ID %.0f.',id);
                frame=frameMap(id); frame.DestinationId=peer;
                frame.Dscp=asNumber(input.value); frame.AckRequired=logical(asNumber(input.value2));
                accepted=mac.enqueue(frame);
                if ~accepted, appliedRow.reason='queue_rejected'; end
            case 'receiver_state'
                if strcmp(mac.State,'Tx')
                    % A replay input cannot terminate or overwrite predicted TX.
                    appliedRow.applied=false; appliedRow.reason='own_tx_active';
                else
                    state=normalizeState(input.value); mac.receiverChanged(state);
                end
            case 'sync'
                syncPresent=logical(asNumber(input.value));
            case 'received'
                heard=asNumber(input.value);
                assert(abs(heard-scheduler.Now)<=0.5001e-9,'mac_replay:HeardTime', ...
                    'Received boundary timestamp differs from native tRx.');
                frame=struct('SourceId',peer);
                slot=asNumber(input.value3);
                if slot>=0, frame.ReservationSlot=slot; end
                mac.receive(frame,struct('Success',true));
            case 'active'
                localActive=max(1,asNumber(input.value)); mac.setActiveNodes(localActive,reported);
            case 'reported'
                reported=max(reported,asNumber(input.value)); mac.setActiveNodes(localActive,reported);
            case 'cancel_ack'
                bitmap=bitor(decimalUint64(input.ack_bitmap),decimalUint64(input.dack_bitmap));
                base=asNumber(input.sequence);
                removed=mac.replayCancelWindow(peer,base,bitmap);
                observe('boundary_cancel_window',struct(),struct('Peer',peer, ...
                    'BaseSequence',base,'Removed',removed));
            case 'cancel_type'
                mac.cancelControl(peer,controlType(asNumber(input.value)));
            otherwise
                error('mac_replay:InputKind','Unsupported input kind %s.',kind);
        end
        inputRows(end+1,1)=appliedRow;
        observe(['input_' kind],struct(),struct('EventOrder',appliedRow.event_order,'Applied',appliedRow.applied,'Reason',appliedRow.reason));
    end
end

function frame=makeFrame(row)
% Decoded fields come from the native boundary, never from a MATLAB oracle.
frame=struct('Id',uint64(numberField(row,{'frame_id','id'})), ...
    'SourceId',numberField(row,{'source','src'}),'DestinationId',numberField(row,{'destination','dest','dst'}), ...
    'Sequence',numberField(row,{'sequence','seq'}),'Type',numberField(row,{'type'}), ...
    'WirePayloadBytes',numberField(row,{'wirebytes','wire_bytes'}), ...
    'ApplicationPayloadBytes',numberField(row,{'application_bytes','appbytes','payload_bytes'},0), ...
    'Dscp',numberField(row,{'dscp'}),'AckRequired',logical(numberField(row,{'ackable'})), ...
    'RateKeyKbps',numberField(row,{'effective_rate','rate','speed_key'}), ...
    'TxPowerDbm',numberField(row,{'effective_power','tx_power_dbm','power','tx_dbm','txpower'}), ...
    'HasAckWindow',logical(numberField(row,{'has_window','has_ack_window'})), ...
    'Kind','DATA','Preamble','long');
if numberField(row,{'is_ack'},double(frame.Type==1)), frame.Kind='ACK';
elseif numberField(row,{'is_dack'},double(frame.Type==2)), frame.Kind='DACK';
elseif frame.Type>2, frame.Kind='CONTROL'; frame.Control=struct('Type',controlType(frame.Type)); end
if isfield(row,'destination_sequences') && strlength(row.destination_sequences)>0
    entries=split(string(row.destination_sequences),';'); targets=zeros(1,numel(entries));
    for k=1:numel(entries), pair=split(entries(k),':'); targets(k)=str2double(pair(1)); end
    frame.DestinationIds=targets;
end
assert(logical(numberField(row,{'has_link_control'},0)), ...
    'mac_replay:FrameControl','Every fixture frame must carry explicit link control.');
assert(any(frame.RateKeyKbps==[8 16 32 64 128 500 1000]), ...
    'mac_replay:FrameRate','Frame %.0f has no supported explicit rate.',double(frame.Id));
assert(isfinite(frame.TxPowerDbm),'mac_replay:FramePower','Frame has invalid explicit TX power.');
end

function comparison=compareRows(expected,actual,fields,label)
required(expected,fields,'reference'); required(actual,fields,'observed');
comparison=struct('pass',true,'message',[label ' match exactly.'], ...
    'expected_rows',height(expected),'actual_rows',height(actual),'first_difference',[]);
count=min(height(expected),height(actual));
for k=1:count
    for n=1:numel(fields)
        name=fields{n}; left=expected.(name)(k,:); right=actual.(name)(k,:);
        if strcmp(name,'frame_ids')
            equal=strcmp(char(string(left)),char(string(right)));
        else
            a=asNumber(left); b=asNumber(right);
            equal=isequal(a,b);
            if strcmp(name,'power'), equal=isfinite(a)&&isfinite(b)&&abs(a-b)<=1e-9; end
        end
        if ~equal
            comparison.pass=false; comparison.message=sprintf('%s differ at row %d, field %s.',label,k,name);
            comparison.first_difference=struct('row',k,'field',name,'expected',string(left),'actual',string(right), ...
                'expected_row',table2struct(expected(k,:)),'actual_row',table2struct(actual(k,:)));
            return;
        end
    end
end
if height(expected)~=height(actual)
    comparison.pass=false; comparison.message=sprintf('%s have unequal row counts (%d expected, %d observed).',label,height(expected),height(actual));
    comparison.first_difference=struct('row',count+1,'field','row_count');
end
end

function value=controlType(type)
% Names below classify native wire types only. No HOP payload interpretation
% is needed by MAC; immediate-tag cancellation uses KEY_REQUEST (native 8).
types=[4 5 6 7 8 9]; names={'DISCOVER','NEIGHBOR_CHECK','ROUTING','SNMP','KEY_REQUEST','KEY_UPDATE'};
index=find(types==type,1);
assert(~isempty(index),'mac_replay:ControlType','Unsupported native control type %g.',type);
value=names{index};
end
function state=normalizeState(value)
switch lower(char(value))
    case {'idle','0'}, state='Idle';
    case {'search','1'}, state='Search';
    case {'track','2'}, state='Track';
    otherwise, error('mac_replay:ReceiverState','Receiver input must be Idle, Search or Track.');
end
end
function value=decimalUint64(text)
digits=char(string(text)); if isempty(digits), value=uint64(0); return; end
assert(all(digits>='0' & digits<='9'),'mac_replay:Bitmap','Bitmap must be an unsigned decimal integer.');
value=uint64(0); limit=idivide(intmax('uint64'),uint64(10),'floor'); last=rem(intmax('uint64'),uint64(10));
for digit=digits
    next=uint64(double(digit)-double('0'));
    assert(value<limit || (value==limit && next<=last),'mac_replay:Bitmap','Bitmap exceeds uint64.');
    value=value*uint64(10)+next;
end
end
function value=numberField(row,names,varargin)
for k=1:numel(names)
    if isfield(row,names{k}), value=asNumber(row.(names{k})); return; end
end
if ~isempty(varargin), value=varargin{1}; return; end
error('mac_replay:Schema','Missing native frame field %s.',strjoin(names,'/'));
end
function value=asNumber(value)
if iscell(value), value=value{1}; end
if ~isnumeric(value) && ~islogical(value), value=str2double(string(value)); end
value=double(value);
assert(isscalar(value) && isfinite(value),'mac_replay:Number','Required numeric value is missing or nonfinite.');
end
function value=numberColumn(table,name)
value=table.(name); if ~isnumeric(value), value=str2double(string(value)); end
value=double(value);
assert(all(isfinite(value)),'mac_replay:Number','Column %s contains missing or nonfinite numbers.',name);
end
function table=readTextTable(file)
options=detectImportOptions(file,'VariableNamingRule','preserve');
options=setvartype(options,options.VariableNames,'string');
options=setvaropts(options,options.VariableNames,'WhitespaceRule','preserve');
table=readtable(file,options);
% Empty CSV fields are deliberate optional values; avoid propagating missing.
for k=1:width(table), name=table.Properties.VariableNames{k}; table.(name)(ismissing(table.(name)))=""; end
end
function required(table,fields,label)
assert(all(ismember(fields,table.Properties.VariableNames)),'mac_replay:Schema','Incomplete %s schema.',label);
end
function value=option(input,name,fallback)
if isfield(input,name), value=input.(name); else, value=fallback; end
end
function writeJson(file,value)
fid=fopen(file,'w'); assert(fid>=0,'mac_replay:Output','Cannot write %s.',file);
cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
end
