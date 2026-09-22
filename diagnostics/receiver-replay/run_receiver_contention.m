function report=run_receiver_contention(inputDir,outputDir)
%RUN_RECEIVER_CONTENTION Replay seed-132 node-2 RF inputs through the real PHY.
% From this directory: report = run_receiver_contention;
% Requires MATLAB R2025a or newer; no additional toolbox or Python is needed.
% This receiver-boundary test does not recreate network queues or change CSR.
root=fileparts(mfilename('fullpath')); here=fullfile(root,'matlab');
if nargin<1 || isempty(inputDir), inputDir=fullfile(root,'inputs'); end
if nargin<2 || isempty(outputDir)
    outputDir=fullfile(root,['out_rc_' datestr(now,'yyyymmdd_HHMMSS')]);
end
core=fullfile(root,'core');
if ~isfolder(core), error('receiver_replay:CoreMissing','Bundled accepted core missing: %s',core); end
oldPath=path; cleanup=onCleanup(@()path(oldPath)); %#ok<NASGU>
addpath(core,here,'-begin');
expected=fullfile(core,'+csr','+phy','SignalEngine.m');
if ~strcmp(which('csr.phy.SignalEngine'),expected)
    error('receiver_replay:ShadowedCore','Another CSR tree shadows the bundled accepted core.');
end
if ~isfolder(outputDir), mkdir(outputDir); end
binding=verifyBinding(root,inputDir);
writeJson(fullfile(outputDir,'runtime_binding.json'),binding);
if ~binding.pass
    report=struct('completed',false,'behavioral_pass',false,'network_parity_claim',false, ...
        'error_identifier','receiver_replay:Binding','error_message',binding.message,'output_directory',outputDir);
    writeJson(fullfile(outputDir,'run_summary.json'),report);
    report.archive=archiveOutput(outputDir);
    fprintf('Receiver replay did not run: %s\nReturn: %s\n',binding.message,report.archive);
    return;
end
profile=jsondecode(fileread(fullfile(inputDir,'profile.json')));
assert(strcmpi(profile.initial_state,'IDLE') && strcmp(profile.duty_cycle,'opnet-aligned'), ...
    'receiver_replay:Profile','This fixture requires natural Idle/opnet-aligned startup.');
inputs=readtable(fullfile(inputDir,'inputs.csv'),'TextType','string','VariableNamingRule','preserve');
children=readtable(fullfile(inputDir,'children.csv'),'TextType','string','VariableNamingRule','preserve');
controls=readtable(fullfile(inputDir,'controls.csv'),'TextType','string','VariableNamingRule','preserve');
required={'event_order','time_ns','kind','signal_id','source','dest','sequence', ...
    'wirebytes','preamblebits','packetbits','rate','tx_dbm','rx_dbm','noise_watts', ...
    'distance_m','start_s','end_s','preamble_end_s','end_ns','preamble_end_ns','sync_threshold_db','slot','ackable', ...
    'channel_matched','queues_empty_at_end','active_nodes'};
assert(all(ismember(required,inputs.Properties.VariableNames)),'receiver_replay:Inputs','Incomplete RF input schema.');
assert(numel(unique(inputs.event_order))==height(inputs),'receiver_replay:Inputs','Duplicate event_order.');
inputs=sortrows(inputs,{'time_ns','event_order'});
node=profile.receiver_id; startNs=profile.warmup_start_ns;
stopNs=profile.replay_stop_ns; compareStart=profile.comparison_start_ns;
compareStop=profile.comparison_stop_ns;
assert(all(inputs.time_ns>=startNs),'receiver_replay:Inputs','Input precedes replay warmup start.');
radio=csr.phy.RadioProfile.defaults();
radio.TxBaseFrequencyHz=profile.receiver_frequency_hz;
radio.RxBaseFrequencyHz=profile.receiver_frequency_hz;
radio.RxBwHz=profile.bandwidth_hz; radio.TxBwHz=profile.bandwidth_hz;
radio.NoiseFloorDbm=profile.noise_floor_dbm; radio.EccThreshold=profile.ecc_threshold;
config=struct('Nodes',struct('Id',node,'RadioProfile',radio,'PositionMeters',[0 0 profile.antenna_height_m]), ...
    'Mac',csr.mac.Layer.defaults());
