classdef LinkDiagnostics < handle
    %LINKDIAGNOSTICS Passive feedback admission and actual OTA observations.
    % This object never calls link control, reads a random stream, schedules an
    % event, tags a packet or changes a protocol queue. Its private queue mirror
    % correlates observed MAC admissions with repeated/replaced ACK transmissions.
    properties (SetAccess = private)
        MaxRecords
    end
    properties (Access = private)
        Attached = false
        AckTransmissions = 0
        DecisionRows
        ActualRows
        DecisionCount = 0
        ActualCount = 0
        OmittedDecisions = 0
        OmittedActual = 0
        UnmatchedActual = 0
        CorrelationErrors = 0
        Queues
    end
    methods
        function obj = LinkDiagnostics(maxRecords)
            if nargin<1, maxRecords = 100000; end
            validateattributes(maxRecords,{'numeric'}, ...
                {'scalar','real','finite','integer','nonnegative','<=',1000000});
            obj.MaxRecords = double(maxRecords);
            obj.DecisionRows = repmat(decisionTemplate(),obj.MaxRecords,1);
            obj.ActualRows = repmat(actualTemplate(),obj.MaxRecords,1);
            obj.Queues = containers.Map('KeyType','double','ValueType','any');
        end

        function attach(obj,ackTransmissions)
            % An observer belongs to exactly one simulation run.
            if obj.Attached
                error('csr:diagnostics:ObserverReuse','Use a fresh observer for each simulation.');
            end
            validateattributes(ackTransmissions,{'numeric'}, ...
                {'scalar','real','finite','integer','positive'});
            obj.AckTransmissions = double(ackTransmissions);
            obj.Attached = true;
        end

        function observeDecision(obj,time,frame,context,nodePower,powerDefaulted,accepted,event,nwkFailures)
            obj.DecisionCount = obj.DecisionCount+1;
            row = decisionTemplate();
            row.DecisionId = uint64(obj.DecisionCount); row.TimeSeconds = time;
            row = feedbackIdentity(row,frame);
            row.SelectedRateKeyKbps = frame.RateKeyKbps;
            row.SelectedRateBps = operationalRate(frame.RateKeyKbps);
            row.SelectedPowerDbm = frame.TxPowerDbm;
            row.ConfiguredNodePowerDbm = nodePower;
            row.PowerDefaulted = logical(powerDefaulted);
            row.QueueAccepted = logical(accepted);
            row.NwkFailureCount = nwkFailures;
            if isstruct(context) && isscalar(context) && ...
                    isfield(context,'Frame') && isfield(context,'Decision')
                incoming = context.Frame;
                row.InputContextAvailable = any(strcmp(incoming.Kind,{'DATA','CONTROL'}));
                if row.InputContextAvailable
                    row.InputFrameKind = incoming.Kind;
                    row.InputAggregateId = context.AggregateId;
                    row.InputSequence = double(incoming.Sequence);
                    if strcmp(incoming.Kind,'DATA')
                        row.InputPacketId = incoming.App.Id;
                    else
                        row.InputPacketId = incoming.Control.Id;
                        row.InputControlType = incoming.Control.Type;
                        target = find(double(incoming.DestinationIds)==context.NodeId,1);
                        if ~isempty(target), row.InputSequence = double(incoming.HopSequences(target)); end
                    end
                    row.InputRateKeyKbps = incoming.RateKeyKbps;
                    row.InputRateBps = operationalRate(incoming.RateKeyKbps);
                    row.InputPowerDbm = scalarOr(incoming,'TxPowerDbm',NaN);
                    row.InputReceivedPowerDbm = scalarOr(context.Decision,'ReceivedPowerDbm',NaN);
                    row.PathlossDb = scalarOr(context.Decision,'PathlossDb',NaN);
                end
            end
            queue = obj.queue(frame.SourceId);
            entry = struct('DecisionId',row.DecisionId,'Frame',frame,'Count',0);
            if accepted && strcmp(event,'mac_enqueue')
                row.QueueDisposition = 'enqueued';
                row.RetainedDecisionId = row.DecisionId;
                queue{end+1} = entry;
            elseif accepted && strcmp(event,'mac_ack_replace')
                row.QueueDisposition = 'replaced';
                target = firstPeer(queue,frame.DestinationId);
                if isempty(target)
                    obj.CorrelationErrors = obj.CorrelationErrors+1;
                else
                    queue{target} = entry;
                    row.RetainedDecisionId = row.DecisionId;
                end
            elseif accepted && isempty(event)
                row.QueueDisposition = 'duplicate_retained';
                target = firstSequence(queue,frame.DestinationId,frame.Sequence);
                if isempty(target) || frame.HasAckWindow
                    obj.CorrelationErrors = obj.CorrelationErrors+1;
                else
                    row.RetainedDecisionId = queue{target}.DecisionId;
                end
            elseif ~accepted && strcmp(event,'mac_queue_drop')
                row.QueueDisposition = 'rejected';
            else
                row.QueueDisposition = 'unresolved';
                obj.CorrelationErrors = obj.CorrelationErrors+1;
            end
            obj.Queues(double(frame.SourceId)) = queue;
            if obj.DecisionCount>obj.MaxRecords
                obj.OmittedDecisions = obj.OmittedDecisions+1;
            else
                obj.DecisionRows(obj.DecisionCount) = row;
            end
        end

        function observeTransmission(obj,time,aggregate)
            members = {aggregate};
            if isfield(aggregate,'Segments') && ~isempty(aggregate.Segments)
                members = aggregate.Segments;
            end
            queue = obj.queue(aggregate.SourceId);
            % MAC chooses a prefix of its ACK queue before DATA members. Keep
            % every original queue index until all members have been observed.
            used = false(1,numel(queue));
            for index = 1:numel(members)
                frame = members{index};
                if ~any(strcmp(frame.Kind,{'ACK','DACK'})), continue; end
                obj.ActualCount = obj.ActualCount+1;
                row = actualTemplate();
                row.ObservationId = uint64(obj.ActualCount); row.TimeSeconds = time;
                row = feedbackIdentity(row,frame);
                row.AggregateId = aggregate.Id;
                row.SegmentIndex = index; row.SegmentCount = numel(members);
                row.RateKeyKbps = aggregate.RateKeyKbps;
                row.RateBps = operationalRate(aggregate.RateKeyKbps);
                row.TxPowerDbm = aggregate.TxPowerDbm;
                row.Preamble = aggregate.Preamble;
                target = [];
                for candidate = 1:numel(queue)
                    if ~used(candidate) && sameFeedback(queue{candidate}.Frame,frame)
                        target = candidate; break
                    end
                end
                if isempty(target)
                    obj.UnmatchedActual = obj.UnmatchedActual+1;
                else
                    used(target) = true;
                    entry = queue{target}; entry.Count = entry.Count+1;
                    queue{target} = entry;
                    row.DecisionId = entry.DecisionId; row.DecisionMatched = true;
                    row.SelectedRateKeyKbps = entry.Frame.RateKeyKbps;
                    row.SelectedRateBps = operationalRate(entry.Frame.RateKeyKbps);
                    row.SelectedPowerDbm = entry.Frame.TxPowerDbm;
                end
                if obj.ActualCount>obj.MaxRecords
                    obj.OmittedActual = obj.OmittedActual+1;
                else
                    obj.ActualRows(obj.ActualCount) = row;
                end
            end
            keep = true(1,numel(queue));
            for index = 1:numel(queue)
                keep(index) = queue{index}.Count<obj.AckTransmissions;
            end
            obj.Queues(double(aggregate.SourceId)) = queue(keep);
        end

        function observed = snapshot(obj)
            queued = 0;
            ids = keys(obj.Queues);
            for index = 1:numel(ids), queued = queued+numel(obj.Queues(ids{index})); end
            summary = struct('SchemaVersion','csr-matlab-link-diagnostics-v1', ...
                'Enabled',true,'MaxRecords',obj.MaxRecords, ...
                'DecisionCount',obj.DecisionCount,'ActualFeedbackCount',obj.ActualCount, ...
                'OmittedDecisionRecords',obj.OmittedDecisions, ...
                'OmittedActualFeedbackRecords',obj.OmittedActual, ...
                'UnmatchedActualFeedbackRecords',obj.UnmatchedActual, ...
                'CorrelationErrors',obj.CorrelationErrors,'PendingFeedbackQueueEntries',queued, ...
                'Complete',obj.complete(),'AckTransmissionsPerRetainedFrame',obj.AckTransmissions, ...
                'SelectionPolicy','Incoming frame rate, with empty HOP feedback power resolved to configured node power', ...
                'LinkControlApplied',false,'PeerS0Available',false,'HopFailureCountAvailable',false, ...
                'NwkFailureCountMeaning','Read-only existing NWK peer count at feedback admission; not used by ACK selection', ...
                'MissingNumericValues','NaN denotes unavailable; never zero-filled or inferred', ...
                'InputContextMeaning','Addressed DATA or reliable control reception invoking synchronous HOP feedback', ...
                'DecisionStage','After MAC admission; enqueued, replacement, retained duplicate, or rejected', ...
                'ActualStage','One row per OTA ACK/DACK aggregate member, including retained-frame repeats', ...
                'Correlation','Private observation queue follows MAC events and ACK repeat limit; packets are unmodified', ...
                'RateMeaning','RateKeyKbps is the legacy key; RateBps is the operational four-bit interval rate', ...
                'Passive',true,'ScheduledEvents',0,'RandomDraws',0);
            observed = struct('LinkDecisionTrace', ...
                struct2table(obj.DecisionRows(1:min(obj.DecisionCount,obj.MaxRecords)),'AsArray',true), ...
                'ActualFeedbackTrace', ...
                struct2table(obj.ActualRows(1:min(obj.ActualCount,obj.MaxRecords)),'AsArray',true), ...
                'LinkDiagnostics',summary);
        end

        function assertComplete(obj)
            if ~obj.complete()
                error('csr:diagnostics:Incomplete', ...
                    ['Feedback evidence incomplete: %g omitted decisions, %g omitted OTA members, ' ...
                    '%g unmatched OTA members, %g correlation errors.'], ...
                    obj.OmittedDecisions,obj.OmittedActual,obj.UnmatchedActual,obj.CorrelationErrors);
            end
        end
    end
    methods (Access = private)
        function value = complete(obj)
            value = obj.Attached && obj.OmittedDecisions==0 && obj.OmittedActual==0 && ...
                obj.UnmatchedActual==0 && obj.CorrelationErrors==0;
        end
        function entries = queue(obj,nodeId)
            entries = {};
            if isKey(obj.Queues,double(nodeId)), entries = obj.Queues(double(nodeId)); end
        end
    end
