classdef AccountingFixture < handle
    %ACCOUNTINGFIXTURE Public-boundary driver for real TerminalSimulation.
    % The recorder is passive. Scheduled driver methods supply decoded HOP
    % receives and sent indications; this is not an RF or MAC timing test.
    properties (SetAccess=private)
        Simulation
        Folder
        Mode
        Checks = struct('label',{},'passed',{},'actual',{},'expected',{})
        Checkpoints = struct('label',{},'value',{})
        Result = []
    end
    properties (Access=private)
        File = -1
        Order = 0
        Admitted = {}
        Retained = {}
        DataEnqueues = 0
        DataRemovals = 0
        AllRemovals = 0
        FinalChecksCompleted = false
    end
    methods
        function obj=AccountingFixture(config,folder,mode)
            obj.Folder=folder; obj.Mode=mode;
            if ~isfolder(folder), mkdir(folder); end
            assert(isempty(ac.Trace.holder()),'batchcase:AccountingTrace','Accounting fixture needs an inactive passive trace sink.');
            config=fixtureConfig(config,mode);
            ac.writeJson(fullfile(folder,'configuration.json'),config);
            try
                obj.Simulation=ac.TerminalSimulation(config,[],[], ...
                    struct('Mode','natural','Fixture','','Folder',folder));
                obj.File=fopen(fullfile(folder,'ordered_events.jsonl'),'w');
                assert(obj.File>=0,'batchcase:AccountingFile','Cannot open accounting trace.');
            catch caught
                try, obj.close(); catch, end
                rethrow(caught)
            end
            % Publish the fully constructed recorder only after setup passes.
            % Constructor failure cannot leave a deleted object in Trace.
            ac.Trace.holder('set',obj);
        end
        function record(obj,time,kind,node,details)
            % Called by ac.Trace; no scheduler, protocol or RNG mutation.
            obj.Order=obj.Order+1;
            row=struct('observation_order',obj.Order,'time_s',time, ...
                'kind',kind,'node',node,'details',details);
            assert(fprintf(obj.File,'%s\n',jsonencode(row))>0,'batchcase:AccountingFile','Cannot write accounting trace.');
            if strcmp(kind,'protocol') && strcmp(details.event,'network_enqueue')
                obj.Retained{end+1}=struct('node',node,'app',details.frame);
            end
            if strcmp(kind,'protocol') && isfield(details,'frame') && ...
                    isfield(details.frame,'Kind') && strcmp(details.frame.Kind,'DATA')
                if strcmp(details.event,'hop_admit')
                    obj.Admitted{end+1}=struct('node',node,'frame',details.frame);
                elseif strcmp(details.event,'mac_enqueue') && node==1
                    obj.DataEnqueues=obj.DataEnqueues+1;
                end
            end
        end
        function execute(obj)
            clock=obj.Simulation.Scheduler;
            if strcmp(obj.Mode,'siblings')
                obj.executeSiblings(); return
            end
            clock.scheduleAt(0,@()obj.establishPublicRoutes());
            clock.scheduleAt(1,@()obj.sendInitial());
            if strcmp(obj.Mode,'relay')
                clock.scheduleAt(4,@()obj.addOlderOwner());
            end
            clock.scheduleAt(6,@()obj.scanTrigger(6001));
            clock.scheduleAt(8.25,@()obj.retiredCheckpoint());
            if ~strcmp(obj.Mode,'cutoff')
                clock.scheduleAt(8.5,@()obj.firstLateReceive());
                clock.scheduleAt(8.6,@()obj.duplicateReceive(false));
                clock.scheduleAt(8.7,@()obj.duplicateReceive(true));
                clock.scheduleAt(8.8,@()obj.recoveredCheckpoint());
                if strcmp(obj.Mode,'relay')
                    clock.scheduleAt(9,@()obj.scanTrigger(6002));
                    clock.scheduleAt(11.25,@()obj.staleCheckpoint());
                    clock.scheduleAt(12,@()obj.finalRelayReceive());
                    clock.scheduleAt(12.1,@()obj.finalRelayDuplicate());
                end
                clock.scheduleAt(12.3,@()obj.unmatchedSent());
            end
            obj.Result=obj.Simulation.run();
            obj.saveResult();
            obj.finalChecks();
            obj.FinalChecksCompleted=true;
            obj.persist();
        end
        function value=summary(obj)
            value=struct('checks',obj.Checks,'checkpoints',obj.Checkpoints, ...
                'execution_complete',~isempty(obj.Result), ...
                'final_checks_complete',obj.FinalChecksCompleted, ...
                'passed',~isempty(obj.Result) && obj.FinalChecksCompleted && ~isempty(obj.Checks) && all([obj.Checks.passed]), ...
                'scope','Real TerminalSimulation records/counters and NWK/HOP/MAC objects; scripted public sent/decoded-receive inputs and, in siblings, public NWK release/terminal boundaries; no RF propagation or actual MAC transmission');
        end
        function persist(obj)
            ac.writeJson(fullfile(obj.Folder,'accounting_case.json'),obj.summary());
            if ~isempty(obj.Simulation)
                partial=obj.Simulation.autonomousPartial();
                ac.writeJson(fullfile(obj.Folder,'partial_statistics.json'),partial.Statistics);
                writetable(partial.ProtocolTrace,fullfile(obj.Folder,'protocol_trace.csv'));
            end
        end
        function close(obj)
            if obj.File>=0, fclose(obj.File); obj.File=-1; end
            if ~isempty(obj.Simulation), obj.Simulation.autonomousClose(); end
        end
        function delete(obj), obj.close(); end
    end
    methods (Access=private)
        function executeSiblings(obj)
            clock=obj.Simulation.Scheduler;
            clock.scheduleAt(0,@()obj.establishPublicRoutes());
            clock.scheduleAt(1,@()obj.siblingReceive(0));
            clock.scheduleAt(1.1,@()obj.siblingReceive(100));
            clock.scheduleAt(1.2,@()obj.siblingCheckpoint('two_retained'));
            clock.scheduleAt(2,@()obj.siblingFailure(1));
            clock.scheduleAt(2.1,@()obj.siblingCheckpoint('one_failed'));
            clock.scheduleAt(2.2,@()obj.siblingFailure(1));
            clock.scheduleAt(2.3,@()obj.siblingCheckpoint('stale_failure'));
            clock.scheduleAt(2.5,@()obj.retainLowerHopSibling());
            clock.scheduleAt(3,@()obj.siblingFailure(2));
            clock.scheduleAt(3.1,@()obj.siblingCheckpoint('lower_hop_survives'));
            clock.scheduleAt(3.2,@()obj.failLowerHopSibling());
            clock.scheduleAt(3.3,@()obj.siblingCheckpoint('last_failed'));
            clock.scheduleAt(4,@()obj.siblingReceive(101));
            clock.scheduleAt(4.1,@()obj.siblingFailure(1));
            clock.scheduleAt(4.2,@()obj.siblingCheckpoint('same_hop_recovered'));
            clock.scheduleAt(5,@()obj.siblingDelivery());
            clock.scheduleAt(5.1,@()obj.siblingDelivery());
            clock.scheduleAt(5.2,@()obj.siblingReceive(102));
            clock.scheduleAt(5.3,@()obj.siblingFailure(3));
            clock.scheduleAt(5.4,@()obj.siblingFailure(4));
            clock.scheduleAt(5.5,@()obj.siblingCheckpoint('delivered_once'));
            obj.Result=obj.Simulation.run(); obj.saveResult();
            stats=obj.Result.Statistics;
            rx=obj.Result.ProtocolTrace(strcmp(obj.Result.ProtocolTrace.Event,'app_receive'),:);
            obj.expect('sibling integration final conservation and unique latency', ...
                stats.Generated==1 && stats.Received==1 && stats.Dropped==0 && stats.Pending==0 && ...
                stats.ApplicationBytesReceived==185 && abs(stats.LatencySumSeconds-4.5)<1e-12 && ...
                stats.RelayAccepted==4 && stats.LateCustodyRecoveries==1 && height(rx)==1 && ...
                stats.OmittedTraceRecords==0 && stats.OmittedPhyTraceRecords==0 && ...
                stats.OmittedApplicationAdmissionRecords==0, ...
                stats,struct('generated',1,'received',1,'dropped',0,'pending',0, ...
                'bytes',185,'latency_sum_s',4.5,'relay_occurrences',4,'recoveries',1,'receive_rows',1));
            obj.FinalChecksCompleted=true; obj.persist();
        end
        function siblingReceive(obj,offset)
            frame=obj.original(); frame.Sequence=uint16(mod(double(frame.Sequence)+offset,65536));
            obj.Simulation.Hops{2}.receive(frame);
            % Retire only the registered source NWK copy. No lower-layer
            % completion is synthesized; HOP release behavior is tested by
            % the independent custody component suite.
            if offset==0, obj.Simulation.Networks{1}.releaseFromHop(frame.App,'fixture_source_release'); end
            obj.stimulus('scripted_sibling_decoded_receive',struct('sequence_offset',offset, ...
                'physical_reception',false));
        end
        function retainLowerHopSibling(obj)
            original=obj.original();
            accepted=obj.Simulation.Networks{1}.sendApplication(original.App);
            obj.expect('scripted lower-hop sibling retained at source NWK',accepted,accepted,true);
            obj.stimulus('scripted_source_nwk_retain_same_application',struct( ...
                'purpose','Adversarial accounting case; not an autonomous generator action'));
        end
        function failLowerHopSibling(obj)
            found=find(cellfun(@(x)x.node==1 && x.app.Id==uint64(1),obj.Retained));
            assert(numel(found)==2,'batchcase:AccountingSibling','Expected two source custody occurrences.');
            app=obj.Retained{found(2)}.app;
            obj.Simulation.Networks{1}.terminal(app,false,'fixture_copy_failure');
            obj.stimulus('scripted_last_lower_hop_terminal_failure',struct('custody_id',app.NwkCustodyId));
        end
        function app=retainedRelay(obj,ordinal)
            found=find(cellfun(@(x)x.node==2 && x.app.Id==uint64(1),obj.Retained));
            assert(numel(found)>=ordinal,'batchcase:AccountingSibling','Missing retained relay occurrence.');
            app=obj.Retained{found(ordinal)}.app;
        end
        function siblingFailure(obj,ordinal)
            app=obj.retainedRelay(ordinal);
            obj.Simulation.Networks{2}.terminal(app,false,'fixture_copy_failure');
            obj.stimulus('scripted_public_nwk_terminal_failure',struct('occurrence',ordinal, ...
                'custody_id',app.NwkCustodyId,'physical_copy_failure_claim',false));
        end
        function siblingDelivery(obj)
            app=obj.retainedRelay(3);
            [accepted,reason]=obj.Simulation.Networks{3}.receiveData(app,2);
            obj.expect('public final NWK delivery is accepted',accepted, ...
                struct('accepted',accepted,'reason',reason),struct('accepted',true));
        end
        function siblingCheckpoint(obj,label)
            partial=obj.Simulation.autonomousPartial(); stats=partial.Statistics;
            original=obj.original(); app=original.App;
            counts=cellfun(@(nwk)nwk.custodyCount(app),obj.Simulation.Networks);
            expectedCount=1; expectedDrop=0; expectedReceived=0; expectedRelay=2; expectedRecovery=0;
            switch label
                case 'two_retained', expectedCount=2;
                case 'last_failed', expectedCount=0; expectedDrop=1;
                case 'same_hop_recovered', expectedRelay=3; expectedRecovery=1;
                case 'delivered_once'
                    expectedCount=0; expectedReceived=1; expectedRelay=4; expectedRecovery=1;
            end
            obj.expect(['sibling accounting ' label], ...
                sum(counts)==expectedCount && stats.Generated==1 && stats.Dropped==expectedDrop && ...
                stats.Received==expectedReceived && stats.RelayAccepted==expectedRelay && ...
                stats.LateCustodyRecoveries==expectedRecovery && ...
                all(cellfun(@(node)node.Dropped,obj.Simulation.Nodes)>=0) && ...
                sum(cellfun(@(node)node.Dropped,obj.Simulation.Nodes))==expectedDrop, ...
                struct('custody_counts',counts,'statistics',stats), ...
                struct('registered_copies',expectedCount,'dropped',expectedDrop, ...
                'received',expectedReceived,'relay_occurrences',expectedRelay,'recoveries',expectedRecovery));
            obj.Checkpoints(end+1)=struct('label',label,'value', ...
                struct('time_s',obj.Simulation.Scheduler.Now,'custody_counts',counts,'statistics',stats));
            obj.persist();
        end
        function establishPublicRoutes(obj)
            sim=obj.Simulation;
            sim.Networks{1}.observe(2,struct()); sim.Networks{2}.observe(1,struct());
            if any(strcmp(obj.Mode,{'relay','siblings'}))
                sim.Networks{2}.observe(3,struct()); sim.Networks{3}.observe(2,struct());
                route=struct('Operation','UPDATE','NodeId',3,'Capability',2,'HopCount',1,'Cost',10,'Path',3);
                sections=csr.nwk.RoutingCodec.sections(csr.nwk.RoutingCodec.encodeRecords({route}),uint32(17));
                obj.expect('one public relay route section',numel(sections)==1,numel(sections),1);
                sim.Networks{1}.receiveControl(struct('Type','ROUTING','Payload',struct('Bytes',sections{1})),2);
            end
            obj.stimulus('public_nwk_observation_and_routing',struct('admission_enabled',false));
        end
        function frame=original(obj)
            found=find(cellfun(@(x)x.node==1 && x.frame.App.Id==uint64(1),obj.Admitted),1);
            assert(~isempty(found),'batchcase:AccountingAdmission','Generated application did not enter source HOP.');
            frame=obj.Admitted{found}.frame;
        end
        function sendInitial(obj)
            frame=obj.original(); obj.removeForSent(frame);
            obj.Simulation.Hops{1}.notifySent(frame);
            obj.stimulus('scripted_initial_sent',struct('frame',frame,'physical_transmission',false));
        end
        function addOlderOwner(obj)
            original=obj.original(); options=obj.Simulation.Config.Radio;
            options.TxPowerDbm=obj.Simulation.Config.Nodes(1).RadioProfile.TxPowerDbm;
            % A different peer has an independent initially empty HOP window.
            % Same-peer admission would correctly block behind the first owner.
            [okay,frame]=obj.Simulation.Hops{1}.send(original.App,3,options);
            obj.expect('admit independent older source owner for stale callback',okay,okay,true);
            obj.removeForSent(frame);
            obj.Simulation.Hops{1}.notifySent(frame);
            obj.stimulus('scripted_second_owner_sent',struct('frame',frame, ...
                'purpose','Creates an explicit stale completion after newer relay custody; not an autonomous traffic claim'));
        end
        function removeForSent(obj,frame)
            removed=obj.Simulation.Macs{1}.cancelData(frame.DestinationId,frame.Sequence);
            obj.DataRemovals=obj.DataRemovals+removed; obj.AllRemovals=obj.AllRemovals+removed;
            obj.expect('public lower-layer dequeue surrogate removes one initial DATA',removed==1,removed,1);
        end
        function scanTrigger(obj,id)
            control=struct('Id',uint64(id),'Type','KEY_UPDATE','Payload',struct('Generation',0),'WirePayloadBytes',16);
            radio=obj.Simulation.Config.Radio; radio.TxPowerDbm=obj.Simulation.Config.Nodes(1).RadioProfile.TxPowerDbm;
            [okay,frame]=obj.Simulation.Hops{1}.sendControl(control,2,radio);
            obj.expect('independent control scan-trigger admission',okay,okay,true);
            removed=obj.Simulation.Macs{1}.cancel(2,frame.Sequence);
            obj.AllRemovals=obj.AllRemovals+removed;
            obj.expect('remove control before scripted sent indication',removed==1,removed,1);
            obj.Simulation.Hops{1}.notifySent(frame);
            obj.stimulus('scripted_control_sent',struct('frame',frame,'physical_transmission',false));
        end
        function retiredCheckpoint(obj)
            v=obj.capture('retired_owner_before_late_reception');
            pending=double(strcmp(obj.Mode,'relay'));
            copies=1+pending;
            obj.expect('owner failure is provisional while queued copies survive', ...
                v.statistics.Generated==1 && v.statistics.Received==0 && v.statistics.Dropped==1 && ...
                v.source_hop.Failed==1 && v.source_hop.PendingData==pending && ...
                v.source_data_copies==copies && strcmp(v.ledger.classification,'unresolved') && ...
                v.statistics.PhysicalTransmissions==0 && v.node_dropped(1)==1, ...
                v,struct('generated',1,'received',0,'raw_dropped',1,'source_failed',1, ...
                'source_pending_owner',pending,'live_data_copies',copies,'fate','unresolved','physical_tx',0));
        end
        function firstLateReceive(obj)
            obj.Simulation.Hops{2}.receive(obj.original());
            obj.stimulus('decoded_late_DATA_at_node2',struct('physical_reception',false));
        end
        function duplicateReceive(obj,freshSequence)
            frame=obj.original();
            if freshSequence, frame.Sequence=uint16(mod(double(frame.Sequence)+100,65536)); end
            obj.Simulation.Hops{2}.receive(frame);
            obj.stimulus('decoded_duplicate_DATA_at_node2',struct('fresh_hop_sequence',freshSequence));
        end
        function recoveredCheckpoint(obj)
            v=obj.capture('late_reception_and_duplicates'); relay=strcmp(obj.Mode,'relay');
            obj.expect('late reception reverses only its provisional application loss', ...
                v.statistics.Dropped==0 && all(v.node_dropped==0) && ...
                v.statistics.Received==double(~relay) && ...
                v.statistics.LateDeliveries==double(~relay) && ...
                v.statistics.LateCustodyRecoveries==double(relay) && ...
                v.statistics.RelayAccepted==2*double(relay),v, ...
                struct('dropped',0,'node_dropped',0,'received',double(~relay), ...
                'late_deliveries',double(~relay),'late_custody_recoveries',double(relay),'relay_accepted',2*double(relay)));
            obj.expect('HOP suppresses its duplicate; only final NWK deduplicates applications', ...
                obj.Simulation.Hops{2}.stats().Duplicates==1 && ...
                obj.Simulation.Networks{2}.stats().DuplicateApplications==double(~relay), ...
                struct('hop',obj.Simulation.Hops{2}.stats(),'nwk',obj.Simulation.Networks{2}.stats()), ...
                struct('hop_duplicates',1,'nwk_duplicates',double(~relay)));
            if relay
                frame=obj.relayFrame();
                obj.expect('fresh relay preserves advanced custody and traversal', ...
                    frame.App.HopCount==1 && isequal(frame.App.Traversal,[1 2]), ...
                    frame.App,struct('HopCount',1,'Traversal',[1 2]));
            end
        end
        function staleCheckpoint(obj)
            v=obj.capture('second_source_owner_failed_after_recovery');
            obj.expect('stale source failure cannot reclaim newer custody or final delivery', ...
                v.source_hop.Failed==2 && v.source_hop.PendingData==0 && ...
                v.statistics.UnconfirmedHopTransfers==1 && v.statistics.Dropped==0 && all(v.node_dropped==0), ...
                v,struct('source_failed',2,'source_pending',0,'unconfirmed',1,'dropped',0));
        end
        function frame=relayFrame(obj)
            found=find(cellfun(@(x)x.node==2 && x.frame.App.Id==uint64(1),obj.Admitted),1);
            assert(~isempty(found),'batchcase:AccountingRelay','Late relay custody was not submitted to HOP.');
            frame=obj.Admitted{found}.frame;
        end
        function finalRelayReceive(obj)
            obj.Simulation.Hops{3}.receive(obj.relayFrame());
            obj.stimulus('decoded_relay_DATA_at_final_sink',struct('physical_reception',false));
        end
        function finalRelayDuplicate(obj)
            obj.Simulation.Hops{3}.receive(obj.relayFrame());
            obj.stimulus('decoded_duplicate_relay_DATA_at_final_sink',struct());
        end
        function unmatchedSent(obj)
            before=obj.Simulation.Hops{1}.PendingDataCount;
            obj.Simulation.Hops{1}.notifySent(obj.original());
            obj.expect('late sent callback cannot resurrect retired HOP owner', ...
                before==0 && obj.Simulation.Hops{1}.PendingDataCount==0, ...
                struct('before',before,'after',obj.Simulation.Hops{1}.PendingDataCount),struct('before',0,'after',0));
        end
        function value=capture(obj,label)
            partial=obj.Simulation.autonomousPartial(); stats=partial.Statistics;
            dropped=cellfun(@(x)x.Dropped,obj.Simulation.Nodes);
            copies=obj.DataEnqueues-obj.DataRemovals;
            classification='unresolved'; if stats.Received==1, classification='delivered'; end
            rawPending=stats.Generated-stats.Received-stats.Dropped;
            value=struct('time_s',obj.Simulation.Scheduler.Now,'statistics',stats, ...
                'source_hop',obj.Simulation.Hops{1}.stats(),'source_mac',obj.Simulation.Macs{1}.snapshot(), ...
                'node_dropped',dropped,'source_data_copies',copies, ...
                'ledger',struct('source',1,'flow_index',1,'attempt_ordinal',1,'generated_s',0.5, ...
                'classification',classification,'raw_pending',rawPending,'raw_dropped',stats.Dropped, ...
                'delivered',stats.Received,'unresolved',double(stats.Received==0),'proven_lost',0, ...
                'basis','One generated app; public DATA enqueue observations minus exact scripted dequeue removals; no physical transmissions or feedback inputs'));
            obj.expect('copy mirror has no unobserved queue removal or physical send', ...
                obj.Simulation.Macs{1}.Counters.Canceled==obj.AllRemovals && stats.PhysicalTransmissions==0 && ...
                copies>=0 && copies<=obj.Simulation.Macs{1}.DataQueueCount, ...
                struct('canceled',obj.Simulation.Macs{1}.Counters.Canceled,'scripted_removals',obj.AllRemovals, ...
                'physical_tx',stats.PhysicalTransmissions,'copies',copies,'queue',obj.Simulation.Macs{1}.DataQueueCount), ...
                struct('all_removals_accounted',true,'physical_tx',0,'copies_within_queue',true));
            obj.Checkpoints(end+1)=struct('label',label,'value',value); obj.persist();
        end
        function finalChecks(obj)
            result=obj.Result; stats=result.Statistics;
            obj.expect('all diagnostic traces are complete',stats.OmittedTraceRecords==0 && ...
                stats.OmittedPhyTraceRecords==0 && stats.OmittedApplicationAdmissionRecords==0, ...
                struct('protocol_omitted',stats.OmittedTraceRecords,'phy_omitted',stats.OmittedPhyTraceRecords, ...
                'admission_omitted',stats.OmittedApplicationAdmissionRecords), ...
                struct('protocol_omitted',0,'phy_omitted',0,'admission_omitted',0));
            v=obj.capture('final'); cutoff=strcmp(obj.Mode,'cutoff'); relay=strcmp(obj.Mode,'relay');
            expectedReceived=double(~cutoff); expectedLatency=0;
            if ~cutoff, expectedLatency=8; if relay, expectedLatency=11.5; end, end
            obj.expect('generated/delivered/bytes/latency/raw conservation', ...
                stats.Generated==1 && stats.Received==expectedReceived && ...
                stats.Dropped==double(cutoff) && stats.Pending==0 && ...
                stats.ApplicationBytesReceived==185*expectedReceived && ...
                abs(stats.LatencySumSeconds-expectedLatency)<1e-12 && ...
                stats.Generated==stats.Received+stats.Dropped+stats.Pending, ...
                stats,struct('generated',1,'received',expectedReceived,'raw_dropped',double(cutoff), ...
                'raw_pending',0,'bytes',185*expectedReceived,'latency_sum_s',expectedLatency));
            reasons=fieldnames(stats.DropReasons);
            okay=isempty(reasons);
            if cutoff, okay=isequal(reasons,{'retry_exhausted'}) && stats.DropReasons.retry_exhausted==1; end
            obj.expect('provisional DropReasons reverse once',okay,stats.DropReasons,struct('retry_exhausted_count',double(cutoff)));
            obj.expect('no negative node or aggregate application counts', ...
                all(result.NodeStatistics.Dropped>=0) && stats.Dropped>=0 && stats.Pending>=0 && ...
                v.ledger.delivered+v.ledger.unresolved+v.ledger.proven_lost==1, ...
                v.ledger,struct('nonnegative',true,'unique_application_conservation',1));
            if ~cutoff
                rx=result.ProtocolTrace(strcmp(result.ProtocolTrace.Event,'app_receive'),:);
                obj.expect('one final sink callback with preserved hop count',height(rx)==1 && ...
                    rx.NodeId==2+double(relay) && rx.HopCount==1+double(relay), ...
                    table2struct(rx),struct('receive_rows',1,'sink',2+double(relay),'hop_count',1+double(relay)));
                obj.expect('integrated recovery branch totals',stats.LateDeliveries==double(~relay) && ...
                    stats.LateCustodyRecoveries==double(relay) && stats.RelayAccepted==2*double(relay), ...
                    struct('late_final',stats.LateDeliveries,'late_custody',stats.LateCustodyRecoveries,'relay',stats.RelayAccepted), ...
                    struct('late_final',double(~relay),'late_custody',double(relay),'relay',2*double(relay)));
                obj.expect('final receiver HOP duplicate path executed exactly once', ...
                    obj.Simulation.Hops{end}.stats().Duplicates==1, ...
                    obj.Simulation.Hops{end}.stats().Duplicates,1);
            end
        end
        function expect(obj,label,condition,actual,expected)
            obj.Checks(end+1)=struct('label',label,'passed',logical(condition),'actual',actual,'expected',expected);
            obj.persist();
            assert(condition,'batchcase:AccountingMismatch','%s. Actual=%s Expected=%s',label,jsonencode(actual),jsonencode(expected));
        end
        function stimulus(obj,name,details)
            obj.record(obj.Simulation.Scheduler.Now,'accounting_stimulus',0,struct('name',name,'details',details));
        end
        function saveResult(obj)
            ac.writeJson(fullfile(obj.Folder,'statistics.json'),obj.Result.Statistics);
            ac.writeJson(fullfile(obj.Folder,'metadata.json'),obj.Result.Metadata);
            for name={'NodeStatistics','NodeHopStatistics','NodeMacStatistics','NodeNwkStatistics','ProtocolTrace'}
                writetable(obj.Result.(name{1}),fullfile(obj.Folder,[name{1} '.csv']));
            end
        end
    end
