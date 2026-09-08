classdef TestRandomStreams < matlab.unittest.TestCase
    methods (Test)
        function creationOrderDoesNotChangePerKeySequences(testCase)
            first = csr.sim.RandomStreams(42);
            second = csr.sim.RandomStreams(42);
            trafficA = first.get(8, 'traffic');
            phyA = first.get(2, 'phy');
            phyB = second.get(2, 'phy');
            trafficB = second.get(8, 'traffic');
            testCase.verifyEqual(rand(trafficA, 1, 20), rand(trafficB, 1, 20));
            testCase.verifyEqual(rand(phyA, 1, 20), rand(phyB, 1, 20));
            testCase.verifyNotEqual(trafficA.Seed, phyA.Seed);
        end

        function cachedStreamsContinueInsteadOfRestarting(testCase)
            owner = csr.sim.RandomStreams(7);
            reference = csr.sim.RandomStreams(7);
            first = rand(owner.get(577, 'mac'), 1, 5);
            second = rand(owner.get(577, "mac"), 1, 5);
            expected = rand(reference.get(577, 'mac'), 1, 10);
            testCase.verifyEqual([first, second], expected);
        end

        function streamsDoNotChangeGlobalRng(testCase)
            before = rng;
            restore = onCleanup(@() rng(before)); %#ok<NASGU>
            owner = csr.sim.RandomStreams(123);
            rand(owner.get(5, 'nwk'), 1, 30);
            randn(owner.get(5, 'phy'), 1, 30);
            testCase.verifyEqual(rng, before);
        end

        function nodeAndSubsystemSeedsAreDistinctAtBounds(testCase)
            owner = csr.sim.RandomStreams(intmax('uint32'));
            names = {'traffic', 'phy', 'mac', 'nwk'};
            nodes = [0, 1, 577, 16777215];
            seeds = zeros(1, numel(names) * numel(nodes));
            count = 0;
            for node = nodes
                for index = 1:numel(names)
                    count = count + 1;
                    stream = owner.get(node, names{index});
                    seeds(count) = stream.Seed;
                end
            end
            testCase.verifyEqual(numel(unique(seeds)), numel(seeds));
            testCase.verifyError(@() owner.get(1, 'application'), ...
                'csr:sim:UnknownSubsystem');
        end

        function zeroSeedUsesReservedNonzeroStream(testCase)
            owner = csr.sim.RandomStreams(0);
            reference = csr.sim.RandomStreams(0);
            stream = owner.get(0, 'traffic');
            testCase.verifyNotEqual(stream.Seed, 0);
            testCase.verifyEqual(rand(stream, 1, 10), ...
                rand(reference.get(0, 'traffic'), 1, 10));
            neighbor = owner.get(0, 'phy');
            testCase.verifyNotEqual(stream.Seed, neighbor.Seed);
        end
    end
end
