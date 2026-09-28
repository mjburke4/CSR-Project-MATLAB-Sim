function report = run_grouped_retry(root,outputDir)
%RUN_GROUPED_RETRY Test completed-group cleanup through production HOP/MAC.
% Native seed132 frame132 remained queued after its final secondary ACK.
% This is a native-history oracle regression, not a native runtime replay.
% The first actual-TX indication is an input at the public HOP boundary.
% Its subsequent retry is put in the real, unmodified MATLAB MAC queue.
if nargin<2, outputDir=fullfile(root,'out','grouped_retry'); end
if ~isfolder(outputDir), mkdir(outputDir); end
report=struct('completed',false,'pass',false,'runtime',version, ...
    'scope','Production HOP/MAC completion cleanup; native-history/source oracle', ...
    'known_behavioral_difference',false,'matlab_execution_required',true, ...
    'expected_native_retry_queue_after_final_ack',1,'cases',{{}}, ...
    'error_identifier','','error_message','');
policies={'actual-tx','native-provisional'};
for k=1:numel(policies)
    result=oneCase(policies{k});
    report.cases{end+1}=result;
end
report.completed=all(cellfun(@(r)r.completed,report.cases));
report.pass=report.completed && all(cellfun(@(r)r.pass,report.cases));
report.known_behavioral_difference=any(cellfun(@(r)r.known_behavioral_difference,report.cases));
report.matlab_execution_required=false;
writeJson(fullfile(outputDir,'grouped_retry_summary.json'),report);
end

function result=oneCase(policy)
result=struct('policy',policy,'completed',false,'pass',false, ...
    'known_behavioral_difference',false,'expected_queue_after_final_ack',1, ...
    'observed_queue_after_final_ack',NaN,'cancel_calls',0, ...
    'error_identifier','','error_message','','observations',{{}});
scheduler=csr.sim.EventScheduler(); scheduler.run(91.494);
streams=csr.sim.RandomStreams(132);
receiver='Track'; mac=[]; hop=[]; first=[];
enqueueCount=0; cancelRows=struct('time_s',{},'peer',{},'sequence',{},'removed',{});
try
    config=csr.mac.Layer.defaults(); config.DutyCycleEnabled=false;
    mac=csr.mac.Layer(8,scheduler,streams,config, ...
        struct('Transmit',@unexpectedTx,'ReceiverState',@receiverState));
    mac.start(); mac.receiverChanged('Track');
    hop=csr.hop.Layer(8,scheduler,[],struct('DataQueuedRetryPolicy',policy), ...
        struct('EnqueueMac',@enqueue,'CancelMac',@cancelQueued));
    control=struct('Id',uint64(132),'Type','ROUTING', ...
        'Payload',struct(),'WirePayloadBytes',88);
    [accepted,first]=hop.sendControl(control,[7 2]);
    assert(accepted,'mac_grouped:Admission','Initial grouped control was rejected.');
    hop.notifySent(first);
    record('original_sent');

    scheduler.run(91.879972442);
    hop.receive(exactAck(7,first.HopSequences(1)));
    s=hop.stats();
    assert(s.ControlPending==1 && s.ControlPendingTargets==1 && isempty(cancelRows), ...
        'mac_grouped:PartialAck','Partial ACK unexpectedly completed or canceled the group.');
    record('primary_ack_partial');

    scheduler.run(93.5);
    s=hop.stats();
    assert(enqueueCount==2 && s.ControlRetransmissions==1 && mac.DataQueueCount==1, ...
        'mac_grouped:Retry','Expected one real HOP retry in the production MAC queue.');
    record('retry_queued');

    scheduler.run(93.557475346);
    hop.receive(exactAck(2,first.HopSequences(2)));
    s=hop.stats(); ms=mac.snapshot();
    assert(s.ControlCompleted==1 && s.ControlPending==0 && s.ControlPendingTargets==0, ...
        'mac_grouped:Completion','Final secondary ACK did not complete HOP ownership.');
    assert(ms.Transmissions==0,'mac_grouped:UnexpectedTx','A queued retry transmitted despite receiver Track.');
    record('secondary_ack_final');
    result.observed_queue_after_final_ack=mac.DataQueueCount;
    result.cancel_calls=numel(cancelRows); result.cancellation_events=cancelRows;
    result.original_primary_sequence=double(first.HopSequences(1));
    result.original_secondary_sequence=double(first.HopSequences(2));
    result.completed=true;
    result.pass=mac.DataQueueCount==result.expected_queue_after_final_ack;
    result.known_behavioral_difference=mac.DataQueueCount==0 && ...
        numel(cancelRows)==1 && cancelRows(1).peer==7 && ...
        cancelRows(1).sequence==double(first.HopSequences(1)) && cancelRows(1).removed==1;
    if result.known_behavioral_difference
        result.message=['Completed HOP group cancels its queued retry through the primary destination; ' ...
            'native seed132 retained the structured queued retry.'];
    elseif result.pass
        result.message='Queued retry remains after HOP completion, matching the native history oracle.';
    else
        result.message='Different completion/queue result; inspect observations.';
    end
catch caught
    result.error_identifier=caught.identifier; result.error_message=caught.message;
    result.error_stack=caught.stack;
end

    function state=receiverState()
        state=receiver;
    end
    function accepted=enqueue(frame)
        enqueueCount=enqueueCount+1;
        if enqueueCount==1
            % Boundary input: the original frame was accepted and actually
            % sent at91.494. Only its later queued retry is under MAC test.
            accepted=true;
        else
            accepted=mac.enqueue(frame);
        end
    end
    function cancelQueued(peer,sequence)
        removed=mac.cancel(peer,sequence);
        cancelRows(end+1)=struct('time_s',scheduler.Now,'peer',double(peer), ...
            'sequence',double(sequence),'removed',removed);
    end
    function frame=exactAck(peer,sequence)
        frame=csr.hop.Frames.acknowledgment(peer,8,sequence,uint64(1),uint64(0), ...
            struct('HasAckWindow',false));
    end
    function unexpectedTx(varargin) %#ok<INUSD>
        error('mac_grouped:UnexpectedTx','Receiver Track must hold the queued retry.');
    end
    function record(action)
        hs=hop.stats(); ms=mac.snapshot();
        result.observations{end+1}=struct('action',action,'time_s',scheduler.Now, ...
            'hop_control_pending',hs.ControlPending,'hop_pending_targets',hs.ControlPendingTargets, ...
            'hop_completed',hs.ControlCompleted,'hop_retries',hs.ControlRetransmissions, ...
            'mac_data_queue',ms.DataQueueDepth,'mac_canceled',ms.Canceled, ...
            'mac_transmissions',ms.Transmissions,'cancel_calls',numel(cancelRows));
    end
end

function writeJson(file,value)
fid=fopen(file,'w'); assert(fid>=0,'mac_grouped:Output','Cannot write grouped retry results.');
cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
end
