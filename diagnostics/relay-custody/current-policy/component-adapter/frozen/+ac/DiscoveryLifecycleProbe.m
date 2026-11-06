classdef DiscoveryLifecycleProbe < handle
    %DISCOVERYLIFECYCLEPROBE Public NWK callback recorder; no private hooks.
    properties
        Layer
        Scheduler
        GateOpen = true
        Accept = true
        CompleteKeyInline = false
        Calls = {}
        GateCalls = {}
        DataCalls = 0
        OwnerCountsAtSend = []
    end
    methods
        function allowed=canSend(obj,peers)
            obj.GateCalls{end+1}=double(peers);
            allowed=logical(obj.GateOpen);
        end
        function accepted=sendControl(obj,control,peers,options)
            accepted=logical(obj.Accept);
            obj.Calls{end+1}=struct('control',control,'peers',peers, ...
                'options',options,'time_s',obj.Scheduler.Now,'accepted',accepted);
            state=obj.Layer.stats();
            obj.OwnerCountsAtSend(end+1)=state.PendingControlMessages;
            if accepted && obj.CompleteKeyInline && strcmp(control.Type,'KEY_UPDATE')
                obj.Layer.controlResult(control,peers(1),true,true,[]);
            end
        end
        function accepted=sendData(obj,app,peer,options) %#ok<INUSD>
            obj.DataCalls=obj.DataCalls+1; accepted=true;
        end
        function selected=ofType(obj,kind)
            selected=obj.Calls(cellfun(@(row)strcmp(row.control.Type,kind),obj.Calls));
        end
        function ids=destinations(obj,kind)
            rows=obj.ofType(kind); ids=zeros(1,numel(rows));
            for k=1:numel(rows), ids(k)=rows{k}.control.Payload.DestinationId; end
        end
    end
end