config.Mac.ActiveNodes=profile.active_nodes;
config.Mac.ReportedActiveNodes=profile.active_nodes;
scheduler=receiver_replay.Scheduler(1000000);
scheduler.run(startNs/1e9);
streams=csr.sim.RandomStreams(132); % PHY/SYNC draws are supplied explicitly below.
tape=receiver_replay.DrawTape(fullfile(inputDir,'draws.csv'));
template=struct('event_index',0,'time_ns',0,'signal_id',0,'stage','', ...
    'source',0,'hop_sequence',0,'result','','reason','','state_before','','state_after','','raw_reason','');
rows=repmat(template,0,1); diagnostics=repmat(template,0,1);
engine=[]; mac=[]; previousState='Search'; activeOwnSignal=0;
engine=receiver_replay.SignalEngine(config,scheduler,streams,@receive,@trace,@stateChanged);
engine.setReplayDrawTape(tape);
callbacks=struct('Transmit',@transmit,'ReceiverState',@()engine.state(node), ...
    'SetReceiverState',@(state)engine.setReceiverState(node,state), ...
    'HasSync',@()engine.hasSync(node),'Event',@macEvent);
mac=receiver_replay.MacLayer(node,scheduler,streams,config,callbacks);
mac.start();
jobs=struct('Time',{},'Order',{},'Callback',{});
for k=1:height(inputs)
    input=table2struct(inputs(k,:)); input.receiver=node;
    if input.time_ns>=stopNs, continue; end
    frame=makeFrame(input,children);
    jobs(end+1)=struct('Time',input.time_ns,'Order',input.event_order,'Callback',@()applyInput(input,frame)); %#ok<AGROW>
end
for k=1:height(controls)
    control=table2struct(controls(k,:));
    if control.time_ns<startNs || control.time_ns>=stopNs, continue; end
    jobs(end+1)=struct('Time',control.time_ns,'Order',control.event_order,'Callback',@()applyControl(control)); %#ok<AGROW>
end
assert(numel(unique([jobs.Order]))==numel(jobs),'receiver_replay:Order','RF/control event order must be globally unique.');
[~,order]=sortrows([[jobs.Time]' [jobs.Order]'],[1 2]);
for k=order'
    scheduler.scheduleAt(jobs(k).Time/1e9,jobs(k).Callback);
end
report=struct('test','common-input receiver contention','runtime',version, ...
    'completed',false,'behavioral_pass',false,'network_parity_claim',false, ...
    'receiver_id',node,'start_ns',startNs,'stop_ns',stopNs, ...
    'comparison_start_ns',compareStart,'comparison_stop_ns',compareStop, ...
    'error_identifier','','error_message','','output_directory',outputDir);
report.scope='Real PHY and MAC receive; hop_ingress is addressed decoded-child dispatch eligibility, not HOP custody or duplicate acceptance.';
report.resolved_core=which('csr.phy.SignalEngine');
timer=tic;
try
    scheduler.run(stopNs/1e9);
    report.completed=true;
catch caught
    report.error_identifier=caught.identifier;
    report.error_message=caught.message;
    report.error_stack=caught.stack;
    report.draw_failure=tape.Failure;
end
report.wall_seconds=toc(timer); report.last_time_ns=round(scheduler.Now*1e9);
report.uniform_draws_used=tape.UsedCount;
allEvents=struct2table(rows); diagnosticEvents=struct2table(diagnostics);
window=allEvents.time_ns>=compareStart & allEvents.time_ns<compareStop;
events=allEvents(window,:); events.event_index=(1:height(events))';
writetable(events,fullfile(outputDir,'events.csv'));
writetable(allEvents,fullfile(outputDir,'warmup_events.csv'));
writetable(diagnosticEvents,fullfile(outputDir,'diagnostic_events.csv'));
usage=tape.usage();
writetable(usage,fullfile(outputDir,'draw_usage.csv'));
requiredDraws=usage.interval_end_ns<stopNs;
report.unused_required_draws=sum(requiredDraws & ~usage.used);
reference=fullfile(root,'reference','events.csv');
if ~isfile(reference), reference=fullfile(root,'native','reference','events.csv'); end
try
    comparison=compareEvents(reference,events,report.completed,compareStart,compareStop);
