classdef PhySampler < handle
    properties (Access=private)
        Owner
        Node
        Original
        Context
    end
    methods
        function obj=PhySampler(owner,node,original,context)
            obj.Owner=owner; obj.Node=node; obj.Original=original; obj.Context=context;
        end
        function errors=draw(obj,bits,probability,component,beginSec,endSec)
            % Preserve production no-draw cases and source binomial formula.
            details=obj.Context; details.bits=bits; details.probability=probability;
            details.component=component; details.component_start_ns=round(beginSec*1e9);
            details.component_end_ns=round(endSec*1e9);
            if bits==0 || probability<=0, errors=0; return; end
            if probability>=1, errors=bits; return; end
            if strcmp(obj.Owner.Mode,'natural')
                uniform=rand(obj.Original);
                obj.Owner.observe(obj.Node,'phy_binomial',uniform,details);
            else
                uniform=obj.Owner.take(obj.Node,'phy_binomial',details);
            end
            errors=csr.phy.Model.sampleSourceBinomial(bits,probability,uniform);
        end
    end
end
