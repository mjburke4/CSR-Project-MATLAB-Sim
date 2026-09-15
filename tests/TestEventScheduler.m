classdef TestEventScheduler < matlab.unittest.TestCase
    methods (Test)
        function sameTimeInsertionAndCancellation(testCase)
            scheduler = csr.sim.EventScheduler();
            observed = [];
            scheduler.scheduleAt(1, @first);
            scheduler.scheduleAt(1, @() record(2));
            canceled = scheduler.scheduleAt(0.5, @() record(99));
            testCase.verifyTrue(scheduler.cancel(canceled));
            testCase.verifyFalse(scheduler.cancel(canceled));
            testCase.verifyEqual(scheduler.PendingCount, 2);
            testCase.verifyEqual(scheduler.run(2), 3);
            testCase.verifyEqual(observed, [1, 2, 3]);
            testCase.verifyEqual(scheduler.Now, 2);
            testCase.verifyEqual(scheduler.PendingCount, 0);

            function first()
                record(1);
                scheduler.scheduleAt(scheduler.Now, @() record(3));
            end
            function record(value)
                observed(end + 1) = value;
            end
        end

        function horizonAndMonotonicClock(testCase)
            scheduler = csr.sim.EventScheduler();
            observed = [];
            scheduler.scheduleAt(2, @record);
            testCase.verifyEqual(scheduler.run(1), 0);
            testCase.verifyEqual(scheduler.Now, 1);
            testCase.verifyEqual(scheduler.PendingCount, 1);
            testCase.verifyError(@() scheduler.scheduleAt(0.9, @record), ...
                'csr:sim:EventInPast');
            testCase.verifyError(@() scheduler.run(0.9), 'csr:sim:TimeReversal');
            testCase.verifyEqual(scheduler.run(2), 1);
            testCase.verifyEqual(observed, 2);

            function record()
                observed(end + 1) = scheduler.Now;
            end
        end

        function heapGrowthRetainsTimeAndFifoOrdering(testCase)
            scheduler = csr.sim.EventScheduler();
            observed = zeros(1, 600);
            count = 0;
            times = mod((600:-1:1) * 37, 19);
            for index = 1:numel(times)
                scheduler.scheduleAt(times(index), @() record(index));
            end
            expected = sortrows([times(:), (1:numel(times))'], [1, 2]);
            scheduler.run(20);
            testCase.verifyEqual(observed, expected(:, 2)');

            function record(value)
                count = count + 1;
                observed(count) = value;
            end
        end

        function eventLimitPreservesPendingWork(testCase)
            scheduler = csr.sim.EventScheduler(3);
            count = 0;
            scheduler.scheduleAt(0, @again);
            testCase.verifyError(@() scheduler.run(1), ...
                'csr:sim:EventLimitExceeded');
            testCase.verifyEqual(count, 3);
            testCase.verifyEqual(scheduler.Now, 0);
            testCase.verifyEqual(scheduler.PendingCount, 1);
            testCase.verifyEqual(scheduler.run(1), 2);
            testCase.verifyEqual(count, 5);

            function again()
                count = count + 1;
                if count < 5
                    scheduler.scheduleAt(scheduler.Now, @again);
                end
            end
        end

        function callbackFailureLeavesClockAndQueueUsable(testCase)
            scheduler = csr.sim.EventScheduler();
            scheduler.scheduleAt(1, @() error('csr:test:Callback', 'Test failure'));
            scheduler.scheduleAt(2, @() []);
            testCase.verifyError(@() scheduler.run(3), 'csr:test:Callback');
            testCase.verifyEqual(scheduler.Now, 1);
            testCase.verifyEqual(scheduler.PendingCount, 1);
            testCase.verifyEqual(scheduler.run(3), 1);
            testCase.verifyEqual(scheduler.Now, 3);
        end

        function eventLimitReportsAdvancingClockAndCallbacks(testCase)
            scheduler = csr.sim.EventScheduler(1);
            scheduler.scheduleAt(1.25, @first);
            scheduler.scheduleAt(2.5, @second);
            caught = [];
            try
                scheduler.run(3);
            catch exception
                caught = exception;
            end
            testCase.assertClass(caught, 'MException');
            testCase.verifyEqual(caught.identifier, 'csr:sim:EventLimitExceeded');
            testCase.verifySubstring(caught.message, 'Now=1.25 s; next=2.5 s;');
            testCase.verifySubstring(caught.message, func2str(@first));
            testCase.verifySubstring(caught.message, func2str(@second));
            testCase.verifyEqual(scheduler.Now, 1.25);
            testCase.verifyEqual(scheduler.PendingCount, 1);
            testCase.verifyEqual(scheduler.run(3), 1);

            function first()
            end
            function second()
            end
        end

        function nestedRunIsRejected(testCase)
            scheduler = csr.sim.EventScheduler();
            scheduler.scheduleAt(1, @() scheduler.run(2));
            testCase.verifyError(@() scheduler.run(3), 'csr:sim:ReentrantRun');
            testCase.verifyEqual(scheduler.run(3), 0);
        end
    end
end
