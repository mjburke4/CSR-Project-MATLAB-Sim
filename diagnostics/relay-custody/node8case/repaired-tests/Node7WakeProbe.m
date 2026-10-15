classdef Node7WakeProbe < handle
    % Passive public Trace sink and receiver callback for component tests.
    properties
        Rows = {}
        State = 'Idle'
        Transmissions = 0
        StartCapture = 221.3
    end
    methods
        function record(obj,time,kind,node,details)
            if time < obj.StartCapture,return;end
            obj.Rows{end+1}=struct('time',time,'kind',kind,'node',node,'details',details);
        end
        function close(~),end
        function state(obj,value),obj.State=value;end
        function transmit(obj,~,~),obj.Transmissions=obj.Transmissions+1;end
        function rows=select(obj,kind,cause)
            rows={};
            for k=1:numel(obj.Rows)
                r=obj.Rows{k};
                if ~strcmp(r.kind,kind),continue;end
                if nargin>2 && ~strcmp(r.details.Cause,cause),continue;end
                rows{end+1}=r; %#ok<AGROW>
            end
        end
    end
end
