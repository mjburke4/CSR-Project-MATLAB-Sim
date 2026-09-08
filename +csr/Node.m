classdef Node < handle
    %NODE CSR address and transport counters, independent of toolbox node IDs.
    properties (SetAccess = private)
        Id
        PositionMeters
    end
    properties
        TxAvailableSeconds = 0
        Generated = 0
        Transmitted = 0
        Received = 0
        Dropped = 0
    end
    methods
        function obj = Node(config)
            obj.Id = config.Id;
            obj.PositionMeters = config.PositionMeters;
        end
    end
end
