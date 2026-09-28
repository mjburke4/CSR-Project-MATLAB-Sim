classdef DiscoveryReplayAllocator
    %DISCOVERYREPLAYALLOCATOR Validation-only named-draw version of source
    % csr.phy.Model.allocateErrors. All interval arithmetic and BER methods
    % remain delegated to the production model; only sampling is routed to
    % the captured, named header/payload uniforms.
    methods (Static)
        function result=allocateErrors(rxProfile,front,signalStartSec, ...
                preambleBits,packetBits,rateKbps,intervals,sampler,node,txId,ordinal)
            rx=csr.phy.RadioProfile.validate(rxProfile);
            result=struct('HeaderBits',0,'PayloadBits',0, ...
                'HeaderErrors',0,'PayloadErrors',0,'TotalErrors',0, ...
                'ActualBer',0,'HeaderBer',0,'PayloadBer',0, ...
                'MinimumSnrDb',Inf,'PeakNoisePowerWatts',0, ...
                'PacketErrorProbability',0);
            headerDefinition=csr.phy.rateDefinition(8);
            payloadDefinition=csr.phy.rateDefinition(rateKbps);
            headerRate=headerDefinition.BitsPerSecond;
            payloadRate=payloadDefinition.BitsPerSecond;
            headerStart=signalStartSec+double(preambleBits)/headerRate;
            payloadStart=signalStartSec+(double(preambleBits)+48)/headerRate;
            packetEnd=payloadStart+max(0,double(packetBits)-double(preambleBits)-48)/payloadRate;
            if isempty(intervals), result.MinimumSnrDb=-Inf; return; end
            [~,order]=sortrows([[intervals.StartSec].',(1:numel(intervals)).'],[1 2]);
            noErrorProbability=1;
            for index=order.'
                current=intervals(index);
                intervalEnd=min(current.EndSec,packetEnd);
                if intervalEnd<current.StartSec || current.StartSec>=packetEnd, continue; end
                values=csr.phy.Model.ber(rx,front,rateKbps,current);
                result.HeaderBer=values.HeaderBer;
                result.PayloadBer=values.PayloadBer;
                result.MinimumSnrDb=min(result.MinimumSnrDb,values.SnrDb);
                result.PeakNoisePowerWatts=max(result.PeakNoisePowerWatts,current.NoisePowerWatts);
                if intervalEnd<headerStart
                    result.ActualBer=values.HeaderBer; continue;
                end
                headerBegin=max(current.StartSec,headerStart);
                headerEnd=min(intervalEnd,payloadStart);
                headerCount=floor(max(0,headerEnd-headerBegin)*headerRate);
                payloadBegin=max(current.StartSec,payloadStart);
                payloadCount=floor(max(0,intervalEnd-payloadBegin)*payloadRate);
                headerErrors=draw(headerCount,values.HeaderBer,"header_uniform");
                payloadErrors=draw(payloadCount,values.PayloadBer,"payload_uniform");
                result.HeaderBits=result.HeaderBits+headerCount;
                result.PayloadBits=result.PayloadBits+payloadCount;
                result.HeaderErrors=result.HeaderErrors+headerErrors;
                result.PayloadErrors=result.PayloadErrors+payloadErrors;
                result.TotalErrors=result.TotalErrors+headerErrors+payloadErrors;
                noErrorProbability=noErrorProbability* ...
                    (1-values.HeaderBer)^headerCount*(1-values.PayloadBer)^payloadCount;
                tested=headerCount+payloadCount;
                if tested>0
                    result.ActualBer=(headerErrors+payloadErrors)/tested;
                elseif intervalEnd<payloadStart
                    result.ActualBer=values.HeaderBer;
                else
                    result.ActualBer=values.PayloadBer;
                end
            end
            if ~isfinite(result.MinimumSnrDb), result.MinimumSnrDb=-Inf; end
            result.PacketErrorProbability=min(1,max(0,1-noErrorProbability));

            function errors=draw(bits,probability,purpose)
                if bits==0 || probability<=0, errors=0;
                elseif probability>=1, errors=bits;
                else
                    u=sampler.uniform(node,txId,ordinal,purpose);
                    errors=csr.phy.Model.sampleSourceBinomial(bits,probability,u);
                end
            end
        end
    end
end
