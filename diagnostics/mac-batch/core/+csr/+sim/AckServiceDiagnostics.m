classdef AckServiceDiagnostics < csr.sim.LinkDiagnostics
    %ACKSERVICEDIAGNOSTICS Passive ordered callbacks around early ACK service.
    % Inherits the complete T8 feedback admission/transmission correlation.
    % The table copies callback arguments and six read-only MAC scalars at
    % cancellation boundaries. It never creates peer state, draws randomness,
    % schedules work or edits a frame. Its window limits the service trace,
    % not the inherited feedback trace.
    properties (SetAccess = private)
        WindowSeconds
    end
    properties (Access = private)
        ServiceRows
        ServiceCount = 0
        OmittedServiceRecords = 0
        OutOfWindowServiceEvents = 0
        CancellationBeforeCount = 0
        CancellationAfterCount = 0
        CancellationPairErrors = 0
        PendingCancellation = []
    end
    methods
        function obj = AckServiceDiagnostics(maxRecords,windowSeconds)
            if nargin<1, maxRecords = 100000; end
            if nargin<2, windowSeconds = [300 320]; end
            obj@csr.sim.LinkDiagnostics(maxRecords);
            validateattributes(windowSeconds,{'numeric'}, ...
                {'vector','numel',2,'real','finite','nonnegative'});
            if windowSeconds(2)<windowSeconds(1)
                error('csr:diagnostics:ServiceWindow', ...
                    'The service window must have start <= end.');
            end
            obj.WindowSeconds = reshape(double(windowSeconds),1,2);
            obj.ServiceRows = repmat(serviceTemplate(),obj.MaxRecords,1);
        end

        function observeService(obj,time,nodeId,event,frame,details)
            % Called at the existing protocolEvent boundary, once per callback.
            if ~obj.inWindow(time), return; end
            row = serviceTemplate();
            row.TimeSeconds = time; row.Stage = 'protocol_callback';
            row.Event = char(event); row.NodeId = double(nodeId);
            row.Layer = callbackLayer(row.Event);
            row = frameIdentity(row,frame,nodeId,event);
            row.PeerId = numericOr(details,'PeerId',numericOr(details,'Peer',row.PeerId));
            row = copyDetails(row,details);
            row.DetailsJSON = jsonencode(details);
            obj.append(row);
        end

        function observeAdmission(obj,admission)
            % recordAdmission already has the generator's completed decision.
            if ~obj.inWindow(admission.TimeSeconds), return; end
            row = serviceTemplate();
            row.TimeSeconds = admission.TimeSeconds;
            row.Stage = 'application_attempt'; row.Layer = 'APP';
            row.Event = 'application_attempt';
            row.NodeId = double(admission.SourceId);
            row.PeerId = double(admission.DestinationId);
            row.FrameKind = 'APP';
            row.ApplicationSourceId = double(admission.SourceId);
            row.ApplicationDestinationId = double(admission.DestinationId);
            row.PacketId = admission.PacketId;
            row.PacketIdAvailable = logical(admission.Accepted) && admission.PacketId~=0;
            row = copyDetails(row,admission);
            row.DetailsJSON = jsonencode(admission);
            obj.append(row);
        end

        function observeCancellation(obj,time,nodeId,event,peer,sequence,controlType,removed,state)
            % The NetworkSimulation wrapper reads the six public MAC scalars
            % only within the window; the protocol callback itself is called
            % exactly once between these paired observations.
            if ~obj.inWindow(time), return; end
            names={'mac_cancel_before','mac_cancel_after', ...
                'mac_control_cancel_before','mac_control_cancel_after'};
            if ~any(strcmp(event,names))
                error('csr:diagnostics:CancellationEvent','Unsupported cancellation observation.');
            end
            row=serviceTemplate(); row.TimeSeconds=time; row.NodeId=double(nodeId);
            row.Stage='cancellation_callback'; row.Layer='MAC'; row.Event=char(event);
            row.PeerId=double(peer); row.Sequence=double(sequence);
            row.ControlType=char(controlType);
            details=state; details.PeerId=double(peer); details.Sequence=double(sequence);
            details.ControlType=char(controlType); details.RemovedCount=double(removed);
            row=copyDetails(row,details); row.DetailsJSON=jsonencode(details);
            identity=struct('TimeSeconds',time,'NodeId',double(nodeId),'PeerId',double(peer), ...
                'Sequence',double(sequence),'ControlType',char(controlType), ...
                'AfterEvent',strrep(char(event),'_before','_after'));
            if endsWith(event,'_before')
                obj.CancellationBeforeCount=obj.CancellationBeforeCount+1;
                if ~isempty(obj.PendingCancellation)
                    obj.CancellationPairErrors=obj.CancellationPairErrors+1;
                end
                obj.PendingCancellation=identity;
            else
                obj.CancellationAfterCount=obj.CancellationAfterCount+1;
                if ~isequaln(identity,obj.PendingCancellation)
                    obj.CancellationPairErrors=obj.CancellationPairErrors+1;
                end
                obj.PendingCancellation=[];
            end
            obj.append(row);
        end

        function observed = snapshot(obj)
            observed = snapshot@csr.sim.LinkDiagnostics(obj);
            retained = min(obj.ServiceCount,obj.MaxRecords);
            cancellationComplete=obj.CancellationPairErrors==0 && isempty(obj.PendingCancellation) && ...
                obj.CancellationBeforeCount==obj.CancellationAfterCount;
            complete = observed.LinkDiagnostics.Complete && obj.OmittedServiceRecords==0 && cancellationComplete;
            cancellationCount=obj.CancellationBeforeCount+obj.CancellationAfterCount;
            summary = struct('SchemaVersion','csr-matlab-ack-service-diagnostics-v1', ...
                'Enabled',true,'MaxRecords',obj.MaxRecords, ...
                'WindowStartSeconds',obj.WindowSeconds(1), ...
                'WindowEndSeconds',obj.WindowSeconds(2),'WindowBoundary','start_inclusive_end_exclusive', ...
                'ServiceEventCount',obj.ServiceCount,'CapturedServiceRecords',retained, ...
                'OmittedServiceRecords',obj.OmittedServiceRecords, ...
                'OutOfWindowServiceEvents',obj.OutOfWindowServiceEvents, ...
                'CancellationSnapshotCount',cancellationCount, ...
                'CancellationBeforeCount',obj.CancellationBeforeCount, ...
                'CancellationAfterCount',obj.CancellationAfterCount, ...
                'CancellationPairErrors',obj.CancellationPairErrors, ...
                'PendingCancellationPair',~isempty(obj.PendingCancellation), ...
                'CancellationPairsComplete',cancellationComplete, ...
                'Complete',complete,'InheritedFeedbackComplete',observed.LinkDiagnostics.Complete, ...
                'StageMeaning','Existing protocol callbacks, completed application admissions and paired cancellation callback observations', ...
                'ObservationOrder','ObservationId is callback arrival order among all in-window service rows', ...
                'DetailsMeaning','DetailsJSON preserves callback details, the complete admission row, or the cancellation scalar snapshot and selector', ...
                'StateMeaning','State is the opaque string supplied by a MAC event or read at a cancellation callback boundary', ...
                'CapacityMeaning','HOP capacity fields copy existing admission snapshots; no additional HOP/NWK reads or intermediate release stages', ...
                'CancellationMeaning','Before/after rows surround one original MAC cancellation callback; peer/sequence/control type are selectors, not a fabricated packet identity', ...
                'MissingNumericValues','NaN denotes unavailable; boolean details are 0 or 1 when supplied', ...
                'IdentityMeaning','PacketId and AggregateId are local uint64 identities with availability flags; no cross-simulator identity equivalence', ...
                'AggregateIdentityLimit','MAC callbacks precede or retain a separate copy from simulation transmission ID assignment; their aggregate ID is unavailable', ...
                'FeedbackWindowMeaning','Only ServiceTrace is windowed; inherited T8 feedback traces cover the entire run', ...
                'Passive',true,'ScheduledEvents',0,'RandomDraws',0,'AdditionalStateReads',6*cancellationCount, ...
                'AdditionalStateReadsMeaning','Six public MAC scalar reads per cancellation snapshot; no HOP/NWK peer or state getters');
            observed.ServiceTrace = struct2table(obj.ServiceRows(1:retained),'AsArray',true);
            observed.ServiceDiagnostics = summary;
        end

        function assertComplete(obj)
            assertComplete@csr.sim.LinkDiagnostics(obj);
            if obj.OmittedServiceRecords~=0
                error('csr:diagnostics:IncompleteService', ...
                    'ACK service evidence incomplete: %g omitted in-window records.', ...
                    obj.OmittedServiceRecords);
            end
            if obj.CancellationPairErrors~=0 || ~isempty(obj.PendingCancellation) || ...
                    obj.CancellationBeforeCount~=obj.CancellationAfterCount
                error('csr:diagnostics:IncompleteCancellation', ...
                    'Cancellation observations are unmatched or incomplete.');
            end
        end
    end
    methods (Access = private)
        function inside = inWindow(obj,time)
            inside = time>=obj.WindowSeconds(1) && time<obj.WindowSeconds(2);
            if ~inside, obj.OutOfWindowServiceEvents = obj.OutOfWindowServiceEvents+1; end
        end

        function append(obj,row)
            obj.ServiceCount = obj.ServiceCount+1;
            if obj.ServiceCount>obj.MaxRecords
                obj.OmittedServiceRecords = obj.OmittedServiceRecords+1;
                return
            end
            row.ObservationId = uint64(obj.ServiceCount);
            obj.ServiceRows(obj.ServiceCount) = row;
        end
    end
