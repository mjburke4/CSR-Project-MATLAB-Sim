classdef TestHistoricalEnvelope < matlab.unittest.TestCase
    % Pinned 486d9e01 source profiles: csr-hop-layer.h ProtectAckFrame,
    % SendData and control constructors; csr-opnet-packet-envelope-smoke.cc.
    % Source executable/application/MAC provenance is tested by the importer.
    methods (Test)
        function productionDefaultRemainsPairwiseAndRequiresMatchingRadio(test)
            config=csr.scenario.routedNetwork('autonomous');
            config=csr.nwk.validateConfig(config);
            test.verifyEqual(config.Nwk.SecurityProfile, ...
                'behavioral-production-pairwise16-size-only');
            test.verifyEqual(config.Radio.EnvelopeProfile,'pairwise16-size-only');
            config.Radio.EnvelopeProfile='bare';
            test.verifyError(@()csr.nwk.validateConfig(config), ...
                'csr:nwk:SecurityProfileMismatch');
        end

        function historicalProfilesAreExplicitAndRetainLifecycleOptions(test)
            reference=csr.nwk.defaults();
            for profile=historicalProfiles()
                config=historicalConfig(profile{1});
                actual=csr.nwk.validateConfig(config);
                test.verifyEqual(actual.Nwk.SecurityProfile,profile{1});
                test.verifyEqual(actual.Radio.EnvelopeProfile,'bare');
                test.verifyEqual(actual.Nwk.Neighbor,reference.Neighbor);
                test.verifyEqual(actual.Nwk.Routing,reference.Routing);
                test.verifyEqual(actual.Nwk.Reassembly,reference.Reassembly);
                test.verifyTrue(actual.Nwk.Neighbor.AdmissionEnabled);
            end
        end

        function historicalProfileRejectsPairwiseRadio(test)
            for profile=historicalProfiles()
                config=historicalConfig(profile{1});
                config.Radio.EnvelopeProfile='pairwise16-size-only';
                test.verifyError(@()csr.nwk.validateConfig(config), ...
                    'csr:nwk:SecurityProfileMismatch');
            end
        end

        function implicitOrMalformedBareProfileIsRejected(test)
            invalid={'bare','hist-adb97c54-bare','hist-dd3f38e8-bare', ...
                'behavioral-historical-bare-size-only', ...
                "behavioral-hist-adb97c54-bare-size-only",42};
            for index=1:numel(invalid)
                config=historicalConfig(invalid{index});
                test.verifyError(@()csr.nwk.validateConfig(config),'csr:nwk:InvalidConfig');
                test.verifyError(@()csr.nwk.controlWireBytes('DISCOVER',struct(),1, ...
                    invalid{index}),'csr:nwk:InvalidSecurityProfile');
            end
        end

        function archivedDataAndCumulativeFeedbackHaveSourceWidths(test)
            % Source br_Network bodies are 192/592 bytes. MATLAB represents
            % application bytes separately from the seven-byte network model.
            networkBytes=[192 592]; wireBytes=[217 617];
            for profile=historicalProfiles()
                config=csr.nwk.validateConfig(historicalConfig(profile{1}));
                for index=1:numel(networkBytes)
                    app=application(networkBytes(index)-7);
                    frame=csr.hop.Frames.data(app,1,2,65535,config.Radio);
                    test.verifyEqual(frame.WirePayloadBytes,wireBytes(index));
                    test.verifyEqual(frame.Sequence,uint16(65535));
                end
                for kind={'ACK','DACK'}
                    radio=config.Radio; radio.Kind=kind{1}; radio.HasAckWindow=true;
                    ack=csr.hop.Frames.acknowledgment(2,1,65535, ...
                        bitshift(uint64(1),63),uint64(1),radio);
                    test.verifyEqual(ack.WirePayloadBytes,41);
                    test.verifyEqual(ack.AckBitmap,bitshift(uint64(1),63));
                    test.verifyEqual(ack.DackBitmap,uint64(1));
                    test.verifyEqual(ack.Kind,kind{1});
                end
                radio.HasAckWindow=false;
                exact=csr.hop.Frames.acknowledgment(2,1,1,0,0,radio);
                test.verifyEqual(exact.WirePayloadBytes,25);
                % Exact ACK is supported by the pinned ns-3 profile; archived
                % executable feedback evidence demonstrates the 41-byte form.
            end
        end

        function allControlKindsRetainSourceRecordSizes(test)
            kinds={'DISCOVER','KEY_REQUEST','KEY_UPDATE','NEIGHBOR_CHECK', ...
                'NEIGHBOR_CHECK','ROUTING','SNMP_START','SNMP_DONE'};
            payloads={struct(),struct(),struct(),struct(), ...
                struct('Subtype','no_path'),struct('Bytes',uint8(0:10)), ...
                struct(),struct('Nodes',[1 256 16777214])};
            expected=[19 18 62 16 19 27 31 31];
            for profile=historicalProfiles()
                for index=1:numel(kinds)
                    for destinations=[1 4 10]
                        bytes=csr.nwk.controlWireBytes(kinds{index}, ...
                            payloads{index},destinations,profile{1});
                        test.verifyEqual(bytes,expected(index));
                    end
                end
            end
        end

        function bareRadioDoesNotStripSecurityFromControlEnvelope(test)
            for profile=historicalProfiles()
                config=csr.nwk.validateConfig(historicalConfig(profile{1}));
                payload=struct('Bytes',uint8(1:11));
                bytes=csr.nwk.controlWireBytes('ROUTING',payload,2,profile{1});
                control=struct('Id',uint64(9),'Type','ROUTING','Payload',payload, ...
                    'WirePayloadBytes',bytes);
                frame=csr.hop.Frames.control(control,1,[2 3],[4 5],config.Radio);
                test.verifyEqual(frame.WirePayloadBytes,27);
                test.verifyEqual(frame.EnvelopeProfile,'bare');
                test.verifyEqual(frame.DestinationIds,[2 3]);
                test.verifyEqual(frame.HopSequences,uint16([4 5]));
            end
        end

        function historicalWireSelectionDoesNotAdmitAnUnverifiedPeer(test)
            for profile=historicalProfiles()
                config=csr.nwk.validateConfig(historicalConfig(profile{1}));
                scheduler=csr.sim.EventScheduler();
                layer=csr.nwk.Layer(1,scheduler,[],config,struct());
                layer.observe(2,struct('Success',true));
                test.verifyFalse(layer.acceptFromNeighbor(application(185),2));
                test.verifyEqual(layer.stats().NeighborActivations,0);
            end
        end
    end
end

function profiles = historicalProfiles()
profiles={'behavioral-hist-adb97c54-bare-size-only', ...
    'behavioral-hist-dd3f38e8-bare-size-only'};
end

function config = historicalConfig(profile)
config=csr.scenario.routedNetwork('autonomous');
config.Nwk.SecurityProfile=profile;
config.Radio.EnvelopeProfile='bare';
end

function app = application(bytes)
app=struct('Id',uint64(1),'SourceId',1,'DestinationId',2, ...
    'GeneratedSeconds',0,'ApplicationPayloadBytes',bytes,'Dscp',0);
end