catch caught
    comparison=struct('pass',false,'message',caught.message,'error_identifier',caught.identifier);
end
if comparison.pass && report.unused_required_draws>0
    comparison.pass=false;
    comparison.message='Receiver events match, but required captured uniform inputs were left unused.';
    comparison.first_unused_draw=table2struct(usage(find(requiredDraws & ~usage.used,1),:));
end
report.behavioral_pass=report.completed && comparison.pass;
writeJson(fullfile(outputDir,'first_difference.json'),comparison);
writeJson(fullfile(outputDir,'run_summary.json'),report);
copyfile(fullfile(inputDir,'profile.json'),fullfile(outputDir,'profile.json'));
if isfile(fullfile(here,'adapter_provenance.json'))
    copyfile(fullfile(here,'adapter_provenance.json'),fullfile(outputDir,'adapter_provenance.json'));
end
archive=archiveOutput(outputDir);
report.archive=archive;
fprintf('\nReceiver replay complete: %d; behavioral comparison pass: %d\n',report.completed,report.behavioral_pass);
fprintf('Return this file: %s\n',archive);
if ~report.completed, fprintf('First execution difference: %s\n',report.error_message); end
if ~comparison.pass, fprintf('Comparison: %s\n',comparison.message); end

    function applyInput(input,frame)
        if strcmp(input.kind,'signal')
            engine.replaySignal(frame,input);
        elseif strcmp(input.kind,'own_tx')
            activeOwnSignal=input.signal_id;
            diagnostic('own_tx_start',frame,'','',engine.state(node),'Tx','');
            mac.replayOwnTx(frame,input.end_ns/1e9,input.queues_empty_at_end,input.active_nodes);
        else
            error('receiver_replay:InputKind','Unsupported physical input kind %s.',input.kind);
        end
    end
    function applyControl(control)
        if strcmp(control.kind,'prep_tx'), mac.replayPrep(control.value);
        elseif strcmp(control.kind,'cancel_post_tx_wait'), mac.replayCancelPostTx();
        else, error('receiver_replay:ControlKind','Unsupported MAC control %s.',control.kind); end
        frame=struct('Id',0,'SourceId',node,'Sequence',0);
        state=engine.state(node);
        diagnostic(char(control.kind),frame,sprintf('%.0f',control.value),'',state,state,'');
    end
    function transmit(~,duration)
        engine.replayOwnTx(node,scheduler.Now+duration);
    end
    function stateChanged(~,state)
        before=previousState; previousState=state;
        frame=struct('Id',0,'SourceId',0,'Sequence',0);
        diagnostic('state',frame,'','',before,state,'');
        if strcmp(before,'Tx') && strcmp(state,'Search')
            frame.Id=activeOwnSignal; frame.SourceId=node;
            diagnostic('own_tx_end',frame,'','',before,state,'');
        end
        if ~isempty(mac), mac.receiverChanged(state); end
    end
    function trace(name,frame,~,details)
        state=engine.state(node);
        if strcmp(name,'phy_track')
            append('track',frame,'','','Search','Track','');
        elseif strcmp(name,'phy_signal_end')
            if details.Success, result='accepted'; reason='accepted';
            else
                result='dropped';
                if details.Tracked
                    if details.EccDropped, reason='ecc';
                    elseif details.Collided, reason='collision';
                    elseif strcmp(state,'Track'), reason='phy';
                    else, reason='state'; end
                elseif strcmp(state,'Tx'), reason='half_duplex';
                else, reason='prior_stage'; end
            end
            append('signal_end',frame,result,reason,state,state,details.Reason);
        elseif strcmp(name,'phy_signal_start')
            diagnostic('signal_start',frame,'','',state,state,'');
        end
    end
    function receive(frame,~,decision)
        if ~decision.Success, return; end
        mac.receive(frame,decision);
        state=engine.state(node);
        append('mac_receive',frame,'accepted','accepted',state,state,'accepted');
        for n=1:numel(frame.Segments)
            member=frame.Segments{n};
            diagnostic('decoded_child',member,'accepted','accepted',state,state,'accepted');
            [addressed,sequence]=addressedSequence(member,node);
            if addressed
                member.Id=frame.Id; member.Sequence=sequence;
                append('hop_ingress',member,'accepted','accepted',state,state,'accepted');
            end
        end
    end
    function macEvent(name,frame,details)
        if strcmp(name,'mac_state')
            if ~isfield(frame,'Id'), frame=struct('Id',0,'SourceId',0,'Sequence',0); end
            diagnostic('mac_state',frame,'','',details.State,details.State,'');
        end
    end
    function append(stage,frame,result,reason,before,after,raw)
        row=makeRow(stage,frame,result,reason,before,after,raw); row.event_index=numel(rows)+1;
        rows(end+1,1)=row;
    end
    function diagnostic(stage,frame,result,reason,before,after,raw)
        row=makeRow(stage,frame,result,reason,before,after,raw); row.event_index=numel(diagnostics)+1;
        diagnostics(end+1,1)=row;
    end
    function row=makeRow(stage,frame,result,reason,before,after,raw)
        row=template; row.time_ns=round(scheduler.Now*1e9); row.signal_id=double(frame.Id);
        row.stage=stage; row.source=double(frame.SourceId); row.hop_sequence=double(frame.Sequence);
        row.result=result; row.reason=reason; row.state_before=before; row.state_after=after; row.raw_reason=raw;
    end
