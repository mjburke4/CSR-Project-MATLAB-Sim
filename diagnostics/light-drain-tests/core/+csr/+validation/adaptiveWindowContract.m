function report = adaptiveWindowContract(outputDirectory,root)
%ADAPTIVEWINDOWCONTRACT Replay prescribed callbacks through the real HOP layer.
% MAC admission succeeds and feedback arrival is prescribed. This is a
% controlled callback contract, not a PHY, campus, or random-stream test.
% Every input row advances the scheduler through its time before acting.
if nargin < 1, outputDirectory = ''; end
if nargin < 2, root = fileparts(fileparts(fileparts(mfilename('fullpath')))); end
inputDirectory = fullfile(root,'scenarios','t22');
reference = fullfile(root,'evidence','t22','native','checkpoints.csv');
cases = readCsv(fullfile(inputDirectory,'cases.csv'), ...
    {'case_id','policy','scope'});
actions = readCsv(fullfile(inputDirectory,'actions.csv'), ...
    {'case_id','action','packet','ack_packets','dack_packets','note'});
validateInputs(cases,actions);
rows = repmat(emptyRow(),0,1);
for caseIndex = 1:height(cases)
    selected = actions.case_id == cases.case_id(caseIndex);
    runCase(cases(caseIndex,:),actions(selected,:));
end
checkpoints = struct2table(rows);
comparison = compareReference(checkpoints,reference);
summary = struct('Schema','csr-tranche22-adaptive-window-contract-v1', ...
    'DiagnosticCompleted',true,'Passed',comparison.UnmatchedRows == 0 && ...
    comparison.ReferencePresent && comparison.SchemaMatches, ...
    'CaseCount',height(cases),'CheckpointCount',height(checkpoints), ...
    'FailedCount',comparison.UnmatchedRows,'NativeComparison',comparison, ...
    'ActionsSHA256',csr.validation.Artifacts.sha256(fullfile(inputDirectory,'actions.csv')), ...
    'CasesSHA256',csr.validation.Artifacts.sha256(fullfile(inputDirectory,'cases.csv')), ...
    'NativeReferenceSHA256','','DataQueuedRetryPolicy','actual-tx', ...
    'Scope','Decoded MATLAB HOP frames and authenticated native fixture feedback; no security-ingress, PHY, campus, or random-stream parity claim', ...
    'StateComparison','Exact integer state; action time tolerance 1e-9 seconds');
if isfile(reference)
    summary.NativeReferenceSHA256 = csr.validation.Artifacts.sha256(reference);
end
if ~isempty(outputDirectory)
    if ~isfolder(outputDirectory), mkdir(outputDirectory); end
    writetable(checkpoints,fullfile(outputDirectory,'checkpoints.csv'));
    copyfile(fullfile(inputDirectory,'actions.csv'),fullfile(outputDirectory,'actions.csv'));
    copyfile(fullfile(inputDirectory,'cases.csv'),fullfile(outputDirectory,'cases.csv'));
    csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'summary.json'),summary);
