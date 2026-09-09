classdef TestMacLayer < matlab.unittest.TestCase
    methods (Test)
        function queueLimitRejectsNewPriorityAndPreservesStableOrder(testCase)
            [mac, scheduler, observed] = fixture(struct('DataQueueLimit', 3));
            testCase.verifyTrue(mac.enqueue(frame(1, 'DATA', 2, 2)));
            testCase.verifyTrue(mac.enqueue(frame(2, 'DATA', 2, 5)));
            testCase.verifyTrue(mac.enqueue(frame(3, 'DATA', 2, 5)));
            testCase.verifyFalse(mac.enqueue(frame(4, 'DATA', 2, 63)));
            scheduler.run(0.326);
            sent = observed();
            testCase.verifyEqual(cellfun(@(item) double(item.Sequence), sent{1}.Segments), [2 3 1]);
            testCase.verifyEqual(sent{1}.Dscp, 5);
            testCase.verifyEqual(mac.Counters.DataQueueDrops, 1);
            testCase.verifyEqual(mac.Counters.MaxDataQueueDepth, 3);
        end

        function fullAckQueueStillReplacesCumulativeWindow(testCase)
            [mac, scheduler, observed] = fixture(struct('AckQueueLimit', 1));
            first = frame(1, 'ACK', 2, 0);
            first.HasAckWindow = true;
            second = first;
            second.Sequence = uint16(2);
            second.AckBitmap = uint64(3);
            testCase.verifyTrue(mac.enqueue(first));
            testCase.verifyFalse(mac.enqueue(frame(3, 'ACK', 3, 0)));
            testCase.verifyTrue(mac.enqueue(second));
            testCase.verifyEqual(mac.AckQueueCount, 1);
            scheduler.run(0.326);
            sent = observed();
            testCase.verifyEqual(sent{1}.Segments{1}.Sequence, uint16(2));
            testCase.verifyEqual(sent{1}.Segments{1}.AckBitmap, uint64(3));
            testCase.verifyEqual(mac.Counters.AckQueueDrops, 1);
            testCase.verifyEqual(mac.Counters.AckReplacements, 1);
        end

        function exactAckDeduplicatesAndMacOwnsFiveTransmissions(testCase)
            [mac, scheduler, observed] = fixture(struct());
            heard = frame(0, 'DATA', 1, 0);
            heard.SourceId = 2;
            mac.receive(heard, struct('Success', true));
            ack = frame(7, 'ACK', 2, 0);
            testCase.verifyTrue(mac.enqueue(ack));
            testCase.verifyTrue(mac.enqueue(ack));
            testCase.verifyEqual(mac.AckQueueCount, 1);
            scheduler.run(2);
            testCase.verifyEqual(numel(observed()), 5);
            testCase.verifyEqual(mac.Counters.AckTransmissions, 5);
            testCase.verifyEqual(mac.AckQueueCount, 0);
        end

        function canceledDataNeverReachesTransmitter(testCase)
            [mac, scheduler, observed] = fixture(struct());
            mac.enqueue(frame(65535, 'DATA', 2, 0));
            mac.enqueue(frame(0, 'DATA', 2, 0));
            testCase.verifyEqual(mac.cancel(2, uint16(65535)), 1);
            testCase.verifyEqual(mac.cancel(2, uint16(65535)), 0);
            scheduler.run(0.326);
            sent = observed();
            testCase.verifyEqual(numel(sent{1}.Segments), 1);
            testCase.verifyEqual(sent{1}.Segments{1}.Sequence, uint16(0));
            testCase.verifyEqual(mac.Counters.Canceled, 1);
        end

        function sentCallbackUsesActualTransmitInstant(testCase)
            scheduler = csr.sim.EventScheduler();
            times = [];
            transmitted = false;
            options = csr.mac.Layer.defaults();
            options.DutyCycleEnabled = false;
            options.ReservationSlotOverride = 1;
            mac = csr.mac.Layer(1, scheduler, csr.sim.RandomStreams(128), options, ...
                struct('Transmit', @transmit, 'Sent', @sent));
            mac.enqueue(frame(1, 'DATA', 2, 0));
            scheduler.run(0.31);
            testCase.verifyEmpty(times);
            scheduler.run(0.326);
            testCase.verifyEqual(times, 0.325, 'AbsTol', 1e-12);
            function transmit(~, ~), transmitted = true; end
            function sent(~)
                testCase.verifyTrue(transmitted);
                times(end + 1) = scheduler.Now;
            end
        end

        function syncAndTrackFreezeAccessCountdown(testCase)
            scheduler = csr.sim.EventScheduler();
            sync = true;
            count = 0;
            options = csr.mac.Layer.defaults();
            options.DutyCycleEnabled = false;
            options.ReservationSlotOverride = 1;
            mac = csr.mac.Layer(1, scheduler, csr.sim.RandomStreams(128), options, ...
                struct('Transmit', @transmit, 'HasSync', @hasSync));
            mac.enqueue(frame(1, 'DATA', 2, 0));
            scheduler.run(0.5);
            testCase.verifyEqual(mac.ReservationCounter, 1);
            testCase.verifyEqual(count, 0);
            mac.receiverChanged('Track');
            sync = false;
            scheduler.run(0.8);
            testCase.verifyEqual(mac.ReservationCounter, 1);
            testCase.verifyEqual(count, 0);
            mac.receiverChanged('Search');
            scheduler.run(0.84);
            testCase.verifyEqual(count, 1);
            function transmit(~, ~), count = count + 1; end
            function present = hasSync()
                % Read the current flag instead of capturing its initial value.
                present = sync;
            end
        end

        function acknowledgementIsPackedBeforePriorityData(testCase)
            [mac, scheduler, observed] = fixture(struct());
            mac.enqueue(frame(1, 'DATA', 2, 63));
            mac.enqueue(frame(2, 'ACK', 3, 0));
            scheduler.run(0.326);
            sent = observed();
            testCase.verifyEqual(sent{1}.Segments{1}.Kind, 'ACK');
            testCase.verifyEqual(sent{1}.Segments{2}.Kind, 'DATA');
            testCase.verifyEqual(sent{1}.Dscp, 63);
            testCase.verifyEqual(mac.AckQueueCount, 1);
            testCase.verifyEqual(mac.DataQueueCount, 0);
        end

        function strictConcatBoundaryBlocksLaterHead(testCase)
            [mac, scheduler, observed] = fixture(struct());
            first = frame(1, 'DATA', 2, 0);
            second = frame(2, 'DATA', 2, 0);
            first.WirePayloadBytes = 128;
            second.WirePayloadBytes = 128;
            mac.enqueue(first);
            mac.enqueue(second);
            mac.enqueue(frame(3, 'DATA', 2, 0));
            scheduler.run(0.326);
            sent = observed();
            testCase.verifyEqual(numel(sent{1}.Segments), 1);
            testCase.verifyEqual(mac.DataQueueCount, 2);
        end

        function oversizedConcatHeadRemainsVisibleAndPending(testCase)
            [mac, scheduler, observed] = fixture(struct());
            large = frame(1, 'DATA', 2, 0);
            large.WirePayloadBytes = 256;
            mac.enqueue(large);
            mac.enqueue(frame(2, 'DATA', 2, 0));
            scheduler.run(1);
            testCase.verifyEmpty(observed());
            testCase.verifyEqual(mac.DataQueueCount, 2);
            testCase.verifyEqual(mac.Counters.PackingBlocked, 1);
        end

        function sourceOversizedRoutingSectionIsPackingBlockedAtEightKbps(testCase)
            [mac, scheduler, observed] = fixture(struct());
            mac.enqueue(controlFrame(1, [2], 'ROUTING', 716, 8));
            mac.enqueue(controlFrame(2, [2], 'ROUTING', 26, 8));
            scheduler.run(1);
            testCase.verifyEmpty(observed());
            testCase.verifyEqual(mac.DataQueueCount, 2);
            testCase.verifyEqual(mac.Counters.PackingBlocked, 1);
        end

        function multiSectionRoutingMakesProgressAtOneTwentyEightKbps(testCase)
            [mac, scheduler, observed] = fixture(struct());
            mac.enqueue(controlFrame(1, [2], 'ROUTING', 716, 128));
            mac.enqueue(controlFrame(2, [2], 'ROUTING', 716, 128));
            scheduler.run(0.326);
            sent = observed();
            testCase.assertNumElements(sent, 1);
            testCase.verifyEqual(numel(sent{1}.Segments), 2);
            testCase.verifyEqual(sent{1}.RateKeyKbps, 128);
            testCase.verifyEqual(mac.DataQueueCount, 0);
        end

        function highRateHeadsMakeProgressWithoutInventedConcatLimit(testCase)
            [mac, scheduler, observed] = fixture(struct());
            first = frame(1, 'DATA', 2, 0);
            first.RateKeyKbps = 500;
            second = first;
            second.Sequence = uint16(2);
            mac.enqueue(first);
            mac.enqueue(second);
            scheduler.run(0.326);
            sent = observed();
            testCase.verifyEqual(numel(sent{1}.Segments), 1);
            testCase.verifyEqual(sent{1}.RateKeyKbps, 500);
            testCase.verifyEqual(mac.DataQueueCount, 1);
        end

        function aggregateUsesSlowestRateAndItsPower(testCase)
            [mac, scheduler, observed] = fixture(struct());
            fast = frame(1, 'DATA', 2, 0);
            fast.RateKeyKbps = 128;
            fast.TxPowerDbm = 20;
            slow = frame(2, 'DATA', 2, 0);
            slow.TxPowerDbm = -5;
            mac.enqueue(fast);
            mac.enqueue(slow);
            scheduler.run(0.326);
            sent = observed();
            testCase.verifyEqual(sent{1}.RateKeyKbps, 8);
            testCase.verifyEqual(sent{1}.TxPowerDbm, -5);
            testCase.verifyEqual(sent{1}.WirePayloadBytes, 120);
        end

        function aggregateHasAtMostSixteenSegments(testCase)
            [mac, scheduler, observed] = fixture(struct());
            for index = 1:20
                item = frame(index, 'DATA', 2, 0);
                item.RateKeyKbps = 128;
                mac.enqueue(item);
            end
            scheduler.run(0.326);
            sent = observed();
            testCase.verifyEqual(numel(sent{1}.Segments), 16);
            testCase.verifyEqual(mac.DataQueueCount, 4);
        end

        function firstContactReservationIgnoredAndKnownOneDecays(testCase)
            [mac, scheduler] = fixture(struct());
            heard = frame(0, 'DATA', 1, 0);
            heard.SourceId = 2;
            heard.ReservationSlot = 9;
            mac.receive(heard, struct('Success', true));
            testCase.verifyEqual(mac.neighborReservation(2), -1);
            mac.receive(heard, struct('Success', true));
            testCase.verifyEqual(mac.neighborReservation(2), 9);
            mac.enqueue(frame(1, 'DATA', 2, 0));
            scheduler.run(0.014);
            testCase.verifyEqual(mac.neighborReservation(2), 8);
            mac.receiverChanged('Track');
            scheduler.run(0.03);
            testCase.verifyEqual(mac.neighborReservation(2), 8);
        end

        function preambleFollowsFreshnessAndOrderedAggregateWalk(testCase)
            [mac, scheduler, observed] = fixture(struct());
            heard = frame(0, 'DATA', 1, 0);
            heard.SourceId = 2;
            mac.receive(heard, struct('Success', true));
            mac.enqueue(frame(1, 'DATA', 3, 1)); % Unknown first.
            mac.enqueue(frame(2, 'DATA', 2, 0)); % Known final => short.
            scheduler.run(0.326);
            sent = observed();
            testCase.verifyEqual(sent{1}.Preamble, 'short');
            [other, otherScheduler, trace] = fixture(struct());
            other.receive(heard, struct('Success', true));
            other.enqueue(frame(1, 'DATA', 2, 1));
            other.enqueue(frame(2, 'DATA', 3, 0)); % Unknown final => long.
            otherScheduler.run(0.326);
            sent = trace();
            testCase.verifyEqual(sent{1}.Preamble, 'long');
        end

        function standaloneGroupedControlUsesOnlyPrimaryForPreamble(testCase)
            [mac, scheduler, observed] = fixture(struct());
            heard = frame(0, 'DATA', 1, 0); heard.SourceId = 2;
            mac.receive(heard, struct('Success', true));
            mac.enqueue(controlFrame(1, [2 3], 'ROUTING', 80, 128));
            scheduler.run(0.326);
            sent = observed();
            testCase.assertNumElements(sent, 1);
            % Frozen source quirk: outside concatenation, only the primary
            % destination contributes to preamble freshness.
            testCase.verifyEqual(sent{1}.Preamble, 'short');
        end

        function keyRequestReplacementCancelsOnlyMatchingUnsentControl(testCase)
            [mac, ~, observed] = fixture(struct());
            mac.enqueue(controlFrame(1, 2, 'KEY_REQUEST', 18, 8));
            mac.enqueue(controlFrame(2, 3, 'KEY_REQUEST', 18, 8));
            mac.enqueue(controlFrame(3, 2, 'KEY_UPDATE', 62, 8));
            testCase.verifyEqual(mac.cancelControl(2, 'KEY_REQUEST'), 1);
            testCase.verifyEqual(mac.DataQueueCount, 2);
            testCase.verifyEqual(mac.Counters.Canceled, 1);
            testCase.verifyEmpty(observed());
        end

        function dutyWakeAndNoSignalSleepActuallyTransition(testCase)
            [mac, scheduler] = fixture(struct('DutyCycleEnabled', true));
            mac.start();
            testCase.verifyEqual(mac.State, 'Idle');
            scheduler.run(0.987);
            testCase.verifyEqual(mac.State, 'Idle');
            scheduler.run(0.988);
            testCase.verifyEqual(mac.State, 'Search');
            scheduler.run(0.996901);
            testCase.verifyEqual(mac.State, 'Idle');
            testCase.verifyFalse(mac.PreparationActive);
        end

        function idleQueueWakesAtGlobalSlotThenUsesRelativeSlots(testCase)
            scheduler = csr.sim.EventScheduler();
            sentTimes = [];
            options = csr.mac.Layer.defaults();
            options.ReservationSlotOverride = 1;
            mac = csr.mac.Layer(1, scheduler, csr.sim.RandomStreams(128), options, ...
                struct('Transmit', @transmit));
            mac.start();
            scheduler.scheduleAt(0.002, @() mac.enqueue(frame(1, 'DATA', 2, 0)));
            scheduler.run(0.012);
            testCase.verifyEqual(mac.State, 'Idle');
            scheduler.run(0.013);
            testCase.verifyEqual(mac.State, 'Search');
            testCase.verifyTrue(mac.PreparationActive);
            scheduler.run(0.339);
            testCase.verifyEqual(sentTimes, 0.338, 'AbsTol', 1e-12);
            function transmit(~, ~), sentTimes(end + 1) = scheduler.Now; end
        end

        function trackedReceiveStartsShortSearchOrImmediateAckPreparation(testCase)
            [mac, scheduler] = fixture(struct('DutyCycleEnabled', true));
            mac.start();
            mac.receiverChanged('Search');
            mac.receiverChanged('Track');
            mac.receiverChanged('Search');
            scheduler.run(0.007801);
            testCase.verifyEqual(mac.State, 'Idle');
            mac.receiverChanged('Search');
            mac.receiverChanged('Track');
            mac.enqueue(frame(1, 'ACK', 2, 0));
            testCase.verifyFalse(mac.PreparationActive);
            mac.receiverChanged('Search');
            testCase.verifyTrue(mac.PreparationActive);
            scheduler.run(0.02);
            testCase.verifyEqual(mac.State, 'Search');
        end

        function slotRangeAndGuardMatchSource(testCase)
            actual = arrayfun(@(nodes) csr.mac.Layer.slotRange(nodes), 0:17);
            testCase.verifyEqual(actual, [15 18 21 25 31 37 44 52 63 75 89 106 127 151 180 214 255 255]);
            testCase.verifyEqual(csr.mac.Layer.slotRange(8, 10), 53);
            testCase.verifyEqual(csr.mac.Layer.slotRange(8, 61), 2);
            testCase.verifyEqual(csr.mac.Layer.slotRange(8, 62), 63);
            testCase.verifyEqual(csr.mac.Layer.slotRange(8, -1), 63);
        end
    end
