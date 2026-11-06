classdef NativeScheduler < handle
    %NATIVESCHEDULER Optional R2026a wireless-clock backend; CSR retains RF.
    % An actual wnet.Node advances the existing deterministic CSR event heap.
    % There is no zero-node assumption and no second channel/packet transport.
    % Each instance permits one run; recreate after completion or exception.
    % Construction resets the global wirelessNetworkSimulator instance.
    properties (SetAccess = private)
        MaxEvents
    end
    properties (Dependent, SetAccess = private)
        Now
        PendingCount
    end
    properties (Access = private)
        Queue
        Simulator
        Anchor
        IsRunning = false
        HasRun = false
        Executed = 0
    end
    methods
        function obj = NativeScheduler(maxEvents)
            csr.sim.native.requireAvailable();
            if nargin == 0, maxEvents = 1000000; end
            obj.Queue = csr.sim.EventScheduler(maxEvents);
            obj.MaxEvents = obj.Queue.MaxEvents;
            obj.Simulator = wirelessNetworkSimulator.init;
            obj.Anchor = csr.sim.native.ClockNode(@(time) obj.advance(time));
            addNodes(obj.Simulator, obj.Anchor);
        end
        function time = get.Now(obj)
            time = obj.Queue.Now;
        end
        function count = get.PendingCount(obj)
            count = obj.Queue.PendingCount;
        end
        function id = scheduleAt(obj, time, callback)
            if obj.HasRun && ~obj.IsRunning
                error('csr:sim:NativeSingleRun', ...
                    'Create a new wireless-clock scenario after a run.');
            end
            if ~isa(callback, 'function_handle')
                error('csr:sim:InvalidCallback', ...
                    'callback must be a function handle with no arguments.');
            end
            id = obj.Queue.scheduleAt(time, @() obj.invoke(callback));
        end
        function wasPending = cancel(obj, id)
            wasPending = obj.Queue.cancel(id);
        end
        function executed = run(obj, untilSeconds)
            validateattributes(untilSeconds, {'numeric'}, ...
                {'scalar', 'real', 'finite', 'nonnegative'}, ...
                mfilename, 'untilSeconds');
            if obj.IsRunning
                error('csr:sim:ReentrantRun', ...
                    'A scheduler callback cannot recursively call run.');
            end
            if obj.HasRun
                error('csr:sim:NativeSingleRun', ...
                    'Create a new wireless-clock scenario after a run.');
            end
            if ~isequal(wirelessNetworkSimulator.getInstance, obj.Simulator)
                error('csr:sim:NativeInstanceReplaced', ...
                    ['Another caller reset wirelessNetworkSimulator. ' ...
                    'Create and run each native scenario sequentially.']);
            end
            obj.HasRun = true;
            obj.IsRunning = true;
            cleanup = onCleanup(@() obj.finishRun()); %#ok<NASGU>
            run(obj.Simulator, double(untilSeconds));
            if obj.Queue.nextTime() <= untilSeconds
                error('csr:sim:NativeMissedEvent', ...
                    'The native clock stopped before a scheduled CSR event.');
            end
            % No callback may run here: otherwise native scheduling failure
            % would be hidden by portable execution after the native run.
            obj.Queue.run(double(untilSeconds));
            executed = obj.Executed;
        end
    end
    methods (Access = private)
        function nextTime = advance(obj, currentTime)
            obj.Queue.run(currentTime);
            nextTime = obj.Queue.nextTime();
        end
        function invoke(obj, callback)
            if obj.Executed >= obj.MaxEvents
                error('csr:sim:EventLimitExceeded', ...
                    'Exceeded MaxEvents (%g) in the native run.', obj.MaxEvents);
            end
            obj.Executed = obj.Executed + 1;
            callback();
        end
        function finishRun(obj)
            obj.IsRunning = false;
        end
    end
end
