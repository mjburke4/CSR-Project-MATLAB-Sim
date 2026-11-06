classdef CongestionHarness < handle
 % Fixture boundary only. Actual NWK/HOP own custody, credits, retries/wakes.
 properties
  S; N; H; G; Config; Rows={}; Queue={}; Identities={}; Incoming=uint16(0)
  Timers={}; Label=''; Limit=5000
 end
 methods
  function obj=CongestionHarness(config,label)
   obj.Config=config;obj.Label=label;obj.S=csr.sim.EventScheduler(10000);
   hc=struct('EnqueueMac',@(f)obj.enqueue(f),'CancelMac',@(p,s)obj.cancel(p,s,false), ...
    'CancelMacData',@(p,s)obj.cancel(p,s,true),'CancelMacControl',@(p,t)obj.cancelControl(p,t), ...
    'Deliver',@(a,p)obj.N.receiveData(a,p),'ValidateControl',@(c,p)obj.N.validateControl(c,p), ...
    'DeliverControl',@(c,p)obj.N.receiveControl(c,p), ...
    'ControlResult',@(c,p,s,d,r)obj.N.controlResult(c,p,s,d,r), ...
    'Terminal',@(a,s,r)obj.N.terminal(a,s,r),'NsdpRelease',@(a,r)obj.N.releaseFromHop(a,r), ...
    'Wake',@()obj.N.checkDataQueue(),'NsdpCount',@(a)obj.N.nsdpCount(a), ...
    'RouteAvailable',@(a)obj.N.routeAvailable(a),'Event',@(e,f,d)obj.event('hop',e,f,d));
   obj.H=ac.TerminalHop(8,obj.S,[],config,hc);
   nc=struct('CanSendData',@(p)obj.H.canSend(p),'SendData',@(a,p,o)obj.H.send(a,p,o), ...
    'CanSendControl',@(p)obj.H.canSendControl(p),'SendControl',@(c,p,o)obj.H.sendControl(c,p,o), ...
    'CancelControl',@(p,t)obj.H.cancelQueuedControl(p,t), ...
    'Event',@(e,f,d)obj.event('nwk',e,f,d));
   obj.N=ac.DiscoveryMembershipNwk(8,obj.S,[],config,nc);
   obj.G=csr.sim.ApplicationGenerator(6,struct('SourceId',8,'DestinationId',1,'DestinationMode','fixed'),true,0);
  end
  function setup(obj)
   % Prescribed peer controls enter real HOP validation/replay and NWK key paths.
   % No start(): background discovery/freshness scans deliberately not started.
   for peer=[2 7]
    obj.N.observeRadio(peer,struct('Success',true));
    obj.input(peer,'KEY_UPDATE',struct());
   end
   obj.S.run(0); % Local KEY_UPDATE sent+exact ACK; all control work remains real.
   for peer=[2 7]
    obj.input(peer,'NEIGHBOR_CHECK',struct('Subtype','message','Sequence',uint32(0),'Active',true));
   end
   obj.S.run(0);
   records={struct('Operation','UPDATE','NodeId',2,'Capability',1,'HopCount',0,'Cost',0,'Path',[]), ...
    struct('Operation','UPDATE','NodeId',1,'Capability',2,'HopCount',1,'Cost',1,'Path',1)};
   sections=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords(records),1);
   for k=1:numel(sections),obj.input(2,'ROUTING',struct('Bytes',sections{k}));end
   obj.S.run(0);
   peers=obj.N.neighborsSnapshot();
   for peer=[2 7]
    p=peers([peers.Id]==peer);assert(isscalar(p)&&p.Active&&p.SentKey&&p.ReceivedKey&&~p.Stale);
   end
   a=obj.app(8,0);assert(obj.N.routeAvailable(a));s=obj.N.applicationState(1);assert(s.GatewayId==1);
   h=obj.H.state(2);assert(h.NeighborThreshold==0&&h.NeighborOutstanding==0&&h.PendingData==0);
   n=obj.N.stats();assert(h.ResendQueueDepth==0&&h.DackHoldCount==0&&isempty(obj.Queue));
   assert(n.PendingControlMessages==0&&n.PendingCustody==0,'fixture:UnsettledSetup','Setup controls/custody unresolved');
   obj.snapshot('setup_zero');
  end
  function input(obj,peer,kind,payload)
   obj.Incoming=obj.Incoming+uint16(1);
   c=struct('Id',uint64(obj.Incoming),'Type',kind,'Payload',payload, ...
    'WirePayloadBytes',ac.controlWireBytes(kind,payload,1,obj.Config.Nwk.SecurityProfile));
   f=csr.hop.Frames.control(c,peer,8,obj.Incoming,struct('EnvelopeProfile','bare','AckRequired',true));
   obj.event('input','control',f,struct());obj.H.receive(f);
  end
  function ok=enqueue(obj,f)
   ok=true;obj.event('boundary','enqueue',f,struct());
   if strcmp(f.Kind,'DATA')
    obj.Queue{end+1}=f;obj.Identities{end+1}=struct('App',f.App,'HopSource',f.SourceId, ...
     'HopPeer',f.DestinationId,'HopSequence',f.Sequence,'RetryCount',f.RetryCount);
   elseif strcmp(f.Kind,'CONTROL')
    % Prescribed successful control service: normal sent and exact ACK callbacks.
    obj.S.scheduleAt(obj.S.Now,@()obj.controlSent(f));
   end
  end
  function controlSent(obj,f)
   obj.event('boundary','control_sent',f,struct());obj.H.notifySent(f);
   if f.AckRequired
    for k=1:numel(f.DestinationIds)
     ack=csr.hop.Frames.acknowledgment(f.DestinationIds(k),8,f.HopSequences(k),uint64(0),uint64(0), ...
      struct('HasAckWindow',false,'EnvelopeProfile','bare'));
     obj.H.receive(ack);
    end
   end
  end
  function n=cancel(obj,peer,sequence,dataOnly)
   keep=true(1,numel(obj.Queue));
   for k=1:numel(obj.Queue),f=obj.Queue{k};keep(k)=~(f.DestinationId==peer&&f.Sequence==sequence&&(~dataOnly||strcmp(f.Kind,'DATA')));end
   n=sum(~keep);obj.Queue=obj.Queue(keep);
   obj.event('boundary','cancel',struct(),struct('peer',peer,'sequence',sequence,'dataOnly',dataOnly,'removed',n));
  end
  function n=cancelControl(obj,peer,kind)
   % Control service is instantaneous at this deterministic boundary.
   n=0;obj.event('boundary','cancel_control',struct(),struct('peer',peer,'kind',kind,'removed',n));
  end
  function a=app(obj,source,sequence)
   a=struct('Id',uint64(source*100000+sequence+1),'SourceId',source,'DestinationId',1, ...
    'FlowOrdinal',sequence,'GeneratedSeconds',obj.S.Now,'ApplicationPayloadBytes',100, ...
    'Dscp',0,'AckRequired',true,'HopCount',0,'Traversal',source);
  end
  function offer(obj,sequence)
   [ok,d,row]=obj.G.attempt(obj.S.Now,@(dest)obj.N.applicationState(dest),@()error('fixture:UnexpectedRng','Fixed destination only'));
   a=obj.app(8,sequence);assert(d==1);obj.event('input','offer',a,row);
   if ok,assert(obj.N.sendApplication(a));end
   if sequence==17,assert(~ok&&strcmp(row.Reason,'nsdp_full'));else,assert(ok);end
  end
  function offer16(obj)
   for k=1:16,obj.offer(k);end
  end
  function relay(obj)
   a=obj.app(7,1);[ok,reason]=obj.N.receiveData(a,7);assert(ok);
   obj.event('input','relay',a,struct('accepted',ok,'reason',reason));
  end
  function sent(obj,source,sequence)
   index=find(cellfun(@(f)f.App.SourceId==source&&f.App.FlowOrdinal==sequence,obj.Queue),1);
   assert(~isempty(index),'fixture:Unsubmitted','Prescribed sent frame was not admitted by actual model');
   f=obj.Queue{index};obj.Queue(index)=[];obj.event('boundary','sent',f,struct());obj.H.notifySent(f);
  end
  function feedback(obj,source,sequence,dack)
   index=find(cellfun(@(v)v.App.SourceId==source&&v.App.FlowOrdinal==sequence,obj.Identities),1);
   assert(~isempty(index));id=obj.Identities{index};ack=uint64(~dack);dk=uint64(dack);
   f=csr.hop.Frames.acknowledgment(2,8,id.HopSequence,ack,dk,struct('HasAckWindow',true,'EnvelopeProfile','bare'));
   obj.event('input','feedback',f,struct('application_source',source,'application_sequence',sequence));obj.H.receive(f);
  end
  function record(obj,t,kind,node,d)
   if strcmp(kind,'scheduler_schedule')
    obj.Timers{end+1}=struct('id',d.EventId,'deadline',d.DeadlineSeconds,'callback',d.Callback,'pending',true);
   elseif any(strcmp(kind,{'scheduler_fire','scheduler_cancel'}))
    for k=1:numel(obj.Timers)
     if obj.Timers{k}.id==d.EventId,obj.Timers{k}.pending=false;end
    end
   end
   obj.add('trace',struct('time',t,'kind',kind,'node',node,'details',d));
  end
  function event(obj,layer,event,frame,details)
   obj.add(layer,struct('event',event,'frame',frame,'details',details));
  end
  function snapshot(obj,label)
   n=obj.N.fixtureReadOnly();h=obj.H.fixtureReadOnly();p=obj.H.state(2);a=obj.N.applicationState(1);
   waiting=n.Pending(cellfun(@(x)~x.Submitted,n.Pending));
   scans=obj.Timers(cellfun(@(x)contains(x.callback,'runResendScan'),obj.Timers));
   latest=NaN;if ~isempty(scans),latest=scans{end};end
   holds=h.DackHolds;
   for k=1:numel(holds)
    holds{k}.ScheduledTimerDeadline=holds{k}.Expiry+obj.Config.Hop.TicSeconds;
    holds{k}.DeadlineProvenance='Source formula; compare against retained scheduler_schedule checkDacks event';
   end
   obj.add('checkpoint',struct('case',obj.Label,'checkpoint',label,'time_s',obj.S.Now, ...
    'tic_seconds',obj.Config.Hop.TicSeconds,'own_nsdp',a.NsdpCount, ...
    'relay_nsdp',obj.N.nsdpCount(struct('SourceId',7,'DestinationId',1)), ...
    'pending',p.PendingData,'peer_outstanding',p.NeighborOutstanding,'threshold',p.NeighborThreshold, ...
    'clean_acks',p.AckCount,'resend_count',p.ResendQueueDepth,'held_count',p.DackHoldCount, ...
    'waiting',{waiting},'pending_rows',{n.Pending},'resends',{h.Resends},'holds',{holds}, ...
    'nwk_local_wake',obj.timer('runLocalDataCheck',n.LocalDataWakePending), ...
    'hop_feedback_wake',obj.timer('obj.wake()',h.WakePending), ...
    'latest_retained_resend_timer',latest,'all_scan_events',{scans}, ...
    'hold_timer_events',{obj.Timers(cellfun(@(x)contains(x.callback,'checkDacks'),obj.Timers))}, ...
    'nwk',n,'hop',h,'peer2',p,'application',a, ...
    'neighbors',obj.N.neighborsSnapshot(),'routes',obj.N.routesSnapshot(),'mac_queue',{obj.Queue}));
  end
  function t=timer(obj,needle,pending)
   t=NaN;if ~pending,return;end
   matches=obj.Timers(cellfun(@(x)x.pending&&contains(x.callback,needle),obj.Timers));
   assert(numel(matches)==1,'fixture:TimerIdentity','Ambiguous or absent observed wake timer');t=matches{1};
  end
  function add(obj,kind,value)
   assert(numel(obj.Rows)<obj.Limit,'fixture:EvidenceLimit','Evidence rows exceeded');
   obj.Rows{end+1}=struct('ordinal',numel(obj.Rows)+1,'episode',obj.Label,'time',obj.S.Now, ...
    'time_hex',num2hex(obj.S.Now),'kind',kind,'value',value);
  end
 end
end
