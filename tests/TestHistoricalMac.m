classdef TestHistoricalMac < matlab.unittest.TestCase
    % Executable-backed selection contracts from ns-3 486d9e01:
    % csr-mac-slot-parity-smoke.cc and model/csr-mac-core.h PickTxSlot.
    % Fixed-draw vectors below exercise support and collision decisions;
    % they do not equate MATLAB's stream to ns-3 or Modeler streams.
    methods (Test)
        function selectionIsExplicitAndDefaultRemainsCurrent(testCase)
            defaults = csr.mac.Layer.defaults();
            testCase.verifyEqual(defaults.SlotProfile,'current-fine-free-slot');
            testCase.verifyEqual(csr.mac.SlotSelection.normalizeProfile( ...
                "hist-2014-next-tslot-modulo-probe"), ...
                'hist-2014-next-tslot-modulo-probe');
            testCase.verifyError(@()csr.mac.SlotSelection.normalizeProfile('campus'), ...
                'csr:mac:SlotProfile');
            testCase.verifyError(@()csr.mac.SlotSelection.normalizeProfile({'current-fine-free-slot'}), ...
                'csr:mac:SlotProfile');
        end

        function historicalCoarseRangeBoundariesMatchExecutable(testCase)
            nodes = [0 4 5 8 9 12 13 17 double(intmax('uint32'))];
            expected = [31 31 63 63 127 127 255 255 255];
            profiles = {'hist-2014-coarse-inclusive-no-avoid', ...
                'hist-2014-zero-based-rebuild-list', ...
                'hist-2014-next-tslot-modulo-probe'};
            for name = profiles
                actual = arrayfun(@(n)csr.mac.SlotSelection.slotRange(name{1},n),nodes);
                testCase.verifyEqual(actual,expected);
            end
        end

        function hiddenProfileRetainsAllFineRangeBoundaries(testCase)
            expected = [15 18 21 25 31 37 44 52 63 75 89 106 127 151 180 214 255 255];
            actual = arrayfun(@(n)csr.mac.SlotSelection.slotRange( ...
                'hist-2015-fine-one-based-table-no-avoid',n),0:17);
            testCase.verifyEqual(actual,expected);
        end

        function campusPopulationExcludesReportedTransitPopulation(testCase)
            campus = 'hist-2014-next-tslot-modulo-probe';
            % Source smoke: node 5 directly knows peers 1/3/4 plus self;
            % route-only nodes 2/7/8 do not enlarge the local input of four.
            active = csr.mac.SlotSelection.activeNodes(campus,4,7);
            testCase.verifyEqual(active,4);
            testCase.verifyEqual(csr.mac.SlotSelection.slotRange(campus,active),31);
            testCase.verifyEqual(csr.mac.SlotSelection.slotRange(campus, ...
                csr.mac.SlotSelection.activeNodes(campus,5,7)),63);
            testCase.verifyEqual(csr.mac.SlotSelection.activeNodes( ...
                'hist-2014-coarse-inclusive-no-avoid',4,13),4);
            for name = {'current-fine-free-slot', ...
                    'hist-2014-zero-based-rebuild-list', ...
                    'hist-2015-fine-one-based-table-no-avoid'}
                testCase.verifyEqual(csr.mac.SlotSelection.activeNodes(name{1},4,7),7);
            end
        end

        function supervisorReductionKeepsSourceStrictGuard(testCase)
            profile = 'hist-2014-next-tslot-modulo-probe';
            testCase.verifyEqual(csr.mac.SlotSelection.slotRange(profile,8,10),53);
            testCase.verifyEqual(csr.mac.SlotSelection.slotRange(profile,8,61),2);
            testCase.verifyEqual(csr.mac.SlotSelection.slotRange(profile,8,62),63);
            testCase.verifyEqual(csr.mac.SlotSelection.slotRange(profile,8,-1),63);
        end

        function operationalInclusiveReturnsOccupiedEndpoints(testCase)
            profile = 'hist-2014-coarse-inclusive-no-avoid';
            % 08c364 source vectors explicitly permit occupied 0,31,255.
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,31,[0 31],0),0);
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,31,[0 31],31),31);
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,255,255,255),255);
        end

        function rebuildListIncludesZeroButExcludesRangeEndpoint(testCase)
            profile = 'hist-2014-zero-based-rebuild-list';
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,31,[0 30],0),0);
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,31,[0 30],30),30);
            testCase.verifyError(@()csr.mac.SlotSelection.historicalSlot(profile,31,[],31), ...
                'csr:mac:HistoricalSlotDraw');
        end

        function fineTableIgnoresReservationsAndExcludesZero(testCase)
            profile = 'hist-2015-fine-one-based-table-no-avoid';
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,31,[1 31],1),1);
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,31,[1 31],31),31);
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,255,254,254),254);
            testCase.verifyError(@()csr.mac.SlotSelection.historicalSlot(profile,31,[],0), ...
                'csr:mac:HistoricalSlotDraw');
        end

        function fineTableDefectFailsRatherThanWrappingOrClamping(testCase)
            testCase.verifyError(@()csr.mac.SlotSelection.historicalSlot( ...
                'hist-2015-fine-one-based-table-no-avoid',255,[],255), ...
                'csr:mac:HistoricalTableIndex');
        end

        function moduloProbeUsesIntentionalRangeEndpointWrap(testCase)
            profile = 'hist-2014-next-tslot-modulo-probe';
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,31,0:30,31),31);
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,31,31,31),1);
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,31,30,30),0);
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,31,[31 1 1 2],31),3);
        end

        function moduloProbeComparesCurrentCountersDirectly(testCase)
            profile = 'hist-2014-next-tslot-modulo-probe';
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,31,[-7 -1 32 255],0),0);
            % Occupancy zero matters directly, unlike the current one-based
            % free-slot ordinal walk. No ordinal or slot-range clamp is used.
            testCase.verifyEqual(csr.mac.SlotSelection.historicalSlot(profile,31,[0 1 2],0),3);
        end

        function moduloExhaustionFailsEvenWhenEndpointIsFree(testCase)
            testCase.verifyError(@()csr.mac.SlotSelection.historicalSlot( ...
                'hist-2014-next-tslot-modulo-probe',31,0:30,0), ...
                'csr:mac:HistoricalProbeExhausted');
        end

        function profileControlsRealMacPreparationDraw(testCase)
            profiles = csr.mac.SlotSelection.profiles();
            supports = [1 63;0 31;0 62;1 63;0 31];
            for index = 1:numel(profiles)
                predictor = csr.sim.RandomStreams(128);
                expected = randi(predictor.get(1,'mac'),supports(index,:));
                [mac,scheduler] = fixture(profiles{index},4,8);
                mac.enqueue(frame(1,2));
                scheduler.run(0.014);
                testCase.verifyEqual(mac.ReservationSlot,expected,profiles{index});
                testCase.verifyTrue(mac.PreparationActive);
                testCase.verifyEqual(mac.Counters.Transmissions,0);
            end
        end

        function realModuloProfileReadsDecayedNeighborReservation(testCase)
            predictor = csr.sim.RandomStreams(128);
            initial = randi(predictor.get(1,'mac'),[0 31]);
            [mac,scheduler] = fixture('hist-2014-next-tslot-modulo-probe',4,8);
            heard = frame(2,1); heard.SourceId = 2;
            heard.ReservationSlot = initial+1;
            mac.receive(heard,struct('Success',true));
            mac.receive(heard,struct('Success',true));
            mac.enqueue(frame(1,2));
            scheduler.run(0.014);
            testCase.verifyEqual(mac.neighborReservation(2),initial);
            testCase.verifyEqual(mac.ReservationSlot,mod(initial+1,31));
        end

        function realFineTableProfileReturnsOccupiedDraw(testCase)
            predictor = csr.sim.RandomStreams(128);
            initial = randi(predictor.get(1,'mac'),[1 63]);
            [mac,scheduler] = fixture('hist-2015-fine-one-based-table-no-avoid',4,8);
            heard = frame(2,1); heard.SourceId = 2;
            heard.ReservationSlot = initial+1;
            mac.receive(heard,struct('Success',true));
            mac.receive(heard,struct('Success',true));
            mac.enqueue(frame(1,2));
            scheduler.run(0.014);
            testCase.verifyEqual(mac.neighborReservation(2),initial);
            testCase.verifyEqual(mac.ReservationSlot,initial);
        end

        function controlledOverridePrecedesHistoricalDrawAndDefect(testCase)
            scheduler = csr.sim.EventScheduler();
            streams = csr.sim.RandomStreams(128);
            expected = streams.get(1,'mac').State;
            options = csr.mac.Layer.defaults();
            options.DutyCycleEnabled = false;
            options.SlotProfile = 'hist-2015-fine-one-based-table-no-avoid';
            options.ActiveNodes = 16;
            options.ReservationSlotOverride = 255;
            mac = csr.mac.Layer(1,scheduler,streams,options,struct('Transmit',@(~,~)[]));
            mac.enqueue(frame(1,2));
            scheduler.run(0.014);
            testCase.verifyEqual(mac.ReservationSlot,255);
            testCase.verifyEqual(streams.get(1,'mac').State,expected);
        end
    end
end

function [mac,scheduler] = fixture(profile,local,reported)
scheduler = csr.sim.EventScheduler();
options = csr.mac.Layer.defaults();
options.DutyCycleEnabled = false;
options.SlotProfile = profile;
options.ActiveNodes = local;
options.ReportedActiveNodes = reported;
mac = csr.mac.Layer(1,scheduler,csr.sim.RandomStreams(128),options, ...
    struct('Transmit',@(~,~)[]));
end

function output = frame(sequence,peer)
output = struct('Id',uint64(sequence),'SourceId',1,'DestinationId',peer, ...
    'Kind','DATA','Sequence',uint16(sequence),'Dscp',0, ...
    'AckRequired',true,'HasAckWindow',false,'AckBitmap',uint64(0), ...
    'DackBitmap',uint64(0),'RateKeyKbps',8,'TxPowerDbm',0, ...
    'WirePayloadBytes',60,'ApplicationPayloadBytes',20, ...
    'GeneratedSeconds',0,'Preamble','long','EnvelopeProfile','bare');
end
