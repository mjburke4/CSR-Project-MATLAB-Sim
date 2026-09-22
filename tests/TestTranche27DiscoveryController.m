classdef TestTranche27DiscoveryController < matlab.unittest.TestCase
    % Bounded actual-controller regressions; intentional contrasts are kept.
    methods (Test)
        function baselineUsesNewestTargetThenWatchdog(test)
            value=runCase('C0');
            test.verifyEqual([value.Controls.final_destination],[5 3]);
            test.verifyEqual([value.Controls.time_s],[0.1 60.1],'AbsTol',1e-9);
            test.verifyEqual(value.FinalStatistics.ScanWatchdogs,1);
        end

        function lateUsablePeerStartsAfterClosedScan(test)
            value=runCase('C1');
            test.verifyEqual([value.Controls.final_destination],[3 4]);
            test.verifyEqual([value.Controls.time_s],[0.1 20],'AbsTol',1e-9);
            test.verifyEqual(value.FinalStatistics.DiscoveryStarts,1);
            test.verifyEqual(value.FinalStatistics.ScanWatchdogs,0);
        end

        function unmatchedDoneKeepsWaitingUntilOriginalDeadline(test)
            value=runCase('C2');
            test.verifyEqual([value.Controls.final_destination],[4 5]);
            test.verifyEqual([value.Controls.time_s],[0.1 60.1],'AbsTol',1e-9);
            test.verifyEqual(value.FinalStatistics.ScanWatchdogs,1);
        end

        function matchingDoneInvalidatesOldWatchdog(test)
            value=runCase('C3_match');
            test.verifyEqual([value.Controls.final_destination],[4 5 3]);
            test.verifyEqual([value.Controls.time_s],[0.1 1 61],'AbsTol',1e-9);
            test.verifyEqual(value.FinalStatistics.ScanWatchdogs,1);
            test.verifyFalse(any(abs([value.Controls.time_s]-60.1)<1e-9));
        end

        function absentDoneUsesOriginalWatchdog(test)
            value=runCase('C3_timeout');
            test.verifyEqual([value.Controls.final_destination],[4 5]);
            test.verifyEqual([value.Controls.time_s],[0.1 60.1],'AbsTol',1e-9);
            test.verifyEqual(value.FinalStatistics.ScanWatchdogs,1);
        end

        function managementControlsRemainBestEffortAndOneHop(test)
            value=runCase('C0');
            test.verifyTrue(value.StructuralPassed);
            test.verifyEqual([value.Controls.source],[1 1]);
            test.verifyEqual([value.Controls.final_destination],[value.Controls.next_hop]);
            test.verifyEqual([value.Controls.ackable],[0 0]);
            test.verifyEqual([value.Controls.send_result],[1 1]);
            test.verifyEqual({value.Controls.command},{'START','START'});
        end

        function publicAdmissionStateTracksLocalDiscovery(test)
            value=runCase('C0'); rows=value.States.Snapshots;
            active=[rows.time_s]<0.1;
            test.verifyEqual([rows.local_discovery_active],active);
            test.verifyTrue(all([rows.topology_known]));
            test.verifyTrue(all([rows.local_is_gateway]));
            test.verifyFalse(any([rows.gateway_available]));
            test.verifyEqual(rows(end).route_storage_order,[3 5]);
            test.verifyEqual(rows(end).logical_destination_birth_order_fixture,[5 3]);
            test.verifyFalse(value.States.PrivateControllerStateAvailable);
        end

        function sampleMembershipIncludesBothTimerBoundaries(test)
            value=runCase('C3_match'); config=caseConfig('C3_match');
            test.verifyEqual([value.States.Snapshots.time_s],reshape(config.checkpoints_s,1,[]));
            test.verifyEqual([value.States.Snapshots.event_order],1:numel(config.checkpoints_s));
            test.verifyEqual(value.CheckpointCount,10);
            test.verifyEqual(value.StopSeconds,61.2);
            test.verifyTrue(value.DiagnosticCompleted);
        end
    end
end

function value=runCase(id)
value=csr.validation.discoveryControllerCase(caseConfig(id));
end

function config=caseConfig(id)
root=fileparts(fileparts(mfilename('fullpath')));
plan=jsondecode(fileread(fullfile(root,'evidence','tranche-27-plan.json')));
index=find(strcmp({plan.cases.id},id));
if numel(index)~=1, error('csr:t27:TestPlan','The named fixture is missing or duplicated.'); end
config=plan.cases(index);
end