end

function row = serviceTemplate()
row = struct('ObservationId',uint64(0),'TimeSeconds',0,'Stage','','Layer','', ...
    'Event','','NodeId',NaN,'PeerId',NaN,'FrameKind','', ...
    'PacketId',uint64(0),'PacketIdAvailable',false, ...
    'AggregateId',uint64(0),'AggregateIdAvailable',false, ...
    'FrameSourceId',NaN,'FrameDestinationId',NaN, ...
    'ApplicationSourceId',NaN,'ApplicationDestinationId',NaN, ...
    'Sequence',NaN,'FrameDestinationsJSON','[]','HopSequencesJSON','[]', ...
    'ControlType','','FeedbackIdentityAvailable',false,'HasAckWindow',NaN, ...
    'AckBitmap',uint64(0),'DackBitmap',uint64(0), ...
    'State','','Reason','','PreparationActive',NaN,'RemovedCount',NaN, ...
    'ReservationSlot',NaN,'ReservationCounter',NaN, ...
    'QueueDepth',NaN,'DataDepth',NaN,'AckDepth',NaN, ...
    'PendingData',NaN,'PendingThreshold',NaN,'GlobalSpare',NaN, ...
    'NeighborOutstanding',NaN,'NeighborThreshold',NaN,'NeighborSpare',NaN, ...
    'GlobalAllowed',NaN,'NeighborAllowed',NaN, ...
    'NsdpBefore',NaN,'NsdpAfter',NaN,'NsdpCount',NaN,'NsdpLimit',NaN, ...
    'NwkQueueSize',NaN,'ResendCount',NaN,'AckWaitSeconds',NaN, ...
    'DurationSeconds',NaN,'HoldSeconds',NaN,'SegmentCount',NaN, ...
    'FirstReception',NaN,'LocalDelivery',NaN,'IsDack',NaN,'CapacityReleased',NaN, ...
    'FlowIndex',NaN,'AttemptIndex',NaN,'Accepted',NaN,'DetailsJSON','{}');
