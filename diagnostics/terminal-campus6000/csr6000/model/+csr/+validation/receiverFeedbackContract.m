function report = receiverFeedbackContract(outputDirectory,root)
%RECEIVERFEEDBACKCONTRACT Exercise real receiver HOP/NWK custody and feedback.
% Decoded DATA arrivals, MAC transmission and downstream feedback are
% prescribed. NWK owns every NSDP entry; no congestion count is assigned.
% This controlled callback contract does not exercise PHY or security ingress.
if nargin < 1, outputDirectory = ''; end
if nargin < 2, root = fileparts(fileparts(fileparts(mfilename('fullpath')))); end
inputDirectory = fullfile(root,'scenarios','t23');
referenceDirectory = fullfile(root,'evidence','t23','native');
cases = readCsv(fullfile(inputDirectory,'cases.csv'),{'case_id','policy','scope'});
actions = readCsv(fullfile(inputDirectory,'actions.csv'), ...
    {'case_id','action','packet','ack_packets','dack_packets','note'});
validateInputs(cases,actions);
rows = repmat(emptyRow(),0,1);
feedbackRows = repmat(emptyFeedback(),0,1);
for caseIndex = 1:height(cases)
    selected = actions.case_id == cases.case_id(caseIndex);
    runCase(cases(caseIndex,:),actions(selected,:));
end
checkpoints = struct2table(rows);
feedback = struct2table(feedbackRows);
comparison = compareReference(checkpoints,fullfile(referenceDirectory,'checkpoints.csv'), ...
    {'case_id','action','packet','rx_ack_hex','rx_dack_hex'});
feedbackComparison = compareReference(feedback,fullfile(referenceDirectory,'feedback.csv'), ...
    {'case_id','kind','ack_hex','dack_hex'});
summary = struct('Schema','csr-tranche23-receiver-feedback-contract-v1', ...
    'DiagnosticCompleted',true,'Passed',comparison.UnmatchedRows == 0 && ...
    comparison.ReferencePresent && comparison.SchemaMatches && ...
    feedbackComparison.UnmatchedRows == 0 && feedbackComparison.ReferencePresent && ...
    feedbackComparison.SchemaMatches, ...
    'CaseCount',height(cases),'CheckpointCount',height(checkpoints), ...
    'FailedCount',comparison.UnmatchedRows,'NativeComparison',comparison, ...
    'FeedbackCount',height(feedback),'FeedbackFailedCount',feedbackComparison.UnmatchedRows, ...
    'NativeFeedbackComparison',feedbackComparison, ...
    'ActionsSHA256',csr.validation.Artifacts.sha256(fullfile(inputDirectory,'actions.csv')), ...
    'CasesSHA256',csr.validation.Artifacts.sha256(fullfile(inputDirectory,'cases.csv')), ...
    'NativeReferenceSHA256','','NativeFeedbackReferenceSHA256','', ...
    'DataQueuedRetryPolicy','actual-tx', ...
    'Scope','Real NWK custody with decoded HOP arrivals, controlled MAC and prescribed downstream feedback; no PHY, security-ingress, campus or stochastic parity claim', ...
    'StateComparison','Exact integer state and 16-digit hexadecimal bitmaps; time tolerance 1e-9 seconds');
if isfile(fullfile(referenceDirectory,'checkpoints.csv'))
    summary.NativeReferenceSHA256 = csr.validation.Artifacts.sha256(fullfile(referenceDirectory,'checkpoints.csv'));
end
if isfile(fullfile(referenceDirectory,'feedback.csv'))
    summary.NativeFeedbackReferenceSHA256 = csr.validation.Artifacts.sha256(fullfile(referenceDirectory,'feedback.csv'));
end
if ~isempty(outputDirectory)
    if ~isfolder(outputDirectory), mkdir(outputDirectory); end
    writetable(checkpoints,fullfile(outputDirectory,'checkpoints.csv'));
    writetable(feedback,fullfile(outputDirectory,'feedback.csv'));
    copyfile(fullfile(inputDirectory,'actions.csv'),fullfile(outputDirectory,'actions.csv'));
    copyfile(fullfile(inputDirectory,'cases.csv'),fullfile(outputDirectory,'cases.csv'));
    csr.validation.Artifacts.writeJson(fullfile(outputDirectory,'summary.json'),summary);
