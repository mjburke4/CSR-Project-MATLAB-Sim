classdef Recorder < handle
    properties (Access=private)
        File = -1
        Count = uint64(0)
    end
    methods
        function obj=Recorder(folder)
            obj.File=fopen(fullfile(folder,'ordered_events.jsonl'),'w');
            assert(obj.File>=0,'autocase:TraceOpen','Cannot open ordered event trace.');
        end
        function record(obj,time,kind,node,details)
            obj.Count=obj.Count+uint64(1);
            row=struct('observation_order',obj.Count,'time_s',time, ...
                'kind',char(kind),'node',double(node),'details',details);
            n=fprintf(obj.File,'%s\n',jsonencode(row));
            assert(n>0,'autocase:TraceWrite','Cannot write ordered event trace.');
        end
        function close(obj)
            if obj.File>=0, fclose(obj.File); obj.File=-1; end
        end
        function delete(obj), obj.close(); end
    end
end
