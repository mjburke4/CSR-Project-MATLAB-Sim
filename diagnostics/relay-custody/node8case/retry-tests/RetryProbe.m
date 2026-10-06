classdef RetryProbe < handle
 properties
  Layer
  Clock
  Calls = {}
  Events = {}
  Actions = {}
  Completed = uint64([])
  NaturalKind = ''
  Hop
  Transmissions = {}
  NaturalCompletions = {}
  Accept = true
  CanSend = true
 end
 methods
  function obj=RetryProbe(config)
   obj.Clock=csr.sim.EventScheduler(2000);
   callbacks=struct('SendControl',@(c,p,o)obj.send(c,p,o), ...
    'CanSendControl',@(p)obj.CanSend,'Event',@(n,p,d)obj.event(n,p,d));
   obj.Layer=ac.DiscoveryMembershipNwk(1,obj.Clock,[],config,callbacks);
   hc=struct('EnqueueMac',@(f)obj.enqueue(f),'ControlResult', ...
    @(c,p,s,d,r)obj.hopComplete(c,p,s,d,r),'Event',@(n,p,d)obj.event(n,p,d));
   obj.Hop=ac.TerminalHop(1,obj.Clock,[],config,hc);
  end
  function yes=send(obj,c,p,o)
   kind='other'; seq=[]; section=[]; total=[]; ops={}; bytes=[];
   if strcmp(c.Type,'ROUTING')
    s=csr.nwk.RoutingCodec.decodeSection(c.Payload.Bytes);
    seq=s.Sequence;section=s.Section;total=s.TotalSections;bytes=double(c.Payload.Bytes);
    assert(total==1,'probe:Section','Fixture expects single-section streams.');
    records=csr.nwk.RoutingCodec.decodeRecords(s.Body);
    ops=cellfun(@(r)r.Operation,records,'UniformOutput',false);
    if any(strcmp(ops,'REQUEST')),kind='request';
    elseif any(strcmp(ops,'FLUSH')),kind='snapshot';else,kind='automatic_update';end
   end
   obj.Calls{end+1}=struct('ordinal',numel(obj.Calls)+1,'t_s',obj.Clock.Now, ...
    't_ns',round(obj.Clock.Now*1e9),'control_id',c.Id,'kind',kind,'sequence',seq, ...
    'section',section,'total_sections',total,'operations',{ops},'bytes',bytes, ...
    'peers',p,'control',c,'options',o,'accepted',obj.Accept);
   yes=obj.Accept;
   if yes && strcmp(kind,obj.NaturalKind),yes=obj.Hop.sendControl(c,p,o);end
  end
  function yes=enqueue(obj,frame)
   obj.Transmissions{end+1}=struct('t_s',obj.Clock.Now,'t_ns',round(obj.Clock.Now*1e9), ...
    'control_id',frame.Control.Id,'hop_sequences',double(frame.HopSequences), ...
    'retry_count',frame.RetryCount,'frame',frame);
   obj.Clock.scheduleAt(obj.Clock.Now,@()obj.Hop.notifySent(frame));yes=true;
  end
  function hopComplete(obj,c,p,s,d,r)
   obj.NaturalCompletions{end+1}=struct('t_s',obj.Clock.Now,'t_ns',round(obj.Clock.Now*1e9), ...
    'control_id',c.Id,'peer',p,'success',s,'complete',d,'remaining',r);
   obj.Layer.controlResult(c,p,s,d,r);
   obj.action('natural_hop_completion');
  end
  function event(obj,n,p,d)
   obj.Events{end+1}=struct('t_s',obj.Clock.Now,'t_ns',round(obj.Clock.Now*1e9), ...
    'name',n,'packet',p,'details',d);
  end
  function action(obj,name)
   peers=obj.Layer.neighborsSnapshot();
   obj.Actions{end+1}=struct('name',name,'t_s',obj.Clock.Now, ...
    't_ns',round(obj.Clock.Now*1e9),'stats',obj.Layer.stats(),'peers',peers);
  end
  function rows=ofKind(obj,kind)
   rows=obj.Calls(cellfun(@(r)strcmp(r.kind,kind),obj.Calls));
  end
  function row=lastControl(obj,kind,subtype)
   for k=numel(obj.Calls):-1:1
    row=obj.Calls{k};if ~strcmp(row.control.Type,kind),continue;end
    if nargin>2 && (~isfield(row.control.Payload,'Subtype') || ...
      ~strcmp(row.control.Payload.Subtype,subtype)),continue;end
    return
   end
   error('probe:Missing','Missing %s',kind);
  end
  function activate(obj,peer)
   if nargin<2,peer=3;end
   obj.Layer.receiveControl(struct('Type','KEY_UPDATE','Payload',struct('Generation',0)),peer);
   obj.Clock.run(0);r=obj.lastControl('KEY_UPDATE');obj.complete(r,true);
   r=obj.lastControl('NEIGHBOR_CHECK','overheard');obj.complete(r,true);
   peers=obj.Layer.neighborsSnapshot();assert(peers([peers.PeerId]==peer).Active);
   obj.action(sprintf('peer%d_active',peer));
  end
  function complete(obj,row,success)
   assert(~ismember(row.control.Id,obj.Completed),'probe:DoubleCompletion');
   obj.Completed(end+1)=row.control.Id;
   for k=1:numel(row.peers)
    obj.Layer.controlResult(row.control,row.peers(k),success,k==numel(row.peers),row.peers);
   end
   obj.Clock.run(obj.Clock.Now);
   obj.action(sprintf('terminal_completion_id_%d_success_%d',row.control.Id,success));
  end
  function ackOther(obj,keep)
   rows=obj.Calls;
   for k=1:numel(rows)
    r=rows{k};if ~ismember(r.control.Id,obj.Completed) && ~ismember(r.control.Id,keep)
     obj.complete(r,true);
    end
   end
  end
  function receiveRequest(obj,seq)
   s=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords( ...
    {struct('Operation','REQUEST')}),seq);
   obj.Layer.receiveControl(struct('Type','ROUTING','Payload',struct('Bytes',s{1})),3);
   obj.Clock.run(obj.Clock.Now);obj.action(sprintf('received_request_%d',seq));
  end
  function result=export(obj,name)
   result=struct('name',name,'class',class(obj.Layer),'calls',{obj.Calls}, ...
    'events',{obj.Events},'actions',{obj.Actions},'final_stats',obj.Layer.stats(), ...
    'natural_kind',obj.NaturalKind,'transmissions',{obj.Transmissions}, ...
    'natural_completions',{obj.NaturalCompletions},'hop_stats',obj.Hop.stats());
  end
 end
end
