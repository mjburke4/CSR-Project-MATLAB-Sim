classdef Routes < handle
    %ROUTES Source-backed ARL candidate selection and routing record state.
    % The scheduler, discovery admission and reliable control transport are
    % owned by Layer. Route changes remain pending until drainChanges().
    properties (SetAccess = private)
        NodeId
        Capability
        Config
        Candidates
    end
    properties (Access = private)
        Peers
        PeerOrder = []
        DestinationOrder = []
        Preferred
        Reverse
        Changed = []
        InfoChanged = false
    end
    methods
        function obj = Routes(nodeId,capability,options)
            if nargin < 2, capability = 1; end
            if nargin < 3, options = struct(); end
            csr.nwk.Routes.number(nodeId,0,16777214);
            csr.nwk.Routes.number(capability,0,255);
            obj.NodeId = double(nodeId); obj.Capability = double(capability);
            obj.Config = csr.nwk.Routes.defaults();
            if ~isstruct(options) || ~isscalar(options)
                error('csr:nwk:InvalidConfig','Route options must be a scalar struct.');
            end
            names = fieldnames(options);
            for k = 1:numel(names)
                if ~isfield(obj.Config,names{k})
                    error('csr:nwk:InvalidConfig','Unknown route option: %s.',names{k});
                end
                obj.Config.(names{k}) = options.(names{k});
            end
            csr.nwk.Routes.number(obj.Config.MaxPathHops,1,32);
            obj.Config.LocalInfo = csr.nwk.Routes.validateInfo(obj.Config.LocalInfo);
            obj.Candidates = repmat(csr.nwk.Routes.emptyCandidate(),1,0);
            obj.Peers = containers.Map('KeyType','double','ValueType','any');
            obj.Preferred = containers.Map('KeyType','double','ValueType','double');
            obj.Reverse = containers.Map('KeyType','double','ValueType','any');
            if obj.Capability ~= 0, obj.Changed = obj.NodeId; end
        end

        function setCapability(obj,capability)
            csr.nwk.Routes.number(capability,0,255);
            if obj.Capability ~= capability
                obj.Capability = double(capability);
                obj.mark(obj.NodeId);
            end
        end

        function setLocalInfo(obj,info)
            info = csr.nwk.Routes.validateInfo(info);
            if ~isequal(obj.Config.LocalInfo,info)
                obj.Config.LocalInfo = info;
                obj.InfoChanged = true;
            end
        end

        function setNeighbor(obj,peer,active,linkCost,now)
            obj.checkPeer(peer,linkCost,now);
            if ~(islogical(active) || isnumeric(active)) || ~isscalar(active) || ...
                    ~isreal(active) || ~ismember(active,[0 1])
                error('csr:nwk:InvalidField','Neighbor active must be logical.');
            end
            peer = double(peer); linkCost = double(linkCost); active = logical(active);
            affected = unique([peer [obj.Candidates([obj.Candidates.NextHop] == peer).DestinationId]],'stable');
            before = obj.states(affected);
            oldActive = false; oldLinkCost = NaN;
            if isKey(obj.Peers,peer)
                entry = obj.Peers(peer); oldActive = entry.Active; oldLinkCost = entry.LinkCost;
            else
                entry = obj.emptyPeer(peer);
                obj.PeerOrder = [peer obj.PeerOrder];
            end
            entry.Active = active; entry.LinkCost = linkCost;
            if oldActive && ~active
                entry.InfoValid = false; entry.InfoSequence = 0;
                obj.Candidates(~[obj.Candidates.Immediate] & [obj.Candidates.NextHop] == peer) = [];
            end
            obj.Peers(peer) = entry;
            index = obj.findCandidate(peer,peer);
            if index == 0
                route = csr.nwk.Routes.emptyCandidate();
                route.DestinationId = peer; route.NextHop = peer;
                route.HopCount = 1; route.Path = peer; route.Immediate = true;
                obj.Candidates(end+1) = route; index = numel(obj.Candidates);
            end
            route = obj.Candidates(index);
            route.Valid = true; route.LinkCost = linkCost; route.Cost = max(1,linkCost);
            route.LastUpdatedSeconds = double(now);
            if oldActive && ~active
                route.Capability = 0; route.SequenceValid = false; route.Sequence = 0;
            end
            obj.Candidates(index) = route;
            if active, obj.noteDestination(peer); end
            % Admission recomputes direct destination only. A measured link
            % change on an already-active peer revisits its valid routes.
            if active && oldActive && oldLinkCost ~= linkCost
                for k = 1:numel(obj.Candidates)
                    route = obj.Candidates(k);
                    if route.NextHop == peer && route.Valid
                        route.LinkCost = linkCost;
                        route.Cost = obj.totalCost(linkCost,route.AdvertisedCost);
                        obj.Candidates(k) = route;
                        position = find(affected == route.DestinationId,1);
                        if ~isempty(before{position}), obj.release(route.DestinationId); end
                    end
                end
            end
            if active, obj.release(peer); end
            for k = 1:numel(affected)
                if oldActive && ~active && ~isempty(before{k}) && before{k}.NextHop == peer
                    obj.release(affected(k));
                end
                obj.finish(affected(k),before{k},false);
            end
        end

        function invalidateNeighbor(obj,peer,now)
            % Explicit failure is stronger than an observation that a peer
            % has not yet been admitted: discard its pre-admission routes too.
            obj.checkPeer(peer,1,now); peer = double(peer);
            if ~isKey(obj.Peers,peer), return; end
            entry = obj.Peers(peer);
            affected = unique([peer [obj.Candidates([obj.Candidates.NextHop] == peer).DestinationId]],'stable');
            before = obj.states(affected);
            obj.setNeighbor(peer,false,entry.LinkCost,now);
            obj.Candidates(~[obj.Candidates.Immediate] & [obj.Candidates.NextHop] == peer) = [];
            index = obj.findCandidate(peer,peer);
            if index ~= 0
                obj.Candidates(index).Capability = 0;
                obj.Candidates(index).SequenceValid = false;
                obj.Candidates(index).Sequence = 0;
            end
            entry = obj.Peers(peer); entry.InfoValid = false; entry.InfoSequence = 0;
            obj.Peers(peer) = entry;
            for k = 1:numel(affected)
                if ~isempty(before{k}) && before{k}.NextHop == peer, obj.release(affected(k)); end
                obj.finish(affected(k),before{k},false);
            end
        end

        function effects = apply(obj,peer,sequence,records,linkCost,now)
            obj.checkPeer(peer,linkCost,now);
            csr.nwk.Routes.number(sequence,0,4294967295);
            peer = double(peer); sequence = double(sequence);
            effects = struct('RequestSnapshot',false,'AppliedRecords',0, ...
                'IgnoredRecords',0,'InfoChanged',false);
            if ~iscell(records), records = num2cell(records); end
            sawInfo = false; sawFlush = false; sawReporterSelfRecord = false;
            if ~isKey(obj.Peers,peer)
                obj.setNeighbor(peer,false,linkCost,now);
            end
            for k = 1:numel(records)
                record = records{k}; accepted = false;
                if ~isstruct(record) || ~isscalar(record) || ~isfield(record,'Operation')
                    error('csr:nwk:InvalidRecord','Every route record requires Operation.');
                end
                switch upper(char(record.Operation))
                    case 'REQUEST'
                        effects.RequestSnapshot = true; accepted = true;
                    case 'INFO'
                        sawInfo = true;
                        info = csr.nwk.Routes.validateInfo(record.Info);
                        entry = obj.Peers(peer);
                        if obj.newer(entry.InfoValid,entry.InfoSequence,sequence)
                            entry.InfoValid = true; entry.InfoSequence = sequence; entry.Info = info;
                            obj.Peers(peer) = entry; accepted = true; effects.InfoChanged = true;
                        end
                    case 'UPDATE'
                        accepted = obj.update(peer,sequence,record,linkCost,now);
                        if all(isfield(record,{'NodeId','HopCount','Cost','Path'})) && ...
                                record.NodeId == peer && record.HopCount == 0 && ...
                                record.Cost == 0 && isempty(record.Path)
                            sawReporterSelfRecord = true;
                        end
                    case 'DELETE'
                        csr.nwk.Routes.number(record.NodeId,0,16777215);
                        if record.NodeId < 16777215 && record.NodeId ~= obj.NodeId
                            if record.NodeId == peer
                                accepted = obj.selfUpdate(peer,sequence,0,linkCost,now);
                                sawReporterSelfRecord = true;
                            else
                                accepted = obj.delete(peer,sequence,double(record.NodeId),now);
                            end
                        end
                    case 'FLUSH'
                        sawFlush = true;
                        accepted = obj.flush(peer,sequence,now);
                    otherwise
                        error('csr:nwk:InvalidRecord','Unknown route operation.');
                end
                effects.AppliedRecords = effects.AppliedRecords + double(accepted);
                effects.IgnoredRecords = effects.IgnoredRecords + double(~accepted);
            end
            if sawInfo && sawFlush && ~sawReporterSelfRecord
                obj.selfUpdate(peer,sequence,0,linkCost,now);
            end
        end

        function route = select(obj,destination)
            csr.nwk.Routes.number(destination,0,16777214);
            obj.noteDestination(double(destination));
            route = obj.best(double(destination));
        end

        function route = relay(obj,destination)
            route = obj.select(destination);
            if ~isempty(route) && route.Capability ~= 0
                route.UsedReverse = false; return
            end
            if isKey(obj.Reverse,double(destination))
                reverse = obj.Reverse(double(destination));
                if obj.usable(reverse.NextHop)
                    route = reverse; route.UsedReverse = true; return
                end
            end
            if ~isempty(route), route.UsedReverse = false; end
        end

        function route = discoveryRelay(obj,destination)
            % Legacy SNMP prefers a capable forward route, otherwise a
            % usable reverse route, then a direct/non-capable forward route.
            route = obj.select(destination);
            if ~isempty(route) && route.Capability ~= 0
                route.UsedReverse = false; return
            end
            if obj.Capability ~= 0 && isKey(obj.Reverse,double(destination))
                reverse = obj.Reverse(double(destination));
                if obj.usable(reverse.NextHop)
                    route = reverse; route.UsedReverse = true; return
                end
            end
            if ~isempty(route), route.UsedReverse = false; end
        end

        function learnReverse(obj,source,peer,now)
            obj.checkPeer(peer,1,now);
            csr.nwk.Routes.number(source,0,16777214);
            if source == obj.NodeId, return; end
            obj.noteDestination(double(peer));
            if ~isKey(obj.Peers,double(peer)), return; end
            obj.noteDestination(double(source));
            route = csr.nwk.Routes.emptyCandidate();
            route.DestinationId = double(source); route.NextHop = double(peer);
            route.Path = double(peer); route.HopCount = 1; route.Valid = true;
            route.LastUpdatedSeconds = double(now);
            obj.Reverse(double(source)) = route;
        end

        function removed = noteNoPath(obj,peer,destination,now)
            % CHECK_NO_PATH is informational for all forward candidates. It
            % clears a reverse path only when its reporting hop matches.
            if nargin < 4, now = 0; end
            obj.checkPeer(peer,1,now);
            csr.nwk.Routes.number(destination,0,16777215);
            destination = double(destination); peer = double(peer); removed = false;
            if destination == 16777215, return; end
            obj.noteDestination(destination);
            if ~isKey(obj.Reverse,destination), return; end
            reverse = obj.Reverse(destination);
            if reverse.NextHop ~= peer, return; end
            remove(obj.Reverse,destination); removed = true;
        end

        function [records,destinations,infoChanged] = drainChanges(obj)
            destinations = obj.DestinationOrder(ismember(obj.DestinationOrder,obj.Changed));
            if ismember(obj.NodeId,obj.Changed), destinations(end+1) = obj.NodeId; end
            records = {};
            infoChanged = obj.InfoChanged;
            if obj.InfoChanged
                records{end+1} = struct('Operation','INFO','Info',obj.Config.LocalInfo);
            end
            for destination = destinations
                records{end+1} = obj.changeRecord(destination); %#ok<AGROW>
            end
            obj.Changed = []; obj.InfoChanged = false;
        end

        function restoreChanges(obj,destinations,infoChanged)
            % A bounded outbound backlog may reject semantic admission after
            % drainChanges. Restore dirty flags so convergence is delayed,
            % never silently lost. No callback can interleave this operation.
            for destination=reshape(double(destinations),1,[])
                if ~ismember(destination,obj.Changed)
                    obj.Changed(end+1)=destination;
                end
            end
            obj.InfoChanged=obj.InfoChanged || logical(infoChanged);
        end

        function destinations = pendingChanges(obj)
            % Read-only flags used by independently scheduled snapshot replies.
            destinations = obj.Changed;
        end

        function records = snapshot(obj,excludeDestinations)
            if nargin < 2, excludeDestinations = []; end
            records = {struct('Operation','INFO','Info',obj.Config.LocalInfo)};
            if obj.Capability ~= 0 && ~ismember(obj.NodeId,excludeDestinations)
                records{end+1} = obj.changeRecord(obj.NodeId);
            end
            % Snapshot follows candidate insertion order; incremental changes
            % use the newest-created destination order in drainChanges().
            for k = 1:numel(obj.Candidates)
                candidate = obj.Candidates(k);
                destination = candidate.DestinationId;
                if ismember(destination,excludeDestinations), continue; end
                route = obj.best(destination);
                if ~isempty(route) && route.Capability ~= 0 && candidate.NextHop == route.NextHop
                    records{end+1} = obj.changeRecord(destination); %#ok<AGROW>
                end
            end
            records{end+1} = struct('Operation','FLUSH');
        end

        function entries = neighbors(obj)
            entries = repmat(obj.emptyPeer(0),1,0);
            for peer = obj.PeerOrder, entries(end+1) = obj.Peers(peer); end %#ok<AGROW>
        end

        function info = neighborInfo(obj,peer)
            info = [];
            if isKey(obj.Peers,double(peer))
                entry = obj.Peers(double(peer));
                if entry.InfoValid, info = entry.Info; end
            end
        end

        function gateway = applicationGateway(obj)
            gateway = []; scanned = [];
            for k = 1:numel(obj.Candidates)
                destination = obj.Candidates(k).DestinationId;
                if ismember(destination,scanned), continue; end
                scanned(end+1) = destination; %#ok<AGROW>
                route = obj.best(destination);
                if ~isempty(route) && route.Capability == 2, gateway = destination; end
            end
        end

        function destinations = applicationDestinationCandidates(obj)
            % Source GetApplicationDestinationCandidates scans every stored
            % route, including unselected/invalid entries, in insertion order.
            % Neighbor fallback belongs to Layer, which owns persistent peers.
            % This observation must not run selection or alter preferences.
            destinations=unique([obj.Candidates.DestinationId],'stable');
            destinations=destinations(destinations~=obj.NodeId);
        end

        function destinations = reachableDestinations(obj)
            destinations = [];
            for destination = obj.DestinationOrder
                if ~isempty(obj.discoveryRelay(destination))
                    destinations(end+1) = destination; %#ok<AGROW>
                end
            end
        end
    end
    methods (Access = private)
        function accepted = update(obj,peer,sequence,record,linkCost,now)
            required = {'NodeId','Capability','HopCount','Cost','Path'};
            if ~all(isfield(record,required))
                error('csr:nwk:InvalidRecord','UPDATE fields are missing.');
            end
            csr.nwk.Routes.number(record.NodeId,0,16777215);
            csr.nwk.Routes.number(record.Capability,0,255);
            csr.nwk.Routes.number(record.HopCount,0,65535);
            csr.nwk.Routes.number(record.Cost,0,4294967295);
            path = record.Path;
            if ~isnumeric(path) || (~isempty(path) && ~isvector(path)) || ~isreal(path) || ...
                    any(~isfinite(path(:))) || any(path(:)<0 | path(:)>16777215 | fix(path(:))~=path(:)) || ...
                    numel(path) ~= record.HopCount
                error('csr:nwk:InvalidRecord','UPDATE Path must contain HopCount node identifiers.');
            end
            accepted = false;
            destination = double(record.NodeId); path = reshape(double(path),1,[]);
            if destination == obj.NodeId || destination == 16777215, return; end
            if destination == peer
                if record.HopCount ~= 0 || record.Cost ~= 0 || ~isempty(path), return; end
                accepted = obj.selfUpdate(peer,sequence,double(record.Capability),linkCost,now);
                return
            end
            if record.HopCount >= obj.Config.MaxPathHops || any(path == 16777215), return; end
            index = obj.findCandidate(destination,peer);
            if index ~= 0 && ~obj.newer(obj.Candidates(index).SequenceValid,obj.Candidates(index).Sequence,sequence)
                return
            end
            obj.noteDestination(destination); before = obj.best(destination);
            replacingSelected = ~isempty(before) && before.NextHop == peer;
            if index == 0
                route = csr.nwk.Routes.emptyCandidate();
                route.DestinationId = destination; route.NextHop = peer;
                obj.Candidates(end+1) = route; index = numel(obj.Candidates);
            end
            route = obj.Candidates(index);
            route.Capability = double(record.Capability);
            route.HopCount = double(record.HopCount)+1;
            route.LinkCost = double(linkCost); route.AdvertisedCost = double(record.Cost);
            route.Cost = obj.totalCost(linkCost,record.Cost);
            route.Valid = ~ismember(obj.NodeId,path);
            route.SelectionDeferred = ~obj.usable(peer);
            route.Path = [peer path];
            route.SequenceValid = true; route.Sequence = sequence;
            route.LastUpdatedSeconds = double(now);
            obj.Candidates(index) = route;
            obj.release(destination);
            obj.finish(destination,before,replacingSelected && route.Valid);
            accepted = true;
        end

        function accepted = selfUpdate(obj,peer,sequence,capability,linkCost,now)
            index = obj.findCandidate(peer,peer); accepted = false;
            if index == 0, return; end
            route = obj.Candidates(index);
            if ~obj.newer(route.SequenceValid,route.Sequence,sequence), return; end
            obj.noteDestination(peer); before = obj.best(peer);
            route.Capability = capability; route.HopCount = 1; route.Path = peer;
            route.Valid = true; route.SelectionDeferred = false;
            route.LinkCost = double(linkCost); route.AdvertisedCost = 0;
            route.Cost = max(1,double(linkCost)); route.LastUpdatedSeconds = double(now);
            route.SequenceValid = true; route.Sequence = sequence;
            obj.Candidates(index) = route;
            obj.finish(peer,before,false); accepted = true;
        end

        function accepted = delete(obj,peer,sequence,destination,now)
            obj.noteDestination(destination); before = obj.best(destination);
            index = obj.findCandidate(destination,peer); accepted = false;
            if index == 0
                route = csr.nwk.Routes.emptyCandidate();
                route.DestinationId = destination; route.NextHop = peer;
                obj.Candidates(end+1) = route; index = numel(obj.Candidates);
            else
                route = obj.Candidates(index);
                if ~obj.newer(route.SequenceValid,route.Sequence,sequence), return; end
            end
            invalidated = route.Valid;
            route.Valid = false; route.SequenceValid = true; route.Sequence = sequence;
            route.LastUpdatedSeconds = double(now); obj.Candidates(index) = route;
            if invalidated && ~isempty(before) && before.NextHop == peer
                obj.release(destination);
            end
            obj.finish(destination,before,false); accepted = true;
        end

        function accepted = flush(obj,peer,sequence,now)
            affected = []; before = {};
            for k = 1:numel(obj.Candidates)
                route = obj.Candidates(k);
                if route.Immediate || route.NextHop ~= peer || ...
                        ~obj.newer(route.SequenceValid,route.Sequence,sequence), continue; end
                if ~ismember(route.DestinationId,affected)
                    affected(end+1) = route.DestinationId; %#ok<AGROW>
                    before{end+1} = obj.best(route.DestinationId); %#ok<AGROW>
                end
                route.Valid = false; route.SequenceValid = true; route.Sequence = sequence;
                route.LastUpdatedSeconds = double(now); obj.Candidates(k) = route;
            end
            entry = obj.Peers(peer);
            if obj.newer(entry.InfoValid,entry.InfoSequence,sequence)
                entry.InfoValid = false; entry.InfoSequence = sequence; obj.Peers(peer) = entry;
            end
            for k = 1:numel(affected)
                if ~isempty(before{k}) && before{k}.NextHop == peer, obj.release(affected(k)); end
                obj.finish(affected(k),before{k},false);
            end
            accepted = true;
        end

        function route = best(obj,destination)
            route = [];
            preferred = -1;
            if isKey(obj.Preferred,destination), preferred = obj.Preferred(destination); end
            for k = 1:numel(obj.Candidates)
                candidate = obj.Candidates(k);
                if candidate.DestinationId ~= destination || ~candidate.Valid || ...
                        candidate.SelectionDeferred || ~obj.usable(candidate.NextHop), continue; end
                if isempty(route) || candidate.Cost < route.Cost || ...
                        (candidate.Cost == route.Cost && candidate.HopCount < route.HopCount) || ...
                        (candidate.Cost == route.Cost && candidate.HopCount == route.HopCount && ...
                        candidate.NextHop == preferred && route.NextHop ~= preferred)
                    route = candidate;
                end
            end
        end

        function release(obj,destination)
            for k = 1:numel(obj.Candidates)
                if obj.Candidates(k).DestinationId == destination && obj.usable(obj.Candidates(k).NextHop)
                    obj.Candidates(k).SelectionDeferred = false;
                end
            end
        end

        function finish(obj,destination,before,force)
            after = obj.best(destination);
            if force || ~obj.sameSelection(before,after), obj.mark(destination); end
        end

        function mark(obj,destination)
            route = obj.best(destination);
            if isempty(route)
                if isKey(obj.Preferred,destination), remove(obj.Preferred,destination); end
            else
                obj.Preferred(destination) = route.NextHop;
            end
            if ~ismember(destination,obj.Changed), obj.Changed(end+1) = destination; end
        end

        function record = changeRecord(obj,destination)
            route = obj.best(destination);
            if destination == obj.NodeId && obj.Capability ~= 0
                record = struct('Operation','UPDATE','NodeId',obj.NodeId, ...
                    'Capability',obj.Capability,'HopCount',0,'Cost',0,'Path',[]);
            elseif destination ~= obj.NodeId && ~isempty(route) && route.Capability ~= 0
                record = struct('Operation','UPDATE','NodeId',destination, ...
                    'Capability',route.Capability,'HopCount',route.HopCount, ...
                    'Cost',route.Cost,'Path',route.Path);
            else
                record = struct('Operation','DELETE','NodeId',destination);
            end
        end

        function noteDestination(obj,destination)
            if destination ~= obj.NodeId && ~ismember(destination,obj.DestinationOrder)
                obj.DestinationOrder = [destination obj.DestinationOrder];
            end
        end

        function states = states(obj,destinations)
            states = cell(1,numel(destinations));
            for k = 1:numel(destinations), states{k} = obj.best(destinations(k)); end
        end

        function index = findCandidate(obj,destination,peer)
            index = find([obj.Candidates.DestinationId] == destination & ...
                [obj.Candidates.NextHop] == peer,1);
            if isempty(index), index = 0; end
        end

        function value = usable(obj,peer)
            value = false;
            if isKey(obj.Peers,peer), entry = obj.Peers(peer); value = entry.Active; end
        end

        function checkPeer(obj,peer,linkCost,now)
            csr.nwk.Routes.number(peer,0,16777214);
            csr.nwk.Routes.number(linkCost,0,4294967295);
            validateattributes(now,{'numeric'},{'scalar','real','finite','nonnegative'});
            if peer == obj.NodeId, error('csr:nwk:InvalidField','A neighbor cannot be the local node.'); end
        end
    end
    methods (Static)
        function config = defaults()
            info = struct('MinSpeedKbps',8,'MaxSpeedKbps',128, ...
                'MinPowerDbmX10',0,'MaxPowerDbmX10',300, ...
                'LinkMarginDbX10',100,'LowPowerDbmX10',140, ...
                'TempLowCx10',0,'TempHighCx10',0);
            config = struct('MaxPathHops',32,'LocalInfo',info);
        end
    end
    methods (Static, Access = private)
        function route = emptyCandidate()
            route = struct('DestinationId',0,'NextHop',0,'Capability',0, ...
                'HopCount',0,'Cost',0,'Path',[],'Immediate',false,'Valid',false, ...
                'SelectionDeferred',false,'LinkCost',0,'AdvertisedCost',0, ...
                'SequenceValid',false,'Sequence',0,'LastUpdatedSeconds',0);
        end

        function entry = emptyPeer(peer)
            entry = struct('PeerId',peer,'Active',false,'LinkCost',1, ...
                'InfoValid',false,'InfoSequence',0,'Info',struct());
        end

        function value = newer(valid,current,incoming)
            % Match CompareRoutingSequence(current,incoming)<0, including
            % rejecting an exactly half-range ambiguous sequence advance.
            value = ~valid || mod(double(current)-double(incoming),4294967296) > 2147483648;
        end

        function cost = totalCost(linkCost,advertisedCost)
            % Preserve the source uint32 addition rather than MATLAB's
            % saturating integer arithmetic.
            cost = max(1,mod(double(linkCost)+double(advertisedCost),4294967296));
        end

        function equal = sameSelection(first,second)
            if isempty(first) || isempty(second), equal = isempty(first) && isempty(second); return; end
            fields = {'NextHop','Cost','HopCount','Immediate','Capability','Path'};
            equal = true;
            for k = 1:numel(fields)
                if ~isequal(first.(fields{k}),second.(fields{k})), equal = false; return; end
            end
        end

        function number(value,minimum,maximum)
            if ~isnumeric(value) || ~isscalar(value) || ~isreal(value) || ~isfinite(value) || ...
                    value < minimum || value > maximum || fix(value) ~= value
                error('csr:nwk:InvalidField','Invalid unsigned routing field.');
            end
        end

        function info = validateInfo(info)
            names = {'MinSpeedKbps','MaxSpeedKbps','MinPowerDbmX10','MaxPowerDbmX10', ...
                'LinkMarginDbX10','LowPowerDbmX10','TempLowCx10','TempHighCx10'};
            if ~isstruct(info) || ~isscalar(info) || numel(fieldnames(info)) ~= numel(names) || ...
                    ~all(isfield(info,names))
                error('csr:nwk:InvalidRecord','INFO requires all eight operating-limit fields.');
            end
            for k = 1:numel(names)
                if k <= 2, minimum = 0; maximum = 65535;
                else, minimum = -32768; maximum = 32767; end
                csr.nwk.Routes.number(info.(names{k}),minimum,maximum);
                info.(names{k}) = double(info.(names{k}));
            end
        end
    end
end