end

function row = decisionTemplate()
row = struct('DecisionId',uint64(0),'TimeSeconds',0,'Stage','feedback_mac_admission', ...
    'NodeId',0,'PeerId',0,'FrameKind','','Sequence',0,'HasAckWindow',false, ...
    'AckBitmap',uint64(0),'DackBitmap',uint64(0), ...
    'InputContextAvailable',false,'InputFrameKind','','InputControlType','', ...
    'InputAggregateId',uint64(0),'InputPacketId',uint64(0),'InputSequence',NaN, ...
    'InputRateKeyKbps',NaN,'InputRateBps',NaN,'InputPowerDbm',NaN, ...
    'InputReceivedPowerDbm',NaN,'PathlossDb',NaN, ...
    'SelectedRateKeyKbps',NaN,'SelectedRateBps',NaN,'SelectedPowerDbm',NaN, ...
    'ConfiguredNodePowerDbm',NaN,'PowerDefaulted',false, ...
    'PeerS0Dbm',NaN,'HopFailureCount',NaN,'NwkFailureCount',NaN, ...
    'LinkControlApplied',false,'QueueAccepted',false,'QueueDisposition','', ...
    'RetainedDecisionId',uint64(0));
end

function row = actualTemplate()
row = struct('ObservationId',uint64(0),'TimeSeconds',0,'Stage','ota_feedback', ...
    'NodeId',0,'PeerId',0,'FrameKind','','Sequence',0,'HasAckWindow',false, ...
    'AckBitmap',uint64(0),'DackBitmap',uint64(0), ...
    'AggregateId',uint64(0),'SegmentIndex',0,'SegmentCount',0, ...
    'DecisionId',uint64(0),'DecisionMatched',false, ...
    'SelectedRateKeyKbps',NaN,'SelectedRateBps',NaN,'SelectedPowerDbm',NaN, ...
    'RateKeyKbps',NaN,'RateBps',NaN,'TxPowerDbm',NaN,'Preamble','');
