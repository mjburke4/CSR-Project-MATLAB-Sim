classdef TestBenchmarkAggregates < matlab.unittest.TestCase
    methods (Test)
        function usesSourceNetworkBytesAndHalfOpenBuckets(test)
            result = syntheticResult(); original = result;
            [series,provenance] = csr.analysis.benchmarkAggregates(result,aggregateOptions());
            test.verifyEqual(result,original);
            test.verifySize(series,[24 12]);
            test.verifyEqual(values(series,'Generator.Traffic Sent (packets/sec)'),[2;1;1]/60);
            test.verifyEqual(values(series,'Generator.Traffic Sent (bits/sec)'),[3072;4736;1536]/60);
            test.verifyEqual(values(series,'Generator.Packet Size (bits)'),[1536;4736;1536]);
            test.verifyEqual(values(series,'Sink.Traffic Received (packets)'),[1;1;1]);
            test.verifyEqual(values(series,'Sink.Traffic Received (bits)'),[1536;1536;4736]);
            test.verifyEqual(provenance.application_size_semantics.network_header_bytes,7);
            test.verifyEqual(provenance.application_size_semantics.legacy_trace_size_exclusion_bits,0);
            test.verifyEqual(provenance.source_file_sha256,repmat('b',1,64));
        end

        function delayIsGroupedByReceptionAndEmptyIsNotZero(test)
            [series,provenance] = csr.analysis.benchmarkAggregates(syntheticResult(),aggregateOptions());
            test.verifyEqual(values(series,'Sink.End-to-End Delay (seconds)'),[59;0.1;61],'AbsTol',1e-12);
            test.verifyEqual(provenance.application_accounting.in_window_sent,4);
            test.verifyEqual(provenance.application_accounting.in_window_received,3);
            test.verifyEqual(provenance.application_accounting.excluded_at_stop_sent,1);
            test.verifyEqual(provenance.application_accounting.excluded_at_stop_received,1);
            test.verifyEqual(provenance.application_accounting.pending,1);
        end

        function noSamplesRemainBlankWhileCountsAndRatesAreZero(test)
            [series,provenance] = csr.analysis.benchmarkAggregates(emptyResult(),aggregateOptions());
            meanRows = strcmp(series.aggregation,'bucket_sample_mean');
            test.verifyEqual(series.value(meanRows),repmat({''},6,1));
            test.verifyEqual(series.value_status(meanRows),repmat({'missing'},6,1));
            test.verifyEqual(series.value(~meanRows),repmat({'0'},18,1));
            test.verifyEqual(provenance.missing_sample_mean_bucket_ends_s.packet_size,[60 120 180]);
            test.verifyEqual(provenance.missing_sample_mean_bucket_ends_s.end_to_end_delay,[60 120 180]);
        end

        function fractionalGridAndFloatingBoundarySnapMatchSource(test)
            result = emptyResult(); result.Config.DurationSeconds = 0.3;
            result.ProtocolTrace = traceRow(0.1-5e-14,'app_generate',1,185);
            result.Statistics.Generated = 1; result.Statistics.Pending = 1;
            options = aggregateOptions(); options.BucketWidthSeconds = 0.1;
            [series,provenance] = csr.analysis.benchmarkAggregates(result,options);
            test.verifyEqual(values(series,'Generator.Traffic Sent (packets/sec)'),[0;10;0]);
            test.verifyEqual(provenance.window.bucket_count,3);
            % This offset is beyond the source quotient snap tolerance.
            result.ProtocolTrace.TimeSeconds = 0.1-2e-13;
            series = csr.analysis.benchmarkAggregates(result,options);
            test.verifyEqual(values(series,'Generator.Traffic Sent (packets/sec)'),[10;0;0]);
        end

        function stopAndAfterStopExclusionsAreDistinct(test)
            result = syntheticResult();
            result.ProtocolTrace.TimeSeconds(end) = 190;
            [~,provenance] = csr.analysis.benchmarkAggregates(result,aggregateOptions());
            test.verifyEqual(provenance.application_accounting.excluded_at_stop_received,0);
            test.verifyEqual(provenance.application_accounting.excluded_after_stop_received,1);
            test.verifyEqual(provenance.application_accounting.in_window_received,3);
        end

        function generatorGateAttemptsAreNotTrafficSent(test)
            result = syntheticResult();
            result.ApplicationAdmissionStatistics = table([8;9],[3;2],[1;0],[0;1], ...
                [1;0],[0;1],[3;5],'VariableNames',{'Attempts','Admitted', ...
                'BlockedDiscovery','BlockedTopology','BlockedGatewayRoute', ...
                'BlockedDestination','BlockedNsdp'});
            [series,provenance] = csr.analysis.benchmarkAggregates(result,aggregateOptions());
            test.verifyEqual(provenance.application_admission.Attempts,17);
            test.verifyEqual(provenance.application_admission.Admitted,5);
            test.verifyEqual(sum(values(series,'Generator.Traffic Sent (packets/sec)'))*60,4);
            result.ApplicationAdmissionStatistics.Attempts(1) = 9;
            test.verifyError(@()csr.analysis.benchmarkAggregates(result,aggregateOptions()), ...
                'csr:benchmark:Admission');
        end

        function duplicateAndUnknownApplicationIdentitiesFail(test)
            result = syntheticResult();
            result.ProtocolTrace.PacketId(strcmp(result.ProtocolTrace.Event,'app_generate')) = uint64(1);
            test.verifyError(@()csr.analysis.benchmarkAggregates(result,aggregateOptions()), ...
                'csr:benchmark:Identity');
            result = syntheticResult(); result.ProtocolTrace.PacketId(2) = uint64(999);
            test.verifyError(@()csr.analysis.benchmarkAggregates(result,aggregateOptions()), ...
                'csr:benchmark:Identity');
        end

        function sourceSizeAndFinalDestinationMustMatchGeneration(test)
            result = syntheticResult(); result.ProtocolTrace.ApplicationBytes(2) = 186;
            test.verifyError(@()csr.analysis.benchmarkAggregates(result,aggregateOptions()), ...
                'csr:benchmark:Identity');
            result = syntheticResult(); result.ProtocolTrace.NodeId(2) = 3;
            test.verifyError(@()csr.analysis.benchmarkAggregates(result,aggregateOptions()), ...
                'csr:benchmark:Identity');
        end

        function incompleteTraceAndCounterMismatchBlockAggregation(test)
            result = syntheticResult(); result.Statistics.OmittedTraceRecords = 1;
            test.verifyError(@()csr.analysis.benchmarkAggregates(result,aggregateOptions()), ...
                'csr:benchmark:TruncatedTrace');
            result = syntheticResult(); result.Statistics.ApplicationBytesReceived = 0;
            test.verifyError(@()csr.analysis.benchmarkAggregates(result,aggregateOptions()), ...
                'csr:benchmark:Accounting');
            result = syntheticResult(); result.ProtocolTrace(2,:) = [];
            test.verifyError(@()csr.analysis.benchmarkAggregates(result,aggregateOptions()), ...
                'csr:benchmark:Accounting');
        end

        function invalidWindowsAndUnorderedTracesFail(test)
            result = syntheticResult(); result.Config.DurationSeconds = 181;
            test.verifyError(@()csr.analysis.benchmarkAggregates(result,aggregateOptions()), ...
                'csr:benchmark:Window');
            result = syntheticResult(); result.ProtocolTrace = flipud(result.ProtocolTrace);
            test.verifyError(@()csr.analysis.benchmarkAggregates(result,aggregateOptions()), ...
                'csr:benchmark:Trace');
        end

        function scenarioAndSourceHashesAreRequired(test)
            options = aggregateOptions(); options = rmfield(options,'ScenarioSHA256');
            test.verifyError(@()csr.analysis.benchmarkAggregates(emptyResult(),options), ...
                'csr:benchmark:Options');
            options = aggregateOptions(); options.SourceFileSHA256 = 'unknown';
            test.verifyError(@()csr.analysis.benchmarkAggregates(emptyResult(),options), ...
                'csr:benchmark:Options');
        end

        function preservesSourceSnapshotAndReferenceIdentity(test)
            options = aggregateOptions(); options.SourceSnapshotSHA256 = repmat('d',1,64);
            result = syntheticResult();
            result.Metadata.SourceCommit = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b';
            [~,provenance] = csr.analysis.benchmarkAggregates(result,options);
            test.verifyEqual(provenance.source_snapshot_sha256,repmat('d',1,64));
            test.verifyEqual(provenance.ns3_reference_commit,result.Metadata.SourceCommit);
            test.verifyFalse(isfield(provenance,'output'));
        end

        function acceptsActualShortNetworkResultWithoutMutation(test)
            config = csr.scenario.routedNetwork('autonomous');
            config.Nwk.StartupMode = 'manual'; config.DurationSeconds = 0.1;
            config.Traffic.StartSeconds = 0.01; config.Traffic.PacketCount = 1;
            result = csr.runScenario(config); original = result;
            options = aggregateOptions(); options.BucketWidthSeconds = 0.1;
            [series,provenance] = csr.analysis.benchmarkAggregates(result,options);
            test.verifyEqual(result,original);
            test.verifyEqual(values(series,'Generator.Traffic Sent (packets/sec)'),10);
            test.verifyEqual(values(series,'Generator.Packet Size (bits)'),8*(64+7));
            test.verifyEqual(provenance.application_accounting.pending,1);
        end
    end