end
report = summary;
report.Checkpoints = checkpoints;

    function runCase(config,sequence)
        clock = csr.sim.EventScheduler();
        options = struct('ResendSeconds',config.resend_seconds, ...
            'MaxResends',config.max_resends,'DackHoldSeconds',config.dack_seconds, ...
            'TicSeconds',config.tic_seconds,'PendingThreshold',config.pending_threshold, ...
            'FlowThresholdMax',config.flow_threshold_max, ...
            'DataQueuedRetryPolicy',char(config.policy));
        % Saved frames retain identities for duplicate feedback; queued frames
        % are only copies handed to the controlled MAC by this HOP instance.
        saved = containers.Map('KeyType','char','ValueType','any');
        queued = containers.Map('KeyType','char','ValueType','any');
        aliases = containers.Map('KeyType','double','ValueType','char');
        releases = 0;
        hop = csr.hop.Layer(7,clock,csr.sim.RandomStreams(130),options, ...
            struct('EnqueueMac',@enqueue,'CancelMac',@cancel, ...
            'NsdpRelease',@release));
        for actionIndex = 1:height(sequence)
            row = sequence(actionIndex,:);
            clock.run(row.time_s);
            accepted = -1;
            alias = char(row.packet);
            switch char(row.action)
                case 'SEND'
                    if isKey(saved,alias)
                        error('csr:t22:PacketReuse','An accepted packet alias cannot be sent twice.');
                    end
                    accepted = double(hop.canSend(row.peer));
                    if accepted
                        id = double(row.step);
                        aliases(id) = alias;
                        app = struct('Id',uint64(id),'SourceId',7,'DestinationId',1, ...
                            'GeneratedSeconds',clock.Now,'ApplicationPayloadBytes',64,'Dscp',0);
                        [admitted,frame] = hop.send(app,row.peer,struct('EnvelopeProfile','bare', ...
                            'RateKeyKbps',8,'Preamble','long','AckRequired',true));
                        if ~admitted
                            error('csr:t22:Admission','HOP rejected a permitted controlled MAC admission.');
                        end
                        saved(alias) = frame;
                    end
                case 'TX'
                    if ~isKey(queued,alias)
                        error('csr:t22:MissingQueuedCopy','TX requires a currently queued HOP copy: %s.',alias);
                    end
                    frame = queued(alias);
                    requirePeer(frame,row.peer);
                    remove(queued,alias);
                    hop.notifySent(frame);
                case 'FEEDBACK'
                    ackAliases = packetList(row.ack_packets);
                    dackAliases = packetList(row.dack_packets);
                    allAliases = [ackAliases; dackAliases];
                    highest = -1;
                    for aliasIndex = 1:numel(allAliases)
                        key = char(allAliases(aliasIndex));
                        if ~isKey(saved,key)
                            error('csr:t22:UnknownFeedback','Feedback packet was not admitted: %s.',key);
                        end
                        frame = saved(key);
                        requirePeer(frame,row.peer);
                        highest = max(highest,double(frame.Sequence));
                    end
                    ack = bitmap(ackAliases,highest);
                    dack = bitmap(dackAliases,highest);
                    feedback = csr.hop.Frames.acknowledgment(row.peer,7,uint16(highest),ack,dack, ...
                        struct('EnvelopeProfile','bare','RateKeyKbps',8,'Preamble','long'));
                    hop.receive(feedback);
                case 'PROBE'
                    % A state observation invokes no protocol callback.
            end
            state = hop.state(row.peer);
            counts = hop.stats();
            snapshot = emptyRow();
            snapshot.case_id = char(row.case_id);
            snapshot.step = row.step;
            snapshot.time_s = clock.Now;
            snapshot.action = char(row.action);
            snapshot.packet = char(row.packet);
            snapshot.peer = row.peer;
            snapshot.accepted = accepted;
            snapshot.threshold = state.NeighborThreshold;
            snapshot.ack_count = state.AckCount;
            snapshot.outstanding = state.NeighborOutstanding;
            snapshot.global_pending = state.PendingData;
            snapshot.dack_holds = state.DackHoldCount;
            snapshot.resend = state.ResendQueueDepth;
            snapshot.can_send = double(hop.canSend(row.peer));
            snapshot.ack_total = counts.Acknowledged;
            snapshot.dack_total = counts.Dacked;
            snapshot.fail_total = counts.Failed;
            snapshot.nsdp_release_total = releases;
            snapshot.retry_total = counts.Retransmissions;
            snapshot.tx_total = counts.Transmitted;
            snapshot.dack_expired_total = counts.DackExpired;
            rows(end+1,1) = snapshot; %#ok<AGROW>
        end

        function permitted = enqueue(frame)
            alias = aliases(double(frame.App.Id));
            queued(alias) = frame;
            permitted = true;
        end
        function cancel(peer,sequenceNumber)
            keys = queued.keys;
            for queueIndex = 1:numel(keys)
                frame = queued(keys{queueIndex});
                if frame.DestinationId == peer && frame.Sequence == sequenceNumber
                    remove(queued,keys{queueIndex});
                end
            end
        end
        function release(~,~), releases = releases+1; end
        function value = bitmap(list,highestSequence)
            value = uint64(0);
            for item = 1:numel(list)
                frame = saved(char(list(item)));
                offset = highestSequence-double(frame.Sequence);
                if offset < 0 || offset >= 64
                    error('csr:t22:FeedbackWindow','Feedback spans more than one 64-sequence window.');
                end
                value = bitset(value,offset+1,1);
            end
        end
    end
end

function row = emptyRow()
row = struct('case_id','','step',0,'time_s',0,'action','','packet','','peer',0, ...
    'accepted',-1,'threshold',0,'ack_count',0,'outstanding',0,'global_pending',0, ...
    'dack_holds',0,'resend',0,'can_send',0,'ack_total',0,'dack_total',0, ...
    'fail_total',0,'nsdp_release_total',0,'retry_total',0,'tx_total',0,'dack_expired_total',0);
end

function tableValue = readCsv(path,textColumns)
options = detectImportOptions(path,'TextType','string','VariableNamingRule','preserve');
present = intersect(textColumns,options.VariableNames,'stable');
options = setvartype(options,present,'string');
tableValue = readtable(path,options);
for name = present
    values = tableValue.(name{1});
    values(ismissing(values)) = "";
    tableValue.(name{1}) = values;
