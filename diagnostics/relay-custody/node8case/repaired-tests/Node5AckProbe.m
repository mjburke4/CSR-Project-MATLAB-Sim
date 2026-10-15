classdef Node5AckProbe < handle
    properties
        Allowed = true
        BlockedPeers = []
        RejectChecks = false
        Calls = {}
    end
    methods
        function yes=canSend(obj,peers)
            yes=obj.Allowed && ~any(ismember(peers,obj.BlockedPeers));
        end
        function yes=send(obj,control,peers,options)
            yes=~(obj.RejectChecks && strcmp(control.Type,'NEIGHBOR_CHECK'));
            obj.Calls{end+1}=struct('Control',control,'Peers',peers,'Options',options,'Accepted',yes);
        end
        function rows=select(obj,kind,peer)
            rows={};
            for k=1:numel(obj.Calls)
                item=obj.Calls{k};
                if strcmp(item.Control.Type,kind) && isequal(item.Peers,peer)
                    rows{end+1}=item; %#ok<AGROW>
                end
            end
        end
    end
end
