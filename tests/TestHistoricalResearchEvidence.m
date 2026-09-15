classdef TestHistoricalResearchEvidence < matlab.unittest.TestCase
    % Runtime evidence checks on short source-gated generators. The admitted
    % fixture seeds one observed direct peer to isolate application/NSDP gates;
    % it is not an autonomous-convergence or end-to-end PHY acceptance case.
    methods (Test)
        function suppressedAttemptsAreNotFabricatedGeneratedPackets(test)
            result = blockedResult();
            row = csr.analysis.researchSummary(result);
            test.verifyTrue(row.StructuralChecksPassed);
            test.verifyEqual(result.ApplicationAdmissionStatistics.Attempts,3);
            test.verifyEqual(result.ApplicationAdmissionStatistics.BlockedTopology,3);
            test.verifyEqual([row.Generated,row.Received,row.Dropped,row.Pending],[0,0,0,0]);
        end

        function fullTracePartitionsAdmittedAndNsdpSuppressedAttempts(test)
            result = admittedResult();
            row = csr.analysis.researchSummary(result);
            counts = result.ApplicationAdmissionStatistics;
            test.verifyTrue(row.StructuralChecksPassed);
            test.verifyEqual([counts.Attempts,counts.Admitted,counts.BlockedNsdp],[20,16,4]);
            test.verifyEqual([row.Generated,row.Pending,row.Dropped],[16,16,0]);
            test.verifyEqual(sum(result.ApplicationAdmissionTrace.Accepted),16);
            test.verifyEqual(sum(strcmp(result.ApplicationAdmissionTrace.Reason,'nsdp_full')),4);
        end

        function admittedCapAllowsGeneratorToStopBeforeAllPossibleInterrupts(test)
            result = admittedResult(1);
            row = csr.analysis.researchSummary(result);
            test.verifyTrue(row.StructuralChecksPassed);
            test.verifyEqual(result.Config.Traffic.PacketCount,20);
            test.verifyEqual(result.ApplicationAdmissionStatistics.Attempts,1);
            test.verifyEqual(result.ApplicationAdmissionStatistics.Admitted,1);
            test.verifyEqual(row.Generated,1);
        end

        function boundedAdmissionTraceAcceptsCompleteSeparateCounters(test)
            result = admittedResult(0,5);
            row = csr.analysis.researchSummary(result);
            test.verifyTrue(row.StructuralChecksPassed);
            test.verifyEqual(height(result.ApplicationAdmissionTrace),5);
            test.verifyEqual(result.Statistics.OmittedApplicationAdmissionRecords,15);
            test.verifyEqual(result.ApplicationAdmissionStatistics.Attempts,20);
            test.verifyEqual(row.Generated,16);
        end

        function rejectsAdmissionEvidenceExceedingConfiguredCap(test)
            result = admittedResult();
            result.Config.ApplicationFlowLimit = 1;
            test.verifyError(@()csr.analysis.researchSummary(result),'csr:research:Admission');
        end

        function decimalStopBoundaryUsesNanosecondInterruptCount(test)
            config = baseConfig(); config.DurationSeconds = 0.4;
            config.Traffic.StartSeconds = 0.1; config.Traffic.IntervalSeconds = 0.1;
            config.Traffic.PacketCount = 4;
            result = csr.runScenario(config);
            row = csr.analysis.researchSummary(result);
            test.verifyTrue(row.StructuralChecksPassed);
            test.verifyEqual(result.ApplicationAdmissionStatistics.Attempts,3);
            test.verifyEqual(result.ApplicationAdmissionTrace.TimeSeconds,[0.1;0.2;0.3],'AbsTol',1e-15);
        end

        function rejectsIncompleteAttemptPartition(test)
            result = blockedResult();
            result.ApplicationAdmissionStatistics.BlockedTopology = 2;
            test.verifyError(@()csr.analysis.researchSummary(result),'csr:research:Admission');
        end

        function rejectsRelabeledReasonsEvenWhenAttemptTotalsBalance(test)
            result = blockedResult();
            result.ApplicationAdmissionStatistics.BlockedTopology = 2;
            result.ApplicationAdmissionStatistics.BlockedDiscovery = 1;
            test.verifyError(@()csr.analysis.researchSummary(result),'csr:research:Admission');
        end

        function rejectsOmissionCountThatDoesNotCoverAllAttempts(test)
            result = admittedResult(0,5);
            result.Statistics.OmittedApplicationAdmissionRecords = 14;
            test.verifyError(@()csr.analysis.researchSummary(result),'csr:research:Admission');
        end

        function rejectsObservedAdmissionsExceedingBoundedTraceCounters(test)
            result = admittedResult(0,5);
            result.ApplicationAdmissionStatistics.Admitted = 4;
            result.ApplicationAdmissionStatistics.BlockedNsdp = 16;
            test.verifyError(@()csr.analysis.researchSummary(result),'csr:research:Admission');
        end

        function rejectsAdmittedPacketIdentityAbsentFromGenerationTrace(test)
            result = admittedResult(1);
            result.ApplicationAdmissionTrace.PacketId(1) = uint64(999999);
            test.verifyError(@()csr.analysis.researchSummary(result),'csr:research:Admission');
        end

        function rejectsBlockedReasonOnAcceptedPacket(test)
            result = admittedResult(1);
            result.ApplicationAdmissionTrace.Reason = {'nsdp_full'};
            test.verifyError(@()csr.analysis.researchSummary(result),'csr:research:Admission');
        end

        function rejectsNonfiniteFlowIdentity(test)
            result = admittedResult(1);
            result.ApplicationAdmissionTrace.FlowIndex(1) = NaN;
            test.verifyError(@()csr.analysis.researchSummary(result),'csr:research:Admission');
        end

        function rejectsAttemptOutsideItsConfiguredInterruptTime(test)
            result = blockedResult();
            result.ApplicationAdmissionTrace.TimeSeconds(2) = ...
                result.ApplicationAdmissionTrace.TimeSeconds(2)+0.001;
            test.verifyError(@()csr.analysis.researchSummary(result),'csr:research:Admission');
        end

        function offeredLoadCannotReplaceActualAdmittedGeneration(test)
            result = admittedResult();
            result.Statistics.Generated = 20; result.Statistics.Pending = 20;
            result.NodeStatistics.Generated(result.NodeStatistics.Id==2) = 20;
            test.verifyError(@()csr.analysis.researchSummary(result),'csr:research:Generation');
        end
    end
