classdef Trace
    %TRACE Process-local passive sink. It never schedules events or uses RNG.
    methods (Static)
        function value = holder(action, value)
            persistent active
            if nargin == 0, value = active; return; end
            if strcmp(action,'set'), active=value;
            elseif strcmp(action,'clear'), active=[]; value=[];
            else, error('autocase:TraceAction','Unknown trace action.'); end
        end
        function open(folder)
            ac.Trace.close();
            ac.Trace.holder('set',ac.Recorder(folder));
        end
        function record(time,kind,node,details)
            sink=ac.Trace.holder();
            if ~isempty(sink), sink.record(time,kind,node,details); end
        end
        function close()
            sink=ac.Trace.holder();
            if ~isempty(sink), sink.close(); end
            ac.Trace.holder('clear',[]);
        end
    end
end