end

function result = syntheticResult()
trace = [traceRow(0,'app_generate',1,185);traceRow(59,'app_receive',1,185); ...
    traceRow(59.9,'app_generate',2,185);traceRow(60,'app_generate',3,585); ...
    traceRow(60,'app_receive',2,185);traceRow(120,'app_generate',4,185); ...
    traceRow(121,'app_receive',3,585);traceRow(180,'app_generate',5,185); ...
    traceRow(180,'app_receive',4,185)];
statistics = struct('Generated',5,'Received',4,'Dropped',0,'Pending',1, ...
    'ApplicationBytesReceived',1140,'OmittedTraceRecords',0);
result = struct('Config',struct('DurationSeconds',180),'Statistics',statistics, ...
    'ProtocolTrace',trace);
end

function result = emptyResult()
result = syntheticResult(); result.ProtocolTrace = result.ProtocolTrace([],:);
names = fieldnames(result.Statistics);
for k = 1:numel(names), result.Statistics.(names{k}) = 0; end
end

function options = aggregateOptions()
options = struct('Scenario','synthetic-test-input','ScenarioSHA256',repmat('a',1,64), ...
    'ProfileID','synthetic-explicit-profile','SourceFile','protocol-trace.csv', ...
    'SourceFileSHA256',repmat('b',1,64));
end

function row = traceRow(time,event,id,bytes)
node = 1; peer = 2;
if strcmp(event,'app_receive'), node = 2; peer = 1; end
row = table(time,{event},node,peer,uint64(id),bytes,0, ...
    'VariableNames',{'TimeSeconds','Event','NodeId','PeerId','PacketId','ApplicationBytes','Dscp'});
end

function result = values(series,name)
result = str2double(series.value(strcmp(series.statistic,name)));
end
