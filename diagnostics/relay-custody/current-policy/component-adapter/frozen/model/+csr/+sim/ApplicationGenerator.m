classdef ApplicationGenerator < handle
    %APPLICATIONGENERATOR Source-runner application admission, separate from NWK.
    % The opt-in historical runner schedules interrupts whether or not they
    % create packets. A suppressed interrupt has no packet ID or sent statistic.
    % The gateway is cached per flow after the first successful capability
    % scan, including when the following NSDP gate suppresses that interrupt.
    properties (SetAccess = private)
        Statistics
        Gated
        AdmittedLimit
    end
    methods
        function obj = ApplicationGenerator(flowIndex,flow,gated,admittedLimit)
            obj.Gated = gated; obj.AdmittedLimit = admittedLimit;
            mode = 'fixed';
            if isfield(flow,'DestinationMode'), mode = flow.DestinationMode; end
            obj.Statistics = struct('FlowIndex',flowIndex,'SourceId',flow.SourceId, ...
                'ConfiguredDestinationId',flow.DestinationId,'DestinationMode',mode, ...
                'Attempts',0,'Admitted',0,'BlockedDiscovery',0,'BlockedTopology',0, ...
                'BlockedGatewayRoute',0,'BlockedDestination',0,'BlockedNsdp',0, ...
                'FirstAdmittedSeconds',NaN,'LastAdmittedSeconds',NaN, ...
                'GatewayCached',false,'GatewayNodeId',NaN);
        end

        function allowed = canAttempt(obj)
            allowed = obj.AdmittedLimit == 0 || obj.Statistics.Admitted < obj.AdmittedLimit;
        end

        function [accepted,destination,row] = attempt(obj,now,observe,draw)
            % observe(destination) is a read-only NWK state snapshot. draw()
            % supplies a uniform [0,1) value only for a dynamic destination.
            if ~obj.canAttempt()
                error('csr:sim:ApplicationLimit','The admitted application cap has been reached.');
            end
            s = obj.Statistics; s.Attempts = s.Attempts+1;
            destination = s.ConfiguredDestinationId;
            if s.GatewayCached, destination = s.GatewayNodeId; end
            observedDestination = destination;
            state = struct('DiscoveryActive',false,'TopologyKnown',false, ...
                'GatewayId',[],'DestinationCandidates',[], ...
                'NsdpCount',0,'NwkQueueSize',0);
            if obj.Gated, state = observe(destination); end
            accepted = true; reason = 'admitted';
            routeCheck = false; routeAvailable = false;
            if obj.Gated && state.DiscoveryActive
                accepted = false; reason = 'discovery_active';
                s.BlockedDiscovery = s.BlockedDiscovery+1;
            elseif obj.Gated && ~state.TopologyKnown
                accepted = false; reason = 'topology_unknown';
                s.BlockedTopology = s.BlockedTopology+1;
            end
            if accepted && strcmp(s.DestinationMode,'random_route_or_neighbor')
                candidates = state.DestinationCandidates;
                if isempty(candidates)
                    accepted = false; reason = 'destination_unavailable';
                    s.BlockedDestination = s.BlockedDestination+1;
                else
                    value = draw();
                    validateattributes(value,{'numeric'},{'scalar','real','finite','>=',0,'<',1});
                    destination = candidates(floor(value*numel(candidates))+1);
                end
            elseif accepted && obj.Gated && ~s.GatewayCached
                routeCheck = true; routeAvailable = ~isempty(state.GatewayId);
                if routeAvailable
                    destination = state.GatewayId;
                    s.GatewayCached = true; s.GatewayNodeId = destination;
                else
                    accepted = false; reason = 'gateway_route_unknown';
                    s.BlockedGatewayRoute = s.BlockedGatewayRoute+1;
                end
            end
            if obj.Gated && destination ~= observedDestination
                % A dynamic choice or first gateway scan can change the
                % source/destination NSDP key. Read the selected key before
                % testing source br_app's strict count < 16 admission gate.
                selectedState = observe(destination);
                state.NsdpCount = selectedState.NsdpCount;
                state.NwkQueueSize = selectedState.NwkQueueSize;
            end
            if accepted && obj.Gated && state.NsdpCount >= 16
                accepted = false; reason = 'nsdp_full';
                s.BlockedNsdp = s.BlockedNsdp+1;
            end
            if accepted
                s.Admitted = s.Admitted+1;
                if isnan(s.FirstAdmittedSeconds), s.FirstAdmittedSeconds = now; end
                s.LastAdmittedSeconds = now;
            end
            obj.Statistics = s;
            row = csr.sim.ApplicationGenerator.emptyTrace();
            row.TimeSeconds = now; row.FlowIndex = s.FlowIndex;
            row.AttemptIndex = s.Attempts; row.SourceId = s.SourceId;
            row.ConfiguredDestinationId = s.ConfiguredDestinationId;
            row.DestinationId = destination; row.Accepted = accepted; row.Reason = reason;
            row.DiscoveryActive = state.DiscoveryActive; row.TopologyKnown = state.TopologyKnown;
            row.GatewayCached = s.GatewayCached; row.GatewayNodeId = s.GatewayNodeId;
            row.RouteCheckPerformed = routeCheck; row.RouteAvailable = routeAvailable;
            row.NsdpCount = state.NsdpCount; row.NwkQueueSize = state.NwkQueueSize;
        end
    end
    methods (Static)
        function row = emptyTrace()
            row = struct('TimeSeconds',0,'FlowIndex',0,'AttemptIndex',0,'SourceId',0, ...
                'ConfiguredDestinationId',0,'DestinationId',0,'PacketId',uint64(0), ...
                'Accepted',false,'Reason','','DiscoveryActive',false,'TopologyKnown',false, ...
                'GatewayCached',false,'GatewayNodeId',NaN,'RouteCheckPerformed',false, ...
                'RouteAvailable',false,'NsdpCount',0,'NsdpLimit',16,'NwkQueueSize',0);
        end
    end
end