end

function config=fixtureConfig(config,mode)
% Explicit test-only setup; never changed in the network replay scenario.
count=2+double(any(strcmp(mode,{'relay','siblings'})));
config.Name=['terminal_integrated_accounting_' mode];
config.DurationSeconds=13; if strcmp(mode,'cutoff'), config.DurationSeconds=8.25; end
if strcmp(mode,'siblings'), config.DurationSeconds=6; end
config.Backend='portable'; config.Stack='network';
config.ApplicationGenerator='configured-count'; config.ApplicationFlowLimit=0;
config.ApplicationProfile='current-send-only';
config.Nodes=repmat(config.Nodes(1),1,count);
for k=1:count
    config.Nodes(k).Id=k; config.Nodes(k).PositionMeters=[100*k 0 1];
    config.Nodes(k).Capability=1; config.Nodes(k).TransitForwardingEnabled=true;
end
config.Nodes(end).Capability=2;
config.Traffic=struct('SourceId',1,'DestinationId',count,'StartSeconds',0.5, ...
    'IntervalSeconds',1,'PacketCount',1,'ApplicationPayloadBytes',185,'Dscp',0,'AckRequired',true);
config.DiscoveryEvents=struct('TimeSeconds',{},'NodeIds',{});
config.LinkEvents=struct('TimeSeconds',{},'NodeIds',{},'Enabled',{});
config.Faults=struct('Kind',{},'SourceId',{},'DestinationId',{},'First',{},'Count',{},'StartSeconds',{},'EndSeconds',{},'ControlType',{});
config.Nwk.StartupMode='manual'; config.Nwk.SendOnlyToGateway=false; config.Nwk.AdaptiveLinkControl=false;
config.Nwk.Neighbor.AdmissionEnabled=false; config.Nwk.Neighbor.FreshnessEnabled=false;
config.Nwk.Neighbor.DiscoveryResponseEnabled=false;
config.Mac.DutyCycleEnabled=false; config.Mac.SlotSeconds=1000; config.Mac.HoldoffSeconds=1000;
config.Hop.DataQueuedRetryPolicy='native-provisional'; config.Hop.ResendSeconds=2;
config.Hop.MaxResends=1; config.Hop.TicSeconds=1e-6;
config.Trace.Enabled=true; config.Trace.MaxRecords=10000; config.Trace.MaxPhyRecords=1000;
config.Trace.MaxApplicationAdmissionRecords=1000; config.MaxEvents=100000;
config=csr.scenario.validate(config);
end