end

function row = feedbackIdentity(row,frame)
row.NodeId = frame.SourceId; row.PeerId = frame.DestinationId;
row.FrameKind = frame.Kind; row.Sequence = double(frame.Sequence);
row.HasAckWindow = logical(frame.HasAckWindow);
row.AckBitmap = frame.AckBitmap; row.DackBitmap = frame.DackBitmap;
end

function target = firstPeer(queue,peer)
target = [];
for index = 1:numel(queue)
    if queue{index}.Frame.DestinationId==peer, target = index; return; end
end
end

function target = firstSequence(queue,peer,sequence)
target = [];
for index = 1:numel(queue)
    frame = queue{index}.Frame;
    if frame.DestinationId==peer && frame.Sequence==sequence, target = index; return; end
end
end

function value = sameFeedback(left,right)
% MAC replaces rate/power/preamble on selected copies, so those fields cannot
% identify the retained admission. The full logical feedback identity can.
value = left.SourceId==right.SourceId && left.DestinationId==right.DestinationId && ...
    strcmp(left.Kind,right.Kind) && left.Sequence==right.Sequence && ...
    left.HasAckWindow==right.HasAckWindow && left.AckBitmap==right.AckBitmap && ...
    left.DackBitmap==right.DackBitmap;
end

function bps = operationalRate(key)
definition = csr.phy.rateDefinition(key); bps = definition.BitsPerSecond;
end

function value = scalarOr(item,name,fallback)
value = fallback;
if isstruct(item) && isfield(item,name) && ~isempty(item.(name)), value = item.(name); end
end
