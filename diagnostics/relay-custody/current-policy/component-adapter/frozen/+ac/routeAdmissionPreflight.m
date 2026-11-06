function report=routeAdmissionPreflight(config,folder) %#ok<INUSD>
%ROUTEADMISSIONPREFLIGHT Public route API checks, without network callbacks.
% A negative control reproduces the observed DELETE bytes. The isolated H
% operation changes only admission; observed HELLO updates remain intact.
if ~isfolder(folder), mkdir(folder); end
checks=struct('name',{},'passed',{},'details',{});

baseline=csr.nwk.Routes(1,0);
baseline.setNeighbor(3,true,3587,14.400468077);
[records,ids]=baseline.drainChanges();
sections=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords(records),4);
expected=uint8([0 0 0 4 0 1 1 0 0 3]);
assert(isequal(ids,3) && isequal(sections{1},expected), ...
    'autocase:RouteAdmissionPreflight','Baseline did not reproduce the observed DELETE3 bytes.');
checks(end+1)=checked('baseline_unobserved_admission_reproduces_delete3', ...
    struct('routing_section_hex','00000004000101000003','selected_cost',3587));

routes=ac.AdmissionRoutes(1,0);
routes.admitNeighbor(3,3587,14.400468077);
[records,ids]=routes.drainChanges();
assert(isempty(routes.Candidates) && isempty(routes.select(3)) && ...
    isempty(records) && isempty(ids),'autocase:RouteAdmissionPreflight', ...
    'Unobserved admission allocated or selected a route or emitted a change.');
checks(end+1)=checked('unobserved_admission_has_no_candidate_or_change', ...
    struct('candidate_count',0,'change_count',0));

% A later observed HELLO creates the direct route through the original path.
routes.setNeighbor(3,true,3587,18.724108077);
selected=routes.select(3); [records,ids]=routes.drainChanges();
assert(isscalar(selected) && selected.Valid && selected.Immediate && ...
    selected.Capability==0 && selected.Cost==3587 && isequal(ids,3) && ...
    numel(records)==1 && strcmp(records{1}.Operation,'DELETE'), ...
    'autocase:RouteAdmissionPreflight','Observed HELLO no longer creates the legitimate direct route.');
checks(end+1)=checked('later_observation_creates_direct_route_and_legitimate_delete', ...
    struct('cost',selected.Cost,'operation',records{1}.Operation));

% A previously observed direct candidate must become selectable, including
% capability zero: only allocation by ACK admission is erroneous.
routes=ac.AdmissionRoutes(1,0);
routes.setNeighbor(3,false,3587,1);
before=routes.Candidates; routes.drainChanges();
routes.admitNeighbor(3,9999,2);
[records,ids]=routes.drainChanges(); selected=routes.select(3);
assert(isequal(before,routes.Candidates) && selected.Cost==3587 && ...
    isequal(ids,3) && strcmp(records{1}.Operation,'DELETE'), ...
    'autocase:RouteAdmissionPreflight','Admission mutated or suppressed an existing direct route.');
checks(end+1)=checked('observed_capability_zero_candidate_is_selected_without_mutation', ...
    struct('cost_before',3587,'admission_cost_argument',9999,'cost_after',selected.Cost));

routes=ac.AdmissionRoutes(1,0);
routes.setNeighbor(3,false,3587,1);
routes.apply(3,7,{update(3,1,0,0,[])},3587,2);
before=routes.Candidates; routes.drainChanges();
routes.admitNeighbor(3,9999,3);
[records,ids]=routes.drainChanges(); selected=routes.select(3);
assert(isequal(before,routes.Candidates) && isequal(ids,3) && ...
    strcmp(records{1}.Operation,'UPDATE') && records{1}.Cost==3587 && ...
    records{1}.Capability==1 && selected.LastUpdatedSeconds==2, ...
    'autocase:RouteAdmissionPreflight','Capability/cost/sequence/timestamp changed during admission.');
routes.admitNeighbor(3,1234,4);
[records,ids]=routes.drainChanges();
assert(isempty(records) && isempty(ids) && isequal(before,routes.Candidates), ...
    'autocase:RouteAdmissionPreflight','Repeated admission changed an already active peer.');
checks(end+1)=checked('observed_capable_candidate_admission_and_repeat', ...
    struct('cost',3587,'capability',1,'sequence',7,'updated_seconds',2));

% Admission recomputes destination=peer, not every cached transit destination.
routes=ac.AdmissionRoutes(1,0);
routes.setNeighbor(3,false,100,1);
routes.apply(3,1,{update(4,1,1,200,4)},100,2);
routes.drainChanges(); before=routes.Candidates;
routes.admitNeighbor(3,100,3);
after=routes.Candidates;
transit=after([after.DestinationId]==4);
assert(transit.Valid && transit.SelectionDeferred && isempty(routes.select(4)) && ...
    isequal(before,after),'autocase:RouteAdmissionPreflight', ...
    'Admission released a transit destination that native leaves deferred.');
checks(end+1)=checked('unrelated_transit_candidate_stays_deferred', ...
    struct('destination',4,'selection_deferred',true));

% Public UPDATE with a loop creates an invalid deferred candidate to peer3
% via peer5. No private candidate state is forged for the invalidity check.
routes=ac.AdmissionRoutes(1,0);
routes.setNeighbor(5,false,100,1);
routes.apply(5,1,{update(3,1,1,200,1)},100,2);
routes.admitNeighbor(5,100,3); routes.drainChanges();
before=routes.Candidates;
routes.admitNeighbor(3,200,4);
after=routes.Candidates; invalid=after([after.DestinationId]==3);
[records,ids]=routes.drainChanges();
assert(isequal(before,after) && ~invalid.Valid && invalid.SelectionDeferred && ...
    isempty(routes.select(3)) && isempty(records) && isempty(ids), ...
    'autocase:RouteAdmissionPreflight','Admission revived or rewrote an invalid cached candidate.');
checks(end+1)=checked('invalid_cached_candidate_preserved', ...
    struct('destination',3,'next_hop',5,'valid',false,'selection_deferred',true));

% Logical destination creation occurs on admission even without a candidate.
% A later observation must not insert that destination again at list head.
routes=ac.AdmissionRoutes(1,0);
routes.admitNeighbor(3,100,1);
routes.setNeighbor(5,false,100,2); routes.admitNeighbor(5,100,3);
routes.setNeighbor(3,true,100,4);
[records,ids]=routes.drainChanges();
assert(isequal(ids,[5 3]) && numel(records)==2, ...
    'autocase:RouteAdmissionPreflight','Admission destination-order side effect was lost.');
checks(end+1)=checked('admission_preserves_logical_destination_creation_order', ...
    struct('changed_destination_order',ids));

report=struct('schema','csr-route-admission-preflight-v1','passed',all([checks.passed]), ...
    'checks',checks,'network_simulation_executed',false,'random_variates_requested',0, ...
    'scope','Public Routes API: admission allocation, legitimate changes, deferred state and ordering', ...
    'limitation','Full H network continuation is a separate result; no private candidate state was injected');
ac.writeJson(fullfile(folder,'route_admission_preflight.json'),report);
end

function record=update(node,capability,hops,cost,path)
record=struct('Operation','UPDATE','NodeId',node,'Capability',capability, ...
    'HopCount',hops,'Cost',cost,'Path',path);
end

function result=checked(name,details)
result=struct('name',name,'passed',true,'details',details);
end
