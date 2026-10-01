function report=run_node8_tests
%RUN_NODE8_TESTS Relay-copy custody repair: seed 132, 0 <= t < 1200 s.
% Restart MATLAB R2025a and set Current Folder to the extracted node8case.
%   report = run_node8_tests;
% Return the printed ZIP, including partial evidence on a divergence.
root=char(java.io.File(fileparts(mfilename('fullpath'))).getCanonicalPath());
oldPath=path; oldFolder=pwd;
restoreEnvironment=onCleanup(@()restore(oldPath,oldFolder)); %#ok<NASGU>
out=uniqueFolder(root,['out_node8_' datestr(now,'yyyymmdd_HHMMSS')]);
report=struct('schema','csr-relay-custody-1200-v1','completed',false, ...
    'candidate_behavior_changed',true, ...
    'repair_scope','Distinct accepted relay-copy custody with unique-application delivery accounting', ...
    'numerical_parity_established',false,'target_percent',20, ...
    'common_input_context_tolerance','Unchanged strict semantic comparisons', ...
    'independent_raw_trace_audit_pending',true, ...
    'runtime',struct('version',version,'release',version('-release'),'computer',computer), ...
    'preflights',struct([]),'cases',struct([]),'archive','','archive_completed',false, ...
    'error_identifier','','error_message','');