end
report = summary;
report.Checkpoints = checkpoints;
report.Feedback = feedback;

    function runCase(config,sequence)
        clock = csr.sim.EventScheduler();
        options = struct('ResendSeconds',config.resend_seconds, ...
            'MaxResends',config.max_resends,'DackHoldSeconds',config.dack_seconds, ...
            'TicSeconds',config.tic_seconds,'PendingThreshold',config.pending_threshold, ...
            'FlowThresholdMax',config.flow_threshold_max, ...
            'DataQueuedRetryPolicy',char(config.policy));
        networkOptions = csr.nwk.defaults();
        networkOptions.StartupMode = 'manual';
        networkOptions.AdaptiveLinkControl = false;
        networkOptions.Neighbor.AdmissionEnabled = false;
        radio = struct('RateKeyKbps',8,'TxPowerDbm',30, ...
            'Preamble','long','EnvelopeProfile','bare');
        fullConfig = struct('Nwk',networkOptions,'Radio',radio, ...
            'Nodes',struct('Id',8,'Capability',1,'TransitForwardingEnabled',true));
        applications = containers.Map('KeyType','char','ValueType','any');
        saved = containers.Map('KeyType','char','ValueType','any');
        queued = containers.Map('KeyType','char','ValueType','any');
        releases = 0;
        deliveredCallbacks = 0;
        currentStep = 0;
        network = [];
        hop = csr.hop.Layer(8,clock,csr.sim.RandomStreams(130),options, ...
            struct('EnqueueMac',@enqueue,'CancelMac',@cancel, ...
            'Deliver',@deliver,'NsdpRelease',@release, ...
            'Terminal',@terminal,'Wake',@wake, ...
            'NsdpCount',@countNsdp,'RouteAvailable',@routeAvailable));
        network = csr.nwk.Layer(8,clock,csr.sim.RandomStreams(130),fullConfig, ...
            struct('CanSendData',@(peer)hop.canSend(peer), ...
            'SendData',@(app,peer,sendOptions)hop.send(app,peer,sendOptions), ...
            'CanSendControl',@(~)false,'Delivered',@(~,~)true,'Event',@networkEvent));
        % Public neighbor observations and a decoded routing update establish
        % the controlled 7 -> 8 -> 2 path toward final destination 1. Startup
        % discovery and autonomous control transmission are outside this gate.
        network.observe(2,struct());
        network.observe(7,struct());
        route = struct('Operation','UPDATE','NodeId',1,'Capability',2, ...
            'HopCount',1,'Cost',1,'Path',1);
        sections = csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords({route}),1);
        for sectionIndex = 1:numel(sections)
            network.receiveControl(struct('Type','ROUTING', ...
                'Payload',struct('Bytes',sections{sectionIndex})),2);
        end
        clock.run(0);
        generator = csr.sim.ApplicationGenerator(1, ...
            struct('SourceId',8,'DestinationId',1,'DestinationMode','fixed'),true,0);
        if ~network.routeAvailable(struct('SourceId',7,'DestinationId',1,'Traversal',7))
            error('csr:t23:FixtureRoute','Controlled route to destination 1 was not admitted.');
        end
        for actionIndex = 1:height(sequence)
            row = sequence(actionIndex,:);
            clock.run(row.time_s);
            currentStep = row.step;
            accepted = -1;
            alias = char(row.packet);
            switch char(row.action)
                case {'RX','LOCAL'}
                    if ~isKey(applications,alias)
                        app = struct('Id',uint64(row.step),'SourceId',row.nwk_source, ...
                            'DestinationId',row.destination,'GeneratedSeconds',clock.Now, ...
                            'ApplicationPayloadBytes',64,'Dscp',0,'AckRequired',true, ...
                            'HopCount',0,'Traversal',row.nwk_source);
                        applications(alias) = app;
                    else
                        app = applications(alias);
                        if strcmp(char(row.action),'LOCAL')
                            error('csr:t23:LocalReuse','LOCAL aliases cannot be reused.');
                        end
                        if app.SourceId ~= row.nwk_source || app.DestinationId ~= row.destination
                            error('csr:t23:ApplicationIdentity','RX alias changed application identity.');
                        end
                    end
                    if strcmp(char(row.action),'RX')
                        frame = csr.hop.Frames.data(app,7,8,uint16(row.sequence),radio);
                        hop.receive(frame);
                    else
                        [permitted,destination] = generator.attempt(clock.Now, ...
                            @(target)network.applicationState(target),@()0);
                        accepted = double(permitted);
                        if permitted
                            if destination ~= app.DestinationId || ~network.sendApplication(app)
                                error('csr:t23:LocalAdmission','A permitted local packet failed NWK admission.');
                            end
                        end
                    end
                case 'TX'
                    key = sequenceKey(row.sequence);
                    if ~isKey(queued,key)
                        error('csr:t23:MissingQueuedCopy','TX requires queued outbound sequence %s.',key);
                    end
                    frame = queued(key);
                    remove(queued,key);
                    hop.notifySent(frame);
                case 'FEEDBACK'
                    ack = sequenceList(row.ack_packets);
                    dack = sequenceList(row.dack_packets);
                    highest = max([ack; dack]);
                    allSequences = [ack; dack];
                    for sequenceIndex = 1:numel(allSequences)
                        if ~isKey(saved,sequenceKey(allSequences(sequenceIndex)))
                            error('csr:t23:UnknownFeedback','Feedback requires an admitted outbound sequence.');
                        end
                    end
                    frame = csr.hop.Frames.acknowledgment(2,8,uint16(highest), ...
                        bitmap(ack,highest),bitmap(dack,highest),radio);
                    hop.receive(frame);
                case 'PROBE'
                    % Observation only; all ownership is maintained by NWK/HOP.
            end
            % Explicit one-microsecond observation settling drains production
            % NWK pumps and +TIC HOP wakes before recording comparable state.
            clock.run(row.observe_s);
            state = hop.state(2);
            receiveState = hop.state(7);
            counts = hop.stats();
            networkCounts = network.stats();
            snapshot = emptyRow();
            snapshot.case_id = char(row.case_id);
            snapshot.step = row.step;
            snapshot.time_s = clock.Now;
            snapshot.action = char(row.action);
            snapshot.packet = char(row.packet);
            snapshot.accepted = accepted;
            snapshot.nsdp_relay = countPair(7);
            snapshot.nsdp_local = countPair(8);
            snapshot.nwk_waiting = networkCounts.WaitingForHop;
            snapshot.nwk_owned = networkCounts.PendingCustody;
            snapshot.hop_pending = state.PendingData;
            snapshot.hop_outstanding = state.NeighborOutstanding;
            snapshot.hop_resend = state.ResendQueueDepth;
            snapshot.hop_holds = state.DackHoldCount;
            snapshot.rx_highest = receiveState.DataReceiveWindow.Highest;
            snapshot.rx_ack_hex = dec2hex(receiveState.DataReceiveWindow.AckBitmap,16);
            snapshot.rx_dack_hex = dec2hex(receiveState.DataReceiveWindow.DackBitmap,16);
            snapshot.ack_generated = counts.AckGenerated;
            snapshot.dack_generated = counts.DackGenerated;
            snapshot.rx_received = counts.DataReceived;
            snapshot.rx_delivered = deliveredCallbacks;
            snapshot.rx_duplicates = counts.Duplicates;
            snapshot.nsdp_releases = releases;
            snapshot.ack_completed = counts.Acknowledged;
            snapshot.dack_completed = counts.Dacked;
            snapshot.dack_expired = counts.DackExpired;
            snapshot.data_tx = counts.Transmitted;
            rows(end+1,1) = snapshot; %#ok<AGROW>
        end

        function permitted = enqueue(frame)
            permitted = true;
            if strcmp(frame.Kind,'DATA')
                key = sequenceKey(double(frame.Sequence));
                saved(key) = frame;
                queued(key) = frame;
            elseif any(strcmp(frame.Kind,{'ACK','DACK'}))
                entry = emptyFeedback();
                entry.case_id = char(config.case_id);
                entry.step = currentStep;
                entry.time_s = clock.Now;
                entry.kind = frame.Kind;
                entry.sequence = double(frame.Sequence);
                entry.ack_hex = dec2hex(frame.AckBitmap,16);
                entry.dack_hex = dec2hex(frame.DackBitmap,16);
                entry.relay_nsdp = countPair(7);
                entry.local_nsdp = countPair(8);
                countsNow = network.stats();
                entry.nwk_owned = countsNow.PendingCustody;
                feedbackRows(end+1,1) = entry; %#ok<AGROW>
            else
                error('csr:t23:UnexpectedControl','The controlled MAC accepts only DATA and feedback.');
            end
        end
        function cancel(peer,sequenceNumber)
            if peer ~= 2, error('csr:t23:CancelPeer','Only downstream peer 2 has outbound custody.'); end
            key = sequenceKey(double(sequenceNumber));
            if isKey(queued,key), remove(queued,key); end
        end
        function acceptedByNetwork = deliver(app,peer)
            deliveredCallbacks = deliveredCallbacks+1;
            acceptedByNetwork = network.receiveData(app,peer);
        end
        function release(app,reason), network.releaseFromHop(app,reason); end
        function terminal(app,success,reason), network.terminal(app,success,reason); end
        function wake(), network.wake(); end
        function count = countNsdp(app), count = network.nsdpCount(app); end
        function available = routeAvailable(app), available = network.routeAvailable(app); end
        function count = countPair(source)
            count = network.nsdpCount(struct('SourceId',source,'DestinationId',1));
        end
        function networkEvent(name,~,~)
            if strcmp(name,'network_custody_release'), releases = releases+1; end
        end
    end
