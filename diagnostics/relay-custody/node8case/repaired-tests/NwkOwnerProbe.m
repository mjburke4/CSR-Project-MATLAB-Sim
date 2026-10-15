classdef NwkOwnerProbe < handle
 properties
  Scheduler
  Network
  Allowed=true
  Accept=true
  GateCalls=0
  Sent={}
  Queue=[]
  Times=[]
  Reentrant=[]
  Records={}
 end
 methods
  function obj=NwkOwnerProbe(s),obj.Scheduler=s;end
  function yes=canSend(obj,~),obj.GateCalls=obj.GateCalls+1;yes=obj.Allowed;end
  function yes=send(obj,app,peer,options)
   yes=obj.Accept;obj.Sent{end+1}=struct('app',app,'peer',peer,'options',options,'accepted',yes,'time',obj.Scheduler.Now);
   if yes,obj.push(double(app.Id));end
   if ~isempty(obj.Reentrant)
    app2=obj.Reentrant;obj.Reentrant=[];assert(obj.Network.sendApplication(app2));
   end
  end
  function push(obj,id),obj.Queue(end+1)=id;obj.Times(end+1)=obj.Scheduler.Now;end
  function record(obj,time,event,node,details)
   obj.Records{end+1}=struct('time',time,'event',event,'node',node,'details',details);
  end
 end
end
