classdef TestTranche1Integration < matlab.unittest.TestCase
    methods (Test)
        function mixedNodeStorageTypesPreserve24BitAddresses(test)
            config = csr.scenario.phyNetwork('clean');
            config.Nodes(1).Id = uint8(1);
            config.Nodes(2).Id = 257;
            config.Traffic(1).SourceId = 257;
            result = csr.runScenario(config);
            test.verifyEqual(result.Statistics.Received,6);
            test.verifyEqual(result.NodeStatistics.Id,[1;257;3]);
        end
        function separateSyncStreamDoesNotPerturbPhyDraws(test)
            first = csr.sim.RandomStreams(128);
            second = csr.sim.RandomStreams(128);
            randn(first.get(16777214,'sync'),1,20);
            test.verifyEqual(rand(first.get(16777214,'phy'),1,12), ...
                rand(second.get(16777214,'phy'),1,12));
            syncStream = first.get(16777214,'sync');
            phyStream = first.get(16777214,'phy');
            test.verifyNotEqual(syncStream.Seed,phyStream.Seed);
        end
        function delegatedClosureExportsMatAndDescriptiveJson(test)
            config = csr.scenario.phyNetwork('clean');
            config.Nodes(1).RadioProfile.ClosureMode = 'DELEGATE';
            config.Nodes(1).RadioProfile.ClosureDelegate = @(distance,txHeight,rxHeight) distance < 50;
            result = csr.runScenario(config);
            test.verifyEqual(result.Statistics.Received,0);
            directory = tempname;
            mkdir(directory);
            cleanup = onCleanup(@() rmdir(directory,'s')); %#ok<NASGU>
            csr.analysis.exportResults(result,directory);
            decoded = jsondecode(fileread(fullfile(directory,'summary.json')));
            delegate = decoded.Config.Nodes(1).RadioProfile.ClosureDelegate;
            test.verifyEqual(delegate.Kind,'matlab-function-handle');
            test.verifyFalse(delegate.ExecutableFromJson);
            test.verifyTrue(isfile(fullfile(directory,'phy_trace.csv')));
            stored = load(fullfile(directory,'results.mat'),'result');
            test.verifyClass(stored.result.Config.Nodes(1).RadioProfile.ClosureDelegate,'function_handle');
        end
    end
end
