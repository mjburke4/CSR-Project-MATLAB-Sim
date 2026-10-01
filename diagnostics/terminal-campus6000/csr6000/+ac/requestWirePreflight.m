function report=requestWirePreflight(config,folder)
%REQUESTWIREPREFLIGHT Public REQUEST creation/ownership plus strict sizing guards.
% No simulation, PHY, MAC or random sampler is run. The recorder constructs
% real public HOP Frames from the candidate NWK's actual control callbacks.
if ~isfolder(folder), mkdir(folder); end
checks=struct('name',{},'passed',{},'details',{}); profile=config.Nwk.SecurityProfile;
sections=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords( ...
    {struct('Operation','REQUEST')}),6);
raw=struct('Bytes',sections{1}); compact=raw; compact.WireRepresentation='legacy_request_header';
assert(csr.nwk.controlWireBytes('ROUTING',raw,1,profile)==23 && ...
    ac.controlWireBytes('ROUTING',raw,1,profile)==23 && ...
    ac.controlWireBytes('ROUTING',compact,1,profile)==16, ...
    'autocase:RequestWirePreflight','REQUEST provenance did not distinguish raw from compact sizing.');
mixed=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords( ...
    {struct('Operation','REQUEST'),struct('Operation','DELETE','NodeId',8)}),7);
mixed=struct('Bytes',mixed{1});
assert(ac.controlWireBytes('ROUTING',mixed,1,profile)==16+numel(mixed.Bytes) && ...
    ac.controlWireBytes('ROUTING',raw,2,profile)==23, ...
    'autocase:RequestWirePreflight','Generic ARL or grouped raw REQUEST was compacted.');
checks(end+1)=checked('explicit_origin_distinguishes_compact_request_from_raw_arl', ...
    struct('unmarked_request_bytes',23,'marked_request_bytes',16,'mixed_raw_bytes',16+numel(mixed.Bytes)));

% Malformed provenance cannot reinterpret other controls, groups or bodies.
mustReject(@()ac.controlWireBytes('ROUTING',compact,2,profile),'autocase:RequestRepresentation');
mustReject(@()ac.controlWireBytes('NEIGHBOR_CHECK',compact,1,profile),'autocase:RequestRepresentation');
bad=compact; bad.Bytes(5)=1;
mustReject(@()ac.controlWireBytes('ROUTING',bad,1,profile),'autocase:RequestRepresentation');
bad=compact; bad.Bytes(7)=4;
mustReject(@()ac.controlWireBytes('ROUTING',bad,1,profile),'autocase:RequestRepresentation');
bad=mixed; bad.WireRepresentation='legacy_request_header';
mustReject(@()ac.controlWireBytes('ROUTING',bad,1,profile),'autocase:RequestRepresentation');
bad=compact; bad.WireRepresentation='unknown';
mustReject(@()ac.controlWireBytes('ROUTING',bad,1,profile),'autocase:RequestRepresentation');
bad=compact; bad.Bytes=double(bad.Bytes); bad.Bytes(1)=256;
mustReject(@()ac.controlWireBytes('ROUTING',bad,1,profile),'csr:nwk:InvalidControl');
checks(end+1)=checked('malformed_compact_markers_and_invalid_raw_bytes_are_rejected',struct('rejections',7));

% Drive actual local requestTick through public discovery completion. A real
% key/proof callback handshake establishes the active peer first. Rejected
% callbacks let the same retained owner exercise pump-time recomputation.
[layer,clock,probe]=ac.ControlWireProbe.fixture(config,true); probe.activatePeer(3);
probe.Accept=false; duration=0.001;
assert(layer.startDiscovery(0,duration),'autocase:RequestWirePreflight','Discovery did not start.');
clock.run(duration); rows=probe.requests();
assert(numel(rows)==1 && ~rows{1}.accepted,'autocase:RequestWirePreflight', ...
    'Public discovery completion did not create exactly one initial REQUEST.');
