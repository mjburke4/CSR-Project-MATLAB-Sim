classdef TestRoutes < matlab.unittest.TestCase
    % Source-policy regressions against ns-3 486d9e0 route state contracts.
    methods (Test)
        function localCapabilityIsAdvertisedButNeverForwarded(test)
            routes = csr.nwk.Routes(1,2);
            test.verifyEmpty(routes.select(1));
            [records,ids] = routes.drainChanges();
            test.verifyEqual(ids,1);
            test.verifyEqual(records,{TestRoutes.update(1,2,0,0,[])});
            routes.setCapability(0);
            test.verifyEqual(routes.drainChanges(),{struct('Operation','DELETE','NodeId',1)});
            routes.setCapability(0); test.verifyEmpty(routes.drainChanges());
            snapshot = routes.snapshot();
            test.verifyEqual(cellfun(@(r)r.Operation,snapshot,'UniformOutput',false),{'INFO','FLUSH'});
        end

        function candidateCostAndStableTieSelectNextHop(test)
            routes = TestRoutes.table();
            routes.apply(2,1,{TestRoutes.update(9,1,1,20,9)},10,0);
            routes.apply(3,1,{TestRoutes.update(9,1,1,15,9)},20,0);
            route = routes.select(9);
            test.verifyEqual(route.NextHop,2);
            routes.apply(3,2,{TestRoutes.update(9,1,1,5,9)},20,1);
            route = routes.select(9);
            test.verifyEqual(route.NextHop,3);
            routes.apply(2,2,{TestRoutes.update(9,1,1,15,9)},10,1);
            route = routes.select(9);
            test.verifyEqual(route.NextHop,3); % Exact tie retains current peer.
            test.verifyEqual(route.Cost,25);
            test.verifyEqual(route.Path,[3 9]);
            test.verifyEqual(route.HopCount,2);
        end

        function hopCountBreaksEqualCostBeforePriorPreference(test)
            routes = TestRoutes.table();
            routes.apply(2,1,{TestRoutes.update(9,1,2,20,[7 9])},10,0);
            routes.apply(3,1,{TestRoutes.update(9,1,1,10,9)},20,0);
            route = routes.select(9);
            test.verifyEqual(route.NextHop,3);
            route = routes.select(9);
            test.verifyEqual(route.HopCount,2);
        end

        function ordinaryNeighborCapabilityDeleteKeepsDirectReachability(test)
            routes = TestRoutes.table();
            routes.apply(2,1,{TestRoutes.update(2,2,0,0,[])},10,0);
            test.verifyEqual(routes.applicationGateway(),2);
            routes.apply(2,2,{struct('Operation','DELETE','NodeId',2)},10,1);
            direct = routes.select(2);
            test.verifyEqual(direct.Capability,0);
            test.verifyEqual(direct.Cost,10);
            test.verifyEqual(direct.Path,2);
            test.verifyEmpty(routes.applicationGateway());
            route = routes.relay(2);
            test.verifyEqual(route.NextHop,2);
        end

        function staleDuplicateAndAmbiguousSequencesCannotResurrect(test)
            routes = TestRoutes.table(); update = TestRoutes.update(9,1,1,20,9);
            routes.apply(2,100,{update},10,0);
            routes.apply(2,101,{struct('Operation','DELETE','NodeId',9)},10,1);
            for sequence = [100 101 101+2147483648]
                result = routes.apply(2,sequence,{update},10,2);
                test.verifyEmpty(routes.select(9));
                test.verifyEqual(result.IgnoredRecords,1);
            end
            routes.apply(2,102,{update},10,3);
            route = routes.select(9);
            test.verifyEqual(route.Sequence,102);
        end

        function sequenceWrapAndUnknownDeleteTombstone(test)
            routes = TestRoutes.table();
            routes.apply(2,4294967295,{struct('Operation','DELETE','NodeId',9)},10,0);
            routes.apply(2,4294967294,{TestRoutes.update(9,1,1,20,9)},10,1);
            test.verifyEmpty(routes.select(9));
            routes.apply(2,0,{TestRoutes.update(9,1,1,20,9)},10,2);
            route = routes.select(9);
            test.verifyEqual(route.Sequence,0);
            route = routes.select(9);
            test.verifyEqual(route.Cost,30);
        end

        function snapshotTailFlushPreservesSameSequenceUpdates(test)
            routes = TestRoutes.table();
            routes.apply(2,1,{TestRoutes.update(8,1,1,10,8),TestRoutes.update(9,1,1,20,9)},10,0);
            info = csr.nwk.Routes.defaults(); info = info.LocalInfo;
            records = {struct('Operation','INFO','Info',info), ...
                TestRoutes.update(9,1,1,22,9),struct('Operation','FLUSH')};
            routes.apply(2,2,records,10,1);
            test.verifyEmpty(routes.select(8));
            route = routes.select(9);
            test.verifyEqual(route.Cost,32);
            test.verifyEqual(routes.neighborInfo(2),info);
            route = routes.select(2);
            test.verifyEqual(route.Cost,10);
            routes.apply(2,3,{struct('Operation','FLUSH')},10,2);
            test.verifyEmpty(routes.select(9));
            test.verifyEmpty(routes.neighborInfo(2));
            test.verifyNotEmpty(routes.select(2));
        end

        function loopedUpdateInvalidatesReporterAndSelectsAlternative(test)
            routes = TestRoutes.table();
            routes.apply(2,1,{TestRoutes.update(9,1,1,20,9)},10,0);
            routes.apply(3,1,{TestRoutes.update(9,1,1,20,9)},20,0);
            routes.apply(2,2,{TestRoutes.update(9,1,2,20,[1 9])},10,1);
            route = routes.select(9);
            test.verifyEqual(route.NextHop,3);
            routes.apply(2,1,{TestRoutes.update(9,1,1,1,9)},10,2);
            route = routes.select(9);
            test.verifyEqual(route.NextHop,3);
        end

        function malformedSelfAndPathBoundaryDoNotEnterTable(test)
            routes = TestRoutes.table();
            records = {TestRoutes.update(2,2,1,0,2), ...
                TestRoutes.update(9,1,32,1,ones(1,32)*9), ...
                TestRoutes.update(9,1,1,1,16777215), ...
                TestRoutes.update(16777215,1,0,0,[])};
            result = routes.apply(2,1,records,10,0);
            test.verifyEqual(result.IgnoredRecords,4);
            test.verifyEmpty(routes.select(9));
            route = routes.select(2);
            test.verifyEqual(route.Capability,0);
            routes.apply(2,2,{TestRoutes.update(9,1,31,1,ones(1,31)*9)},10,0);
            route = routes.select(9);
            test.verifyEqual(route.HopCount,32);
        end

        function inactiveCandidateWaitsForDestinationRecomputation(test)
            routes = csr.nwk.Routes(1,1);
            routes.setNeighbor(2,false,10,0);
            routes.apply(2,1,{TestRoutes.update(9,1,1,20,9)},10,0);
            test.verifyEmpty(routes.select(9));
            routes.setNeighbor(2,true,10,1);
            test.verifyNotEmpty(routes.select(2));
            test.verifyEmpty(routes.select(9));
            routes.setNeighbor(2,true,10,1); % A decoded unrelated control is not a route recomputation.
            test.verifyEmpty(routes.select(9));
            routes.setNeighbor(2,true,11,1); % Cost change still requires a pre-existing selected destination.
            test.verifyEmpty(routes.select(9));
            routes.setNeighbor(3,true,20,1);
            routes.apply(3,1,{TestRoutes.update(9,1,1,20,9)},20,2);
            route = routes.select(9);
            test.verifyEqual(route.NextHop,2);
        end

        function failureWhileInactiveDiscardsCachedTransitAndCapability(test)
            routes = csr.nwk.Routes(1,1); defaults = csr.nwk.Routes.defaults();
            routes.setNeighbor(2,false,10,0);
            routes.apply(2,1,{struct('Operation','INFO','Info',defaults.LocalInfo), ...
                TestRoutes.update(2,2,0,0,[]),TestRoutes.update(9,1,1,20,9)},10,0);
            test.verifyTrue(any([routes.Candidates.DestinationId] == 9));
            routes.setNeighbor(2,false,10,1); % Ordinary observation retains cache.
            test.verifyTrue(any([routes.Candidates.DestinationId] == 9));
            routes.invalidateNeighbor(2,2);
            test.verifyFalse(any([routes.Candidates.DestinationId] == 9));
            test.verifyEmpty(routes.neighborInfo(2));
            routes.setNeighbor(2,true,10,3);
            route = routes.select(2); test.verifyEqual(route.Capability,0);
            test.verifyEmpty(routes.select(9));
        end

        function lossRecoveryRequiresFreshTransitAndSelfCapability(test)
            routes = TestRoutes.table();
            routes.apply(2,10,{TestRoutes.update(2,2,0,0,[]),TestRoutes.update(9,1,1,20,9)},10,0);
            routes.setNeighbor(2,false,10,1);
            test.verifyEmpty(routes.select(2)); test.verifyEmpty(routes.select(9));
            test.verifyFalse(any([routes.Candidates.DestinationId] == 9));
            routes.setNeighbor(2,true,10,2);
            route = routes.select(2);
            test.verifyEqual(route.Capability,0);
            test.verifyEmpty(routes.select(9));
            routes.apply(2,0,{TestRoutes.update(2,2,0,0,[]),TestRoutes.update(9,1,1,20,9)},10,3);
            test.verifyEqual(routes.applicationGateway(),2);
            route = routes.select(9);
            test.verifyEqual(route.NextHop,2);
        end

        function linkCostChangeRecomputesRouteSelection(test)
            routes = TestRoutes.table();
            routes.apply(2,1,{TestRoutes.update(9,1,1,20,9)},10,0);
            routes.apply(3,1,{TestRoutes.update(9,1,1,20,9)},20,0);
            routes.setNeighbor(2,true,30,1);
            route = routes.select(9);
            test.verifyEqual(route.NextHop,3);
            candidate = routes.Candidates([routes.Candidates.DestinationId]==9 & [routes.Candidates.NextHop]==2);
            test.verifyEqual(candidate.Cost,50);
        end

        function reverseRoutePriorityAndNeighborGate(test)
            routes = TestRoutes.table();
            routes.learnReverse(2,3,0);
            route = routes.relay(2);
            test.verifyTrue(route.UsedReverse); test.verifyEqual(route.NextHop,3);
            routes.apply(2,1,{TestRoutes.update(2,1,0,0,[])},10,0);
            route = routes.relay(2);
            test.verifyFalse(route.UsedReverse); test.verifyEqual(route.NextHop,2);
            routes.apply(2,2,{struct('Operation','DELETE','NodeId',2)},10,1);
            routes.setNeighbor(3,false,20,1);
            route = routes.relay(2);
            test.verifyFalse(route.UsedReverse); test.verifyEqual(route.NextHop,2);
        end

        function noPathOnlyClearsMatchingReverseAndPreservesAllForwardRoutes(test)
            routes = TestRoutes.table();
            routes.apply(2,1,{TestRoutes.update(9,1,1,20,9)},10,0);
            routes.learnReverse(2,3,0); routes.learnReverse(9,3,0);
            candidates = routes.Candidates;
            test.verifyFalse(routes.noteNoPath(2,2,1));
            route = routes.relay(2); test.verifyTrue(route.UsedReverse);
            test.verifyEqual(route.NextHop,3);
            test.verifyTrue(routes.noteNoPath(3,2,2));
            route = routes.relay(2); test.verifyFalse(route.UsedReverse);
            test.verifyEqual(route.NextHop,2);
            test.verifyTrue(routes.noteNoPath(3,9,3));
            route = routes.relay(9); test.verifyFalse(route.UsedReverse);
            test.verifyEqual(route.NextHop,2);
            test.verifyFalse(routes.noteNoPath(2,9,4));
            test.verifyFalse(routes.noteNoPath(3,16777215,5));
            test.verifyEqual(routes.Candidates,candidates);
        end

        function groupedChangesFollowDestinationCreationOrderAndInfoFirst(test)
            routes = TestRoutes.table(); routes.drainChanges();
            routes.apply(2,1,{TestRoutes.update(7,1,1,7,7),TestRoutes.update(9,1,1,9,9)},10,0);
            routes.setCapability(0);
            config = csr.nwk.Routes.defaults(); info = config.LocalInfo; info.MaxSpeedKbps = 1000;
            routes.setLocalInfo(info);
            [records,ids] = routes.drainChanges();
            test.verifyEqual(ids,[9 7 1]);
            test.verifyEqual(records{1},struct('Operation','INFO','Info',info));
            test.verifyEqual([records{2}.NodeId records{3}.NodeId records{4}.NodeId],[9 7 1]);
            test.verifyEqual(records{4}.Operation,'DELETE');
            test.verifyEmpty(routes.drainChanges());
        end

        function identicalSelectedReplacementStillPropagates(test)
            routes = TestRoutes.table(); update = TestRoutes.update(9,1,1,20,9);
            routes.apply(2,1,{update},10,0); routes.drainChanges();
            routes.apply(2,2,{update},10,1);
            [records,ids] = routes.drainChanges();
            test.verifyEqual(ids,9); test.verifyEqual(records{1}.Cost,30);
            routes.apply(2,2,{update},10,1); test.verifyEmpty(routes.drainChanges());
        end

        function snapshotExcludesSamePassChangesAndOrdinaryRoutes(test)
            routes = TestRoutes.table();
            routes.apply(2,1,{TestRoutes.update(7,1,1,7,7),TestRoutes.update(9,1,1,9,9)},10,0);
            snapshot = routes.snapshot([9 1]);
            test.verifyEqual(cellfun(@(r)r.Operation,snapshot,'UniformOutput',false),{'INFO','UPDATE','FLUSH'});
            test.verifyEqual(snapshot{2}.NodeId,7);
        end

        function snapshotUsesSelectedCandidateInsertionPosition(test)
            routes = TestRoutes.table();
            routes.apply(2,1,{TestRoutes.update(9,1,1,20,9),TestRoutes.update(7,1,1,7,7)},10,0);
            routes.apply(3,1,{TestRoutes.update(9,1,1,1,9)},20,0);
            snapshot = routes.snapshot();
            test.verifyEqual([snapshot{2}.NodeId snapshot{3}.NodeId snapshot{4}.NodeId],[1 7 9]);
        end

        function gatewaySelectionFollowsSourceLastCapableDestination(test)
            routes = TestRoutes.table();
            routes.apply(2,1,{TestRoutes.update(2,2,0,0,[])},10,0);
            routes.apply(3,1,{TestRoutes.update(3,2,0,0,[])},20,0);
            test.verifyEqual(routes.applicationGateway(),3);
            routes.setNeighbor(3,false,20,1);
            test.verifyEqual(routes.applicationGateway(),2);
        end

        function sourceLinkCostGoldenBoundaries(test)
            [cost,detail] = csr.nwk.linkCost(100,0);
            test.verifyEqual(cost,29); test.verifyEqual(detail.RateKeyKbps,128);
            test.verifyEqual(detail.TxPowerDbm,7); test.verifyEqual(detail.EstimatedDistance,75);
            [cost,detail] = csr.nwk.linkCost(130,0);
            test.verifyEqual(cost,1393); test.verifyEqual(detail.RateKeyKbps,16);
            test.verifyEqual(detail.TxPowerDbm,28); test.verifyEqual(detail.EstimatedDistance,223);
            [cost,detail] = csr.nwk.linkCost(140,0);
            test.verifyEqual(cost,6274); test.verifyEqual(detail.RateKeyKbps,8);
            test.verifyEqual(detail.TxPowerDbm,30); test.verifyEqual(detail.EstimatedDistance,251);
            [cost,detail] = csr.nwk.linkCost(100,0,struct('MaxSpeedKbps',1000));
            test.verifyEqual(cost,6); test.verifyEqual(detail.RateKeyKbps,1000);
            test.verifyEqual(detail.TxPowerDbm,18); test.verifyEqual(detail.EstimatedDistance,125);
        end

        function linkCostFailurePenaltyAndBadLimits(test)
            [base,~] = csr.nwk.linkCost(100,0);
            [penalized,~] = csr.nwk.linkCost(100,12);
            test.verifyEqual(base,29); test.verifyEqual(penalized,116);
            test.verifyError(@()csr.nwk.linkCost(100,0,struct('MaxSpeedKbps',9)), ...
                'csr:nwk:InvalidConfig');
            test.verifyError(@()csr.nwk.Routes(1,1,struct('MaxPathHops',33)), ...
                'csr:nwk:InvalidField');
        end
    end
    methods (Static, Access = private)
        function routes = table()
            routes = csr.nwk.Routes(1,1);
            routes.setNeighbor(2,true,10,0);
            routes.setNeighbor(3,true,20,0);
        end

        function record = update(node,capability,hops,cost,path)
            record = struct('Operation','UPDATE','NodeId',node,'Capability',capability, ...
                'HopCount',hops,'Cost',cost,'Path',path);
        end
    end
end