end

function row = emptyRow()
row = struct('case_id','','step',0,'time_s',0,'action','','packet','','accepted',-1, ...
    'nsdp_relay',0,'nsdp_local',0,'nwk_waiting',0,'nwk_owned',0, ...
    'hop_pending',0,'hop_outstanding',0,'hop_resend',0,'hop_holds',0, ...
    'rx_highest',-1,'rx_ack_hex','','rx_dack_hex','', ...
    'ack_generated',0,'dack_generated',0,'rx_received',0,'rx_delivered',0, ...
    'rx_duplicates',0,'nsdp_releases',0,'ack_completed',0,'dack_completed',0, ...
    'dack_expired',0,'data_tx',0);
end

function row = emptyFeedback()
row = struct('case_id','','step',0,'time_s',0,'kind','','sequence',0, ...
    'ack_hex','','dack_hex','','relay_nsdp',0,'local_nsdp',0,'nwk_owned',0);
end

function key = sequenceKey(value)
key = sprintf('%u',value);
end

function bits = bitmap(sequences,highest)
bits = uint64(0);
for index = 1:numel(sequences)
    offset = highest-sequences(index);
    if offset < 0 || offset >= 64
        error('csr:t23:FeedbackWindow','Feedback spans more than 64 outbound sequences.');
    end
    bits = bitset(bits,offset+1,1);
