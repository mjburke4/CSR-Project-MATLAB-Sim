classdef TestEdgeRecords < matlab.unittest.TestCase
    % Independent diagnostics: these run even if the six-case fixture fails.
    methods (Test)
        function mixedCaseNamesAndFixedWidthHexRetainRowsAndExactIntegers(test)
            prototype = struct('case','','phase','','time_hex','', ...
                'id',uint64(0),'time',0,'passed',false);
            empty = csr.validation.edgeRecordTable(repmat(prototype,0,1),prototype);
            test.verifySize(empty.('case'),[0 1]); test.verifyClass(empty.('case'),'string');
            test.verifySize(empty.id,[0 1]); test.verifyClass(empty.id,'uint64');
            test.verifySize(empty.passed,[0 1]); test.verifyClass(empty.passed,'logical');
            names = {'tie_early','tie_late','before','after','continuous','quantized'};
            expected = strings(12,1); expectedHex = strings(12,1); allRows = empty;
            for k=1:numel(names)
                rows = repmat(prototype,2,1);
                for n=1:2
                    rows(n).('case') = names{k}; rows(n).phase = 'ack_tx';
                    rows(n).time = 3.144961+(n-1)*eps(3.144961);
                    rows(n).time_hex = num2hex(rows(n).time);
                    rows(n).id = intmax('uint64')-uint64(n-1); rows(n).passed = true;
                    expected(2*k-2+n) = string(names{k});
                    expectedHex(2*k-2+n) = string(rows(n).time_hex);
                end
                block = csr.validation.edgeRecordTable(rows,prototype);
                one = csr.validation.edgeRecordTable(rows(1),prototype);
                test.verifySize(one.time_hex,[1 1]);
                test.verifyEqual(one.time_hex,string(num2hex(3.144961)));
                allRows = [allRows;block]; %#ok<AGROW>
            end
            test.verifyEqual(height(allRows),12);
            test.verifyEqual(allRows.('case'),expected);
            test.verifyEqual(allRows.time_hex,expectedHex);
            test.verifySize(allRows.time_hex,[12 1]);
            test.verifyClass(allRows.time,'double'); test.verifyClass(allRows.passed,'logical');
            test.verifyEqual(allRows.id,repmat([intmax('uint64');intmax('uint64')-uint64(1)],6,1));
            directory = tempname; mkdir(directory); test.addTeardown(@()rmdir(directory,'s'));
            path = fullfile(directory,'rows.csv'); writetable(allRows,path);
            options = detectImportOptions(path,'VariableNamingRule','preserve');
            options = setvartype(options,{'case','phase','time_hex','id'},'string');
            exported = readtable(path,options);
            test.verifyEqual(exported.('case'),expected); test.verifyEqual(exported.time_hex,expectedHex);
            test.verifyEqual(exported.id,repmat(["18446744073709551615";"18446744073709551614"],6,1));
        end
        function schedulerEmptySingleAndMixedCaseRecordsKeepWholeTextValues(test)
            early = csr.validation.TraceScheduler('tie_early');
            late = csr.validation.TraceScheduler('tie_late');
            empty = early.records();
            test.verifyEqual(height(empty),0); test.verifySize(empty.observed_hex,[0 1]);
            test.verifyClass(empty.observed_hex,'string'); test.verifyClass(empty.event_id,'uint64');
            test.verifyClass(empty.was_pending,'logical');
            id = early.scheduleAt(3.144961,@noop);
            one = early.records();
            test.verifyEqual(height(one),1); test.verifySize(one.scheduled_hex,[1 1]);
            test.verifyEqual(one.scheduled_hex,string(num2hex(3.144961)));
            test.verifyTrue(early.cancel(id));
            late.scheduleAt(3.144961,@noop); late.run(3.144961);
            rows = [empty;early.records();late.records()];
            test.verifyEqual(height(rows),4);
            test.verifyEqual(rows.('case'),["tie_early";"tie_early";"tie_late";"tie_late"]);
            test.verifyEqual(rows.operation,["schedule";"cancel";"schedule";"execute"]);
            test.verifyEqual(rows.callback(2),"");
            test.verifySize(rows.observed_hex,[4 1]);
            test.verifyEqual(rows.observed_hex(4),string(num2hex(3.144961)));
            test.verifyEqual(rows.event_id,uint64(ones(4,1)));
            test.verifyEqual(rows.parent_id,zeros(4,1,'uint64'));
            function noop(), end
        end
        function replayTablesNormalizeZeroOneAndManyRowsAtTheDiagnosticBoundary(test)
            prototype = struct('case','','node',0,'ordinal',0,'time_ns',0, ...
                'min',0,'max',0,'draw',0,'resolved',-1,'purpose','unresolved');
            usagePrototype = struct('case','','node',0,'supplied',0,'consumed',0,'unused',0);
            allDraws = csr.validation.edgeRecordTable(repmat(prototype,0,1),prototype);
            allUsage = csr.validation.edgeRecordTable(repmat(usagePrototype,0,1),usagePrototype);
            for name=["tie_early","tie_late"]
                tape = table([1;1;4],[1;2;1],zeros(3,1),31*ones(3,1),zeros(3,1), ...
                    'VariableNames',{'node','ordinal','min','max','draw'});
                owner = csr.validation.ReplayStreams(tape,@()3.144961,name);
                empty = csr.validation.edgeRecordTable(owner.draws(),prototype);
                test.verifyEqual(height(empty),0); test.verifySize(empty.('case'),[0 1]);
                test.verifyClass(empty.('case'),'string'); test.verifyClass(empty.draw,'double');
                owner.get(1,'mac'); owner.draw(1,0,31); owner.resolve(1,'prepare',0);
                one = csr.validation.edgeRecordTable(owner.draws(),prototype);
                test.verifyEqual(height(one),1); test.verifyEqual(one.('case'),name);
                test.verifyEqual(one.purpose,"prepare");
                owner.draw(1,0,31); owner.resolve(1,'advertise',0);
                rows = csr.validation.edgeRecordTable(owner.draws(),prototype);
                test.verifyEqual(rows.purpose,["prepare";"advertise"]);
                allDraws = [allDraws;rows]; %#ok<AGROW>
                allUsage = [allUsage;csr.validation.edgeRecordTable(owner.usage(),usagePrototype)]; %#ok<AGROW>
            end
            test.verifyEqual(allDraws.('case'),["tie_early";"tie_early";"tie_late";"tie_late"]);
            test.verifyEqual(allUsage.('case'),allDraws.('case'));
            test.verifyEqual(allUsage.supplied,[2;1;2;1]);
            test.verifyEqual(allUsage.consumed,[2;0;2;0]);
            test.verifyEqual(allUsage.unused,[0;1;0;1]);
        end
    end
end
