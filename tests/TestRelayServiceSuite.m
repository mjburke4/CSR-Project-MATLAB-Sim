classdef TestRelayServiceSuite < matlab.unittest.TestCase
    % Fast scenario and observation preflight; never runs 600/900-second cases.
    methods (Test)
        function declaredCasesPreserveThreeSeedsAndFullPrefix(test)
            [cases,plan]=csr.scenario.tranche18Suite();
            test.verifyEqual({cases.CaseId}, ...
                {'r128','l128','m128','r129','l129','m129','r130','l130','m130','p128'});
            test.verifyEqual([cases.Seed],[128 128 128 129 129 129 130 130 130 128]);
            test.verifyEqual([cases.DurationSeconds],[600*ones(1,9) 900]);
            test.verifyEqual(sum([cases.DurationSeconds])+cases(3).DurationSeconds,6900);
            test.verifyEqual(numel(plan.execution_order),11);
            test.verifyEqual(plan.control.case_id,'m128_off');
            test.verifyTrue(plan.control.configuration_must_match_exactly);
        end

        function conditionsChangeOnlyRetainedNodeAndFlowMembership(test)
            [cases,~]=csr.scenario.tranche18Suite();
            [parent,~]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
            expectedNodes=parent.Config.Nodes(ismember([parent.Config.Nodes.Id],[1 4 5]));
            expectedFlows={4,5,[4 5]};
            for k=1:9
                config=cases(k).Config;
                test.verifyEqual(config.Nodes,expectedNodes);
                test.verifyEqual([config.Traffic.SourceId],expectedFlows{mod(k-1,3)+1});
                test.verifyEqual([config.Traffic.DestinationId],ones(1,numel(config.Traffic)));
                test.verifyEqual([config.Traffic.Dscp],zeros(1,numel(config.Traffic)));
                test.verifyEqual([config.Traffic.StartSeconds],300*ones(1,numel(config.Traffic)));
                test.verifyEqual([config.Traffic.IntervalSeconds],0.02*ones(1,numel(config.Traffic)));
                test.verifyEqual([config.Traffic.PacketCount],15000*ones(1,numel(config.Traffic)));
                test.verifyEmpty(config.Faults); test.verifyEmpty(config.LinkEvents);
                test.verifyEqual(config.Channel.Model,'csr-phy');
                test.verifyEqual(config.Nwk.StartupMode,parent.Config.Nwk.StartupMode);
            end
        end

        function prefixRetainsUpstreamSevenAndEightAndEveryOriginalFlow(test)
            [cases,~]=csr.scenario.tranche18Suite(); prefix=cases(end).Config;
            [parent,~]=csr.scenario.benchmarkSuite(struct('Cases',{{'campus_multihop_6000'}}));
            test.verifyEqual(prefix.Nodes,parent.Config.Nodes);
            test.verifyEqual([prefix.Traffic.SourceId],[2 3 4 5 7 8]);
            test.verifyEqual([prefix.Traffic.PacketCount],30000*ones(1,6));
            test.verifyEqual(prefix.Hop,parent.Config.Hop);
            test.verifyEqual(prefix.Mac,parent.Config.Mac);
            test.verifyEqual(prefix.Nwk,parent.Config.Nwk);
            test.verifyEqual(prefix.Radio,parent.Config.Radio);
            test.verifyEqual(prefix.Channel,parent.Config.Channel);
        end

        function budgetsRetainEveryScheduledAdmissionIncludingPrefixTail(test)
            [cases,~]=csr.scenario.tranche18Suite();
            for k=1:numel(cases)
                item=cases(k);
                attempts=sum([item.Config.Traffic.PacketCount]);
                test.verifyEqual(attempts,item.PlanEntry.expected_admission_attempts);
                test.verifyGreaterThanOrEqual(item.Config.Trace.MaxApplicationAdmissionRecords,attempts);
                test.verifyGreaterThan(item.ObserverMaxRecords,attempts);
                test.verifyEqual(item.ServiceWindowSeconds,[0 item.DurationSeconds+1]);
                test.verifyEqual(item.Config.ApplicationFlowLimit,0);
                test.verifyEqual(item.Config.Backend,'portable');
                test.verifyEqual(item.Config.ApplicationGenerator,'historical-opnet-gated');
            end
            test.verifyEqual(cases(end).PlanEntry.expected_admission_attempts,180000);
            test.verifyGreaterThan(cases(end).Config.Trace.MaxApplicationAdmissionRecords,100000);
        end

        function observerIncludesExactStopWithoutSchedulingAnEvent(test)
            observer=csr.sim.AckServiceDiagnostics(4,[0 601]); observer.attach(5);
            observer.observeService(599.9,5,'mac_state',struct(),struct('State','Search'));
            observer.observeService(600,5,'mac_state',struct(),struct('State','Idle'));
            observer.observeService(601,5,'mac_state',struct(),struct('State','Idle'));
            snapshot=observer.snapshot();
            test.verifyEqual(snapshot.ServiceTrace.TimeSeconds,[599.9;600]);
            test.verifyEqual(snapshot.ServiceDiagnostics.OutOfWindowServiceEvents,1);
            test.verifyEqual(snapshot.ServiceDiagnostics.ScheduledEvents,0);
            test.verifyEqual(snapshot.ServiceDiagnostics.RandomDraws,0);
            observer.assertComplete();
        end

        function applicationOriginDistinguishesLocalRelayAndPreviousHop(test)
            observer=csr.sim.AckServiceDiagnostics(4,[0 601]); observer.attach(5);
            wide=bitshift(uint64(1),55)+uint64(7);
            local=application(wide,5); relay=application(wide+uint64(1),8);
            incoming=csr.hop.Frames.data(relay,4,5,uint16(12),struct('RateKeyKbps',8,'TxPowerDbm',33));
            outgoing=csr.hop.Frames.data(local,5,1,uint16(13),struct('RateKeyKbps',8,'TxPowerDbm',33));
            observer.observeService(301,5,'hop_receive',incoming,struct('FirstReception',true,'LocalDelivery',false));
            observer.observeService(302,5,'hop_admit',outgoing,struct('PendingData',1));
            snapshot=observer.snapshot(); rows=snapshot.ServiceTrace;
            test.verifyEqual(rows.ApplicationSourceId,[8;5]);
            test.verifyEqual(rows.FrameSourceId,[4;5]);
            test.verifyEqual(rows.PeerId,[4;1]);
            test.verifyEqual(rows.PacketId,[wide+uint64(1);wide]);
            test.verifyTrue(all(rows.PacketIdAvailable));
            test.verifyEqual(rows.Sequence,[12;13]);
        end

        function dackHoldAndLaterCapacityReleaseRemainDistinctStages(test)
            observer=csr.sim.AckServiceDiagnostics(4,[0 601]); observer.attach(5);
            frame=csr.hop.Frames.data(application(uint64(3),4),4,5,uint16(12), ...
                struct('RateKeyKbps',8,'TxPowerDbm',33));
            observer.observeService(400,4,'hop_dack',frame, ...
                struct('HoldSeconds',10,'CapacityReleased',false));
            observer.observeService(410,4,'hop_dack_expired',frame, ...
                struct('PendingData',2,'NeighborOutstanding',2,'GlobalAllowed',true,'NeighborAllowed',true));
            snapshot=observer.snapshot(); rows=snapshot.ServiceTrace;
            test.verifyEqual(rows.Event,{'hop_dack';'hop_dack_expired'});
            test.verifyEqual(rows.CapacityReleased(1),0);
            test.verifyTrue(isnan(rows.PendingData(1)));
            test.verifyTrue(isnan(rows.CapacityReleased(2)));
            test.verifyEqual(rows.PendingData(2),2);
            test.verifyEqual(rows.ObservationId,uint64([1;2]));
        end

        function blockedAttemptsDoNotAcquirePacketIdentity(test)
            observer=csr.sim.AckServiceDiagnostics(4,[0 601]); observer.attach(5);
            row=csr.sim.ApplicationGenerator.emptyTrace();
            row.TimeSeconds=300.32; row.SourceId=5; row.DestinationId=1;
            row.AttemptIndex=17; row.FlowIndex=2; row.Reason='nsdp_full';
            row.NsdpCount=16; row.NwkQueueSize=15; row.Accepted=false;
            observer.observeAdmission(row);
            row.TimeSeconds=305; row.AttemptIndex=251; row.Reason='admitted';
            row.NsdpCount=15; row.Accepted=true; row.PacketId=uint64(99);
            observer.observeAdmission(row);
            snapshot=observer.snapshot(); rows=snapshot.ServiceTrace;
            test.verifyEqual(rows.PacketIdAvailable,[false;true]);
            test.verifyEqual(rows.PacketId,uint64([0;99]));
            test.verifyEqual(rows.NsdpCount,[16;15]);
            test.verifyEqual(rows.ApplicationSourceId,[5;5]);
            test.verifyEqual(rows.Stage,{'application_attempt';'application_attempt'});
        end

        function observerOverflowIsAnExplicitEvidenceFailure(test)
            observer=csr.sim.AckServiceDiagnostics(1,[0 601]); observer.attach(5);
            observer.observeService(1,5,'network_enqueue',application(uint64(1),5),struct('QueueDepth',1));
            observer.observeService(2,5,'network_enqueue',application(uint64(2),4),struct('QueueDepth',2));
            snapshot=observer.snapshot();
            test.verifyEqual(snapshot.ServiceDiagnostics.ServiceEventCount,2);
            test.verifyEqual(snapshot.ServiceDiagnostics.OmittedServiceRecords,1);
            test.verifyFalse(snapshot.ServiceDiagnostics.Complete);
            test.verifyError(@()observer.assertComplete(),'csr:diagnostics:IncompleteService');
        end

        function outputCannotOverwriteAnInstallationOrReferenceTree(test)
            root=fileparts(fileparts(mfilename('fullpath')));
            test.verifyError(@()run_tranche18_validation(root),'csr:t18:Output');
            test.verifyError(@()run_tranche18_validation(fullfile(root,'scenarios','t18')),'csr:t18:Output');
            test.verifyError(@()run_tranche18_validation(fullfile(root,'evidence')),'csr:t18:Output');
        end
    end
end

function app=application(id,source)
app=struct('Id',id,'SourceId',source,'DestinationId',1, ...
    'GeneratedSeconds',300,'ApplicationPayloadBytes',185);
end