end
end

function list = packetList(value)
if strlength(value) == 0, list = strings(0,1); return; end
list = split(value,';');
if any(strlength(list) == 0) || any(strip(list) ~= list) || numel(unique(list)) ~= numel(list)
    error('csr:t22:FeedbackList','Feedback lists require unique nonempty packet aliases.');
end
end

function requirePeer(frame,peer)
if double(frame.DestinationId) ~= peer
    error('csr:t22:PacketPeer','Packet and action peer differ.');
end
end

function validateInputs(cases,actions)
caseFields = {'case_id','resend_seconds','max_resends','dack_seconds','tic_seconds', ...
    'pending_threshold','flow_threshold_max','policy','scope'};
actionFields = {'case_id','step','time_s','action','packet','peer','ack_packets','dack_packets','note'};
if ~isequal(cases.Properties.VariableNames,caseFields) || ...
        ~isequal(actions.Properties.VariableNames,actionFields)
    error('csr:t22:Schema','Case and action CSV columns must match the T22 schema.');
end
if isempty(cases) || isempty(actions) || any(cases.case_id == "") || ...
        numel(unique(cases.case_id)) ~= height(cases) || any(cases.policy ~= "actual-tx") || ...
        ~isequal(unique(actions.case_id),sort(cases.case_id))
    error('csr:t22:Cases','Cases must be unique, complete, and use the unchanged actual-tx policy.');
end
for name = caseFields(2:7)
    value = cases.(name{1});
    if ~isnumeric(value) || any(~isfinite(value) | value < 0)
        error('csr:t22:Configuration','Case configuration must contain finite nonnegative numbers.');
    end
end
for name = {'step','time_s','peer'}
    value = actions.(name{1});
    if ~isnumeric(value) || any(~isfinite(value) | value < 0)
        error('csr:t22:ActionNumber','Action numbers must be finite and nonnegative.');
    end
end
if any(actions.peer ~= fix(actions.peer) | actions.peer > 16777214 | actions.peer == 7) || ...
        any(~ismember(actions.action,["SEND","TX","FEEDBACK","PROBE"]))
    error('csr:t22:Action','Unknown action or invalid remote peer.');
end
for caseIndex = 1:height(cases)
    sequence = actions(actions.case_id == cases.case_id(caseIndex),:);
    if ~isequal(sequence.step,(1:height(sequence))') || any(diff(sequence.time_s) < 0)
        error('csr:t22:Ordering','Actions must have consecutive steps and nondecreasing times within each case.');
    end
end
for actionIndex = 1:height(actions)
    row = actions(actionIndex,:);
    hasPacket = strlength(row.packet) > 0;
    if ismember(row.action,["SEND","TX"]) ~= hasPacket
        error('csr:t22:Packet','Only SEND and TX rows require a packet alias.');
    end
    ack = packetList(row.ack_packets); dack = packetList(row.dack_packets);
    hasFeedback = ~isempty(ack) || ~isempty(dack);
    if (row.action == "FEEDBACK") ~= hasFeedback
        error('csr:t22:Feedback','Only FEEDBACK rows require a nonempty ACK or DACK list.');
    end
end
end

function result = compareReference(actual,path)
result = struct('ReferencePresent',isfile(path),'SchemaMatches',false, ...
    'ActualRows',height(actual),'ReferenceRows',0,'MatchedRows',0, ...
    'UnmatchedRows',height(actual),'FailedRows',[]);
if ~result.ReferencePresent, return; end
expected = readCsv(path,{'case_id','action','packet'});
result.ReferenceRows = height(expected);
result.UnmatchedRows = max(height(actual),height(expected));
result.SchemaMatches = isequal(actual.Properties.VariableNames,expected.Properties.VariableNames);
if ~result.SchemaMatches, return; end
count = min(height(actual),height(expected));
matched = true(count,1);
for name = actual.Properties.VariableNames
    field = name{1};
    if ismember(field,{'case_id','action','packet'})
        matched = matched & string(actual.(field)(1:count)) == string(expected.(field)(1:count));
    else
        left = double(actual.(field)(1:count)); right = double(expected.(field)(1:count));
        tolerance = 0;
        if strcmp(field,'time_s'), tolerance = 1e-9; end
        matched = matched & isfinite(left) & isfinite(right) & abs(left-right) <= tolerance;
    end
end
result.MatchedRows = sum(matched);
result.UnmatchedRows = max(height(actual),height(expected))-sum(matched);
result.FailedRows = [find(~matched); (count+1:max(height(actual),height(expected)))'];
end
