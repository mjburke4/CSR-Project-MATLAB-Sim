classdef TestNs3ScenarioImport < matlab.unittest.TestCase
    % Shared imports fail before scheduling when source behavior is unsupported.
    properties
        Folder
    end
    methods (TestMethodSetup)
        function temporaryFiles(test)
            fixture = test.applyFixture(matlab.unittest.fixtures.TemporaryFolderFixture);
            test.Folder = fixture.Folder;
        end
    end
    methods (Test)
        function currentProfileMapsBytesAndRealPhy(test)
            path = test.fixture();
            config = csr.scenario.importNs3(path);
            test.verifyEqual(config.Stack,'network');
            test.verifyEqual(config.Traffic.ApplicationPayloadBytes,64);
            test.verifyEqual(config.Traffic.PacketCount,3);
            test.verifyEqual(config.Traffic.Dscp,2);
            test.verifyEqual([config.Nodes.Capability],[2,1]);
            test.verifyEqual(config.Nwk.Routing.LocalInfo.MinPowerDbmX10,300);
            test.verifyFalse(config.Nwk.AdaptiveLinkControl);
            test.verifyEqual(config.Nwk.StartupDelaySeconds,10);
            test.verifyEqual(config.Nwk.DiscoveryDurationSeconds,30);
            test.verifyEqual(config.Mac.WakeCycleSeconds,0.988);
            test.verifyEqual(config.Channel.Model,'csr-phy');
            test.verifyEqual(config.Channel.PropagationSpeedMps,3e8);
            radio = config.Nodes(1).RadioProfile;
            test.verifyEqual(radio.ClosureMode,'EARTH_LINE_OF_SIGHT');
            test.verifyEmpty(radio.ClosureDelegate);
            test.verifyEqual(radio.PropagationModel,'OPNET_THREE_PATH');
            test.verifyFalse(radio.StochasticSyncThreshold);
            test.verifyEqual([radio.TxBaseFrequencyHz,radio.RxBaseFrequencyHz],[400e6,400e6]);
            test.verifyEqual([radio.TxBwHz,radio.RxBwHz],[1e6,1e6]);
            test.verifyEqual(radio.NoiseFloorDbm,-106.975);
            test.verifyEqual(config.Radio.EnvelopeProfile,'pairwise16-size-only');
            test.verifyFalse(isfield(config.Traffic,'Path'));
        end
        function exactSourceProvenanceAndOptions(test)
            path = test.fixture();
            config = csr.scenario.importNs3(string(path),struct('FlowLimit',uint8(2),'Backend',"wireless-clock"));
            evidence = config.SharedScenario;
            test.verifyEqual(config.Backend,'wireless-clock');
            test.verifyEqual(config.Traffic.PacketCount,2);
            test.verifyEqual(evidence.FlowLimit,2);
            test.verifyEqual(evidence.SourceCommit,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b');
            test.verifyEqual(evidence.SourceSHA256,test.hash(path));
            test.verifyEqual(evidence.ApplicationPayloadExclusionBytes,15);
            test.verifyEqual(evidence.ConfiguredFlowPacketBytes,79);
            test.verifyFalse(evidence.RunOptions.opnetAppGating);
            test.verifyFalse(evidence.RunOptions.stochasticSyncThreshold);
            test.verifyTrue(evidence.RunOptions.gatewayDiscovery);
        end
        function nodesSortAndOrdinaryNodesCannotRelay(test)
            path = test.fixture({2,'node_id','2';3,'node_id','1';3,'node_type','ordinary'});
            config = csr.scenario.importNs3(path);
            test.verifyEqual([config.Nodes.Id],[1,2]);
            test.verifyEqual([config.Nodes.Capability],[0,2]);
            test.verifyEqual([config.Nodes.TransitForwardingEnabled],[false,true]);
            test.verifyEqual(config.SharedScenario.NodeNames,{'relay','gateway'});
        end
        function strictStopBoundaryAndPerFlowCap(test)
            path = test.fixture({1,'duration_s','150';4,'flow_start_s','120';4,'flow_interval_s','15'});
            config = csr.scenario.importNs3(path,struct('FlowLimit',10));
            test.verifyEqual(config.Traffic.PacketCount,2); % 120,135; no repeat at150
            path = test.fixture({4,'flow_start_s','201'});
            config = csr.scenario.importNs3(path);
            test.verifyEqual(config.Traffic.PacketCount,0);
            path = test.fixture({4,'flow_start_s','200'});
            test.verifyError(@()csr.scenario.importNs3(path),'csr:scenario:ImportUnsupported');
        end
        function fractionalIntervalsUseNanosecondBoundary(test)
            path = test.fixture({1,'duration_s','0.3';4,'flow_start_s','0';4,'flow_interval_s','0.1'});
            config = csr.scenario.importNs3(path,struct('FlowLimit',10));
            test.verifyEqual(config.Traffic.PacketCount,3);
        end
        function flowOrderAndCapsRemainIndependent(test)
            path = test.fixture({5,'flow_src','1';5,'flow_dst','2'; ...
                5,'flow_start_s','195';5,'flow_dscp','5'});
            config = csr.scenario.importNs3(path,struct('FlowLimit',2));
            test.verifyEqual([config.Traffic.SourceId],[2,1]);
            test.verifyEqual([config.Traffic.Dscp],[2,5]);
            test.verifyEqual([config.Traffic.PacketCount],[2,1]);
            test.verifySize(config.Traffic,[1,2]);
            test.verifyEqual(config.SharedScenario.ConfiguredFlowPacketBytes,[79,79]);
        end
        function minimumPacketHasZeroApplicationPayload(test)
            path = test.fixture({4,'flow_packet_bytes','15'});
            config = csr.scenario.importNs3(path);
            test.verifyEqual(config.Traffic.ApplicationPayloadBytes,0);
            for value = {'14','65551'}
                path = test.fixture({4,'flow_packet_bytes',value{1}});
                test.verifyError(@()csr.scenario.importNs3(path),'csr:scenario:ImportNumber');
            end
        end
        function highRateExtensionsRemainExplicit(test)
            for rate = [500,1000]
                token = sprintf('%d',rate);
                path = test.fixture({2,'min_speed_kbps',token;2,'max_speed_kbps',token; ...
                    3,'min_speed_kbps',token;3,'max_speed_kbps',token});
                config = csr.scenario.importNs3(path);
                test.verifyEqual(config.Radio.RateKeyKbps,rate);
                test.verifyTrue(config.SharedScenario.HighRateExtension);
            end
        end
        function profileDefaultsAndHistoricalTuplesAreRejected(test)
            rows = {1,'application_profile','';1,'application_profile','legacy-send-only-no-dscp'; ...
                1,'mac_profile','hist-2014-next-tslot-modulo-probe'; ...
                1,'hop_security_profile','hist-adb97c54-bare'; ...
                1,'ack_envelope_profile','hist-adb97c54-bare'};
            for index = 1:size(rows,1)
                path = test.fixture(rows(index,:));
                test.verifyError(@()csr.scenario.importNs3(path),'csr:scenario:ImportProfile');
            end
        end
        function unsupportedPopulatedFieldsAndModesFailClosed(test)
            rows = {1,'tmm','1';1,'reservation_control_start_s','1'; ...
                1,'source_executable_sha256',repmat('a',1,64); ...
                2,'forced_reservation_slot','5';2,'interarrival_s','10'; ...
                4,'flow_destination_mode','random_route_or_neighbor'; ...
                1,'unmodeled_feature','enabled';2,'flow_dscp','3'};
            for index = 1:size(rows,1)
                path = test.fixture(rows(index,:));
                test.verifyError(@()csr.scenario.importNs3(path),'csr:scenario:ImportUnsupported');
            end
            path = test.fixture({1,'future_blank_field',''});
            config = csr.scenario.importNs3(path);
            test.verifyEqual(config.Traffic.PacketCount,3);
        end
        function varyingLinkLimitsAndHeightsFailClosed(test)
            rows = {2,'max_speed_kbps','128';2,'min_power_dbm','0'; ...
                2,'link_margin_db','9';2,'height_m','2';2,'link_margin_db','10.05'};
            for index = 1:size(rows,1)
                path = test.fixture(rows(index,:));
                test.verifyError(@()csr.scenario.importNs3(path),'csr:scenario:ImportUnsupported');
            end
        end
        function rejectsDuplicateNodesAndBadEndpoints(test)
            for change = {{3,'node_id','1'},{3,'name','gateway'}}
                path = test.fixture(change{1});
                test.verifyError(@()csr.scenario.importNs3(path),'csr:scenario:ImportNode');
            end
            for value = {'1','3'}
                path = test.fixture({4,'flow_src',value{1}});
                test.verifyError(@()csr.scenario.importNs3(path),'csr:scenario:ImportFlow');
            end
        end
        function invalidNumbersCannotBeSilentlyCoerced(test)
            rows = {1,'seed','0';1,'seed','4294944443';1,'duration_s','NaN'; ...
                2,'node_id','010';2,'node_id','0x2';2,'x_m','1junk'; ...
                2,'ecc_threshold','1.1';4,'flow_dscp','8';4,'flow_interval_s','0'; ...
                4,'flow_packet_bytes','79.0'};
            for index = 1:size(rows,1)
                path = test.fixture(rows(index,:));
                test.verifyError(@()csr.scenario.importNs3(path),'csr:scenario:ImportNumber');
            end
            path = test.fixture({4,'flow_interval_s','0.0000000015'});
            test.verifyError(@()csr.scenario.importNs3(path),'csr:scenario:ImportUnsupported');
        end
        function optionsRejectUnknownOrUnboundedValues(test)
            path = test.fixture();
            bad = {struct('flowLimit',3),struct('FlowLimit',0),struct('FlowLimit',Inf), ...
                struct('FlowLimit',1.5),struct('FlowLimit',[1,2]), ...
                struct('Backend','native'),struct('Backend',{{'portable'}})};
            for index = 1:numel(bad)
                test.verifyError(@()csr.scenario.importNs3(path,bad{index}),'csr:scenario:ImportOptions');
            end
        end
        function textQuotingAndWindowsLineEndingsRetainRowShapes(test)
            path = test.fixture({1,'scenario','comma, and "quote"';2,'name','gateway, "one"'},true);
            config = csr.scenario.importNs3(path);
            test.verifyEqual(config.Name,'comma, and "quote"');
            test.verifyEqual(config.SharedScenario.NodeNames{1},'gateway, "one"');
            test.verifySize(config.Nodes,[1,2]);
            test.verifySize(config.Traffic,[1,1]);
            test.verifyEqual(config.SharedScenario.SourceSHA256,test.hash(path));
        end
        function metadataScaleDoesNotScaleMetersAgain(test)
            path = test.fixture({1,'coordinate_scale_m_per_unit','1000';2,'height_m','1.05';3,'height_m','1.05'});
            config = csr.scenario.importNs3(path);
            test.verifyEqual(config.Nodes(2).PositionMeters,[100,0,1.05]);
            test.verifyEqual(config.Nodes(2).RadioProfile.TxHeightMeters,1.05);
            test.verifyEqual(config.SharedScenario.CoordinateScaleMetersPerUnit,1000);
        end
        function malformedCsvIsRejected(test)
            contents = {'schema,record,record\n', ...
                'schema,record\ncsr-opnet-scenario-v1,run,extra\n', ...
                'schema,record\n"unterminated,run\n', ...
                'schema,record\n"closed"trailing,run\n'};
            for index = 1:numel(contents)
                path = fullfile(test.Folder,sprintf('bad%d.csv',index));
                test.write(path,sprintf(contents{index}));
                test.verifyError(@()csr.scenario.importNs3(path),'csr:scenario:ImportCsv');
            end
        end
        function runAndSchemaStructureAreRequired(test)
            bodies = {'csr-opnet-scenario-v1,node\n', ...
                'csr-opnet-scenario-v1,run\ncsr-opnet-scenario-v1,run\n', ...
                'csr-opnet-scenario-v1,unknown\n','other-schema,run\n'};
            for index = 1:numel(bodies)
                path = fullfile(test.Folder,sprintf('rows%d.csv',index));
                test.write(path,sprintf(['schema,record\n',bodies{index}]));
                expected = 'csr:scenario:ImportRows';
                if index == 4, expected = 'csr:scenario:ImportSchema'; end
                test.verifyError(@()csr.scenario.importNs3(path),expected);
            end
        end
        function noFlowInputKeepsAnEmptyTypedTrafficArray(test)
            path = test.fixture();
            lines = regexp(fileread(path),'\n','split');
            test.write(path,strjoin(lines(1:4),sprintf('\n')));
            config = csr.scenario.importNs3(path);
            test.verifyEmpty(config.Traffic);
            test.verifyTrue(isfield(config.Traffic,'ApplicationPayloadBytes'));
        end
        function syntheticOriginIsNotAnOpnetArchiveHash(test)
            path = test.fixture({1,'source_sha256','synthetic-shared-scenario-v1'});
            config = csr.scenario.importNs3(path);
            test.verifyEmpty(config.SharedScenario.OriginalSourceSHA256);
            test.verifyEqual(config.SharedScenario.OriginalSourceLabel,'synthetic-shared-scenario-v1');
            test.verifyEqual(config.SharedScenario.SourceSHA256,test.hash(path));
        end
    end
    methods (Access=private)
        function path = fixture(test,changes,windows)
            if nargin < 2, changes = cell(0,3); end
            if nargin < 3, windows = false; end
            run = struct('record','run','schema','csr-opnet-scenario-v1', ...
                'scenario','shared_test','duration_s','200','seed','128','tmm','0', ...
                'application_profile','current-send-only','mac_profile','current-fine-free-slot', ...
                'hop_security_profile','production-pairwise16');
            gateway = struct('record','node','schema','csr-opnet-scenario-v1', ...
                'node_id','1','name','gateway','node_type','gateway','x_m','0','y_m','0', ...
                'height_m','1','min_speed_kbps','8','max_speed_kbps','8', ...
                'min_power_dbm','30','max_power_dbm','30','link_margin_db','10', ...
                'ecc_threshold','0.1','rx_frequency_hz','400000000','tx_frequency_hz','400000000');
            relay = gateway; relay.node_id = '2'; relay.name = 'relay';
            relay.node_type = 'routable'; relay.x_m = '100';
            flow = struct('record','flow','schema','csr-opnet-scenario-v1', ...
                'flow_src','2','flow_dst','1','flow_start_s','120','flow_interval_s','15', ...
                'flow_packet_bytes','79','flow_dscp','2','flow_destination_mode','fixed');
            records = {run,gateway,relay,flow};
            if ~isempty(changes)
                for index = 5:max([changes{:,1}])
                    records{index} = flow; %#ok<AGROW>
                end
            end
            for index = 1:size(changes,1)
                records{changes{index,1}}.(changes{index,2}) = changes{index,3};
            end
            headers = {};
            for index = 1:numel(records)
                headers = union(headers,reshape(fieldnames(records{index}),1,[]),'stable');
            end
            lines = cell(1,numel(records)+1); lines{1} = strjoin(headers,',');
            for index = 1:numel(records)
                cells = repmat({''},1,numel(headers));
                for column = 1:numel(headers)
                    if isfield(records{index},headers{column})
                        token = records{index}.(headers{column});
                        cells{column} = ['"',strrep(token,'"','""'),'"'];
                    end
                end
                lines{index+1} = strjoin(cells,',');
            end
            lineEnding = sprintf('\n'); if windows, lineEnding = sprintf('\r\n'); end
            path = [tempname(test.Folder),'.csv'];
            test.write(path,[strjoin(lines,lineEnding),lineEnding]);
        end
        function write(~,path,text)
            fid = fopen(path,'wb');
            if fid < 0, error('csr:test:FileOpen','Cannot create CSV fixture.'); end
            cleanup = onCleanup(@()fclose(fid)); %#ok<NASGU>
            fwrite(fid,unicode2native(text,'UTF-8'),'uint8');
        end
        function digest = hash(~,path)
            fid = fopen(path,'rb');
            cleanup = onCleanup(@()fclose(fid)); %#ok<NASGU>
            bytes = fread(fid,Inf,'*uint8');
            hasher = javaMethod('getInstance','java.security.MessageDigest','SHA-256');
            hasher.update(typecast(bytes,'int8'));
            digest = lower(reshape(dec2hex(typecast(hasher.digest(),'uint8'),2).',1,[]));
        end
    end
end