diary(fullfile(out,'console.log')); diaryCleanup=onCleanup(@()diary('off')); %#ok<NASGU>
started=tic;
fprintf('\nRelay-copy custody repair: seed 132, 0–1200 s, all seven nodes from time zero.\n');
fprintf('Only common random inputs are supplied. MATLAB generates all network states and feedback.\n');
fprintf('The engineering target is now +/-20%%. This diagnostic keeps strict contexts and random-request timestamp checks.\n');
fprintf('Allow one to several hours; long quiet periods during simulation are expected.\n');
fprintf('Return the final ZIP even if the test stops at a divergence.\n');
try
    model=fullfile(root,'model');
    loaded=inmem('-completenames');
    for k=1:numel(loaded)
        file=strrep(char(loaded{k}),'\','/');
        if contains(file,'/+csr/') || contains(file,'/+ac/') || endsWith(file,'/TestQueuedRetryPolicy.m')
            file=char(java.io.File(char(loaded{k})).getCanonicalPath());
            assert(startsWith(file,[root filesep]),'autocase:CachedModel', ...
                'Another CSR copy is loaded. Restart MATLAB and run this node8case folder.');
        end
    end
    cd(root); restoredefaultpath; addpath(root,model,'-begin'); rehash;
    manifestPath=fullfile(root,'FILES.json'); manifestHash=hashFile(manifestPath);
    manifest=jsondecode(fileread(manifestPath));
    assert(strcmp(manifest.schema,'csr-relay-custody-1200-kit-v1') && manifest.target_percent==20 && ...
        manifest.model_behavior_changed && manifest.candidate_behavior_changed, ...
        'node8:Manifest','Unexpected kit or acceptance target.');
    verifyFiles(root,manifest.files); resolved=bindSource(root,manifest.files);
    delta=verifyCandidateDelta(root,manifest);
    historical=verifyHistoricalReference(root,report.runtime);
    report.historical_reference=historical;
    ac.writeJson(fullfile(out,'provenance.json'),struct('runtime',report.runtime, ...
        'manifest_sha256',manifestHash,'manifest',manifest,'resolved_matlab_files',resolved, ...
        'candidate_delta',delta,'historical_reference',historical, ...
        'production_model_changed',true,'candidate_behavior_changed',true, ...
        'receiver_state_or_feedback_replayed',false, ...
        'simulation_class','ac.TerminalSimulation','random_mode','native', ...
        'ordered_trace_sink','Unchanged ac.Recorder; streamed directly to disk', ...
        'node8_pump_skip_reasons','Not instrumented; reconstruct observable queue/capacity transitions only'));
    % A short-duration configuration feeds isolated component checks only.
    % Historical natural tables do not validate this changed candidate.
    config=loadScenario(root,132,330);
    config.Trace.MaxRecords=200000; config.Trace.MaxPhyRecords=200000;
    config.Trace.MaxApplicationAdmissionRecords=20000; config.MaxEvents=2000000;
    config=csr.scenario.validate(config);
    report.preflights=runPreflight('original_native_import', ...
        @()ac.nativeImportPreflight(root,fullfile(out,'import_preflight')),out);
    names={'tx_timing_comparator','receiver_interval_order','key_request','check_gate','population','route_admission', ...
        'request_wire','no_path_wire','discovery_identity','receiver_timer','discovery_lifecycle', ...
        'discovery_membership','feedback_identity','retry_policy','terminal','integrated_accounting','relay_custody'};
    callbacks={ ...
        @()txTimingPreflight(root,fullfile(out,'tx_timing_preflight')), ...
        @()ac.receiverOrderPreflight(root,config,fullfile(out,'receiver_order_preflight')), ...
        @()ac.keyRequestPreflight(config,fullfile(out,'key_preflight')), ...
        @()ac.checkGatePreflight(config,fullfile(out,'check_preflight')), ...
        @()ac.populationPreflight(config,fullfile(out,'population_preflight')), ...
        @()ac.routeAdmissionPreflight(config,fullfile(out,'route_preflight')), ...
        @()ac.requestWirePreflight(config,fullfile(out,'request_preflight')), ...
        @()ac.noPathWirePreflight(config,fullfile(out,'no_path_preflight')), ...
        @()ac.discoveryIdentityPreflight(root,fullfile(out,'identity_preflight')), ...
        @()ac.receiverTimerPreflight(root,config,fullfile(out,'timer_preflight')), ...
        @()ac.discoveryLifecyclePreflight(config,fullfile(out,'lifecycle_preflight')), ...
        @()ac.discoveryMembershipPreflight(config,fullfile(out,'membership_preflight')), ...
        @()ac.feedbackIdentityPreflight(root,fullfile(out,'feedback_preflight')), ...
        @()ac.retryPolicyPreflight(config,fullfile(out,'retry_preflight')), ...
        @()ac.terminalPreflight(config,fullfile(out,'terminal_preflight')), ...
        @()ac.integratedAccountingPreflight(config,fullfile(out,'integrated_accounting')), ...
        @()ac.relayCustodyPreflight(config,fullfile(out,'relay_custody_preflight'))};
    for k=1:numel(names)
        report.preflights(end+1)=runPreflight(names{k},callbacks{k},out);
    end
    definition=struct('name','S132_1200','seed',132,'stop_seconds',1200,'fixture','native132_1200');
    caseFolder=fullfile(out,definition.name); mkdir(caseFolder);
    fixture=fullfile(root,'ref',definition.fixture);
    importResult=runPreflight('S132_1200_import', ...
        @()ac.batchImportPreflight(fixture,132,1200,fullfile(caseFolder,'import_preflight')),out);
    if all([report.preflights.passed]) && importResult.passed
        item=runNetwork(caseFolder,loadScenario(root,132,1200),definition,fixture);
    else
        item=emptyCase(definition); item.diagnostic_status='prerequisite_failed';
        item.error_identifier='node8:Prerequisite';
        item.error_message='A required import or component preflight failed. Network was not started.';
    end
    item.import_preflight=importResult; report.cases=item;
    ac.writeJson(fullfile(caseFolder,'case_summary.json'),item);
    verifyFiles(root,manifest.files);
    assert(strcmp(manifestHash,hashFile(manifestPath)), ...
        'node8:ManifestChanged','Kit manifest changed during the run.');
    report.completed=item.completed && all([report.preflights.passed]) && importResult.passed;
catch caught
    report.error_identifier=caught.identifier; report.error_message=caught.message;
    report.error_stack=caught.stack;
    fprintf('\nSetup or final verification failed: %s\n',caught.message);
end
ac.Trace.close(); report.wall_seconds=toc(started); report.archive=[out '.zip'];
embeddedReport=rmfield(report,'archive_completed');
embeddedReport.archive_status='Archive creation follows this report; receipt is saved beside the output.';
ac.writeJson(fullfile(out,'report.json'),embeddedReport); diary('off');
try
    listing=dir(fullfile(out,'**','*')); listing=listing(~[listing.isdir]);
    names=cell(numel(listing),1);
    for k=1:numel(listing)
        file=fullfile(listing(k).folder,listing(k).name); names{k}=file(numel(out)+2:end);
    end
    zip(report.archive,names,out); report.archive_completed=true;
    ac.writeJson(fullfile(out,'archive_receipt.json'), ...
        struct('archive',report.archive,'sha256',hashFile(report.archive),'completed',true));
    fprintf('\nReturn this ZIP, including every partial result or failure:\n%s\n',report.archive);
catch caught
    report.archive_error=caught.message;
    fprintf('\nZIP creation failed: %s\nEvidence is in %s\n',caught.message,out);
end
fprintf('All diagnostic gates passed=%d; ZIP created=%d; elapsed %.1f min.\n', ...
    report.completed,report.archive_completed,toc(started)/60);
end

function proof=verifyCandidateDelta(root,manifest)
% The accepted source manifest is immutable history. The current manifest
% hashes every packaged byte; this independent allowlist bounds the repair.
folder=fullfile(root,'review','validated_short_v2');
audit=jsondecode(fileread(fullfile(folder,'return_audit.json')));
assert(strcmp(audit.status,'pass') && ...
    strcmp(audit.issued_manifest_sha256,'8c3a4e7f0dc4e9d956509f2399877377bad90ff531290980b64427cfe9fb3920'), ...
    'node8:AcceptedCandidate','The historical short-batch source receipt is not the accepted v2.');
issuedPath=fullfile(folder,'issued_FILES.json');
assert(strcmp(hashFile(issuedPath),audit.issued_manifest_sha256), ...
    'node8:AcceptedManifest','Historical accepted source manifest changed.');
issued=jsondecode(fileread(issuedPath));
authorized={'+ac/AccountingFixture.m';'+ac/DiscoveryMembershipNwk.m'; ...
    '+ac/TerminalSimulation.m';'+ac/integratedAccountingPreflight.m'; ...
    'model/+csr/+nwk/Layer.m'; ...
    'model/+csr/+sim/NetworkSimulation.m'};
added={'+ac/RelayCustodyProbe.m';'+ac/relayCustodyPreflight.m'};
assert(isequal(sort(string(manifest.authorized_existing_delta_paths(:))),sort(string(authorized))) && ...
    isequal(sort(string(manifest.added_candidate_paths(:))),sort(string(added))), ...
    'node8:RepairScope','Manifest repair scope differs from the reviewed exact allowlist.');
oldPaths=string({issued.files.path}); newPaths=string({manifest.files.path});
assert(numel(unique(newPaths))==numel(newPaths),'node8:ManifestDuplicate','Duplicate manifest path.');
changed=struct('path',{},'historical_sha256',{},'candidate_sha256',{}); unchanged=0; count=0;
for k=1:numel(issued.files)
    p=char(issued.files(k).path);
    if ~(startsWith(p,'model/') || startsWith(p,'+ac/')), continue; end
    count=count+1;
    index=find(newPaths==string(p));
    assert(numel(index)==1,'node8:CandidatePopulation','Historical candidate file missing from current manifest: %s.',p);
    currentHash=hashFile(fullfile(root,strrep(p,'/',filesep)));
    if any(strcmp(p,authorized))
        assert(~strcmp(currentHash,issued.files(k).sha256),'node8:RepairMissing', ...
            'Expected reviewed repair is absent from %s.',p);
        changed(end+1)=struct('path',p,'historical_sha256',issued.files(k).sha256, ...
            'candidate_sha256',currentHash); %#ok<AGROW>
    else
        verifyFiles(root,issued.files(k)); unchanged=unchanged+1;
    end
end
assert(count==167 && numel(changed)==numel(authorized),'node8:CandidatePopulation', ...
    'Historical source population or authorized repair population changed.');
extra=newPaths((startsWith(newPaths,'model/') | startsWith(newPaths,'+ac/')) & ~ismember(newPaths,oldPaths));
assert(isequal(sort(extra(:)),sort(string(added))),'node8:AddedCandidateScope', ...
    'Unexpected added candidate file, or a required focused-test dependency is missing.');
proof=struct('historical_short_archive_sha256',audit.archive.sha256, ...
    'historical_issued_manifest_sha256',audit.issued_manifest_sha256, ...
    'historical_model_and_candidate_files',count,'unchanged_files',unchanged, ...
    'authorized_changed_files',changed,'added_test_files',{added}, ...
    'model_behavior_changed',true,'historical_acceptance_applies_to_current_model',false, ...
    'current_common_input_window',[0 1200]);
end

function item=runPreflight(name,callback,out)
item=struct('name',name,'passed',false,'result',struct(),'error_identifier','','error_message','');
fprintf('Checking %s.\n',name);
try
    item.result=callback();
    assert(isfield(item.result,'passed') && item.result.passed, ...
        'paritybatch:PreflightFailed','Preflight returned an unsuccessful result.');
    item.passed=true;
catch caught
    item.error_identifier=caught.identifier; item.error_message=caught.message;
    ac.writeJson(fullfile(out,[name '_error.json']),errorDetails(caught));
    fprintf('%s failed: %s\n',name,caught.message);
end
ac.Trace.close();
end

function config=loadScenario(root,seed,stopSeconds)
config=csr.scenario.importNs3(fullfile(root,'inputs',sprintf('s%g.csv',seed)), ...
    struct('HistoricalBenchmark',true,'FlowLimit',0,'Backend','portable'));
assert(config.Seed==seed && config.DurationSeconds==6000,'autocase:Scenario','Wrong source scenario.');
assert(isequal([config.Nodes.Id],[1 2 3 4 5 7 8]),'autocase:Nodes','All seven campus nodes are required.');
assert(numel(config.Traffic)==6 && all([config.Traffic.StartSeconds]==300) && ...
    all([config.Traffic.IntervalSeconds]==0.02) && all([config.Traffic.DestinationId]==1), ...
    'autocase:Traffic','Original source offers changed.');
config.DurationSeconds=stopSeconds;
config.Trace.Enabled=true; config.Trace.MaxRecords=750000; config.Trace.MaxPhyRecords=750000;
% 132/1200 offers 270,000 attempts; retain every admission decision.
config.Trace.MaxApplicationAdmissionRecords=500000;
config.MaxEvents=4000000; config=csr.scenario.validate(config);
end

function item=emptyCase(definition)
if nargin==0, definition=struct('name','','seed',NaN,'stop_seconds',NaN); end
item=struct('name',definition.name,'seed',definition.seed,'mode','native', ...
    'requested_stop_seconds',definition.stop_seconds,'completed',false, ...
    'reached_time_s',NaN,'diagnostic_status','not_started', ...
    'error_identifier','','error_message','','wall_seconds',0,'import_preflight',struct());
end

function item=runNetwork(folder,config,definition,fixture)
item=emptyCase(definition); started=tic; ac.Trace.open(folder);
observer=csr.sim.AckServiceDiagnostics(500000,[0 definition.stop_seconds]);
timing=csr.sim.TransportTiming('nanoseconds',750000);
options=struct('Mode','native','Fixture',fullfile(fixture,'random_draws.csv'),'Folder',folder);
fprintf('\n%s starting from time zero. Stop at first semantic divergence.\n',definition.name);
try
    assert(strcmp(config.Hop.DataQueuedRetryPolicy,'actual-tx'),'autocase:RetryPolicyBaseline', ...
        'Expected unchanged actual-tx default.');
    caseConfig=config; caseConfig.Hop.DataQueuedRetryPolicy='native-provisional';
    caseConfig=csr.scenario.validate(caseConfig);
    restored=caseConfig; restored.Hop.DataQueuedRetryPolicy=config.Hop.DataQueuedRetryPolicy;
    assert(isequaln(restored,config),'autocase:RetryPolicyScope','Fields outside DATA retry policy changed.');
    ac.writeJson(fullfile(folder,'configuration.json'),caseConfig);
    ac.writeJson(fullfile(folder,'policy_selection.json'),struct( ...
        'path','Hop.DataQueuedRetryPolicy','baseline','actual-tx','selected','native-provisional', ...
        'single_field_change_verified',true,'default_changed',false, ...
        'receiver_state_or_feedback_replayed',false));
    simulation=ac.TerminalSimulation(caseConfig,observer,timing,options);
    simulationCleanup=onCleanup(@()simulation.autonomousClose()); %#ok<NASGU>
    result=simulation.run(); item.reached_time_s=simulation.Scheduler.Now;
    exportRaw(result,folder,definition.stop_seconds);
    exportFinal(result,folder);
    txTiming=txTimingGate(result.ProtocolTrace,fixture,folder,definition.stop_seconds);
    assert(txTiming.passed,'node8:TxTimingDivergence', ...
        'Physical TX counts, source/order or integer-nanosecond times differed; comparison evidence is saved.');
    assert(item.reached_time_s==definition.stop_seconds,'autocase:Incomplete','Requested endpoint was not reached.');
    assert(result.Statistics.OmittedTraceRecords==0 && result.Statistics.OmittedPhyTraceRecords==0 && ...
        result.Statistics.OmittedApplicationAdmissionRecords==0,'autocase:Omitted','Required trace truncated.');
    observer.assertComplete();
    timerStatus=simulation.autonomousReceiverTimingSummary();
    assert(timerStatus.Omitted==0,'autocase:Omitted','Relative timer evidence was truncated.');
    randomStatus=simulation.autonomousRandomSummary();
    assert(randomStatus.native_tape_exhausted,'autocase:UnusedNativeDraws', ...
        'Simulation reached its endpoint with unused native random inputs or transmissions.');
    assert(isempty(randomStatus.first_context_mismatch) && randomStatus.strict_context_matched, ...
        'node8:ContextDivergence','Native random or TX contexts differed.');
    assert(isempty(randomStatus.first_time_difference),'node8:TimingDivergence', ...
        'An endogenous random-request timestamp differed; exact evidence is retained.');
    assert(height(result.ApplicationAdmissionTrace)==270000, ...
        'node8:OfferPopulation','Expected all 270,000 application opportunities before 1200 seconds.');
    assert(height(result.ApplicationAdmissionStatistics)==6 && ...
        isequal(sort(result.ApplicationAdmissionStatistics.SourceId(:))',[2 3 4 5 7 8]) && ...
        all(result.ApplicationAdmissionStatistics.Attempts==45000), ...
        'node8:SourceOffers','Expected 45,000 opportunities for each of six sources.');
    item.diagnostic_status='completed_context_checks'; item.completed=true;
catch caught
    item.error_identifier=caught.identifier; item.error_message=caught.message;
    if any(strcmp(caught.identifier,{'autocase:DrawContextDivergence','autocase:TxContextDivergence','autocase:UnusedNativeDraws','node8:ContextDivergence','node8:TimingDivergence','node8:TxTimingDivergence'}))
        item.diagnostic_status='context_divergence';
    else, item.diagnostic_status='unexpected_harness_error'; end
    ac.writeJson(fullfile(folder,'error.json'),errorDetails(caught));
    fprintf('%s stopped: %s\n',definition.name,caught.message);
    if exist('simulation','var')
        item.reached_time_s=simulation.Scheduler.Now;
        try
            partial=simulation.autonomousPartial(); exportRaw(partial,folder,definition.stop_seconds);
            ac.writeJson(fullfile(folder,'partial_statistics.json'),partial.Statistics);
        catch exportError
            ac.writeJson(fullfile(folder,'partial_export_error.json'),errorDetails(exportError));
        end
    end
end
try
    observed=observer.snapshot();
    writetable(observed.ServiceTrace,fullfile(folder,'service_trace.csv'));
    writetable(observed.LinkDecisionTrace,fullfile(folder,'link_decisions.csv'));
    writetable(observed.ActualFeedbackTrace,fullfile(folder,'actual_feedback.csv'));
    ac.writeJson(fullfile(folder,'observer_status.json'),observed.ServiceDiagnostics);
catch caught
    item.completed=false; ac.writeJson(fullfile(folder,'observer_export_error.json'),errorDetails(caught));
end
if exist('simulation','var')
    try
        ac.writeJson(fullfile(folder,'random_summary.json'),simulation.autonomousRandomSummary());
        simulation.autonomousClose();
    catch caught
        item.completed=false; ac.writeJson(fullfile(folder,'random_export_error.json'),errorDetails(caught));
    end
    try
        relative=simulation.autonomousReceiverTimingSummary();
        writetable(relative.Records,fullfile(folder,'receiver_timing.csv'));
        ac.writeJson(fullfile(folder,'receiver_timing_summary.json'),rmfield(relative,'Records'));
        assert(relative.Omitted==0,'autocase:Omitted','Relative timer evidence was truncated.');
    catch caught
        item.completed=false; ac.writeJson(fullfile(folder,'receiver_timing_export_error.json'),errorDetails(caught));
    end
end
try
    transport=timing.snapshot();
    writetable(transport.Records,fullfile(folder,'transport_timing.csv'));
    ac.writeJson(fullfile(folder,'transport_timing_summary.json'),rmfield(transport,'Records'));
catch caught
    item.completed=false; ac.writeJson(fullfile(folder,'transport_export_error.json'),errorDetails(caught));
end
ac.Trace.close(); item.wall_seconds=toc(started);
fprintf('%s endpoint %.9g s, completed=%d, elapsed %.1f min.\n', ...
    definition.name,item.reached_time_s,item.completed,item.wall_seconds/60);
end

function exportRaw(result,folder,stopSeconds)
map={'ProtocolTrace','protocol_trace.csv';'PhyTrace','phy_trace.csv'; ...
    'ApplicationAdmissionTrace','application_admission_trace.csv'};
boundary=struct('file',{},'strict_prefix_rows',{},'exact_endpoint_rows',{});
for k=1:size(map,1)
    raw=result.(map{k,1}); value=raw(raw.TimeSeconds<stopSeconds,:);
    endpoint=raw(raw.TimeSeconds==stopSeconds,:);
    writetable(value,fullfile(folder,map{k,2}));
    if ~isempty(endpoint), writetable(endpoint,fullfile(folder,['endpoint_' map{k,2}])); end
    boundary(end+1)=struct('file',map{k,2},'strict_prefix_rows',height(value), ...
        'exact_endpoint_rows',height(endpoint)); %#ok<AGROW>
end
ac.writeJson(fullfile(folder,'endpoint_contract.json'),struct( ...
    'native_prefix_stop_ns_exclusive',stopSeconds*1e9, ...
    'matlab_scheduler_processes_callbacks_at_endpoint',true, ...
    'raw_exports_use_strictly_before_endpoint',true,'endpoint_rows_saved_separately',true, ...
    'random_requests_and_semantic_trace_are_not_time_filtered',true,'rows',boundary, ...
    'completion_does_not_establish_exact_timing_parity',true));
end

function exportFinal(result,folder)
map={'ApplicationAdmissionStatistics','application_admission_statistics.csv'; ...
    'NodeStatistics','node_statistics.csv';'NodeMacStatistics','node_mac_statistics.csv'; ...
    'NodeHopStatistics','node_hop_statistics.csv';'NodeNwkStatistics','node_nwk_statistics.csv'; ...
    'Routes','routes.csv';'Neighbors','neighbors.csv'};
for k=1:size(map,1), writetable(result.(map{k,1}),fullfile(folder,map{k,2})); end
ac.writeJson(fullfile(folder,'statistics.json'),result.Statistics);
ac.writeJson(fullfile(folder,'metadata.json'),result.Metadata);
ac.writeJson(fullfile(folder,'accounting_scope.json'),struct( ...
    'admitted',result.Statistics.Generated,'unique_delivered',result.Statistics.Received, ...
    'unfinished_or_unresolved',result.Statistics.Generated-result.Statistics.Received, ...
    'selected_data_retry_policy',result.Config.Hop.DataQueuedRetryPolicy, ...
    'raw_dropped_is_provisional',strcmp(result.Config.Hop.DataQueuedRetryPolicy,'native-provisional'), ...
    'raw_pending_is_not_a_complete_live_copy_ledger',true, ...
    'copy_liveness_partition','Not classified by aggregate counters; use terminal-copy evidence and raw event trace', ...
    'raw_dropped',result.Statistics.Dropped,'raw_pending',result.Statistics.Pending, ...
    'late_deliveries',result.Statistics.LateDeliveries, ...
    'late_custody_recoveries',result.Statistics.LateCustodyRecoveries, ...
    'hop_owner_failure_is_not_final_application_loss',true,'full_network_acceptance_claim',false));
end

function output=txTimingGate(actual,fixture,folder,stopSeconds)
expected=ac.Fixture.readTx(fullfile(fixture,'tx_signatures.csv'));
actual=actual(strcmp(actual.Event,'tx_start') & actual.TimeSeconds<stopSeconds,{'TimeSeconds','NodeId'});
expected=expected(expected.child_index==0 & expected.time_ns<stopSeconds*1e9,:);
[rows,output]=compareTxTimes(actual,expected);
writetable(rows,fullfile(folder,'tx_timing_comparison.csv'));
ac.writeJson(fullfile(folder,'tx_timing_summary.json'),output);
if ~output.passed
    ac.writeJson(fullfile(folder,'first_tx_timing_difference.json'),output.first_mismatch);
end
end

function [rows,output]=compareTxTimes(actual,expected)
% Physical TX only: packet IDs cannot identify aggregated DATA/control frames.
% Both tables retain their original event order. Source ordinals are local.
nActual=height(actual); nExpected=height(expected); n=max(nActual,nExpected);
actualNode=NaN(n,1); actualOrdinal=NaN(n,1); actualTimeNs=NaN(n,1);
expectedNode=NaN(n,1); expectedOrdinal=NaN(n,1); expectedTimeNs=NaN(n,1);
expectedTxId=NaN(n,1); sourceCounts=containers.Map('KeyType','double','ValueType','double');
for k=1:nActual
    node=double(actual.NodeId(k)); ordinal=1;
    if isKey(sourceCounts,node), ordinal=sourceCounts(node)+1; end
    sourceCounts(node)=ordinal;
    actualNode(k)=node; actualOrdinal(k)=ordinal;
    actualTimeNs(k)=round(double(actual.TimeSeconds(k))*1e9);
end
expectedNode(1:nExpected)=double(expected.source);
expectedOrdinal(1:nExpected)=double(expected.source_tx_ordinal);
expectedTimeNs(1:nExpected)=double(expected.time_ns);
expectedTxId(1:nExpected)=double(expected.tx_id);
identityMatched=actualNode==expectedNode & actualOrdinal==expectedOrdinal;
timeMatched=actualTimeNs==expectedTimeNs;
matched=identityMatched & timeMatched;
rows=table((1:n)',expectedTxId,actualNode,expectedNode,actualOrdinal,expectedOrdinal, ...
    actualTimeNs,expectedTimeNs,identityMatched,timeMatched,matched, ...
    'VariableNames',{'EventIndex','NativeTxId','ActualNodeId','NativeNodeId', ...
    'ActualSourceOrdinal','NativeSourceOrdinal','ActualTimeNs','NativeTimeNs', ...
    'IdentityAndOrderMatched','TimeMatched','Matched'});
first=find(~matched,1); mismatch=struct();
if ~isempty(first), mismatch=table2struct(rows(first,:)); end
output=struct('schema','csr-node8-physical-tx-timing-v1', ...
    'passed',nActual==nExpected && all(matched),'actual_tx_count',nActual, ...
    'native_tx_count',nExpected,'counts_equal',nActual==nExpected, ...
    'global_identity_and_order_match',all(identityMatched), ...
    'integer_nanosecond_times_match',all(timeMatched),'first_mismatch',mismatch, ...
    'comparison','Original physical TX order; source plus per-source ordinal; integer nanoseconds', ...
    'time_tolerance_ns',0,'packet_ids_used_for_pairing',false);
end

function output=txTimingPreflight(root,folder)
if ~isfolder(folder), mkdir(folder); end
actual=readtable(fullfile(root,'review','accepted400_tx_starts.csv'));
expected=ac.Fixture.readTx(fullfile(root,'ref','native132_400','tx_signatures.csv'));
expected=expected(expected.child_index==0,:);
[baselineRows,baseline]=compareTxTimes(actual,expected);
writetable(baselineRows,fullfile(folder,'accepted400_comparison.csv'));
ac.writeJson(fullfile(folder,'accepted400_summary.json'),baseline);
assert(baseline.passed && height(actual)>2,'node8:TxTimingPreflight', ...
    'The accepted 400-second physical TX population failed comparison.');
names={'one_nanosecond_change','missing_transmission','reordered_transmissions', ...
    'changed_source','duplicate_transmission'};
checks=struct('mutation',{},'rejected',{},'first_mismatch',{});
for k=1:numel(names)
    changed=actual;
    switch k
        case 1, changed.TimeSeconds(1)=changed.TimeSeconds(1)+1e-9;
        case 2, changed(end,:)=[];
        case 3
            other=find(changed.NodeId~=changed.NodeId(1),1);
            assert(~isempty(other),'node8:TxTimingPreflight','Need two native TX sources for order mutation.');
            changed([1 other],:)=changed([other 1],:);
        case 4, changed.NodeId(1)=99;
        case 5, changed=[changed; changed(end,:)];
    end
    [rows,comparison]=compareTxTimes(changed,expected);
    writetable(rows,fullfile(folder,[names{k} '_comparison.csv']));
    ac.writeJson(fullfile(folder,[names{k} '_summary.json']),comparison);
    assert(~comparison.passed && ~isempty(fieldnames(comparison.first_mismatch)), ...
        'node8:TxTimingPreflight','Mutation was not rejected with retained first-difference evidence.');
    if k==1, assert(~comparison.integer_nanosecond_times_match,'node8:TxTimingPreflight','Time mutation was missed.'); end
    if k==2, assert(~comparison.counts_equal,'node8:TxTimingPreflight','Count mutation was missed.'); end
    if k==4, assert(~comparison.global_identity_and_order_match,'node8:TxTimingPreflight','Source mutation was missed.'); end
    if k==5, assert(~comparison.counts_equal,'node8:TxTimingPreflight','Duplicate mutation was missed.'); end
    if k==3, assert(~comparison.global_identity_and_order_match,'node8:TxTimingPreflight','Order mutation was missed.'); end
    checks(end+1)=struct('mutation',names{k},'rejected',true, ...
        'first_mismatch',comparison.first_mismatch); %#ok<AGROW>
end
output=struct('schema','csr-node8-tx-timing-preflight-v1','passed',true, ...
    'accepted400_tx_count',baseline.actual_tx_count,'baseline',baseline, ...
    'mutation_checks',checks,'network_simulation_executed',false);
ac.writeJson(fullfile(folder,'preflight.json'),output);
end
function value=errorDetails(caught)
value=struct('identifier',caught.identifier,'message',caught.message,'stack',caught.stack);
end

function details=verifyHistoricalReference(root,runtime)
% Revalidate archived evidence integrity only. Source bytes have changed;
% this is not an accepted natural result for the repaired candidate.
folder=fullfile(root,'ref','accepted');
proof=jsondecode(fileread(fullfile(folder,'reuse_proof.json')));
assert(strcmp(proof.schema,'csr-accepted-natural-reuse-v1') && ...
    proof.static_natural_source_identity_proven,'autocase:ReuseProof','Invalid historical natural-source proof.');
verifyFiles(folder,proof.accepted_files);
runtimeMatches=strcmp(runtime.version,proof.accepted_runtime.version) && ...
    strcmp(runtime.release,proof.accepted_runtime.release) && strcmp(runtime.computer,proof.accepted_runtime.computer);
assert(runtimeMatches,'node8:CandidateRuntime', ...
    'This candidate kit targets MATLAB R2025a 25.1.0.2943329 on Windows; use that runtime.');
accepted=jsondecode(fileread(fullfile(folder,'case_summary.json')));
oldGate=jsondecode(fileread(fullfile(folder,'prefix_gate.json')));
assert(accepted.completed && accepted.natural_prefix_passed && accepted.reached_time_s==330 && ...
    oldGate.passed && all([oldGate.checks.passed]),'autocase:ReuseAcceptance','Historical natural evidence was not accepted.');
gate=comparePrefix(folder,fullfile(root,'ref','matlab'));
assert(gate.passed,'autocase:ReusePrefix','Historical tables no longer match the original exact prefix.');
details=struct('schema','csr-relay-custody-historical-reference-v1', ...
    'status','historical_reference_only','historical_integrity_passed',true, ...
    'accepted_runtime',proof.accepted_runtime,'current_runtime',runtime, ...
    'runtime_matches',runtimeMatches,'historical_prefix_gate',gate, ...
    'historical_source_proof_current_model_validation',false, ...
    'natural_result_reused_as_current_acceptance',false, ...
    'fresh_natural_simulation_executed',false, ...
    'reason','Relay-copy and unique-accounting behavior changed; prior natural evidence is reference only');
fprintf('Historical 330-s tables verified as reference only; this changed model has no reused natural acceptance.\n');
end

function output=comparePrefix(folder,reference)
files={'protocol_trace.csv','phy_trace.csv','application_admission_trace.csv'};
checks=struct('file',{},'actual_rows',{},'reference_rows',{},'passed',{},'first_row',{},'first_column',{});
for k=1:numel(files)
    wantedFile=fullfile(reference,files{k}); actualFile=fullfile(folder,files{k});
    opts=detectImportOptions(wantedFile,'TextType','string');
    expected=readtable(wantedFile,opts); actual=readtable(actualFile,opts);
    item=struct('file',files{k},'actual_rows',height(actual),'reference_rows',height(expected), ...
        'passed',isequaln(actual,expected),'first_row',NaN,'first_column','');
    if ~item.passed
        for row=1:min(height(actual),height(expected))
            for col=1:width(expected)
                if ~isequaln(actual{row,col},expected{row,col})
                    item.first_row=row; item.first_column=expected.Properties.VariableNames{col}; break
                end
            end
            if ~isnan(item.first_row), break; end
        end
    end
    checks(end+1)=item; %#ok<AGROW>
end
output=struct('schema','csr-autonomous-natural-prefix-v1','passed',all([checks.passed]), ...
    'window','0 <= time < 330','comparison','Exact table values after identical CSV import options; no timing tolerance', ...
    'reference','Corrected owner 6,000-second seed-132 return, R2025a', 'checks',checks);
end

function resolved=bindSource(root,files)
resolved=struct('name',{},'path',{},'sha256',{});
for k=1:numel(files)
    relative=char(files(k).path);
    if ~endsWith(relative,'.m'), continue; end
    % Archived source is hash-covered but must never resolve as active code.
    active=startsWith(relative,'model/') || startsWith(relative,'+ac/') || ~contains(relative,'/');
    if ~active, continue; end
    % Hash verification covers this optional branch, but resolving its
    % class definitions may load an unavailable wnet.Node on R2025a.
    if startsWith(relative,'model/+csr/+sim/+native/'), continue; end
    parts=strsplit(relative,'/');
    if strcmp(parts{1},'model'), parts=parts(2:end); end
    if any(strcmp(parts,'private')), continue; end
    for j=1:numel(parts), parts{j}=erase(parts{j},'+'); end
    parts{end}=parts{end}(1:end-2); name=strjoin(parts,'.');
    found=which(name); expected=fullfile(root,strrep(relative,'/',filesep));
    assert(~isempty(found) && strcmp(char(java.io.File(found).getCanonicalPath()), ...
        char(java.io.File(expected).getCanonicalPath())), ...
        'autocase:SourceBinding','Wrong source resolves for %s. Restart MATLAB in this kit.',name);
    resolved(end+1)=struct('name',name,'path',found,'sha256',hashFile(found)); %#ok<AGROW>
end
end

function verifyFiles(root,files)
for k=1:numel(files)
    p=char(files(k).path);
    assert(isempty(regexp(p,'(^/|^[A-Za-z]:|(^|[\\/])\.\.([\\/]|$))','once')), ...
        'autocase:ManifestPath','Unsafe manifest path.');
    assert(strcmp(hashFile(fullfile(root,strrep(p,'/',filesep))),files(k).sha256), ...
        'autocase:SourceChanged','Missing or changed kit file: %s.',p);
end
end
function value=hashFile(file)
fid=fopen(file,'rb'); assert(fid>=0,'autocase:HashOpen','Cannot read %s.',file);
cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
md=java.security.MessageDigest.getInstance('SHA-256');
while ~feof(fid)
    bytes=fread(fid,1048576,'*uint8');
    if ~isempty(bytes), md.update(typecast(bytes,'int8')); end
end
value=lower(reshape(dec2hex(typecast(md.digest(),'uint8'),2).',1,[]));
end
function folder=uniqueFolder(root,stem)
folder=fullfile(root,stem); n=1;
while isfolder(folder) || isfile(folder) || isfile([folder '.zip']), n=n+1; folder=fullfile(root,sprintf('%s_%02d',stem,n)); end
[ok,message]=mkdir(folder); assert(ok,'autocase:Mkdir','%s',message);
end
function restore(oldPath,oldFolder)
path(oldPath); if isfolder(oldFolder), cd(oldFolder); end
end
