classdef TestAckServiceSuite < matlab.unittest.TestCase
    methods (Test)
        function fixedSmallCasesRetainAcceptedConfigurations(test)
            [cases,plan]=csr.scenario.ackServiceSuite();
            parents=csr.scenario.linkDiagnosticSuite();
            test.verifyEqual({cases.StorageKey},{'c129','c128','c130','c131','c132','a129'});
            test.verifyEqual([cases.DurationSeconds],[360 360 360 360 360 1200]);
            test.verifyEqual(plan.service_window_s(:)',[300 320]);
            test.verifyTrue(plan.service_window_end_exclusive);
            for k=1:numel(cases)
                index=find(strcmp({parents.CaseId},cases(k).CaseId));
                test.verifyEqual(cases(k).Config,parents(index).Config);
                test.verifyEqual(cases(k).ScenarioSHA256,parents(index).ScenarioSHA256);
            end
        end

        function controlsAndReferencePathsStayShort(test)
            [cases,plan]=csr.scenario.ackServiceSuite();
            test.verifyEqual(plan.control_keys(:)',{'c129','a129'});
            for k=1:numel(cases)
                test.verifyEqual(cases(k).ServiceReferenceDirectory, ...
                    ['evidence/tranche-9-ns3-reference/' cases(k).StorageKey]);
                test.verifyLessThanOrEqual(length(['b/' cases(k).StorageKey '/raw/service_trace.csv']),30);
            end
        end
    end
end
