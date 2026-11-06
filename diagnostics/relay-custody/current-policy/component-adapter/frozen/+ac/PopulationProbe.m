classdef PopulationProbe < handle
    %POPULATIONPROBE Passive trace sink and public Neighbors callback recorder.
    properties
        NodeId = 1
        Neighbors
        PublishedCounts = []
        Ledger = {}
        Frames = {}
    end
    methods
        function record(obj,time,kind,node,details) %#ok<INUSD>
            if node~=obj.NodeId, return; end
            if strcmp(kind,'mac_population_publish')
                obj.publish(details.ActiveNodes);
            elseif strcmp(kind,'protocol') && strcmp(details.event,'mac_enqueue')
                obj.Frames{end+1}=details.frame;
                obj.Ledger{end+1}=struct('event','mac_enqueue','kind',details.frame.Kind, ...
                    'count',NaN,'frame',details.frame);
            end
        end
        function publish(obj,count)
            obj.PublishedCounts(end+1)=count;
            obj.Ledger{end+1}=struct('event','publish','kind','','count',count,'frame',[]);
        end
        function observed(obj)
            state=obj.Neighbors.snapshot();
            obj.publish(1+sum([state.Peers.LastHeardSeconds]>=0));
        end
        function changed(obj,peer,active) %#ok<INUSD>
            obj.Ledger{end+1}=struct('event','neighbor_changed','kind','','count',NaN,'frame',[]);
        end
        function accepted=neighborSend(obj,kind,peers,payload,reliable) %#ok<INUSD>
            obj.Ledger{end+1}=struct('event','neighbor_send','kind',kind,'count',NaN,'frame',[]);
            accepted=true;
        end
        function frame=lastControl(obj,kind,peer,subtype)
            for k=numel(obj.Frames):-1:1
                frame=obj.Frames{k};
                if ~strcmp(frame.Kind,'CONTROL') || ~strcmp(frame.Control.Type,kind) || ...
                        frame.DestinationId~=peer, continue; end
                if nargin>3 && ~strcmp(frame.Control.Payload.Subtype,subtype), continue; end
                return
            end
            error('autocase:PopulationPreflight','Expected outgoing %s to peer %g was not observed.',kind,peer);
        end
        function value=countKind(obj,kind)
            value=0;
            for k=1:numel(obj.Frames), value=value+strcmp(obj.Frames{k}.Kind,kind); end
        end
        function close(obj) %#ok<MANU>
            % ac.Trace.close can release this passive in-memory sink.
        end
    end
end