end
end

function list = sequenceList(value)
if strlength(value) == 0, list = zeros(0,1); return; end
parts = split(value,';');
if any(cellfun(@isempty,regexp(cellstr(parts),'^(0|[1-9][0-9]*)$','once')))
    error('csr:t23:FeedbackList','Feedback requires canonical decimal outbound sequences.');
end
list = str2double(parts);
if any(list > 65535) || numel(unique(list)) ~= numel(list)
    error('csr:t23:FeedbackList','Feedback requires unique uint16 outbound sequences.');
end
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

function validateInputs(cases,actions)
caseFields = {'case_id','resend_seconds','max_resends','dack_seconds','tic_seconds', ...
    'pending_threshold','flow_threshold_max','policy','scope'};
actionFields = {'case_id','step','time_s','observe_s','action','packet','sequence', ...
    'nwk_source','destination','ack_packets','dack_packets','note'};
if ~isequal(cases.Properties.VariableNames,caseFields) || ...
        ~isequal(actions.Properties.VariableNames,actionFields)
    error('csr:t23:Schema','Case and action CSV columns must match the T23 schema.');
end
if isempty(cases) || isempty(actions) || any(cases.case_id == "") || ...
        numel(unique(cases.case_id)) ~= height(cases) || any(cases.policy ~= "actual-tx") || ...
        ~isequal(unique(actions.case_id),sort(cases.case_id))
    error('csr:t23:Cases','Cases must be unique, complete, and retain actual-tx.');
