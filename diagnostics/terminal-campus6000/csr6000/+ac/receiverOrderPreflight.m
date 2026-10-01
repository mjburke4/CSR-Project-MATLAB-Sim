function report=receiverOrderPreflight(root,config,folder)
%RECEIVERORDERPREFLIGHT Public three-radio RNG ownership regression.
% Arrivals remain in arrival order. Native closes all intervals in ascending
% source-owned physical signal ID, which can reverse arrival order.
if ~isfolder(folder), mkdir(folder); end
native=jsondecode(fileread(fullfile(root,'ref','receiver_order','native_receiver_order.json')));
assert(strcmp(native.schema,'csr-native-receiver-order-probe-v1') && native.passed, ...
    'autocase:ReceiverOrderPreflight','Missing verified native public probe.');
checks=struct('name',{},'passed',{},'details',{});
for name={'reverse','ascending'}
    key=name{1}; expected=native.(key);
    local=fullfile(folder,key); if ~isfolder(local), mkdir(local); end
    try
        actual=runProbe(config,local,expected);
        verifyCandidate(actual,expected);
        checks(end+1)=checked([key '_arrival_preserved_native_rng_order_matched'],actual); %#ok<AGROW>
    catch caught
        details=struct('identifier',caught.identifier,'message',caught.message,'stack',caught.stack);
        ac.writeJson(fullfile(local,'error.json'),details);
        checks(end+1)=struct('name',[key '_arrival_preserved_native_rng_order_matched'], ...
            'passed',false,'details',details); %#ok<AGROW>
    end
end
report=struct('schema','csr-receiver-order-preflight-v1','passed',all([checks.passed]), ...
    'checks',checks,'native_source_pin',native.native_source_pin, ...
    'scope','Public PHY transmissions and unchanged allocator; receiver-local draw context order only', ...
    'native_context_reference',native, ...
    'native_numeric_scope','Captured synthetic bits and probabilities are reference evidence, not a new full-PHY parity gate', ...
    'state_replayed',false,'feedback_replayed',false,'private_state_injected',false, ...
    'network_parity_established',false,'matlab_runtime_executed',true);
ac.writeJson(fullfile(folder,'receiver_order_preflight.json'),report);
end

function result=runProbe(config,folder,expected)
if ~isfolder(folder), mkdir(folder); end
ids=[config.Nodes.Id]; config.Nodes=config.Nodes(ismember(ids,[1 2 3]));
assert(numel(config.Nodes)==3,'autocase:ReceiverOrderPreflight','Probe requires nodes 1, 2 and 3.');
profile=csr.phy.RadioProfile.defaults(); profile.StochasticSyncThreshold=false;
profile.NoiseFloorDbm=0;
for k=1:numel(config.Nodes)
    config.Nodes(k).RadioProfile=profile;
    config.Nodes(k).PositionMeters=[double(config.Nodes(k).Id==3) 0 1];
end
config.Channel.PropagationSpeedMps=3e8;
config.Phy.SyncToTrackSeconds=0.00663; config.Phy.CaptureMarginDb=10.5;
clock=csr.sim.EventScheduler(1000);
streams=ac.Streams(132,clock,'natural','',folder);
cleanup=onCleanup(@()closeStreams(streams)); %#ok<NASGU>
probe=ac.ReceiverOrderProbe(streams); timing=csr.sim.TransportTiming('nanoseconds');
engine=ac.ReceiverTimerSignalEngine(config,clock,streams,@(frame,node,decision)[], ...
    @(name,frame,node,details)probe.record(name,frame,node,details),[],timing,ac.ReceiverTimer());
sources=reshape(expected.arrival_sources,1,[]);
first=frameFor(sources(1),uint64(1001)); second=frameFor(sources(2),uint64(1002));
assert(first.WirePayloadBytes==198 && second.WirePayloadBytes==198, ...
    'autocase:ReceiverOrderPreflight','Native probe wire geometry changed.');
