classdef MacStream < handle
    properties (Access=private)
        Owner
        Node
        Original
        Context = struct()
    end
    methods
        function obj=MacStream(owner,node,original)
            obj.Owner=owner; obj.Node=node; obj.Original=original;
        end
        function setContext(obj,details)
            obj.Context=details;
        end
        function value=randi(obj,bounds,varargin)
            assert(isempty(varargin),'autocase:VectorDraw','Only source scalar randi requests are supported.');
            if numel(bounds)==1, low=1; high=double(bounds); else, low=double(bounds(1)); high=double(bounds(2)); end
            details=obj.Context; details.low=low; details.high=high;
            if strcmp(obj.Owner.Mode,'natural')
                % Exactly one unmodified source randi call, same stream/bounds.
                value=randi(obj.Original,bounds);
                obj.Owner.observe(obj.Node,'mac_slot',value,details);
            else
                value=obj.Owner.take(obj.Node,'mac_slot',details);
                assert(value>=low && value<=high && value==floor(value), ...
                    'autocase:IntegerDraw','Native integer is outside the request range.');
            end
        end
    end
end