end
for name = caseFields(2:7)
    value = cases.(name{1});
    if ~isnumeric(value) || any(~isfinite(value) | value < 0)
        error('csr:t23:Configuration','Case options must be finite nonnegative numbers.');
    end
end
for name = {'step','time_s','observe_s','sequence','nwk_source','destination'}
    value = actions.(name{1});
    if ~isnumeric(value) || any(~isfinite(value) | value < 0)
        error('csr:t23:ActionNumber','Action numbers must be finite and nonnegative.');
    end
end
if any(actions.sequence ~= fix(actions.sequence) | actions.sequence > 65535) || ...
        any(~ismember(actions.action,["RX","LOCAL","TX","FEEDBACK","PROBE"]))
    error('csr:t23:Action','Unknown action or invalid HOP sequence.');
end
for caseIndex = 1:height(cases)
    sequence = actions(actions.case_id == cases.case_id(caseIndex),:);
    if ~isequal(sequence.step,(1:height(sequence))') || ...
            any(sequence.observe_s < sequence.time_s) || ...
            any(sequence.time_s(2:end) < sequence.observe_s(1:end-1))
        error('csr:t23:Ordering','Actions require consecutive steps and nondecreasing times.');
    end
end
for actionIndex = 1:height(actions)
    row = actions(actionIndex,:);
    hasPacket = strlength(row.packet) > 0;
    if ismember(row.action,["RX","LOCAL"]) ~= hasPacket
        error('csr:t23:Packet','Only RX and LOCAL rows require application aliases.');
    end
    if row.action == "RX" && (row.nwk_source ~= 7 || ~ismember(row.destination,[1 8]))
        error('csr:t23:ReceiveAddress','RX applications originate at 7 and terminate at 1 or 8.');
    end
    if row.action == "LOCAL" && (row.nwk_source ~= 8 || row.destination ~= 1)
        error('csr:t23:LocalAddress','LOCAL applications originate at 8 and terminate at 1.');
    end
    ack = sequenceList(row.ack_packets); dack = sequenceList(row.dack_packets);
    hasFeedback = ~isempty(ack) || ~isempty(dack);
    if (row.action == "FEEDBACK") ~= hasFeedback
        error('csr:t23:Feedback','Only FEEDBACK requires ACK or DACK sequence lists.');
    end
end
end

function result = compareReference(actual,path,textColumns)
result = struct('ReferencePresent',isfile(path),'SchemaMatches',false, ...
    'ActualRows',height(actual),'ReferenceRows',0,'MatchedRows',0, ...
    'UnmatchedRows',height(actual),'FailedRows',[]);
if ~result.ReferencePresent, return; end
expected = readCsv(path,textColumns);
result.ReferenceRows = height(expected);
result.UnmatchedRows = max(height(actual),height(expected));
result.SchemaMatches = isequal(actual.Properties.VariableNames,expected.Properties.VariableNames);
if ~result.SchemaMatches, return; end
count = min(height(actual),height(expected));
matched = true(count,1);
for name = actual.Properties.VariableNames
    field = name{1};
    if ismember(field,textColumns)
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
