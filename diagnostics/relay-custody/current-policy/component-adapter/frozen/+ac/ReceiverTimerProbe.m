classdef ReceiverTimerProbe < handle
    %RECEIVERTIMERPROBE Public MAC/PHY callback bridge for one TX component.
    properties
        Scheduler
        Engine
        Mac
        TxCount = 0
        TxTime = NaN
        TxDuration = NaN
        Ledger = {}
    end
    methods
        function transmit(obj,frame,duration)
            obj.TxCount=obj.TxCount+1; obj.TxTime=obj.Scheduler.Now; obj.TxDuration=duration;
            obj.Engine.transmit(frame,duration);
        end
        function phyState(obj,node,state)
            if node~=1, return; end
            if obj.TxCount>0 && strcmp(state,'Search')
                obj.Ledger{end+1}=struct('kind','phy_search','time_s',obj.Scheduler.Now);
            end
            if ~isempty(obj.Mac), obj.Mac.receiverChanged(state); end
        end
        function macEvent(obj,event,frame,details) %#ok<INUSD>
            if obj.TxCount>0 && strcmp(event,'mac_state') && strcmp(details.State,'Search')
                obj.Ledger{end+1}=struct('kind','mac_search','time_s',obj.Scheduler.Now);
            end
        end
    end
end
