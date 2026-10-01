function report=populationPreflight(config,folder)
%POPULATIONPREFLIGHT Exercise actual G NWK/HOP/MAC bridge through public APIs.
% Component inputs/completions remain at time zero. The network run method
% is never called; no PHY transmission or random variate is requested.
if ~isfolder(folder), mkdir(folder); end
bridgeFolder=fullfile(folder,'bridge'); if ~isfolder(bridgeFolder), mkdir(bridgeFolder); end
checks=struct('name',{},'passed',{},'details',{});
assert(isempty(ac.Trace.holder()),'autocase:PopulationPreflight','A trace capture is already active.');
probe=ac.PopulationProbe(); ac.Trace.holder('set',probe);
traceCleanup=onCleanup(@()ac.Trace.close()); %#ok<NASGU>
small=config; small.Trace.Enabled=false;
options=struct('Mode','natural','Fixture','','Folder',bridgeFolder);
simulation=ac.PopulationSimulation(small,[],[],options);
simulationCleanup=onCleanup(@()simulation.autonomousClose()); %#ok<NASGU>
index=find([simulation.Config.Nodes.Id]==1,1);
layer=simulation.Networks{index}; hop=simulation.Hops{index}; mac=simulation.Macs{index};
assert(rawCount(layer)==1 && macCount(mac)==1,'autocase:PopulationPreflight','Unexpected initial population.');

% A qualifying observation commits last-heard state and publishes before
% its fresh KEY_REQUEST takes the real HOP-to-MAC enqueue path.
layer.receiveControl(struct('Type','DISCOVER','Payload',discover()),5);
assert(rawCount(layer)==2 && macCount(mac)==2 && isequal(probe.PublishedCounts,2), ...
    'autocase:PopulationPreflight','DISCOVER did not publish the committed direct-peer count.');
assert(numel(probe.Ledger)>=2 && strcmp(probe.Ledger{1}.event,'publish') && ...
    strcmp(probe.Ledger{2}.event,'mac_enqueue') && ...
    strcmp(probe.Ledger{2}.frame.Control.Type,'KEY_REQUEST'), ...
    'autocase:PopulationPreflight','Publication did not precede inline admission.');
checks(end+1)=checked('actual_bridge_publishes_before_key_request_enqueue', ...
    struct('raw_count',2,'mac_count',2,'publication_precedes_response',true));

% KEY_UPDATE does not qualify as ProcessHello. Its real reliable HOP owner
% and subsequent Overheard owner complete through exact ACK receive inputs.
layer.receiveControl(struct('Type','KEY_UPDATE','Payload',struct('Generation',0)),3);
simulation.Scheduler.run(0);
own=probe.lastControl('KEY_UPDATE',3); exactAck(hop,own);
simulation.Scheduler.run(0);
own=probe.lastControl('NEIGHBOR_CHECK',3,'overheard'); exactAck(hop,own);
assert(rawCount(layer)==3 && macCount(mac)==2 && isequal(probe.PublishedCounts,2), ...
    'autocase:PopulationPreflight','ACK completion eagerly published or failed to retain the third direct peer.');
checks(end+1)=checked('acked_proof_changes_raw_count_without_publishing', ...
    struct('raw_count',3,'latched_mac_count',2,'published_values',probe.PublishedCounts));

% Exercise actual ACK and ROUTING enqueue paths while raw count and MAC
% latch deliberately differ. Passive radio, key and DATA callbacks do not
% publish; these inputs do not represent a new network simulation.
before=numel(probe.PublishedCounts); beforeAck=probe.countKind('ACK');
layer.observeRadio(8,struct('Success',true,'PathlossDb',120));
incoming=controlFrame(config,'KEY_UPDATE',struct('Generation',0),uint64(9001),7,1,uint16(101),true);
hop.receive(incoming,struct('Success',true));
assert(probe.countKind('ACK')>beforeAck,'autocase:PopulationPreflight','Actual feedback enqueue was not exercised.');
app=struct('Id',uint64(9002),'SourceId',3,'DestinationId',8,'GeneratedSeconds',0, ...
    'ApplicationPayloadBytes',0,'HopCount',0,'Traversal',3);