end

function row = frameIdentity(row,frame,nodeId,event)
row.FrameKind = textOr(frame,'Kind','');
row.FrameSourceId = numericOr(frame,'SourceId',NaN);
row.FrameDestinationId = numericOr(frame,'DestinationId',NaN);
row.Sequence = numericOr(frame,'Sequence',NaN);
row.PeerId = row.FrameDestinationId;
incoming = contains(event,'receive') || any(strcmp(event,{'hop_no_route','hop_custody_refused'}));
if incoming, row.PeerId = row.FrameSourceId; end
if isfield(frame,'DestinationIds')
    row.FrameDestinationsJSON = jsonencode(frame.DestinationIds);
    if incoming && isfield(frame,'HopSequences')
        target = find(double(frame.DestinationIds)==double(nodeId),1);
        if ~isempty(target), row.Sequence = double(frame.HopSequences(target)); end
    end
elseif isfield(frame,'DestinationId') && isnumeric(frame.DestinationId) && numel(frame.DestinationId)>1
    row.FrameDestinationsJSON = jsonencode(frame.DestinationId);
end
if isfield(frame,'HopSequences'), row.HopSequencesJSON = jsonencode(frame.HopSequences); end
if strcmp(row.FrameKind,'AGGREGATE')
    % The MAC callback retains a member ID. NetworkSimulation.transmit
    % assigns an OTA aggregate ID to a separate MATLAB value copy. A shared
    % time and NodeId can locate the inherited actual-feedback observations;
    % the callback's copied Id must never be mislabeled as that aggregate ID.
    return
