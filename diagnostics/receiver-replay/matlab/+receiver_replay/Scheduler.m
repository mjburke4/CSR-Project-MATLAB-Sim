classdef Scheduler < csr.sim.EventScheduler
    %SCHEDULER Native ns resolution for callbacks; physical times stay double.
    methods
        function obj=Scheduler(maxEvents)
            obj@csr.sim.EventScheduler(maxEvents);
        end
        function id=scheduleAt(obj,time,callback)
            id=scheduleAt@csr.sim.EventScheduler(obj,round(time*1e9)/1e9,callback);
        end
    end
end
