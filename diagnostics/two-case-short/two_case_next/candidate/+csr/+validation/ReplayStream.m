classdef ReplayStream < handle
    %REPLAYSTREAM Test-only scalar randi dispatch for an explicit MAC tape.
    % This object is deliberately not a RandStream and cannot supply any
    % traffic, PHY, NWK or normal/uniform floating random variates.
    properties (SetAccess = private)
        NodeId
    end
    properties (Access = private)
        Owner
    end
    methods
        function obj = ReplayStream(owner,nodeId)
            if ~isa(owner,'csr.validation.ReplayStreams')
                error('csr:validation:ReplayOwner','A ReplayStreams owner is required.');
            end
            obj.Owner = owner; obj.NodeId = double(nodeId);
        end
        function value = randi(obj,bounds,varargin)
            % Only a scalar output is meaningful at the production seam.
            shape = [1 1];
            if numel(varargin) == 1
                shape = varargin{1};
                if isnumeric(shape) && isscalar(shape), shape = [shape shape]; end
            elseif numel(varargin) == 2
                if isnumeric(varargin{1}) && isscalar(varargin{1}) && ...
                        isnumeric(varargin{2}) && isscalar(varargin{2})
                    shape = [varargin{1} varargin{2}];
                else, shape = []; end
            elseif ~isempty(varargin), shape = []; end
            if ~isnumeric(shape) || ~isreal(shape) || ~isequal(double(shape),[1 1])
                error('csr:validation:ReplayShape','Replay randi supports a scalar output only.');
            end
            if ~isnumeric(bounds) || ~isreal(bounds) || ...
                    any(~isfinite(bounds(:))) || any(fix(bounds(:))~=bounds(:))
                error('csr:validation:ReplaySupport','Replay bounds must be finite integers.');
            end
            if isscalar(bounds), bounds = [1 double(bounds)]; end
            if ~isrow(bounds) || numel(bounds)~=2 || bounds(1)<0 || ...
                    bounds(2)>255 || bounds(1)>bounds(2)
                error('csr:validation:ReplaySupport','Replay support must be an ordered interval within 0..255.');
            end
            value = obj.Owner.draw(obj.NodeId,double(bounds(1)),double(bounds(2)));
        end
    end
end
