classdef RandomStreams < handle
    %RANDOMSTREAMS Reproducible per-node/per-subsystem MATLAB RNG ownership.
    %   get(nodeId, subsystem) returns the same cached RandStream handle on
    %   every call. rand(stream, ...) leaves MATLAB's global RNG untouched.
    %   Stream creation order does not affect the stream assigned to a key.
    %
    %   Source-independent engineering seed mapping (version 2):
    %     keyCode = 4 * nodeId + subsystemIndex
    %     streamSeed = mod(seed + 2654435761 * keyCode, 2^32)
    %   subsystemIndex is traffic=0, phy=1, mac=2, nwk=3; these codes are
    %   unchanged from version 1. The new sync stream uses keyCode=2^26+1+
    %   nodeId, retaining all old seeds and keeping the zero-remap code free.
    %   SYNC-threshold normals are separate from PHY error draws, as in ns-3.
    %   Node IDs are
    %   unsigned 24-bit values. Exact uint64 arithmetic avoids floating-point
    %   rounding; the odd multiplier makes the mapping injective over the
    %   supported key domain for each master seed. A zero result is replaced
    %   by the same formula at reserved keyCode=2^26 (outside the node domain)
    %   because MATLAB's mt19937ar seed 0 aliases its default seed 5489. The
    %   reserved code preserves uniqueness and yields a nonzero replacement.
    %   A runtime ownership check also prevents silent collisions if this
    %   mapping is changed later.
    %
    %   These are independently owned mt19937ar streams, not a guarantee of
    %   mathematical independence or ns-3 stream equivalence. Numeric seed
    %   equality across simulators does not imply packet-level equality.

    properties (SetAccess = private)
        Seed
        MappingVersion = 2
    end

    properties (Access = private)
        Streams
        SeedOwners
    end

    methods
        function obj = RandomStreams(seed)
            if nargin == 0
                seed = 1;
            end
            validateattributes(seed, {'numeric'}, ...
                {'scalar', 'real', 'finite', 'integer', 'nonnegative', ...
                '<=', double(intmax('uint32'))}, mfilename, 'seed');
            obj.Seed = uint32(seed);
            obj.Streams = containers.Map('KeyType', 'char', 'ValueType', 'any');
            obj.SeedOwners = containers.Map('KeyType', 'uint32', ...
                'ValueType', 'char');
        end

        function stream = get(obj, nodeId, subsystem)
            validateattributes(nodeId, {'numeric'}, ...
                {'scalar', 'real', 'finite', 'integer', 'nonnegative', ...
                '<=', 16777215}, mfilename, 'nodeId');
            if isstring(subsystem) && isscalar(subsystem)
                subsystem = char(subsystem);
            end
            names = {'traffic', 'phy', 'mac', 'nwk', 'sync'};
            if ~ischar(subsystem) || ~isrow(subsystem)
                error('csr:sim:UnknownSubsystem', ...
                    'subsystem must be traffic, phy, mac, nwk, or sync.');
            end
            index = find(strcmp(subsystem, names), 1);
            if isempty(index)
                error('csr:sim:UnknownSubsystem', ...
                    'Unknown subsystem "%s"; use traffic, phy, mac, nwk, or sync.', ...
                    subsystem);
            end
            key = sprintf('%u:%s', uint32(nodeId), subsystem);
            if isKey(obj.Streams, key)
                stream = obj.Streams(key);
                return
            end

            keyCode = uint64(nodeId) * uint64(4) + uint64(index - 1);
            if strcmp(subsystem,'sync')
                keyCode = uint64(67108865) + uint64(nodeId);
            end
            mixed = uint64(obj.Seed) + uint64(2654435761) * keyCode;
            streamSeed = uint32(mod(mixed, uint64(4294967296)));
            if streamSeed == 0
                reserved = uint64(obj.Seed) + ...
                    uint64(2654435761) * uint64(67108864);
                streamSeed = uint32(mod(reserved, uint64(4294967296)));
            end
            if isKey(obj.SeedOwners, streamSeed)
                error('csr:sim:RandomSeedCollision', ...
                    'Stream keys "%s" and "%s" map to the same seed.', ...
                    obj.SeedOwners(streamSeed), key);
            end
            stream = RandStream('mt19937ar', 'Seed', double(streamSeed));
            obj.Streams(key) = stream;
            obj.SeedOwners(streamSeed) = key;
        end
    end
end
