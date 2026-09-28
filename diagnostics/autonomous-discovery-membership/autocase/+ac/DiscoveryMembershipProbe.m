classdef DiscoveryMembershipProbe < handle
    %DISCOVERYMEMBERSHIPPROBE Public control/data callback recorder.
    properties
        Scheduler
        Controls = {}
        Data = {}
    end
    methods
        function accepted=sendControl(obj,control,peers,options)
            obj.Controls{end+1}=struct('control',control,'peers',peers, ...
                'options',options,'time_s',obj.Scheduler.Now);
            accepted=true;
        end
        function accepted=sendData(obj,app,peer,options)
            obj.Data{end+1}=struct('app',app,'peer',peer, ...
                'options',options,'time_s',obj.Scheduler.Now);
            accepted=true;
        end
        function rows=ofType(obj,kind)
            rows=obj.Controls(cellfun(@(row)strcmp(row.control.Type,kind),obj.Controls));
        end
        function ids=destinations(obj,kind)
            rows=obj.ofType(kind); ids=zeros(1,numel(rows));
            for k=1:numel(rows), ids(k)=rows{k}.control.Payload.DestinationId; end
        end
    end
end
