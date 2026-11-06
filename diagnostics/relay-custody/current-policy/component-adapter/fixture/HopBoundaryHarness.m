classdef HopBoundaryHarness < handle
 % Isolated HOP-only raw TIC boundary. No NWK, key setup or control traffic.
 properties
  S; H; Config; Rows={}; Queue={}; Identities={}; Frame
 end
 methods
  function obj=HopBoundaryHarness(config)
   obj.Config=config;obj.S=csr.sim.EventScheduler(1000);
   cb=struct('EnqueueMac',@(f)obj.enqueue(f),'CancelMac',@(p,s)obj.cancel(p,s), ...
    'CancelMacData',@(p,s)obj.cancel(p,s),'Event',@(e,f,d)obj.event(e,f,d), ...
    'NsdpRelease',@(a,r)obj.event('nsdp_release_callback',a,struct('reason',r)), ...
    'Terminal',@(a,s,r)obj.event('terminal_callback',a,struct('success',s,'reason',r)), ...
    'Wake',@()obj.event('wake_callback',struct(),struct()));
   obj.H=ac.TerminalHop(8,obj.S,[],config,cb);
  end
  function execute(obj)
   a=struct('Id',uint64(800001),'SourceId',8,'DestinationId',1,'FlowOrdinal',0, ...
    'GeneratedSeconds',0,'ApplicationPayloadBytes',100,'Dscp',0,'AckRequired',true);
   [ok,f]=obj.H.send(a,2,struct('AckRequired',true,'EnvelopeProfile','bare','Dscp',0));assert(ok);obj.Frame=f;
   obj.S.scheduleAt(2.000000028,@()obj.feedback()); % Before initial sent installs its scan.
   assert(numel(obj.Queue)==1);obj.Queue(1)=[];
   obj.event('sent',f,struct());obj.H.notifySent(f);
   obj.snapshot('initial_sent');
   obj.S.run(2.000001);
   obj.snapshot('after_ack_retry_boundary');
  end
  function snapshot(obj,label)
   obj.event('checkpoint',struct(),struct('label',label,'hop',obj.H.fixtureReadOnly(), ...
    'peer2',obj.H.state(2),'mac_queue',{obj.Queue},'tic_seconds',obj.Config.Hop.TicSeconds));
  end
  function ok=enqueue(obj,f)
   ok=true;obj.Queue{end+1}=f;obj.Identities{end+1}=struct('App',f.App,'HopSequence',f.Sequence,'Peer',f.DestinationId,'RetryCount',f.RetryCount);
   obj.event('mac_output',f,struct());
  end
  function feedback(obj)
   f=csr.hop.Frames.acknowledgment(2,8,obj.Frame.Sequence,uint64(1),uint64(0), ...
    struct('HasAckWindow',true,'EnvelopeProfile','bare'));
   obj.event('feedback',f,struct());obj.H.receive(f);
  end
  function n=cancel(obj,peer,sequence)
   hit=cellfun(@(f)f.DestinationId==peer&&f.Sequence==sequence,obj.Queue);
   n=sum(hit);obj.Queue=obj.Queue(~hit);obj.event('cancel',struct(),struct('peer',peer,'sequence',sequence,'removed',n));
  end
  function record(obj,t,kind,node,d)
   obj.event('trace',struct(),struct('time',t,'kind',kind,'node',node,'details',d));
  end
  function event(obj,event,frame,details)
   assert(numel(obj.Rows)<1000);obj.Rows{end+1}=struct('ordinal',numel(obj.Rows)+1, ...
    'case','exact_28ns_ack_before_native_retry','time_s',obj.S.Now,'time_hex',num2hex(obj.S.Now), ...
    'event',event,'frame',frame,'details',details);
  end
 end
end