[accepted,reason]=layer.receiveData(app,3);
assert(~accepted && strcmp(reason,'no_route'),'autocase:PopulationPreflight','Unexpected component DATA route.');
bytes=routingBytes(); payload=struct('Bytes',bytes);
control=struct('Id',uint64(9003),'Type','ROUTING','Payload',payload, ...
    'WirePayloadBytes',csr.nwk.controlWireBytes('ROUTING',payload,1,config.Nwk.SecurityProfile));
[accepted,~]=hop.sendControl(control,5,struct('AckRequired',true,'EnvelopeProfile',config.Radio.EnvelopeProfile));
assert(accepted,'autocase:PopulationPreflight','Outgoing ROUTING did not reach the MAC queue.');
probe.lastControl('ROUTING',5);
assert(rawCount(layer)==3 && macCount(mac)==2 && numel(probe.PublishedCounts)==before, ...
    'autocase:PopulationPreflight','A nonqualifying callback or enqueue published the raw population.');
checks(end+1)=checked('passive_key_data_ack_and_routing_enqueue_do_not_publish', ...
    struct('actual_ack_enqueued',true,'actual_routing_enqueued',true,'raw_count',3,'mac_count',2));

% Each qualifying public observation path publishes the same persistent
% count. No synthetic population assignment is made by this preflight.
layer.receiveControl(struct('Type','DISCOVER','Payload',discover()),5);
assert(macCount(mac)==3 && numel(probe.PublishedCounts)==before+1, ...
    'autocase:PopulationPreflight','Next DISCOVER did not publish the pending count.');
layer.receiveControl(struct('Type','NEIGHBOR_CHECK','Payload', ...
    struct('Subtype','overheard','Sequence',0,'Active',false,'Generation',0)),5);
assert(numel(probe.PublishedCounts)==before+2,'autocase:PopulationPreflight','NeighborCheck did not publish.');
layer.receiveControl(struct('Type','ROUTING','Payload',payload),5);
assert(numel(probe.PublishedCounts)==before+3 && all(probe.PublishedCounts(end-2:end)==3), ...
    'autocase:PopulationPreflight','Valid ROUTING did not publish the direct-peer count.');
checks(end+1)=checked('qualifying_discover_check_routing_publish_current_count', ...
    struct('published_values',probe.PublishedCounts,'raw_count',rawCount(layer),'mac_count',macCount(mac)));
random=simulation.autonomousRandomSummary(); partial=simulation.autonomousPartial();
assert(random.draw_count==0 && partial.Statistics.PhysicalTransmissions==0 && simulation.Scheduler.Now==0, ...
    'autocase:PopulationPreflight','Component preflight unexpectedly started PHY/RNG work.');
simulation.autonomousClose(); ac.Trace.close();

% Freshness does not remove a persistent qualifying last-heard marker and
% does not itself publish a new population. Test the public Neighbors timer
% separately so no network clock or MAC timer advances.
neighborOptions=config.Nwk.Neighbor; neighborOptions.FreshnessEnabled=true;
neighborOptions.FreshnessTimeoutSeconds=2; neighborOptions.FreshnessPeriodSeconds=1;
[neighbors,clock,observer]=neighborFixture(neighborOptions);
neighbors.observe(5,struct()); neighbors.start(); clock.run(3);
state=neighbors.snapshot();
assert(state.Peers.Stale && 1+sum([state.Peers.LastHeardSeconds]>=0)==2 && ...
    isequal(observer.PublishedCounts,2),'autocase:PopulationPreflight', ...
    'Freshness expiry changed the persistent population or published eagerly.');
