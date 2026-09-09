classdef TestRoutingCodec < matlab.unittest.TestCase
    % Golden fields/boundaries from csr-nwk-arl-routing-stream-smoke.cc at
    % 486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b. Requires actual MATLAB.
    methods (Test)
        function bigEndianGoldenStreamPreservesSignedAndWideFields(test)
            records = {struct('Operation','INFO','Info',routingInfo()), ...
                update(hex2dec('0abcde'),2,2,hex2dec('89abcdef'),[hex2dec('123456') 66]), ...
                struct('Operation','DELETE','NodeId',hex2dec('654321')), ...
                struct('Operation','FLUSH'),struct('Operation','REQUEST')};
            expected = uint8([4 0 8 0 128 255 81 1 44 0 95 0 140 254 62 2 113 ...
                2 10 188 222 2 0 2 137 171 205 239 18 52 86 0 0 66 ...
                1 101 67 33 0 3]);
            test.verifyEqual(csr.nwk.RoutingCodec.encodeRecords(records),expected);
            test.verifyEqual(csr.nwk.RoutingCodec.decodeRecords(expected),records);
            sections = csr.nwk.RoutingCodec.sections(expected,hex2dec('12345678'));
            test.verifyEqual(sections{1},[uint8([18 52 86 120 0 1]) expected]);
        end

        function sixteenBitHopCountCrossesSectionBoundary(test)
            record = update(hex2dec('010203'),3,258,hex2dec('fedcba98'),1:258);
            stream = csr.nwk.RoutingCodec.encodeRecords({record});
            test.verifyEqual(stream(1:11),uint8([2 1 2 3 3 1 2 254 220 186 152]));
            sections = csr.nwk.RoutingCodec.sections(stream,9);
            test.verifyEqual(cellfun(@numel,sections),[700 97]);
            receiver = csr.nwk.Reassembly();
            [complete,records] = receiver.accept(2,sections{2});
            test.verifyFalse(complete); test.verifyEmpty(records);
            [complete,records,sequence] = receiver.accept(2,sections{1});
            test.verifyTrue(complete); test.verifyEqual(sequence,9);
            test.verifyEqual(records,{record});
        end

        function originalCrossBoundaryFixtureIs700Plus10Bytes(test)
            [records,sections] = crossBoundary(77);
            test.verifyEqual(cellfun(@numel,sections),[700 10]);
            receiver = csr.nwk.Reassembly();
            [complete,partial] = receiver.accept(2,sections{2});
            test.verifyFalse(complete); test.verifyEmpty(partial);
            state = receiver.stats(); test.verifyEqual(state.PendingMessages,1);
            [complete,recovered] = receiver.accept(2,sections{1});
            test.verifyTrue(complete); test.verifyEqual(recovered,records);
            test.verifyEqual(recovered{41}.NodeId,1039);
            state = receiver.stats(); test.verifyEqual(state.PendingMessages,0);
            test.verifyEqual(state.BufferedBytes,0);
        end

        function conflictsAndDuplicatesCannotOverwriteAcceptedSections(test)
            [records,sections] = crossBoundary(77);
            receiver = csr.nwk.Reassembly(); receiver.accept(2,sections{2});
            [complete,partial] = receiver.accept(2,sections{2});
            test.verifyFalse(complete); test.verifyEmpty(partial);
            changedBody = sections{2}; changedBody(end) = 255;
            receiver.accept(2,changedBody);
            changedTotal = sections{2}; changedTotal(6) = 3;
            receiver.accept(2,changedTotal);
            [complete,recovered] = receiver.accept(2,sections{1});
            test.verifyTrue(complete); test.verifyEqual(recovered,records);
            state = receiver.stats(); test.verifyEqual(state.Duplicates,1);
            test.verifyEqual(state.Conflicts,2); test.verifyEqual(state.Completed,1);
        end

        function malformedCompletedStreamNeverReturnsPartialRecords(test)
            receiver = csr.nwk.Reassembly();
            first = [uint8([0 0 0 5 0 2]) csr.nwk.RoutingCodec.encodeRecords( ...
                {struct('Operation','INFO','Info',routingInfo())})];
            [complete,records] = receiver.accept(2,first);
            test.verifyFalse(complete); test.verifyEmpty(records);
            [complete,records] = receiver.accept(2,uint8([0 0 0 5 1 2 255]));
            test.verifyFalse(complete); test.verifyEmpty(records);
            state = receiver.stats(); test.verifyEqual(state.Malformed,1);
            test.verifyEqual(state.PendingMessages,0);
            [complete,records] = receiver.accept(2,uint8([0 0 0 5 0 1 3]));
            test.verifyTrue(complete); test.verifyEqual(records,{struct('Operation','REQUEST')});
        end

        function peerAndGlobalBoundsEvictOldestIncompleteMessages(test)
            receiver = csr.nwk.Reassembly(struct('MaxMessages',2,'MaxMessagesPerPeer',1));
            [~,a] = crossBoundary(1); [~,b] = crossBoundary(2);
            [~,c] = crossBoundary(3); [~,d] = crossBoundary(4);
            receiver.accept(2,a{2}); receiver.accept(2,b{2}); % Per-peer eviction.
            receiver.accept(3,c{2}); receiver.accept(4,d{2}); % Global eviction.
            state = receiver.stats(); test.verifyEqual(state.PendingMessages,2);
            test.verifyEqual(state.BufferedBytes,8); test.verifyEqual(state.Evicted,2);
            receiver.discardPeer(3);
            state = receiver.stats(); test.verifyEqual(state.PendingMessages,1);
            test.verifyEqual(state.Discarded,1);
            [complete,~] = receiver.accept(4,d{1}); test.verifyTrue(complete);
        end

        function maximumSequenceAndIndependentPeersRemainDistinct(test)
            receiver = csr.nwk.Reassembly();
            [records,sections] = crossBoundary(4294967295);
            receiver.accept(1,sections{1}); receiver.accept(2,sections{2});
            state = receiver.stats(); test.verifyEqual(state.PendingMessages,2);
            [complete,recovered,sequence] = receiver.accept(1,sections{2});
            test.verifyTrue(complete); test.verifyEqual(sequence,4294967295);
            test.verifyEqual(recovered,records);
            [complete,~,sequence] = receiver.accept(1,uint8([0 0 0 0 0 1 3]));
            test.verifyTrue(complete); test.verifyEqual(sequence,0);
            state = receiver.stats(); test.verifyEqual(state.PendingMessages,1);
        end

        function malformedLengthsIndicesAndTruncationAreRejected(test)
            malformed = {uint8([0 0 0 1 0]),uint8([0 0 0 1 0 0]), ...
                uint8([0 0 0 1 2 2]),zeros(1,701,'uint8'),[0 0 0 1 0 1 256]};
            receiver = csr.nwk.Reassembly();
            for index = 1:numel(malformed)
                test.verifyError(@() csr.nwk.RoutingCodec.decodeSection(malformed{index}), ...
                    'csr:nwk:MalformedRouting');
                [complete,records] = receiver.accept(2,malformed{index});
                test.verifyFalse(complete); test.verifyEmpty(records);
            end
            for bytes = {uint8([4 0]),uint8([1 0 1]),uint8([2 0 0 1]), ...
                    uint8([2 0 0 1 1 0 1 0 0 0 1]),uint8(255)}
                test.verifyError(@() csr.nwk.RoutingCodec.decodeRecords(bytes{1}), ...
                    'csr:nwk:MalformedRouting');
            end
            state = receiver.stats(); test.verifyEqual(state.PendingMessages,0);
            test.verifyEqual(state.Malformed,numel(malformed));
        end

        function encodingRejectsNarrowingAndInconsistentPaths(test)
            records = {update(16777216,1,0,0,[]),update(1,256,0,0,[]), ...
                update(1,1,65536,0,[]),update(1,1,0,4294967296,[]), ...
                update(1,1,1,0,[]),update(1,1,1,0,16777216)};
            for index = 1:numel(records)
                test.verifyError(@() csr.nwk.RoutingCodec.encodeRecords(records(index)), ...
                    'csr:nwk:InvalidRoutingRecord');
            end
            test.verifyError(@() csr.nwk.RoutingCodec.encodeRecords({struct('Operation','UPDATE')}), ...
                'csr:nwk:InvalidRoutingRecord');
            info = routingInfo(); info.MinPowerDbmX10 = -32769;
            test.verifyError(@() csr.nwk.RoutingCodec.encodeRecords( ...
                {struct('Operation','INFO','Info',info)}),'csr:nwk:InvalidRoutingRecord');
            test.verifyError(@() csr.nwk.RoutingCodec.sections(uint8([]),1), ...
                'csr:nwk:InvalidRoutingSections');
            test.verifyError(@() csr.nwk.RoutingCodec.sections(zeros(1,694*255+1,'uint8'),1), ...
                'csr:nwk:InvalidRoutingSections');
        end

        function sourceWireLimitsRemainSeparateFromRoutingPolicy(test)
            records = {update(16777215,255,0,4294967295,[])};
            bytes = csr.nwk.RoutingCodec.encodeRecords(records);
            test.verifyEqual(csr.nwk.RoutingCodec.decodeRecords(bytes),records);
            section = csr.nwk.RoutingCodec.decodeSection(uint8([0 0 0 1 0 1]));
            test.verifyEmpty(section.Body); % Source decoder accepts empty body.
            test.verifyError(@() csr.nwk.Reassembly(struct('MaxMessages',0)), ...
                'csr:nwk:InvalidReassemblyConfig');
            test.verifyError(@() csr.nwk.Reassembly(struct('MaxMessage',2)), ...
                'csr:nwk:InvalidReassemblyConfig');
        end
    end
end

function info = routingInfo()
info = struct('MinSpeedKbps',8,'MaxSpeedKbps',128,'MinPowerDbmX10',-175, ...
    'MaxPowerDbmX10',300,'LinkMarginDbX10',95,'LowPowerDbmX10',140, ...
    'TempLowCx10',-450,'TempHighCx10',625);
end

function record = update(node,capability,hops,cost,path)
record = struct('Operation','UPDATE','NodeId',node,'Capability',capability, ...
    'HopCount',hops,'Cost',cost,'Path',path);
end

function [records,sections] = crossBoundary(sequence)
records = {struct('Operation','INFO','Info',routingInfo())};
for index = 0:39
    destination = 1000+index;
    records{end+1} = update(destination,1,2,100+index,[3 destination]); %#ok<AGROW>
end
records{end+1} = struct('Operation','FLUSH');
sections = csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords(records),sequence);
end
