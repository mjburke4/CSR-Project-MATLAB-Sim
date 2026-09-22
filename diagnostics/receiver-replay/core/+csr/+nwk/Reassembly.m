classdef Reassembly < handle
    %REASSEMBLY Bounded, atomic per-peer ARL section reassembly.
    % Conflicting sections never overwrite accepted bytes. Caller owns route
    % sequence freshness after completion and peer expiry via discardPeer.
    properties (Access = private)
        Messages
        Order = {}
        Config
        Counters
    end
    methods
        function obj = Reassembly(config)
            if nargin < 1, config = struct(); end
            obj.Config = struct('MaxMessages',64,'MaxMessagesPerPeer',8);
            if ~isstruct(config) || ~isscalar(config)
                error('csr:nwk:InvalidReassemblyConfig','Reassembly config must be a scalar struct.');
            end
            names = fieldnames(config);
            for index = 1:numel(names)
                name = names{index};
                if ~isfield(obj.Config,name)
                    error('csr:nwk:InvalidReassemblyConfig','Unknown reassembly setting.');
                end
                value = config.(name);
                if ~isnumeric(value) || ~isscalar(value) || ~isreal(value) || ...
                        ~isfinite(value) || value < 1 || fix(value) ~= value
                    error('csr:nwk:InvalidReassemblyConfig','Reassembly bounds must be positive integers.');
                end
                obj.Config.(name) = double(value);
            end
            obj.Messages = containers.Map('KeyType','char','ValueType','any');
            obj.Counters = struct('AcceptedSections',0,'Duplicates',0,'Conflicts',0, ...
                'Malformed',0,'Completed',0,'Evicted',0,'Discarded',0);
        end

        function [complete,records,sequence] = accept(obj,peer,sectionBytes)
            validateattributes(peer,{'numeric'},{'scalar','real','finite','integer','>=',0,'<=',16777214});
            complete = false; records = {}; sequence = NaN;
            try
                section = csr.nwk.RoutingCodec.decodeSection(sectionBytes);
            catch exception
                if ~strcmp(exception.identifier,'csr:nwk:MalformedRouting'), rethrow(exception); end
                obj.Counters.Malformed = obj.Counters.Malformed+1; return
            end
            sequence = section.Sequence;
            key = sprintf('%.0f:%.0f',double(peer),sequence);
            if ~isKey(obj.Messages,key)
                obj.makeRoom(double(peer));
                message = struct('Peer',double(peer),'TotalSections',section.TotalSections, ...
                    'Bodies',{cell(1,section.TotalSections)}, ...
                    'Received',false(1,section.TotalSections));
                obj.Messages(key) = message; obj.Order{end+1} = key;
            else
                message = obj.Messages(key);
            end
            if message.TotalSections ~= section.TotalSections
                obj.Counters.Conflicts = obj.Counters.Conflicts+1; return
            end
            index = section.Section+1;
            if message.Received(index)
                if isequal(message.Bodies{index},section.Body)
                    obj.Counters.Duplicates = obj.Counters.Duplicates+1;
                else
                    obj.Counters.Conflicts = obj.Counters.Conflicts+1;
                end
                return
            end
            message.Bodies{index} = section.Body; message.Received(index) = true;
            obj.Messages(key) = message;
            obj.Counters.AcceptedSections = obj.Counters.AcceptedSections+1;
            if ~all(message.Received), return; end
            obj.remove(key);
            try
                records = csr.nwk.RoutingCodec.decodeRecords([message.Bodies{:}]);
            catch exception
                if ~strcmp(exception.identifier,'csr:nwk:MalformedRouting'), rethrow(exception); end
                obj.Counters.Malformed = obj.Counters.Malformed+1; return
            end
            complete = true; obj.Counters.Completed = obj.Counters.Completed+1;
        end

        function discardPeer(obj,peer)
            keys = obj.Order;
            for index = 1:numel(keys)
                message = obj.Messages(keys{index});
                if message.Peer == double(peer)
                    obj.remove(keys{index}); obj.Counters.Discarded = obj.Counters.Discarded+1;
                end
            end
        end

        function output = stats(obj)
            output = obj.Counters;
            output.PendingMessages = double(obj.Messages.Count); output.BufferedBytes = 0;
            for index = 1:numel(obj.Order)
                message = obj.Messages(obj.Order{index});
                output.BufferedBytes = output.BufferedBytes+sum(cellfun(@numel,message.Bodies));
            end
        end
    end
    methods (Access = private)
        function makeRoom(obj,peer)
            peers = zeros(1,numel(obj.Order));
            for index = 1:numel(obj.Order)
                message = obj.Messages(obj.Order{index}); peers(index) = message.Peer;
            end
            if sum(peers == peer) >= obj.Config.MaxMessagesPerPeer
                oldest = find(peers == peer,1,'first');
                obj.remove(obj.Order{oldest}); obj.Counters.Evicted = obj.Counters.Evicted+1;
            end
            if obj.Messages.Count >= obj.Config.MaxMessages
                obj.remove(obj.Order{1}); obj.Counters.Evicted = obj.Counters.Evicted+1;
            end
        end
        function remove(obj,key)
            remove(obj.Messages,key); obj.Order(strcmp(obj.Order,key)) = [];
        end
    end
end
