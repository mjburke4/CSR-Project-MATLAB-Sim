classdef TestHopFrames < matlab.unittest.TestCase
    % Independent byte constants copied from the original ns-3 smoke fixture,
    % csr-opnet-packet-envelope-smoke.cc at 486d9e0. MATLAB execution required.
    methods (Test)
        function modeledSizesExcludeObservationAndSecurityMetadata(test)
            app = TestHopFrames.app();
            frame = csr.hop.Frames.data(app,257,16777214,65535,struct());
            test.verifyEqual(frame.WirePayloadBytes,96);
            test.verifyEqual(frame.SourceId,257);
            test.verifyEqual(frame.DestinationId,16777214);
            test.verifyEqual(frame.Sequence,uint16(65535));
            test.verifyEqual(frame.App,app);
            test.verifyEqual(frame.Id,uint64(0));
            options = struct('EnvelopeProfile','pairwise16-size-only');
            secureSize = csr.hop.Frames.data(app,257,16777214,1,options);
            test.verifyEqual(secureSize.WirePayloadBytes,101);
            test.verifyEqual(secureSize.App.Id,app.Id);
            test.verifyEqual(secureSize.EnvelopeProfile,'pairwise16-size-only');
        end

        function cumulativeAckBytesPreserveHighBits(test)
            ack = bitor(bitshift(uint64(hex2dec('01234567')),32),uint64(hex2dec('89abcdef')));
            dack = bitor(bitshift(uint64(hex2dec('fedcba98')),32),uint64(hex2dec('76543210')));
            frame = csr.hop.Frames.acknowledgment(hex2dec('123456'),hex2dec('abcdef'), ...
                hex2dec('1357'),ack,dack,struct());
            expected = uint8([18 52 86 171 205 239 19 87 ...
                1 35 69 103 137 171 205 239 254 220 186 152 118 84 50 16]);
            test.verifyEqual(csr.hop.Frames.serializeAckBody(frame),expected);
            test.verifyEqual(frame.WirePayloadBytes,41);
            decoded = csr.hop.Frames.deserializeAckBody(expected);
            test.verifyEqual(decoded.AckBitmap,ack);
            test.verifyEqual(decoded.DackBitmap,dack);
            test.verifyEqual(decoded.Sequence,uint16(hex2dec('1357')));
            test.verifyTrue(decoded.HasAckWindow);
        end

        function ackEnvelopeProfilesAndSingleAck(test)
            radio = struct('HasAckWindow',false);
            frame = csr.hop.Frames.acknowledgment(1,2,3,uint64(0),uint64(0),radio);
            test.verifyEqual(frame.WirePayloadBytes,25);
            test.verifyEqual(frame.Dscp,7);
            test.verifyEqual(csr.hop.Frames.serializeAckBody(frame),uint8([0 0 1 0 0 2 0 3]));
            decoded = csr.hop.Frames.deserializeAckBody(csr.hop.Frames.serializeAckBody(frame));
            test.verifyFalse(decoded.HasAckWindow);
            radio.EnvelopeProfile = 'pairwise16-size-only';
            frame = csr.hop.Frames.acknowledgment(1,2,3,0,0,radio);
            test.verifyEqual(frame.WirePayloadBytes,30);
            radio.HasAckWindow = true; radio.Kind = 'DACK';
            frame = csr.hop.Frames.acknowledgment(1,2,3,0,1,radio);
            test.verifyEqual(frame.WirePayloadBytes,46);
            test.verifyEqual(frame.Kind,'DACK');
        end

        function aggregateKeepsEveryEnvelopeAndSlowestRatePower(test)
            app = TestHopFrames.app();
            a = csr.hop.Frames.acknowledgment(1,2,3,1,0, ...
                struct('RateKeyKbps',8,'TxPowerDbm',5));
            b = csr.hop.Frames.data(app,1,3,4, ...
                struct('RateKeyKbps',16,'TxPowerDbm',30,'Dscp',4));
            c = csr.hop.Frames.data(app,1,4,5, ...
                struct('RateKeyKbps',8,'TxPowerDbm',10,'Dscp',3));
            aggregate = csr.hop.Frames.aggregate({a,b,c},'short');
            test.verifyEqual(aggregate.WirePayloadBytes,41+96+96);
            test.verifyEqual(aggregate.ApplicationPayloadBytes,128);
            test.verifyEqual(aggregate.RateKeyKbps,8);
            test.verifyEqual(aggregate.TxPowerDbm,10); % Higher-rate 30 dBm ignored.
            test.verifyEqual(aggregate.Dscp,4); % The ACK member's DSCP 7 is excluded.
            test.verifyEqual(aggregate.Segments,{a,b,c});
            test.verifyEqual(aggregate.DestinationId,2);
            test.verifyEqual(aggregate.Preamble,'short');
        end

        function allFixedPacketSizesMatchOriginalSource(test)
            formats = {'Ack','Hello','Hop','Mac','MacHopInstance','Network', ...
                'OtaLongPreamble','OtaShortPreamble','Routes','Snmp','SentInfo'};
            sizes = [8 12 8 17 8 7 996 23 11 6 3];
            for k = 1:numel(formats)
                test.verifyEqual(csr.hop.Frames.fixedSize(formats{k}),sizes(k));
                bytes = csr.hop.Frames.serializeModel(formats{k},struct());
                test.verifyEqual(numel(bytes),sizes(k));
                [fields,payload] = csr.hop.Frames.deserializeModel(formats{k},bytes);
                test.verifyEqual(csr.hop.Frames.serializeModel(formats{k},fields,payload),bytes);
            end
        end

        function fixedControlLayoutsMatchOriginalGoldenBytes(test)
            fields = struct('source',hex2dec('123456'),'destination',hex2dec('abcdef'), ...
                'sequence16',hex2dec('1357'));
            expected = uint8([18 52 86 171 205 239 19 87]);
            test.verifyEqual(csr.hop.Frames.serializeModel('Ack',fields),expected);
            test.verifyEqual(csr.hop.Frames.serializeModel('MacHopInstance',fields),expected);
            fields = struct('sequence8',18,'nodeId',hex2dec('345678'), ...
                'capabilityNumber',154,'capability',188,'cost',hex2dec('def0'), ...
                'timeOffset',hex2dec('12345678'));
            test.verifyEqual(csr.hop.Frames.serializeModel('Hello',fields), ...
                uint8([18 52 86 120 154 188 222 240 18 52 86 120]));
            test.verifyEqual(csr.hop.Frames.serializeModel('Routes',fields), ...
                uint8([52 86 120 154 188 222 240 18 52 86 120]));
            fields = struct('message',hex2dec('1234'),'value',hex2dec('89abcdef'));
            test.verifyEqual(csr.hop.Frames.serializeModel('Snmp',fields), ...
                uint8([18 52 137 171 205 239]));
        end

        function inheritedLayoutsPreserveNetworkDscpTrailer(test)
            payload = uint8([222 173 190 239]);
            fields = struct('source',hex2dec('123456'),'destination',hex2dec('abcdef'), ...
                'numberOfDestinations',2,'sequence8',122,'dscp',126);
            test.verifyEqual(csr.hop.Frames.serializeModel('Hop',fields,payload), ...
                uint8([18 52 86 2 171 205 239 122 222 173 190 239]));
            expected = uint8([18 52 86 171 205 239 222 173 190 239 126]);
            test.verifyEqual(csr.hop.Frames.serializeModel('Network',fields,payload),expected);
            [decoded,recovered] = csr.hop.Frames.deserializeModel('Network',expected);
            test.verifyEqual(decoded.dscp,126);
            test.verifyEqual(recovered,payload);
            mac = struct('globalTime',hex2dec('01020304'),'globalAddress',hex2dec('112233'), ...
                'globalCost',68,'txPower',85,'rxPower',102,'active',119, ...
                'source',hex2dec('8899aa'),'payloadLength',hex2dec('bbcc'),'type',221);
            test.verifyEqual(csr.hop.Frames.serializeModel('Mac',mac,payload), ...
                uint8([1 2 3 4 17 34 51 68 85 102 119 136 153 170 187 204 221 222 173 190 239]));
        end

        function otaSpeedUsesLiteral16BitsAndPreambleLengths(test)
            fields = struct('startOfFrame',hex2dec('1234'),'speed',1000, ...
                'length',hex2dec('2345'),'fcs',hex2dec('def01234'));
            payload = uint8([165 90]);
            short = csr.hop.Frames.serializeModel('OtaShortPreamble',fields,payload);
            test.verifyEqual(short(1:13),zeros(1,13,'uint8'));
            test.verifyEqual(short(14:end),uint8([18 52 3 232 35 69 165 90 222 240 18 52]));
            long = csr.hop.Frames.serializeModel('OtaLongPreamble',fields,payload);
            test.verifyEqual(numel(long),998);
            test.verifyEqual(long(1:986),zeros(1,986,'uint8'));
            [decoded,recovered] = csr.hop.Frames.deserializeModel('OtaLongPreamble',long);
            test.verifyEqual(decoded.speed,1000);
            test.verifyEqual(recovered,payload);
            for rate = [8 16 32 64 128 500 1000]
                test.verifyEqual(csr.hop.Frames.decodeRateKey(csr.hop.Frames.encodeRateKey(rate)),rate);
            end
            test.verifyEqual(csr.hop.Frames.encodeRateKey(500),uint8(129));
            test.verifyEqual(csr.hop.Frames.encodeRateKey(1000),uint8(130));
        end

        function malformedFieldsDoNotSilentlyNarrow(test)
            test.verifyError(@() csr.hop.Frames.serializeModel('Ack', ...
                struct('source',16777216)), 'csr:hop:InvalidField');
            test.verifyError(@() csr.hop.Frames.serializeModel('Hop', ...
                struct('sequence8',256)), 'csr:hop:InvalidField');
            test.verifyError(@() csr.hop.Frames.deserializeModel('Ack',uint8(zeros(1,7))), ...
                'csr:hop:InvalidWireLength');
            test.verifyError(@() csr.hop.Frames.serializeModel('Ack',struct(),uint8(1)), ...
                'csr:hop:UnexpectedPayload');
            test.verifyError(@() csr.hop.Frames.encodeRateKey(129),'csr:hop:InvalidRateCode');
            test.verifyError(@() csr.hop.Frames.aggregate({}),'csr:hop:EmptyAggregate');
        end

        function configurationUsesLayerDefaultsAndNormalizesIntegers(test)
            input = struct('Mac',struct('DataQueueLimit',uint16(2),'DutyCycleEnabled',0), ...
                'Hop',struct('NsdpLimit',uint8(0),'MaxResends',uint8(0)));
            config = csr.hop.validateConfig(input);
            test.verifyEqual(config.Mac.DataQueueLimit,2);
            test.verifyFalse(config.Mac.DutyCycleEnabled);
            test.verifyEqual(config.Hop.NsdpLimit,0);
            test.verifyEqual(config.Hop.MaxResends,0);
            defaults = csr.hop.Layer.defaults();
            test.verifyEqual(config.Hop.ResendSeconds,defaults.ResendSeconds);
            test.verifyEqual(config.Hop.PendingThreshold,16);
        end

        function configurationRejectsUnknownAndInvalidSettings(test)
            test.verifyError(@() csr.hop.validateConfig(struct('Mac',struct('QueueLmit',1))), ...
                'csr:hop:InvalidConfig');
            test.verifyError(@() csr.hop.validateConfig(struct('Hop',struct('ResendSeconds',0))), ...
                'csr:hop:InvalidConfig');
            test.verifyError(@() csr.hop.validateConfig(struct('Mac',struct('DutyCycleEnabled',2))), ...
                'csr:hop:InvalidConfig');
            test.verifyError(@() csr.hop.validateConfig(struct('Mac',struct('SlotSeconds',NaN))), ...
                'csr:hop:InvalidConfig');
        end
    end
    methods (Static, Access = private)
        function app = app()
            app = struct('Id',uint64(123),'SourceId',1,'DestinationId',9, ...
                'GeneratedSeconds',0.25,'ApplicationPayloadBytes',64,'Dscp',3);
        end
    end
end