end
if any(strcmp(row.FrameKind,{'ACK','DACK'}))
    row.FeedbackIdentityAvailable = true;
    row.HasAckWindow = numericOr(frame,'HasAckWindow',NaN);
    row.AckBitmap = frame.AckBitmap; row.DackBitmap = frame.DackBitmap;
    return
end
packet = frame;
if isfield(frame,'App') && isstruct(frame.App), packet = frame.App; end
if isfield(frame,'Control') && isstruct(frame.Control)
    packet = frame.Control; row.FrameKind = 'CONTROL';
end
row.ControlType = textOr(packet,'Type','');
if isfield(packet,'Id') && ~isempty(packet.Id)
    row.PacketId = uint64(packet.Id); row.PacketIdAvailable = true;
end
if isfield(packet,'ApplicationPayloadBytes')
    row.ApplicationSourceId = numericOr(packet,'SourceId',NaN);
    row.ApplicationDestinationId = numericOr(packet,'DestinationId',NaN);
    if isempty(row.FrameKind), row.FrameKind = 'APP'; end
elseif ~isempty(row.ControlType)
    row.FrameKind = 'CONTROL';
end
end

function row = copyDetails(row,details)
names = {'PreparationActive','RemovedCount','ReservationSlot','ReservationCounter','QueueDepth','DataDepth','AckDepth', ...
    'PendingData','PendingThreshold','GlobalSpare','NeighborOutstanding', ...
    'NeighborThreshold','NeighborSpare','GlobalAllowed','NeighborAllowed', ...
    'NsdpBefore','NsdpAfter','NsdpCount','NsdpLimit','NwkQueueSize', ...
    'ResendCount','AckWaitSeconds','DurationSeconds','HoldSeconds','FirstReception', ...
    'LocalDelivery','IsDack','CapacityReleased','FlowIndex','AttemptIndex','Accepted'};
for index = 1:numel(names)
    name = names{index}; row.(name) = numericOr(details,name,row.(name));
end
row.SegmentCount = numericOr(details,'Segments',NaN);
row.State = textOr(details,'State',''); row.Reason = textOr(details,'Reason','');
end

function layer = callbackLayer(event)
if startsWith(event,'mac_'), layer = 'MAC';
elseif startsWith(event,'hop_'), layer = 'HOP';
else, layer = 'NWK'; end
end

function value = numericOr(item,name,fallback)
value = fallback;
if isstruct(item) && isscalar(item) && isfield(item,name)
    candidate = item.(name);
    if (isnumeric(candidate) || islogical(candidate)) && isscalar(candidate)
        value = double(candidate);
    end
end
end

function value = textOr(item,name,fallback)
value = fallback;
if isstruct(item) && isscalar(item) && isfield(item,name) && ~isempty(item.(name))
    value = char(item.(name));
end
end