end

function result = blockedResult()
config = baseConfig();
config.DurationSeconds = 0.375;
config.Traffic.StartSeconds = 0; config.Traffic.IntervalSeconds = 0.125;
config.Traffic.PacketCount = 4;
result = csr.runScenario(config);
end

function result = admittedResult(limit,traceLimit)
if nargin<1, limit = 0; end
if nargin<2, traceLimit = 100; end
config = baseConfig();
config.DurationSeconds = 0.02; config.ApplicationFlowLimit = limit;
config.Traffic.StartSeconds = 0; config.Traffic.IntervalSeconds = 0.001;
config.Traffic.PacketCount = 20;
config.Traffic.DestinationMode = 'random_route_or_neighbor';
config.Trace.MaxApplicationAdmissionRecords = traceLimit;
config.Nwk.Neighbor.AdmissionEnabled = false;
simulation = csr.sim.NetworkSimulation(config);
% A direct observed peer supplies the source-runner dynamic destination list.
% Stop before a long-preamble frame can finish, keeping all admitted NSDPs
% under source custody and reaching the strict 16-packet application gate.
simulation.Networks{2}.observe(1,struct('Success',true));
result = simulation.run();
end

function config = baseConfig()
config = csr.scenario.routedNetwork('autonomous');
config.Nodes = config.Nodes(1:2);
config.Nwk.StartupMode = 'manual'; config.Nwk.AdaptiveLinkControl = false;
config.ApplicationGenerator = 'historical-opnet-gated';
config.Traffic.SourceId = 2; config.Traffic.DestinationId = 1;
config.Trace.MaxRecords = 2000; config.Trace.MaxPhyRecords = 2000;
config.Trace.MaxApplicationAdmissionRecords = 100;
end