end

function [mac, scheduler, observed] = fixture(overrides)
scheduler = csr.sim.EventScheduler();
transmissions = {};
options = csr.mac.Layer.defaults();
options.DutyCycleEnabled = false;
options.ReservationSlotOverride = 1;
names = fieldnames(overrides);
for index = 1:numel(names), options.(names{index}) = overrides.(names{index}); end
mac = csr.mac.Layer(1, scheduler, csr.sim.RandomStreams(128), options, ...
    struct('Transmit', @transmit));
observed = @getTransmissions;
    function transmit(value, ~), transmissions{end + 1} = value; end
    function values = getTransmissions()
        % Share the mutable log with transmit after fixture returns.
        values = transmissions;
    end
end

function output = frame(sequence, kind, peer, dscp)
output = struct('Id', uint64(sequence + 1), 'SourceId', 1, ...
    'DestinationId', double(peer), 'Kind', kind, 'Sequence', uint16(sequence), ...
    'Dscp', double(dscp), 'AckRequired', strcmp(kind, 'DATA'), ...
    'HasAckWindow', false, 'AckBitmap', uint64(0), 'DackBitmap', uint64(0), ...
    'RateKeyKbps', 8, 'TxPowerDbm', 0, 'WirePayloadBytes', 60, ...
    'ApplicationPayloadBytes', 20 * strcmp(kind, 'DATA'), ...
    'GeneratedSeconds', 0, 'Preamble', 'long', 'EnvelopeProfile', 'bare');
end

function output = controlFrame(sequence, peers, kind, bytes, rate)
peers = reshape(double(peers), 1, []);
output = frame(sequence, 'CONTROL', peers(1), 7);
output.AckRequired = ~strcmp(kind, 'KEY_REQUEST');
output.DestinationIds = peers;
output.HopSequences = uint16(sequence + (0:numel(peers)-1));
output.Control = struct('Id', uint64(sequence), 'Type', kind, 'Payload', struct(), ...
    'WirePayloadBytes', bytes);
output.WirePayloadBytes = bytes;
output.RateKeyKbps = rate;
end
