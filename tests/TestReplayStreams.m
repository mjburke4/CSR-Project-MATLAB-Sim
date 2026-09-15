classdef TestReplayStreams < matlab.unittest.TestCase
    % Runtime dispatch and rejection checks for the test-only raw-draw seam.
    methods (Test)
        function cachedStreamHandle(test)
            owner = test.owner([0 31]);
            test.verifyTrue(owner.get(1,'mac')==owner.get(1,"mac"));
        end
        function inclusiveEndpointsRemainRaw(test)
            owner = test.owner([0 31]); stream = owner.get(1,'mac');
            test.verifyEqual(randi(stream,[0 31]),0);
            test.verifyEqual(randi(stream,[0 31],1,1),31);
            rows = owner.draws();
            test.verifyEqual(rows.ordinal,[1;2]);
            test.verifyEqual(rows.draw,[0;31]);
            test.verifyEqual(rows.time_ns,[250000000;250000000]);
        end
        function eachNodeOwnsItsConsumptionOrdinal(test)
            tape = [test.tape([4 6]); test.tape([9 3])];
            tape.node(3:4) = 2;
            owner = csr.validation.ReplayStreams(tape,@()0,'test');
            a = owner.get(1,'mac'); b = owner.get(2,'mac');
            test.verifyEqual([randi(b,[0 31]),randi(a,[0 31]), ...
                randi(a,[0 31]),randi(b,[0 31])],[9 4 6 3]);
            test.verifyEqual(owner.usage().unused,[0;0]);
        end
        function wrongSupportDoesNotConsumeTheTape(test)
            owner = test.owner(4); stream = owner.get(1,'mac');
            test.verifyError(@()randi(stream,[0 30]),'csr:validation:ReplaySupport');
            test.verifyEqual(randi(stream,[0 31]),4);
        end
        function exhaustionNeverFallsBackToRandomness(test)
            owner = test.owner(4); stream = owner.get(1,'mac');
            randi(stream,[0 31]);
            test.verifyError(@()randi(stream,[0 31]),'csr:validation:ReplayExhausted');
        end
        function arrayDrawsAreRejected(test)
            owner = test.owner(4); stream = owner.get(1,'mac');
            test.verifyError(@()randi(stream,[0 31],2,1),'csr:validation:ReplayShape');
            test.verifyError(@()randi(stream,[0 31],[1 2]),'csr:validation:ReplayShape');
            test.verifyError(@()randi(stream,[0 31],'uint32'),'csr:validation:ReplayShape');
        end
        function nonMacSubsystemIsRejected(test)
            owner = test.owner(4);
            test.verifyError(@()owner.get(1,'phy'),'csr:validation:ReplaySubsystem');
            test.verifyError(@()owner.get(1,'nwk'),'csr:validation:ReplaySubsystem');
        end
        function missingNodeTapeIsRejected(test)
            owner = test.owner(4);
            test.verifyError(@()owner.get(2,'mac'),'csr:validation:ReplayNode');
        end
        function outOfSupportInputIsRejected(test)
            tape = test.tape(32);
            test.verifyError(@()csr.validation.ReplayStreams(tape,@()0), ...
                'csr:validation:ReplayTape');
        end
        function fractionalInputIsRejected(test)
            tape = test.tape(2.5);
            test.verifyError(@()csr.validation.ReplayStreams(tape,@()0), ...
                'csr:validation:ReplayTape');
        end
        function ordinalGapsAreRejected(test)
            tape = test.tape([2 3]); tape.ordinal(2) = 3;
            test.verifyError(@()csr.validation.ReplayStreams(tape,@()0), ...
                'csr:validation:ReplayOrdinal');
        end
        function unusedSuffixIsExplicit(test)
            owner = test.owner([4 5 6]); stream = owner.get(1,'mac');
            randi(stream,[0 31]);
            usage = owner.usage();
            test.verifyEqual([usage.supplied usage.consumed usage.unused],[3 1 2]);
        end
        function productionMacStillPerformsOccupiedSlotProbing(test)
            scheduler = csr.sim.EventScheduler();
            owner = csr.validation.ReplayStreams(test.tape(31),@()scheduler.Now);
            options = csr.mac.Layer.defaults();
            options.DutyCycleEnabled = false; options.ActiveNodes = 3;
            options.SlotProfile = 'hist-2014-next-tslot-modulo-probe';
            mac = csr.mac.Layer(1,scheduler,owner,options,struct('Transmit',@(~,~)[]));
            for peer=[2 3]
                heard = test.frame(); heard.SourceId = peer;
                if peer==2, heard.ReservationSlot = 32;
                else, heard.ReservationSlot = 2; end
                mac.receive(heard,struct('Success',true));
                mac.receive(heard,struct('Success',true));
            end
            mac.enqueue(test.frame()); scheduler.run(.014);
            % At the first tick, occupied slots are 31 and 1. Raw 31
            % probes to 1 then 2 under the source modulo-R rule.
            test.verifyEqual(mac.neighborReservation(2),31);
            test.verifyEqual(mac.neighborReservation(3),1);
            test.verifyEqual(mac.ReservationCounter,2);
            test.verifyEqual(owner.draws().draw,31);
            test.verifyEqual(mac.Counters.Transmissions,0);
        end
    end
    methods (Static, Access = private)
        function owner = owner(values)
            owner = csr.validation.ReplayStreams(TestReplayStreams.tape(values),@().25);
        end
        function tape = tape(values)
            values = values(:); count = numel(values);
            tape = table(ones(count,1),(1:count)',zeros(count,1), ...
                31*ones(count,1),values,'VariableNames',{'node','ordinal','min','max','draw'});
        end
        function output = frame()
            app = struct('Id',uint64(1),'SourceId',1,'DestinationId',2, ...
                'GeneratedSeconds',0,'ApplicationPayloadBytes',16,'Dscp',0);
            output = csr.hop.Frames.data(app,1,2,uint16(1), ...
                struct('EnvelopeProfile','bare','RateKeyKbps',128,'TxPowerDbm',33));
        end
    end
end