first=rows{1}; checkRequest(first);
checks(end+1)=checked('public_discovery_completion_preserves_request_origin_through_backlog', ...
    struct('wire_bytes',first.frame.WirePayloadBytes,'destination',first.peers, ...
    'payload_bytes',double(first.control.Payload.Bytes),'ack_required',first.options.AckRequired));

probe.Accept=true; layer.wake(); clock.run(clock.Now); rows=probe.requests();
assert(numel(rows)==2 && rows{2}.accepted && rows{2}.control.Id==first.control.Id && ...
    isequal(rows{2}.control.Payload,first.control.Payload), ...
    'autocase:RequestWirePreflight','Rejected submission lost the owner or its wire provenance.');
checkRequest(rows{2});
checks(end+1)=checked('rejected_admission_retry_preserves_owner_payload_and_sizing', ...
    struct('owner_id',first.control.Id,'attempts',2,'wire_bytes',rows{2}.frame.WirePayloadBytes));

% Final HOP failure retains ROUTING custody for another NWK cycle, changes
% its owner ID and recalculates bytes through the third size callsite.
sent=rows{2}; layer.controlResult(sent.control,3,false,true,[]); clock.run(clock.Now);
rows=probe.requests(); last=rows{end}; checkRequest(last);
assert(numel(rows)==3 && last.control.Id~=sent.control.Id && ...
    isequal(last.control.Payload,sent.control.Payload), ...
    'autocase:RequestWirePreflight','Residual routing retry changed compact request semantics.');
checks(end+1)=checked('residual_routing_cycle_recalculation_retains_compact_size', ...
    struct('old_owner_id',sent.control.Id,'new_owner_id',last.control.Id,'wire_bytes',last.frame.WirePayloadBytes));

% The request timer generates a fresh section/sequence with the same origin.
clock.run(duration+config.Nwk.RouteRequestSeconds); rows=probe.requests(); later=rows{end}; checkRequest(later);
assert(numel(rows)==4 && later.control.Id~=last.control.Id && ...
    ~isequal(later.control.Payload.Bytes,last.control.Payload.Bytes), ...
    'autocase:RequestWirePreflight','Scheduled REQUEST renewal lost provenance or reused the old section.');
checks(end+1)=checked('scheduled_request_renewal_remains_compact_with_new_sequence', ...
    struct('request_callbacks',numel(rows),'wire_bytes',later.frame.WirePayloadBytes, ...
    'time_s',later.time_s,'payload_bytes',double(later.control.Payload.Bytes)));

report=struct('schema','csr-request-wire-preflight-v1','passed',all([checks.passed]), ...
    'checks',checks,'network_simulation_executed',false,'random_variates_requested',0, ...
    'scope','Public NWK discovery/completion and HOP Frames API; no PHY reception or full-network parity claim');
ac.writeJson(fullfile(folder,'request_wire_preflight.json'),report);
end

function checkRequest(row)
payload=row.control.Payload; decoded=csr.nwk.RoutingCodec.decodeSection(payload.Bytes);
assert(strcmp(payload.WireRepresentation,'legacy_request_header') && isequal(row.peers,3) && ...
    row.options.AckRequired && row.control.WirePayloadBytes==16 && row.frame.WirePayloadBytes==16 && ...
    isequal(row.frame.Control.Payload,payload) && decoded.Section==0 && decoded.TotalSections==1 && ...
    numel(payload.Bytes)==7 && payload.Bytes(7)==3, ...
    'autocase:RequestWirePreflight','Actual request callback/frame changed size, destination or semantic payload.');
end
function mustReject(action,identifier)
rejected=false;
try, action(); catch problem, rejected=strcmp(problem.identifier,identifier); end
assert(rejected,'autocase:RequestWirePreflight','Malformed compact input did not fail with the expected guard.');
end
function value=checked(name,details)
value=struct('name',name,'passed',true,'details',details);
end
