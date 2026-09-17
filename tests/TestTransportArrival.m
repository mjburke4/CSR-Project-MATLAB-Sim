classdef TestTransportArrival < matlab.unittest.TestCase
    % Small independent arithmetic tests; no fixture setup can mask them.
    methods (Test)
        function continuousPreservesTheObservedOneUlpResidual(test)
            tx = hex2num('4008f5c28f5c28f6');
            duration = hex2num('3f998f1d3ed527e6');
            [arrival,row] = csr.validation.transportArrival(tx,duration,1e-6,'continuous');
            tick = hex2num('400928e15011904b');
            test.verifyEqual(arrival,tx+duration+1e-6);
            test.verifyEqual(arrival-tick,eps(tick));
            test.verifyEqual(row.arrival_hex,'400928e15011904c');
            test.verifyEqual(str2double(row.arrival_seconds),arrival);
            test.verifyEqual(row.delta_hex,num2hex(0));
        end
        function localNanosecondsResolveTheMeasuredTransportTie(test)
            tx = hex2num('4008f5c28f5c28f6');
            duration = hex2num('3f998f1d3ed527e6');
            [arrival,row] = csr.validation.transportArrival(tx,duration,1e-6,'nanoseconds');
            tick = hex2num('400928e15011904b');
            test.verifyEqual(arrival,tick); test.verifyEqual(row.sum_ns,uint64(3144961000));
            test.verifyEqual(row.tx_ns,uint64(3120000000));
            test.verifyEqual(row.duration_ns,uint64(24960000));
            test.verifyEqual(row.propagation_ns,uint64(1000));
            test.verifyEqual(hex2num(row.delta_hex),-eps(tick));
        end
        function componentsRoundSeparatelyBeforeTheyAreAdded(test)
            [arrival,row] = csr.validation.transportArrival(0.6e-9,0.6e-9,0.6e-9,'nanoseconds');
            test.verifyEqual(arrival,3/1e9);
            test.verifyEqual([row.tx_ns,row.duration_ns,row.propagation_ns],uint64([1 1 1]));
            test.verifyEqual(row.sum_ns,uint64(3));
            test.verifyNotEqual(arrival,round((0.6e-9+0.6e-9+0.6e-9)*1e9)/1e9);
            test.verifyEqual(hex2num(row.continuous_hex),0.6e-9+0.6e-9+0.6e-9);
        end
        function oneNanosecondBeforeTieAndAfterRemainDistinct(test)
            arrivals = zeros(1,3);
            for k=1:3
                arrivals(k) = csr.validation.transportArrival(3.12, ...
                    (24960000+k-2)/1e9,1e-6,'nanoseconds');
            end
            tick = 3144961000/1e9;
            test.verifyLessThan(arrivals(1),tick);
            test.verifyEqual(arrivals(2),tick);
            test.verifyGreaterThan(arrivals(3),tick);
            test.verifyEqual(round(arrivals*1e9),[3144960999 3144961000 3144961001]);
        end
        function localConversionPreservesSchedulerTieInsertionOrder(test)
            scheduler = csr.sim.EventScheduler(); order = [];
            tick = 3144961000/1e9;
            arrival = csr.validation.transportArrival(3.12,0.02496,1e-6,'nanoseconds');
            scheduler.scheduleAt(arrival,@()record(1));
            scheduler.scheduleAt(tick,@()record(2));
            scheduler.scheduleAt((3144961000+1)/1e9,@()record(3));
            scheduler.run(4);
            test.verifyEqual(order,[1 2 3]);
            function record(value), order(end+1) = value; end
        end
        function zeroAndFixtureHorizonRetainFiniteExactRecords(test)
            for mode=["continuous","nanoseconds"]
                [arrival,row] = csr.validation.transportArrival(0,0,0,mode);
                test.verifyEqual(arrival,0); test.verifyEqual(row.sum_ns,uint64(0));
                [arrival,row] = csr.validation.transportArrival(64,0,0,mode);
                test.verifyEqual(arrival,64); test.verifyEqual(row.tx_ns,uint64(64000000000));
                test.verifyEqual(hex2num(row.arrival_hex),arrival);
                test.verifyEqual(str2double(row.arrival_seconds),arrival);
            end
            [~,row] = csr.validation.transportArrival(0,flintmax/1e9,0,'nanoseconds');
            test.verifyClass(row.sum_ns,'uint64');
            test.verifyEqual(row.sum_ns,uint64(flintmax));
        end
        function invalidComponentsAndInexactSumsAreRejected(test)
            values = {-1,NaN,Inf,1+1i,[0 1],[],single(0),uint64(0),flintmax};
            for k=1:numel(values)
                value = values{k};
                test.verifyError(@()csr.validation.transportArrival(value,0,0,'continuous'), ...
                    'csr:validation:TransportTime');
                test.verifyError(@()csr.validation.transportArrival(0,value,0,'nanoseconds'), ...
                    'csr:validation:TransportTime');
                test.verifyError(@()csr.validation.transportArrival(0,0,value,'nanoseconds'), ...
                    'csr:validation:TransportTime');
            end
            test.verifyError(@()csr.validation.transportArrival(flintmax/1e9,1,0,'nanoseconds'), ...
                'csr:validation:TransportTime');
        end
        function unknownModeAndPastArrivalAreRejected(test)
            test.verifyError(@()csr.validation.transportArrival(0,0,0,'ns'), ...
                'csr:validation:TransportMode');
            test.verifyError(@()csr.validation.transportArrival(0,0,0,["continuous","nanoseconds"]), ...
                'csr:validation:TransportMode');
            test.verifyError(@()csr.validation.transportArrival(0.4e-9,0,0,'nanoseconds'), ...
                'csr:validation:TransportPast');
            test.verifyEqual(csr.validation.transportArrival(0.4e-9,0,0,'continuous'),0.4e-9);
        end
    end
end