end

function frame=makeFrame(input,children)
selected=children(children.signal_id==input.signal_id,:);
selected=sortrows(selected,'child_index');
assert(~isempty(selected),'receiver_replay:Children','Physical signal has no captured children.');
assert(isequal(selected.child_index,(0:height(selected)-1)'), ...
    'receiver_replay:Children','Aggregate child indices must be contiguous and zero based.');
assert(sum(selected.wirebytes)==input.wirebytes, ...
    'receiver_replay:Children','Full aggregate wire size differs from captured child sizes.');
assert(any(input.preamblebits==[104 7888]) && ...
    input.packetbits==input.preamblebits+48+8*input.wirebytes+32, ...
    'receiver_replay:Inputs','Invalid preamble or total packet bit count.');
members=cell(1,height(selected));
for n=1:height(selected)
    child=selected(n,:);
    members{n}=struct('Id',input.signal_id,'SourceId',child.source,'DestinationId',child.dest, ...
        'Sequence',child.sequence,'WirePayloadBytes',child.wirebytes,'Type',child.type, ...
        'PacketHex',char(child.packet_hex));
end
frame=members{1}; frame.Kind='AGGREGATE'; frame.Segments=members;
frame.SourceId=input.source; frame.DestinationId=input.dest; frame.Sequence=input.sequence;
frame.RateKeyKbps=input.rate; frame.TxPowerDbm=input.tx_dbm;
frame.WirePayloadBytes=input.wirebytes; frame.ReservationSlot=input.slot;
frame.AckRequired=logical(input.ackable);
if input.preamblebits==7888, frame.Preamble='long'; else, frame.Preamble='short'; end
end

function [yes,sequence]=addressedSequence(member,node)
% Decode only the real serialized CsrHeader destination list, not payloads.
yes=member.DestinationId==node || member.DestinationId==16777215;
sequence=member.Sequence;
hex=member.PacketHex;
bytes=uint8(sscanf(hex,'%2x').');
assert(numel(bytes)>=13,'receiver_replay:Header','Captured CsrHeader is truncated.');
flags=bytes(10);
if bitand(flags,uint8(16))==0, return; end
position=14+16*double(bitand(flags,uint8(8))~=0)+ ...
    4*double(bitand(flags,uint8(32))~=0)+2*double(bitand(flags,uint8(64))~=0);
assert(position<=numel(bytes),'receiver_replay:Header','Missing destination-list count.');
count=double(bytes(position)); position=position+1; yes=false;
assert(position+5*count-1<=numel(bytes),'receiver_replay:Header','Truncated destination list.');
for k=1:count
    destination=double(bytes(position))*65536+double(bytes(position+1))*256+double(bytes(position+2));
    targetSequence=double(bytes(position+3))*256+double(bytes(position+4));
    if destination==node, yes=true; sequence=targetSequence; return; end
    position=position+5;
end
end

function comparison=compareEvents(reference,observed,completed,startNs,stopNs)
comparison=struct('pass',false,'message','','reference',reference,'observed_rows',height(observed));
if ~isfile(reference), comparison.message='Bundled native reference missing; no pass can be claimed.'; return; end
expected=readtable(reference,'TextType','string','VariableNamingRule','preserve');
fields={'time_ns','signal_id','stage','source','hop_sequence','result','reason','state_before','state_after'};
assert(all(ismember(fields,expected.Properties.VariableNames)),'receiver_replay:Reference','Invalid native event schema.');
expected=expected(expected.time_ns>=startNs & expected.time_ns<stopNs,:);
comparison.expected_rows=height(expected);
for k=1:min(height(expected),height(observed))
    for n=1:numel(fields)
        field=fields{n}; a=expected.(field)(k,:); b=observed.(field)(k,:);
        if iscell(b), b=string(b); end
        if isstring(a)
            if ismissing(a), a=""; end
            if ismissing(b), b=""; end
            equal=strcmp(a,b);
        else, equal=isequaln(a,b); end
        if ~equal
            comparison.message=sprintf('First event difference at row %d, field %s.',k,field);
            comparison.row=k; comparison.field=field;
            comparison.expected=table2struct(expected(k,:)); comparison.observed=table2struct(observed(k,:));
            return;
        end
    end
end
if height(expected)~=height(observed)
    comparison.message=sprintf('Event count differs: native %d, MATLAB %d.',height(expected),height(observed));
    comparison.row=min(height(expected),height(observed))+1; return;
end
if ~completed, comparison.message='Execution stopped before the comparison interval completed.'; return; end
comparison.pass=true; comparison.message='All ordered receiver events match the native reference exactly.';
end

function writeJson(file,value)
handle=fopen(file,'w');
if handle<0, error('receiver_replay:Output','Cannot write %s.',file); end
closer=onCleanup(@()fclose(handle)); %#ok<NASGU>
fprintf(handle,'%s\n',jsonencode(value,'PrettyPrint',true));
end

function binding=verifyBinding(root,inputDir)
binding=struct('pass',false,'message','','files',struct('path',{},'expected_sha256',{},'actual_sha256',{},'match',{}));
try
    manifest=jsondecode(fileread(fullfile(root,'RUN_FILES.json')));
    assert(strcmp(manifest.schema,'csr.receiver-run-files.v1'),'receiver_replay:Binding','Unexpected run manifest schema.');
    for k=1:numel(manifest.files)
        item=manifest.files(k); relative=char(item.path);
        assert(~startsWith(relative,'/') && ~contains(relative,'..'),'receiver_replay:Binding','Invalid manifest path.');
        if startsWith(relative,'inputs/'), file=fullfile(inputDir,relative(8:end));
        else, file=fullfile(root,relative); end
        actual=csr.validation.Artifacts.sha256(file);
        binding.files(end+1)=struct('path',relative,'expected_sha256',item.sha256, ...
            'actual_sha256',actual,'match',strcmpi(actual,item.sha256));
    end
    binding.pass=all([binding.files.match]) && ~isempty(binding.files);
    if binding.pass, binding.message='All issued source, input and reference hashes match.';
    else, binding.message='One or more issued source/input/reference hashes differ; see runtime_binding.json.'; end
catch caught
    binding.message=caught.message;
    binding.error_identifier=caught.identifier;
end
end

function archive=archiveOutput(outputDir)
archive=[outputDir '.zip'];
listing=dir(outputDir); names={listing(~[listing.isdir]).name};
zip(archive,names,outputDir);
end
