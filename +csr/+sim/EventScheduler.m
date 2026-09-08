classdef EventScheduler < handle
    %EVENTSCHEDULER Portable deterministic discrete-event clock.
    %   This simulation infrastructure is an engineering choice, not a port
    %   of ns-3 internals. Times are finite, nonnegative seconds. Equal-time
    %   callbacks run in insertion order, including events inserted by a
    %   callback. No CSR protocol priority is implied by that ordering.
    %
    %   run(T) executes events at times <= T and advances Now to T on normal
    %   completion. MaxEvents bounds callbacks executed by each run call;
    %   it catches zero-time rescheduling loops without discarding the next
    %   event. Cancellation is lazy and never executes the canceled callback.

    properties (SetAccess = private)
        Now = 0
        MaxEvents = 1000000
    end

    properties (Dependent, SetAccess = private)
        PendingCount
    end

    properties (Access = private)
        Times = zeros(1, 256)
        Ids = zeros(1, 256, 'uint64')
        Callbacks = cell(1, 256)
        HeapCount = 0
        NextId = uint64(1)
        Active
        IsRunning = false
    end

    methods
        function obj = EventScheduler(maxEvents)
            if nargin > 0
                validateattributes(maxEvents, {'numeric'}, ...
                    {'scalar', 'real', 'finite', 'integer', 'positive', ...
                    '<=', flintmax}, mfilename, 'maxEvents');
                obj.MaxEvents = double(maxEvents);
            end
            obj.Active = containers.Map('KeyType', 'uint64', ...
                'ValueType', 'logical');
        end

        function count = get.PendingCount(obj)
            % Expose a double count consistently with the other counters.
            % containers.Map.Count returns uint64 on R2025a; IDs stay uint64.
            count = double(obj.Active.Count);
        end

        function time = nextTime(obj)
            %NEXTTIME Earliest active event, or Inf when the queue is empty.
            % This supports a native clock driver without copying the heap.
            while obj.HeapCount > 0 && ~isKey(obj.Active, obj.Ids(1))
                obj.popEarliest();
            end
            time = Inf;
            if obj.HeapCount > 0
                time = obj.Times(1);
            end
        end

        function id = scheduleAt(obj, time, callback)
            validateattributes(time, {'numeric'}, ...
                {'scalar', 'real', 'finite', 'nonnegative'}, ...
                mfilename, 'time');
            time = double(time);
            if time < obj.Now
                error('csr:sim:EventInPast', ...
                    'Cannot schedule time %.17g before Now %.17g.', ...
                    time, obj.Now);
            end
            if ~isa(callback, 'function_handle')
                error('csr:sim:InvalidCallback', ...
                    'callback must be a function handle invoked with no arguments.');
            end
            if obj.NextId == intmax('uint64')
                error('csr:sim:EventIdExhausted', ...
                    'The scheduler has exhausted its event-ID space.');
            end

            id = obj.NextId;
            obj.NextId = obj.NextId + uint64(1);
            obj.ensureCapacity();
            obj.HeapCount = obj.HeapCount + 1;
            index = obj.HeapCount;
            obj.Times(index) = time;
            obj.Ids(index) = id;
            obj.Callbacks{index} = callback;
            obj.Active(id) = true;
            while index > 1
                parent = floor(index / 2);
                if ~obj.precedes(index, parent)
                    break
                end
                obj.swap(index, parent);
                index = parent;
            end
        end

        function wasPending = cancel(obj, id)
            % Cancellation of an unknown, completed, or canceled ID is a no-op.
            validateattributes(id, {'uint64'}, {'scalar'}, mfilename, 'id');
            wasPending = isKey(obj.Active, id);
            if wasPending
                remove(obj.Active, id);
            end
        end

        function executed = run(obj, untilSeconds)
            validateattributes(untilSeconds, {'numeric'}, ...
                {'scalar', 'real', 'finite', 'nonnegative'}, ...
                mfilename, 'untilSeconds');
            untilSeconds = double(untilSeconds);
            if obj.IsRunning
                error('csr:sim:ReentrantRun', ...
                    'A scheduler callback cannot recursively call run.');
            end
            if untilSeconds < obj.Now
                error('csr:sim:TimeReversal', ...
                    'run cannot move the simulation clock backwards.');
            end

            obj.IsRunning = true;
            cleanup = onCleanup(@() obj.finishRun()); %#ok<NASGU>
            executed = 0;
            while obj.HeapCount > 0
                id = obj.Ids(1);
                if ~isKey(obj.Active, id)
                    obj.popEarliest();
                    continue
                end
                if obj.Times(1) > untilSeconds
                    break
                end
                if executed >= obj.MaxEvents
                    error('csr:sim:EventLimitExceeded', ...
                        ['Exceeded MaxEvents (%g) in one run call. ' ...
                        'Check for zero-time rescheduling loops.'], obj.MaxEvents);
                end

                time = obj.Times(1);
                callback = obj.Callbacks{1};
                obj.popEarliest();
                remove(obj.Active, id);
                obj.Now = time;
                executed = executed + 1;
                callback();
            end
            obj.Now = untilSeconds;
        end
    end

    methods (Access = private)
        function finishRun(obj)
            obj.IsRunning = false;
        end

        function ensureCapacity(obj)
            if obj.HeapCount < numel(obj.Times)
                return
            end
            capacity = 2 * numel(obj.Times);
            obj.Times(capacity) = 0;
            obj.Ids(capacity) = uint64(0);
            obj.Callbacks{capacity} = [];
        end

        function before = precedes(obj, left, right)
            before = obj.Times(left) < obj.Times(right) || ...
                (obj.Times(left) == obj.Times(right) && ...
                obj.Ids(left) < obj.Ids(right));
        end

        function swap(obj, left, right)
            obj.Times([left, right]) = obj.Times([right, left]);
            obj.Ids([left, right]) = obj.Ids([right, left]);
            obj.Callbacks([left, right]) = obj.Callbacks([right, left]);
        end

        function popEarliest(obj)
            last = obj.HeapCount;
            if last > 1
                obj.Times(1) = obj.Times(last);
                obj.Ids(1) = obj.Ids(last);
                obj.Callbacks{1} = obj.Callbacks{last};
            end
            obj.Callbacks{last} = [];
            obj.Ids(last) = uint64(0);
            obj.Times(last) = 0;
            obj.HeapCount = last - 1;
            index = 1;
            while 2 * index <= obj.HeapCount
                child = 2 * index;
                if child < obj.HeapCount && obj.precedes(child + 1, child)
                    child = child + 1;
                end
                if ~obj.precedes(child, index)
                    break
                end
                obj.swap(index, child);
                index = child;
            end
        end
    end
end
