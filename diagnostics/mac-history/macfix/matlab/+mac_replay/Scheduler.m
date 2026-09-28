classdef Scheduler < csr.sim.EventScheduler
    %SCHEDULER Quantize this native-boundary fixture to integer nanoseconds.
    % Production EventScheduler remains unchanged. The ns-3 fixture uses the
    % same resolution; equal timestamps retain scheduler insertion order.
    methods
        function obj = Scheduler(maxEvents)
            obj@csr.sim.EventScheduler(maxEvents);
        end
        function id = scheduleAt(obj,time,callback)
            id = scheduleAt@csr.sim.EventScheduler(obj,round(time*1e9)/1e9,callback);
        end
    end
end
