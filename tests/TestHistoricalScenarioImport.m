classdef TestHistoricalScenarioImport < matlab.unittest.TestCase
    properties
        Folder
    end
    methods (TestMethodSetup)
        function folder(test)
            test.Folder = tempname; mkdir(test.Folder);
            test.addTeardown(@()rmdir(test.Folder,'s'));
        end
    end
    methods (Test)
        function historicalProfileRequiresExplicitOptIn(test)
            path = test.fixture();
            test.verifyError(@()csr.scenario.importNs3(path),'csr:scenario:ImportProfile');
            config = csr.scenario.importNs3(path,struct('HistoricalBenchmark',true));
            test.verifyEqual(config.ApplicationGenerator,'historical-opnet-gated');
            test.verifyEqual(config.ApplicationFlowLimit,0);
            test.verifyEqual(config.ApplicationProfile,'legacy-send-only-no-dscp');
            test.verifyEqual(config.Mac.SlotProfile,'hist-2014-next-tslot-modulo-probe');
            test.verifyEqual(config.Nwk.SecurityProfile,'behavioral-hist-adb97c54-bare-size-only');
            test.verifyEqual(config.Radio.EnvelopeProfile,'bare');
            test.verifyTrue(config.SharedScenario.RunOptions.opnetAppGating);
            test.verifyTrue(config.SharedScenario.RunOptions.stochasticSyncThreshold);
            test.verifyTrue(all(arrayfun(@(n)n.RadioProfile.StochasticSyncThreshold,config.Nodes)));
        end

        function adaptiveLimitsAndPacketExclusionsArePreserved(test)
            config = csr.scenario.importNs3(test.fixture(),struct('HistoricalBenchmark',true));
            info = config.Nwk.Routing.LocalInfo;
            test.verifyEqual([info.MinSpeedKbps,info.MaxSpeedKbps],[8,128]);
            test.verifyEqual([info.MinPowerDbmX10,info.MaxPowerDbmX10,info.LinkMarginDbX10],[-360,330,120]);
            test.verifyTrue(config.Nwk.AdaptiveLinkControl);
            test.verifyEqual(config.Radio.RateKeyKbps,8);
            test.verifyEqual(config.Nodes(1).RadioProfile.TxPowerDbm,33);
            test.verifyEqual(config.Traffic.ApplicationPayloadBytes,185);
            packet = csr.packet(uint64(1),config.Traffic,300,config.Radio);
            test.verifyEqual(packet.WirePayloadBytes,217);
            test.verifyEqual(packet.ApplicationPayloadBytes+7,192); % br_Network=N-8
        end

        function benchmarkCatalogImportsWithoutChangingCanonicalInputs(test)
            root = fileparts(fileparts(mfilename('fullpath')));
            names = {'campus_multihop_6000','two_node_admission_1200','three_node_contention_360'};
            attempts = [1710000,45000,60000]; nodeCounts = [7,2,3];
            for k = 1:numel(names)
                path = fullfile(root,'scenarios','benchmarks',[names{k},'.csv']);
                before = csr.validation.Artifacts.sha256(path);
                config = csr.scenario.importNs3(path,struct('HistoricalBenchmark',true));
                test.verifyEqual(sum([config.Traffic.PacketCount]),attempts(k));
                test.verifyEqual(numel(config.Nodes),nodeCounts(k));
                test.verifyEqual(config.SharedScenario.SourceSHA256,before);
                test.verifyEqual(csr.validation.Artifacts.sha256(path),before);
                test.verifyTrue(all([config.SharedScenario.OriginalNodeApplicationSettings.Present]));
            end
        end

        function redundantNodeApplicationSettingsCannotDisagreeWithFlows(test)
            changes = {3,'interarrival_s','0.02';3,'packet_bytes','200';3,'start_s','301'};
            path = test.fixture(changes);
            test.verifyError(@()csr.scenario.importNs3(path,struct('HistoricalBenchmark',true)), ...
                'csr:scenario:ImportFlow');
            path = test.fixture(changes(1,:));
            test.verifyError(@()csr.scenario.importNs3(path,struct('HistoricalBenchmark',true)), ...
                'csr:scenario:ImportRows');
        end

        function admittedCapDoesNotTruncateScheduledAttempts(test)
            path = test.fixture();
            config = csr.scenario.importNs3(path,struct('HistoricalBenchmark',true,'FlowLimit',2));
            test.verifyEqual(config.ApplicationFlowLimit,2);
            test.verifyEqual(config.Traffic.PacketCount,285000); % [300,6000) / .02
            test.verifyEqual(config.SharedScenario.FlowLimit,2);
            test.verifyEqual(config.Traffic.StartSeconds,300);
            test.verifyEqual(config.Traffic.IntervalSeconds,0.02);
        end

        function atomicProfileAndExecutableBindingFailClosed(test)
            changes = {1,'source_executable_sha256',repmat('a',1,64); ...
                1,'source_sha256','synthetic-shared-scenario-v1'; ...
                1,'mac_profile','current-fine-free-slot'; ...
                1,'ack_envelope_profile','production-pairwise16'; ...
                1,'hop_security_profile','hist-dd3f38e8-bare'};
            for k = 1:size(changes,1)
                path = test.fixture(changes(k,:));
                test.verifyError(@()csr.scenario.importNs3(path,struct('HistoricalBenchmark',true)), ...
                    'csr:scenario:ImportProfile');
            end
        end

        function historicalFlowDirectionsAreChecked(test)
            changes = {4,'flow_dscp','1';4,'flow_src','1'; ...
                3,'node_type','gateway';4,'flow_destination_mode','random_route_or_neighbor'};
            for k = 1:size(changes,1)
                path = test.fixture(changes(k,:));
                expected = 'csr:scenario:ImportProfile';
                if k == 2, expected = 'csr:scenario:ImportFlow'; end
                test.verifyError(@()csr.scenario.importNs3(path,struct('HistoricalBenchmark',true)),expected);
            end
        end

        function dd3fTupleRetainsDynamicGatewayFlow(test)
            changes = {1,'application_profile','legacy-send-to-from-no-dscp'; ...
                1,'mac_profile','hist-2015-fine-one-based-table-no-avoid'; ...
                1,'hop_security_profile','hist-dd3f38e8-bare'; ...
                1,'source_executable_sha256', ...
                'dd3f38e8d33700b61f9e360a737ba34e56cb75b2570eb2960a02de381ed0fff0'; ...
                5,'flow_src','1';5,'flow_dst','2';5,'flow_destination_mode','random_route_or_neighbor'};
            path = test.fixture(changes);
            config = csr.scenario.importNs3(path,struct('HistoricalBenchmark',true));
            test.verifyEqual(config.Nwk.SecurityProfile,'behavioral-hist-dd3f38e8-bare-size-only');
            test.verifyEqual({config.Traffic.DestinationMode},{'fixed','random_route_or_neighbor'});
            test.verifyEqual([config.Traffic.SourceId],[2,1]);
        end

        function unsupportedTerrainAndHeterogeneousLimitsRemainExplicit(test)
            changes = {1,'tmm','1';3,'height_m','100';3,'min_speed_kbps','16'; ...
                3,'min_power_dbm','-30';3,'link_margin_db','10';1,'reservation_control_start_s','1'};
            for k = 1:size(changes,1)
                path = test.fixture(changes(k,:));
                test.verifyError(@()csr.scenario.importNs3(path,struct('HistoricalBenchmark',true)), ...
                    'csr:scenario:ImportUnsupported');
            end
        end

        function historicalProvenanceRetainsExactInputAndIndependentOrigin(test)
            path = test.fixture();
            config = csr.scenario.importNs3(path,struct('HistoricalBenchmark',true));
            test.verifyEqual(config.SharedScenario.SourceSHA256,csr.validation.Artifacts.sha256(path));
            test.verifyEqual(config.SharedScenario.OriginalSourceSHA256,repmat('b',1,64));
            test.verifyEqual(config.SharedScenario.SourceExecutableSHA256, ...
                'adb97c54f7566439f1404e972d3d777a3bca613e2a965bf12f03353fb009d9af');
        end

        function optionShapeAndStopBoundaryAreRejected(test)
            path = test.fixture();
            bad = {struct('HistoricalBenchmark',1),struct('HistoricalBenchmark',[true,false]), ...
                struct('HistoricalBenchmark',true,'FlowLimit',-1)};
            for k = 1:numel(bad)
                test.verifyError(@()csr.scenario.importNs3(path,bad{k}),'csr:scenario:ImportOptions');
            end
            path = test.fixture({4,'flow_start_s','6000'});
            test.verifyError(@()csr.scenario.importNs3(path,struct('HistoricalBenchmark',true)), ...
                'csr:scenario:ImportUnsupported');
        end
    end
    methods (Access=private)
        function path = fixture(test,changes)
            if nargin < 2, changes = cell(0,3); end
            run = struct('schema','csr-opnet-scenario-v1','record','run', ...
                'scenario','historical_import_contract','source_sha256',repmat('b',1,64), ...
                'duration_s','6000','seed','128','tmm','0', ...
                'application_profile','legacy-send-only-no-dscp', ...
                'mac_profile','hist-2014-next-tslot-modulo-probe', ...
                'hop_security_profile','hist-adb97c54-bare', ...
                'source_executable_sha256', ...
                'adb97c54f7566439f1404e972d3d777a3bca613e2a965bf12f03353fb009d9af');
            gateway = struct('schema','csr-opnet-scenario-v1','record','node', ...
                'node_id','1','name','gateway','node_type','gateway','x_m','0','y_m','0', ...
                'height_m','1','min_speed_kbps','8','max_speed_kbps','128', ...
                'min_power_dbm','-36','max_power_dbm','33','link_margin_db','12', ...
                'ecc_threshold','0.1','rx_frequency_hz','400000000','tx_frequency_hz','400000000');
            node = gateway; node.node_id = '2'; node.name = 'source';
            node.node_type = 'routable'; node.x_m = '100';
            flow = struct('schema','csr-opnet-scenario-v1','record','flow', ...
                'flow_src','2','flow_dst','1','flow_start_s','300','flow_interval_s','0.02', ...
                'flow_packet_bytes','200','flow_dscp','0','flow_destination_mode','fixed');
            records = {run,gateway,node,flow};
            if ~isempty(changes)
                for k = 5:max([changes{:,1}]), records{k} = flow; end %#ok<AGROW>
            end
            for k = 1:size(changes,1), records{changes{k,1}}.(changes{k,2}) = changes{k,3}; end
            headers = {};
            for k = 1:numel(records), headers = union(headers,fieldnames(records{k})','stable'); end
            lines = {strjoin(headers,',')};
            for k = 1:numel(records)
                row = repmat({''},1,numel(headers));
                for j = 1:numel(headers)
                    if isfield(records{k},headers{j}), row{j} = records{k}.(headers{j}); end
                end
                lines{end+1} = strjoin(row,','); %#ok<AGROW>
            end
            path = fullfile(test.Folder,'scenario.csv');
            fid = fopen(path,'wb'); cleanup = onCleanup(@()fclose(fid)); %#ok<NASGU>
            fwrite(fid,[strjoin(lines,sprintf('\n')),sprintf('\n')],'char');
        end
    end
end