try
    engine.transmit(first);
    clock.scheduleAt(0.026009895,@()engine.transmit(second)); clock.run(0.4);
catch caught
    streams.close();
    try, ac.writeJson(fullfile(folder,'public_phy_callbacks.json'),probe.Records); catch, end
    rethrow(caught);
end
streams.close();
records=probe.Records;
ac.writeJson(fullfile(folder,'public_phy_callbacks.json'),records);
arrival=[]; tracked=[]; closed=[];
for k=1:numel(records)
    row=records{k}; if row.node~=3, continue; end
    if strcmp(row.event,'phy_signal_start'), arrival(end+1)=row.source; end %#ok<AGROW>
    if strcmp(row.event,'phy_track'), tracked(end+1)=row.source; end %#ok<AGROW>
    if strcmp(row.event,'phy_interval') && row.time_ns==expected.close_time_ns
        closed(end+1)=row.source; %#ok<AGROW>
    end
end
assert(~isempty(tracked),'autocase:ReceiverOrderPreflight','No real acquisition callback executed.');
text=splitlines(string(fileread(fullfile(folder,'random_requests.jsonl')))); contexts={};
for k=1:numel(text)
    if strlength(text(k))==0, continue; end
    row=jsondecode(text(k));
    if row.node==3 && strcmp(row.purpose,'phy_binomial') && round(row.time_s*1e9)==expected.close_time_ns
        contexts{end+1}=row.actual; %#ok<AGROW>
    end
end
assert(numel(contexts)==3,'autocase:ReceiverOrderPreflight','Expected three observable receiver RNG requests at overlap closure.');
drawSources=cellfun(@(x)floor(x.tx_id/4294967296),contexts);
result=struct('mode','candidate','arrival_sources',arrival,'first_track_source',tracked(1), ...
    'close_time_ns',expected.close_time_ns,'close_sources',closed, ...
    'draw_sources',drawSources,'draw_contexts',[contexts{:}], ...
    'active_signals_at_end',engine.ActiveSignalCount);
assert(result.active_signals_at_end==0,'autocase:ReceiverOrderPreflight','Probe left uncompleted PHY signals.');
ac.writeJson(fullfile(folder,'probe_result.json'),result);
end

function frame=frameFor(source,id)
% Native's public raw packet plus header is 198 modeled on-air bytes. The
% portable DATA constructor contributes 32 envelope bytes, so a 166-byte
% synthetic body has the same PHY geometry. No application statistic is used.
app=struct('Id',id,'SourceId',source,'DestinationId',3, ...
    'GeneratedSeconds',0,'ApplicationPayloadBytes',166);
radio=struct('RateKeyKbps',8,'TxPowerDbm',0,'Preamble','short', ...
    'EnvelopeProfile','bare','AckRequired',false);
frame=csr.hop.Frames.data(app,source,3,uint16(1),radio); frame.Id=id;
end
function verifyCandidate(actual,expected)
assert(isequal(actual.arrival_sources,reshape(expected.arrival_sources,1,[])) && ...
    actual.first_track_source==expected.arrival_sources(1) && ...
    isequal(actual.close_sources,[1 2]) && ...
    isequal(actual.draw_sources,reshape(expected.draw_sources,1,[])), ...
    'autocase:ReceiverOrderPreflight','Arrival, acquisition or native interval/RNG order differs.');
a=actual.draw_contexts; b=expected.draw_contexts;
assert(numel(a)==numel(b),'autocase:ReceiverOrderPreflight','Native context count differs.');
for k=1:numel(a)
    assert(a(k).tx_id==b(k).tx_id && strcmp(a(k).component,b(k).component) && ...
        a(k).bits>0 && a(k).probability>0 && a(k).probability<1, ...
        'autocase:ReceiverOrderPreflight','Native signal/component order or active RNG ownership differs.');
end
end
function closeStreams(streams), streams.close(); end
function row=checked(name,details), row=struct('name',name,'passed',true,'details',details); end