neighbors.observe(5,struct());
assert(isequal(observer.PublishedCounts,[2 2]),'autocase:PopulationPreflight', ...
    'Re-observation changed the persistent direct-peer count.');
checks(end+1)=checked('stale_peer_retains_count_until_qualified_republication', ...
    struct('persistent_count',2,'published_values',observer.PublishedCounts));

% Admission-disabled observe has an early return; publication must still
% precede its NeighborChanged callback and later Discovery response.
neighborOptions=config.Nwk.Neighbor; neighborOptions.AdmissionEnabled=false;
[neighbors,clock,observer]=neighborFixture(neighborOptions);
neighbors.receiveControl('DISCOVER',5,discover());
assert(numel(observer.Ledger)>=2 && strcmp(observer.Ledger{1}.event,'publish') && ...
    strcmp(observer.Ledger{2}.event,'neighbor_changed'), ...
    'autocase:PopulationPreflight','Admission-disabled observation skipped or delayed publication.');
clock.run(neighborOptions.ResponseDelaySeconds);
assert(any(cellfun(@(row)strcmp(row.event,'neighbor_send'),observer.Ledger)) && ...
    isequal(observer.PublishedCounts,2),'autocase:PopulationPreflight', ...
    'Admission-disabled response ordering was not exercised.');
checks(end+1)=checked('admission_disabled_publishes_before_changed_and_response', ...
    struct('first_event',observer.Ledger{1}.event,'second_event',observer.Ledger{2}.event));

report=struct('schema','csr-population-publication-preflight-v1','passed',all([checks.passed]), ...
    'checks',checks,'network_run_method_called',false,'physical_transmissions',0,'random_variates_requested',0, ...
    'integrated_component_clock_s',0, ...
    'scope','Actual G public NWK/HOP/MAC callback bridge plus separate public Neighbors timer; not network parity');
ac.writeJson(fullfile(folder,'population_preflight.json'),report);
end

function value=rawCount(layer)
state=layer.applicationState(); value=state.ActiveNodeCount;
end
function value=macCount(mac)
state=mac.snapshot(); value=state.ActiveNodesForSlotting;
end
function payload=discover()
payload=struct('Subtype','broadcast','Sequence',1,'ActivePeers',[]);
end
function exactAck(hop,sent)
ack=csr.hop.Frames.acknowledgment(sent.DestinationId,sent.SourceId,sent.Sequence,uint64(0),uint64(0), ...
    struct('HasAckWindow',false,'EnvelopeProfile',sent.EnvelopeProfile));
hop.receive(ack,struct('Success',true));
end
function frame=controlFrame(config,kind,payload,id,source,destination,sequence,reliable)
control=struct('Id',id,'Type',kind,'Payload',payload, ...
    'WirePayloadBytes',csr.nwk.controlWireBytes(kind,payload,1,config.Nwk.SecurityProfile));
frame=csr.hop.Frames.control(control,source,destination,sequence, ...
    struct('AckRequired',reliable,'EnvelopeProfile',config.Radio.EnvelopeProfile));
end
function bytes=routingBytes()
encoded=csr.nwk.RoutingCodec.encodeRecords({struct('Operation','REQUEST')});
sections=csr.nwk.RoutingCodec.sections(encoded,1); bytes=sections{1};
end
function [neighbors,clock,probe]=neighborFixture(options)
clock=csr.sim.EventScheduler(100); probe=ac.PopulationProbe();
callbacks=struct('PopulationObserved',@()probe.observed(), ...
    'NeighborChanged',@(peer,active)probe.changed(peer,active), ...
    'SendControl',@(kind,peers,payload,reliable)probe.neighborSend(kind,peers,payload,reliable));
neighbors=ac.PopulationNeighbors(1,clock,options,callbacks); probe.Neighbors=neighbors;
end
function value=checked(name,details)
value=struct('name',name,'passed',true,'details',details);
end
