classdef KeyProbe < handle
    %KEYPROBE Public callback recorder for isolated NWK admission checks.
    properties
        Layer
        Scheduler
        Accept = true
        CompleteInline = false
        Calls = {}
        Ledger = {}
        DataCalls = 0
    end
    methods
        function accepted = sendControl(obj,control,peers,options)
            entry=struct('control',control,'peers',peers,'options',options, ...
                'time_s',obj.Scheduler.Now,'accepted',logical(obj.Accept));
            obj.Calls{end+1}=entry;
            obj.Ledger{end+1}=struct('event','send','kind',control.Type, ...
                'id',control.Id,'peer',peers(1));
            accepted=logical(obj.Accept);
            if accepted && obj.CompleteInline
                obj.Layer.controlResult(control,peers(1),true,true,[]);
            end
        end
        function accepted = cancelControl(obj,peer,kind)
            obj.Ledger{end+1}=struct('event','cancel','kind',char(kind), ...
                'id',uint64(0),'peer',peer);
            accepted=true;
        end
        function accepted = sendData(obj,app,peer,options) %#ok<INUSD>
            obj.DataCalls=obj.DataCalls+1; accepted=true;
        end
    end
end
