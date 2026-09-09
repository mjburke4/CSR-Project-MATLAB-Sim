classdef TestControlWireProfile < matlab.unittest.TestCase
    % Atomic Tranche 3 profile sizes and fail-closed configuration boundary.
    methods (Test)
        function singleTargetControlSizesAreExplicit(test)
            profile='behavioral-production-pairwise16-size-only';
            test.verifyEqual(csr.nwk.controlWireBytes('DISCOVER',struct(),1,profile),19);
            test.verifyEqual(csr.nwk.controlWireBytes('KEY_REQUEST',struct(),1,profile),18);
            test.verifyEqual(csr.nwk.controlWireBytes('KEY_UPDATE',struct(),1,profile),62);
            test.verifyEqual(csr.nwk.controlWireBytes('NEIGHBOR_CHECK',struct(),1,profile),16);
            noPath=struct('Subtype','no_path');
            test.verifyEqual(csr.nwk.controlWireBytes('NEIGHBOR_CHECK',noPath,1,profile),19);
            routing=struct('Bytes',uint8(0:10));
            test.verifyEqual(csr.nwk.controlWireBytes('ROUTING',routing,1,profile),27);
            test.verifyEqual(csr.nwk.controlWireBytes('SNMP_START',struct(),1,profile),31);
            snmp=struct('Nodes',[1 256 16777214]);
            test.verifyEqual(csr.nwk.controlWireBytes('SNMP_DONE',snmp,1,profile),31);
        end
        function compatibilityDestinationListsAddNoModeledWireBytes(test)
            profile='behavioral-production-pairwise16-size-only';
            routing=struct('Bytes',uint8(zeros(1,700)));
            for count=[1 4 10]
                test.verifyEqual(csr.nwk.controlWireBytes('ROUTING',routing,count,profile),716);
            end
        end
        function snmpCompatibilityNodeListRetainsFixedEnvelope(test)
            for count=[0 1 10]
                payload=struct('Nodes',0:count-1,'SourceId',1,'DestinationId',2);
                test.verifyEqual(csr.nwk.controlWireBytes('SNMP_DONE',payload),31);
            end
        end
        function hopCopiesCompleteControlEnvelopeWithoutDoubleCounting(test)
            profile='behavioral-production-pairwise16-size-only';
            payload=struct('Bytes',uint8(1:11));
            bytes=csr.nwk.controlWireBytes('ROUTING',payload,2,profile);
            control=struct('Id',uint64(9),'Type','ROUTING','Payload',payload, ...
                'WirePayloadBytes',bytes);
            radio=struct('RateKeyKbps',8,'Preamble','long', ...
                'EnvelopeProfile','pairwise16-size-only','AckRequired',true);
            frame=csr.hop.Frames.control(control,1,[2 3],[4 5],radio);
            test.verifyEqual(frame.WirePayloadBytes,bytes);
            test.verifyEqual(frame.EnvelopeProfile,'pairwise16-size-only');
            test.verifyEqual(frame.Dscp,7);
        end
        function dataAndAckPairwiseEnvelopeAddsFiveBytes(test)
            app=struct('Id',uint64(1),'SourceId',1,'DestinationId',2, ...
                'GeneratedSeconds',0,'ApplicationPayloadBytes',64,'Dscp',0);
            bare=csr.hop.Frames.data(app,1,2,1,struct('EnvelopeProfile','bare'));
            pairwise=csr.hop.Frames.data(app,1,2,1, ...
                struct('EnvelopeProfile','pairwise16-size-only'));
            test.verifyEqual(pairwise.WirePayloadBytes-bare.WirePayloadBytes,5);
            bareAck=csr.hop.Frames.acknowledgment(2,1,1,0,0, ...
                struct('EnvelopeProfile','bare','HasAckWindow',false));
            pairwiseAck=csr.hop.Frames.acknowledgment(2,1,1,0,0, ...
                struct('EnvelopeProfile','pairwise16-size-only','HasAckWindow',false));
            test.verifyEqual(pairwiseAck.WirePayloadBytes-bareAck.WirePayloadBytes,5);
        end
        function unsupportedProfilesAndMalformedInputsFailClosed(test)
            test.verifyError(@()csr.nwk.controlWireBytes('DISCOVER',struct(),1,'bare'), ...
                'csr:nwk:InvalidSecurityProfile');
            test.verifyError(@()csr.nwk.controlWireBytes('DISCOVER',struct(),1, ...
                "behavioral-production-pairwise16-size-only"), ...
                'csr:nwk:InvalidSecurityProfile');
            invalidCounts={0,11,1.5,NaN,[1 2]};
            for k=1:numel(invalidCounts)
                verifyCountRejected(test,invalidCounts{k});
            end
            test.verifyError(@()csr.nwk.controlWireBytes('ROUTING',struct()), ...
                'csr:nwk:InvalidControl');
            test.verifyError(@()csr.nwk.controlWireBytes('ROUTING', ...
                struct('Bytes',ones(2))), 'csr:nwk:InvalidControl');
            test.verifyError(@()csr.nwk.controlWireBytes('SNMP_DONE', ...
                struct('Nodes',0:10)), 'csr:nwk:InvalidControl');
            test.verifyError(@()csr.nwk.controlWireBytes('SNMP_DONE', ...
                struct('Nodes',16777215)), 'csr:nwk:InvalidControl');
            test.verifyError(@()csr.nwk.controlWireBytes('UNKNOWN',struct()), ...
                'csr:nwk:InvalidControl');
        end
    end
end

function verifyCountRejected(test,count)
rejected=false;
try
    csr.nwk.controlWireBytes('DISCOVER',struct(),count);
catch exception
    rejected=startsWith(exception.identifier,'MATLAB:');
    test.verifyTrue(rejected, ...
        sprintf('Unexpected destination-count exception: %s',exception.identifier));
end
test.verifyTrue(rejected,'Invalid destination count was accepted.');
end
