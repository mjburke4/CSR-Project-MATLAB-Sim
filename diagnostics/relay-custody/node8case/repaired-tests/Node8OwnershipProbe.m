classdef Node8OwnershipProbe < handle
    % Public callback adapter; never reads or writes private model state.
    properties
        Engine
        Mac
        Node = 3
        States = {}
        Clock
    end
    methods
        function state(obj,node,value)
            obj.States{end+1}=struct('node',node,'state',value,'time',obj.Clock.Now);
            if node==obj.Node && ~isempty(obj.Mac),obj.Mac.receiverChanged(value);end
        end
        function transmit(obj,frame,duration),obj.Engine.transmit(frame,duration);end
    end
end
