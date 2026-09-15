classdef TraceScheduler < handle
    %TRACESCHEDULER Observe an unchanged portable scheduler through its API.
    % IDs are actual EventScheduler IDs. This adapter does not round time,
    % assign priority, inspect private MAC timers, or add simulation events.
    properties (SetAccess = private)
        CurrentEventId = uint64(0)
    end
    properties (Dependent, SetAccess = private)
        Now
        MaxEvents
        PendingCount
    end
    properties (Access = private)
        Scheduler
        CaseName
        Rows
    end
    methods
        function obj = TraceScheduler(caseName,maxEvents)
            if nargin<1, caseName = 'test'; end
            if nargin<2, maxEvents = 1000000; end
            obj.Scheduler = csr.sim.EventScheduler(maxEvents);
            obj.CaseName = char(caseName);
            obj.Rows = repmat(struct('case','','order',0,'operation','', ...
                'event_id',uint64(0),'parent_id',uint64(0), ...
                'observed_seconds','','observed_hex','','scheduled_seconds','', ...
                'scheduled_hex','','callback','','was_pending',false),0,1);
        end
        function value = get.Now(obj), value = obj.Scheduler.Now; end
        function value = get.MaxEvents(obj), value = obj.Scheduler.MaxEvents; end
        function value = get.PendingCount(obj), value = obj.Scheduler.PendingCount; end
        function value = nextTime(obj), value = obj.Scheduler.nextTime(); end
        function id = scheduleAt(obj,time,callback)
            % A distinct nested workspace belongs to each scheduleAt call;
            % the ID is filled before its callback can execute.
            if ~isa(callback,'function_handle')
                error('csr:sim:InvalidCallback','callback must be a function handle invoked with no arguments.');
            end
            id = obj.Scheduler.scheduleAt(time,@execute);
            obj.record('schedule',id,obj.CurrentEventId,time,func2str(callback),true);
            function execute()
                previous = obj.CurrentEventId;
                obj.CurrentEventId = id;
                cleanup = onCleanup(@()obj.restoreCurrent(previous)); %#ok<NASGU>
                obj.record('execute',id,previous,time,func2str(callback),true);
                callback();
            end
        end
        function pending = cancel(obj,id)
            pending = obj.Scheduler.cancel(id);
            obj.record('cancel',id,obj.CurrentEventId,obj.Now,'',pending);
        end
        function count = run(obj,untilSeconds)
            count = obj.Scheduler.run(untilSeconds);
        end
        function output = records(obj)
            prototype = struct('case','','order',0,'operation','', ...
                'event_id',uint64(0),'parent_id',uint64(0), ...
                'observed_seconds','','observed_hex','','scheduled_seconds','', ...
                'scheduled_hex','','callback','','was_pending',false);
            output = csr.validation.edgeRecordTable(obj.Rows,prototype);
        end
    end
    methods (Access = private)
        function restoreCurrent(obj,id), obj.CurrentEventId = id; end
        function record(obj,operation,id,parent,time,callback,pending)
            obj.Rows(end+1,1) = struct('case',obj.CaseName,'order',numel(obj.Rows)+1, ...
                'operation',operation,'event_id',id,'parent_id',parent, ...
                'observed_seconds',sprintf('%.17g',obj.Now),'observed_hex',num2hex(obj.Now), ...
                'scheduled_seconds',sprintf('%.17g',time),'scheduled_hex',num2hex(time), ...
                'callback',callback,'was_pending',logical(pending));
        end
    end
end
