function tests=test_replay_lineage_shapes
% Isolated selector tests; no simulator model, writer, or installed callback.
tests=functiontests(localfunctions);
end

function test_ackFirstBundleKeepsLaterData(t)
ack=struct('Kind','ACK','App',struct());
data=makeData(9);
bundle=ack;
bundle.Segments={ack,data};
verifyEqual(t,ReplayLineageTap.applicationSources(bundle,0),9);
end

function test_dataFirstBundleCountsEachMemberOnce(t)
first=makeData(8);
bundle=first;
bundle.Segments={first,makeData(12)};
verifyEqual(t,ReplayLineageTap.applicationSources(bundle,0),[8 12]);
end

function test_ordinaryControlDoesNotHaveAnApp(t)
control=struct('Kind','CONTROL','App',struct());
verifyEmpty(t,ReplayLineageTap.applicationSources(control,0));
verifyEqual(t,ReplayLineageTap.applicationSources(makeData(10),0),10);
end

function test_malformedSegmentsReject(t)
f=makeData(8);
f.Segments=[makeData(8),makeData(9)];
checkReject(t,f);
f.Segments={};
checkReject(t,f);
f.Segments={makeData(8);makeData(9)};
checkReject(t,f);
f.Segments={makeData(8),42};
checkReject(t,f);
f.Segments=repmat({makeData(8)},1,1025);
checkReject(t,f);
end

function test_aggregateWithoutMembersRejects(t)
f=struct('Kind','AGGREGATE','App',struct());
checkReject(t,f);
end

function checkReject(t,f)
verifyError(t,@()ReplayLineageTap.applicationSources(f,0),'replayTap:Shape');
end

function f=makeData(src)
app=struct('Id',uint64(src),'SourceId',src,'DestinationId',1, ...
    'GeneratedSeconds',300,'ApplicationPayloadBytes',185);
f=struct('Kind','DATA','App',app);
end
