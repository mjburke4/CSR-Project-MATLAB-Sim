classdef CheckGateProbe < handle
    %CHECKGATEPROBE Passive public Neighbors callback recorder.
    properties
        Scheduler
        Calls = {}
    end
    methods
        function accepted=send(obj,kind,peers,payload,reliable)
            obj.Calls{end+1}=struct('kind',char(kind),'peers',peers, ...
                'payload',payload,'reliable',logical(reliable),'time_s',obj.Scheduler.Now);
            accepted=true;
        end
        function count=countChecks(obj,subtype)
            count=0;
            for k=1:numel(obj.Calls)
                row=obj.Calls{k};
                if strcmp(row.kind,'NEIGHBOR_CHECK') && ...
                        (nargin<2 || strcmp(row.payload.Subtype,subtype))
                    count=count+1;
                end
            end
        end
        function row=last(obj,kind)
            row=[];
            for k=numel(obj.Calls):-1:1
                if strcmp(obj.Calls{k}.kind,kind), row=obj.Calls{k}; return; end
            end
            error('autocase:CheckGatePreflight','Expected %s callback was not observed.',kind);
        end
    end
end
