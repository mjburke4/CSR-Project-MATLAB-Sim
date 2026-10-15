function output=review_hop_boundary()
% Real HOP capacity/cleanup boundary, no network or PHY simulation.
% Caller must bind the isolated candidate +ac and model directories.
output=struct('Cases',{{}},'Passed',true);
for limit=[1 2]
    output.Cases{end+1}=oneCase(limit);
end
end

function result=oneCase(limit)
scheduler=csr.sim.EventScheduler();
seen=0; gateInside=false; insideAccepted=false; afterAccepted=false;
frames={}; callbackDepth=NaN;
hop=ac.TerminalHop(5,scheduler,[],struct('ResendQueueLimit',limit), ...
    struct('EnqueueMac',@enqueue,'ControlResult',@completed));
key=struct('Id',uint64(1),'Type','KEY_UPDATE','Payload',struct(),'WirePayloadBytes',40);
check=struct('Id',uint64(2),'Type','NEIGHBOR_CHECK', ...
    'Payload',struct('Subtype','discovery'),'WirePayloadBytes',40);
[accepted,frame]=hop.sendControl(key,3,struct('AckRequired',true));
assert(accepted); hop.notifySent(frame);
ack=csr.hop.Frames.acknowledgment(3,5,frame.Sequence,uint64(0),uint64(0), ...
    struct('HasAckWindow',false));
hop.receive(ack);
assert(seen==1 && callbackDepth==1);
if limit==1
    assert(~gateInside && ~insideAccepted);
    state=hop.stats(); assert(state.ResendQueueDepth==0);
    scheduler.scheduleAt(scheduler.Now,@retry);
    scheduler.run(scheduler.Now);
    assert(afterAccepted);
else
    assert(gateInside && insideAccepted);
end
state=hop.stats(); assert(state.ResendQueueDepth==1);
assert(numel(frames)==2 && strcmp(frames{2}.Control.Type,'NEIGHBOR_CHECK'));
hop.receive(ack); assert(seen==1,'Duplicate ACK must not repeat callback.');
result=struct('Limit',limit,'CallbackDepth',callbackDepth,'GateInside',gateInside, ...
    'ImmediateAccepted',insideAccepted,'DeferredAccepted',afterAccepted,'Passed',true);
    function ok=enqueue(f)
        frames{end+1}=f; ok=true;
    end
    function completed(control,peer,success,complete,remaining)
        assert(control.Id==key.Id && peer==3 && success && complete && isempty(remaining));
        seen=seen+1; st=hop.stats(); callbackDepth=st.ResendQueueDepth;
        gateInside=hop.canSendControl(3);
        if gateInside, insideAccepted=hop.sendControl(check,3,struct('AckRequired',true)); end
    end
    function retry()
        afterAccepted=hop.sendControl(check,3,struct('AckRequired',true));
    end
end
