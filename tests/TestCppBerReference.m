classdef TestCppBerReference < matlab.unittest.TestCase
    % Differential inputs obtained by executing unchanged original C++.
    % These MATLAB checks are prepared; only a MATLAB run can pass them.
    methods (Test)
        function modulationCurvesMatchOriginalCpp(test)
            evidence = TestCppBerReference.reference();
            names = {'standard', 'dpsk', 'dqpsk'};
            methods = {@csr.phy.BerTables.standard, ...
                @csr.phy.BerTables.dpsk, @csr.phy.BerTables.dqpsk};
            for mode = 1:numel(names)
                rows = evidence.vectors.(names{mode});
                evaluate = methods{mode};
                for k = 1:numel(rows)
                    test.verifyEqual(evaluate(rows(k).snr_db), ...
                        rows(k).ber, 'AbsTol', 2e-14, ...
                        sprintf('%s C++ reference %d', names{mode}, k));
                end
            end
        end

        function collisionTablesMatchOriginalCpp(test)
            evidence = TestCppBerReference.reference();
            rows = evidence.vectors.collision;
            for k = 1:numel(rows)
                row = rows(k);
                actual = csr.phy.BerTables.collision(row.rate_kbps, ...
                    row.jsr_db, row.offset_seconds, row.snr_db);
                test.verifyEqual(actual, row.ber, 'AbsTol', 2e-14, ...
                    sprintf('collision C++ reference %d', k));
            end
        end

        function jsrBoundariesMatchOriginalCpp(test)
            evidence = TestCppBerReference.reference();
            rows = evidence.vectors.jsr_quantization;
            for k = 1:numel(rows)
                test.verifyEqual(csr.phy.BerTables.quantizeJsrDb(rows(k).jsr_db), ...
                    rows(k).bucket_db);
            end
        end

        function circularOffsetBoundariesMatchOriginalCpp(test)
            evidence = TestCppBerReference.reference();
            rows = evidence.vectors.offset_quantization;
            for k = 1:numel(rows)
                test.verifyEqual(csr.phy.BerTables.quantizeChipOffset( ...
                    rows(k).rate_kbps, rows(k).offset_seconds), rows(k).chip_offset);
            end
        end

        function rateIntervalsMatchOriginalCpp(test)
            evidence = TestCppBerReference.reference();
            rows = evidence.vectors.symbol_duration;
            for k = 1:numel(rows)
                test.verifyEqual(csr.phy.BerTables.symbolDurationSeconds( ...
                    rows(k).rate_kbps), rows(k).seconds, 'AbsTol', 1e-18);
            end
        end
    end

    methods (Static, Access = private)
        function evidence = reference()
            root = fileparts(fileparts(mfilename('fullpath')));
            evidence = jsondecode(fileread(fullfile(root, 'evidence', ...
                'tranche-1-ns3-reference.json')));
        end
    end
end
