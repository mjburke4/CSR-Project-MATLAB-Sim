classdef ControlledChannel < handle
    %CONTROLLEDCHANNEL Geometric delay plus an explicit controlled-loss gate.
    %   This is a Tranche 0 integration/test channel, not the CSR ns-3 PHY.
    %   It does not implement path loss, TX/RX power, receiver acquisition,
    %   BER tables, ECC/FEC, interference, collisions, or carrier sensing.
    %   Every otherwise scheduled receiver is eligible regardless of range.
    %   FixedDropProbability is independent of rate, size, and distance.

    properties (SetAccess = private)
        PropagationSpeedMps = 299792458
        FixedDropProbability = 0
    end

    methods
        function obj = ControlledChannel(config)
            if nargin == 0
                config = struct();
            end
            validateattributes(config, {'struct'}, {'scalar'}, ...
                mfilename, 'config');
            allowed = {'PropagationSpeedMps', 'FixedDropProbability'};
            unknown = setdiff(fieldnames(config), allowed);
            if ~isempty(unknown)
                error('csr:phy:UnknownChannelOption', ...
                    'Unknown controlled-channel option: %s.', unknown{1});
            end
            if isfield(config, 'PropagationSpeedMps')
                validateattributes(config.PropagationSpeedMps, {'numeric'}, ...
                    {'real', 'finite', 'scalar', 'positive'}, ...
                    mfilename, 'PropagationSpeedMps');
                obj.PropagationSpeedMps = double(config.PropagationSpeedMps);
            end
            if isfield(config, 'FixedDropProbability')
                validateattributes(config.FixedDropProbability, {'numeric'}, ...
                    {'real', 'finite', 'scalar', '>=', 0, '<=', 1}, ...
                    mfilename, 'FixedDropProbability');
                obj.FixedDropProbability = double(config.FixedDropProbability);
            end
        end

        function result = evaluate(obj, txPosition, rxPosition, stream)
            %EVALUATE Evaluate one scheduled receiver using a dedicated RNG.
            %   Positions are matching 2-D or 3-D vectors, in metres.
            %   Intermediate loss probabilities require an explicit
            %   RandStream; no global random stream is used or modified.
            %   Probability 0 or 1 consumes no random numbers.
            validateattributes(txPosition, {'numeric'}, ...
                {'real', 'finite', 'vector'}, mfilename, 'txPosition');
            validateattributes(rxPosition, {'numeric'}, ...
                {'real', 'finite', 'vector'}, mfilename, 'rxPosition');
            if ~ismember(numel(txPosition), [2 3]) || ...
                    numel(txPosition) ~= numel(rxPosition)
                error('csr:phy:InvalidPosition', ...
                    'TX and RX positions must be matching 2-D or 3-D vectors.');
            end
            distance = norm(double(txPosition(:)) - double(rxPosition(:)));
            probability = obj.FixedDropProbability;
            if probability == 0
                success = true;
            elseif probability == 1
                success = false;
            else
                if nargin < 4 || ~isa(stream, 'RandStream') || ~isscalar(stream)
                    error('csr:phy:MissingRandomStream', ...
                        'Controlled stochastic loss requires an explicit scalar RandStream.');
                end
                success = rand(stream) >= probability;
            end
            reason = 'success';
            if ~success
                reason = 'controlled_drop';
            end
            result = struct('DelaySeconds', distance / obj.PropagationSpeedMps, ...
                'Success', success, 'Reason', reason, 'DistanceMeters', distance);
        end
    end
end
